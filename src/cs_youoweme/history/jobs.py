"""Bounded collection workers with page commits and durable opaque cursors."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from ..collectors.website import KLINE, TRADES, WebsiteClient
from ..errors import AccessStopped, CollectionError
from ..paths import CHINA
from .catalog import TARGETS, discover_styles, resolve_item
from .normalize import bar_record, trade_record
from .store import now


def boundary(value, end=False):
    """Date-only end bounds include that Beijing day; timestamps are exclusive."""
    try:
        date = datetime.fromisoformat(value)
    except ValueError:
        raise CollectionError("Date must be ISO YYYY-MM-DD or an ISO timestamp") from None
    if date.tzinfo is None:
        date = date.replace(tzinfo=CHINA)
    if end and len(value) == 10:
        date += timedelta(days=1)
    return int(date.timestamp())


def enqueue(db, name, kind, start, end, platform="ALL", period="1h", style="", priority=100):
    result = db.execute("""
        INSERT OR IGNORE INTO jobs(market_hash_name,kind,platform,period,style,start_time,end_time,
                                  priority,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (name, kind, platform, period, style, start, end, priority, now(), now()))
    return result.rowcount


def plan(store, start, end, names=None, categories=None, kinds=("bars", "trades"),
         platforms=("ALL",), period="1h", priority=100):
    if start >= end:
        raise CollectionError("Start must precede end")
    if set(kinds) - {"bars", "trades"} or not kinds or period not in {"1h", "1d"}:
        raise CollectionError("Unsupported history job type")
    if not platforms or set(platforms) - {"ALL", "BUFF", "YOUPIN", "STEAM", "C5", "HALOSKINS"}:
        raise CollectionError("Unsupported source platform")
    categories = set(categories or TARGETS)
    if not categories or categories - TARGETS:
        raise CollectionError("History scope must be weapons, knives or gloves")
    if names:
        rows = []
        for name in names:
            row = store.db.execute("SELECT market_hash_name,category FROM catalog WHERE market_hash_name=?", (name,)).fetchone()
            if not row or row["category"] not in categories:
                raise CollectionError("Named item is absent from the selected catalog scope")
            rows.append(row)
    else:
        rows = store.db.execute("SELECT market_hash_name,category FROM catalog WHERE category IN ("
                                + ",".join("?" for _ in categories) + ") ORDER BY market_hash_name", sorted(categories)).fetchall()
    if not rows:
        raise CollectionError("No catalog items selected; run catalog sync first")
    inserted = 0
    with store.db:
        for row in rows:
            name = row["market_hash_name"]
            for kind in kinds:
                for platform in (platforms if kind == "bars" else ("ALL",)):
                    inserted += enqueue(store.db, name, kind, start, end, platform,
                                        period if kind == "bars" else "event", priority=priority)
                    if kind == "bars":
                        for style in store.db.execute("SELECT style FROM styles WHERE market_hash_name=?", (name,)).fetchall():
                            inserted += enqueue(store.db, name, kind, start, end, platform, period, style[0], priority)
    return {"selected_items": len(rows), "new_jobs": inserted, "start_inclusive": start,
            "end_exclusive": end, "timezone": "Asia/Shanghai", "period": period}


def styles_for_job(store, client, job, item):
    # Doppler phases are independent price series sharing the market hash name.
    if item["category"] != "knife" or "Doppler" not in (item["skin"] or "") or item["styles_checked"]:
        return
    styles = discover_styles(store, client, job["market_hash_name"], item["steamdt_item_id"])
    with store.db:
        store.db.execute("UPDATE catalog SET styles_checked=1 WHERE market_hash_name=?", (job["market_hash_name"],))
        parent_jobs = store.db.execute("SELECT * FROM jobs WHERE market_hash_name=? AND kind='bars' AND style=''",
                                      (job["market_hash_name"],)).fetchall()
        for parent in parent_jobs:
            for style in styles:
                enqueue(store.db, parent["market_hash_name"], "bars", parent["start_time"], parent["end_time"],
                        parent["platform"], parent["period"], style, parent["priority"])


def fetch_page(client, job, item_id):
    if job["kind"] == "trades":
        data, request_id = client.call(TRADES, {
            "itemId": item_id, "pageSize": 20, "nextId": job["cursor"],
            "sortBy": "tradeTime", "sortType": "desc", "hasSteam": -1,
            "startTime": job["start_time"], "endTime": job["end_time"] - 1,
        }, post=True)
        if not isinstance(data, dict) or not isinstance(data.get("list"), list) or "nextId" not in data:
            raise CollectionError("Unexpected trade pagination schema")
        cursor = data["nextId"]
        if cursor is not None and not isinstance(cursor, str):
            raise CollectionError("Trade cursor must be an opaque string or null")
        rows = [trade_record(row) for row in data["list"]]
        if any(not job["start_time"] <= row[2] < job["end_time"] for row in rows):
            raise CollectionError("Trade event outside requested interval")
        if cursor and not rows:
            raise CollectionError("Empty trade page with a continuation cursor")
        return rows, cursor or "", "source_cursor_exhausted" if not cursor else None, request_id
    data, request_id = client.call(KLINE, {
        "type": {"1h": 1, "1d": 2}[job["period"]], "typeVal": item_id,
        "platform": job["platform"], "specialStyle": job["style"],
        "maxTime": int(job["cursor"]) if job["cursor"] else job["end_time"] - 1,
    })
    if not isinstance(data, list):
        raise CollectionError("Unexpected K-line page schema")
    all_rows = [bar_record(row, job["period"]) for row in data]
    if not all_rows:
        return [], "", "source_history_exhausted", request_id
    earliest = min(row[0] for row in all_rows)
    if job["cursor"] and earliest >= int(job["cursor"]):
        raise CollectionError("K-line cursor made no backward progress")
    rows = [row for row in all_rows if job["start_time"] <= row[0] < job["end_time"]]
    reason = "reached_requested_start" if earliest <= job["start_time"] else None
    return rows, str(earliest - 1), reason, request_id


def commit_page(store, job, rows, next_cursor, reason, request_id):
    if next_cursor and not reason:
        if next_cursor == job["cursor"] or store.db.execute("SELECT 1 FROM checkpoints WHERE job_id=? AND cursor=?",
                                                           (job["job_id"], next_cursor)).fetchone():
            raise CollectionError("Repeated continuation cursor; refusing an infinite loop")
    inserted = 0
    times = []
    with store.db:
        for row in rows:
            name = job["market_hash_name"]
            if job["kind"] == "trades":
                result = store.db.execute("INSERT OR IGNORE INTO trades VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                          (name, *row, request_id, request_id))
                inserted += result.rowcount
                if not result.rowcount:
                    store.db.execute("""UPDATE trades SET platform_code=?,trade_time=?,price_cny=?,trade_num=?,
                        paint_index=?,paint_seed=?,wear_decimal=?,wear_value=?,min_sell_price_cny=?,
                        special_style_json=?,stickers_json=?,last_request=?
                        WHERE market_hash_name=? AND source_trade_id=?""",
                        (*row[1:], request_id, name, row[0]))
                times.append(row[2])
            else:
                key = (name, job["platform"], job["period"], job["style"])
                result = store.db.execute("INSERT OR IGNORE INTO bars VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                          (*key, *row, request_id))
                inserted += result.rowcount
                if not result.rowcount:
                    store.db.execute("""UPDATE bars SET bucket_time=?,open_cny=?,close_cny=?,high_cny=?,low_cny=?,
                        source_volume=?,source_turnover_cny=?,source_request=?
                        WHERE market_hash_name=? AND platform=? AND period=? AND style=? AND source_time=?""",
                        (*row[1:], request_id, *key, row[0]))
                times.append(row[0])
        if next_cursor:
            store.db.execute("INSERT OR IGNORE INTO checkpoints VALUES(?,?,?)", (job["job_id"], next_cursor, request_id))
        low = min(times + ([job["min_time"]] if job["min_time"] is not None else []), default=None)
        high = max(times + ([job["max_time"]] if job["max_time"] is not None else []), default=None)
        store.db.execute("""UPDATE jobs SET cursor=?,state=?,pages=pages+1,fetched_rows=fetched_rows+?,
            inserted_rows=inserted_rows+?,min_time=?,max_time=?,finish_reason=?,last_error=NULL,updated_at=? WHERE job_id=?""",
            (next_cursor, "done" if reason else "pending", len(rows), inserted, low, high, reason, now(), job["job_id"]))
    return inserted


def work(store, max_pages=30, delay=2.5, retry_blocked=False, client=None, emit=print, max_storage_mb=2048):
    if max_pages < 0:
        raise CollectionError("max-pages must be nonnegative; zero means all queued pages")
    if max_storage_mb <= 0:
        raise CollectionError("Storage budget must be positive")
    client = client or WebsiteClient(store.archive, delay)
    pages = 0
    stopped = None
    with store.worker_lock():
        if retry_blocked:
            with store.db:
                store.db.execute("UPDATE jobs SET state='pending',last_error=NULL WHERE state='blocked'")
        while not max_pages or pages < max_pages:
            if store.disk_bytes() >= max_storage_mb * 1024 * 1024:
                stopped = "Local database/raw storage budget reached; checkpoints retained"
                break
            job = store.db.execute("SELECT * FROM jobs WHERE state='pending' ORDER BY priority,pages,job_id LIMIT 1").fetchone()
            if job is None:
                break
            try:
                name = job["market_hash_name"]
                item = store.db.execute("SELECT * FROM catalog WHERE market_hash_name=?", (name,)).fetchone()
                if not item["steamdt_item_id"]:
                    resolve_item(store, client, name)
                    item = store.db.execute("SELECT * FROM catalog WHERE market_hash_name=?", (name,)).fetchone()
                styles_for_job(store, client, job, item)
                rows, cursor, reason, request_id = fetch_page(client, job, item["steamdt_item_id"])
                added = commit_page(store, job, rows, cursor, reason, request_id)
                pages += 1
                emit(json.dumps({"job": job["job_id"], "name": name, "kind": job["kind"], "style": job["style"],
                                 "page": job["pages"] + 1, "received": len(rows), "new_rows": added,
                                 "state": "done" if reason else "pending"}, ensure_ascii=False), flush=True)
            except CollectionError as error:
                stopped = str(error)
                with store.db:
                    store.db.execute("UPDATE jobs SET state=?,last_error=?,updated_at=? WHERE job_id=?",
                        ("blocked" if isinstance(error, AccessStopped) else "pending", stopped, now(), job["job_id"]))
                break
    return {"committed_pages": pages, "http_requests": getattr(client, "requests", None), "stopped": stopped}
