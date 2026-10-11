"""Collect item details and cross-platform quotes from public HTML."""
from __future__ import annotations

import json
import time
import urllib.parse
from datetime import datetime
from ..paths import CHINA
from ..errors import AccessStopped, CollectionError
from ..cleaning import count, identity, numeric, positive_price, quote_row, stamp
from ..config import load_names
from ..parsing import parse_public
from ..transport import request_bytes
from ..storage import dump_json, save_raw, start_run, finish_run


def collect_public(args):
    if args.delay < 2:
        raise CollectionError("Public collection delay must be at least 2 seconds")
    names = load_names(args.seeds, args.limit)
    run_id, run_dir = start_run("public")
    items, quotes, variants, errors = [], [], {}, []
    for index, name in enumerate(names):
        if index:
            time.sleep(args.delay)
        url = "https://www.steamdt.com/cs2/" + urllib.parse.quote(name, safe="")
        print(f"[{index + 1}/{len(names)}] {name}", flush=True)
        try:
            content, content_type = request_bytes(url)
            observed = datetime.now(CHINA)
            raw_path, digest = save_raw(run_dir, f"item_{index+1:03d}.html", content)
            if "html" not in content_type.lower():
                raise CollectionError("Expected HTML item page")
            page = content.decode("utf-8-sig")
            item, related, exact = parse_public(page, name)
            common = {"run_id": run_id, "collected_at": observed.isoformat(timespec="seconds"), "source": "public_html", "source_url": url, "raw_path": raw_path, "raw_sha256": digest}
            item_row = {
                **common, "item_id": str(item.get("itemId", "")), "market_hash_name": name,
                "name_zh": item.get("name"), **identity(name), "rarity": item.get("rarityName"),
                "display_sell_price_cny": positive_price(exact.get("sellPrice")), "item_updated_at": stamp(exact.get("updateTime")),
                "survive_count": count(item.get("surviveNum")), "holders_count": count(item.get("holdersNum")),
                "added_count": count(item.get("addNum")), "estimated_trade_count_today": count(item.get("transactionCount")),
                "turnover_rate_raw": numeric(item.get("turnoverRate")), "volume_ratio_raw": numeric(item.get("volumeRatio")),
                "diff_1day_pct_raw": numeric(item.get("diff1Day")), "diff_7day_pct_raw": numeric(item.get("diff7Day")),
                "diff_30day_pct_raw": numeric(item.get("diff30Day")), "diff_6month_pct_raw": numeric(item.get("diff6Month")),
                "analysis_tags_json": json.dumps(item.get("analysisTags", []), ensure_ascii=False),
            }
            quote_rows = [quote_row(common, name, quote, observed, "public_html") for quote in item["sellingPriceList"]]
            if len({row["platform"] for row in quote_rows}) != len(quote_rows) or any(not row["platform"] for row in quote_rows):
                raise CollectionError("Missing or duplicate quote platform")
            local_variants = []
            for row in related:
                variant_name = row.get("marketHashName")
                if not variant_name:
                    continue
                local_variants.append({
                    "run_id": run_id, "collected_at": common["collected_at"], "source_url": url,
                    "raw_path": raw_path, "raw_sha256": digest, "item_id": str(row.get("itemId", "")),
                    "market_hash_name": variant_name, "name_zh": row.get("name"), **identity(variant_name),
                    "raw_sell_price": numeric(row.get("sellPrice")), "sell_price_cny": positive_price(row.get("sellPrice")),
                    "survive_count": count(row.get("surviveNum")), "source_updated_at": stamp(row.get("updateTime")),
                })
            dump_json(run_dir / "raw" / f"item_{index+1:03d}_decoded.json", {"item": item, "related_variants": related})
            items.append(item_row)
            quotes.extend(quote_rows)
            for row in local_variants:
                variants.setdefault(row["market_hash_name"], row)
        except (CollectionError, ValueError, KeyError, UnicodeError) as error:
            errors.append({"market_hash_name": name, "error": str(error), "source_url": url})
            print(f"  Failed: {error}", flush=True)
            if isinstance(error, AccessStopped):
                break
    return finish_run(run_id, run_dir, "public", names, items, quotes, list(variants.values()), errors)
