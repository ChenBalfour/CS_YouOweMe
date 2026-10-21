"""Bounded P02 research-universe survey; no training, trading or history queue."""
from __future__ import annotations

from collections import Counter
import argparse
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from cs_youoweme import __version__
from cs_youoweme.collectors.website import ATTRIBUTES, ITEM, KLINE, MARKET, WebsiteClient
from cs_youoweme.errors import CollectionError
from cs_youoweme.history.catalog import dimensions, upsert_item
from cs_youoweme.history.normalize import bar_record
from cs_youoweme.history.store import DEFAULT_DB, Store, compact, now
from cs_youoweme.history.universe import sector_types
from cs_youoweme.paths import CHINA, LOCAL_DATA, ROOT

PRIORITY = [
    "AK-47 | The Oligarch (Factory New)",
    "AK-47 | The Oligarch (Minimal Wear)",
    "AK-47 | The Oligarch (Field-Tested)",
    "AK-47 | Fuel Injector (Field-Tested)",
    "AK-47 | Fuel Injector (Minimal Wear)",
    "AK-47 | Fuel Injector (Battle-Scarred)",
]
START = int(datetime(2026, 10, 5, tzinfo=CHINA).timestamp())
END = int(datetime(2026, 10, 12, tzinfo=CHINA).timestamp())
LIMITS = {"ranking_pages": 2, "ranking_page_size": 20, "enrichments": 24, "http_requests": 60, "delay_seconds": 2.5, "storage_mib": 32, "main": 10, "reserve": 6}


def sha(path):
    if not path.exists():
        return None
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def uu_quote(item, observed):
    quote = next((q for q in item.get("sellingPriceList", []) if str(q.get("platform", "")).upper() == "YOUPIN"), None)
    if not quote:
        return None, None, None
    try:
        price = Decimal(str(quote.get("price")))
        updated = int(quote["updateTime"])
        if not price.is_finite() or price <= 0:
            return None, updated, quote.get("platformName")
        return str(price), updated, quote.get("platformName")
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return None, None, quote.get("platformName")


class BudgetClient(WebsiteClient):
    def __init__(self, store, prior_requests=0):
        self.store = store
        self.remaining_budget = LIMITS["http_requests"] - prior_requests
        super().__init__(store.archive, LIMITS["delay_seconds"])

    def _request(self, path, params, post):
        if self.requests >= self.remaining_budget or self.store.disk_bytes() >= LIMITS["storage_mib"] * 1024 * 1024:
            raise CollectionError("Finite P02 request/storage budget reached")
        return super()._request(path, params, post)


def choose(rows):
    for row in rows:
        for field in ("role", "reserve_reason", "selection_reasons"):
            row.pop(field, None)
    eligible = [row for row in rows if not row["exclusion_reasons"]]
    # Field observability is a data-quality criterion, not proof of market liquidity.
    eligible.sort(key=lambda row: (-row["price_hours"], -row["volume_hours"], -row["turnover_hours"], row["heat_position"] if row["heat_position"] is not None else 100000, row["market_hash_name"]))
    main, overflow = [], []
    families, weapons = Counter(), Counter()
    for row in eligible:
        if Decimal(row["uu_price_cny"]) >= 5000:
            row["reserve_reason"] = "5000 元以上，资金规模与退出证据敏感，先作高价候补"
            overflow.append(row)
            continue
        if families[row["family"]] or weapons[row["weapon"]] >= 4 or len(main) >= LIMITS["main"]:
            row["reserve_reason"] = "同涂装或武器相关、有限主力容量；用于候补比较"
            overflow.append(row)
            continue
        main.append(row)
        families[row["family"]] += 1
        weapons[row["weapon"]] += 1
    # Enforce the stated one-weapon <= half constraint using actual selected size.
    while main and max(Counter(row["weapon"] for row in main).values()) > len(main) / 2:
        weapon = Counter(row["weapon"] for row in main).most_common(1)[0][0]
        index = max(i for i, row in enumerate(main) if row["weapon"] == weapon)
        row = main.pop(index)
        row["reserve_reason"] = "控制单一武器在实际名单中的占比"
        overflow.append(row)
    reserves = overflow[:LIMITS["reserve"]]
    for row in rows:
        row["role"] = "main" if row in main else "reserve" if row in reserves else "excluded" if row["exclusion_reasons"] else "observe"
        reasons = ["UU 报价与平台身份可核验", f"7 日小时价格 {row.get('price_hours', 0)}/168", f"可观察量额小时 {row.get('volume_hours', 0)}/{row.get('turnover_hours', 0)}，不视为完整成交"] if not row["exclusion_reasons"] else list(row["exclusion_reasons"])
        if row.get("heat_position"):
            reasons.append(f"有限来源关注排序第 {row['heat_position']}，非 UU 成交排名")
        if row.get("reserve_reason"):
            reasons.append(row["reserve_reason"])
        if row["role"] == "main":
            reasons.append("家族分散后的主力验证对象；须在 P03 补充执行证据")
        row["selection_reasons"] = reasons
    return main, reserves


def run(supplement=None):
    base_profile, base_manifest = None, None
    if supplement:
        supplement = Path(supplement).resolve()
        if not supplement.is_relative_to((LOCAL_DATA / "universes").resolve()):
            raise CollectionError("Supplement must reference a private universe selection")
        base_profile = json.loads(supplement.read_text(encoding="utf-8"))
        base_manifest = json.loads((LOCAL_DATA / "staging/steamdt" / base_profile["parent_run_id"] / "reports/manifest.json").read_text(encoding="utf-8"))
    stamp = datetime.now(CHINA).strftime("%Y%m%dT%H%M%S+0800")
    token = uuid.uuid4().hex[:6]
    run_id = f"p02_steamdt_selection_{stamp}_{token}"
    run_dir = LOCAL_DATA / "staging/steamdt" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    source_dir = ROOT / "scripts/local/selection_sources" / run_id
    source_dir.mkdir(parents=True, exist_ok=False)
    source_snapshot = source_dir / "collect_v1.py"
    source_snapshot.write_bytes(Path(__file__).read_bytes())
    plan_path = ROOT / "docs/research/SELECTION_PLAN.md"
    before = sha(DEFAULT_DB)
    manifest = {"version": "p02-survey-1.0", "run_id": run_id, "phase": "P02", "started_at_utc": now(), "selection_plan_sha256": sha(plan_path), "source_script_sha256": sha(Path(__file__)), "source_snapshot": source_snapshot.relative_to(ROOT).as_posix(), "base_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(), "code_version": __version__, "scope": "bounded ordinary weapon research candidates; no orders, training or long collection", "history_window_beijing": [datetime.fromtimestamp(START, CHINA).isoformat(), datetime.fromtimestamp(END, CHINA).isoformat()], "limits": LIMITS, "legacy_db_sha256_before": before}
    dump(run_dir / "reports/manifest.json", manifest)
    print(json.dumps({"run_id": run_id, "phase": "P02", "candidate_budget": LIMITS["enrichments"]}, ensure_ascii=False), flush=True)
    candidates = base_profile["all_candidates"] if base_profile else []
    for row in candidates:
        row["source_run_id"] = base_profile["parent_run_id"]
        row["exclusion_reasons"] = [reason for reason in row["exclusion_reasons"] if not reason.startswith("有限来源关注排序")]
        if "Gold Arabesque" in row["market_hash_name"]:
            row["origin"] = "legacy-alias-corrected-extra-reference"
    ranking_rows, skipped = [], base_profile["skipped_ranking_rows"] if base_profile else []
    stopped = None
    with Store(run_dir / "survey.sqlite") as store:
        client = BudgetClient(store, base_manifest["http_requests"] if base_manifest else 0)
        try:
            if base_profile:
                pool = [{"name": name, "origin": "identity-correction" if "The Oligarch" in name else "weapon-diversity-control", "ranking": None} for name in ["AK-47 | The Oligarch (Factory New)", "AK-47 | The Oligarch (Minimal Wear)", "AK-47 | The Oligarch (Field-Tested)", "AWP | Asiimov (Field-Tested)"]]
                attributes = None
            else:
                attributes, attribute_request = client.call(ATTRIBUTES)
            if attributes is not None:
                pool = ranked_pool(client, attributes, ranking_rows, skipped)
            for entry in pool:
                # Every added candidate is attributed to its actual raw-response run.
                if len(candidates) >= LIMITS["enrichments"]:
                    break
                row = enrich(store, client, entry)
                row["source_run_id"] = run_id
                candidates.append(row)
                print(json.dumps({"candidate": entry["name"], "uu_price_cny": row["uu_price_cny"], "price_hours": row["price_hours"], "known_volume_hours": row["volume_hours"], "excluded": bool(row["exclusion_reasons"])}, ensure_ascii=False), flush=True)
        except CollectionError as error:
            stopped = str(error)
        manifest["http_requests"] = client.requests
        dump(run_dir / "reports/requests.json", [dict(row) for row in store.db.execute("SELECT request_id,endpoint,collected_at,http_status,error_code,raw_path,raw_sha256 FROM requests ORDER BY request_id")])
    main, reserves = choose(candidates)
    return finish(run_dir, manifest, candidates, ranking_rows, skipped, stopped, main, reserves, before, stamp, token, base_profile, base_manifest)


def ranked_pool(client, attributes, ranking_rows, skipped):
    types = sector_types(attributes)["weapon"]
    cursor = ""
    for page in range(LIMITS["ranking_pages"]):
        data, request_id = client.call(MARKET, {"dataField": "pvNums", "dataRange": "", "sortType": "desc", "nextId": cursor, "queryName": "", "pageSize": LIMITS["ranking_page_size"], "typeList": types}, post=True)
        if not isinstance(data, dict) or not isinstance(data.get("list"), list) or "nextId" not in data:
            raise CollectionError("P02 ranking response schema changed")
        for row in data["list"]:
            ranking_rows.append({"item": row, "position": len(ranking_rows) + 1, "request_id": request_id})
        next_cursor = data["nextId"]
        if not next_cursor:
            break
        if not isinstance(next_cursor, str) or next_cursor == cursor:
            raise CollectionError("P02 ranking cursor made no progress")
        cursor = next_cursor
    positions = {row["item"].get("marketHashName"): row for row in ranking_rows}
    pool = [{"name": name, "origin": "user-example", "ranking": positions.get(name)} for name in PRIORITY]
    seen = set(PRIORITY)
    seen_families = set()
    for ranked in ranking_rows:
        item = ranked["item"]
        name = item.get("marketHashName", "")
        category, weapon, skin, quality, exterior, family = dimensions(name)
        price, _, _ = uu_quote(item, int(time.time()))
        if name in seen:
            continue
        if category != "weapon" or quality != "normal" or not exterior:
            skipped.append({"name": name, "reason": "非普通枪皮精确磨损规格", "heat_position": ranked["position"]})
            continue
        if price is not None and not Decimal(100) <= Decimal(price) < Decimal(10000):
            skipped.append({"name": name, "reason": "排序行 UU 报价不在本轮价格层", "heat_position": ranked["position"], "uu_price_cny": price})
            continue
        if family in seen_families:
            skipped.append({"name": name, "reason": "关注榜重复涂装，节省详情请求预算", "heat_position": ranked["position"]})
            continue
        seen.add(name)
        seen_families.add(family)
        pool.append({"name": name, "origin": "source-attention-ranking", "ranking": ranked})
        if len(pool) >= LIMITS["enrichments"]:
            break

    return pool


def enrich(store, client, entry):
    observed = now()
    item, item_request = client.call(ITEM, {"appId": 730, "marketHashName": entry["name"]}, post=True)
    if not isinstance(item, dict) or item.get("marketHashName") != entry["name"] or not item.get("itemId"):
        raise CollectionError("P02 item identity mismatch")
    category, weapon, skin, quality, exterior, family = dimensions(entry["name"])
    price, updated, label = uu_quote(item, int(time.time()))
    age = int(time.time()) - updated if updated is not None else None
    row = {"market_hash_name": entry["name"], "name_zh": item.get("name"), "weapon": weapon, "skin": skin, "family": family, "quality": quality, "exterior": exterior, "steamdt_item_id": str(item["itemId"]), "origin": entry["origin"], "heat_position": entry["ranking"]["position"] if entry["ranking"] else None, "uu_price_cny": price, "price_band": "hundreds" if price is not None and Decimal(price) < 1000 else "thousands" if price else "unknown", "quote_age_seconds": age, "source_updated_at_beijing": datetime.fromtimestamp(updated, CHINA).isoformat() if updated else None, "observed_at_utc": observed, "uu_platform_name": label, "source_supply": item.get("surviveNum"), "source_holders": item.get("holdersNum"), "source_estimated_trades_today_all_platforms": item.get("transactionCount"), "metadata_request": item_request, "ranking_request": entry["ranking"]["request_id"] if entry["ranking"] else None, "exclusion_reasons": [], "unknown_fields": ["UU 可比在售数量", "UU 求购价及深度", "UU 真实成交完整率", "退出等待与执行概率", "属性溢价影响"], "price_hours": 0, "volume_hours": 0, "turnover_hours": 0}
    if price is None:
        row["exclusion_reasons"].append("无正 UU 报价")
    elif not Decimal(100) <= Decimal(price) < Decimal(10000):
        row["exclusion_reasons"].append("UU 价格不在 [100,10000) 元")
    if label != "悠悠":
        row["exclusion_reasons"].append("UU 平台显示名未确认")
    if age is None or not -30 <= age <= 3600:
        row["exclusion_reasons"].append("UU 报价时间缺失或超过 1 小时")
    upsert_item(store.db, item, item_request)
    with store.db:
        store.db.execute("UPDATE catalog SET steamdt_item_id=?,metadata_request=? WHERE market_hash_name=?", (str(item["itemId"]), item_request, entry["name"]))
        store.db.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?,?)", (entry["name"], item_request, compact(item)))
    if not row["exclusion_reasons"]:
        data, bar_request = client.call(KLINE, {"type": 1, "typeVal": str(item["itemId"]), "platform": "YOUPIN", "specialStyle": "", "maxTime": END - 1})
        if not isinstance(data, list):
            raise CollectionError("P02 hourly history shape changed")
        recent = [bar_record(raw, "1h") for raw in data]
        recent = sorted(bar for bar in recent if START <= bar[0] < END)
        buckets = {bar[1]: bar for bar in recent}
        row.update({"price_hours": len(buckets), "volume_hours": sum(bar[6] is not None for bar in buckets.values()), "turnover_hours": sum(bar[7] is not None for bar in buckets.values()), "source_bar_rows": len(data), "window_bar_rows": len(recent), "source_time_offsets": sum(bar[0] != bar[1] for bar in recent), "hourly_request": bar_request, "source_nonnull_volume_sum": sum(bar[6] for bar in buckets.values() if bar[6] is not None), "source_nonnull_volume_is_complete": False})
        if row["price_hours"] / 168 < .95:
            row["exclusion_reasons"].append("固定 7 日小时价格覆盖不足 95%")
    return row


def finish(run_dir, manifest, candidates, ranking_rows, skipped, stopped, main, reserves, before, stamp, token, base_profile, base_manifest):
    run_id = manifest["run_id"]
    universe_id = f"uu_research_selection_{stamp}_v1_1_{token}"
    universe_dir = LOCAL_DATA / "universes" / universe_id
    universe_dir.mkdir(parents=True, exist_ok=False)
    parent_runs = [base_profile["parent_run_id"], run_id] if base_profile else [run_id]
    profile = {"universe_id": universe_id, "version": "universe-1.1", "asset_status": "validated", "validated_use": "finite P03 source/field validation list only; not buying or training approval", "selection_plan_version": "selection-plan-1.1", "selected_at_utc": now(), "parent_run_id": run_id, "parent_run_ids": parent_runs, "parent_universe_id": base_profile["universe_id"] if base_profile else None, "history_window_beijing": manifest["history_window_beijing"], "limits": LIMITS, "items": main, "reserves": reserves, "all_candidates": candidates, "skipped_ranking_rows": skipped, "stopped": stopped, "limitations": ["limited, retrospectively chosen pool; not all-market or future profitability proof", "attention ranking, supply and inferred trading stats are source proxies", "UU true trades, buy depth, comparable listings and execution remain unknown", "nonnull source volume sum is partial and semantics remain unverified"], "history_jobs_created": 0}
    dump(universe_dir / "selection.json", profile)
    columns = ["role", "name_zh", "market_hash_name", "steamdt_item_id", "uu_price_cny", "price_band", "source_updated_at_beijing", "observed_at_utc", "heat_position", "price_hours", "volume_hours", "turnover_hours", "source_supply", "source_estimated_trades_today_all_platforms", "metadata_request", "hourly_request", "selection_reasons", "unknown_fields"]
    with (universe_dir / "candidates.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in candidates:
            writer.writerow({**row, "selection_reasons": "；".join(row["selection_reasons"]), "unknown_fields": "；".join(row["unknown_fields"])})
    manifest.update({"completed_at_utc": now(), "candidate_count": len(candidates), "ranking_rows": len(ranking_rows), "main_count": len(main), "reserve_count": len(reserves), "roles": dict(Counter(row["role"] for row in candidates)), "stopped": stopped, "universe_id": universe_id, "legacy_db_sha256_after": sha(DEFAULT_DB), "history_jobs_created": 0})
    manifest.update({"parent_run_ids": parent_runs, "parent_universe_id": profile["parent_universe_id"], "total_http_requests": manifest["http_requests"] + (base_manifest["http_requests"] if base_manifest else 0), "total_ranking_rows": len(ranking_rows) + (base_manifest["ranking_rows"] if base_manifest else 0)})
    manifest["legacy_db_unchanged"] = before == manifest["legacy_db_sha256_after"]
    manifest["run_files"] = [{"path": path.relative_to(run_dir).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size} for path in sorted(run_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
    manifest["selection_files"] = [{"path": path.name, "sha256": sha(path), "bytes": path.stat().st_size} for path in sorted(universe_dir.iterdir()) if path.is_file()]
    dump(run_dir / "reports/manifest.json", manifest)
    dump(universe_dir / "manifest.json", {"version": "universe-manifest-1.0", "universe_id": universe_id, "asset_status": "validated", "validated_use": profile["validated_use"], "parent_run_id": run_id, "source_run_manifest_sha256": sha(run_dir / "reports/manifest.json"), "selection_files": manifest["selection_files"]})
    print(json.dumps({"run_id": run_id, "universe_id": universe_id, "candidates": len(candidates), "main": len(main), "reserve": len(reserves), "http_requests": manifest["http_requests"], "stopped": stopped, "legacy_db_unchanged": manifest["legacy_db_unchanged"]}, ensure_ascii=False), flush=True)
    return 2 if stopped or not main or not manifest["legacy_db_unchanged"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supplement", type=Path, help="Merge one identity-correction supplement with a saved private selection")
    raise SystemExit(run(parser.parse_args().supplement))
