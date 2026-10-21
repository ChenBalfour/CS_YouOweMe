"""Train-only CPU models and portable, fit-free seven-day return inference.

Optional numerical packages are imported only inside the adapter that uses them.
``auto_arima`` is a bounded, train-only AIC search using statsmodels SARIMAX,
not pmdarima's unrestricted stepwise implementation.  Its coefficients are
frozen before validation: inference filters the past 672 hours without refits.
All models predict ``y_return_7d``; price conversion belongs to evaluation.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import warnings

VERSION = "classical-models-1.0"
MODEL_NAMES = ("persistence", "ridge", "auto_arima", "lightgbm")
HOUR = 3600
LOOKBACK_HOURS = 672
HORIZON_HOURS = 168
ARIMA_ORDERS = ((0, 1, 0), (1, 1, 0), (0, 1, 1), (1, 1, 1))


class ModelFitError(RuntimeError):
    """A model could not be fitted; no substitute forecast was produced."""


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _package_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _number(value, *, positive=False):
    if value is None or isinstance(value, bool):
        raise ValueError("A finite numeric value is required")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError("A finite positive value is required" if positive else "A finite value is required")
    return result


def _second(value):
    number = _number(value)
    if number != int(number) or number <= 0 or number % HOUR:
        raise ValueError("Timestamps must be positive integer UTC seconds on an hour boundary")
    return int(number)


def _reference(row):
    # Read an input field only, never any target or future eligibility field.
    return _number(row.get("x_reference_close", row.get("reference_close_cny")), positive=True)


def _rows(rows, expected_split=None, *, labels=False):
    result = [dict(row) for row in rows]
    if not result:
        raise ValueError("At least one sample is required")
    seen = set()
    for row in result:
        item = row.get("market_hash_name")
        if not isinstance(item, str) or not item:
            raise ValueError("Every sample requires an exact market_hash_name")
        decision = _second(row.get("decision_time"))
        if (item, decision) in seen:
            raise ValueError("Duplicate sample key")
        seen.add((item, decision))
        _reference(row)
        if expected_split is not None:
            if row.get("split") != expected_split or row.get("purged") != 0:
                raise ValueError(f"Fitting requires non-purged {expected_split} rows")
        if labels:
            if _number(row.get("y_return_7d")) <= -1:
                raise ValueError("Seven-day price return must exceed -1")
    return result


def _check_splits(train_rows, validation_rows):
    latest_train = max(_second(row["decision_time"]) for row in train_rows)
    earliest_validation = min(_second(row["decision_time"]) for row in validation_rows)
    if latest_train + HORIZON_HOURS * HOUR >= earliest_validation:
        raise ValueError("Training labels overlap validation; seven-day purge is required")
    return latest_train, earliest_validation


def _processor_digest(preprocessor):
    if not hasattr(preprocessor, "to_dict"):
        raise TypeError("A fitted train-only preprocessor with to_dict() is required")
    return _digest(preprocessor.to_dict())


def _matrix(preprocessor, rows, *, for_tree=False):
    import numpy as np

    matrix = np.asarray(preprocessor.transform_tabular(rows, for_tree=for_tree), dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != len(rows) or matrix.shape[1] == 0:
        raise ValueError("Preprocessor returned an invalid tabular shape")
    if np.isinf(matrix).any() or (not for_tree and not np.isfinite(matrix).all()):
        raise ValueError("Scaled model inputs must be finite; tree inputs may contain NaN only")
    return matrix


def _row_ids(rows):
    return _digest(sorted((row["market_hash_name"], _second(row["decision_time"])) for row in rows))


def _config(name, value):
    settings = dict(value or {})
    allowed = {
        "persistence": set(),
        "ridge": {"ridge_alphas"},
        "lightgbm": {"seed", "n_jobs", "n_estimators", "learning_rate", "early_stopping_rounds"},
        "auto_arima": {"arima_maxiter", "arima_max_train_hours", "arima_min_train_observed"},
    }[name]
    if set(settings) - allowed:
        raise ValueError(f"Unknown {name} settings: {sorted(set(settings) - allowed)}")
    if name == "ridge":
        alphas = settings.get("ridge_alphas", [0.1, 1.0, 10.0])
        if not isinstance(alphas, (tuple, list)) or not 1 <= len(alphas) <= 10:
            raise ValueError("ridge_alphas must contain one to ten fixed candidates")
        return {"ridge_alphas": [_number(alpha, positive=True) for alpha in alphas]}
    if name == "auto_arima":
        defaults = {"arima_maxiter": 50, "arima_max_train_hours": 8760, "arima_min_train_observed": 336}
        limits = {"arima_maxiter": (1, 200), "arima_max_train_hours": (672, 17520),
                  "arima_min_train_observed": (24, 17520)}
        for key, default in defaults.items():
            candidate = settings.get(key, default)
            if type(candidate) is not int or not limits[key][0] <= candidate <= limits[key][1]:
                raise ValueError(f"{key} outside fixed computational budget")
            defaults[key] = candidate
        if defaults["arima_min_train_observed"] > defaults["arima_max_train_hours"]:
            raise ValueError("ARIMA minimum observations exceed training budget")
        return defaults
    if name == "lightgbm":
        defaults = {"seed": 42, "n_jobs": 4, "n_estimators": 300,
                    "learning_rate": 0.03, "early_stopping_rounds": 30}
        defaults.update(settings)
        for key, lower, upper in (("seed", 0, 2**31 - 1), ("n_jobs", 1, 16),
                                  ("n_estimators", 1, 300), ("early_stopping_rounds", 1, 100)):
            if type(defaults[key]) is not int or not lower <= defaults[key] <= upper:
                raise ValueError(f"Invalid bounded {key}")
        defaults["learning_rate"] = _number(defaults["learning_rate"], positive=True)
        if defaults["learning_rate"] > 0.3:
            raise ValueError("learning_rate exceeds pilot budget")
        defaults.update(num_leaves=15, max_depth=4, min_child_samples=30)
        return defaults
    return {}


def _ridge(train_rows, validation_rows, preprocessor, config):
    import numpy as np
    from sklearn.linear_model import Ridge

    train = _matrix(preprocessor, train_rows)
    validation = _matrix(preprocessor, validation_rows)
    y_train = np.asarray([_number(row["y_return_7d"]) for row in train_rows])
    y_validation = np.asarray([_number(row["y_return_7d"]) for row in validation_rows])
    if len(train_rows) < 2:
        raise ValueError("Ridge requires at least two training samples")
    candidates, selected, best_mae = [], None, math.inf
    for alpha in config["ridge_alphas"]:
        fitted = Ridge(alpha=alpha, fit_intercept=True).fit(train, y_train)
        predictions = fitted.predict(validation)
        if not np.isfinite(predictions).all():
            raise ModelFitError("Ridge generated non-finite validation predictions")
        mae = float(np.mean(np.abs(predictions - y_validation)))
        candidates.append({"alpha": alpha, "validation_return_mae": mae})
        if mae < best_mae:
            selected, best_mae = fitted, mae
    parameters = {"alpha": float(selected.alpha), "coef": selected.coef_.tolist(),
                  "intercept": float(selected.intercept_),
                  "feature_names": list(preprocessor.feature_names(for_tree=False))}
    return parameters, {"selection": "lowest_validation_return_mae_first_candidate_breaks_ties",
                        "candidate_results": candidates, "selected_validation_return_mae": best_mae,
                        "packages": {"numpy": _package_version("numpy"), "scikit-learn": _package_version("scikit-learn")}}


def _lightgbm(train_rows, validation_rows, preprocessor, config, directory):
    import numpy as np
    try:
        import lightgbm as lgb
    except ImportError as error:
        raise ImportError("LightGBM is optional; install the project's training dependencies before this model") from error

    train = _matrix(preprocessor, train_rows, for_tree=True)
    validation = _matrix(preprocessor, validation_rows, for_tree=True)
    y_train = np.asarray([_number(row["y_return_7d"]) for row in train_rows])
    y_validation = np.asarray([_number(row["y_return_7d"]) for row in validation_rows])
    train_set = lgb.Dataset(train, label=y_train, free_raw_data=True)
    validation_set = lgb.Dataset(validation, label=y_validation, reference=train_set, free_raw_data=True)
    model = lgb.train({"objective": "regression_l1", "metric": "l1", "device_type": "cpu",
                       "seed": config["seed"], "num_threads": config["n_jobs"],
                       "learning_rate": config["learning_rate"], "num_leaves": 15,
                       "max_depth": 4, "min_data_in_leaf": 30, "deterministic": True,
                       "force_col_wise": True, "verbosity": -1},
                      train_set, num_boost_round=config["n_estimators"],
                      valid_sets=[validation_set], valid_names=["validation"],
                      callbacks=[lgb.early_stopping(config["early_stopping_rounds"], first_metric_only=True, verbose=False),
                                 lgb.log_evaluation(period=0)])
    best_iteration = int(model.best_iteration or model.current_iteration())
    prediction = np.asarray(model.predict(validation, num_iteration=best_iteration, num_threads=1))
    if not np.isfinite(prediction).all():
        raise ModelFitError("LightGBM generated non-finite validation predictions")
    booster_path = directory / "booster.txt"
    model.save_model(str(booster_path), num_iteration=best_iteration)
    parameters = {"booster_file": booster_path.name, "booster_sha256": _sha(booster_path),
                  "best_iteration": best_iteration, "feature_count": int(train.shape[1]),
                  "feature_names": list(preprocessor.feature_names(for_tree=True))}
    return parameters, {"selection": "validation_return_l1_early_stopping_fixed_tree_config",
                        "selected_validation_return_mae": float(np.mean(np.abs(prediction - y_validation))),
                        "packages": {"numpy": _package_version("numpy"), "lightgbm": _package_version("lightgbm")},
                        "device": "cpu"}


def _hourly_index(hourly_by_item, item):
    if hourly_by_item is None or item not in hourly_by_item:
        raise ValueError(f"Frozen hourly history is required for item {item}")
    rows = hourly_by_item[item]
    if isinstance(rows, dict):
        rows = rows.values()
    index = {}
    for source in rows:
        timestamp = _second(source.get("bucket_time"))
        if timestamp in index:
            raise ValueError("Duplicate frozen hourly key")
        index[timestamp] = source
    return index


def _log_grid(index, start, end):
    import numpy as np

    output = np.full((end - start) // HOUR, np.nan, dtype=float)
    for i, timestamp in enumerate(range(start, end, HOUR)):
        row = index.get(timestamp)
        if row is None or row.get("price_valid") not in (1, True):
            continue
        output[i] = math.log(_number(row.get("close_cny"), positive=True))
    return output


def _sarimax(series, order):
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    return SARIMAX(series, order=tuple(order), trend="n", enforce_stationarity=False,
                   enforce_invertibility=False, missing="none")


def _arima(train_rows, hourly_by_item, config, directory):
    import numpy as np

    by_item = defaultdict(list)
    for row in train_rows:
        by_item[row["market_hash_name"]].append(row)
    items = {}
    attempts = []
    for item in sorted(by_item):
        index = _hourly_index(hourly_by_item, item)
        cutoff = max(_second(row["decision_time"]) for row in by_item[item])
        available = [timestamp for timestamp in index if timestamp < cutoff]
        if not available:
            raise ModelFitError(f"No training history before cutoff for {item}")
        start = max(min(available), cutoff - config["arima_max_train_hours"] * HOUR)
        series = _log_grid(index, start, cutoff)
        observed = int(np.isfinite(series).sum())
        if observed < config["arima_min_train_observed"]:
            raise ModelFitError(f"Too few observed training hours for {item}: {observed}")
        best = None
        for order in ARIMA_ORDERS:
            attempt = {"market_hash_name": item, "order": list(order), "train_start": start,
                       "train_cutoff_exclusive": cutoff, "observed_hours": observed,
                       "grid_hours": len(series)}
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    fitted = _sarimax(series, order).fit(disp=False, maxiter=config["arima_maxiter"])
                attempt["warnings"] = sorted(set(str(warning.message)[:240] for warning in caught))
                converged = bool(fitted.mle_retvals.get("converged", False))
                valid = np.isfinite(fitted.params).all() and math.isfinite(float(fitted.aic))
                attempt.update(converged=converged, aic=float(fitted.aic) if valid else None,
                               status="converged" if converged and valid else "rejected_nonconverged_or_nonfinite")
                if converged and valid and (best is None or float(fitted.aic) < best["aic"]):
                    best = {"order": list(order), "params": [float(value) for value in fitted.params],
                            "param_names": list(fitted.param_names), "aic": float(fitted.aic),
                            "converged": True, "train_start": start, "train_cutoff_exclusive": cutoff,
                            "observed_hours": observed, "grid_hours": len(series)}
            except (ValueError, RuntimeError, ArithmeticError, np.linalg.LinAlgError) as error:
                attempt.update(status="failed", error_type=type(error).__name__, error=str(error)[:300])
            attempts.append(attempt)
            # Persist every bounded attempt, including failed convergence, for interruption review.
            attempt_path = directory / "arima_attempts.json"
            attempt_path.write_text(json.dumps(attempts, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                                    encoding="utf-8", newline="\n")
        if best is None:
            raise ModelFitError(f"All bounded ARIMA candidates failed for {item}; inspect arima_attempts.json")
        items[item] = best
    return {"items": items, "orders_searched": [list(order) for order in ARIMA_ORDERS],
            "trend": "n", "enforce_stationarity": False, "enforce_invertibility": False,
            "lookback_hours": LOOKBACK_HOURS, "horizon_hours": HORIZON_HOURS}, {
                "implementation": "bounded_auto_arima", "selection": "lowest_training_aic_per_item",
                "validation_used_for_order_selection": False,
                "inference": "filter_saved_coefficients_on_past_672h_then_forecast_168h_without_fit",
                "packages": {"numpy": _package_version("numpy"), "statsmodels": _package_version("statsmodels")},
                "attempt_file": "arima_attempts.json", "attempt_sha256": _sha(directory / "arima_attempts.json")}


def fit_model(name, train_rows, validation_rows, preprocessor, hourly_by_item=None,
              config=None, output_dir=None):
    """Fit only training rows, select with validation, and save portable parameters.

    ``output_dir`` must be absent or empty.  Returns metadata with an absolute
    ``artifact_path`` to its model.json.  Failed/interrupted fits raise and leave
    an explicit failure record; they never masquerade as a successful baseline.
    The parent experiment freezes the entire artifact directory after success.
    """
    if name == "bounded_auto_arima":
        name = "auto_arima"
    if name not in MODEL_NAMES:
        raise ValueError(f"Unknown CPU model {name}")
    if output_dir is None:
        raise ValueError("An explicit new model output directory is required")
    directory = Path(output_dir).resolve()
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise FileExistsError("Model output directory must be new or empty")
    settings = _config(name, config)
    train_rows = _rows(train_rows, "train", labels=True)
    validation_rows = _rows(validation_rows, "validation", labels=True)
    latest_train, earliest_validation = _check_splits(train_rows, validation_rows)
    if {row["market_hash_name"] for row in validation_rows} - {row["market_hash_name"] for row in train_rows}:
        raise ValueError("Validation contains an item absent from training")
    processor_sha = _processor_digest(preprocessor)
    processor_state = preprocessor.to_dict()
    if processor_state.get("fit_split") != "train" or processor_state.get("fit_row_keys_sha256") != _row_ids(train_rows):
        raise ValueError("Preprocessor must be fitted on exactly this model's training rows")
    directory.mkdir(parents=True, exist_ok=True)
    metadata = {"schema": VERSION, "model_name": name, "status": "complete", "target": "y_return_7d",
                "forecast_horizon_hours": HORIZON_HOURS, "lookback_hours": LOOKBACK_HOURS,
                "config": settings, "preprocessor_sha256": processor_sha,
                "train_rows": len(train_rows), "validation_rows": len(validation_rows),
                "train_row_ids_sha256": _row_ids(train_rows), "validation_row_ids_sha256": _row_ids(validation_rows),
                "trained_items": sorted({row["market_hash_name"] for row in train_rows}),
                "latest_train_decision": latest_train, "earliest_validation_decision": earliest_validation,
                "fit_scope": "training_only_not_rolling_point_in_time", "test_used_for_fitting_or_selection": False,
                "price_semantics": "reference_close_times_one_plus_predicted_return_not_executable_price"}
    try:
        if name == "persistence":
            parameters, details = {"constant_return": 0.0}, {"implementation": "fixed_persistence", "selection": "none", "packages": {}}
        elif name == "ridge":
            parameters, details = _ridge(train_rows, validation_rows, preprocessor, settings)
        elif name == "lightgbm":
            parameters, details = _lightgbm(train_rows, validation_rows, preprocessor, settings, directory)
        else:
            parameters, details = _arima(train_rows, hourly_by_item, settings, directory)
        parameters_path = directory / "parameters.json"
        _write_json(parameters_path, parameters)
        metadata.update(details)
        metadata.update(parameters_file=parameters_path.name, parameters_sha256=_sha(parameters_path))
        _write_json(directory / "model.json", metadata)
    except BaseException as error:
        # KeyboardInterrupt/SystemExit still propagate; a resumed run uses a new ID.
        failure = {"schema": VERSION, "model_name": name,
                   "status": "interrupted" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "failed",
                   "error_type": type(error).__name__, "error": str(error)[:500], "config": settings}
        _write_json(directory / "failure.json", failure)
        raise
    return {**metadata, "artifact_path": str(directory / "model.json")}


def _local_file(directory, filename):
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise ValueError("Only a model-local artifact filename is accepted")
    path = (directory / filename).resolve()
    if not path.is_relative_to(directory.resolve()) or not path.is_file():
        raise ValueError("Model artifact is absent or escapes its directory")
    return path


def load_model(metadata_or_path):
    """Verify and load metadata/JSON parameters; never unpickle arbitrary code."""
    path = metadata_or_path.get("artifact_path") if isinstance(metadata_or_path, dict) else metadata_or_path
    if path is None:
        raise ValueError("Returned metadata must retain its artifact_path")
    path = Path(path).resolve()
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if metadata.get("schema") != VERSION or metadata.get("status") != "complete":
        raise ValueError("Unsupported or incomplete CPU model artifact")
    if metadata.get("model_name") not in MODEL_NAMES or metadata.get("target") != "y_return_7d":
        raise ValueError("Wrong model target/schema")
    if metadata.get("forecast_horizon_hours") != HORIZON_HOURS:
        raise ValueError("Wrong forecast horizon")
    directory = path.parent
    parameters_path = _local_file(directory, metadata.get("parameters_file"))
    if _sha(parameters_path) != metadata.get("parameters_sha256"):
        raise ValueError("Saved model parameters failed SHA-256 verification")
    parameters = json.loads(parameters_path.read_text(encoding="utf-8"))
    if metadata["model_name"] == "lightgbm":
        booster = _local_file(directory, parameters.get("booster_file"))
        if _sha(booster) != parameters.get("booster_sha256"):
            raise ValueError("Saved LightGBM booster failed SHA-256 verification")
    return {**metadata, "artifact_path": str(path)}, parameters


def predict_model(metadata_or_path, rows, preprocessor, hourly_by_item=None, **options):
    """Load frozen coefficients and return seven-day simple returns, in row order.

    Accepts no labels.  Does not select hyperparameters or call ``fit``.  The
    generic runner may pass ``device``; CPU adapters always remain on CPU.
    Non-finite outputs fail explicitly; finite returns below -1 are left visible
    to evaluation's invalid-price reporting, never silently clipped.
    """
    if set(options) - {"device"}:
        raise ValueError(f"Unsupported inference options: {sorted(set(options) - {'device'})}")
    metadata, parameters = load_model(metadata_or_path)
    if _processor_digest(preprocessor) != metadata["preprocessor_sha256"]:
        raise ValueError("Inference preprocessor differs from the frozen training preprocessor")
    rows = _rows(rows)
    if {row["market_hash_name"] for row in rows} - set(metadata["trained_items"]):
        raise ValueError("An unseen item requires a new model training experiment")
    name = metadata["model_name"]
    if name == "persistence":
        prediction = [0.0] * len(rows)
    elif name == "ridge":
        import numpy as np

        matrix = _matrix(preprocessor, rows)
        coefficients = np.asarray(parameters["coef"], dtype=float)
        if matrix.shape[1] != len(coefficients) or list(preprocessor.feature_names(for_tree=False)) != parameters["feature_names"]:
            raise ValueError("Ridge feature schema differs from saved coefficients")
        prediction = (matrix @ coefficients + _number(parameters["intercept"])).tolist()
    elif name == "lightgbm":
        import lightgbm as lgb

        matrix = _matrix(preprocessor, rows, for_tree=True)
        if matrix.shape[1] != parameters["feature_count"] or list(preprocessor.feature_names(for_tree=True)) != parameters["feature_names"]:
            raise ValueError("LightGBM feature schema differs from saved booster")
        booster = lgb.Booster(model_file=str(Path(metadata["artifact_path"]).parent / parameters["booster_file"]))
        prediction = booster.predict(matrix, num_iteration=parameters["best_iteration"], num_threads=1).tolist()
    else:
        prediction = _predict_arima(parameters, rows, hourly_by_item)
    return [_number(value) for value in prediction]


def _predict_arima(parameters, rows, hourly_by_item):
    import numpy as np

    if parameters.get("lookback_hours") != LOOKBACK_HOURS or parameters.get("horizon_hours") != HORIZON_HOURS:
        raise ValueError("Unexpected saved ARIMA window/horizon")
    indexes, prediction = {}, []
    for row in rows:
        item = row["market_hash_name"]
        if item not in parameters["items"]:
            raise ValueError(f"ARIMA has no trained coefficients for item {item}")
        if item not in indexes:
            indexes[item] = _hourly_index(hourly_by_item, item)
        origin = _second(row["decision_time"])
        series = _log_grid(indexes[item], origin - LOOKBACK_HOURS * HOUR, origin)
        if int(np.isfinite(series).sum()) < 24 or not math.isfinite(float(series[-1])):
            raise ValueError("ARIMA origin needs an observed reference and at least 24 past observed hours")
        reference = _reference(row)
        if not math.isclose(math.exp(float(series[-1])), reference, rel_tol=1e-9, abs_tol=1e-8):
            raise ValueError("Sample reference differs from the frozen last hourly close")
        item_parameters = parameters["items"][item]
        model = _sarimax(series, item_parameters["order"])
        if list(model.param_names) != item_parameters["param_names"]:
            raise ValueError("statsmodels parameter schema differs from frozen ARIMA")
        # filter updates latent state with observations only; coefficients remain frozen.
        filtered = model.filter(np.asarray(item_parameters["params"], dtype=float))
        log_price = float(np.asarray(filtered.forecast(steps=HORIZON_HOURS))[-1])
        try:
            prediction.append(math.exp(log_price - math.log(reference)) - 1.0)
        except OverflowError as error:
            raise ValueError("ARIMA forecast is outside the finite return range") from error
    return prediction
