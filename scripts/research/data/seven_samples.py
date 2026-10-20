"""Frozen, retrospective daily features and independent seven-day labels from clean hours."""
from __future__ import annotations

from collections import Counter
from contextlib import closing
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import statistics
import uuid

ROOT = Path(__file__).resolve().parents[3]
CLEAN_BASE = ROOT / "data/local/datasets/steamdt_clean"
BASE = ROOT / "data/local/datasets/seven_daily"
DEFAULT_SPEC = ROOT / "scripts/config/seven_daily_spec.json"
VERSION = "seven-daily-samples-1.0"
CHINA = timezone(timedelta(hours=8))
HOUR, DAY = 3600, 86400
CODE_FILES = ("scripts/build_seven_samples.py", "scripts/research/__init__.py",
              "scripts/research/data/__init__.py", "scripts/research/data/seven_samples.py")
SPEC = {
    "version": "seven-daily-spec-1.0", "platform": "YOUPIN", "period": "1h", "style": "",
    "decision_time_beijing": "10:00", "lookback_days": 28, "horizon_days": 7,
    "return_lags_days": [1, 3, 7, 14], "ma_days": [7, 14, 28], "vol_days": [7, 14],
    "range_days": 7, "input_min_coverage": 0.95, "input_recent_complete_hours": 24,
    "validation_start_beijing": "2026-04-01T10:00:00+08:00",
    "test_start_beijing": "2026-07-01T10:00:00+08:00",
    "feature_profile": "observed_price_quality_peer_v1", "impute_prices": False,
    "use_source_flows_as_features": False, "peer_return_days": 7,
    "historical_available_at_verified": False, "training_approved": False,
    "test_usage": "exploratory_already_viewed_no_new_independent_holdout",
}
EXPECTED_SPEC = SPEC
FEATURE_FIELDS = (
    "x_reference_close", "x_return_1d", "x_return_3d", "x_return_7d", "x_return_14d",
    "x_ma_ratio_7d", "x_ma_ratio_14d", "x_ma_ratio_28d",
    "x_vol_7d", "x_vol_14d", "x_adjacent_return_coverage_7d", "x_adjacent_return_coverage_14d",
    "x_range_7d", "x_min_hourly_return_7d", "x_max_hourly_return_7d",
    "x_price_coverage_28d", "x_price_coverage_24h", "x_longest_missing_hours_28d",
    "x_price_age_hours", "x_peer_median_return_7d", "x_peer_count_7d",
)
KEY_FIELDS = ("market_hash_name", "steamdt_item_id", "uu_template_id", "decision_time", "decision_at_beijing", "split")
LABEL_FIELDS = ("target_time", "target_at_beijing", "target_bucket_time", "reference_bucket_time",
                "reference_close_cny", "y_reference_close_7d", "y_return_7d", "point_label_status", "point_label_available",
                "y_path_min_low_7d", "y_path_max_high_7d", "y_path_min_return_7d", "y_path_max_return_7d",
                "path_label_status", "path_label_available", "future_valid_hours", "purged",
                "strict_input_complete", "input_quality_pass", "eligible_point_strict", "eligible_point_quality",
                "eligible_path_strict", "eligible_path_quality")


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def _inside(path, root):
    path = Path(path).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("Path escapes designated root")
    return path


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_+\-]{0,95}", value):
        raise ValueError("Invalid dataset id")
    if value.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
        raise ValueError("Reserved dataset id")
    return value


def _iso(value):
    return datetime.fromtimestamp(value, CHINA).isoformat()


def _epoch(value):
    try:
        date = datetime.fromisoformat(value)
        if date.utcoffset() != timedelta(hours=8) or date.strftime("%H:%M:%S") != "10:00:00" or date.microsecond:
            raise ValueError("Expected Beijing 10:00 boundary with explicit +08:00")
        return int(date.timestamp())
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid split boundary") from error


def _validate_spec(spec):
    if not isinstance(spec, dict) or set(spec) != set(SPEC):
        raise ValueError("Sample specification fields differ from v1")
    if any(spec[key] != value for key, value in SPEC.items() if key not in {"validation_start_beijing", "test_start_beijing"}):
        raise ValueError("Sample specification differs from v1 rules")
    validation, test = (_epoch(spec[key]) for key in ("validation_start_beijing", "test_start_beijing"))
    if validation >= test:
        raise ValueError("Validation must precede test")
    return validation, test


def split_for(decision, spec):
    """Same decision dates share one split across all items; purge touching next boundary."""
    validation, test = _validate_spec(spec)
    if type(decision) is not int:
        raise ValueError("Decision must be integer seconds")
    if decision < validation:
        return "train", int(decision + spec["horizon_days"] * DAY >= validation)
    if decision < test:
        return "validation", int(decision + spec["horizon_days"] * DAY >= test)
    return "test", 0


def _price(value):
    try:
        if value is None or isinstance(value, bool):
            raise ValueError("Missing valid price")
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0 or not math.isfinite(float(number)) or float(number) == 0:
            raise ValueError("Invalid valid price")
        return number
    except (TypeError, InvalidOperation, OverflowError) as error:
        raise ValueError("Invalid price") from error


def _grid(rows, item, cutoff):
    if type(cutoff) is not int or cutoff % HOUR:
        raise ValueError("Cutoff must be whole-hour epoch seconds")
    start = item.get("start_time")
    if type(start) is not int or start % HOUR or start >= cutoff:
        raise ValueError("Item requires explicit whole-hour start before cutoff")
    by_time = {}
    for source in rows:
        row = dict(source)
        t = row.get("bucket_time")
        if type(t) is not int or t % HOUR or t < start or t >= cutoff or t in by_time:
            raise ValueError("Clean hourly grid has invalid, duplicate or out-of-range buckets")
        if row.get("market_hash_name") != item["market_hash_name"]:
            raise ValueError("Clean row belongs to another item")
        if row.get("steamdt_item_id") != item["steamdt_item_id"] or row.get("uu_template_id") != item.get("uu_template_id"):
            raise ValueError("Clean row identity differs from item")
        if row.get("observed") not in (0, 1) or row.get("price_valid") not in (0, 1):
            raise ValueError("Clean row mask contract differs")
        valid = row["price_valid"] == 1
        values = {}
        if valid:
            if not row["observed"]:
                raise ValueError("Valid price cannot be unobserved")
            values = {key: _price(row.get(key)) for key in ("open_cny", "close_cny", "high_cny", "low_cny")}
            if not values["low_cny"] <= min(values["open_cny"], values["close_cny"]) <= max(values["open_cny"], values["close_cny"]) <= values["high_cny"]:
                raise ValueError("Clean OHLC contradicts itself")
        elif any(row.get(key) is not None for key in ("open_cny", "close_cny", "high_cny", "low_cny")):
            raise ValueError("Invalid-price mask requires NULL clean OHLC")
        by_time[t] = (row, values)
    if set(by_time) != set(range(start, cutoff, HOUR)):
        raise ValueError("Clean grid must include explicit NULL rows for every missing hour")
    return start, by_time


def _ratio(a, b):
    return float(a / b - 1) if a is not None and b is not None else None


def compute_item_samples(rows, item, spec, cutoff):
    """Pure daily rows. All x values use only [t-672h,t); point and path labels are independent."""
    _validate_spec(spec)
    start, hours = _grid(rows, item, cutoff)
    lookback, horizon = spec["lookback_days"] * DAY, spec["horizon_days"] * DAY
    first = datetime.fromtimestamp(start + lookback, CHINA).replace(hour=10, minute=0, second=0, microsecond=0)
    if first.timestamp() < start + lookback:
        first += timedelta(days=1)
    decision = int(first.timestamp())
    samples = []
    while decision <= cutoff:
        past = [hours[t] for t in range(decision - lookback, decision, HOUR)]
        valid_count = sum(bool(values) for _, values in past)
        ref_values = past[-1][1]
        ref = ref_values.get("close_cny")
        longest, run = 0, 0
        last_valid = None
        for index, (_, values) in enumerate(past):
            run = 0 if values else run + 1
            longest = max(longest, run)
            if values:
                last_valid = index
        recent = sum(bool(values) for _, values in past[-24:])
        split, purged = split_for(decision, spec)
        result = {"market_hash_name": item["market_hash_name"], "steamdt_item_id": item["steamdt_item_id"],
                  "uu_template_id": item.get("uu_template_id"), "decision_time": decision,
                  "decision_at_beijing": _iso(decision), "split": split, "purged": purged,
                  "reference_bucket_time": decision - HOUR,
                  "reference_close_cny": past[-1][0]["close_cny"] if ref is not None else None,
                  "target_time": decision + horizon, "target_at_beijing": _iso(decision + horizon),
                  "target_bucket_time": decision + horizon - HOUR,
                  "strict_input_complete": int(valid_count == len(past)),
                  "input_quality_pass": int(valid_count / len(past) >= spec["input_min_coverage"] and recent == 24),
                  "past_valid_hours": valid_count, "past_expected_hours": len(past),
                  "aux_volume_unknown_hours": sum(row.get("source_volume") is None for row, _ in past),
                  "aux_turnover_unknown_hours": sum(row.get("source_turnover_cny") is None for row, _ in past),
                  "x_reference_close": float(ref) if ref is not None else None,
                  "x_price_coverage_28d": valid_count / len(past), "x_price_coverage_24h": recent / 24,
                  "x_longest_missing_hours_28d": longest,
                  "x_price_age_hours": len(past) - 1 - last_valid if last_valid is not None else None,
                  "x_peer_median_return_7d": None, "x_peer_count_7d": 0}
        for days in spec["return_lags_days"]:
            lag = past[-1 - days * 24][1].get("close_cny")
            result[f"x_return_{days}d"] = _ratio(ref, lag)
        for days in spec["ma_days"]:
            values = [values["close_cny"] for _, values in past[-days * 24:] if values]
            mean = sum(values) / len(values) if values else None
            result[f"x_ma_ratio_{days}d"] = _ratio(ref, mean)
        for days in spec["vol_days"]:
            window = past[-days * 24:]
            changes = [math.log(float(right[1]["close_cny"] / left[1]["close_cny"]))
                       for left, right in zip(window, window[1:]) if left[1] and right[1]]
            result[f"x_vol_{days}d"] = statistics.stdev(changes) if len(changes) >= 2 else None
            result[f"x_adjacent_return_coverage_{days}d"] = len(changes) / (days * 24 - 1)
        week = past[-spec["range_days"] * 24:]
        lows = [values["low_cny"] for _, values in week if values]
        highs = [values["high_cny"] for _, values in week if values]
        changes = [_ratio(right[1]["close_cny"], left[1]["close_cny"])
                   for left, right in zip(week, week[1:]) if left[1] and right[1]]
        result["x_range_7d"] = _ratio(max(highs), min(lows)) if lows else None
        result["x_min_hourly_return_7d"] = min(changes) if changes else None
        result["x_max_hourly_return_7d"] = max(changes) if changes else None
        mature = decision + horizon <= cutoff
        target = hours.get(decision + horizon - HOUR)
        target_values = target[1] if target else {}
        point_available = mature and bool(target_values)
        result.update(point_label_status="available" if point_available else "missing_endpoint" if mature else "pending",
                      point_label_available=int(point_available),
                      y_reference_close_7d=target[0]["close_cny"] if point_available else None,
                      y_return_7d=_ratio(target_values.get("close_cny"), ref) if point_available else None)
        future = [hours[t] for t in range(decision, min(decision + horizon, cutoff), HOUR)]
        future_valid = sum(bool(values) for _, values in future)
        path_available = mature and future_valid == horizon // HOUR
        low = min(values["low_cny"] for _, values in future) if path_available else None
        high = max(values["high_cny"] for _, values in future) if path_available else None
        result.update(path_label_status="available" if path_available else "incomplete_path" if mature else "pending",
                      path_label_available=int(path_available), future_valid_hours=future_valid,
                      y_path_min_low_7d=str(low) if low is not None else None,
                      y_path_max_high_7d=str(high) if high is not None else None,
                      y_path_min_return_7d=_ratio(low, ref), y_path_max_return_7d=_ratio(high, ref))
        for target_name, available in (("point", point_available), ("path", path_available)):
            for profile, ready in (("strict", result["strict_input_complete"]), ("quality", result["input_quality_pass"])):
                result[f"eligible_{target_name}_{profile}"] = int(available and ready and not purged)
        if any(value is not None and not math.isfinite(value) for key, value in result.items() if key in FEATURE_FIELDS):
            raise ValueError("Non-finite feature; stop rather than silently replace")
        samples.append(result)
        decision += DAY
    return samples


build_rows = compute_item_samples


def add_peer_features(samples):
    """Leave-one-item-out peers based on past endpoint returns, never future eligibility."""
    dates = {}
    seen = set()
    for row in samples:
        key = (row["market_hash_name"], row["decision_time"])
        if key in seen:
            raise ValueError("Duplicate item/date sample")
        seen.add(key)
        value = row["x_return_7d"]
        if value is not None and not math.isfinite(value):
            raise ValueError("Non-finite peer return")
        dates.setdefault(row["decision_time"], []).append(row)
    output = []
    for row in samples:
        peers = [other["x_return_7d"] for other in dates[row["decision_time"]]
                 if other["market_hash_name"] != row["market_hash_name"] and other["x_return_7d"] is not None]
        copy = dict(row)
        copy.update(x_peer_median_return_7d=statistics.median(peers) if peers else None, x_peer_count_7d=len(peers))
        output.append(copy)
    return output


def _verify_outputs(root, manifest):
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        raise ValueError("Frozen manifest has no output hashes")
    for name, info in outputs.items():
        path = _inside(root / name, root)
        if not path.is_file() or not isinstance(info, dict) or path.stat().st_size != info.get("bytes") or _sha(path) != info.get("sha256"):
            raise ValueError("Frozen output missing or hash changed: " + name)


def _parent(clean_id):
    clean_id = _identifier(clean_id)
    root = _inside(CLEAN_BASE / clean_id, CLEAN_BASE)
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    if (manifest.get("version") != "steamdt-hourly-cleaning-1.0"
            or manifest.get("status") != "frozen_research_cleaning_candidate" or manifest.get("output_id") != clean_id
            or manifest.get("database") != "clean.sqlite" or "clean.sqlite" not in manifest.get("outputs", {})):
        raise ValueError("Parent is not a recognized frozen cleaning version")
    cutoff = manifest.get("source_cutoff_exclusive")
    if type(cutoff) is not int or cutoff % HOUR:
        raise ValueError("Parent has no explicit complete-hour cutoff")
    _verify_outputs(root, manifest)
    database = _inside(root / "clean.sqlite", root)
    wal = Path(str(database) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise ValueError("Frozen parent has an active WAL; stop")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Parent SQLite integrity check failed")
        items = [dict(row) for row in db.execute("SELECT * FROM items ORDER BY market_hash_name")]
        if not 1 <= len(items) <= 50 or len({item["market_hash_name"] for item in items}) != len(items):
            raise ValueError("Parent item registry invalid")
        if len(items) != manifest.get("summary", {}).get("item_count"):
            raise ValueError("Parent item count differs from manifest")
        rows = {item["market_hash_name"]: [dict(row) for row in db.execute(
            "SELECT * FROM hourly WHERE market_hash_name=? ORDER BY bucket_time", (item["market_hash_name"],))] for item in items}
        if sum(map(len, rows.values())) != manifest.get("summary", {}).get("grid_hours"):
            raise ValueError("Parent hourly grid count differs from manifest")
        db.rollback()
    _verify_outputs(root, manifest)
    if (root / "manifest.json").read_bytes() != manifest_bytes:
        raise ValueError("Parent manifest changed during read")
    return root, manifest, manifest_bytes, items, rows


def _csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _table(db, name, rows, fields, integer_fields=()):
    kinds = {field: "REAL" if field in FEATURE_FIELDS or field in {"y_return_7d", "y_path_min_return_7d", "y_path_max_return_7d"}
             else "INTEGER" if field in integer_fields else "TEXT" for field in fields}
    db.execute('CREATE TABLE "' + name + '" (' + ','.join('"' + field + '" ' + kinds[field] for field in fields) + ')')
    db.executemany('INSERT INTO "' + name + '" VALUES (' + ','.join('?' for _ in fields) + ')',
                   ([row.get(field) for field in fields] for row in rows))


def build_samples(clean_id="seven_clean_20261019_v1", dataset_id=None, spec_path=DEFAULT_SPEC):
    """Offline immutable feature/label candidate; never fit a model or alter the parent."""
    spec_path = _inside(Path(spec_path), ROOT)
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes.decode("utf-8-sig"))
    _validate_spec(spec)
    parent, parent_manifest, parent_bytes, items, hour_rows = _parent(clean_id)
    created = datetime.now(CHINA)
    dataset_id = _identifier(dataset_id or "seven_daily_" + created.strftime("%Y%m%dT%H%M%S%z_") + uuid.uuid4().hex[:8])
    output = _inside(BASE / dataset_id, BASE)
    if output.exists():
        raise FileExistsError("Sample version exists; choose a new dataset id")
    code = {name: _inside(ROOT / name, ROOT).read_bytes() for name in CODE_FILES}
    output.mkdir(parents=True, exist_ok=False)
    try:
        (output / "source").mkdir()
        (output / "source/spec.json").write_bytes(spec_bytes)
        (output / "source/parent_manifest.json").write_bytes(parent_bytes)
        for name, data in code.items():
            path = output / "source/code" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        _dump(output / "protocol_locked.json", {"version": VERSION, "locked_at": created.isoformat(),
              "parent_clean_id": clean_id, "parent_manifest_sha256": hashlib.sha256(parent_bytes).hexdigest(),
              "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(), "feature_fields": list(FEATURE_FIELDS),
              "no_imputation": True, "test_usage": spec["test_usage"], "historical_available_at_verified": False})
        cutoff = parent_manifest["source_cutoff_exclusive"]
        samples = add_peer_features([row for item in items for row in compute_item_samples(hour_rows[item["market_hash_name"]], item, spec, cutoff)])
        if not samples:
            raise ValueError("No complete 28-day input periods in parent")
        integer_fields = {"decision_time", "reference_bucket_time", "target_time", "target_bucket_time", "purged",
                          "strict_input_complete", "input_quality_pass", "past_valid_hours", "past_expected_hours",
                          "aux_volume_unknown_hours", "aux_turnover_unknown_hours", "future_valid_hours",
                          "point_label_available", "path_label_available", "eligible_point_strict", "eligible_point_quality",
                          "eligible_path_strict", "eligible_path_quality"}
        fields = list(samples[0])
        with closing(sqlite3.connect(output / "samples.sqlite")) as db:
            _table(db, "samples", samples, fields, integer_fields)
            db.execute("CREATE UNIQUE INDEX sample_identity ON samples(market_hash_name,decision_time)")
            _table(db, "items", items, list(items[0]), {"start_time", "enabled"})
            db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value_json TEXT NOT NULL)")
            metadata = {"version": VERSION, "spec": spec, "feature_fields": list(FEATURE_FIELDS),
                        "parent_clean_id": clean_id, "parent_manifest_sha256": hashlib.sha256(parent_bytes).hexdigest(),
                        "source_cutoff_exclusive": cutoff, "historical_available_at_verified": False,
                        "training_approved": False, "numeric_features": "IEEE-754 double; reference/target CNY preserved as parent decimal text",
                        "moving_average": "Observed valid closes only; missing prices stay NULL; coverage records missingness",
                        "hourly_volatility": "Sample stdev of adjacent valid hourly log returns; no gap bridging; unannualized",
                        "point_label": "close of target_time-1h; independent of missing interior future hours",
                        "path_labels": "Full 168h valid OHLC required; low/high relative to decision reference, not maximum drawdown"}
            db.executemany("INSERT INTO metadata VALUES (?,?)", ((key, json.dumps(value, ensure_ascii=False, allow_nan=False)) for key, value in metadata.items()))
            db.commit()
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Sample database integrity check failed")
            schema_sql = ";\n".join(row[0] for row in db.execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name")) + ";\n"
        (output / "source/schema.sql").write_text(schema_sql, encoding="utf-8", newline="\n")
        _csv(output / "features.csv", samples, (*KEY_FIELDS, *FEATURE_FIELDS))
        _csv(output / "labels.csv", samples, (*KEY_FIELDS, *LABEL_FIELDS))
        eligibility = ("strict_input_complete", "input_quality_pass", "point_label_available", "path_label_available",
                       "eligible_point_strict", "eligible_point_quality", "eligible_path_strict", "eligible_path_quality", "purged")
        summaries = []
        for item in items:
            own = [row for row in samples if row["market_hash_name"] == item["market_hash_name"]]
            summaries.append({"market_hash_name": item["market_hash_name"], "name_zh": item.get("name_zh"), "samples": len(own),
                              **{key: sum(row[key] for row in own) for key in eligibility},
                              "point_status": dict(Counter(row["point_label_status"] for row in own)),
                              "path_status": dict(Counter(row["path_label_status"] for row in own)),
                              "split_counts": dict(Counter(row["split"] for row in own)),
                              "eligible_point_quality_by_split": dict(Counter(row["split"] for row in own if row["eligible_point_quality"]))})
        quality = {"version": VERSION, "item_count": len(items), "samples": len(samples), "feature_count": len(FEATURE_FIELDS),
                   "feature_fields": list(FEATURE_FIELDS), "items": summaries,
                   **{key: sum(row[key] for row in samples) for key in eligibility},
                   "point_status": dict(Counter(row["point_label_status"] for row in samples)),
                   "path_status": dict(Counter(row["path_label_status"] for row in samples)),
                   "null_features": {key: sum(row[key] is None for row in samples) for key in FEATURE_FIELDS},
                   "input_quality_gate_is_unvalidated_engineering_candidate": True,
                   "historical_available_at_verified": False, "training_approved": False,
                   "forward_holdout_available": False, "test_usage": spec["test_usage"], "models_fit": 0,
                   "prices_imputed": 0, "flows_used_as_features": False, "network_requests": 0}
        _dump(output / "quality_report.json", quality)
        lines = ["# 七品日级特征与七日标签", "", f"组件{VERSION}；生成{created.isoformat()}。",
                 f"父清洗版`{clean_id}`；小时截止{_iso(cutoff)}。不联网、不训练、不修改父库或旧Cyrex版本。", "",
                 "每日北京时间10:00，仅用此前28天672小时。收益1/3/7/14日、观察值均线/相邻小时波动、幅度/尾部、缺失与过去七日其他品中位数。",
                 "均线仅使用真实有效观察，未补价格；波动不跨缺口。reference_close_cny、y_reference_close_7d保留源十进制文本与bucket链接，x/收益为double近似。", "",
                 "| 商品 | 全时点 | 严格输入 | 95%且最近24h | 成熟点标签 | 完整路径标签 | 点/严格可评估 | 点/容缺可评估 |",
                 "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for summary in summaries:
            lines.append(f"| {summary['name_zh'] or summary['market_hash_name']} | {summary['samples']} | {summary['strict_input_complete']} | {summary['input_quality_pass']} | {summary['point_label_available']} | {summary['path_label_available']} | {summary['eligible_point_strict']} | {summary['eligible_point_quality']} |")
        lines.extend(["", "点标签只需t+168h成熟且其前完整小时真实有效；未来内部缺口不删除终点。路径低/高价格要求完整168h，路径相对收益不是最大回撤。",
                      "未来未到或缺失不补答案；输入资格、点/路径可用性、跨split标签隔离分别记录。eligible表示本研究规范可评估，不表示正式训练或交易批准。",
                      "同日跨品共同split，train/validation标签触及下一分界按7日purge；旧test已经查看，只作探索，没有新独立前向留出。",
                      "历史available_at未经验证，使用冻结来源后来已收到的版本，是回顾研究候选。95%门槛未经预测收益验证。",
                      "来源量额语义尚未验收，仅在samples保留unknown计数辅助审计，不进入FEATURE_FIELDS；未来状态、修订ID、missing_kind均不作输入。",
                      "输出samples.sqlite、features.csv（严格x白名单）、labels.csv、quality_report.json、准确代码/规范和父manifest。父库按清洗版ID和哈希引用，不复制原始响应。", ""])
        (output / "report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
        _verify_outputs(parent, parent_manifest)
        parent_wal = Path(str(parent / "clean.sqlite") + "-wal")
        if parent_wal.exists() and parent_wal.stat().st_size:
            raise ValueError("Parent WAL changed while building; result not finalized")
        if ((parent / "manifest.json").read_bytes() != parent_bytes or spec_path.read_bytes() != spec_bytes
                or any((ROOT / name).read_bytes() != data for name, data in code.items())):
            raise ValueError("Parent/spec/code changed while building; result not finalized")
        manifest = {"version": VERSION, "status": "frozen_retrospective_feature_label_candidate", "output_id": dataset_id,
                    "dataset_id": dataset_id, "output_dir": str(output), "created_at_beijing": created.isoformat(),
                    "parent_clean_id": clean_id, "parent_manifest": str(parent / "manifest.json"),
                    "parent_manifest_sha256": hashlib.sha256(parent_bytes).hexdigest(),
                    "parent_database_sha256": parent_manifest["outputs"]["clean.sqlite"]["sha256"],
                    "parent_outputs_verified": True, "parent_unchanged": True, "source_cutoff_exclusive": cutoff,
                    "source_cutoff_beijing": _iso(cutoff), "source_request_cap": parent_manifest.get("source_request_cap"),
                    "spec": spec, "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
                    "code_files": {name: hashlib.sha256(data).hexdigest() for name, data in code.items()},
                    "feature_fields": list(FEATURE_FIELDS), "sample_fields": fields, "database": "samples.sqlite",
                    "schema": "source/schema.sql", "schema_sha256": _sha(output / "source/schema.sql"),
                    "features": "features.csv", "labels": "labels.csv", "report": "report.md", "summary": quality,
                    "historical_available_at_verified": False, "training_approved": False, "network_requests": 0,
                    "outputs": {path.relative_to(output).as_posix(): {"bytes": path.stat().st_size, "sha256": _sha(path)}
                                for path in sorted(output.rglob("*")) if path.is_file()}}
        _dump(output / "manifest.json", manifest)
        temporary = BASE / ("latest." + uuid.uuid4().hex + ".tmp")
        _dump(temporary, {"output_id": dataset_id, "manifest": dataset_id + "/manifest.json"})
        temporary.replace(BASE / "latest.json")
        return manifest
    except Exception as error:
        _dump(output / "build_error.json", {"status": "not_finalized", "reason": str(error)})
        raise


def status(dataset_id=None):
    """Read an explicitly named or latest finalized version; verify its frozen outputs."""
    if dataset_id is None:
        pointer = BASE / "latest.json"
        if not pointer.exists():
            return {"version": VERSION, "status": "no_samples"}
        value = json.loads(pointer.read_text(encoding="utf-8-sig"))
        dataset_id = _identifier(value.get("output_id"))
        if value.get("manifest") != dataset_id + "/manifest.json":
            raise ValueError("Latest pointer is not an explicit dataset manifest")
    root = _inside(BASE / _identifier(dataset_id), BASE)
    if (root / "build_error.json").exists():
        raise ValueError("Sample version has a failed-build marker")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
    if (manifest.get("version") != VERSION or manifest.get("status") != "frozen_retrospective_feature_label_candidate"
            or manifest.get("output_id") != dataset_id):
        raise ValueError("Sample version is not finalized")
    _verify_outputs(root, manifest)
    return manifest
