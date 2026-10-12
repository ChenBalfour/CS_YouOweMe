"""Select a bounded research universe from live heat ranks and source activity."""
from __future__ import annotations

import json
import hashlib
import math
import time
from collections import defaultdict
from pathlib import Path

from ..collectors.website import ATTRIBUTES, ITEM, KLINE, MARKET, WebsiteClient
from ..errors import CollectionError
from ..paths import LOCAL_DATA
from .catalog import dimensions, upsert_item
from .normalize import bar_record, integer
from .store import compact, now


def sector_types(attributes):
    group = next((r for r in attributes if r.get("key") == "Type"), {})
    items = group.get("list", [])
    aliases = {"weapon": {"Rifle", "Pistol", "SMG", "Shotgun", "Machinegun"},
               "knife": {"Knife"}, "glove": {"Gloves"}}
    result = {sector: [r["key"] for r in items if r.get("alias") in names] for sector, names in aliases.items()}
    if any(not keys for keys in result.values()):
        raise CollectionError("Website sector dictionary changed")
    return result


def fresh_price(item, asof):
    prices = []
    for quote in item.get("sellingPriceList", []):
        if quote.get("platform", "").lower() not in {"buff", "youpin", "c5", "haloskins"}:
            continue
        price = quote.get("price")
        updated = quote.get("updateTime", quote.get("lastUpdate"))
        try:
            if price is not None and math.isfinite(float(price)) and float(price) > 0 and updated is not None and 0 <= asof - int(updated) <= 3600:
                prices.append(float(price))
        except (ValueError, TypeError):
            continue
    return min(prices) if prices else None


def percentile(value, peers, higher=True):
    # Mid-ranks handle ties; normalization is within each observed candidate sector.
    below = sum(v < value for v in peers)
    tied = sum(v == value for v in peers)
    score = (below + tied / 2) / len(peers)
    return score if higher else 1 - score


def rank_candidates(candidates, per_sector=12, family_limit=2, price_band_cap=8):
    groups = defaultdict(list)
    rejected = []
    for row in candidates:
        reasons = []
        if not row.get("survive_count"):
            reasons.append("missing_or_zero_source_supply")
        if not row.get("recent_known_volume"):
            reasons.append("no_known_recent_source_activity")
        if row.get("observed_recent_hours", 0) < 168 * .8:
            reasons.append("insufficient_recent_price_coverage")
        if row.get("price_cny") is None:
            reasons.append("missing_fresh_quote")
        elif row["category"] == "weapon" and not 100 <= row["price_cny"] < 10000:
            reasons.append("outside_weapon_price_range")
        if reasons:
            rejected.append({**row, "exclusion_reasons": reasons})
        else:
            groups[row["category"]].append(dict(row))
    selected, reserves = [], []
    for sector, rows in sorted(groups.items()):
        activity = [r["recent_known_volume"] for r in rows]
        supply = [r["survive_count"] for r in rows]
        ranks = [r["source_heat_rank"] for r in rows]
        for row in rows:
            heat = percentile(row["source_heat_rank"], ranks, higher=False)
            rarity = percentile(row["survive_count"], supply, higher=False)
            liquidity = percentile(row["recent_known_volume"], activity)
            row.update({"heat_percentile": round(heat, 6), "scarcity_percentile": round(rarity, 6),
                        "activity_percentile": round(liquidity, 6),
                        "selection_score": round(.40*heat + .35*rarity + .25*liquidity, 6)})
        rows.sort(key=lambda r: (-r["selection_score"], r["source_heat_rank"], r["market_hash_name"]))
        families = defaultdict(int)
        bands = defaultdict(int)
        accepted = 0
        for row in rows:
            band = "hundreds" if row["price_cny"] < 1000 else "thousands"
            row["price_band"] = band
            if accepted < per_sector and families[row["family"]] < family_limit and bands[band] < price_band_cap:
                selected.append(row)
                families[row["family"]] += 1
                accepted += 1
                bands[band] += 1
            else:
                row["reserve_reason"] = "selection/family/price-band capacity"
                reserves.append(row)
    return selected, reserves, rejected


def save_profile(store, profile, output):
    output = Path(output).resolve()
    if not output.is_relative_to(LOCAL_DATA.resolve()):
        raise CollectionError("Universe snapshots must remain in data/local/")
    digest = hashlib.sha256(compact(profile).encode("utf-8")).hexdigest()
    with store.db:
        store.db.execute("INSERT OR IGNORE INTO universes VALUES(?,?,?,?,?)",
                         (digest, profile["selected_at"], now(), profile.get("scope", "weapon"), compact(profile)))
        for key, role in (("items", "selected"), ("reserves", "reserve"), ("rejected", "rejected")):
            for position, row in enumerate(profile[key], 1):
                price = str(row["price_cny"]) if row.get("price_cny") is not None else None
                store.db.execute("INSERT OR IGNORE INTO universe_members VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (digest, row["market_hash_name"], role, position, row.get("selection_score"), price,
                     row.get("survive_count"), row.get("recent_known_volume"), row.get("source_heat_rank"), compact(row)))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    return {"universe_id": digest, "universe_path": str(output), "selected_items": len(profile["items"]),
            "enriched_candidates": sum(len(profile[k]) for k in ("items", "reserves", "rejected")),
            "history_jobs_created": 0}


def narrow(store, source, output, max_items=12):
    if not 1 <= max_items <= 100:
        raise CollectionError("Selection capacity must be between 1 and 100")
    source = Path(source).resolve()
    if not source.is_relative_to(LOCAL_DATA.resolve()):
        raise CollectionError("Use a private saved universe under data/local/")
    profile = json.loads(source.read_text(encoding="utf-8"))
    candidates = [r for k in ("items", "reserves", "rejected") for r in profile[k] if r["category"] == "weapon"]
    # Rebuild a historical observation; old quotes are not fresh at rebuild time.
    for row in candidates:
        for key in ("reserve_reason", "exclusion_reasons"):
            row.pop(key, None)
    selected, reserves, rejected = rank_candidates(candidates, max_items)
    profile.update({"scope": "weapon", "rebuilt_at": now(), "items": selected, "reserves": reserves, "rejected": rejected})
    profile["criteria"].update({"sectors": ["weapon"], "selection_cap_per_sector": max_items,
                               "price_band_cap": 8, "max_wears_per_family": 2})
    profile["excluded_ranking_rows"] = [r for r in profile.get("excluded_ranking_rows", []) if r.get("sector") == "weapon"]
    with store.worker_lock():
        return save_profile(store, profile, output)


def discover(store, candidate_pages=2, enrich_per_sector=20, per_sector=12, delay=2.5, output=None, client=None, emit=print):
    if not 1 <= candidate_pages <= 10 or not 1 <= enrich_per_sector <= 100 or not 1 <= per_sector <= enrich_per_sector:
        raise CollectionError("Bounded selection requires 1–10 pages, 1–100 enrichments and a smaller selection size")
    if output is None:
        output = LOCAL_DATA / "universes" / ("core_" + now().replace(":", "").replace("+", "_") + ".json")
    output = Path(output).resolve()
    if not output.is_relative_to(LOCAL_DATA.resolve()):
        raise CollectionError("Live universe snapshots must remain in data/local/")
    client = client or WebsiteClient(store.archive, delay)
    asof = int(time.time())
    candidates = []
    excluded_rank_rows = []
    request_ids = []
    with store.worker_lock():
        attributes, req = client.call(ATTRIBUTES)
        if not isinstance(attributes, list):
            raise CollectionError("Unexpected website attributes")
        request_ids.append(req)
        types = sector_types(attributes)
        for sector in ("weapon",):
            cursor, seen = "", set()
            pool = []
            for page in range(candidate_pages):
                data, req = client.call(MARKET, {"dataField": "pvNums", "dataRange": "", "sortType": "desc",
                    "nextId": cursor, "queryName": "", "pageSize": 20, "typeList": types[sector]}, post=True)
                request_ids.append(req)
                if not isinstance(data, dict) or not isinstance(data.get("list"), list) or "nextId" not in data:
                    raise CollectionError("Unexpected heat-ranking pagination")
                for row in data["list"]:
                    name = row.get("marketHashName")
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    category, weapon, skin, quality, exterior, family = dimensions(name)
                    price = fresh_price(row, int(time.time()))
                    if category != sector or quality != "normal" or price is None or (sector == "weapon" and not 100 <= price < 10000):
                        excluded_rank_rows.append({"market_hash_name": name, "sector": sector,
                            "reason": "category/quality/fresh-price/weapon-price-range filter"})
                        continue
                    pool.append((row, len(seen), req))
                next_cursor = data["nextId"]
                if not next_cursor:
                    break
                if not isinstance(next_cursor, str) or next_cursor == cursor or (page and not data["list"]):
                    raise CollectionError("Heat-ranking cursor made no progress")
                cursor = next_cursor
            for ranked, heat_rank, ranking_request in pool[:enrich_per_sector]:
                name = ranked["marketHashName"]
                item, req = client.call(ITEM, {"appId": 730, "marketHashName": name}, post=True)
                request_ids.append(req)
                if not isinstance(item, dict) or item.get("marketHashName") != name or not item.get("itemId"):
                    raise CollectionError("Candidate item identity mismatch")
                with store.db:
                    if not store.db.execute("SELECT 1 FROM catalog WHERE market_hash_name=?", (name,)).fetchone():
                        upsert_item(store.db, item, req)
                    store.db.execute("UPDATE catalog SET steamdt_item_id=?,metadata_request=? WHERE market_hash_name=?",
                                     (str(item["itemId"]), req, name))
                    store.db.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?,?)", (name, req, compact(item)))
                data, bar_request = client.call(KLINE, {"type": 1, "typeVal": str(item["itemId"]),
                    "platform": "ALL", "specialStyle": "", "maxTime": asof})
                request_ids.append(bar_request)
                if not isinstance(data, list):
                    raise CollectionError("Unexpected candidate hourly schema")
                recent = [bar_record(row, "1h") for row in data if asof - 7*86400 <= int(row[0]) < asof]
                hours = {row[1] for row in recent}
                known_volume = sum(row[6] for row in recent if row[6] is not None)
                row = {"market_hash_name": name, "name_zh": item.get("name"), "category": sector,
                    "family": dimensions(name)[5], "source_heat_rank": heat_rank,
                    "price_cny": fresh_price(item, int(time.time())),
                    "survive_count": integer(item.get("surviveNum"), nullable=True),
                    "holders_count": integer(item.get("holdersNum"), nullable=True),
                    "estimated_trade_count_today": integer(item.get("transactionCount"), nullable=True),
                    "recent_known_volume": known_volume, "observed_recent_hours": len(hours),
                    "missing_volume_hours": sum(r[6] is None for r in recent),
                    "ranking_request": ranking_request, "metadata_request": req, "recent_bars_request": bar_request}
                candidates.append(row)
                emit(json.dumps({"candidate": name, "category": sector, "heat_rank": heat_rank,
                                 "source_supply": row["survive_count"], "known_7d_volume": known_volume}, ensure_ascii=False), flush=True)
        selected, reserves, rejected = rank_candidates(candidates, per_sector)
        profile = {"selected_at": now(), "ranking_started_at_epoch": asof, "scope": "weapon",
                   "purpose": "research sampling; selection score is not an expected return or buy signal",
                   "criteria": {"heat": "source pvNums descending position; source does not return the absolute count",
                       "weights": {"heat": .40, "scarcity": .35, "activity": .25},
                       "weapon_price_cny": [100, 10000], "weapon_upper_bound_exclusive": True,
                       "quality": "normal", "candidate_pages_per_sector": candidate_pages,
                       "enrich_per_sector": enrich_per_sector, "selection_cap_per_sector": per_sector,
                       "sectors": ["weapon"], "price_band_cap": 8,
                       "max_wears_per_family": 2, "activity": "sum of known webpage hourly volume in trailing 7d; nulls retained"},
                   "limitations": ["candidate pool is bounded and may miss other active/scarce items",
                       "source supply is observed inventory, not a census of every Steam account",
                       "current selection creates look-ahead/survivorship bias if treated as a 2025 ex-ante universe",
                       "heat is source traffic rank, not actual trade volume; weights are research heuristics"],
                   "items": selected, "reserves": reserves, "rejected": rejected,
                   "excluded_ranking_rows": excluded_rank_rows, "source_request_ids": request_ids}
        result = save_profile(store, profile, output)
    return {**result, "http_requests": getattr(client, "requests", None)}
