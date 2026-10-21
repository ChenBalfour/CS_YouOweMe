"""Training-only missing adapters and scaling, saved as portable JSON.

These transforms affect model inputs, never the frozen clean/raw databases.
Targets remain unscaled seven-day returns. Tree mode preserves numeric NaNs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .training_data import FEATURE_FIELDS, SEQUENCE_FIELDS, _feature_fields, prepare_rows

VERSION = "seven-train-only-preprocessing-1.0"


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _fit_stats(values):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or not len(values) or np.isinf(values).any():
        raise ValueError("Fitting requires a nonempty finite-or-NaN numeric matrix")
    empty = np.isnan(values).all(axis=0)
    median = np.array([0.0 if no_data else np.median(values[np.isfinite(values[:, j]), j])
                       for j, no_data in enumerate(empty)], dtype=np.float64)
    imputed = np.where(np.isnan(values), median, values)
    mean, scale = imputed.mean(axis=0), imputed.std(axis=0)
    constant = scale < 1e-12
    scale[constant] = 1.0
    if not all(np.isfinite(x).all() for x in (median, mean, scale)):
        raise ValueError("Non-finite fitted preprocessing statistics")
    return {"median": median.tolist(), "mean": mean.tolist(), "scale": scale.tolist(),
            "all_missing": empty.tolist(), "constant": constant.tolist()}


def _scaled(values, stats):
    values = np.asarray(values, dtype=np.float64)
    if np.isinf(values).any():
        raise ValueError("Infinite transform input")
    mask = np.isnan(values)
    result = (np.where(mask, stats["median"], values) - stats["mean"]) / stats["scale"]
    if not np.isfinite(result).all():
        raise ValueError("Non-finite transformed input")
    return np.concatenate((result, mask.astype(np.float64)), axis=-1).astype(np.float32)


def _sequence(values, count):
    values = np.asarray(values, dtype=np.float64)
    if values.shape != (count, 672, 3) or np.isinf(values).any():
        raise ValueError("Raw sequences must have shape [N,672,3] and contain finite values or NaN")
    return values


class TrainOnlyPreprocessor:
    """Fit once on eligible, non-purged training rows; transform never refits.

    Missing values use training-column medians. An entirely missing training
    column uses 0 as an explicitly recorded model-input fallback, with its mask
    retained. Standardization uses the imputed training matrix's population
    mean/std; a constant column has scale 1. Unknown items stop prediction.
    """

    def __init__(self):
        self._state = None

    @property
    def feature_fields(self):
        return list(self._require()["feature_fields"])

    @property
    def item_names(self):
        return list(self._require()["item_names"])

    def _require(self):
        if self._state is None:
            raise ValueError("Preprocessor is not fitted; fit only the training split")
        return self._state

    def fit_rows(self, rows, feature_fields=FEATURE_FIELDS, sequences=None,
                 eligibility_field="eligible_point_quality"):
        if self._state is not None:
            raise ValueError("Preprocessor is already fitted; create a new experiment to refit")
        if eligibility_field not in ("eligible_point_quality", "eligible_point_strict"):
            raise ValueError("Unknown frozen point-eligibility profile")
        fields, rows = _feature_fields(feature_fields), list(rows)
        if not rows or any(row.get("split") != "train" or row.get("purged") != 0
                           or row.get(eligibility_field) != 1 for row in rows):
            raise ValueError("Fit requires only eligible, non-purged training rows")
        prepared = prepare_rows(rows, fields)
        names = sorted(set(prepared["item_names"]))
        keys = sorted([list(key) for key in prepared["keys"]])
        seq_stats = None
        if sequences is not None:
            sequences = _sequence(sequences, len(rows))
            seq_stats = _fit_stats(sequences.reshape(-1, 3))
        self._state = {
            "version": VERSION, "feature_fields": list(fields), "item_names": names,
            "sequence_fields": list(SEQUENCE_FIELDS), "lookback_hours": 672,
            "tabular_statistics": _fit_stats(prepared["x_tabular"]),
            "sequence_statistics": seq_stats, "fit_split": "train", "fit_rows": len(rows),
            "eligibility_field": eligibility_field, "fit_row_keys": keys,
            "fit_row_keys_sha256": _canonical_hash(keys),
            "missing_policy": "training_median_with_mask",
            "all_missing_training_column_fallback": 0.0,
            "scale_policy": "imputed_training_population_mean_std_constant_scale_1",
            "target": "y_return_7d", "target_scaled": False,
            "unseen_item_policy": "error", "source_data_mutated": False,
        }
        return self

    def feature_names(self, for_tree=False):
        state = self._require()
        fields = list(state["feature_fields"])
        if not for_tree:
            fields += [field + "__missing" for field in state["feature_fields"]]
        return fields + ["item__" + name for name in state["item_names"]]

    def transform_tabular(self, rows, for_tree=False):
        state = self._require()
        prepared = prepare_rows(rows, state["feature_fields"])
        levels = {name: i for i, name in enumerate(state["item_names"])}
        onehot = np.zeros((len(prepared["keys"]), len(levels)), dtype=np.float32)
        for i, name in enumerate(prepared["item_names"]):
            if name not in levels:
                raise ValueError(f"Unseen item requires a new training experiment: {name}")
            onehot[i, levels[name]] = 1.0
        numeric = prepared["x_tabular"] if for_tree else _scaled(prepared["x_tabular"], state["tabular_statistics"])
        return np.concatenate((numeric, onehot), axis=1).astype(np.float32)

    def transform_sequences(self, sequences):
        state = self._require()
        if state["sequence_statistics"] is None:
            raise ValueError("Sequence statistics were not fitted on training rows")
        values = np.asarray(sequences, dtype=np.float64)
        _sequence(values, len(values))
        return _scaled(values, state["sequence_statistics"])

    def transform_rows(self, rows, sequences=None, mode="scaled"):
        if mode not in ("scaled", "tree"):
            raise ValueError("mode must be scaled or tree")
        rows = list(rows)
        result = prepare_rows(rows, self.feature_fields, include_labels=False)
        tabular = self.transform_tabular(rows, for_tree=(mode == "tree"))
        result.update(x_tabular=tabular, tabular=tabular)
        if sequences is not None:
            raw = _sequence(sequences, len(rows))
            sequence = self.transform_sequences(raw)
            result.update(x_sequence=sequence, sequence=sequence)
        return result

    def to_dict(self):
        return json.loads(json.dumps(self._require(), ensure_ascii=False, allow_nan=False))

    @classmethod
    def from_dict(cls, state):
        value = json.loads(json.dumps(state, ensure_ascii=False, allow_nan=False))
        if (value.get("version") != VERSION or tuple(value.get("feature_fields", ())) != FEATURE_FIELDS
                or value.get("sequence_fields") != list(SEQUENCE_FIELDS) or value.get("lookback_hours") != 672
                or value.get("fit_split") != "train" or type(value.get("fit_rows")) is not int
                or value["fit_rows"] <= 0 or value.get("target") != "y_return_7d"
                or value.get("target_scaled") is not False or value.get("unseen_item_policy") != "error"
                or value.get("source_data_mutated") is not False
                or value.get("eligibility_field") not in ("eligible_point_quality", "eligible_point_strict")):
            raise ValueError("Unsupported preprocessing state")
        names, keys = value.get("item_names"), value.get("fit_row_keys")
        if (not isinstance(names, list) or not names or not all(isinstance(name, str) and name for name in names)
                or names != sorted(set(names)) or not isinstance(keys, list) or len(keys) != value["fit_rows"]
                or any(not isinstance(key, list) or len(key) != 2 or key[0] not in names
                       or type(key[1]) is not int for key in keys)
                or len({tuple(key) for key in keys}) != len(keys) or sorted(keys) != keys
                or _canonical_hash(keys) != value.get("fit_row_keys_sha256")):
            raise ValueError("Preprocessing item identity or fit-row digest differs")
        for name, width in (("tabular_statistics", 21), ("sequence_statistics", 3)):
            stats = value.get(name)
            if stats is None and name == "sequence_statistics":
                continue
            if not isinstance(stats, dict):
                raise ValueError("Missing preprocessing statistics")
            for field in ("median", "mean", "scale", "all_missing", "constant"):
                if not isinstance(stats.get(field), list) or len(stats[field]) != width:
                    raise ValueError("Preprocessing statistics width differs")
            for field in ("median", "mean", "scale"):
                if not np.isfinite(np.asarray(stats[field], dtype=np.float64)).all():
                    raise ValueError("Non-finite stored preprocessing statistics")
            if any(float(scale) <= 0 for scale in stats["scale"]):
                raise ValueError("Stored scale must be positive")
            if any(type(flag) is not bool for field in ("all_missing", "constant") for flag in stats[field]):
                raise ValueError("Stored missing/constant masks must be boolean")
        result = cls()
        result._state = value
        return result

    def save(self, path):
        """Save once inside the caller's new local experiment; never overwrite."""
        path = Path(path)
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        return path

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
