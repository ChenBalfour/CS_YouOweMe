"""Official API collection, quota state and raw history retention."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from ..paths import LOCAL_DATA, CHINA
from ..errors import AccessStopped, CollectionError
from ..cleaning import identity, quote_row
from ..config import load_names, read_key
from ..transport import request_bytes
from ..storage import dump_json, save_raw, start_run, finish_run


class OfficialClient:
    def __init__(self, key):
        self.key = key
        # Cache/quota state is tied to key hash, never to the plaintext secret.
        self.cache = LOCAL_DATA / "api_cache" / hashlib.sha256(key.encode()).hexdigest()[:16]
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
            code = code if type(code) is int else "unavailable"
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
    dump_json(run_dir / "reports" / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False), flush=True)
    return 0
