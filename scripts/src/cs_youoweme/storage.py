"""Persist raw evidence, tables, quality reports and local SQLite history."""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from .errors import CollectionError
from .paths import ROOT, LOCAL_DATA, CHINA

ITEM_FIELDS = [
    "run_id", "collected_at", "source", "source_url", "raw_path", "raw_sha256",
    "item_id", "market_hash_name", "name_zh", "weapon", "skin_en", "quality",
    "exterior", "rarity", "display_sell_price_cny", "item_updated_at",
    "survive_count", "holders_count", "added_count", "estimated_trade_count_today",
    "turnover_rate_raw", "volume_ratio_raw", "diff_1day_pct_raw", "diff_7day_pct_raw",
    "diff_30day_pct_raw", "diff_6month_pct_raw", "analysis_tags_json",
]
QUOTE_FIELDS = [
    "run_id", "collected_at", "source", "source_url", "raw_path", "raw_sha256",
    "market_hash_name", "platform", "platform_name", "platform_item_id", "currency",
    "raw_sell_price", "sell_price_cny", "has_positive_sell_quote", "sell_count",
    "raw_bid_price", "bid_price_cny", "bid_count", "source_update_time_raw",
    "source_updated_at", "quote_age_hours", "is_stale_24h", "market_url",
]
VARIANT_FIELDS = [
    "run_id", "collected_at", "source_url", "raw_path", "raw_sha256", "item_id",
    "market_hash_name", "name_zh", "weapon", "skin_en", "quality", "exterior",
    "raw_sell_price", "sell_price_cny", "survive_count", "source_updated_at",
]


def dump_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(path)


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def save_raw(run_dir, name, content):
    path = run_dir / "raw" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path.relative_to(ROOT).as_posix(), hashlib.sha256(content).hexdigest()


def start_run(kind):
    now = datetime.now(CHINA)
    run_id = now.strftime("%Y%m%dT%H%M%S_%f") + "_" + kind
    run_dir = LOCAL_DATA / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def commit_sqlite(run_id, manifest, items, quotes, variants):
    LOCAL_DATA.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(LOCAL_DATA / "steamdt.sqlite")) as db, db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS items (
                run_id TEXT, market_hash_name TEXT, payload_json TEXT NOT NULL,
                PRIMARY KEY (run_id, market_hash_name));
            CREATE TABLE IF NOT EXISTS quotes (
                run_id TEXT, market_hash_name TEXT, platform TEXT, payload_json TEXT NOT NULL,
                PRIMARY KEY (run_id, market_hash_name, platform));
            CREATE TABLE IF NOT EXISTS variants (
                run_id TEXT, market_hash_name TEXT, payload_json TEXT NOT NULL,
                PRIMARY KEY (run_id, market_hash_name));
        """)
        db.execute("INSERT INTO runs VALUES (?, ?)", (run_id, json.dumps(manifest, ensure_ascii=False)))
        for table, rows in (("items", items), ("quotes", quotes), ("variants", variants)):
            for row in rows:
                keys = [run_id, row["market_hash_name"]]
                if table == "quotes":
                    keys.append(row["platform"])
                keys.append(json.dumps(row, ensure_ascii=False, allow_nan=False))
                placeholders = ",".join("?" for _ in keys)
                db.execute(f"INSERT INTO {table} VALUES ({placeholders})", keys)


def finish_run(run_id, run_dir, kind, names, items, quotes, variants, errors, extra=None):
    keys = [(row["market_hash_name"], row["platform"]) for row in quotes]
    if len(keys) != len(set(keys)):
        raise CollectionError("Duplicate item/platform quotes; refusing misleading output")
    collected = {row["market_hash_name"] for row in items} if kind == "public" else {row["market_hash_name"] for row in quotes}
    successful_names = [name for name in names if name in collected]
    non_positive = sum(not row["has_positive_sell_quote"] for row in quotes)
    stale = sum(row["is_stale_24h"] == 1 for row in quotes)
    future = sum(row["quote_age_hours"] is not None and row["quote_age_hours"] < -0.1 for row in quotes)
    manifest = {
        "run_id": run_id, "mode": kind, "status": "complete" if len(successful_names) == len(names) and not errors else "partial",
        "finished_at": datetime.now(CHINA).isoformat(timespec="seconds"), "timezone": "Asia/Shanghai",
        "currency": "CNY", "requested_items": names, "successful_items": successful_names,
        "item_rows": len(items), "quote_rows": len(quotes), "related_variant_rows": len(variants),
        "positive_sell_quote_rows": len(quotes) - non_positive, "non_positive_or_missing_quote_rows": non_positive,
        "stale_24h_quote_rows": stale, "future_timestamp_quote_rows": future,
        "missing_quote_timestamp_rows": sum(row["source_updated_at"] is None for row in quotes),
        "errors": errors, "sample_design": "Purposeful pilot of common weapon skins, Field-Tested, ordinary quality. Not a representative market sample.",
        "notes": [
            "Sell quotes are asking prices, not realized transaction prices.",
            "transactionCount in public payload is displayed as estimated trades today, not verified trade tape.",
            "Source zero/nonpositive prices remain in raw fields; cleaned price is null, not free merchandise.",
            "Collection time differs from source update time. Old quotes are retained and flagged.",
            "24h staleness threshold is a research QA choice, not a platform rule.",
            "Public quote counts and bidding data are unavailable and remain null.",
            "Public turnover and percentage fields keep their original scale pending definition verification.",
            "These are item types by marketHashName, not individual asset IDs or float values.",
        ],
        **(extra or {}),
    }
    write_csv(run_dir / "tables" / "items.csv", items, ITEM_FIELDS)
    write_csv(run_dir / "tables" / "quotes.csv", quotes, QUOTE_FIELDS)
    write_csv(run_dir / "tables" / "related_variants.csv", variants, VARIANT_FIELDS)
    dump_json(run_dir / "reports" / "manifest.json", manifest)
    commit_sqlite(run_id, manifest, items, quotes, variants)
    dump_json(LOCAL_DATA / "latest_run.json", {"run_id": run_id, "path": run_dir.relative_to(ROOT).as_posix(), "status": manifest["status"]})
    quality = f"""# 本次采集检查

- 状态：{manifest['status']}
- 请求商品：{len(names)}，成功商品：{len(successful_names)}
- 商品信息：{len(items)} 行；平台报价：{len(quotes)} 行；页面关联规格：{len(variants)} 行
- 正数在售报价：{len(quotes) - non_positive} 行
- 零值、非正数或缺失报价：{non_positive} 行，清洗价格列留空
- 超过 24 小时未更新：{stale} 行，保留并标记
- 明显晚于采集时间的来源时间：{future} 行

每条数据有采集时间、来源地址、原始文件路径和 SHA-256。市场名称和平台联合键无重复。
本批是便利试采样本；关联规格只提供少数字段，不能视作完整商品详情。
在售报价、存世量、今日推算成交均沿用来源口径，不代表真实逐笔交易数据。
本次没有历史日线。`reports/manifest.json` 保留错误和完整范围。
"""
    (run_dir / "reports" / "quality_report.md").write_text(quality, encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": manifest["status"], "items": len(items), "quotes": len(quotes), "variants": len(variants), "positive_quotes": len(quotes)-non_positive, "path": str(run_dir)}, ensure_ascii=False), flush=True)
    return 0 if manifest["status"] == "complete" else 2
