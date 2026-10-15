"""Bounded user-run SteamDT UU research warehouse; no training or trading."""
from __future__ import annotations

import argparse
from contextlib import closing
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from cs_youoweme.collectors.website import ITEM, MARKET_COMPARISON, WebsiteClient
from cs_youoweme.errors import AccessStopped, CollectionError
from cs_youoweme.history.catalog import dimensions, upsert_item
from cs_youoweme.history.jobs import enqueue, work
from cs_youoweme.history.store import Store, now
from cs_youoweme.history.verification import uu_snapshot
from cs_youoweme.paths import ROOT, LOCAL_DATA, CHINA

VERSION = "steamdt-research-1.0"
BASE = LOCAL_DATA / "staging/steamdt"
CONTROL = BASE / "research_control"
SEEDS = ROOT / "scripts/config/steamdt_research_items.json"
SOURCE_FILES = [Path(__file__), *[ROOT / "scripts/src/cs_youoweme" / p for p in (
    "__init__.py", "collectors/website.py", "history/store.py", "history/schema.sql",
    "history/catalog.py", "history/jobs.py", "history/normalize.py", "history/verification.py",
    "collectors/official.py", "config.py", "errors.py", "paths.py", "transport.py")]]
SCHEMA = """
CREATE TABLE IF NOT EXISTS research_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_receipts(request_id INTEGER PRIMARY KEY REFERENCES requests,received_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_quotes(run_id TEXT,name TEXT,request_id INTEGER,quote_json TEXT NOT NULL,PRIMARY KEY(run_id,name));
CREATE TABLE IF NOT EXISTS research_job_generations(generation_id INTEGER PRIMARY KEY,job_id INTEGER,prior_job_json TEXT,prior_checkpoints_json TEXT,archived_at TEXT);
CREATE TABLE IF NOT EXISTS research_bar_versions(
 version_id INTEGER PRIMARY KEY,market_hash_name TEXT,platform TEXT,period TEXT,style TEXT,
 source_time INTEGER,bucket_time INTEGER,open_cny TEXT,close_cny TEXT,high_cny TEXT,low_cny TEXT,
 source_volume INTEGER,source_turnover_cny TEXT,source_request INTEGER REFERENCES requests);
CREATE INDEX IF NOT EXISTS research_versions_time ON research_bar_versions(market_hash_name,bucket_time,version_id);
CREATE TRIGGER IF NOT EXISTS research_initial AFTER INSERT ON bars BEGIN
 INSERT INTO research_bar_versions(market_hash_name,platform,period,style,source_time,bucket_time,open_cny,close_cny,high_cny,low_cny,source_volume,source_turnover_cny,source_request)
 VALUES(NEW.market_hash_name,NEW.platform,NEW.period,NEW.style,NEW.source_time,NEW.bucket_time,NEW.open_cny,NEW.close_cny,NEW.high_cny,NEW.low_cny,NEW.source_volume,NEW.source_turnover_cny,NEW.source_request); END;
CREATE TRIGGER IF NOT EXISTS research_revision AFTER UPDATE ON bars
 WHEN OLD.bucket_time IS NOT NEW.bucket_time OR OLD.open_cny IS NOT NEW.open_cny OR OLD.close_cny IS NOT NEW.close_cny
 OR OLD.high_cny IS NOT NEW.high_cny OR OLD.low_cny IS NOT NEW.low_cny OR OLD.source_volume IS NOT NEW.source_volume OR OLD.source_turnover_cny IS NOT NEW.source_turnover_cny
 BEGIN INSERT INTO research_bar_versions(market_hash_name,platform,period,style,source_time,bucket_time,open_cny,close_cny,high_cny,low_cny,source_volume,source_turnover_cny,source_request)
 VALUES(NEW.market_hash_name,NEW.platform,NEW.period,NEW.style,NEW.source_time,NEW.bucket_time,NEW.open_cny,NEW.close_cny,NEW.high_cny,NEW.low_cny,NEW.source_volume,NEW.source_turnover_cny,NEW.source_request); END;
CREATE VIEW IF NOT EXISTS research_hourly_latest AS
 SELECT market_hash_name,platform,period,style,source_time,bucket_time,open_cny,close_cny,high_cny,low_cny,source_volume,source_turnover_cny,source_request FROM
 (SELECT bars.*,ROW_NUMBER() OVER(PARTITION BY market_hash_name,platform,period,style,bucket_time ORDER BY source_request DESC,source_time DESC) AS rn FROM bars WHERE platform='YOUPIN' AND period='1h' AND style='') WHERE rn=1;
"""


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE_FILES}


def directory(name):
    if not re.fullmatch(r"research_[a-zA-Z0-9_]{1,70}", name) or name == "research_control":
        raise CollectionError("Invalid research workspace name")
    return BASE / name


def registry(path):
    if path.stat().st_size > 128 * 1024:
        raise CollectionError("Registry too large")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or set(value) != {"version", "items"} or value["version"] != "steamdt-research-registry-1.0" or not isinstance(value["items"], list) or not 1 <= len(value["items"]) <= 50:
        raise CollectionError("Invalid registry")
    seen = set()
    for item in value["items"]:
        if not isinstance(item, dict) or set(item) != {"market_hash_name", "name_zh", "steamdt_item_id", "uu_template_id", "history_start", "enabled"}:
            raise CollectionError("Registry fields differ")
        name = item["market_hash_name"]
        if not isinstance(name, str) or len(name) > 300:
            raise CollectionError("Registry item name must be text")
        category, _, _, quality, exterior, _ = dimensions(name)
        if category != "weapon" or quality != "normal" or exterior is None or name in seen or not isinstance(item["name_zh"], str) or len(item["name_zh"]) > 200 or type(item["enabled"]) is not bool:
            raise CollectionError("Registry needs unique exact ordinary weapon specifications")
        seen.add(name)
        for key in ("steamdt_item_id", "uu_template_id"):
            if item[key] is not None and (not isinstance(item[key], str) or not re.fullmatch(r"[1-9][0-9]{0,23}", item[key])):
                raise CollectionError("Registry identifier must be numeric text or null")
        if item["history_start"] is not None:
            date = datetime.strptime(item["history_start"], "%Y-%m-%d")
            if date.year < 2013 or date.date() > datetime.now(CHINA).date():
                raise CollectionError("Invalid history start")
    if not any(item["enabled"] for item in value["items"]):
        raise CollectionError("No enabled registry items")
    return value


def init_workspace(name):
    path = directory(name)
    if path.exists():
        raise CollectionError("Workspace exists; preserve it and use sync/status")
    registry(SEEDS)
    path.mkdir(parents=True)
    (path / "registry.json").write_bytes(SEEDS.read_bytes())
    with Store(path / "research.sqlite") as store:
        store.db.executescript(SCHEMA)
        store.db.execute("INSERT INTO research_meta VALUES('version',?)", (VERSION,))
        store.db.commit()
    dump(path / "workspace.json", {"version": VERSION, "created_at": now(), "core_hashes": {k: v for k, v in hashes().items() if k != Path(__file__).relative_to(ROOT).as_posix()}, "source": "steamdt_website_explicit_YOUPIN", "capability": "L0"})
    return path


def check_workspace(name):
    path = directory(name)
    value = json.loads((path / "workspace.json").read_text(encoding="utf-8"))
    current = hashes()
    if value.get("version") != VERSION or any(current.get(k) != v for k, v in value["core_hashes"].items()):
        raise CollectionError("Frozen core differs; do not mutate an existing workspace")
    return path


class Guard:
    def __init__(self, maximum=80, delay=5, seconds=900, confirmed=False):
        self.maximum, self.delay = maximum, delay
        self.deadline = time.monotonic() + seconds
        self.requests = 0
        self.path = CONTROL / "research-client"  # Store.worker_lock only needs path.
        CONTROL.mkdir(parents=True, exist_ok=True)
        self.state = json.loads((CONTROL / "state.json").read_text()) if (CONTROL / "state.json").exists() else {"blocked": False, "not_before": 0, "last_request": 0, "requests": [], "recovery_confirmations": []}
        if time.time() < self.state["not_before"]:
            raise AccessStopped("Server cooldown remains active")
        if self.state["blocked"]:
            if not confirmed:
                raise AccessStopped("SteamDT access stopped; normal access must be confirmed before an explicit retry")
            self.state["blocked"] = False
            self.state["recovery_confirmations"].append(now())
            dump(CONTROL / "state.json", self.state)

    def before(self, endpoint, params, store):
        if self.requests >= self.maximum or time.monotonic() >= self.deadline:
            raise CollectionError("Research invocation request/time budget reached")
        self.state["requests"] = [t for t in self.state["requests"] if t > time.time() - 86400]
        if len(self.state["requests"]) >= 300 or store.disk_bytes() >= 128 * 1024 * 1024:
            raise CollectionError("Research rolling quota/storage budget reached")
        wait = self.delay - (time.time() - self.state["last_request"])
        if time.monotonic() + max(0, wait) >= self.deadline:
            raise CollectionError("Research invocation request/time budget reached")
        if wait > 0:
            time.sleep(wait)
        self.requests += 1
        self.state["last_request"] = time.time()
        self.state["requests"].append(time.time())
        dump(CONTROL / "state.json", self.state)  # Record attempt before network I/O.

    def stop(self, cooldown=0):
        self.state["blocked"] = True
        self.state["not_before"] = max(self.state["not_before"], cooldown)
        dump(CONTROL / "state.json", self.state)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Opener:
    def __init__(self, guard):
        self.guard = guard
        self.inner = urllib.request.build_opener(NoRedirect())

    def open(self, request, timeout):
        try:
            return self.inner.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                wait = time.time() + 900
                try:
                    value = error.headers.get("Retry-After")
                    wait = time.time() + int(value) if value.isdigit() else parsedate_to_datetime(value).timestamp()
                except (AttributeError, ValueError, TypeError, OverflowError):
                    pass
                self.guard.stop(wait)
            raise


def sources(path):
    snapshot = path / "source"
    for source in SOURCE_FILES:
        target = snapshot / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return hashes()


def ensure_tasks(store, item, end, overlap_days):
    name = item["market_hash_name"]
    earliest = int(datetime.strptime(item["history_start"], "%Y-%m-%d").replace(tzinfo=CHINA).timestamp()) if item["history_start"] else 1
    initial = store.db.execute("SELECT 1 FROM jobs WHERE market_hash_name=? AND kind='bars' AND platform='YOUPIN' AND start_time=?", (name, earliest)).fetchone()
    if not initial:
        enqueue(store.db, name, "bars", earliest, end, "YOUPIN", "1h", priority=100)
    latest = store.db.execute("SELECT max(bucket_time) FROM bars WHERE market_hash_name=? AND platform='YOUPIN' AND period='1h'", (name,)).fetchone()[0]
    if latest is not None:
        start = max(earliest, latest - overlap_days * 86400)
        if start < end:
            enqueue(store.db, name, "bars", start, end, "YOUPIN", "1h", priority=10)
            job = store.db.execute("SELECT * FROM jobs WHERE market_hash_name=? AND kind='bars' AND platform='YOUPIN' AND start_time=? AND end_time=? AND priority=10", (name, start, end)).fetchone()
            if job is not None and job["state"] == "done":
                checkpoints = [dict(r) for r in store.db.execute("SELECT * FROM checkpoints WHERE job_id=?", (job["job_id"],))]
                store.db.execute("INSERT INTO research_job_generations(job_id,prior_job_json,prior_checkpoints_json,archived_at) VALUES(?,?,?,?)", (job["job_id"], json.dumps(dict(job)), json.dumps(checkpoints), now()))
                store.db.execute("DELETE FROM checkpoints WHERE job_id=?", (job["job_id"],))
                store.db.execute("UPDATE jobs SET cursor='',state='pending',pages=0,fetched_rows=0,inserted_rows=0,min_time=NULL,max_time=NULL,finish_reason=NULL,last_error=NULL WHERE job_id=?", (job["job_id"],))
    store.db.commit()


def aggregate(rows, period):
    width = {"4h": 14400, "1d": 86400, "1w": 604800}[period]
    groups = {}
    for row in rows:
        if period == "1w":
            day = datetime.fromtimestamp(row["bucket_time"], CHINA).replace(hour=0, minute=0, second=0, microsecond=0)
            bucket = int((day - timedelta(days=day.weekday())).timestamp())
        else:
            bucket = (row["bucket_time"] + 28800) // width * width - 28800
        groups.setdefault(bucket, []).append(row)
    result = []
    for bucket, values in sorted(groups.items()):
        values.sort(key=lambda r: r["bucket_time"])
        full = len(values) == width // 3600
        result.append({"bucket_time": bucket, "period": period, "open_cny": values[0]["open_cny"], "high_cny": str(max(Decimal(r["high_cny"]) for r in values)), "low_cny": str(min(Decimal(r["low_cny"]) for r in values)), "close_cny": values[-1]["close_cny"],
                       "source_volume": sum(r["source_volume"] for r in values) if full and all(r["source_volume"] is not None for r in values) else None,
                       "source_turnover_cny": str(sum(Decimal(r["source_turnover_cny"]) for r in values)) if full and all(r["source_turnover_cny"] is not None for r in values) else None,
                       "observed_hours": len(values), "expected_hours": width // 3600, "complete_hours": full, "derived_from": "SteamDT_YOUPIN_1h"})
    return result


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def report(path, run, items):
    output = path / "reports" / run["invocation_id"]
    output.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect((path / "research.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        details = []
        cutoff = run["end_exclusive"]
        for item in items["items"]:
            name = item["market_hash_name"]
            rows = [dict(r) for r in db.execute("SELECT * FROM research_hourly_latest WHERE market_hash_name=? AND bucket_time<? ORDER BY bucket_time", (name, cutoff))]
            known = db.execute("SELECT steamdt_item_id FROM catalog WHERE market_hash_name=?", (name,)).fetchone()
            quote = db.execute("SELECT quote_json FROM research_quotes WHERE name=? ORDER BY rowid DESC LIMIT 1", (name,)).fetchone()
            jobs = [dict(r) for r in db.execute("SELECT job_id,start_time,end_time,cursor,state,pages,finish_reason,last_error FROM jobs WHERE market_hash_name=? ORDER BY job_id", (name,))]
            expected = ((rows[-1]["bucket_time"] - rows[0]["bucket_time"]) // 3600 + 1) if rows else 0
            label = known[0] if known else str(len(details))
            requested = int(datetime.strptime(item["history_start"], "%Y-%m-%d").replace(tzinfo=CHINA).timestamp()) if item["history_start"] else None
            uu_id = db.execute("SELECT platform_item_id FROM platform_ids WHERE market_hash_name=? AND platform='YOUPIN'", (name,)).fetchone()
            row = {"market_hash_name": name, "name_zh": item["name_zh"], "steamdt_item_id": known[0] if known else None, "enabled": item["enabled"], "quote": json.loads(quote[0]) if quote else None,
                   "uu_template_id": uu_id[0] if uu_id else None,
                   "hour_rows": len(rows), "first_hour_beijing": datetime.fromtimestamp(rows[0]["bucket_time"], CHINA).isoformat() if rows else None,
                   "last_hour_beijing": datetime.fromtimestamp(rows[-1]["bucket_time"], CHINA).isoformat() if rows else None,
                   "missing_between_first_last": expected - len(rows), "null_volume_hours": sum(r["source_volume"] is None for r in rows), "null_turnover_hours": sum(r["source_turnover_cny"] is None for r in rows),
                   "unaligned_source_times": sum(r["source_time"] != r["bucket_time"] for r in rows), "history_start_requested": item["history_start"],
                   "requested_start_observed": bool(rows and requested is not None and rows[0]["bucket_time"] <= requested),
                   "source_exhausted_before_requested_start": bool(requested is not None and rows and rows[0]["bucket_time"] > requested and any(j["finish_reason"] == "source_history_exhausted" and j["start_time"] == requested for j in jobs)),
                   "jobs": jobs, "attributes_verified": False, "execution_eligible": False}
            details.append(row)
            write_csv(output / f"item_{label}_1h.csv", rows)
            for period in ("4h", "1d", "1w"):
                write_csv(output / f"item_{label}_{period}.csv", aggregate(rows, period))
        requests = db.execute("SELECT count(*) FROM requests").fetchone()[0]
        revisions = db.execute("SELECT (SELECT count(*) FROM research_bar_versions)-(SELECT count(*) FROM bars)").fetchone()[0]
    result = {"version": VERSION, "run": run, "integrity": integrity, "items": details, "workspace_http_attempts_archived": requests, "changed_bar_versions": revisions, "capability": "L0", "historical_available_at": None, "training_started": False}
    dump(output / "report.json", result)
    write_csv(output / "resolved_items.csv", [{k: row[k] for k in ("market_hash_name", "name_zh", "steamdt_item_id", "uu_template_id", "hour_rows", "history_start_requested", "requested_start_observed")} for row in details])
    lines = ["# SteamDT目标品数据库报告", "", f"版本 {VERSION}；状态 {run['status']}；SQLite完整性 {integrity}。来源量额不认定UU真实订单。", "", "| 规格 | 小时数 | 首小时 | 末小时 | 区间缺口 | 量/额空值 |", "| --- | ---: | --- | --- | ---: | --- |"]
    for row in details:
        lines.append(f"| {row['name_zh']} | {row['hour_rows']} | {row['first_hour_beijing']} | {row['last_hour_beijing']} | {row['missing_between_first_last']} | {row['null_volume_hours']}/{row['null_turnover_hours']} |")
    lines.extend(["", "registry.json是可编辑清单；catalog保存已核对ID，jobs保存每品分页进度与范围；bars为当前来源值，research_bar_versions保留首次值与变化，raw保留压缩响应。research_hourly_latest每规格/小时只取最近来源记录。", "", "本报告只导出已过小时边界的桶，不代表来源不可修订。4h/日/周是从小时派生，覆盖不完整时complete_hours=false，缺失量额不补0。", "", "任务完成不等于覆盖请求起点；首末范围、内部缺口与source_history_exhausted/reached_requested_start分开核对。价格与属性/求购均需复核，当前非正式买入名单，不训练、不交易。", ""])
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    dump(path / "latest_report.json", {"report": str((output / "report.json").relative_to(path)), "status": run["status"], "invocation_id": run["invocation_id"]})
    return result


def sync(name, *, mode="daily", maximum=80, delay=5, confirmed=False, client_factory=None):
    path = check_workspace(name)
    items = registry(path / "registry.json")
    if maximum < 1 or maximum > 120 or not 3 <= delay <= 60:
        raise CollectionError("Use 1-120 requests and a 3-60 second interval")
    run_id = datetime.now(CHINA).strftime("%Y%m%dT%H%M%S+0800_") + uuid.uuid4().hex[:6]
    run_dir = path / "runs" / run_id
    run_dir.mkdir(parents=True)
    run = {"invocation_id": run_id, "started_at": now(), "mode": mode, "end_exclusive": int(time.time()) // 3600 * 3600,
           "request_limit": maximum, "delay_seconds": delay, "status": "running", "source_sha256": sources(run_dir)}
    dump(run_dir / "registry.json", items)
    dump(run_dir / "run.json", run)
    CONTROL.mkdir(parents=True, exist_ok=True)
    # Shared OS lock releases if the process crashes; the lock file is not deleted.
    lock_owner = type("LockOwner", (), {"path": CONTROL / "research-client"})()
    with Store.worker_lock(lock_owner), Store(path / "research.sqlite") as store:
        try:
            guard = Guard(maximum, delay, confirmed=confirmed)
        except CollectionError as error:
            run.update(status="stopped", stopped=str(error), completed_at=now(), http_attempts=0)
            dump(run_dir / "run.json", run)
            raise
        def archive(endpoint, params, observed, raw, status, code):
            ident = store.archive(endpoint, params, observed, raw, status, code)
            with store.db:
                store.db.execute("INSERT INTO research_receipts VALUES(?,?)", (ident, now()))
            return ident
        client = client_factory(archive, guard, store) if client_factory else WebsiteClient(archive, delay, opener=Opener(guard), max_response_bytes=2 * 1024 * 1024, before_request=lambda endpoint, params: guard.before(endpoint, params, store))
        try:
            active = [i for i in items["items"] if i["enabled"]]
            names = {i["market_hash_name"] for i in active}
            with store.db:
                for row in store.db.execute("SELECT job_id,market_hash_name,last_error FROM jobs WHERE state='pending' OR last_error='registry_disabled'").fetchall():
                    store.db.execute("UPDATE jobs SET state=?,last_error=? WHERE job_id=?", ("pending" if row[1] in names else "blocked", None if row[1] in names else "registry_disabled", row[0]))
                if confirmed:
                    store.db.execute("UPDATE jobs SET state='pending',last_error=NULL WHERE state='blocked' AND last_error!='registry_disabled'")
            for entry in active:
                item, item_request = client.call(ITEM, {"appId": 730, "marketHashName": entry["market_hash_name"]}, post=True)
                if not isinstance(item, dict) or item.get("marketHashName") != entry["market_hash_name"] or not str(item.get("itemId", "")).isdigit() or (entry["steamdt_item_id"] and str(item["itemId"]) != entry["steamdt_item_id"]):
                    raise AccessStopped("Exact candidate identity/SteamDT ID differs")
                comparison, request = client.call(MARKET_COMPARISON, {"itemId": str(item["itemId"]), "platform": "YOUPIN", "typeDay": "1", "dateType": 4})
                matches = [r for r in comparison.get("platformMarket", []) if isinstance(r, dict) and str(r.get("platform", "")).upper() == "YOUPIN"] if isinstance(comparison, dict) else []
                if len(matches) != 1:
                    raise AccessStopped("UU comparison identity missing or ambiguous")
                observed = now()
                quote = uu_snapshot(matches[0], observed, request)
                if entry["uu_template_id"] and quote["template_id"] != entry["uu_template_id"]:
                    raise AccessStopped("UU template ID differs")
                price = quote["source_sell_price_cny"]
                quote["price_range_observed"] = price is not None and Decimal(100) <= Decimal(price) < Decimal(1000)
                with store.db:
                    upsert_item(store.db, {"marketHashName": entry["market_hash_name"], "name": entry["name_zh"], "platformList": [{"name": "YOUPIN", "itemId": quote["template_id"]}]}, item_request)
                    store.db.execute("UPDATE catalog SET steamdt_item_id=?,metadata_request=? WHERE market_hash_name=?", (str(item["itemId"]), item_request, entry["market_hash_name"]))
                    store.db.execute("INSERT INTO research_quotes VALUES(?,?,?,?)", (run_id, entry["market_hash_name"], request, json.dumps(quote, ensure_ascii=False)))
                ensure_tasks(store, entry, run["end_exclusive"], 35 if mode == "weekly" else 7)
                print(json.dumps({"event": "identity_checked", "name": entry["market_hash_name"], "steamdt_id": str(item["itemId"]), "uu_template_id": quote["template_id"], "price_range_observed": quote["price_range_observed"]}, ensure_ascii=False), flush=True)
            result = work(store, max_pages=maximum, delay=delay, client=client, max_storage_mb=128)
            stopped = result.get("stopped")
            if stopped and "budget" not in stopped.lower():
                guard.stop()
            pending = store.db.execute("SELECT count(*) FROM jobs WHERE state='pending'").fetchone()[0]
            run.update(status="stopped" if stopped and "budget" not in stopped.lower() else "paused_budget" if pending else "completed", stopped=stopped, pending_jobs=pending)
        except KeyboardInterrupt:
            run.update(status="interrupted", stopped="user_interrupted")
        except CollectionError as error:
            budget = "budget" in str(error).lower()
            if not budget:
                guard.stop()
            run.update(status="paused_budget" if budget else "stopped", stopped=str(error))
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
            guard.stop()
            run.update(status="stopped", stopped="local_io_or_schema_error")
        finally:
            run.update(completed_at=now(), http_attempts=guard.requests)
            dump(run_dir / "run.json", run)
    return report(path, run, items)


def status(name):
    path = check_workspace(name)
    pointer = path / "latest_report.json"
    if not pointer.exists():
        return {"status": "initialized", "workspace": name}
    p = json.loads(pointer.read_text())
    return json.loads((path / p["report"]).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "sync", "status"])
    parser.add_argument("--workspace", default="research_20261016_v1")
    parser.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    parser.add_argument("--max-requests", type=int, default=80)
    parser.add_argument("--delay", type=float, default=5)
    parser.add_argument("--normal-access-confirmed", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "init":
            print(json.dumps({"initialized": str(init_workspace(args.workspace)), "market_requests": 0})); return 0
        value = status(args.workspace) if args.command == "status" else sync(args.workspace, mode=args.mode, maximum=args.max_requests, delay=args.delay, confirmed=args.normal_access_confirmed)
        print(json.dumps({"status": value.get("run", {}).get("status", value.get("status")), "items": [{k: r[k] for k in ("market_hash_name", "hour_rows", "first_hour_beijing", "last_hour_beijing", "missing_between_first_last")} for r in value.get("items", [])]}, ensure_ascii=False), flush=True)
        return 0 if value.get("run", {}).get("status", value.get("status")) in {"initialized", "completed", "paused_budget"} else 2
    except (CollectionError, ValueError, OSError, KeyError, TypeError, sqlite3.Error):
        error = sys.exception()
        message = str(error) if isinstance(error, CollectionError) else "configuration_or_local_io_error"
        print(json.dumps({"status": "stopped", "reason": message}, ensure_ascii=False)); return 2


if __name__ == "__main__":
    raise SystemExit(main())
