"""SteamDT research collector. Python 3.11+, standard library only.

public: read item information already embedded in public HTML.
api: official authenticated batch quote API, optionally cached base info.
kline: retain official history as raw JSON until its schema is verified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = "0.1.0"
CHINA = timezone(timedelta(hours=8))
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


class CollectionError(RuntimeError):
    pass


class AccessStopped(CollectionError):
    """Authentication, denial, or rate limit. Do not attempt to bypass."""


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlparse(req.full_url)
        new = urllib.parse.urlparse(newurl)
        if new.scheme != "https" or new.netloc != old.netloc:
            raise AccessStopped("Unexpected cross-origin redirect; request stopped")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def dump_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(path)


def write_csv(path: Path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def numeric(value):
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return str(result) if result.is_finite() else None
    except InvalidOperation:
        return None


def positive_price(value):
    number = numeric(value)
    return number if number is not None and Decimal(number) > 0 else None


def count(value):
    number = numeric(value)
    if number is None:
        return None
    decimal = Decimal(number)
    return int(decimal) if decimal >= 0 and decimal == decimal.to_integral_value() else None


def stamp(value):
    """Support both Unix seconds and milliseconds. No guessed date strings."""
    number = numeric(value)
    if number is None or Decimal(number) <= 0:
        return None
    epoch = float(number)
    if epoch >= 1e12:
        epoch /= 1000
    try:
        return datetime.fromtimestamp(epoch, CHINA).isoformat(timespec="seconds")
    except (OverflowError, ValueError, OSError):
        return None


def identity(market_hash_name):
    quality = "normal"
    name = market_hash_name
    if name.startswith("StatTrak™ "):
        quality, name = "stattrak", name.removeprefix("StatTrak™ ")
    elif name.startswith("Souvenir "):
        quality, name = "souvenir", name.removeprefix("Souvenir ")
    match = re.fullmatch(r"(.+?) \| (.+?) \((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)", name)
    if not match:
        raise CollectionError(f"Not a supported weapon skin: {market_hash_name}")
    weapon, skin, exterior = match.groups()
    return {"weapon": weapon, "skin_en": skin, "quality": quality, "exterior": exterior}


def decode_nuxt(page):
    match = re.search(r'<script\b[^>]*\bid=[\"\']__NUXT_DATA__[\"\'][^>]*>(.*?)</script>', page, re.S | re.I)
    if not match:
        raise CollectionError("No public Nuxt payload found; page layout may have changed")
    flat = json.loads(match.group(1))
    if not isinstance(flat, list):
        raise CollectionError("Unexpected Nuxt payload shape")
    memo = {}

    def resolve(index):
        if not isinstance(index, int):
            raise CollectionError("Invalid Nuxt reference")
        if index < 0:
            return None  # devalue undefined / non-finite / empty special values
        if index in memo:
            return memo[index]
        if index >= len(flat):
            raise CollectionError("Nuxt reference out of range")
        node = flat[index]
        if isinstance(node, dict):
            result = {}
            memo[index] = result
            result.update({key: resolve(ref) for key, ref in node.items()})
        elif isinstance(node, list):
            if node and isinstance(node[0], str):
                kind = node[0]
                if kind in {"ShallowReactive", "Reactive", "Ref", "ShallowRef"}:
                    if len(node) != 2:
                        raise CollectionError(f"Unexpected Nuxt {kind} wrapper")
                    result = resolve(node[1])
                elif kind == "EmptyRef":
                    result = None
                elif kind == "Set":
                    result = [resolve(ref) for ref in node[1:]]
                else:
                    raise CollectionError(f"Unsupported Nuxt wrapper: {kind}")
                memo[index] = result
            else:
                result = []
                memo[index] = result
                result.extend(resolve(ref) for ref in node)
        else:
            result = node
            memo[index] = result
        return result

    return resolve(0)


def parse_public(page, expected_name):
    root = decode_nuxt(page)
    responses = root.get("data", {})
    item = None
    related = None
    for response in responses.values():
        if not isinstance(response, dict) or response.get("success") is not True:
            continue
        data = response.get("data")
        if not isinstance(data, dict):
            continue
        if data.get("marketHashName") == expected_name and "sellingPriceList" in data:
            item = data
        if "relatedList" in data and "all" in data:
            related = data
    if item is None:
        raise CollectionError(f"No matching live item payload for {expected_name}")
    if not isinstance(item.get("sellingPriceList"), list):
        raise CollectionError("Unexpected public quote list")
    related_rows = related.get("all", []) if related else []
    if not isinstance(related_rows, list):
        raise CollectionError("Unexpected related variants")
    exact = next((row for row in related_rows if row.get("marketHashName") == expected_name), {})
    return item, related_rows, exact


def request_bytes(url, body=None, key=None):
    headers = {"User-Agent": "SteamDT-CourseResearch/0.1", "Accept-Language": "zh-CN,zh;q=0.9"}
    payload = None
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(url, data=payload, headers=headers)
    try:
        opener = urllib.request.build_opener(SameOriginRedirect())
        with opener.open(request, timeout=30) as response:
            if urllib.parse.urlparse(response.url).hostname not in {"www.steamdt.com", "open.steamdt.com"}:
                raise AccessStopped("Unexpected redirect host")
            return response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        if error.code in {401, 403, 429}:
            raise AccessStopped(f"HTTP {error.code}: stopped; authentication or quota needs attention") from None
        raise CollectionError(f"HTTP {error.code}") from None
    except urllib.error.URLError as error:
        raise CollectionError(f"Network failure: {error.reason}") from None


def save_raw(run_dir, name, content):
    path = run_dir / "raw" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path.relative_to(ROOT).as_posix(), hashlib.sha256(content).hexdigest()


def quote_row(common, market_name, quote, observed, source, api_currency=None):
    public = source == "public_html"
    raw_sell = quote.get("price") if public else quote.get("sellPrice")
    raw_bid = None if public else quote.get("biddingPrice")
    update_raw = quote.get("updateTime")
    updated = stamp(update_raw)
    age = (observed - datetime.fromisoformat(updated)).total_seconds() / 3600 if updated else None
    currency = "CNY" if public else api_currency
    return {
        **common, "market_hash_name": market_name,
        "platform": str(quote.get("platform", "")).upper(),
        "platform_name": quote.get("platformName"), "platform_item_id": quote.get("platformItemId"),
        "currency": currency, "raw_sell_price": numeric(raw_sell),
        "sell_price_cny": positive_price(raw_sell) if currency == "CNY" else None,
        "has_positive_sell_quote": int(positive_price(raw_sell) is not None),
        "sell_count": None if public else count(quote.get("sellCount")),
        "raw_bid_price": numeric(raw_bid), "bid_price_cny": positive_price(raw_bid) if currency == "CNY" else None,
        "bid_count": None if public else count(quote.get("biddingCount")),
        "source_update_time_raw": update_raw, "source_updated_at": updated,
        "quote_age_hours": round(age, 4) if age is not None else None,
        "is_stale_24h": int(age > 24) if age is not None else None,
        "market_url": quote.get("link"),
    }


def load_names(path, limit):
    names = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(names, list) or not names or any(not isinstance(x, str) for x in names):
        raise CollectionError("Seed file must be a nonempty JSON array of exact marketHashName strings")
    if len(set(names)) != len(names):
        raise CollectionError("Duplicate seeds; fix seed list first")
    for name in names:
        identity(name)
    if limit < 1:
        raise CollectionError("Limit must be positive")
    return names[:limit]


def start_run(kind):
    now = datetime.now(CHINA)
    run_id = now.strftime("%Y%m%dT%H%M%S_%f") + "_" + kind
    run_dir = ROOT / "data" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def commit_sqlite(run_id, manifest, items, quotes, variants):
    with sqlite3.connect(ROOT / "data" / "steamdt.sqlite") as db:
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
    write_csv(run_dir / "items.csv", items, ITEM_FIELDS)
    write_csv(run_dir / "quotes.csv", quotes, QUOTE_FIELDS)
    write_csv(run_dir / "related_variants.csv", variants, VARIANT_FIELDS)
    dump_json(run_dir / "manifest.json", manifest)
    commit_sqlite(run_id, manifest, items, quotes, variants)
    dump_json(ROOT / "data" / "latest_run.json", {"run_id": run_id, "path": run_dir.relative_to(ROOT).as_posix(), "status": manifest["status"]})
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
本次没有历史日线。`manifest.json` 保留错误和完整范围。
"""
    (run_dir / "quality_report.md").write_text(quality, encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": manifest["status"], "items": len(items), "quotes": len(quotes), "variants": len(variants), "positive_quotes": len(quotes)-non_positive, "path": str(run_dir)}, ensure_ascii=False), flush=True)
    return 0 if manifest["status"] == "complete" else 2


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


def read_key():
    key = os.environ.get("STEAMDT_API_KEY", "").strip()
    if not key and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("STEAMDT_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('\"\'')
    if not key:
        raise CollectionError("API key missing. Copy .env.example to .env and fill STEAMDT_API_KEY locally.")
    return key


class OfficialClient:
    def __init__(self, key):
        self.key = key
        # Cache/quota state is tied to key hash, never to the plaintext secret.
        self.cache = ROOT / "data" / "api_cache" / hashlib.sha256(key.encode()).hexdigest()[:16]
        self.cache.mkdir(parents=True, exist_ok=True)
        self.state_path = self.cache / "quota_state.json"
        self.state = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}

    def call(self, path, body=None):
        interval = {"/open/cs2/v1/base": 86401, "/open/cs2/v1/price/batch": 61, "/open/cs2/item/v1/kline": 0.6}[path]
        wait = interval - (time.time() - self.state.get(path, 0))
        if wait > 0:
            if path.endswith("/base"):
                raise CollectionError("Base endpoint already called in last 24h; use cached base info")
            print(f"Respecting official quota: waiting {wait:.1f}s", flush=True)
            time.sleep(wait)
        self.state[path] = time.time()
        dump_json(self.state_path, self.state)
        url = "https://open.steamdt.com" + path
        raw, _ = request_bytes(url, body, self.key)
        try:
            response = json.loads(raw)
        except (ValueError, UnicodeError):
            raise CollectionError("Official API returned non-JSON data") from None
        if not isinstance(response, dict) or response.get("success") is not True:
            code = response.get("errorCode") if isinstance(response, dict) else None
            # Do not print arbitrary response strings which might echo credentials.
            raise AccessStopped(f"Official API success=false; errorCode={code}. Check key/permission/quota.")
        return raw, response.get("data")

    def base(self):
        cached = self.cache / "base.json"
        if cached.exists() and time.time() - cached.stat().st_mtime < 86400:
            return cached.read_bytes(), True
        raw, data = self.call("/open/cs2/v1/base")
        if not isinstance(data, list):
            raise CollectionError("Unexpected official base response")
        cached.write_bytes(raw)
        return raw, False


def collect_api(args):
    names = load_names(args.seeds, args.limit)
    if len(names) > 100:
        raise CollectionError("Pilot limited to 100 names per batch; split seed files")
    client = OfficialClient(read_key())
    run_id, run_dir = start_run("api")
    quotes, errors = [], []
    extra = {"live_api_validation": True, "currency": args.currency or "unverified"}
    try:
        if args.with_base:
            raw, from_cache = client.base()
            save_raw(run_dir, "base.json", raw)
            extra["base_from_cache"] = from_cache
        raw, data = client.call("/open/cs2/v1/price/batch", {"marketHashNames": names})
        observed = datetime.now(CHINA)
        path, digest = save_raw(run_dir, "batch_prices.json", raw)
        if not isinstance(data, list):
            raise CollectionError("Unexpected official batch response")
        seen = set()
        for item in data:
            name = item.get("marketHashName")
            if name not in names or name in seen:
                raise CollectionError("Unexpected or duplicate marketHashName in official response")
            seen.add(name)
            if not isinstance(item.get("dataList"), list):
                raise CollectionError("Unexpected official platform list")
            common = {"run_id": run_id, "collected_at": observed.isoformat(timespec="seconds"), "source": "official_api", "source_url": "https://open.steamdt.com/open/cs2/v1/price/batch", "raw_path": path, "raw_sha256": digest}
            quotes.extend(quote_row(common, name, quote, observed, "official_api", args.currency) for quote in item["dataList"])
        for name in names:
            if not any(row["market_hash_name"] == name for row in quotes):
                errors.append({"market_hash_name": name, "error": "No platform quote records returned"})
    except CollectionError as error:
        errors.append({"error": str(error)})
        extra["live_api_validation"] = False
    return finish_run(run_id, run_dir, "api", names, [], quotes, [], errors, extra)


def collect_kline(args):
    identity(args.name)
    client = OfficialClient(read_key())
    run_id, run_dir = start_run("kline_raw")
    raw, data = client.call("/open/cs2/item/v1/kline", {"marketHashName": args.name, "type": args.type, "platform": args.platform, "specialStyle": args.special_style})
    path, digest = save_raw(run_dir, "kline.json", raw)
    manifest = {"run_id": run_id, "status": "raw_only_unverified_schema", "market_hash_name": args.name, "type": args.type, "platform": args.platform, "special_style": args.special_style, "collected_at": datetime.now(CHINA).isoformat(timespec="seconds"), "raw_path": path, "raw_sha256": digest, "data_length": len(data) if isinstance(data, list) else None, "note": "No assumptions made about array order, period, currency or volume. Inspect live response and verify definitions before creating an OHLCV table."}
    dump_json(run_dir / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"CS_YouOweMe {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)
    for mode in ("public", "api"):
        cmd = sub.add_parser(mode)
        cmd.add_argument("--seeds", type=Path, default=ROOT / "config" / "seeds.json")
        cmd.add_argument("--limit", type=int, default=20)
        if mode == "public":
            cmd.add_argument("--delay", type=float, default=2.5)
        else:
            cmd.add_argument("--with-base", action="store_true")
            cmd.add_argument("--currency", choices=["CNY"], help="Only set after independently confirming API prices are CNY")
    kline = sub.add_parser("kline")
    kline.add_argument("--name", required=True)
    kline.add_argument("--type", type=int, required=True, help="Use a platform-confirmed period value; no guessed default")
    kline.add_argument("--platform", required=True)
    kline.add_argument("--special-style", default="")
    args = parser.parse_args()
    try:
        return {"public": collect_public, "api": collect_api, "kline": collect_kline}[args.command](args)
    except (CollectionError, OSError, ValueError) as error:
        print(f"Collection stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
