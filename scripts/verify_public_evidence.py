"""Bounded, anonymous public-page evidence capture for the P03 verification.

No browser cookies or application credentials are read. Re-running skips URLs
already recorded, and blocked origins stay blocked within this evidence run.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/local/recon"
MAX_REQUESTS = 50
MAX_BODY = 8 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
UU_READ_ENDPOINTS = {
    "detail": "/api/homepage/pc/goods/market/queryTemplateDetail",
    "sale": "/api/homepage/pc/goods/market/queryOnSaleCommodityList",
    "buy": "/api/youpin/bff/trade/purchase/order/getTemplatePurchaseOrderListPC",
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


class SameHost(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(req.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            raise urllib.error.URLError("cross-origin redirect stopped")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def capture(run, urls, body=None):
    if not re.fullmatch(r"p03_[0-9]{8}_[a-z0-9_]+", run):
        raise ValueError("Use a named p03_YYYYMMDD_evidence run")
    directory = BASE / run
    directory.mkdir(exist_ok=True)
    manifest_path = directory / "evidence.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {
        "version": "public-evidence-1.0", "run_id": run, "requests": [], "blocked_hosts": [],
        "limits": {"requests": MAX_REQUESTS, "response_bytes": MAX_BODY, "raw_total_bytes": MAX_TOTAL},
    }
    source = Path(__file__).read_bytes()
    snapshot = ROOT / "scripts/local/pilot_sources" / run
    snapshot.mkdir(parents=True, exist_ok=True)
    source_path = snapshot / (digest(source) + ".py")
    if not source_path.exists():
        source_path.write_bytes(source)
    opener = urllib.request.build_opener(SameHost())
    for url in urls:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname:
            raise ValueError("Only anonymous HTTPS URLs accepted")
        if body is not None and (parsed.netloc != "pc-api.youpin898.com" or parsed.path not in UU_READ_ENDPOINTS.values()):
            raise ValueError("POST is restricted to the three verified read-only UU endpoints")
        if any(row["url"] == url and row.get("body") == body for row in manifest["requests"]):
            print(json.dumps({"url": url, "result": "already-recorded"}), flush=True)
            continue
        if parsed.hostname in manifest["blocked_hosts"]:
            raise ValueError("This origin was access-blocked; no retry")
        used = sum(row.get("bytes", 0) for row in manifest["requests"])
        if len(manifest["requests"]) >= MAX_REQUESTS or used >= MAX_TOTAL:
            raise ValueError("Evidence budget exhausted")
        row = {"id": len(manifest["requests"]) + 1, "url": url,
               "observed_at_utc": datetime.now(timezone.utc).isoformat(),
               "script_sha256": digest(source), "status": None, "body": body}
        # Save the attempt before I/O so an interruption consumes the budget.
        manifest["requests"].append(row)
        save(manifest_path, manifest)
        raw = b""
        try:
            headers = {"User-Agent": "CS-YouOweMe-Research/0.3", "Accept-Encoding": "identity"}
            if body is not None:
                headers.update({"Content-Type": "application/json", "platform": "pc", "appType": "1", "AppVersion": "5.26.0"})
            req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers)
            with opener.open(req, timeout=30) as response:
                row.update(status=response.status, content_type=response.headers.get("Content-Type"), final_url=response.url)
                limit = min(MAX_BODY, MAX_TOTAL - used)
                raw = response.read(limit + 1)
                if len(raw) > limit:
                    raw = raw[:limit]
                    row["truncated"] = True
        except urllib.error.HTTPError as error:
            row["status"] = error.code
            row["retry_after"] = error.headers.get("Retry-After") if error.headers else None
            if error.code in {401, 403, 429}:
                manifest["blocked_hosts"].append(parsed.hostname)
        except (urllib.error.URLError, TimeoutError):
            row["error"] = "network-or-redirect-failure"
        if raw:
            checksum = digest(raw)
            target = directory / (checksum + ".body.gz")
            if not target.exists():
                target.write_bytes(gzip.compress(raw, mtime=0))
            row.update(bytes=len(raw), sha256=checksum, raw_path=target.name)
            if body is not None:
                try:
                    obj = json.loads(raw)
                    row["application_code"] = obj.get("Code", obj.get("code"))
                    if row["application_code"] in {84103, 84101, 2002, 401, 403, 429}:
                        manifest["blocked_hosts"].append(parsed.hostname)
                except (ValueError, AttributeError):
                    row["error"] = "non-json-api-response"
                    manifest["blocked_hosts"].append(parsed.hostname)
        save(manifest_path, manifest)
        print(json.dumps({key: row.get(key) for key in ("id", "url", "status", "bytes", "application_code", "error", "truncated")}, ensure_ascii=False), flush=True)
        time.sleep(2.5)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--uu-endpoint", choices=UU_READ_ENDPOINTS)
    parser.add_argument("--template-id", choices=["113014", "46298"])
    args = parser.parse_args()
    if args.uu_endpoint:
        if args.urls or not args.template_id:
            parser.error("UU read needs one --template-id and no URL arguments")
        body = {"templateId": args.template_id}
        if args.uu_endpoint != "buy":
            body.update(gameId="730", listType="10")
        if args.uu_endpoint != "detail":
            body.update(pageIndex=1, pageSize=10)
        if args.uu_endpoint == "sale":
            body.update(listSortType=1, sortType=0)
        capture(args.run, ["https://pc-api.youpin898.com" + UU_READ_ENDPOINTS[args.uu_endpoint]], body)
    elif args.urls:
        capture(args.run, args.urls)
    else:
        parser.error("Specify URLs or a UU read endpoint")
