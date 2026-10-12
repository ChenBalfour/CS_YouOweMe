"""Coverage reports and parameterized queries; exports contain market facts only."""
from __future__ import annotations

import csv
from pathlib import Path

from ..errors import CollectionError
from ..paths import LOCAL_DATA


def status(store, limit=20):
    db = store.db
    return {
        "database": str(store.path),
        "catalog_categories": {r[0]: r[1] for r in db.execute("SELECT category,count(*) FROM catalog GROUP BY category")},
        "resolved_steamdt_ids": db.execute("SELECT count(*) FROM catalog WHERE steamdt_item_id IS NOT NULL").fetchone()[0],
        "trade_rows": db.execute("SELECT count(*) FROM trades").fetchone()[0],
        "bar_rows": db.execute("SELECT count(*) FROM bars").fetchone()[0],
        "style_dimensions": db.execute("SELECT count(*) FROM styles").fetchone()[0],
        "requests": db.execute("SELECT count(*) FROM requests").fetchone()[0],
        "database_and_raw_mb": round(store.disk_bytes() / 1024 / 1024, 2),
        "job_states": {r[0]: r[1] for r in db.execute("SELECT state,count(*) FROM jobs GROUP BY state")},
        "jobs": [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY priority,job_id LIMIT ?", (limit,))],
        "interpretation": "done means source pagination ended; it does not certify complete market coverage",
    }


def coverage(store, name, kind="bars", period="1h", platform="ALL", style=""):
    if kind == "trades":
        period = "event"
    jobs = store.db.execute("SELECT * FROM jobs WHERE market_hash_name=? AND kind=? AND period=? AND platform=? AND style=?",
                            (name, kind, period, platform, style)).fetchall()
    reports = []
    for job in jobs:
        report = {k: job[k] for k in ("job_id", "state", "start_time", "end_time", "pages", "fetched_rows", "min_time", "max_time", "finish_reason", "last_error")}
        if kind == "bars":
            width = 3600 if period == "1h" else 86400
            offset = 0 if period == "1h" else 28800
            first = (job["start_time"] + offset) // width * width - offset
            exclusive = (job["end_time"] - 1 + offset) // width * width - offset + width
            rows = store.db.execute("""SELECT source_time,bucket_time,source_volume,source_turnover_cny FROM bars
                WHERE market_hash_name=? AND period=? AND platform=? AND style=? AND source_time>=? AND source_time<?
                ORDER BY bucket_time,source_time""",
                (name, period, platform, style, job["start_time"], job["end_time"])).fetchall()
            buckets = sorted({r["bucket_time"] for r in rows})
            cursor = first
            gaps = []
            for bucket in buckets:
                if bucket > cursor:
                    gaps.append({"start_inclusive": cursor, "end_exclusive": bucket, "buckets": (bucket - cursor) // width})
                cursor = max(cursor, bucket + width)
            if cursor < exclusive:
                gaps.append({"start_inclusive": cursor, "end_exclusive": exclusive, "buckets": (exclusive - cursor) // width})
            report.update({"expected_buckets": (exclusive - first) // width, "observed_buckets": len(buckets),
                           "missing_buckets": sum(g["buckets"] for g in gaps), "gaps": gaps,
                           "null_volume_rows": sum(r["source_volume"] is None for r in rows),
                           "null_turnover_rows": sum(r["source_turnover_cny"] is None for r in rows),
                           "unaligned_timestamps": sum(r["source_time"] != r["bucket_time"] for r in rows),
                           "extra_rows_in_same_bucket": len(rows) - len(buckets),
                           "complete_buckets": len(buckets) == (exclusive - first) // width,
                           "last_bucket_may_be_partial": True})
        else:
            report["coverage_note"] = "source-reported trade observations; no assertion that every market sale is captured"
        reports.append(report)
    return {"market_hash_name": name, "kind": kind, "period": period, "platform": platform, "style": style, "coverage": reports}


def trade_query(store, name, start=None, end=None, wear_min=None, wear_max=None, paint_seed=None, limit=100):
    if not 1 <= limit <= 10000:
        raise CollectionError("Trade query limit must be between 1 and 10000")
    terms, values = ["market_hash_name=?"], [name]
    for sql, value in (("trade_time>=?", start), ("trade_time<?", end),
                       ("wear_value>=?", wear_min), ("wear_value<=?", wear_max), ("paint_seed=?", paint_seed)):
        if value is not None:
            terms.append(sql)
            values.append(value)
    columns = "source_trade_id,platform_code,trade_time,price_cny,trade_num,paint_index,paint_seed,wear_decimal,min_sell_price_cny,special_style_json,stickers_json,source_request,last_request"
    rows = store.db.execute("SELECT " + columns + " FROM trades WHERE " + " AND ".join(terms)
                            + " ORDER BY trade_time DESC,source_trade_id DESC LIMIT ?", (*values, limit)).fetchall()
    return {"market_hash_name": name, "rows": [dict(row) for row in rows]}


def export_table(store, table, destination):
    destination = Path(destination).resolve()
    if not destination.is_relative_to(LOCAL_DATA.resolve()):
        raise CollectionError("Market exports must stay inside ignored data/local/")
    allowed = {"catalog", "platform_ids", "styles", "trades", "bars", "jobs"}
    if table not in allowed:
        raise CollectionError("Unsupported export table")
    destination.parent.mkdir(parents=True, exist_ok=True)
    cursor = store.db.execute("SELECT * FROM " + table)
    fields = [column[0] for column in cursor.description]
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    count = 0
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        for row in cursor:
            writer.writerow(row)
            count += 1
    temporary.replace(destination)
    return {"table": table, "rows": count, "path": str(destination)}
