"""HTTP transport with credential-preserving redirect restrictions."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from .errors import AccessStopped, CollectionError


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlparse(req.full_url)
        new = urllib.parse.urlparse(newurl)
        if new.scheme != "https" or new.netloc != old.netloc:
            raise AccessStopped("Unexpected cross-origin redirect; request stopped")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def request_bytes(url, body=None, key=None):
    headers = {"User-Agent": "SteamDT-CourseResearch/0.2", "Accept-Language": "zh-CN,zh;q=0.9"}
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
