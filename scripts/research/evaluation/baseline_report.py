"""Prespecified fixed rules, validation selection and locked retrospective test."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import uuid

from ..models.baselines import MODEL_ORDER, positive, predict_path

ROOT = Path(__file__).resolve().parents[3]
SAMPLE_BASE = ROOT / "data/local/staging/research_samples"
BASE = ROOT / "data/local/artifacts/baseline_evaluations"
DEFAULT_SPEC = ROOT / "scripts/config/cyrex_baseline_spec.json"
VERSION = "cyrex-baseline-evaluation-1.0"
CHINA = timezone(timedelta(hours=8))
DAY = 86400


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def _contained(path, root):
    result = path.resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes its designated root")
    return result


def _iso(timestamp):
    return datetime.fromtimestamp(timestamp, CHINA).isoformat()


def _csv_bytes(rows):
    if not rows:
        raise ValueError("Cannot save an empty prediction table")
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode("utf-8")


def _read_csv(raw):
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")))


def _validate_spec(spec):
    expected = {
        "version": "cyrex-fixed-baselines-1.0", "evaluation_scope": "exploratory_retrospective_evaluation",
        "market_hash_name": "USP-S | Cyrex (Factory New)", "horizon_days": 7,
        "models_in_tie_order": list(MODEL_ORDER),
        "forecast_formula": "persistence=P_t; log_drift_Ld=P_t*exp(log1p(x_return_Ld)/L*day)",
        "model_inputs": ["x_reference_close", "x_return_3d", "x_return_7d", "x_return_14d"],
        "selection_split": "validation", "selection_metric": "mae_cny",
        "test_policy": "lock_model_after_validation_then_report_selected_and_persistence_only",
        "fit_parameters": False, "historical_available_at_verified": False,
        "execution_profit_modelled": False,
        "label_overlap_policy": "overlapping_7d_labels_are_not_independent_trades"}
    if spec != expected:
        raise ValueError("Baseline specification differs from the prespecified fixed rules")


def load_candidate(candidate_id=None):
    """Read one frozen file snapshot, verify every SHA, then reconstruct samples.

    Source DB is deliberately not opened: the candidate contains its exact hourly
    snapshot. Before/after byte checks prevent mixing files during concurrent edits.
    """
    if candidate_id is None:
        pointer = json.loads((SAMPLE_BASE / "latest_cyrex.json").read_text(encoding="utf-8-sig"))
        manifest_path = _contained(SAMPLE_BASE / pointer["manifest"], SAMPLE_BASE)
    else:
        if not isinstance(candidate_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_+\-]{0,95}", candidate_id):
            raise ValueError("Invalid candidate_id")
        manifest_path = _contained(SAMPLE_BASE / candidate_id / "manifest.json", SAMPLE_BASE)
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest.decode("utf-8-sig"))
    if manifest.get("version") not in {"cyrex-daily-samples-1.0", "cyrex-daily-samples-1.1"}:
        raise ValueError("Unsupported sample candidate version")
    if manifest.get("status") != "retrospective_research_candidate" or manifest.get("training_approved") is not False:
        raise ValueError("Use a retrospective research candidate with its original approval status")
    directory = manifest_path.parent
    required = {"samples.csv", "sequence.csv", "source_hourly.csv", "source/cyrex_daily_spec.json"}
    outputs = manifest.get("outputs", {})
    if not required.issubset(outputs):
        raise ValueError("Candidate snapshot is missing required outputs")
    frozen = {}
    for relative, expected in outputs.items():
        path = _contained(directory / relative, directory)
        data = path.read_bytes()
        if type(expected.get("bytes")) is not int or expected["bytes"] != len(data) or expected.get("sha256") != _sha(data):
            raise ValueError("Candidate output SHA or byte-count mismatch: " + relative)
        frozen[relative] = data
    from ..data import daily_samples as builder
    source_spec_bytes = frozen["source/cyrex_daily_spec.json"]
    sample_spec = json.loads(source_spec_bytes.decode("utf-8-sig"))
    if sample_spec != manifest.get("spec") or _sha(source_spec_bytes) != manifest.get("spec_sha256"):
        raise ValueError("Candidate specification hash/content mismatch")
    builder._validate_spec(sample_spec)
    hours = _read_csv(frozen["source_hourly.csv"])
    integer_fields = {"version_id", "source_time", "bucket_time", "source_request"}
    for hour in hours:
        if set(hour) != set(builder.SOURCE_FIELDS):
            raise ValueError("Unexpected hourly schema")
        for key in integer_fields:
            hour[key] = int(hour[key])
        for key in ("source_volume", "source_turnover_cny"):
            if hour[key] == "":
                hour[key] = None
        if (hour["market_hash_name"] != sample_spec["market_hash_name"] or hour["platform"] != "YOUPIN"
                or hour["period"] != "1h" or hour["style"] != ""
                or not 0 < hour["source_request"] <= manifest["source_request_cap"]):
            raise ValueError("Hourly identity or source request bound mismatch")
    cutoff = manifest["summary"]["source_cutoff_exclusive"]
    samples, sequence, summary = builder.build_rows(hours, sample_spec, cutoff)
    if summary != manifest.get("summary"):
        raise ValueError("Reconstructed sample summary differs from manifest")
    for name, expected_rows in (("samples.csv", samples), ("sequence.csv", sequence)):
        saved = _read_csv(frozen[name])
        expected = [{key: "" if value is None else str(value) for key, value in row.items()}
                    for row in expected_rows]
        if saved != expected:
            raise ValueError("Reconstructed time, feature, label or eligibility mismatch: " + name)
    if manifest_path.read_bytes() != raw_manifest or any(
            (_contained(directory / relative, directory)).read_bytes() != data for relative, data in frozen.items()):
        raise ValueError("Candidate changed while reading; stop its writer and retry")
    return {"manifest": manifest, "manifest_bytes": raw_manifest, "manifest_path": manifest_path,
            "files": frozen, "samples": samples, "hours": hours, "summary": summary}


def prediction_rows(samples, model):
    rows = []
    for sample in samples:
        # Only an explicit x_ dict crosses the model boundary. Labels are read afterwards.
        features = {key: sample[key] for key in ("x_reference_close", "x_return_3d", "x_return_7d", "x_return_14d")}
        prediction = predict_path(features, model)[7]
        reference = positive(features["x_reference_close"])
        actual = positive(sample["y_source_close_7d"])
        rows.append({"sample_id": sample["sample_id"], "split": sample["split"],
                     "origin_time": sample["decision_time"], "target_time": sample["target_time"],
                     "target_at_beijing": sample["target_at_beijing"], "reference_price": reference,
                     "actual": actual, "prediction": prediction, "persistence_prediction": reference,
                     "selected_model": model})
    return rows


def metrics(rows):
    if not rows:
        raise ValueError("At least one eligible row is required for metrics")
    errors = [row["prediction"] - row["actual"] for row in rows]
    baseline_mae = sum(abs(row["persistence_prediction"] - row["actual"]) for row in rows) / len(rows)
    mae = sum(map(abs, errors)) / len(rows)
    return {"n": len(rows), "mae_cny": mae,
            "rmse_cny": math.sqrt(sum(error * error for error in errors) / len(rows)),
            "mape_percent": sum(abs(error) / row["actual"] for error, row in zip(errors, rows)) / len(rows) * 100,
            "return_error_mae_pp": sum(abs(error) / row["reference_price"] for error, row in zip(errors, rows)) / len(rows) * 100,
            "relative_mae_skill_vs_persistence": None if baseline_mae == 0 else 1 - mae / baseline_mae}


def select_on_validation(validation_samples):
    """Selection accepts validation rows only and cannot inspect test outcomes."""
    if not validation_samples or any(row["split"] != "validation" or not row["eligible"] for row in validation_samples):
        raise ValueError("Selection requires eligible validation rows only")
    predictions = {model: prediction_rows(validation_samples, model) for model in MODEL_ORDER}
    scores = {model: metrics(rows) for model, rows in predictions.items()}
    selected = min(MODEL_ORDER, key=lambda model: scores[model]["mae_cny"])
    return selected, scores, predictions


def _report(manifest, score):
    selected = manifest["selected_model"]
    lines = ["# 次时代固定规则：探索性回顾评估", "", f"版本：{VERSION}；生成：{manifest['generated_at_beijing']}。",
             "", "不拟合参数。先冻结四条规则，仅按validation七日价格MAE选择，再锁定评估test。",
             f"选择：**{selected}**；选择依据仅来自validation。目标是来源参考价，不是可执行退出价或利润。", "",
             "| 分段 | 规则 | n | MAE/元 | RMSE/元 | MAPE/% | 收益率误差/百分点 | 相对不变价MAE改善 |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for split in ("train", "validation", "test"):
        for model, values in score[split].items():
            skill = values["relative_mae_skill_vs_persistence"]
            lines.append(f"| {split} | {model} | {values['n']} | {values['mae_cny']:.4f} | {values['rmse_cny']:.4f} | {values['mape_percent']:.3f} | {values['return_error_mae_pp']:.3f} | {'未知' if skill is None else f'{skill:.3%}'} |")
    forecast = manifest["forecast"]
    lines.extend(["", "train仅描述，不参与拟合；相对改善为负表示比不变价更差。上述误差均不是交易收益。",
                  "", f"最新示例起点：{forecast['origin_at_beijing']}；目标：{forecast['target_at_beijing']}。",
                  f"起点参考价：{forecast['reference_price']:.4f}；七日规则预测：{forecast['prediction_7d']:.4f}元。",
                  f"候选构建于：{manifest['input_candidate']['created_at_beijing']}；来源批次完成：{manifest['input_candidate']['source_run_completed_at']}。",
                  "按固定10:00起点生成的回顾示例，不是当时已发出的实时预测；生成时刻另列，不掩盖数据较晚取得。",
                  "未来day 1..7只是同一固定规则的每日期望路径，不是目标价线性插值，也不制造小时波动。",
                  "", "## 限制", "", "- 历史available_at未知、可能含来源修订；不称PIT已验证。",
                  "- 每日七日标签重叠，不是独立交易；本次单商品分段不能支持可靠泛化结论。",
                  "- 未建立匹配盘口、费用、真实收货与解锁时间，不能据此直接输出买入或利润。",
                  "- 测试段已用于本次报告，后续反复据此调规则会使其失去独立留出含义。",
                  "", "forecast.csv为未来规则路径；test_predictions.csv按target_time对齐真实值与七日前预测；history.csv只含起点前28天小时来源收盘。", ""])
    return "\n".join(lines)


def evaluate(candidate_id=None, output_id=None, spec_path=DEFAULT_SPEC):
    """Write an immutable offline report. No DB writes, network, fitted models or orders."""
    spec_path = Path(spec_path).resolve()
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes.decode("utf-8-sig"))
    _validate_spec(spec)
    candidate = load_candidate(candidate_id)
    created = datetime.now(CHINA)
    output_id = output_id or "cyrex_baselines_" + created.strftime("%Y%m%dT%H%M%S%z_") + uuid.uuid4().hex[:8]
    if not isinstance(output_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_+\-]{0,95}", output_id):
        raise ValueError("Invalid output_id")
    if output_id.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{n}" for n in range(1, 10)], *[f"LPT{n}" for n in range(1, 10)]}:
        raise ValueError("Reserved Windows output_id")
    output = _contained(BASE / output_id, BASE)
    if output.exists():
        raise FileExistsError("Evaluation output exists; use a new version")
    source_files = [Path(__file__).resolve(), ROOT / "scripts/research/__init__.py",
                    ROOT / "scripts/research/data/__init__.py", ROOT / "scripts/research/models/__init__.py",
                    ROOT / "scripts/research/evaluation/__init__.py", ROOT / "scripts/research/models/baselines.py",
                    ROOT / "scripts/research/evaluation/costs.py", ROOT / "scripts/evaluate_research_baselines.py",
                    ROOT / "scripts/research/data/daily_samples.py"]
    code_bytes = {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in source_files}
    output.mkdir(parents=True, exist_ok=False)
    (output / "source").mkdir()
    (output / "source/cyrex_baseline_spec.json").write_bytes(spec_bytes)
    (output / "source/input_candidate_manifest.json").write_bytes(candidate["manifest_bytes"])
    for relative, data in code_bytes.items():
        path = output / "source" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    # Rules and exact implementation bytes have now been saved, before any score.
    _dump(output / "protocol_locked.json", {"locked_at_beijing": created.isoformat(), "spec_sha256": _sha(spec_bytes),
          "source_sha256": {name: _sha(data) for name, data in code_bytes.items()}, "selection_split": "validation"})
    try:
        samples = candidate["samples"]
        split_rows = {split: [row for row in samples if row["eligible"] and row["split"] == split]
                      for split in ("train", "validation", "test")}
        selected, validation_metrics, validation_predictions = select_on_validation(split_rows["validation"])
        selection = {"model": selected, "criterion": "validation_mae_cny", "tie_order": list(MODEL_ORDER),
                     "locked_at_beijing": datetime.now(CHINA).isoformat(), "test_used_for_selection": False}
        _dump(output / "selection_locked.json", selection)
        # Test labels enter prediction scoring only after saving the model choice.
        # Earlier snapshot reconstruction reads all labels solely for integrity checks.
        test_models = list(dict.fromkeys((selected, "persistence")))
        test_predictions = {model: prediction_rows(split_rows["test"], model) for model in test_models}
        score = {"version": VERSION, "scope": "exploratory_retrospective_evaluation", "selection": selection,
                 "train": {model: metrics(prediction_rows(split_rows["train"], model)) for model in MODEL_ORDER},
                 "validation": validation_metrics,
                 "test": {model: metrics(test_predictions[model]) for model in test_models},
                 "historical_available_at_verified": False, "execution_profit_modelled": False}
        origin_sample = max((row for row in samples if row["feature_complete"]), key=lambda row: row["decision_time"])
        origin = origin_sample["decision_time"]
        path = predict_path({key: origin_sample[key] for key in spec["model_inputs"]}, selected)
        cutoff = candidate["summary"]["source_cutoff_exclusive"]
        forecast_rows = [{"origin_time": origin, "target_time": origin + day * DAY,
                          "target_at_beijing": _iso(origin + day * DAY), "horizon_days": day,
                          "selected_model": selected, "prediction": price, "persistence_prediction": path[0],
                          "generated_at_beijing": created.isoformat(), "source_cutoff_exclusive": cutoff}
                         for day, price in enumerate(path)]
        history = [{"bucket_time": row["bucket_time"], "time_beijing": _iso(row["bucket_time"]),
                    "close_cny": row["close_cny"]} for row in candidate["hours"]
                   if origin - 28 * DAY <= row["bucket_time"] < origin]
        (output / "history.csv").write_bytes(_csv_bytes(history))
        (output / "forecast.csv").write_bytes(_csv_bytes(forecast_rows))
        validation_flat = [{**row, "model": model} for model, rows in validation_predictions.items() for row in rows]
        (output / "validation_predictions.csv").write_bytes(_csv_bytes(validation_flat))
        (output / "test_predictions.csv").write_bytes(_csv_bytes(test_predictions[selected]))
        _dump(output / "metrics.json", score)
        source_report = json.loads(candidate["files"]["source/source_report.json"].decode("utf-8-sig"))
        input_manifest = candidate["manifest"]
        manifest = {"version": VERSION, "status": "exploratory_retrospective_evaluation", "output_id": output_id,
                    "output_dir": str(output), "generated_at_beijing": created.isoformat(), "selected_model": selected,
                    "input_candidate": {"output_id": input_manifest["output_id"], "manifest": str(candidate["manifest_path"]),
                                        "manifest_sha256": _sha(candidate["manifest_bytes"]),
                                        "created_at_beijing": input_manifest["created_at_beijing"],
                                        "source_run_completed_at": source_report.get("run", {}).get("completed_at")},
                    "spec_sha256": _sha(spec_bytes), "source_sha256": {name: _sha(data) for name, data in code_bytes.items()},
                    "candidate_reconstructed_and_hash_verified": True, "source_database_opened": False,
                    "selected_model_locked_before_test": True,
                    "counts": {name: len(rows) for name, rows in split_rows.items()},
                    "forecast": {"origin_time": origin, "origin_at_beijing": _iso(origin),
                                 "target_time": origin + 7 * DAY, "target_at_beijing": _iso(origin + 7 * DAY),
                                 "reference_price": path[0], "prediction_7d": path[7],
                                 "origin_label_status": origin_sample["label_status"],
                                 "source_cutoff_exclusive": cutoff, "scope": "retrospective_fixed_origin_example"},
                    "files": {"history": "history.csv", "forecast": "forecast.csv", "test_predictions": "test_predictions.csv",
                              "validation_predictions": "validation_predictions.csv", "metrics": "metrics.json", "report": "report.md"},
                    "historical_available_at_verified": False, "fit_parameters": False,
                    "execution_profit_modelled": False, "training_approved": False}
        (output / "report.md").write_text(_report(manifest, score), encoding="utf-8", newline="\n")
        if spec_path.read_bytes() != spec_bytes or any((ROOT / name).read_bytes() != data for name, data in code_bytes.items()):
            raise ValueError("Specification or source changed during evaluation; artifact is not finalized")
        if candidate["manifest_path"].read_bytes() != candidate["manifest_bytes"]:
            raise ValueError("Candidate manifest changed during evaluation")
        manifest["outputs"] = {path.relative_to(output).as_posix(): {"bytes": path.stat().st_size, "sha256": _sha(path.read_bytes())}
                               for path in sorted(output.rglob("*")) if path.is_file()}
        _dump(output / "manifest.json", manifest)
        temporary = BASE / ("latest." + uuid.uuid4().hex + ".tmp")
        _dump(temporary, {"output_id": output_id, "manifest": f"{output_id}/manifest.json"})
        temporary.replace(BASE / "latest.json")
        return manifest
    except Exception as error:
        _dump(output / "evaluation_error.json", {"status": "not_finalized", "reason": str(error)})
        raise


def status():
    pointer_path = BASE / "latest.json"
    if not pointer_path.exists():
        return {"version": VERSION, "status": "no_evaluation"}
    pointer = json.loads(pointer_path.read_text(encoding="utf-8-sig"))
    manifest_path = _contained(BASE / pointer["manifest"], BASE)
    return json.loads(manifest_path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("evaluate", help="Offline fixed-rule evaluation; never fetches market data")
    run.add_argument("--candidate-id")
    run.add_argument("--output-id")
    commands.add_parser("status", help="Read the latest saved evaluation")
    args = parser.parse_args()
    try:
        value = evaluate(args.candidate_id, args.output_id) if args.command == "evaluate" else status()
        print(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"version": VERSION, "status": "stopped", "reason": str(error)}, ensure_ascii=False))
        return 2
