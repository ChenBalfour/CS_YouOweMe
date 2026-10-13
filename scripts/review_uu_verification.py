"""Review frozen P03 responses offline; export only research fields and counts."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from cs_youoweme.collectors.website import ITEM, TRADES, MARKET_COMPARISON
from cs_youoweme.history.normalize import trade_record
from cs_youoweme.history.verification import source_trade, uu_snapshot
from cs_youoweme.history.store import DEFAULT_DB, now
from cs_youoweme.paths import ROOT, LOCAL_DATA
from pilot_uu_day import dump, sha


def response_rows(directory):
    requests = json.loads((directory / "reports/requests.json").read_text(encoding="utf-8"))
    rows = []
    for request in requests:
        if not request.get("raw_path"):
            continue
        raw = gzip.decompress((directory / request["raw_path"]).read_bytes())
        if hashlib.sha256(raw).hexdigest() != request["raw_sha256"]:
            raise ValueError("Raw hash mismatch")
        rows.append((request, json.loads(raw, parse_float=Decimal)["data"]))
    return requests, rows


def review(field_run, pilot_runs, evidence_run):
    directory = LOCAL_DATA / "staging/steamdt" / field_run
    if not directory.resolve().is_relative_to((LOCAL_DATA / "staging/steamdt").resolve()):
        raise ValueError("Review path outside staging")
    target = directory / "reports/verification_review_v1.json"
    if target.exists():
        raise ValueError("Review already exists; use a new version")
    manifest = json.loads((directory / "reports/manifest.json").read_text(encoding="utf-8"))
    source_dir = ROOT / "scripts/local/pilot_sources" / field_run
    review_snapshot = source_dir / ("review_" + sha(Path(__file__)) + ".py")
    if not review_snapshot.exists():
        review_snapshot.write_bytes(Path(__file__).read_bytes())
    for filename, current in [("website_v1.py", ROOT / "scripts/src/cs_youoweme/collectors/website.py"),
                              ("verification_v1.py", ROOT / "scripts/src/cs_youoweme/history/verification.py")]:
        if filename == "website_v1.py" and sha(current) != manifest["module_hashes"][current.relative_to(ROOT).as_posix()]:
            raise ValueError("Collection client changed before exact snapshot")
        snapshot = source_dir / filename
        if snapshot.exists() and sha(snapshot) != sha(current):
            raise ValueError("Existing dependency snapshot must not be replaced")
        if not snapshot.exists():
            snapshot.write_bytes(current.read_bytes())
    if sha(source_dir / "collect_v1.py") != manifest["script_sha256"]:
        raise ValueError("Field collector snapshot hash mismatch")
    requests, raw_fields = response_rows(directory)
    snapshots = []
    for entry in manifest["items"]:
        request, data = next((q, d) for q, d in raw_fields if q["request_id"] == entry["comparison_request"] and q["endpoint"] == MARKET_COMPARISON)
        _, item = next((q, d) for q, d in raw_fields if q["request_id"] == entry["metadata_request"] and q["endpoint"] == ITEM)
        if item["marketHashName"] != entry["name"] or str(item["itemId"]) != entry["item_id"]:
            raise ValueError("Field-probe item identity mismatch")
        rows = [row for row in data["platformMarket"] if str(row.get("platform", "")).upper() == "YOUPIN"]
        if len(rows) != 1:
            raise ValueError("UU comparison identity ambiguous")
        snap = uu_snapshot(rows[0], request["collected_at"], request["request_id"])
        snap.update(market_hash_name=entry["name"], source_run_id=field_run)
        snapshots.append(snap)
    trials, observations = [], []
    raw_checked = len(raw_fields)
    for ident in pilot_runs:
        trial_dir = LOCAL_DATA / "staging/steamdt" / ident
        if not trial_dir.resolve().is_relative_to((LOCAL_DATA / "staging/steamdt").resolve()):
            raise ValueError("Pilot path outside staging")
        original = json.loads((trial_dir / "reports/manifest.json").read_text(encoding="utf-8"))
        quality = json.loads((trial_dir / "reports/quality_review_v1.json").read_text(encoding="utf-8"))
        if sha(trial_dir / "reports/manifest.json") != quality["original_manifest_sha256"]:
            raise ValueError("Pilot original manifest changed")
        original_source = ROOT / original["pilot_source_snapshot"]
        if sha(original_source) != original["pilot_script_sha256"]:
            raise ValueError("Pilot collector snapshot mismatch")
        _, raw = response_rows(trial_dir)
        raw_checked += len(raw)
        pages = [(q, d) for q, d in raw if q["endpoint"] == TRADES]
        all_rows = [(q["request_id"], row) for q, d in pages for row in d["list"]]
        latest = {}
        codes_by_id = {}
        for request_id, row in all_rows:
            source_id = str(row["id"])
            codes_by_id.setdefault(source_id, set()).add(str(row["platform"]))
            latest[source_id] = (request_id, row)
        if any(len(codes) > 1 for codes in codes_by_id.values()):
            raise ValueError("Cross-platform source ID collision; stored deduplication needs review")
        db_uri = (trial_dir / "pilot.sqlite").resolve().as_uri() + "?mode=ro&immutable=1"
        with closing(sqlite3.connect(db_uri, uri=True)) as connection:
            stored = {row[0]: row[1:] for row in connection.execute("SELECT source_trade_id,platform_code,trade_time,price_cny,trade_num,paint_index,paint_seed,wear_decimal,wear_value,min_sell_price_cny,special_style_json,stickers_json FROM trades")}
            for source_id, (_, row) in latest.items():
                expected = trade_record(row)[1:]
                actual = stored.get(source_id)
                # The old collector parsed JSON floats, so insignificant trailing
                # zeros can differ. Verify numerical equality; exact lexemes stay
                # in the hashed raw response and the new Decimal-based export.
                numeric_text_columns = {2, 6, 8}
                matches = actual is not None and all(
                    Decimal(left) == Decimal(right) if index in numeric_text_columns and left is not None and right is not None else left == right
                    for index, (left, right) in enumerate(zip(actual, expected)))
                if not matches:
                    raise ValueError("Stored trade differs from frozen source")
            if len(stored) != len(latest):
                raise ValueError("Stored trade count differs from raw deduplication")
        normalized = [source_trade(row, request_id) for request_id, row in latest.values()]
        for row in normalized:
            row.update(source_run_id=ident, market_hash_name=original["market_hash_name"])
        observations.extend(normalized)
        complete = lambda key: sum(row[key] is not None for row in normalized)
        attr = {key: complete(key) for key in ["wear_decimal", "paint_seed", "paint_index"]}
        minmax = [Decimal(row["wear_decimal"]) for row in normalized if row["wear_decimal"] is not None]
        trial = {"run_id": ident, "name": original["market_hash_name"], "start_inclusive": original["start_inclusive"],
                 "end_exclusive": original["end_exclusive"], "request_count": original["http_requests"],
                 "hours": quality["observed_hour_buckets"], "volume_null": quality["null_volume_rows"],
                 "turnover_null": quality["null_turnover_rows"], "unaligned_timestamps": quality["unaligned_source_timestamps"],
                 "raw_trade_rows": len(all_rows), "unique_source_trades": len(normalized),
                 "duplicate_rows": len(all_rows) - len(normalized), "source_trade_pages": len(pages),
                 "last_next_id": pages[-1][1]["nextId"], "source_totals": [d["total"] for _, d in pages],
                 "platform_codes": dict(Counter(row["platform_code"] for row in normalized)),
                 "source_venues": dict(Counter(row["venue"] for row in normalized)),
                 "nonnull_attributes": attr, "wear_min": str(min(minmax)) if minmax else None,
                 "wear_max": str(max(minmax)) if minmax else None,
                 "stickers_states": dict(Counter(row["stickers_state"] for row in normalized)),
                 "nonnull_source_min_sell_price": complete("source_min_sell_price_cny"),
                 "csv_matches_raw": quality["csv_matches_raw"], "db_trades_match_raw": True,
                 "legacy_db_unchanged": sha(DEFAULT_DB) == original["legacy_db_sha256_before"],
                 "execution_eligible_trades": 0}
        if quality["trade_source_rows_raw"] != len(all_rows) or quality["duplicate_source_records"] != trial["duplicate_rows"]:
            raise ValueError("Multipage pilot quality report mismatch")
        trials.append(trial)
    evidence_dir = LOCAL_DATA / "recon" / evidence_run
    evidence = json.loads((evidence_dir / "evidence.json").read_text(encoding="utf-8"))
    webpage_checked = 0
    for row in evidence["requests"]:
        source = ROOT / "scripts/local/pilot_sources" / evidence_run / (row["script_sha256"] + ".py")
        if sha(source) != row["script_sha256"]:
            raise ValueError("Evidence capture source hash mismatch")
        if row.get("raw_path"):
            raw = gzip.decompress((evidence_dir / row["raw_path"]).read_bytes())
            if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"] or row.get("truncated"):
                raise ValueError("Public evidence integrity or completeness failed")
            webpage_checked += 1
    all_dirs = [directory, evidence_dir] + [LOCAL_DATA / "staging/steamdt" / ident for ident in pilot_runs]
    result = {"review_version": "verification-review-1.0", "reviewed_at_utc": now(),
              "review_script_sha256": sha(Path(__file__)), "review_source_snapshot": review_snapshot.relative_to(ROOT).as_posix(), "trials": trials, "uu_snapshots": snapshots,
              "raw_json_responses_hash_verified": raw_checked, "raw_page_assets_hash_verified": webpage_checked,
              "recorded_http_requests": sum(row["request_count"] for row in trials) + len(requests) + len(evidence["requests"]),
              "blocked_origins": evidence["blocked_hosts"], "private_directory_bytes": sum(p.stat().st_size for d in all_dirs for p in d.rglob("*") if p.is_file()),
              "source_field_probe_manifest_unchanged": sha(directory / "reports/manifest.json"),
              "legacy_db_unchanged": sha(DEFAULT_DB) == manifest["legacy_db_before"] == manifest["legacy_db_after"],
              "result": "L0-only; L1/L2 execution admission not passed"}
    tables = directory / "tables"
    dump(tables / "uu_source_snapshots_v1.json", snapshots)
    dump(tables / "source_trade_observations_v1.json", observations)
    result["output_hashes"] = {p.name: sha(p) for p in tables.iterdir() if p.is_file()}
    dump(target, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field-run", required=True)
    parser.add_argument("--pilot-runs", nargs=2, required=True)
    parser.add_argument("--evidence-run", required=True)
    args = parser.parse_args()
    review(args.field_run, args.pilot_runs, args.evidence_run)
