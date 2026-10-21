"""Explicit, local-only research fitting and reload-only evaluation of frozen samples."""
from __future__ import annotations

import csv
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import re
import shutil
import uuid

import numpy as np

from scripts.research.data.training_data import load_dataset, build_sequences, prediction_rows
from scripts.research.data.model_preprocessing import TrainOnlyPreprocessor

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "data/local/artifacts/seven_training"
REPORTS = ROOT / "data/local/reports/seven_training"
SPEC_PATH = ROOT / "scripts/config/seven_training_spec.json"
VERSION = "seven-training-1.1"
CLASSICAL = ("persistence", "ridge", "auto_arima", "lightgbm")
NEURAL = ("dlinear", "lstm", "transformer", "gated_lstm_transformer")
CODE_FILES = (
    "scripts/train_seven_models.py", "scripts/config/seven_training_spec.json",
    "scripts/research/__init__.py", "scripts/research/data/__init__.py",
    "scripts/research/data/training_data.py", "scripts/research/data/model_preprocessing.py",
    "scripts/research/data/seven_samples.py", "scripts/research/data/clean_hourly.py",
    "scripts/research/models/__init__.py", "scripts/research/models/classical.py",
    "scripts/research/models/neural.py", "scripts/research/evaluation/__init__.py",
    "scripts/research/evaluation/seven_training.py",
)


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value):
        raise ValueError("Invalid artifact id")
    if value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
        raise ValueError("Reserved artifact id")
    return value


def _path(base, artifact_id):
    path = (base / _id(artifact_id)).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError("Artifact escapes root")
    return path


def _new(base, artifact_id, prefix):
    artifact_id = artifact_id or f"{prefix}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:6]}"
    path = _path(base, artifact_id)
    path.mkdir(parents=True, exist_ok=False)
    return path


def _outputs(path):
    return [{"path": p.relative_to(path).as_posix(), "bytes": p.stat().st_size, "sha256": _sha(p)}
            for p in sorted(path.rglob("*")) if p.is_file() and p.name != "manifest.json"]


def verify(base, artifact_id, kind=None):
    path = _path(base, artifact_id)
    manifest = _read(path / "manifest.json")
    if manifest.get("artifact_id") != artifact_id or (kind and manifest.get("kind") != kind):
        raise ValueError("Manifest identity mismatch")
    if not manifest.get("outputs"):
        raise ValueError("Missing artifact output inventory")
    seen = set()
    for entry in manifest["outputs"]:
        target = (path / entry["path"]).resolve()
        if not target.is_relative_to(path) or entry["path"] in seen:
            raise ValueError("Unsafe or duplicate manifest output")
        seen.add(entry["path"])
        if not target.is_file() or target.stat().st_size != entry["bytes"] or _sha(target) != entry["sha256"]:
            raise ValueError(f"Artifact hash mismatch: {entry['path']}")
    actual = {p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if actual != seen:
        raise ValueError("Artifact file inventory mismatch")
    return path, manifest


def _snapshot(path):
    for relative in CODE_FILES:
        target = path / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)


def _check_runtime_code(path):
    for relative in CODE_FILES:
        if relative.endswith(".py") and _sha(ROOT / relative) != _sha(path / "source" / relative):
            raise ValueError(f"Runtime source differs from frozen artifact: {relative}; use the saved compatible Git version")


def environment():
    result = {"python": platform.python_version(), "packages": {}}
    for name in ("numpy", "scikit-learn", "statsmodels", "lightgbm", "torch", "matplotlib"):
        try:
            result["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][name] = None
    try:
        import torch
        result.update(cuda_available=torch.cuda.is_available(), cuda_runtime=torch.version.cuda,
                      gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
    except (ImportError, OSError, RuntimeError) as error:
        result.update(cuda_available=False, cuda_runtime=None, gpu=None, torch_error=type(error).__name__)
    return result


def prepare(dataset_id="seven_daily_20261020_v1", prepared_id=None, profile="quality"):
    """Fit ONLY preprocessing on training rows; never fit a prediction model."""
    bundle = load_dataset(dataset_id, profile=profile)
    training = bundle["splits"]["train"]
    seq = build_sequences(training, bundle["hourly_by_item"])
    preprocessor = TrainOnlyPreprocessor().fit_rows(training, bundle["feature_fields"], sequences=seq,
                                                eligibility_field=bundle["provenance"]["eligibility_field"])
    path = _new(BASE / "prepared", prepared_id, "prep")
    preprocessor.save(path / "preprocessor.json")
    _dump(path / "protocol.json", _read(SPEC_PATH))
    _snapshot(path)
    manifest = {"version": VERSION, "kind": "prepared", "artifact_id": path.name,
                "dataset_id": dataset_id, "profile": profile, "provenance": bundle["provenance"],
                "split_counts": {k: len(v) for k, v in bundle["splits"].items()},
                "purpose": "user_authorized_retrospective_research_fit_not_execution",
                "outputs": _outputs(path)}
    _dump(path / "manifest.json", manifest)
    return manifest


def _load_prepared(prepared_id):
    path, manifest = verify(BASE / "prepared", prepared_id, "prepared")
    _check_runtime_code(path)
    bundle = load_dataset(manifest["dataset_id"], profile=manifest["profile"])
    if bundle["provenance"] != manifest["provenance"]:
        raise ValueError("Frozen input provenance differs from prepared artifact")
    return path, manifest, bundle, TrainOnlyPreprocessor.load(path / "preprocessor.json")


def _arrays(rows, bundle, preprocessor):
    sequence = build_sequences(rows, bundle["hourly_by_item"])
    values = preprocessor.transform_rows(prediction_rows(rows), sequences=sequence, mode="scaled")
    # Targets are appended explicitly only for fitting. They are never passed to transform.
    return {"sequence": values["x_sequence"], "tabular": values["x_tabular"],
            "target": np.asarray([r["y_return_7d"] for r in rows], dtype=np.float32)}


def _predict(name, model_dir, rows, bundle, preprocessor, device="auto"):
    inputs = prediction_rows(rows)
    if name in CLASSICAL:
        from scripts.research.models.classical import predict_model
        predictions = predict_model(model_dir / "model.json", inputs, preprocessor, bundle["hourly_by_item"])
    else:
        from scripts.research.models.neural import predict_neural
        values = preprocessor.transform_rows(inputs, sequences=build_sequences(inputs, bundle["hourly_by_item"]), mode="scaled")
        predictions = predict_neural(model_dir, {"sequence": values["x_sequence"], "tabular": values["x_tabular"]}, device=device)
    predictions = np.asarray(predictions, dtype=float)
    if predictions.shape != (len(rows),) or not np.isfinite(predictions).all():
        raise ValueError("Prediction shape/nonfinite failure; no automatic fallback")
    return predictions


def metrics(rows, predictions):
    if not rows:
        raise ValueError("Empty evaluation split")
    pred = np.asarray(predictions, dtype=float)
    actual = np.asarray([float(r["y_return_7d"]) for r in rows])
    reference = np.asarray([float(r["reference_close_cny"]) for r in rows])
    true_price = np.asarray([float(r["y_reference_close_7d"]) for r in rows])
    pred_price = reference * (1 + pred)
    residual = pred_price - true_price
    return {"n": len(rows), "return_mae": float(np.mean(np.abs(pred - actual))),
            "price_mae_cny": float(np.mean(np.abs(residual))),
            "price_rmse_cny": float(np.sqrt(np.mean(residual ** 2))),
            "price_mape_percent": float(100 * np.mean(np.abs(residual) / true_price)),
            "price_bias_cny": float(np.mean(residual)),
            "direction_accuracy": float(np.mean(np.sign(pred) == np.sign(actual))),
            "invalid_nonpositive_price_count": int(np.sum(pred_price <= 0))}


def train(prepared_id, model_names=CLASSICAL, experiment_id=None, device="auto", overrides=None):
    """Explicit bounded set of fits. Test rows are never transformed or scored here."""
    names = list(model_names)
    if not names or len(set(names)) != len(names) or any(n not in CLASSICAL + NEURAL for n in names):
        raise ValueError("Unknown, empty or duplicate model list")
    prepared_path, prepared, bundle, preprocessor = _load_prepared(prepared_id)
    protocol = _read(prepared_path / "protocol.json")
    if overrides and any(k not in names for k in overrides):
        raise ValueError("Overrides contain unrequested model")
    path = _new(BASE / "experiments", experiment_id, "fit")
    _snapshot(path)
    shutil.copyfile(prepared_path / "preprocessor.json", path / "preprocessor.json")
    _dump(path / "protocol.json", protocol)
    _dump(path / "environment.json", environment())
    training, validation = bundle["splits"]["train"], bundle["splits"]["validation"]
    results = {}
    neural_arrays = None
    for name in names:
        config = dict(protocol["model_configs"][name])
        config.update((overrides or {}).get(name, {}))
        print(f"[training] {name}: starting; output={path / name}", flush=True)
        try:
            if name in CLASSICAL:
                from scripts.research.models.classical import fit_model
                fit_model(name, training, validation, preprocessor, bundle["hourly_by_item"], config, path / name)
            else:
                from scripts.research.models.neural import fit_neural
                if neural_arrays is None:
                    neural_arrays = (_arrays(training, bundle, preprocessor), _arrays(validation, bundle, preprocessor))
                fit_neural(name, *neural_arrays, config, path / name, device=device)
            pred = _predict(name, path / name, validation, bundle, preprocessor, device)
            results[name] = {"status": "complete", "validation": metrics(validation, pred), "config": config}
            print(f"[training] {name}: saved; validation return MAE={results[name]['validation']['return_mae']:.6g}", flush=True)
        except (KeyboardInterrupt, SystemExit):
            results[name] = {"status": "interrupted", "config": config}
            _dump(path / "progress.json", results)
            raise
        except Exception as error:
            results[name] = {"status": "failed", "error_type": type(error).__name__, "error": str(error), "config": config}
            print(f"[training] {name}: failed ({type(error).__name__}): {error}", flush=True)
        _dump(path / "progress.json", results)
    completed = [n for n in names if results[n]["status"] == "complete"]
    selected = min(completed, key=lambda n: results[n]["validation"]["return_mae"]) if completed else None
    status = "complete" if len(completed) == len(names) else "partial" if completed else "failed"
    manifest = {"version": VERSION, "kind": "experiment", "artifact_id": path.name, "status": status,
                "prepared_id": prepared_id, "prepared_manifest_sha256": _sha(prepared_path / "manifest.json"),
                "dataset_id": prepared["dataset_id"], "profile": prepared["profile"], "provenance": prepared["provenance"],
                "split_counts": prepared["split_counts"], "models": results, "selected_model": selected,
                "selection_metric": "validation_return_mae", "test_evaluated": False,
                "interpretation": "retrospective_source_price_research_not_profit_or_PIT_verification",
                "outputs": _outputs(path)}
    _dump(path / "manifest.json", manifest)
    if status == "complete":
        _dump(BASE / "latest.json", {"experiment_id": path.name})
    return manifest


def _write_predictions(path, rows, pred):
    columns = ("market_hash_name", "decision_time", "target_time", "split", "reference_close_cny",
               "actual_price_cny", "predicted_price_cny", "actual_return", "predicted_return")
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row, value in zip(rows, pred):
            writer.writerow(dict(zip(columns, (row["market_hash_name"], row["decision_time"], row["target_time"], row["split"],
                                               row["reference_close_cny"], row["y_reference_close_7d"],
                                               float(row["reference_close_cny"]) * (1 + float(value)),
                                               row["y_return_7d"], float(value)))))


def _plots(path, rows, predictions, selected):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plot_paths = []
    for i, item in enumerate(sorted({r["market_hash_name"] for r in rows})):
        indices = sorted((j for j, r in enumerate(rows) if r["market_hash_name"] == item), key=lambda j: rows[j]["target_time"])
        xx, yy, pp, baseline = [], [], [], []
        last = None
        for j in indices:
            row = rows[j]
            when = datetime.fromtimestamp(row["target_time"], timezone(timedelta(hours=8)))
            if last is not None and (when - last).total_seconds() > 86400:
                xx.append(last + timedelta(days=1)); yy.append(np.nan); pp.append(np.nan); baseline.append(np.nan)
            xx.append(when); yy.append(float(row["y_reference_close_7d"])); baseline.append(float(row["reference_close_cny"]))
            pp.append(float(row["reference_close_cny"]) * (1 + float(predictions[selected][j])))
            last = when
        fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
        axes[0].plot(xx, yy, label="Observed target reference", color="#253858")
        axes[0].plot(xx, pp, label=f"Predicted +7d: {selected}", linestyle="--")
        axes[0].plot(xx, baseline, label="Persistence", linestyle=":", alpha=.75)
        axes[0].set(title=item, ylabel="Source price / CNY")
        axes[0].legend(); axes[0].grid(alpha=.2)
        axes[1].plot(xx, np.asarray(pp) - np.asarray(yy), color="#386cb0")
        axes[1].axhline(0, color="gray", linewidth=.8); axes[1].grid(alpha=.2)
        axes[1].set(ylabel="Error / CNY", xlabel="Target time (Beijing); forecast issued 7 days earlier; gaps remain")
        fig.autofmt_xdate(); fig.tight_layout()
        output = path / f"item_{i + 1}.png"
        fig.savefig(output, dpi=130); plt.close(fig)
        plot_paths.append({"item": item, "path": output.name})
    return plot_paths


def evaluate(experiment_id, split="validation", report_id=None, device="auto", allow_exploratory_test=False):
    """Reload checkpoints/scaler. This path contains no fitting or normalization updates."""
    if split not in ("validation", "test_exploratory"):
        raise ValueError("Only validation or explicit exploratory test supported")
    if split == "test_exploratory" and not allow_exploratory_test:
        raise ValueError("Old test was already viewed; explicit exploratory permission required")
    experiment_path, experiment = verify(BASE / "experiments", experiment_id, "experiment")
    if experiment["status"] != "complete" or not experiment["selected_model"]:
        failed = [f"{name} ({entry['status']}: {entry.get('error_type', 'unknown')})"
                  for name, entry in experiment["models"].items() if entry["status"] != "complete"]
        raise ValueError("Incomplete experiment: " + ", ".join(failed) +
                         ". Inspect progress.json; keep the saved files and run the corrected v1.1 Notebook with a new experiment ID.")
    _check_runtime_code(experiment_path)
    prepared_path, _, bundle, preprocessor = _load_prepared(experiment["prepared_id"])
    if _sha(prepared_path / "manifest.json") != experiment["prepared_manifest_sha256"]:
        raise ValueError("Prepared manifest changed")
    if _sha(experiment_path / "preprocessor.json") != _sha(prepared_path / "preprocessor.json"):
        raise ValueError("Training preprocessor differs")
    rows = bundle["splits"][split]
    selected = experiment["selected_model"]
    names = list(experiment["models"]) if split == "validation" else list(dict.fromkeys([selected, "persistence"]))
    predictions = {}
    for name in names:
        predictions[name] = (np.zeros(len(rows)) if name == "persistence" else
                             _predict(name, experiment_path / name, rows, bundle, preprocessor, device))
    path = _new(REPORTS, report_id, "eval")
    scores, per_item = {}, {}
    for name in names:
        scores[name] = metrics(rows, predictions[name])
        _write_predictions(path / f"{name}_predictions.csv", rows, predictions[name])
        per_item[name] = {}
        for item in sorted({r["market_hash_name"] for r in rows}):
            idx = [i for i, r in enumerate(rows) if r["market_hash_name"] == item]
            per_item[name][item] = metrics([rows[i] for i in idx], predictions[name][idx])
    _dump(path / "scores.json", {"overall": scores, "per_item": per_item})
    charts = _plots(path, rows, predictions, selected)
    text = (f"# Seven-item reload evaluation\n\nExperiment: `{experiment_id}`; split: `{split}`.\n\n"
            f"Validation-selected model: `{selected}`. Selection metric: return MAE.\n\n"
            "| Model | N | Return MAE | Price MAE (CNY) | Price RMSE (CNY) |\n| --- | ---: | ---: | ---: | ---: |\n")
    for name, score in scores.items():
        text += f"| {name} | {score['n']} | {score['return_mae']:.6f} | {score['price_mae_cny']:.4f} | {score['price_rmse_cny']:.4f} |\n"
    text += ("\nSeven-day overlapping labels and correlated items are not independent trades. No profit estimate, "
             "uncertainty interval, new independent test, or verified historical availability is claimed. "
             "ARIMA uses price history; tabular/neural inputs include additional features.\n")
    (path / "report.md").write_text(text, encoding="utf-8")
    result = {"version": VERSION, "kind": "evaluation", "artifact_id": path.name,
              "experiment_id": experiment_id, "experiment_manifest_sha256": _sha(experiment_path / "manifest.json"),
              "split": split, "selected_model": selected, "scores": scores, "charts": charts,
              "fit_calls": 0, "outputs": _outputs(path)}
    _dump(path / "manifest.json", result)
    return result
