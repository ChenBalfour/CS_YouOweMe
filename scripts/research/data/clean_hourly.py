"""Offline hourly cleaning: preserve source values, missingness and market shocks."""
from __future__ import annotations

import argparse
from collections import Counter, deque
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
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
SOURCE_BASE = ROOT / "data/local/staging/steamdt"
BASE = ROOT / "data/local/datasets/steamdt_clean"
DEFAULT_SPEC = ROOT / "scripts/config/steamdt_cleaning_spec.json"
VERSION = "steamdt-hourly-cleaning-1.0"
CHINA = timezone(timedelta(hours=8))
HOUR, DAY = 3600, 86400
CODE_FILES = ("scripts/clean_steamdt_data.py", "scripts/research/__init__.py",
              "scripts/research/data/__init__.py", "scripts/research/data/clean_hourly.py")
SOURCE_FIELDS = ("version_id", "market_hash_name", "platform", "period", "style", "source_time",
                 "bucket_time", "open_cny", "close_cny", "high_cny", "low_cny", "source_volume",
                 "source_turnover_cny", "source_request")
EXPECTED_SPEC = {"version": "steamdt-cleaning-spec-1.0", "platform": "YOUPIN", "period": "1h", "style": "",
                 "impute_prices": False, "impute_flows": False, "remove_extreme_moves": False,
                 "large_abs_hourly_return": 0.30, "large_intrabar_range": 0.30,
                 "robust_window_hours": 168, "robust_min_returns": 48, "robust_abs_score_threshold": 6,
                 "input_lookback_days": 28, "input_min_coverage": 0.95,
                 "input_recent_complete_hours": 24, "decision_hour_beijing": 10,
                 "historical_available_at_verified": False, "training_approved": False,
                 "purpose": "research_cleaning_and_quality_only_no_new_predictive_features_or_labels"}


def _sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def _inside(path, root):
    path = path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Path escapes designated data root")
    return path


def _iso(value):
    return datetime.fromtimestamp(value, CHINA).isoformat()


def _state(database):
    return {p.name: {"bytes": p.stat().st_size, "sha256": _sha(p)}
            for p in (database, Path(str(database) + "-wal")) if p.exists()}


def _number(value, *, positive=False, integer=False):
    try:
        if value is None or isinstance(value, bool):
            raise ValueError("Missing number")
        n = Decimal(str(value))
        if not n.is_finite() or n < 0 or (positive and n == 0) or not math.isfinite(float(n)):
            raise ValueError("Invalid number")
        if positive and float(n) == 0:
            raise ValueError("Price is outside numerical working range")
        if integer and (n != n.to_integral_value() or n > 9223372036854775807):
            raise ValueError("Invalid integral volume")
        return int(n) if integer else n
    except (InvalidOperation, TypeError, OverflowError) as error:
        raise ValueError("Invalid number") from error


def _integer(value):
    if type(value) is not int or value <= 0:
        raise ValueError("Source identifiers/times must be positive integers")
    return value


def select_versions(versions, name, start, cutoff):
    """Select the latest saved version per hour; keep every input version separately."""
    grouped = {}
    seen = set()
    for row in versions:
        if (row["market_hash_name"] != name or row["platform"] != "YOUPIN"
                or row["period"] != "1h" or row["style"] != ""):
            raise ValueError("Unexpected source identity")
        ident, request = _integer(row["version_id"]), _integer(row["source_request"])
        if ident in seen:
            raise ValueError("Duplicate source version id")
        seen.add(ident)
        bucket, event = _integer(row["bucket_time"]), _integer(row["source_time"])
        if bucket % HOUR or event // HOUR * HOUR != bucket or event > 10_000_000_000:
            raise ValueError("Source timestamp/bucket contract differs; stop rather than move prices")
        if start <= bucket < cutoff:
            grouped.setdefault(bucket, []).append(row)
    return {t: (max(rows, key=lambda r: (r["source_request"], r["source_time"], r["version_id"])), len(rows))
            for t, rows in grouped.items()}


def clean_rows(versions, item, start, cutoff, spec):
    """Return an exact hourly grid and causal diagnostics, without imputing prices."""
    if spec != EXPECTED_SPEC or start % HOUR or cutoff % HOUR or start >= cutoff:
        raise ValueError("Cleaning specification or whole-hour bounds differ")
    name = item["market_hash_name"]
    selected = select_versions(versions, name, start, cutoff)
    first, last = (min(selected), max(selected)) if selected else (None, None)
    rows, history = [], deque()
    previous, last_valid = None, None
    for t in range(start, cutoff, HOUR):
        pair = selected.get(t)
        flags = []
        row = {"market_hash_name": name, "steamdt_item_id": item["steamdt_item_id"],
               "uu_template_id": item.get("uu_template_id"), "bucket_time": t, "at_beijing": _iso(t),
               "observed": int(pair is not None), "price_valid": 0,
               "open_cny": None, "close_cny": None, "high_cny": None, "low_cny": None,
               "source_volume": None, "source_turnover_cny": None,
               "source_version_id": None, "source_time": None, "source_request": None,
               "version_count": 0, "source_offset_seconds": None, "missing_kind": None,
               "price_age_hours": None, "large_up_move": 0, "large_down_move": 0,
               "wide_intrabar": 0, "robust_jump": 0, "robust_score": None,
               "robust_reference_returns": 0, "robust_reference_zero_mad": 0,
               "volume_missing": 1, "turnover_missing": 1}
        if pair is None:
            row["missing_kind"] = ("no_observations" if first is None else "before_first_observation" if t < first
                                   else "after_last_observation" if t > last else "internal_gap")
            flags.append("missing_hour")
        else:
            source, count = pair
            row.update(source_version_id=source["version_id"], source_time=source["source_time"],
                       source_request=source["source_request"], version_count=count,
                       source_offset_seconds=source["source_time"] - t)
            if count > 1:
                flags.append("multiple_source_versions")
            if row["source_offset_seconds"]:
                flags.append("source_timestamp_offset")
            try:
                values = {key: _number(source[key], positive=True)
                          for key in ("open_cny", "close_cny", "high_cny", "low_cny")}
                if not (values["low_cny"] <= min(values["open_cny"], values["close_cny"])
                        <= max(values["open_cny"], values["close_cny"]) <= values["high_cny"]):
                    raise ValueError("OHLC contradiction")
                row.update({key: str(value) for key, value in values.items()})
                row["price_valid"] = 1
            except ValueError:
                flags.append("invalid_price_or_ohlc")
            for key, integer, flag in (("source_volume", True, "invalid_volume"),
                                       ("source_turnover_cny", False, "invalid_turnover")):
                value = source[key]
                if value is None or (isinstance(value, str) and not value.strip()):
                    continue
                try:
                    parsed = _number(value, integer=integer)
                    row[key] = parsed if integer else str(parsed)
                except ValueError:
                    flags.append(flag)
        row["volume_missing"] = int(row["source_volume"] is None)
        row["turnover_missing"] = int(row["source_turnover_cny"] is None)
        while history and history[0][0] < t - spec["robust_window_hours"] * HOUR:
            history.popleft()
        if row["price_valid"]:
            last_valid = t
            lo, hi = Decimal(row["low_cny"]), Decimal(row["high_cny"])
            row["wide_intrabar"] = int(hi / lo - 1 >= Decimal(str(spec["large_intrabar_range"])))
            if previous is not None and previous["price_valid"]:
                ratio = Decimal(row["close_cny"]) / Decimal(previous["close_cny"])
                change, log_return = ratio - 1, float(ratio.ln())
                threshold = Decimal(str(spec["large_abs_hourly_return"]))
                row["large_up_move"], row["large_down_move"] = int(change >= threshold), int(change <= -threshold)
                row["robust_reference_returns"] = len(history)
                if len(history) >= spec["robust_min_returns"]:
                    past = [entry[1] for entry in history]
                    center = statistics.median(past)
                    mad = statistics.median(abs(value - center) for value in past)
                    if mad > 0:
                        score = (log_return - center) / (1.4826 * mad)
                        row["robust_score"] = score
                        row["robust_jump"] = int(abs(score) >= spec["robust_abs_score_threshold"])
                    else:
                        row["robust_reference_zero_mad"] = 1
                # Current return cannot change its own reference distribution.
                history.append((t, log_return))
            for key in ("large_up_move", "large_down_move", "wide_intrabar", "robust_jump"):
                if row[key]:
                    flags.append(key)
        row["price_age_hours"] = None if last_valid is None else (t - last_valid) // HOUR
        row["quality_flags"] = json.dumps(flags, separators=(",", ":"))
        rows.append(row)
        previous = row  # Missing hour breaks adjacency; no returns across a gap.
    return rows


def quality_windows(rows, start, cutoff, spec):
    """Past-only input readiness. No predictive features, target values or eligibility labels."""
    width = spec["input_lookback_days"] * 24
    recent = spec["input_recent_complete_hours"]
    prefix = [0]
    for row in rows:
        prefix.append(prefix[-1] + row["price_valid"])
    earliest = start + width * HOUR
    date = datetime.fromtimestamp(earliest, CHINA).replace(hour=spec["decision_hour_beijing"], minute=0, second=0, microsecond=0)
    if date.timestamp() < earliest:
        date += timedelta(days=1)
    result = []
    decision = int(date.timestamp())
    while decision <= cutoff:
        end = (decision - start) // HOUR
        valid = prefix[end] - prefix[end - width]
        fresh = prefix[end] - prefix[end - recent]
        result.append({"market_hash_name": rows[0]["market_hash_name"], "decision_time": decision,
                       "decision_at_beijing": _iso(decision), "expected_hours": width, "valid_price_hours": valid,
                       "missing_or_invalid_price_hours": width - valid, "price_coverage": valid / width,
                       "recent_complete": int(fresh == recent), "strict_input_complete": int(valid == width),
                       "input_quality_pass": int(Decimal(valid) / Decimal(width) >= Decimal(str(spec["input_min_coverage"])) and fresh == recent)})
        decision += DAY
    return result


def gap_rows(rows):
    gaps = []
    active = None
    for row in rows:
        kind = row["missing_kind"]
        if active is not None and kind != active["kind"]:
            gaps.append(active)
            active = None
        if kind is not None:
            if active is None:
                active = {"market_hash_name": row["market_hash_name"], "kind": kind, "start": row["bucket_time"],
                          "start_beijing": row["at_beijing"], "end_exclusive": row["bucket_time"], "hours": 0}
            active["end_exclusive"] = row["bucket_time"] + HOUR
            active["hours"] += 1
    if active is not None:
        gaps.append(active)
    for gap in gaps:
        gap["end_beijing_exclusive"] = _iso(gap["end_exclusive"])
    return gaps


def _table(db, table, rows, keys=None):
    keys = list(keys or rows[0].keys())
    integers = {"version_id", "source_time", "bucket_time", "source_request", "source_version_id", "source_volume",
                "observed", "price_valid", "version_count", "source_offset_seconds", "price_age_hours", "large_up_move",
                "large_down_move", "wide_intrabar", "robust_jump", "robust_reference_returns", "robust_reference_zero_mad",
                "volume_missing", "turnover_missing", "decision_time", "expected_hours", "valid_price_hours",
                "missing_or_invalid_price_hours", "recent_complete", "strict_input_complete", "input_quality_pass", "request_id", "http_status", "error_code", "start_time", "enabled"}
    real = {"robust_score", "price_coverage"}
    db.execute('CREATE TABLE "' + table + '" (' + ','.join('"' + k + '" ' + ("INTEGER" if k in integers else "REAL" if k in real else "TEXT") for k in keys) + ')')
    _insert(db, table, keys, rows)


def _insert(db, table, keys, rows):
    db.executemany('INSERT INTO "' + table + '" VALUES (' + ','.join('?' for _ in keys) + ')',
                   ([row.get(k) for k in keys] for row in rows))


def _csv(path, rows, keys):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _load(workspace):
    if not re.fullmatch(r"research_[A-Za-z0-9_]{1,70}", workspace) or workspace == "research_control":
        raise ValueError("Invalid source workspace")
    source = _inside(SOURCE_BASE / workspace, SOURCE_BASE)
    database = source / "research.sqlite"
    pointer_bytes = (source / "latest_report.json").read_bytes()
    pointer = json.loads(pointer_bytes.decode("utf-8-sig"))
    report_path = _inside(source / pointer["report"].replace("\\", "/"), source)
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes.decode("utf-8-sig"))
    cap, cutoff = report.get("workspace_http_attempts_archived"), report.get("run", {}).get("end_exclusive")
    if (type(cap) is not int or cap <= 0 or type(cutoff) is not int or cutoff % HOUR
            or report.get("integrity") != "ok" or report.get("run", {}).get("status") != "completed"):
        raise ValueError("Use a completed integrity-checked source report with an explicit request cap")
    registry_bytes = (source / "registry.json").read_bytes()
    registry = json.loads(registry_bytes.decode("utf-8-sig"))
    items = [dict(item) for item in registry["items"] if item["enabled"]]
    if not 1 <= len(items) <= 50 or len({item["market_hash_name"] for item in items}) != len(items):
        raise ValueError("Registry must contain unique enabled items")
    before = _state(database)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Source database integrity check failed")
        versions = {}
        for item in items:
            name = item["market_hash_name"]
            identity = db.execute("SELECT steamdt_item_id,metadata_request FROM catalog WHERE market_hash_name=?", (name,)).fetchone()
            if identity is None or identity[0] != item["steamdt_item_id"] or not 0 < identity[1] <= cap:
                raise ValueError("Current identity is not covered by the frozen source report")
            uu = db.execute("SELECT platform_item_id FROM platform_ids WHERE market_hash_name=? AND platform='YOUPIN'", (name,)).fetchone()
            if uu is None or (item["uu_template_id"] is not None and item["uu_template_id"] != uu[0]):
                raise ValueError("UU identity differs or is missing")
            item["uu_template_id"] = uu[0]
            if item["history_start"] is None:
                raise ValueError("Cleaning needs an explicit registered start date")
            item["start_time"] = int(datetime.strptime(item["history_start"], "%Y-%m-%d").replace(tzinfo=CHINA).timestamp())
            versions[name] = [dict(row) for row in db.execute(
                "SELECT " + ','.join(SOURCE_FIELDS) + " FROM research_bar_versions WHERE market_hash_name=? AND platform='YOUPIN' AND period='1h' AND style='' AND source_request<=? AND bucket_time<? ORDER BY version_id", (name, cap, cutoff))]
        requests = [dict(row) for row in db.execute("SELECT * FROM requests WHERE request_id<=? ORDER BY request_id", (cap,))]
        db.rollback()
    if _state(database) != before:
        raise ValueError("Source changed during read-only snapshot")
    return {"source": source, "database": database, "state": before, "items": items, "versions": versions,
            "requests": requests, "cap": cap, "cutoff": cutoff, "report_path": report_path,
            "report_bytes": report_bytes, "registry_bytes": registry_bytes, "pointer_bytes": pointer_bytes}


def build(workspace="research_20261016_v1", output_id=None, spec_path=DEFAULT_SPEC):
    """Create one immutable research-cleaning version, without network or training."""
    spec_path = Path(spec_path).resolve()
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes.decode("utf-8-sig"))
    if spec != EXPECTED_SPEC:
        raise ValueError("Cleaning spec differs from the frozen 1.0 protocol")
    inputs = _load(workspace)
    created = datetime.now(CHINA)
    output_id = output_id or "seven_clean_" + created.strftime("%Y%m%dT%H%M%S%z_") + uuid.uuid4().hex[:8]
    if not isinstance(output_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_+\-]{0,95}", output_id):
        raise ValueError("Invalid output id")
    if output_id.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
        raise ValueError("Reserved output id")
    output = _inside(BASE / output_id, BASE)
    if output.exists():
        raise FileExistsError("Cleaning version exists; use a new output id")
    code = {name: (ROOT / name).read_bytes() for name in CODE_FILES}
    methods_path = ROOT / "docs/research/DATA_METHODS_20261019.md"
    methods = methods_path.read_bytes()
    output.mkdir(parents=True, exist_ok=False)
    (output / "source").mkdir()
    (output / "source/spec.json").write_bytes(spec_bytes)
    (output / "source/source_report.json").write_bytes(inputs["report_bytes"])
    (output / "source/source_latest_report.json").write_bytes(inputs["pointer_bytes"])
    (output / "source/source_registry.json").write_bytes(inputs["registry_bytes"])
    (output / "source/methods.md").write_bytes(methods)
    for name, raw in code.items():
        path = output / "source/code" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    _dump(output / "protocol_locked.json", {"version": VERSION, "locked_at": created.isoformat(),
          "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(), "source_request_cap": inputs["cap"],
          "source_cutoff_exclusive": inputs["cutoff"], "all_extreme_moves_retained": True})
    summary, gaps, events, quarantine = [], [], [], []
    try:
        with closing(sqlite3.connect(output / "clean.sqlite")) as db:
            db.execute("PRAGMA foreign_keys=ON")
            all_versions = [row for rows in inputs["versions"].values() for row in rows]
            if not all_versions:
                raise ValueError("No saved source versions")
            _table(db, "source_versions", all_versions, SOURCE_FIELDS)
            db.execute("CREATE UNIQUE INDEX source_version_id ON source_versions(version_id)")
            _table(db, "source_requests", inputs["requests"])
            _table(db, "items", inputs["items"])
            initialized = False
            for item in inputs["items"]:
                rows = clean_rows(inputs["versions"][item["market_hash_name"]], item, item["start_time"], inputs["cutoff"], spec)
                windows = quality_windows(rows, item["start_time"], inputs["cutoff"], spec)
                if not initialized:
                    _table(db, "hourly", rows)
                    _table(db, "input_quality_windows", windows,
                           keys=list(windows[0]) if windows else ["market_hash_name", "decision_time", "decision_at_beijing", "expected_hours", "valid_price_hours", "missing_or_invalid_price_hours", "price_coverage", "recent_complete", "strict_input_complete", "input_quality_pass"])
                    initialized = True
                else:
                    _insert(db, "hourly", list(rows[0]), rows)
                    _insert(db, "input_quality_windows", [d[1] for d in db.execute("PRAGMA table_info(input_quality_windows)")], windows)
                counts = Counter()
                for row in rows:
                    counts.update(json.loads(row["quality_flags"]))
                    if row["observed"]:
                        if json.loads(row["quality_flags"]):
                            events.append({k: row[k] for k in ("market_hash_name", "bucket_time", "at_beijing", "close_cny", "source_version_id", "quality_flags")})
                        if any(flag.startswith("invalid_") for flag in json.loads(row["quality_flags"])):
                            quarantine.append({k: row[k] for k in ("market_hash_name", "bucket_time", "at_beijing", "source_version_id", "quality_flags")})
                item_gaps = gap_rows(rows)
                gaps.extend(item_gaps)
                summary.append({"market_hash_name": item["market_hash_name"], "name_zh": item["name_zh"],
                                "grid_hours": len(rows), "observed_hours": sum(r["observed"] for r in rows),
                                "valid_price_hours": sum(r["price_valid"] for r in rows),
                                "internal_missing_hours": sum(g["hours"] for g in item_gaps if g["kind"] == "internal_gap"),
                                "before_first_observation_hours": sum(g["hours"] for g in item_gaps if g["kind"] == "before_first_observation"),
                                "volume_missing_observed_hours": sum(r["volume_missing"] for r in rows if r["observed"]),
                                "turnover_missing_observed_hours": sum(r["turnover_missing"] for r in rows if r["observed"]),
                                "source_versions": len(inputs["versions"][item["market_hash_name"]]),
                                "strict_complete_input_windows": sum(w["strict_input_complete"] for w in windows),
                                "proposed_quality_pass_windows": sum(w["input_quality_pass"] for w in windows),
                                "quality_window_count": len(windows), "flags": dict(counts)})
            db.execute("CREATE UNIQUE INDEX hourly_identity ON hourly(market_hash_name,bucket_time)")
            db.execute("CREATE UNIQUE INDEX quality_window_identity ON input_quality_windows(market_hash_name,decision_time)")
            db.execute("CREATE VIEW valid_observed_prices AS SELECT * FROM hourly WHERE observed=1 AND price_valid=1")
            db.commit()
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Clean database integrity failed")
        _csv(output / "gaps.csv", gaps, ["market_hash_name", "kind", "start", "start_beijing", "end_exclusive", "hours", "end_beijing_exclusive"])
        _csv(output / "flagged_hours.csv", events, ["market_hash_name", "bucket_time", "at_beijing", "close_cny", "source_version_id", "quality_flags"])
        _csv(output / "quarantine.csv", quarantine, ["market_hash_name", "bucket_time", "at_beijing", "source_version_id", "quality_flags"])
        quality = {"version": VERSION, "items": summary, "item_count": len(summary),
                   "grid_hours": sum(s["grid_hours"] for s in summary), "observed_hours": sum(s["observed_hours"] for s in summary),
                   "valid_price_hours": sum(s["valid_price_hours"] for s in summary), "quarantined_observed_hours": len(quarantine),
                   "source_versions": sum(s["source_versions"] for s in summary), "flagged_observed_hours": len(events),
                   "prices_imputed": 0, "extreme_prices_deleted": 0, "flows_imputed": 0,
                   "input_quality_windows_are_not_training_eligibility": True, "new_predictive_features_built": False,
                   "new_labels_built": False, "historical_available_at_verified": False, "training_approved": False}
        _dump(output / "quality_report.json", quality)
        lines = ["# 七品小时清洗研究版", "", f"版本{VERSION}；生成{created.isoformat()}。",
                 "", "保留全部源版本与真实极端走势；缺失不补造，非法字段隔离，历史可得时间未验证。没有特征工程、标签生成或训练。", "",
                 "| 商品 | 来源小时 | 网格小时 | 内部缺小时 | 严格完整窗口 | 95%且最近24h完整窗口 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for s in summary:
            lines.append(f"| {s['name_zh']} | {s['observed_hours']} | {s['grid_hours']} | {s['internal_missing_hours']} | {s['strict_complete_input_windows']} | {s['proposed_quality_pass_windows']} |")
        lines.extend(["", f"来源版本{quality['source_versions']}；观察小时{quality['observed_hours']}；合法价格{quality['valid_price_hours']}；隔离观察小时{len(quarantine)}。",
                      "", "clean.sqlite保存source_versions、source_requests、items、hourly和input_quality_windows，价格精确文本、NULL与mask分开；不重复导出全部小时CSV。",
                      "flagged_hours.csv是质量/事件诊断，不是操盘认定；大幅涨跌未删除。gaps.csv分清首次观察前与内部缺口。",
                      "95%/24小时门槛和30%/MAD阈值是预设工程候选，非文献最优值、非已验证预测提升。质量窗口不含未来标签，不能视为正式训练批准。",
                      "旧Cyrex严格样本/预测入口仍读取原路径，未自动切换本清洗库；后续特征工程要显式接入新版本并使用新的前向留出。", ""])
        (output / "report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
        after = _state(inputs["database"])
        if (after != inputs["state"] or (inputs["source"] / "registry.json").read_bytes() != inputs["registry_bytes"]
                or inputs["report_path"].read_bytes() != inputs["report_bytes"] or spec_path.read_bytes() != spec_bytes
                or methods_path.read_bytes() != methods or any((ROOT / n).read_bytes() != b for n, b in code.items())):
            raise ValueError("Source/code/spec changed during cleaning; result not finalized")
        manifest = {"version": VERSION, "status": "frozen_research_cleaning_candidate", "output_id": output_id,
                    "output_dir": str(output), "created_at_beijing": created.isoformat(), "workspace": workspace,
                    "source_database": str(inputs["database"]), "source_database_before": inputs["state"],
                    "source_database_after": after, "source_database_unchanged": True, "source_request_cap": inputs["cap"],
                    "source_cutoff_exclusive": inputs["cutoff"], "source_cutoff_beijing": _iso(inputs["cutoff"]),
                    "spec": spec, "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
                    "code_files": {n: hashlib.sha256(b).hexdigest() for n, b in code.items()},
                    "methods_sha256": hashlib.sha256(methods).hexdigest(), "summary": quality,
                    "database": "clean.sqlite", "report": "report.md", "network_requests": 0,
                    "historical_available_at_verified": False, "training_approved": False,
                    "outputs": {p.relative_to(output).as_posix(): {"bytes": p.stat().st_size, "sha256": _sha(p)}
                                for p in sorted(output.rglob("*")) if p.is_file()}}
        _dump(output / "manifest.json", manifest)
        temporary = BASE / ("latest." + uuid.uuid4().hex + ".tmp")
        _dump(temporary, {"output_id": output_id, "manifest": output_id + "/manifest.json"})
        temporary.replace(BASE / "latest.json")
        return manifest
    except Exception as error:
        _dump(output / "cleaning_error.json", {"status": "not_finalized", "reason": str(error)})
        raise


def status():
    pointer = BASE / "latest.json"
    if not pointer.exists():
        return {"version": VERSION, "status": "no_cleaning"}
    value = json.loads(pointer.read_text(encoding="utf-8-sig"))
    path = _inside(BASE / value["manifest"], BASE)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("build", help="Create one offline immutable cleaning version")
    run.add_argument("--workspace", default="research_20261016_v1")
    run.add_argument("--output-id")
    commands.add_parser("status", help="Read the latest saved cleaning manifest")
    args = parser.parse_args()
    try:
        result = build(args.workspace, args.output_id) if args.command == "build" else status()
        print(json.dumps({k: v for k, v in result.items() if k != "outputs"}, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        print(json.dumps({"version": VERSION, "status": "stopped", "reason": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
