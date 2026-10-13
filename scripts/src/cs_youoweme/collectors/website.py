"""Anonymous, paced calls to the data endpoints used by the SteamDT website.

The public freshness timestamp is reproduced from the website client. It is
not authentication. This client never reads an API key, token or browser cookie.
"""
from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from ..errors import AccessStopped, CollectionError
from ..transport import SameOriginRedirect

BASE = "https://www.steamdt.com/api"
SYSTEM = "/user/system-config/v1/default-config"
ITEM = "/user/skin/v1/item"
VARIANTS = "/user/skin/v2/sale-wear-detail"
KLINE = "/user/steam/category/v1/kline"
TRADES = "/item/trade/v1/list"
OVERVIEW = "/item/trade/v1/overview/today"
MARKET = "/skin/market/v3/page"
ATTRIBUTES = "/user/ranking/v1/attribute/730"
MARKET_COMPARISON = "/user/skin/v1/market-comparsion"
ALLOWED = {SYSTEM, ITEM, VARIANTS, KLINE, TRADES, OVERVIEW, MARKET, ATTRIBUTES, MARKET_COMPARISON}


def freshness_timestamp(milliseconds):
    prefix = str(int(milliseconds))[:12]
    return prefix + str(sum(int(d) for d in prefix) % 10)


class WebsiteClient:
    def __init__(self, archive, delay=2.5, opener=None, max_response_bytes=None, before_request=None):
        if delay < 2:
            raise CollectionError("Website request interval must be at least 2 seconds")
        self.archive = archive
        self.delay = delay
        self.opener = opener or urllib.request.build_opener(SameOriginRedirect())
        self.offset = 0
        self.last_request = 0
        self.synced_at = None
        self.requests = 0
        if max_response_bytes is not None and (type(max_response_bytes) is not int or max_response_bytes < 1024):
            raise CollectionError("Invalid response size bound")
        self.max_response_bytes = max_response_bytes
        self.before_request = before_request

    def _request(self, path, params, post):
        wait = self.delay - (time.monotonic() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        params = dict(params)
        params["timestamp"] = freshness_timestamp(time.time() * 1000 + self.offset)
        query = {"timestamp": params["timestamp"]} if post else params
        url = BASE + path + "?" + urllib.parse.urlencode(query)
        headers = {
            "User-Agent": "CS-YouOweMe-Research/0.3",
            "Accept": "application/json", "language": "zh_CN",
            "x-device": "1", "x-app-version": "1.0.0", "x-currency": "CNY",
        }
        body = None
        if post:
            body = json.dumps(params, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers)
        if self.before_request is not None:
            self.before_request(path, params)
        self.last_request = time.monotonic()
        self.requests += 1
        observed = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        try:
            with self.opener.open(req, timeout=30) as response:
                if urllib.parse.urlparse(response.url).netloc != "www.steamdt.com":
                    raise AccessStopped("Unexpected website redirect")
                raw = response.read(self.max_response_bytes + 1) if self.max_response_bytes else response.read()
                if self.max_response_bytes and len(raw) > self.max_response_bytes:
                    # A partial body must not be archived as a complete response.
                    self.archive(path, params, observed, b"", response.status, None)
                    raise AccessStopped("Website response size limit exceeded; no parsed record saved")
        except urllib.error.HTTPError as error:
            self.archive(path, params, observed, b"", error.code, None)
            if error.code in {401, 403, 429}:
                raise AccessStopped(f"Website HTTP {error.code}; worker stopped") from None
            raise CollectionError(f"Website HTTP {error.code}; checkpoint retained") from None
        except (urllib.error.URLError, TimeoutError):
            self.archive(path, params, observed, b"", None, None)
            raise CollectionError("Website network failure; checkpoint retained") from None
        try:
            obj = json.loads(raw)
        except (ValueError, UnicodeError):
            self.archive(path, params, observed, raw, 200, None)
            raise AccessStopped("Website returned non-JSON; worker stopped") from None
        code = obj.get("errorCode") if isinstance(obj, dict) else None
        request_id = self.archive(path, params, observed, raw, 200, code)
        if not isinstance(obj, dict) or obj.get("success") is not True:
            # Error text is not logged: it may contain reflected input or private data.
            safe_code = code if type(code) is int else "unknown"
            raise AccessStopped(f"Website success=false, code={safe_code}; worker stopped")
        return obj.get("data"), request_id

    def call(self, path, params=None, post=False):
        if path not in ALLOWED:
            raise CollectionError("Unsupported website endpoint")
        if path != SYSTEM and (self.synced_at is None or time.monotonic() - self.synced_at > 240):
            before = time.time() * 1000
            config, _ = self._request(SYSTEM, {}, False)
            after = time.time() * 1000
            try:
                server_time = float(config["systemTime"])
            except (TypeError, ValueError, KeyError):
                raise CollectionError("Missing website server clock")
            if not math.isfinite(server_time) or abs(server_time - after) > 86400000:
                raise CollectionError("Invalid website server clock")
            self.offset = server_time - (before + after) / 2
            self.synced_at = time.monotonic()
        return self._request(path, params or {}, post)
