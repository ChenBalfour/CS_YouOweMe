"""Read frozen seven-item inputs without changing source data or exposing labels.

This is an adapter for retrospective exploratory experiments. The source's
``training_approved=False`` and unknown historical availability remain intact.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

import numpy as np

VERSION = "seven-training-data-1.0"
ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "data/local/datasets/seven_daily"
CLEAN_BASE = ROOT / "data/local/datasets/steamdt_clean"
DEFAULT_DATASET_ID = "seven_daily_20261020_v1"
HOUR = 3600
FEATURE_FIELDS = (
    "x_reference_close", "x_return_1d", "x_return_3d", "x_return_7d", "x_return_14d",
    "x_ma_ratio_7d", "x_ma_ratio_14d", "x_ma_ratio_28d", "x_vol_7d", "x_vol_14d",
    "x_adjacent_return_coverage_7d", "x_adjacent_return_coverage_14d", "x_range_7d",
    "x_min_hourly_return_7d", "x_max_hourly_return_7d", "x_price_coverage_28d",
    "x_price_coverage_24h", "x_longest_missing_hours_28d", "x_price_age_hours",
    "x_peer_median_return_7d", "x_peer_count_7d",
)
SEQUENCE_FIELDS = ("log_close_over_reference", "adjacent_hour_log_return", "log_high_over_low")
IDENTITY_FIELDS = ("market_hash_name", "steamdt_item_id", "uu_template_id", "decision_time",
                   "decision_at_beijing", "split")
PREDICTION_FIELDS = IDENTITY_FIELDS + ("reference_bucket_time", "reference_close_cny") + FEATURE_FIELDS


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bytes_sha(value):
    return hashlib.sha256(value).hexdigest()


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_+\-]{0,95}", value):
        raise ValueError("Invalid dataset ID")
    if value.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)],
                        *[f"LPT{i}" for i in range(1, 10)]}:
        raise ValueError("Reserved dataset ID")
    return value


def _inside(path, root):
    resolved, designated = Path(path).resolve(), Path(root).resolve()
    if not resolved.is_relative_to(designated):
        raise ValueError("Dataset path escapes its designated root")
    return resolved


def _read_manifest(root, expected_version, expected_status, expected_id, database):
    path = root / "manifest.json"
    raw = path.read_bytes()
    value = json.loads(raw)
    if (value.get("version") != expected_version or value.get("status") != expected_status
            or value.get("output_id") != expected_id or value.get("database") != database):
        raise ValueError("Unexpected frozen dataset contract")
    if (root / "build_error.json").exists():
        raise ValueError("Dataset contains a failed-build marker")
    _verify_outputs(root, value)
    return value, raw


def _verify_outputs(root, manifest):
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict) or not outputs or manifest.get("database") not in outputs:
        raise ValueError("Frozen manifest has no verified database output")
    for relative, record in outputs.items():
        if not isinstance(relative, str) or Path(relative).is_absolute() or "\\" in relative:
            raise ValueError("Invalid manifest output path")
        path = _inside(root / relative, root)
        if (not isinstance(record, dict) or not path.is_file()
                or type(record.get("bytes")) is not int or record["bytes"] < 0
                or not isinstance(record.get("sha256"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", record["sha256"])
                or path.stat().st_size != record["bytes"] or _sha(path) != record["sha256"]):
            raise ValueError(f"Frozen output hash differs: {relative}")
    for relative, digest in manifest.get("code_files", {}).items():
        snapshot = "source/code/" + relative
        if snapshot not in outputs or outputs[snapshot]["sha256"] != digest:
            raise ValueError("Code snapshot hash is not covered by frozen outputs")
    spec_path = root / "source/spec.json"
    if ("source/spec.json" not in outputs or _sha(spec_path) != manifest.get("spec_sha256")
            or json.loads(spec_path.read_bytes()) != manifest.get("spec")):
        raise ValueError("Frozen specification differs")
    if manifest.get("schema"):
        schema = manifest["schema"]
        if schema not in outputs or outputs[schema]["sha256"] != manifest.get("schema_sha256"):
            raise ValueError("Frozen schema hash differs")
    db = root / manifest["database"]
    for suffix in ("-wal", "-journal"):
        sidecar = Path(str(db) + suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            raise ValueError("Frozen database has an active WAL or journal")


def _read_tables(path, table_names):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Frozen database integrity check failed")
        result = {name: [dict(row) for row in connection.execute(f'SELECT * FROM "{name}"')]
                  for name in table_names}
        connection.rollback()
    return result


def _boundary(value):
    date = datetime.fromisoformat(value)
    if date.utcoffset() != timedelta(hours=8) or date.strftime("%H:%M:%S") != "10:00:00" or date.microsecond:
        raise ValueError("Split boundary must be Beijing 10:00 with explicit timezone")
    return int(date.timestamp())


def _validate_sample_rows(rows, items, manifest):
    spec = manifest["spec"]
    if (spec.get("platform") != "YOUPIN" or spec.get("period") != "1h" or spec.get("style") != ""
            or spec.get("lookback_days") != 28 or spec.get("horizon_days") != 7
            or spec.get("impute_prices") is not False):
        raise ValueError("Unsupported feature/target specification")
    validation, test = (_boundary(spec[key]) for key in ("validation_start_beijing", "test_start_beijing"))
    if validation >= test:
        raise ValueError("Invalid date split")
    by_name = {item["market_hash_name"]: item for item in items}
    if len(by_name) != len(items) or len(items) != manifest["summary"]["item_count"]:
        raise ValueError("Duplicate or inconsistent item identities")
    cutoff = manifest["source_cutoff_exclusive"]
    if type(cutoff) is not int or cutoff % HOUR:
        raise ValueError("Invalid source cutoff")
    seen = set()
    for row in rows:
        name, decision = row.get("market_hash_name"), row.get("decision_time")
        key = (name, decision)
        item = by_name.get(name)
        if not item or type(decision) is not int or decision % HOUR or key in seen:
            raise ValueError("Invalid or duplicate sample identity")
        seen.add(key)
        if any(row.get(k) != item.get(k) for k in ("steamdt_item_id", "uu_template_id")):
            raise ValueError("Sample item mapping differs from frozen registry")
        split = "train" if decision < validation else "validation" if decision < test else "test"
        boundary = validation if split == "train" else test if split == "validation" else None
        purged = int(boundary is not None and decision + 168 * HOUR >= boundary)
        if (row.get("split") != split or row.get("purged") != purged
                or row.get("target_time") != decision + 168 * HOUR
                or row.get("target_bucket_time") != decision + 167 * HOUR
                or row.get("reference_bucket_time") != decision - HOUR or decision > cutoff):
            raise ValueError("Sample split, purge or time contract differs")
        for field in FEATURE_FIELDS:
            if field not in row or (row[field] is not None and not math.isfinite(float(row[field]))):
                raise ValueError("Feature is missing from schema or not finite")
        for profile in ("quality", "strict"):
            field = "eligible_point_" + profile
            if row.get(field) not in (0, 1):
                raise ValueError("Invalid eligibility flag")
            if row[field] and (purged or row.get("point_label_available") != 1
                               or decision + 168 * HOUR > cutoff
                               or not _finite_positive(row.get("x_reference_close"))
                               or row.get("y_return_7d") is None
                               or not math.isfinite(float(row["y_return_7d"]))):
                raise ValueError("Eligible point has unavailable target or input")
    if len(rows) != manifest["summary"]["samples"]:
        raise ValueError("Sample row count differs from frozen summary")


def _finite_positive(value):
    if value is None or isinstance(value, (bool, np.bool_)):
        return False
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (ValueError, TypeError, OverflowError):
        return False


def load_dataset(dataset_id=DEFAULT_DATASET_ID, profile="quality", include_hourly=True):
    """Verify both immutable parents and load eligible rows; no training is run.

    ``splits['test_exploratory']`` contains source rows whose stored split is
    ``test``. This old test was already viewed and is not a new holdout.
    All rows, including unavailable/purged ones, remain in ``all_rows``.
    """
    if profile not in ("quality", "strict"):
        raise ValueError("profile must be quality or strict")
    root = _inside(BASE / _identifier(dataset_id), BASE)
    manifest, raw = _read_manifest(root, "seven-daily-samples-1.0",
                                   "frozen_retrospective_feature_label_candidate", dataset_id, "samples.sqlite")
    if manifest.get("dataset_id") != dataset_id or tuple(manifest.get("feature_fields", ())) != FEATURE_FIELDS:
        raise ValueError("Frozen dataset feature order differs")
    parent_id = _identifier(manifest["parent_clean_id"])
    parent_root = _inside(CLEAN_BASE / parent_id, CLEAN_BASE)
    parent, parent_raw = _read_manifest(parent_root, "steamdt-hourly-cleaning-1.0",
                                       "frozen_research_cleaning_candidate", parent_id, "clean.sqlite")
    if (_bytes_sha(parent_raw) != manifest.get("parent_manifest_sha256")
            or (root / "source/parent_manifest.json").read_bytes() != parent_raw
            or parent["outputs"]["clean.sqlite"]["sha256"] != manifest.get("parent_database_sha256")
            or parent.get("source_cutoff_exclusive") != manifest.get("source_cutoff_exclusive")
            or parent.get("source_request_cap") != manifest.get("source_request_cap")):
        raise ValueError("Frozen parent provenance differs")
    tables = _read_tables(root / "samples.sqlite", ("items", "samples"))
    items = sorted(tables["items"], key=lambda row: row["market_hash_name"])
    all_rows = sorted(tables["samples"], key=lambda row: (row["decision_time"], row["market_hash_name"]))
    _validate_sample_rows(all_rows, items, manifest)
    parent_tables = _read_tables(parent_root / "clean.sqlite", ("items", "hourly") if include_hourly else ("items",))
    if sorted(parent_tables["items"], key=lambda row: row["market_hash_name"]) != items:
        raise ValueError("Sample and hourly item identities differ")
    hourly_by_item = {item["market_hash_name"]: [] for item in items}
    if include_hourly:
        for row in parent_tables["hourly"]:
            if row.get("market_hash_name") not in hourly_by_item:
                raise ValueError("Unexpected hourly item")
            hourly_by_item[row["market_hash_name"]].append(row)
        for item in items:
            hours = sorted(hourly_by_item[item["market_hash_name"]], key=lambda row: row["bucket_time"])
            expected = range(item["start_time"], manifest["source_cutoff_exclusive"], HOUR)
            if [row["bucket_time"] for row in hours] != list(expected):
                raise ValueError("Parent hourly grid has duplicate or missing explicit buckets")
            hourly_by_item[item["market_hash_name"]] = hours
    field = "eligible_point_" + profile
    rows = [row for row in all_rows if row[field] == 1]
    splits = {name: [row for row in rows if row["split"] == source]
              for name, source in (("train", "train"), ("validation", "validation"), ("test_exploratory", "test"))}
    for frozen_root, value, original in ((root, manifest, raw), (parent_root, parent, parent_raw)):
        _verify_outputs(frozen_root, value)
        if (frozen_root / "manifest.json").read_bytes() != original:
            raise ValueError("Frozen manifest changed during loading")
    provenance = {
        "adapter_version": VERSION, "dataset_id": dataset_id, "profile": profile, "eligibility_field": field,
        "dataset_manifest_sha256": _bytes_sha(raw),
        "dataset_database_sha256": manifest["outputs"]["samples.sqlite"]["sha256"],
        "parent_clean_id": parent_id, "parent_manifest_sha256": _bytes_sha(parent_raw),
        "parent_database_sha256": parent["outputs"]["clean.sqlite"]["sha256"],
        "source_cutoff_exclusive": manifest["source_cutoff_exclusive"],
        "source_request_cap": manifest["source_request_cap"],
        "source_outputs_verified": True, "source_unchanged": True,
        "historical_available_at_verified": manifest.get("historical_available_at_verified", False),
        "source_training_approved": manifest.get("training_approved", False),
        "test_usage": manifest["spec"]["test_usage"],
        "dataset_outputs": manifest["outputs"], "parent_outputs": parent["outputs"],
    }
    return {"rows": rows, "all_rows": all_rows, "splits": splits, "feature_fields": list(FEATURE_FIELDS),
            "items": items, "hourly_by_item": hourly_by_item, "provenance": provenance,
            "manifest": manifest, "parent_manifest": parent}


def _feature_fields(feature_fields):
    fields = tuple(feature_fields)
    if fields != FEATURE_FIELDS:
        raise ValueError("Exactly the frozen 21 features in their original order are required")
    return fields


def prediction_rows(rows):
    """Explicitly remove future labels, target quality and eligibility metadata."""
    return [{field: row[field] for field in PREDICTION_FIELDS if field in row} for row in rows]


def prepare_rows(rows, feature_fields=FEATURE_FIELDS, include_labels=False):
    """Convert the input whitelist; labels are returned only when explicitly requested."""
    fields, rows = _feature_fields(feature_fields), list(rows)
    x = np.empty((len(rows), len(fields)), dtype=np.float64)
    references, names, keys = [], [], []
    for i, row in enumerate(rows):
        name, time = row.get("market_hash_name"), row.get("decision_time")
        if not isinstance(name, str) or not name or type(time) is not int or time % HOUR:
            raise ValueError("Prediction input requires an item and whole-hour origin")
        names.append(name)
        keys.append((name, time))
        for j, field in enumerate(fields):
            if field not in row:
                raise ValueError(f"Prediction input lacks feature {field}")
            value = row[field]
            if isinstance(value, (bool, np.bool_)):
                raise ValueError("Boolean is not a numeric model feature")
            x[i, j] = np.nan if value is None else float(value)
            if np.isinf(x[i, j]):
                raise ValueError("Infinite model input")
        if not _finite_positive(row.get("x_reference_close")):
            raise ValueError("Prediction input requires a known positive reference close")
        references.append(float(row["x_reference_close"]))
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate prediction sample keys")
    result = {"x_tabular": x, "tabular": x, "item_names": names, "keys": keys,
              "reference": np.asarray(references, dtype=np.float64)}
    if include_labels:
        targets = np.asarray([row.get("y_return_7d", np.nan) for row in rows], dtype=np.float64)
        if not np.isfinite(targets).all():
            raise ValueError("Explicit labeled preparation requires finite seven-day targets")
        result.update(target=targets, y_return_7d=targets)
    return result


def build_sequences(rows, hourly_by_item, lookback_hours=672):
    """Build only past, exact hourly buckets; missing hours never bridge a return.

    The first return in each window is NaN because it has no predecessor inside
    this window. No source flow, diagnosis, future target or eligibility is read.
    """
    if type(lookback_hours) is not int or lookback_hours != 672:
        raise ValueError("The frozen sequence contract requires 672 hours")
    rows = prediction_rows(list(rows))
    prepared = prepare_rows(rows)
    result = np.full((len(rows), lookback_hours, 3), np.nan, dtype=np.float64)
    indices = {}
    for name in set(prepared["item_names"]):
        if name not in hourly_by_item:
            raise ValueError("Missing parent hourly series")
        by_time = {}
        for row in hourly_by_item[name]:
            bucket = row.get("bucket_time")
            if type(bucket) is not int or bucket % HOUR or bucket in by_time:
                raise ValueError("Invalid or duplicate parent hourly bucket")
            if row.get("market_hash_name", name) != name:
                raise ValueError("Parent hourly item differs")
            by_time[bucket] = row
        indices[name] = by_time
    for i, (name, decision) in enumerate(prepared["keys"]):
        reference = prepared["reference"][i]
        previous = None
        for j, time in enumerate(range(decision - lookback_hours * HOUR, decision, HOUR)):
            hour = indices[name].get(time)
            if hour is None or hour.get("observed") != 1 or hour.get("price_valid") != 1:
                previous = None
                continue
            if not all(_finite_positive(hour.get(key)) for key in ("close_cny", "high_cny", "low_cny")):
                raise ValueError("Valid parent hourly mask contradicts numeric prices")
            close, high, low = (float(hour[key]) for key in ("close_cny", "high_cny", "low_cny"))
            if not low <= close <= high:
                raise ValueError("Parent high/low contradict close")
            result[i, j, 0] = math.log(close) - math.log(reference)
            result[i, j, 2] = math.log(high) - math.log(low)
            if previous is not None:
                result[i, j, 1] = math.log(close) - math.log(previous)
            previous = close
        if not np.isfinite(result[i, -1, 0]) or abs(result[i, -1, 0]) > 1e-10:
            raise ValueError("Latest past close differs from sample reference")
    return result
