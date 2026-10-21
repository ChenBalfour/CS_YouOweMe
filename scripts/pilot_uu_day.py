"""Collect one complete Beijing day for one ordinary weapon into a fresh pilot."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import csv
from datetime import datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sqlite3
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from cs_youoweme import __version__
from cs_youoweme.collectors.website import ITEM, SYSTEM, WebsiteClient
from cs_youoweme.errors import CollectionError
from cs_youoweme.history.catalog import dimensions, upsert_item
from cs_youoweme.history.jobs import plan, work
from cs_youoweme.history.query import coverage
from cs_youoweme.history.store import DEFAULT_DB, Store, now
from cs_youoweme.paths import CHINA, LOCAL_DATA, ROOT


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sha(path):
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run(args):
    category, _, _, quality, exterior, _ = dimensions(args.name)
    if category != "weapon" or quality != "normal" or not exterior:
        raise CollectionError("Pilot requires one exact ordinary weapon/exterior name")
    start_date = datetime.fromisoformat(args.date)
    if len(args.date) != 10 or start_date.time().isoformat() != "00:00:00":
        raise CollectionError("Pilot date must be YYYY-MM-DD")
    start = start_date.replace(tzinfo=CHINA)
    end = start + timedelta(days=1)
    if end > datetime.now(CHINA):
        raise CollectionError("Select a complete past Beijing day")
    if not 1 <= args.max_pages <= 10 or not 2 <= args.delay <= 30:
        raise CollectionError("Pilot budget: 1-10 history pages, request delay 2-30 seconds")
    stamp = datetime.now(CHINA).strftime("%Y%m%dT%H%M%S+0800")
    run_id = f"p03_steamdt_uu_{stamp}_{uuid.uuid4().hex[:6]}"
    directory = LOCAL_DATA / "staging" / "steamdt" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    source_directory = ROOT / "scripts/local/pilot_sources" / run_id
    source_directory.mkdir(parents=True, exist_ok=False)
    source_snapshot = source_directory / "collect_v1.py"
    source_snapshot.write_bytes(Path(__file__).read_bytes())
    tables, reports = directory / "tables", directory / "reports"
    reports.mkdir()
    legacy_hash = sha(DEFAULT_DB)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    modified = subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, capture_output=True, text=True, check=True).stdout != ""
    manifest = {"manifest_version": "pilot-1.0", "run_id": run_id, "asset_status": "candidate", "phase": "user-authorized-single-day-data-feasibility-pilot", "source": "steamdt-anonymous-website", "requested_venue": "YOUPIN", "market_hash_name": args.name, "timezone": "Asia/Shanghai", "start_inclusive": start.isoformat(), "end_exclusive": end.isoformat(), "code_version": __version__, "base_commit": revision, "working_tree_modified": modified, "pilot_script_sha256": sha(Path(__file__)), "pilot_source_snapshot": source_snapshot.relative_to(ROOT).as_posix(), "started_at_utc": now(), "request_budget": {"history_pages": args.max_pages, "delay_seconds": args.delay, "storage_mib": 16}, "legacy_db_sha256_before": legacy_hash}
    dump(reports / "manifest.json", manifest)
    print(json.dumps({"run_id": run_id, "item": args.name, "date": args.date, "requested_platform": "YOUPIN"}, ensure_ascii=False), flush=True)
    failure = None
    result = {}
    platform_evidence = {}
    with Store(directory / "pilot.sqlite") as store:
        client = WebsiteClient(store.archive, args.delay)
        try:
            item, request_id = client.call(ITEM, {"appId": 730, "marketHashName": args.name}, post=True)
            if not isinstance(item, dict) or item.get("marketHashName") != args.name or not item.get("itemId"):
                raise CollectionError("Pilot website item identity mismatch")
            upsert_item(store.db, {"marketHashName": args.name, "name": item.get("name"), "platformList": []}, request_id)
            with store.db:
                store.db.execute("UPDATE catalog SET steamdt_item_id=?,metadata_request=? WHERE market_hash_name=?", (str(item["itemId"]), request_id, args.name))
            config_row = store.db.execute("SELECT raw_path,request_id FROM requests WHERE endpoint=? ORDER BY request_id DESC LIMIT 1", (SYSTEM,)).fetchone()
            if config_row and config_row["raw_path"]:
                config = json.loads(gzip.decompress((directory / config_row["raw_path"]).read_bytes())).get("data", {})
                matches = [row for row in config.get("comparePricePlatformList", []) if isinstance(row, dict) and row.get("key") == "YOUPIN"]
                platform_evidence["system_config"] = {"request_id": config_row["request_id"], "YOUPIN_label": matches[0].get("name") if matches else None}
            quotes = [row for row in item.get("sellingPriceList", []) if isinstance(row, dict) and str(row.get("platform", "")).upper() == "YOUPIN"]
            platform_evidence["current_item_quote"] = {"request_id": request_id, "platform": "YOUPIN", "platform_name": quotes[0].get("platformName") if quotes else None, "price_cny": quotes[0].get("price") if quotes else None, "source_update_time": quotes[0].get("updateTime") if quotes else None, "note": "current observation, not a historical quote for the requested date"}
            manifest["steamdt_item_id"] = str(item["itemId"])
            manifest["name_zh"] = item.get("name")
            dump(reports / "platform_evidence.json", platform_evidence)
            plan(store, int(start.timestamp()), int(end.timestamp()), names=[args.name], categories=["weapon"], kinds=["bars", "trades"], platforms=["YOUPIN"], period="1h")
            result = work(store, max_pages=args.max_pages, delay=args.delay, client=client, max_storage_mb=16)
        except CollectionError as error:
            failure = str(error)
        bars = [dict(row) for row in store.db.execute("SELECT source_time,bucket_time,open_cny,close_cny,high_cny,low_cny,source_volume,source_turnover_cny,source_request FROM bars WHERE platform='YOUPIN' ORDER BY source_time")]
        for row in bars:
            row.update({"market_hash_name": args.name, "platform": "YOUPIN", "source_time_beijing": datetime.fromtimestamp(row["source_time"], CHINA).isoformat(), "bucket_time_beijing": datetime.fromtimestamp(row["bucket_time"], CHINA).isoformat(), "period": "1h", "source": "steamdt"})
        hourly = tables / "uu_hourly.csv"
        write_csv(hourly, ["market_hash_name", "source", "platform", "period", "source_time", "source_time_beijing", "bucket_time", "bucket_time_beijing", "open_cny", "high_cny", "low_cny", "close_cny", "source_volume", "source_turnover_cny", "source_request"], bars)
        trades = [dict(row) for row in store.db.execute("SELECT source_trade_id,platform_code,trade_time,price_cny,trade_num,paint_index,paint_seed,wear_decimal,min_sell_price_cny,source_request FROM trades ORDER BY trade_time,source_trade_id")]
        for row in trades:
            row.update({"market_hash_name": args.name, "trade_time_beijing": datetime.fromtimestamp(row["trade_time"], CHINA).isoformat(), "venue": "unknown", "source": "steamdt"})
        write_csv(tables / "source_trades_unmapped.csv", ["market_hash_name", "source", "venue", "platform_code", "source_trade_id", "trade_time", "trade_time_beijing", "price_cny", "trade_num", "paint_index", "paint_seed", "wear_decimal", "min_sell_price_cny", "source_request"], trades)
        jobs = [dict(row) for row in store.db.execute("SELECT kind,platform,period,state,pages,fetched_rows,inserted_rows,finish_reason,last_error FROM jobs ORDER BY job_id")]
        reports_coverage = coverage(store, args.name, platform="YOUPIN")["coverage"]
        requests = [dict(row) for row in store.db.execute("SELECT request_id,endpoint,http_status,error_code,raw_path,raw_sha256,collected_at FROM requests ORDER BY request_id")]
        dump(reports / "requests.json", requests)
        manifest.update({"completed_at_utc": now(), "result": result, "failure": failure, "jobs": jobs, "http_requests": client.requests, "hourly_rows": len(bars), "trade_source_rows": len(trades), "trade_platform_codes": dict(Counter(row["platform_code"] for row in trades)), "trade_venue_mapping": "unverified; no records certified as UU", "capability_level": "L0-source-reported-UU-hourly-price-observations" if bars else "no-usable-price-data", "platform_evidence": platform_evidence, "coverage": reports_coverage, "expected_hour_buckets": 24, "observed_hour_buckets": len({row["bucket_time"] for row in bars}), "missing_hour_buckets": 24 - len({row["bucket_time"] for row in bars}), "source_volume_note": "source-reported; true executed volume versus inferred volume not yet established", "legacy_db_sha256_after": sha(DEFAULT_DB)})
    manifest["legacy_db_unchanged"] = manifest["legacy_db_sha256_after"] == legacy_hash
    manifest["output_files"] = [{"path": path.relative_to(directory).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size} for path in sorted(directory.rglob("*")) if path.is_file() and path != reports / "manifest.json"]
    dump(reports / "manifest.json", manifest)
    stopped = failure or result.get("stopped")
    report_path = ROOT / "docs/local/pilots" / (run_id + ".md")
    text = f"""# 单品单日试跑

报告版本 pilot-1.0；代码 {__version__}，运行 {run_id}。资产为 candidate，不是正式数据集。

- 商品：{args.name}；SteamDT 编号：{manifest.get('steamdt_item_id', '未取得')}。
- 窗口：{start.isoformat()} 至 {end.isoformat()}，左闭右开。
- 来源：SteamDT 匿名网页接口；小时行情请求平台 YOUPIN。
- 小时记录：{len(bars)}；小时桶：{manifest['observed_hour_buckets']}/24；缺失：{manifest['missing_hour_buckets']}。
- 混合来源成交记录：{len(trades)}；平台代码：{manifest['trade_platform_codes']}。代码未映射，不认定这些为 UU 成交。
- 请求数：{client.requests}；历史页预算：{args.max_pages}；间隔：{args.delay} 秒。
- 停止原因：{stopped or '来源分页完成或到达设定页预算'}。
- 旧市场库内容保持一致：{manifest['legacy_db_unchanged']}。

小时 OHLC、量额按来源原样保留，缺失不填零；量额是否真实成交仍待口径核验。当前报价属于采集时刻，不能回填到历史日。小时覆盖齐全不证明完整成交、可执行买卖价格或退出能力。

数据、请求记录、原始响应及 SHA-256 位于项目 data/local/staging/steamdt/{run_id}。uu_hourly.csv 为来源标称 UU 行情；source_trades_unmapped.csv 为待映射混合成交；pilot.sqlite 为独立试跑库。原始响应私有，不公开。
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8", newline="\n")
    summary = {"run_id": run_id, "hourly_rows": len(bars), "hour_buckets": manifest["observed_hour_buckets"], "trade_source_rows": len(trades), "http_requests": client.requests, "stopped": stopped, "legacy_db_unchanged": manifest["legacy_db_unchanged"], "data_path": str(directory), "report_path": str(report_path)}
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 2 if stopped or not bars or not manifest["legacy_db_unchanged"] else 0


def review(run_id):
    if Path(run_id).name != run_id or not run_id.startswith("p03_steamdt_uu_"):
        raise CollectionError("Review requires a pilot run ID, not a path")
    directory = LOCAL_DATA / "staging" / "steamdt" / run_id
    original_manifest = directory / "reports/manifest.json"
    manifest = json.loads(original_manifest.read_text(encoding="utf-8"))
    review_file = directory / "reports/quality_review_v1.json"
    if review_file.exists():
        raise CollectionError("Review version exists; preserve it and use a new review version")
    source_directory = ROOT / "scripts/local/pilot_sources" / run_id
    source_directory.mkdir(parents=True, exist_ok=True)
    source_snapshot = source_directory / "review_v1.py"
    if source_snapshot.exists():
        raise CollectionError("Review source version exists; do not overwrite it")
    source_snapshot.write_bytes(Path(__file__).read_bytes())
    requests = json.loads((directory / "reports/requests.json").read_text(encoding="utf-8"))
    raw = {}
    trade_pages = []
    for request in requests:
        content = gzip.decompress((directory / request["raw_path"]).read_bytes())
        if hashlib.sha256(content).hexdigest() != request["raw_sha256"]:
            raise CollectionError("Raw response integrity check failed")
        response = json.loads(content)
        raw[request["endpoint"]] = response
        if request["endpoint"] == "/item/trade/v1/list":
            trade_pages.append(response)
    item = raw[ITEM]["data"]
    quote = next((row for row in item.get("sellingPriceList", []) if str(row.get("platform", "")).upper() == "YOUPIN"), None)
    if item.get("marketHashName") != manifest["market_hash_name"] or not quote or quote.get("platformName") != "悠悠":
        raise CollectionError("Current quote does not confirm the UU platform label")
    with (directory / "tables/uu_hourly.csv").open(encoding="utf-8-sig") as handle:
        csv_rows = list(csv.DictReader(handle))
    start = int(datetime.fromisoformat(manifest["start_inclusive"]).timestamp())
    end = int(datetime.fromisoformat(manifest["end_exclusive"]).timestamp())
    from cs_youoweme.collectors.website import KLINE, TRADES
    from cs_youoweme.history.normalize import bar_record
    selected = [bar_record(row, "1h") for row in raw[KLINE]["data"]]
    selected = sorted(row for row in selected if start <= row[0] < end)
    if len(csv_rows) != len(selected):
        raise CollectionError("CSV row count differs from the requested raw history window")
    for row, source in zip(csv_rows, selected):
        values = [row[column] or None for column in ("open_cny", "close_cny", "high_cny", "low_cny", "source_volume", "source_turnover_cny")]
        expected = [str(value) if value is not None else None for value in source[2:]]
        if row["platform"] != "YOUPIN" or row["market_hash_name"] != manifest["market_hash_name"] or int(row["source_time"]) != source[0] or int(row["bucket_time"]) != source[1] or values != expected:
            raise CollectionError("CSV values differ from the original source response")
    # Each run is written once and closed before review; immutable avoids WAL sidecars.
    db_uri = (directory / "pilot.sqlite").resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(db_uri, uri=True)) as connection:
        params = json.loads(connection.execute("SELECT params_json FROM requests WHERE endpoint=?", (KLINE,)).fetchone()[0])
    if params.get("platform") != "YOUPIN" or params.get("type") != 1 or str(params.get("typeVal")) != str(item["itemId"]):
        raise CollectionError("Archived request scope differs from the requested UU hourly series")
    trades = [row for page in trade_pages for row in page["data"]["list"]]
    duplicate_count = sum(count - 1 for count in Counter((str(row["id"]), str(row["platform"])) for row in trades).values())
    quality = {"review_version": "pilot-review-1.0", "run_id": run_id, "original_manifest_sha256": sha(original_manifest), "review_script_sha256": sha(Path(__file__)), "reviewed_at_utc": now(), "source_raw_hashes_verified": len(requests), "csv_matches_raw": True, "source_platform_key": params["platform"], "quote_platform_key": quote["platform"], "quote_platform_label": quote["platformName"], "current_quote_cny": str(quote["price"]), "current_quote_is_historical": False, "expected_hour_buckets": 24, "observed_hour_buckets": len({row[1] for row in selected}), "null_volume_rows": sum(row[6] is None for row in selected), "null_turnover_rows": sum(row[7] is None for row in selected), "unaligned_source_timestamps": sum(row[0] != row[1] for row in selected), "trade_source_rows_raw": len(trades), "trade_source_rows_deduplicated": manifest["trade_source_rows"], "duplicate_source_records": duplicate_count, "trade_platform_codes_raw": dict(Counter(str(row["platform"]) for row in trades)), "uu_trade_mapping_verified": False, "legacy_db_unchanged": sha(DEFAULT_DB) == manifest["legacy_db_sha256_before"], "capability_level": "L0", "notes": ["Current item quotes use lower-case youpin; K-line selector uses upper-case YOUPIN.", "Volume and turnover nulls are retained, not filled with zero.", "Full hourly coverage does not certify real UU executed volume or executable prices.", "The screenshot product is a technical probe, not a formal universe admission."]}
    quality.update({"review_source_snapshot": source_snapshot.relative_to(ROOT).as_posix(), "source_bar_rows_raw": len(raw[KLINE]["data"]), "retained_hourly_rows": len(selected)})
    dump(review_file, quality)
    report = ROOT / "docs/local/pilots" / (run_id + "_review_v1.md")
    report.write_text(f"""# 悠悠单品单日试跑核验

核验版本 pilot-review-1.0，原始运行 {run_id}；商品 {manifest['market_hash_name']}，SteamDT 编号 {item['itemId']}。

| 检查项 | 结果 |
| --- | --- |
| 北京时间窗口 | {manifest['start_inclusive']} 至 {manifest['end_exclusive']}，左闭右开 |
| 平台证据 | K 线请求 YOUPIN；同商品当前报价键 youpin、名称“悠悠” |
| 小时价格 | {len(selected)} 条，覆盖 {quality['observed_hour_buckets']}/24 小时，CSV 与原始响应一致 |
| 原始响应 | {len(requests)} 份 SHA-256 核验通过 |
| 缺失成交量 | {quality['null_volume_rows']}/24 行，保留空值 |
| 缺失成交额 | {quality['null_turnover_rows']}/24 行，保留空值 |
| 非整点来源时间 | {quality['unaligned_source_timestamps']} 行，原始秒数保留，另存小时桶 |
| 成交分页 | 返回 {len(trades)} 条，重复 {duplicate_count} 条，去重保存 {manifest['trade_source_rows']} 条 |
| 成交平台 | 原始代码 {quality['trade_platform_codes_raw']}，尚未核验 UU 归属 |
| 旧库保护 | 旧市场库 SHA-256 一致：{quality['legacy_db_unchanged']} |

结论：SteamDT 的 YOUPIN 小时价格采集在该商品、该日期可用，当前能力 L0。量额仍有缺失且真实成交口径未确认；混合平台逐笔不能直接用于 UU 执行标签。当前悠悠报价 {quote['price']} 元属于采集时刻，不是所选历史日的价格。

原始响应、独立 pilot.sqlite、uu_hourly.csv、source_trades_unmapped.csv 及版本清单保留在 data/local/staging/steamdt/{run_id}。原始 manifest 保留，修正大小写匹配后的平台证据与核验结果另存 reports/quality_review_v1.json，不修改原始响应或历史数据。该规格仅作为技术样本，不代表正式选品；未启动长期采集或训练。
""", encoding="utf-8", newline="\n")
    print(json.dumps({"run_id": run_id, "csv_matches_raw": True, "hour_buckets": quality["observed_hour_buckets"], "null_volume_rows": quality["null_volume_rows"], "null_turnover_rows": quality["null_turnover_rows"], "uu_platform_label": quote["platformName"], "review_path": str(report)}, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="AK-47 | Cartel (Battle-Scarred)")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--date")
    scope.add_argument("--review-run", help="Verify one saved pilot offline and add a new review artifact")
    parser.add_argument("--max-pages", type=int, default=6)
    parser.add_argument("--delay", type=float, default=2.5)
    args = parser.parse_args()
    try:
        return review(args.review_run) if args.review_run else run(args)
    except (CollectionError, ValueError):
        print("Pilot input/collection failed; no response content or credentials printed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
