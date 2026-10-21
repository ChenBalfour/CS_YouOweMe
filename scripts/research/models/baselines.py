"""Prespecified price baselines which accept past feature values only."""
from __future__ import annotations

import math

MODEL_ORDER = ("persistence", "log_drift_3d", "log_drift_7d", "log_drift_14d")


def positive(value):
    if value is None or isinstance(value, bool):
        raise ValueError("A finite positive price is required")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("A finite positive price is required")
    return number


def predict_path(features, model, horizon_days=7):
    """Return day 0..horizon; reads no labels, dates, or future metadata."""
    if model not in MODEL_ORDER or type(horizon_days) is not int or not 1 <= horizon_days <= 7:
        raise ValueError("Unsupported fixed model or horizon")
    reference = positive(features.get("x_reference_close"))
    daily_drift = 0.0
    if model != "persistence":
        lag = int(model.removeprefix("log_drift_").removesuffix("d"))
        value = features.get(f"x_return_{lag}d")
        if value is None or isinstance(value, bool):
            raise ValueError("Finite past return greater than -1 required")
        past_return = float(value)
        if not math.isfinite(past_return) or past_return <= -1:
            raise ValueError("Finite past return greater than -1 required")
        daily_drift = math.log1p(past_return) / lag
    try:
        return [positive(reference * math.exp(daily_drift * day)) for day in range(horizon_days + 1)]
    except OverflowError as error:
        raise ValueError("Forecast is outside finite positive range") from error
