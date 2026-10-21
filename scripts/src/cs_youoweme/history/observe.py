"""Resumable, bounded forward observation, started explicitly by the local user."""
from __future__ import annotations

from contextlib import closing
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
import uuid

from .. import __version__
from ..collectors.website import ITEM, MARKET_COMPARISON, WebsiteClient
from ..errors import AccessStopped, CollectionError
from ..paths import ROOT, LOCAL_DATA, CHINA
from .normalize import number, seconds
from .store import Store
from .verification import uu_snapshot

SPECIMENS = (
    {"name": "AK-47 | The Oligarch (Field-Tested)", "item_id": "1442265962434310144", "template_id": "113014"},
    {"name": "M4A1-S | Printstream (Factory New)", "item_id": "808857281272217600", "template_id": "46298"},
)
RUNS = LOCAL_DATA / "staging/steamdt"
POINTER = LOCAL_DATA / "manifests/uu_observe_last_run.json"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
TERMINAL = {"completed", "access_blocked", "safe_error", "request_budget", "storage_budget"}
SOURCE_FILES = (
    "__init__.py", "collectors/website.py", "history/observe.py", "history/store.py",
    "history/verification.py", "history/normalize.py", "history/schema.sql", "errors.py", "paths.py", "transport.py",
)


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="microseconds")


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes():
    base = ROOT / "scripts/src/cs_youoweme"
    return {str(Path("scripts/src/cs_youoweme") / name).replace("\\", "/"): _hash(base / name) for name in SOURCE_FILES}


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _run_path(value):
    path = Path(value).resolve()
    if path.parent != RUNS.resolve() or not path.name.startswith("p03_steamdt_observe_"):
        raise CollectionError("Choose an observation run under data/local/staging/steamdt")
    if not (path / "manifest.json").is_file() or not (path / "observations.sqlite").is_file():
        raise CollectionError("Observation manifest/database missing")
    return path


def _manifest(path):
    value = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if value.get("schema_version") != "observe-1.0" or value.get("specimens") != list(SPECIMENS):
        raise CollectionError("Observation scope/schema differs from this collector")
    if value["end_epoch"] != value["start_epoch"] + value["hours"] * 3600 or value["slots"] != math.ceil(value["hours"] * 60 / value["interval_minutes"]):
        raise CollectionError("Frozen observation schedule is inconsistent")
    with closing(sqlite3.connect((path / "observations.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
        original_hash = db.execute("SELECT manifest_sha256 FROM observer_control WHERE id=1").fetchone()[0]
    if original_hash != _hash(path / "manifest.json"):
        raise CollectionError("Frozen observation manifest changed; resume refused")
    return value


def _schema(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS observer_control (
            id INTEGER PRIMARY KEY CHECK(id=1), status TEXT NOT NULL,
            updated_at TEXT NOT NULL, last_error TEXT, manifest_sha256 TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS observer_samples (
            slot INTEGER NOT NULL, item TEXT NOT NULL, due_at TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending', metadata_request INTEGER,
            comparison_request INTEGER, observed_at TEXT, snapshot_json TEXT,
            error TEXT, PRIMARY KEY(slot,item));
        CREATE TABLE IF NOT EXISTS observer_attempts (
            attempt_id INTEGER PRIMARY KEY, slot INTEGER NOT NULL, item TEXT,
            endpoint TEXT NOT NULL, reserved_at TEXT NOT NULL,
            request_id INTEGER, response_available_at TEXT);
    """)


def create_run(hours=24, interval_minutes=60, max_storage_mb=64, *, _clock=time.time):
    """Create a fresh empty run only; this function never sends an HTTP request."""
    if type(hours) is not int or not 1 <= hours <= 24:
        raise CollectionError("Duration must be an integer from 1 to 24 hours")
    if type(interval_minutes) is not int or not 60 <= interval_minutes <= 240:
        raise CollectionError("Sampling interval must be 60-240 minutes")
    if type(max_storage_mb) is not int or not 8 <= max_storage_mb <= 64:
        raise CollectionError("Storage stop budget must be 8-64 MiB")
    RUNS.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(RUNS).free < (max_storage_mb + 128) * 1024 * 1024:
        raise CollectionError("Insufficient free disk for the bounded run")
    started = _clock()
    ident = "p03_steamdt_observe_" + datetime.fromtimestamp(started, CHINA).strftime("%Y%m%dT%H%M%S+0800_") + uuid.uuid4().hex[:6]
    path = RUNS / ident
    path.mkdir(exist_ok=False)
    source_hashes = _source_hashes()
    source_dir = ROOT / "scripts/local/pilot_sources" / ident
    source_dir.mkdir(parents=True, exist_ok=False)
    for relative in source_hashes:
        target = source_dir / relative.removeprefix("scripts/src/cs_youoweme/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    slots = math.ceil(hours * 60 / interval_minutes)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    manifest = {"schema_version": "observe-1.0", "run_id": ident, "asset_status": "candidate-L0",
                "code_version": __version__, "base_commit": commit, "source_hashes": source_hashes,
                "source_snapshot": source_dir.relative_to(ROOT).as_posix(), "specimens": list(SPECIMENS),
                "start_epoch": started, "end_epoch": started + hours * 3600,
                "start_at_utc": utc(started), "end_at_utc": utc(started + hours * 3600),
                "timezone": "Asia/Shanghai", "hours": hours, "interval_minutes": interval_minutes,
                "slots": slots, "max_http_requests": slots * 5 + max(8, slots),
                "soft_storage_bytes": max_storage_mb * 1024 * 1024,
                "max_response_bytes": MAX_RESPONSE_BYTES, "capability_level": "L0",
                "execution_eligible": False}
    _write_json(path / "manifest.json", manifest)
    with Store(path / "observations.sqlite") as store:
        _schema(store.db)
        with store.db:
            store.db.execute("INSERT INTO observer_control VALUES(1,'ready',?,NULL,?)", (utc(started), _hash(path / "manifest.json")))
            store.db.executemany("INSERT INTO observer_samples(slot,item,due_at) VALUES(?,?,?)",
                                 [(slot, item["name"], utc(started + slot * interval_minutes * 60))
                                  for slot in range(slots) for item in SPECIMENS])
    _write_json(POINTER, {"version": "observe-pointer-1.0", "run_dir": str(path.resolve()),
                          "manifest_sha256": _hash(path / "manifest.json")})
    _reports(path)
    return path.resolve()


def load_last_run():
    """Read and validate the pointer; no database connection or network request."""
    if not POINTER.exists():
        return None
    pointer = json.loads(POINTER.read_text(encoding="utf-8"))
    path = _run_path(pointer["run_dir"])
    if _hash(path / "manifest.json") != pointer["manifest_sha256"]:
        raise CollectionError("Observation pointer manifest integrity mismatch")
    _manifest(path)
    return path


def inspect_run(run_dir):
    """Read-only status, including WAL-visible progress during an active run."""
    path = _run_path(run_dir)
    manifest = _manifest(path)
    with closing(sqlite3.connect((path / "observations.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        control = dict(db.execute("SELECT * FROM observer_control WHERE id=1").fetchone())
        counts = {row["state"]: row["n"] for row in db.execute("SELECT state,count(*) n FROM observer_samples GROUP BY state")}
        rows = [dict(row) for row in db.execute("SELECT * FROM observer_samples WHERE state='success' ORDER BY slot,item")]
        attempts = db.execute("SELECT count(*) FROM observer_attempts").fetchone()[0]
        failures = db.execute("SELECT count(*) FROM requests WHERE http_status IS NULL OR http_status!=200 OR (error_code IS NOT NULL AND error_code!=0)").fetchone()[0]
    per_item = []
    for item in SPECIMENS:
        selected = [row for row in rows if row["item"] == item["name"]]
        flags = {}
        metadata_flags = {}
        for row in selected:
            for flag in json.loads(row["snapshot_json"])["quality_flags"]:
                flags[flag] = flags.get(flag, 0) + 1
            for flag in json.loads(row["snapshot_json"]).get("item_quote_quality_flags", []):
                metadata_flags[flag] = metadata_flags.get(flag, 0) + 1
        per_item.append({"name": item["name"], "planned": manifest["slots"], "success": len(selected),
                         "comparison_quality_flags": flags, "item_quote_quality_flags": metadata_flags})
    return {"run_id": path.name, "run_dir": str(path), "status": control["status"], "last_error": control["last_error"],
            "start_at_utc": manifest["start_at_utc"], "end_at_utc": manifest["end_at_utc"],
            "planned_samples": manifest["slots"] * len(SPECIMENS), "sample_states": counts,
            "http_attempts": attempts, "max_http_requests": manifest["max_http_requests"], "http_failures": failures,
            "directory_bytes": sum(p.stat().st_size for p in path.rglob("*") if p.is_file()),
            "storage_stop_budget_bytes": manifest["soft_storage_bytes"], "items": per_item,
            "capability_level": "L0", "execution_eligible": False}


def _reports(path):
    summary = inspect_run(path)
    _write_json(path / "reports/summary.json", summary)
    with closing(sqlite3.connect((path / "observations.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
        rows = [json.loads(row[0]) for row in db.execute("SELECT snapshot_json FROM observer_samples WHERE state='success' ORDER BY slot,item")]
    tables = path / "tables"
    tables.mkdir(exist_ok=True)
    target = tables / "source_snapshots.csv"
    columns = ["slot", "scheduled_at_utc", "market_hash_name", "observed_at_utc", "response_available_at_utc",
               "item_quote_price_cny", "item_quote_update_time", "item_quote_quality_flags",
               "source_sell_price_cny", "source_bidding_price_cny", "source_sell_count",
               "source_bidding_count", "source_update_time", "age_seconds", "quality_flags",
               "source_run_id", "metadata_request", "source_request", "execution_eligible"]
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            row = dict(row)
            row["quality_flags"] = ",".join(row["quality_flags"])
            row["item_quote_quality_flags"] = ",".join(row.get("item_quote_quality_flags", []))
            writer.writerow(row)
    report = path / "reports/summary.md"
    report.write_text(f"# 连续观察状态\n\n运行 {path.name}；状态 {summary['status']}；固定截止 {summary['end_at_utc']}。\n\n"
                      f"计划样本 {summary['planned_samples']}，当前状态 {summary['sample_states']}；HTTP 尝试 {summary['http_attempts']}/{summary['max_http_requests']}。\n\n"
                      "采样是小时级当前来源快照，不补历史缺采，不代表小时内高低点。L0 观察用途，执行准入 false。\n",
                      encoding="utf-8", newline="\n")
    return summary


class _StopBudget(Exception):
    pass


class _SlotElapsed(Exception):
    pass


def collect(run_dir, progress=print, *, _clock=time.time, _sleep=time.sleep, _client_factory=WebsiteClient):
    """Foreground run. Interrupt safely; resume preserves the frozen deadline."""
    path = _run_path(run_dir)
    manifest = _manifest(path)
    if manifest["source_hashes"] != _source_hashes():
        raise CollectionError("Collector source changed; do not silently resume this run")
    with Store(path / "observations.sqlite") as store, store.worker_lock():
        control = store.db.execute("SELECT status FROM observer_control WHERE id=1").fetchone()[0]
        if control in TERMINAL:
            progress(f"Run already stopped: {control}; no HTTP request sent.")
            return _reports(path)
        latest_reserved = store.db.execute("SELECT max(reserved_at) FROM observer_attempts").fetchone()[0]
        latest_epoch = datetime.fromisoformat(latest_reserved).timestamp() if latest_reserved else manifest["start_epoch"]
        context = {"slot": -1, "item": None, "attempt": None, "last_clock": latest_epoch}

        def status(value, error=None):
            with store.db:
                store.db.execute("UPDATE observer_control SET status=?,updated_at=?,last_error=? WHERE id=1", (value, utc(_clock()), error))

        def guard(endpoint, params):
            current = _clock()
            if current < context["last_clock"] - 5:
                raise CollectionError("System clock moved backward; collection stopped")
            context["last_clock"] = max(current, context["last_clock"])
            if current >= manifest["end_epoch"]:
                raise _StopBudget("completed")
            if current >= manifest["start_epoch"] + (context["slot"] + 1) * manifest["interval_minutes"] * 60:
                raise _SlotElapsed()
            count = store.db.execute("SELECT count(*) FROM observer_attempts").fetchone()[0]
            if count >= manifest["max_http_requests"]:
                raise _StopBudget("request_budget")
            if sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) >= manifest["soft_storage_bytes"]:
                raise _StopBudget("storage_budget")
            with store.db:
                cursor = store.db.execute("INSERT INTO observer_attempts(slot,item,endpoint,reserved_at) VALUES(?,?,?,?)",
                                          (context["slot"], context["item"], endpoint, utc(_clock())))
            context["attempt"] = cursor.lastrowid

        def archive(endpoint, params, observed, raw, http_status, code):
            request = store.archive(endpoint, params, observed, raw, http_status, code)
            with store.db:
                store.db.execute("UPDATE observer_attempts SET request_id=?,response_available_at=? WHERE attempt_id=?",
                                 (request, utc(_clock()), context["attempt"]))
            if sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) > manifest["soft_storage_bytes"]:
                raise _StopBudget("storage_budget")
            return request

        client = _client_factory(archive, delay=2.5, max_response_bytes=manifest["max_response_bytes"], before_request=guard)
        status("running")
        progress(f"Observation run: {path}\nFixed deadline (Beijing): {datetime.fromtimestamp(manifest['end_epoch'], CHINA).isoformat()}")
        try:
            while _clock() < manifest["end_epoch"]:
                current = _clock()
                if current < context["last_clock"] - 5:
                    raise CollectionError("System clock moved backward; collection stopped")
                context["last_clock"] = max(current, context["last_clock"])
                slot = min(int((current - manifest["start_epoch"]) // (manifest["interval_minutes"] * 60)), manifest["slots"] - 1)
                if slot < 0:
                    raise CollectionError("System clock moved before the frozen run start")
                with store.db:
                    store.db.execute("UPDATE observer_samples SET state='missed',error='slot elapsed before a successful sample' WHERE state='pending' AND slot<?", (slot,))
                context["slot"] = slot
                for item in SPECIMENS:
                    context["item"] = item["name"]
                    state = store.db.execute("SELECT state FROM observer_samples WHERE slot=? AND item=?", (slot, item["name"])).fetchone()[0]
                    if state != "pending":
                        continue
                    try:
                        data, metadata_request = client.call(ITEM, {"appId": 730, "marketHashName": item["name"]}, post=True)
                        if not isinstance(data, dict) or data.get("marketHashName") != item["name"] or str(data.get("itemId")) != item["item_id"]:
                            raise AccessStopped("Frozen specimen identity mismatch")
                        prices = data.get("sellingPriceList")
                        if not isinstance(prices, list) or any(not isinstance(row, dict) for row in prices):
                            raise AccessStopped("Unexpected metadata quote schema")
                        quote = [q for q in prices if str(q.get("platform", "")).upper() == "YOUPIN" and q.get("platformName") == "悠悠"]
                        if len(quote) != 1:
                            raise AccessStopped("UU metadata quote identity missing")
                        compared, request = client.call(MARKET_COMPARISON, {"itemId": item["item_id"], "platform": "YOUPIN", "typeDay": "1", "dateType": 4})
                        if not isinstance(compared, dict) or not isinstance(compared.get("platformMarket"), list) or any(not isinstance(row, dict) for row in compared["platformMarket"]):
                            raise AccessStopped("Unexpected comparison schema")
                        rows = [row for row in compared["platformMarket"] if str(row.get("platform", "")).upper() == "YOUPIN"]
                        if len(rows) != 1:
                            raise AccessStopped("UU comparison identity ambiguous")
                        source = store.db.execute("SELECT collected_at FROM requests WHERE request_id=?", (request,)).fetchone()
                        snapshot = uu_snapshot(rows[0], source[0], request)
                        if snapshot["template_id"] != item["template_id"]:
                            raise AccessStopped("Frozen UU template identity mismatch")
                        snapshot.update(slot=slot, scheduled_at_utc=utc(manifest["start_epoch"] + slot * manifest["interval_minutes"] * 60),
                                        market_hash_name=item["name"], source_run_id=path.name, metadata_request=metadata_request,
                                        item_quote_price_cny=number(quote[0].get("price"), nullable=True),
                                        item_quote_update_time=seconds(quote[0]["updateTime"]) if quote[0].get("updateTime") is not None else None,
                                        response_available_at_utc=utc(_clock()))
                        metadata_flags = []
                        if snapshot["item_quote_price_cny"] is None or Decimal(snapshot["item_quote_price_cny"]) == 0:
                            metadata_flags.append("side_missing_or_zero")
                        updated = snapshot["item_quote_update_time"]
                        item_observed = store.db.execute("SELECT collected_at FROM requests WHERE request_id=?", (metadata_request,)).fetchone()[0]
                        metadata_age = datetime.fromisoformat(item_observed).timestamp() - updated if updated is not None else None
                        if metadata_age is None:
                            metadata_flags.append("source_time_missing")
                        elif metadata_age < 0:
                            metadata_flags.append("source_time_future")
                        elif metadata_age > 3600:
                            metadata_flags.append("stale_over_1h")
                        snapshot["item_quote_quality_flags"] = metadata_flags
                        with store.db:
                            store.db.execute("UPDATE observer_samples SET state='success',metadata_request=?,comparison_request=?,observed_at=?,snapshot_json=?,error=NULL WHERE slot=? AND item=?",
                                             (metadata_request, request, source[0], json.dumps(snapshot, ensure_ascii=False), slot, item["name"]))
                        progress(f"Slot {slot + 1}/{manifest['slots']}: {item['name']}; sell={snapshot['source_sell_price_cny']} bid={snapshot['source_bidding_price_cny']} flags={snapshot['quality_flags']}")
                    except AccessStopped:
                        raise
                    except _SlotElapsed:
                        with store.db:
                            store.db.execute("UPDATE observer_samples SET state='missed',error='slot elapsed before the next request' WHERE slot=? AND item=? AND state='pending'", (slot, item["name"]))
                        break
                    except CollectionError as error:
                        # Transient transport failures are not immediately retried.
                        # Invalid numeric/schema data must persistently stop instead.
                        if "network failure" not in str(error) and not str(error).startswith("Website HTTP 5"):
                            raise
                        with store.db:
                            store.db.execute("UPDATE observer_samples SET state='failed',error=? WHERE slot=? AND item=?", (str(error), slot, item["name"]))
                        progress(f"Slot {slot + 1}: transport failure recorded; next attempt is next scheduled slot.")
                _reports(path)
                next_due = min(manifest["start_epoch"] + (slot + 1) * manifest["interval_minutes"] * 60, manifest["end_epoch"])
                while _clock() < next_due:
                    if _clock() < context["last_clock"] - 5:
                        raise CollectionError("System clock moved backward; collection stopped")
                    context["last_clock"] = max(_clock(), context["last_clock"])
                    _sleep(min(30, next_due - _clock()))
            status("completed")
        except KeyboardInterrupt:
            status("interrupted", "User interrupted; original deadline retained")
            progress("Interrupted safely. Resume this same run; deadline has not changed.")
        except _StopBudget as error:
            status(str(error))
            progress(f"Stopped: {error}")
        except AccessStopped as error:
            status("access_blocked", str(error))
            progress(f"Access stopped: {error}. This run will not auto-retry.")
        except (CollectionError, ValueError, TypeError, KeyError, AttributeError, OSError) as error:
            status("safe_error", type(error).__name__)
            progress("Data/schema validation failed; original evidence retained. No automatic retry.")
        finally:
            if _clock() >= manifest["end_epoch"]:
                with store.db:
                    store.db.execute("UPDATE observer_samples SET state='missed',error='deadline elapsed' WHERE state='pending'")
            result = _reports(path)
    return result
