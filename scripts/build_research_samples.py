"""Offline, retrospective Cyrex daily sample candidates; no training or network."""
from __future__ import annotations

import argparse
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

ROOT = Path(__file__).resolve().parents[1]
SOURCE_BASE = ROOT / "data/local/staging/steamdt"
BASE = ROOT / "data/local/staging/research_samples"
DEFAULT_SPEC = ROOT / "scripts/config/cyrex_daily_spec.json"
VERSION = "cyrex-daily-samples-1.0"
CHINA = timezone(timedelta(hours=8))
HOUR = 3600
DAY = 24 * HOUR
NAME = "USP-S | Cyrex (Factory New)"
SOURCE_FIELDS = ["version_id", "market_hash_name", "platform", "period", "style",
                 "source_time", "bucket_time", "open_cny", "close_cny", "high_cny",
                 "low_cny", "source_volume", "source_turnover_cny", "source_request"]


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n", encoding="utf-8", newline="\n")


def _csv(path, rows, fields=None):
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _iso(timestamp):
    return datetime.fromtimestamp(timestamp, CHINA).isoformat()


def _timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        if result.utcoffset() != timedelta(hours=8):
            raise ValueError("Split boundary must explicitly use +08:00")
        if result.second or result.microsecond:
            raise ValueError("Split boundary must have whole minute precision")
        return int(result.timestamp())
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid Beijing split boundary") from error


def _validate_spec(spec):
    expected = {"version": "cyrex-daily-spec-1.0", "market_hash_name": NAME,
                "decision_time_beijing": "10:00", "lookback_days": 28,
                "horizon_days": 7, "return_lags_days": [1, 3, 7, 14],
                "ma_days": [7, 14, 28], "vol_days": [7, 14], "range_days": 7,
                "require_complete_feature_window": True,
                "require_complete_label_window": True,
                "historical_available_at_verified": False,
                "training_approved": False, "feature_profile": "price_only_v1"}
    if not isinstance(spec, dict) or any(spec.get(key) != value for key, value in expected.items()):
        raise ValueError("Specification differs from the frozen Cyrex v1 sample rules")
    validation = _timestamp(spec.get("validation_start_beijing"))
    test = _timestamp(spec.get("test_start_beijing"))
    if validation >= test:
        raise ValueError("Validation boundary must precede test boundary")
    for boundary in (validation, test):
        if datetime.fromtimestamp(boundary, CHINA).strftime("%H:%M") != "10:00":
            raise ValueError("Split boundaries must be at the decision hour")
    return validation, test


def predictive_features(spec):
    return ["x_reference_close", *[f"x_return_{n}d" for n in spec["return_lags_days"]],
            *[f"x_ma_ratio_{n}d" for n in spec["ma_days"]],
            *[f"x_vol_{n}d" for n in spec["vol_days"]],
            f"x_range_{spec['range_days']}d"]


def _number(value, *, positive=False, integer=False):
    try:
        if value is None or isinstance(value, bool):
            raise ValueError("Missing numeric value")
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or (positive and number == 0):
            raise ValueError("Invalid source numeric value")
        if integer and number != number.to_integral_value():
            raise ValueError("Source volume must be integral")
        return int(number) if integer else number
    except (InvalidOperation, TypeError) as error:
        raise ValueError("Invalid source numeric value") from error


def _hours(hour_rows, source_cutoff):
    if isinstance(source_cutoff, bool) or not isinstance(source_cutoff, int) or source_cutoff % HOUR:
        raise ValueError("Source cutoff must be an integer whole-hour epoch")
    hours = {}
    for row in hour_rows:
        bucket = row.get("bucket_time")
        if isinstance(bucket, bool) or not isinstance(bucket, int) or bucket % HOUR:
            raise ValueError("Source bucket_time must be an integer whole-hour epoch")
        if bucket >= source_cutoff:
            continue
        if bucket in hours:
            raise ValueError("Duplicate source hour; resolve source versions before building")
        values = {key: _number(row.get(key), positive=True)
                  for key in ("open_cny", "close_cny", "high_cny", "low_cny")}
        if not (values["low_cny"] <= min(values["open_cny"], values["close_cny"])
                <= max(values["open_cny"], values["close_cny"]) <= values["high_cny"]):
            raise ValueError("Source OHLC values are inconsistent")
        values["source_volume"] = (None if row.get("source_volume") is None
                                   else _number(row["source_volume"], integer=True))
        values["source_turnover_cny"] = (None if row.get("source_turnover_cny") is None
                                         else _number(row["source_turnover_cny"]))
        hours[bucket] = values
    return hours


def build_rows(hour_rows, spec, source_cutoff):
    """Return (daily samples, 28-row-per-sample sequences, quality summary).

    Time boundaries are epoch seconds. Each feature window is [t-28d,t), and
    each target window is [t,t+7d). Flow columns are auxiliary source fields.
    """
    validation_start, test_start = _validate_spec(spec)
    hours = _hours(hour_rows, source_cutoff)
    if not hours:
        raise ValueError("No usable source hours")
    lookback = spec["lookback_days"] * DAY
    horizon = spec["horizon_days"] * DAY
    first_possible = min(hours) + lookback
    first = datetime.fromtimestamp(first_possible, CHINA).replace(hour=10, minute=0, second=0, microsecond=0)
    if first.timestamp() < first_possible:
        first += timedelta(days=1)
    samples, sequences = [], []
    feature_names = predictive_features(spec)
    decision = int(first.timestamp())
    while decision <= source_cutoff:
        target = decision + horizon
        sample_id = "cyrex_" + datetime.fromtimestamp(decision, CHINA).strftime("%Y%m%dT%H%M%S%z")
        window = [hours.get(bucket) for bucket in range(decision - lookback, decision, HOUR)]
        feature_complete = all(row is not None for row in window)
        day_rows = []
        for index in range(spec["lookback_days"]):
            start = decision - lookback + index * DAY
            day_hours = window[index * 24:(index + 1) * 24]
            present = [row for row in day_hours if row is not None]
            complete = len(present) == 24
            volume_count = sum(row["source_volume"] is not None for row in present)
            turnover_count = sum(row["source_turnover_cny"] is not None for row in present)
            day_row = {"sample_id": sample_id, "sequence_index": index,
                       "period_start": start, "period_end": start + DAY,
                       "period_start_beijing": _iso(start), "period_end_beijing": _iso(start + DAY),
                       "observed_hours": len(present), "complete_hours": complete,
                       "known_volume_hours": volume_count, "known_turnover_hours": turnover_count,
                       "open_cny": float(present[0]["open_cny"]) if complete else None,
                       "close_cny": float(present[-1]["close_cny"]) if complete else None,
                       "high_cny": float(max(row["high_cny"] for row in present)) if complete else None,
                       "low_cny": float(min(row["low_cny"] for row in present)) if complete else None,
                       "source_volume": sum(row["source_volume"] for row in present)
                       if complete and volume_count == 24 else None,
                       "source_turnover_cny": float(sum(row["source_turnover_cny"] for row in present))
                       if complete and turnover_count == 24 else None,
                       "flow_role": "auxiliary_only", "derived_from": "steamdt_YOUPIN_1h"}
            day_rows.append(day_row)
        sequences.extend(day_rows)
        split = "train" if decision < validation_start else "validation" if decision < test_start else "test"
        purged = ((split == "train" and target >= validation_start)
                  or (split == "validation" and target >= test_start))
        sample = {"sample_id": sample_id, "market_hash_name": NAME,
                  "decision_time": decision, "decision_at_beijing": _iso(decision),
                  "feature_window_start": decision - lookback,
                  "feature_window_end_exclusive": decision,
                  "feature_observed_hours": sum(row is not None for row in window),
                  "feature_expected_hours": lookback // HOUR,
                  "target_time": target, "target_at_beijing": _iso(target),
                  "split": split, "purged": purged, "feature_complete": feature_complete,
                  **{name: None for name in feature_names}}
        reference_row = hours.get(decision - HOUR)
        reference = reference_row["close_cny"] if reference_row else None
        if feature_complete:
            sample["x_reference_close"] = float(reference)
            for n in spec["return_lags_days"]:
                sample[f"x_return_{n}d"] = float(reference / hours[decision - n * DAY - HOUR]["close_cny"] - 1)
            for n in spec["ma_days"]:
                closes = [Decimal(str(row["close_cny"])) for row in day_rows[-n:]]
                sample[f"x_ma_ratio_{n}d"] = float(reference / (sum(closes) / n) - 1)
            for n in spec["vol_days"]:
                closes = [row["close_cny"] for row in day_rows[-(n + 1):]]
                sample[f"x_vol_{n}d"] = statistics.pstdev(
                    math.log(right / left) for left, right in zip(closes, closes[1:]))
            recent = window[-spec["range_days"] * 24:]
            sample[f"x_range_{spec['range_days']}d"] = float(
                max(row["high_cny"] for row in recent) / min(row["low_cny"] for row in recent) - 1)
        future = [hours.get(bucket) for bucket in range(decision, target, HOUR)]
        future_observed = sum(row is not None for row in future)
        if target > source_cutoff:
            label_status = "pending_future"
        elif future_observed != horizon // HOUR:
            label_status = "future_gap"
        elif reference is None:
            label_status = "reference_gap"
        else:
            label_status = "ready"
        label_ready = label_status == "ready"
        sample.update({"future_observed_hours": future_observed,
                       "future_expected_hours": horizon // HOUR,
                       "label_status": label_status, "label_ready": label_ready,
                       "y_source_close_7d": float(future[-1]["close_cny"]) if label_ready else None,
                       "y_source_return_7d": float(future[-1]["close_cny"] / reference - 1) if label_ready else None,
                       "y_min_source_low_return_7d": float(min(row["low_cny"] for row in future) / reference - 1)
                       if label_ready else None,
                       "eligible": feature_complete and label_ready and not purged,
                       "historical_available_at_verified": False, "training_approved": False})
        samples.append(sample)
        decision += DAY
    split_counts = Counter(row["split"] for row in samples)
    eligible_counts = Counter(row["split"] for row in samples if row["eligible"])
    exclusions = Counter()
    for row in samples:
        if not row["feature_complete"]:
            exclusions["incomplete_feature_window"] += 1
        if not row["label_ready"]:
            exclusions[row["label_status"]] += 1
        if row["purged"]:
            exclusions["purged_split_boundary"] += 1
    summary = {"total_samples": len(samples), "sequence_rows": len(sequences),
               "source_hourly_rows": len(hours), "source_first_hour_beijing": _iso(min(hours)),
               "source_last_hour_beijing": _iso(max(hours)), "source_cutoff_exclusive": source_cutoff,
               "source_cutoff_beijing": _iso(source_cutoff),
               "first_decision_beijing": samples[0]["decision_at_beijing"] if samples else None,
               "last_decision_beijing": samples[-1]["decision_at_beijing"] if samples else None,
               "feature_complete": sum(row["feature_complete"] for row in samples),
               "label_ready": sum(row["label_ready"] for row in samples),
               "pending_future": sum(row["label_status"] == "pending_future" for row in samples),
               "future_gap": sum(row["label_status"] == "future_gap" for row in samples),
               "reference_gap": sum(row["label_status"] == "reference_gap" for row in samples),
               "purged": sum(row["purged"] for row in samples),
               "eligible_by_split": {name: eligible_counts[name] for name in ("train", "validation", "test")},
               "samples_by_split": {name: split_counts[name] for name in ("train", "validation", "test")},
               "exclusion_reason_counts_overlapping": dict(sorted(exclusions.items())),
               "predictive_features": feature_names,
               "flow_predictive_features": [], "historical_available_at_verified": False,
               "training_approved": False}
    return samples, sequences, summary


def _workspace(name):
    if not isinstance(name, str) or not re.fullmatch(r"research_[A-Za-z0-9_]{1,70}", name) or name == "research_control":
        raise ValueError("Invalid research workspace name")
    return SOURCE_BASE / name


def _source_state(database):
    return {part.name: {"bytes": part.stat().st_size, "sha256": _sha(part)}
            for part in (database, Path(str(database) + "-wal")) if part.exists()}


def _contained(path, root):
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("Referenced path escapes its source workspace")
    return resolved


def _report_text(manifest):
    summary = manifest["summary"]
    lines = ["# 次时代崭新：日级回顾研究样本候选", "", f"组件：{VERSION}；构建：{manifest['created_at_beijing']}。",
             "", "仅离线整理来源价格，不训练、不联网，也不估算可执行净利润。历史修订及当时可得时间未知，不能称为已通过无泄露验收的正式训练集。",
             "", f"固定来源请求上限：{manifest['source_request_cap']}；来源截止：{summary['source_cutoff_beijing']}（不含此小时）。",
             f"精确小时快照：{summary['source_hourly_rows']}行；日级候选：{summary['total_samples']}行；序列：{summary['sequence_rows']}行。",
             f"过去窗口完整：{summary['feature_complete']}；未来标签完整：{summary['label_ready']}；等待未来：{summary['pending_future']}；成熟未来缺口：{summary['future_gap']}。",
             f"边界清除：{summary['purged']}；按规则可用候选：{summary['eligible_by_split']}。可用候选仍不等于训练批准。", "",
             "每天北京时间10:00，输入严格取此前28天672小时；28个日段均从10:00到下一日10:00。缺小时的日段OHLC全部留空；量额任一未知不补零。",
             "预测输入仅含过去价格特征；量额仅辅助保留。y字段和未来覆盖字段禁止进入预测输入。目标为+168小时之前最后一个完成小时的来源收盘；未来七天最低来源low仅为风险参考。",
             "", "## 固定时间划分", "",
             f"- train：决策时刻早于 {manifest['spec']['validation_start_beijing']}。",
             f"- validation：此后至 {manifest['spec']['test_start_beijing']} 之前。",
             "- test：此后；不随机划分。train/validation标签达到下一段边界即purged，保留行但不纳入该段可用候选。", "",
             "## 文件", "", "source_hourly.csv是请求上限内逐小时最新版本的精确来源值；samples.csv是候选与排除状态；sequence.csv为每候选28行过去日段；quality_report.json登记排除计数。",
             "source/保存本次脚本、配置、来源报告的准确字节。manifest.json记录输入输出哈希与请求上限；manifest自身不做循环自哈希。",
             "", "原研究库以mode=ro事务快照读取，读取前后主文件及已有WAL字节哈希必须一致。候选另存，不回写原库。", ""]
    return "\n".join(lines)


def build(workspace="research_20261016_v1", output_id=None, spec_path=DEFAULT_SPEC):
    """Build one immutable private candidate directory; return its manifest."""
    source_dir = _contained(_workspace(workspace), SOURCE_BASE)
    database = source_dir / "research.sqlite"
    pointer_path = source_dir / "latest_report.json"
    pointer_bytes = pointer_path.read_bytes()
    pointer = json.loads(pointer_bytes.decode("utf-8-sig"))
    report_path = _contained(source_dir / pointer["report"].replace("\\", "/"), source_dir)
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes.decode("utf-8-sig"))
    cap = report.get("workspace_http_attempts_archived")
    cutoff = report.get("run", {}).get("end_exclusive")
    if type(cap) is not int or cap <= 0 or type(cutoff) is not int or cutoff % HOUR:
        raise ValueError("Source report lacks a valid request cap or whole-hour cutoff")
    if report.get("integrity") != "ok" or report.get("run", {}).get("status") != "completed":
        raise ValueError("Use an integrity-checked completed source report")
    script_path = Path(__file__).resolve()
    script_bytes = script_path.read_bytes()
    spec_path = Path(spec_path).resolve()
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes.decode("utf-8-sig"))
    _validate_spec(spec)
    evidence_path = source_dir / "manual_cyrex_20261019_v1/evidence.json"
    evidence_bytes = evidence_path.read_bytes() if evidence_path.is_file() else None
    created = datetime.now(CHINA)
    output_id = output_id or "cyrex_" + created.strftime("%Y%m%dT%H%M%S%z_") + uuid.uuid4().hex[:8]
    if not isinstance(output_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_+\-]{0,95}", output_id):
        raise ValueError("Invalid output_id")
    if output_id.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{n}" for n in range(1, 10)],
                             *[f"LPT{n}" for n in range(1, 10)]}:
        raise ValueError("Reserved Windows output_id")
    output = _contained(BASE / output_id, BASE)
    if output.exists():
        raise FileExistsError("Output already exists; use a new output_id")
    before = _source_state(database)
    if database.name not in before:
        raise ValueError("Source database is missing")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        request_count = connection.execute("SELECT count(*) FROM requests WHERE request_id<=?", (cap,)).fetchone()[0]
        if integrity != "ok" or request_count != cap:
            raise ValueError("Database integrity or source request-cap count mismatch")
        query = """SELECT """ + ",".join(SOURCE_FIELDS) + """ FROM (
            SELECT v.*,ROW_NUMBER() OVER(PARTITION BY bucket_time
                ORDER BY source_request DESC,source_time DESC,version_id DESC) AS rn
            FROM research_bar_versions v WHERE platform='YOUPIN' AND period='1h'
                AND style='' AND market_hash_name=? AND source_request<=? AND bucket_time<?
            ) WHERE rn=1 ORDER BY bucket_time"""
        hourly = [dict(row) for row in connection.execute(query, (spec["market_hash_name"], cap, cutoff))]
        connection.rollback()
    if _source_state(database) != before:
        raise ValueError("Source database changed during snapshot; stop collection and rebuild with a new output_id")
    samples, sequence, summary = build_rows(hourly, spec, cutoff)
    output.mkdir(parents=True, exist_ok=False)
    source_output = output / "source"
    source_output.mkdir()
    try:
        (source_output / "build_research_samples.py").write_bytes(script_bytes)
        (source_output / "cyrex_daily_spec.json").write_bytes(spec_bytes)
        (source_output / "source_report.json").write_bytes(report_bytes)
        (source_output / "source_latest_report.json").write_bytes(pointer_bytes)
        if evidence_bytes is not None:
            (source_output / "attribute_assumption_evidence.json").write_bytes(evidence_bytes)
        _csv(output / "source_hourly.csv", hourly, SOURCE_FIELDS)
        _csv(output / "samples.csv", samples)
        _csv(output / "sequence.csv", sequence)
        manifest = {"version": VERSION, "output_id": output_id, "output_dir": str(output),
                    "status": "retrospective_research_candidate", "created_at_beijing": created.isoformat(),
                    "workspace": workspace, "source_database": str(database),
                    "source_database_files_before": before, "source_request_cap": cap,
                    "source_request_rows_at_or_below_cap": request_count,
                    "source_report": str(report_path),
                    "source_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
                    "code_sha256": hashlib.sha256(script_bytes).hexdigest(),
                    "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(), "spec": spec,
                    "summary": summary, "report": "report.md", "quality_report": "quality_report.json",
                    "attribute_assumption_evidence": None if evidence_bytes is None else {
                        "path": str(evidence_path), "sha256": hashlib.sha256(evidence_bytes).hexdigest()},
                    "csv_null_representation": "empty field; source style empty string is not a missing attribute",
                    "historical_available_at_verified": False, "training_approved": False,
                    "execution_profit_modelled": False,
                    "limitations": ["source revisions may contain information unavailable at historical decision times",
                                    "source close is not an executable matched bid or realized exit price",
                                    "overlapping seven-day labels are not independent trades",
                                    "daily historical bid/ask, costs and actual unlock status are unavailable"]}
        _dump(output / "quality_report.json", {"version": VERSION, "summary": summary,
                                                "predictive_features": summary["predictive_features"],
                                                "prohibited_predictors": ["y_*", "future_*", "target_*", "label_*", "eligible", "purged"],
                                                "spec": spec, "training_approved": False})
        (output / "report.md").write_text(_report_text(manifest), encoding="utf-8", newline="\n")
        after = _source_state(database)
        if after != before or report_path.read_bytes() != report_bytes or spec_path.read_bytes() != spec_bytes or script_path.read_bytes() != script_bytes:
            raise ValueError("Source database/report/code/spec changed during build; candidate not finalized")
        manifest["source_database_files_after"] = after
        manifest["source_database_unchanged"] = True
        manifest["outputs"] = {p.relative_to(output).as_posix(): {"bytes": p.stat().st_size, "sha256": _sha(p)}
                               for p in sorted(output.rglob("*")) if p.is_file()}
        _dump(output / "manifest.json", manifest)
        BASE.mkdir(parents=True, exist_ok=True)
        temporary = BASE / ("latest_cyrex." + uuid.uuid4().hex + ".tmp")
        _dump(temporary, {"output_id": output_id, "manifest": f"{output_id}/manifest.json"})
        temporary.replace(BASE / "latest_cyrex.json")
        return manifest
    except Exception as error:
        _dump(output / "build_error.json", {"version": VERSION, "status": "not_finalized",
                                             "reason": str(error), "training_approved": False})
        raise


def status():
    """Return the last saved candidate manifest, without opening the source DB."""
    pointer_path = BASE / "latest_cyrex.json"
    if not pointer_path.exists():
        return {"version": VERSION, "status": "no_build"}
    pointer = json.loads(pointer_path.read_text(encoding="utf-8-sig"))
    path = _contained(BASE / pointer["manifest"], BASE)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("build", help="Build an offline immutable retrospective candidate")
    run.add_argument("--workspace", default="research_20261016_v1")
    run.add_argument("--output-id")
    run.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    commands.add_parser("status", help="Read the latest saved candidate manifest")
    args = parser.parse_args()
    try:
        value = build(args.workspace, args.output_id, args.spec) if args.command == "build" else status()
        print(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        print(json.dumps({"version": VERSION, "status": "stopped", "reason": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
