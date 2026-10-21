"""Private SQLite database and compressed, content-addressed source responses."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ..errors import AccessStopped, CollectionError
from ..paths import LOCAL_DATA

DEFAULT_DB = LOCAL_DATA / "database" / "market.sqlite"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class Store:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path).resolve()
        # Databases and raw responses must remain in the ignored local data tree.
        if not self.path.is_relative_to(LOCAL_DATA.resolve()):
            raise CollectionError("Database must be inside data/local/ to keep private records out of Git")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.row_factory = sqlite3.Row
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in {0, 1, 2}:
            self.db.close()
            raise CollectionError("Unsupported history database schema")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
        # Early local pilots tagged event jobs as hourly. Preserve IDs and cursors.
        duplicates = self.db.execute("""SELECT 1 FROM jobs WHERE kind='trades'
            GROUP BY market_hash_name,platform,style,start_time,end_time HAVING count(*)>1 LIMIT 1""").fetchone()
        if duplicates:
            self.db.close()
            raise CollectionError("Overlapping legacy trade jobs require review; cursors were not changed")
        with self.db:
            self.db.execute("UPDATE jobs SET period='event' WHERE kind='trades' AND period!='event'")
            self.db.execute("PRAGMA user_version=2")
        self.raw_bytes = sum(p.stat().st_size for p in (self.path.parent / "raw").rglob("*.json.gz"))

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def worker_lock(self):
        """OS-held lock releases on crashes; never remove another worker's lock file."""
        lock = self.path.with_suffix(".worker.lock")
        with lock.open("a+b") as handle:
            if lock.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise AccessStopped("Another crawler holds this database worker lock") from None
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def archive(self, endpoint, params, observed, raw, status, code):
        digest = hashlib.sha256(raw).hexdigest() if raw else None
        relative = None
        if raw:
            target = self.path.parent / "raw" / digest[:2] / (digest + ".json.gz")
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                temporary = target.with_suffix(".tmp")
                temporary.write_bytes(gzip.compress(raw, mtime=0))
                temporary.replace(target)
                self.raw_bytes += target.stat().st_size
            relative = target.relative_to(self.path.parent).as_posix()
        with self.db:
            result = self.db.execute(
                "INSERT INTO requests(endpoint,params_json,collected_at,http_status,error_code,raw_path,raw_sha256) VALUES(?,?,?,?,?,?,?)",
                (endpoint, compact(params), observed, status, code if type(code) is int else None, relative, digest),
            )
        return result.lastrowid

    def disk_bytes(self):
        return self.raw_bytes + sum(p.stat().st_size for p in
            (self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")) if p.exists())
