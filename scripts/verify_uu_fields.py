"""Finite SteamDT market-comparison field probe for the two P03 specimens."""
from datetime import datetime
from pathlib import Path
import json
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from cs_youoweme import __version__
from cs_youoweme.collectors.website import WebsiteClient, ITEM, MARKET_COMPARISON
from cs_youoweme.errors import CollectionError
from cs_youoweme.history.store import Store, DEFAULT_DB, now
from cs_youoweme.paths import ROOT, LOCAL_DATA, CHINA
from pilot_uu_day import dump, sha

NAMES = ["AK-47 | The Oligarch (Field-Tested)", "M4A1-S | Printstream (Factory New)"]


class LimitedClient(WebsiteClient):
    def __init__(self, store):
        super().__init__(store.archive, 2.5)
        self.store = store

    def _request(self, *args, **kwargs):
        if self.requests >= 10 or self.store.disk_bytes() >= 16 * 1024 * 1024:
            raise CollectionError("Field probe budget reached")
        result = super()._request(*args, **kwargs)
        if self.store.disk_bytes() > 16 * 1024 * 1024:
            raise CollectionError("Field probe storage budget reached; response retained")
        return result


def run():
    ident = "p03_steamdt_fields_" + datetime.now(CHINA).strftime("%Y%m%dT%H%M%S+0800_") + uuid.uuid4().hex[:6]
    directory = LOCAL_DATA / "staging/steamdt" / ident
    directory.mkdir(parents=True, exist_ok=False)
    reports = directory / "reports"
    reports.mkdir()
    source_dir = ROOT / "scripts/local/pilot_sources" / ident
    source_dir.mkdir(parents=True, exist_ok=False)
    source_dir.joinpath("collect_v1.py").write_bytes(Path(__file__).read_bytes())
    source_dir.joinpath("verification_plan_v1.md").write_bytes(ROOT.joinpath("docs/research/P03_VERIFICATION_PLAN.md").read_bytes())
    manifest = {"version": "field-probe-1.0", "run_id": ident, "asset_status": "candidate-L0",
                "started_at_utc": now(), "code_version": __version__, "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "script_sha256": sha(Path(__file__)), "source_snapshot": source_dir.relative_to(ROOT).as_posix(),
                "module_hashes": {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / "scripts/src/cs_youoweme").rglob("*.py")},
                "legacy_db_before": sha(DEFAULT_DB), "budget": {"requests": 10, "storage_mib": 16}, "items": []}
    dump(reports / "manifest.json", manifest)
    with Store(directory / "verification.sqlite") as store:
        client = LimitedClient(store)
        try:
            for name in NAMES:
                item, item_request = client.call(ITEM, {"appId": 730, "marketHashName": name}, post=True)
                if not isinstance(item, dict) or item.get("marketHashName") != name or not item.get("itemId"):
                    raise CollectionError("Exact field-probe identity mismatch")
                comparison, request_id = client.call(MARKET_COMPARISON, {"itemId": str(item["itemId"]), "platform": "YOUPIN", "typeDay": "1", "dateType": 4})
                if not isinstance(comparison, dict) or not isinstance(comparison.get("platformMarket"), list):
                    raise CollectionError("Unexpected market comparison schema")
                uu = [row for row in comparison["platformMarket"] if str(row.get("platform", "")).upper() in {"YOUPIN", "UU"} or row.get("platformName") == "悠悠"]
                result = {"name": name, "item_id": str(item["itemId"]), "metadata_request": item_request,
                          "comparison_request": request_id, "comparison_keys": list(comparison), "uu_raw_summary": uu}
                manifest["items"].append(result)
                dump(reports / "manifest.json", manifest)
                print(json.dumps(result, ensure_ascii=False), flush=True)
        except CollectionError as error:
            manifest["failure"] = str(error)
        manifest["request_count"] = client.requests
        dump(reports / "requests.json", [dict(row) for row in store.db.execute("SELECT * FROM requests ORDER BY request_id")])
    manifest.update(completed_at_utc=now(), legacy_db_after=sha(DEFAULT_DB))
    manifest["legacy_unchanged"] = manifest["legacy_db_before"] == manifest["legacy_db_after"]
    dump(reports / "manifest.json", manifest)
    print(json.dumps({"run_id": ident, "requests": manifest["request_count"], "failure": manifest.get("failure"), "legacy_unchanged": manifest["legacy_unchanged"]}), flush=True)


if __name__ == "__main__":
    run()
