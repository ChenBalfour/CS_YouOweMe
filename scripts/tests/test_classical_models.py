"""Small synthetic CPU-model persistence tests; never fit real project data."""
from __future__ import annotations

import copy
from contextlib import ExitStack
import importlib.util
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.research.models import classical

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
HAS_SKLEARN = importlib.util.find_spec("sklearn") is not None
HAS_STATSMODELS = importlib.util.find_spec("statsmodels") is not None
HAS_LIGHTGBM = importlib.util.find_spec("lightgbm") is not None
if HAS_NUMPY:
    import numpy as np
    from scripts.research.data.model_preprocessing import TrainOnlyPreprocessor
    from scripts.research.data.training_data import FEATURE_FIELDS, prediction_rows

ROOT = Path(__file__).resolve().parents[2]
ITEM = "Synthetic CPU item (Factory New)"
HOUR = 3600
START = (1_700_000_000 // HOUR) * HOUR


class LazyCPUImportTests(unittest.TestCase):
    def test_module_import_does_not_require_optional_ml_libraries(self):
        program = """
import builtins, importlib.util, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'numpy','sklearn','statsmodels','lightgbm','joblib','torch'}:
        raise AssertionError('Eager optional dependency import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
spec = importlib.util.spec_from_file_location('standalone_classical', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert len(module.MODEL_NAMES) == 4
"""
        result = subprocess.run([sys.executable, "-B", "-c", program, str(Path(classical.__file__))],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(HAS_NUMPY, "Optional research dependencies are unavailable")
class ClassicalModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        local = ROOT / "data/local"
        local.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix="cpu_models_test_", dir=local)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.hours = {ITEM: []}
        generator, log_price = random.Random(42), math.log(100)
        for h in range(2100):
            log_price += 0.00005 + generator.gauss(0, 0.005)
            price = math.exp(log_price)
            cls.hours[ITEM].append({"bucket_time": START + h * HOUR, "price_valid": 1,
                                    "close_cny": str(price), "high_cny": str(price * 1.001),
                                    "low_cny": str(price / 1.001), "observed": 1})

        def row(h, split):
            result = {field: 0.01 * (i + 1) + 0.0001 * h for i, field in enumerate(FEATURE_FIELDS)}
            result.update(market_hash_name=ITEM, decision_time=START + h * HOUR,
                          split=split, purged=0, eligible_point_quality=1,
                          x_reference_close=float(cls.hours[ITEM][h - 1]["close_cny"]),
                          x_return_1d=0.01 * math.sin(h / 9),
                          y_return_7d=0.03 * math.sin(h / 8))
            if h % 144 == 0:
                result["x_return_3d"] = None
            return result

        cls.make_row = staticmethod(row)
        cls.training = [row(h, "train") for h in range(672, 1610, 24)]
        cls.validation = [row(h, "validation") for h in (1800, 1824, 1848, 1872)]
        cls.preprocessor = TrainOnlyPreprocessor().fit_rows(cls.training)
        cls.preprocessor.save(cls.directory / "preprocessor.json")
        cls.models = {}
        dependency = {"persistence": True, "ridge": HAS_SKLEARN,
                      "auto_arima": HAS_STATSMODELS, "lightgbm": HAS_LIGHTGBM}
        for name in classical.MODEL_NAMES:
            if not dependency[name]:
                continue
            config = {}
            if name == "auto_arima":
                config = {"arima_maxiter": 30, "arima_max_train_hours": 672,
                          "arima_min_train_observed": 24}
            elif name == "lightgbm":
                config = {"n_estimators": 10, "early_stopping_rounds": 3, "n_jobs": 1}
            cls.models[name] = classical.fit_model(name, cls.training, cls.validation,
                                                   cls.preprocessor, cls.hours, config, cls.directory / name)

    def test_portable_save_reload_predictions_never_refit_or_read_labels(self):
        processor = TrainOnlyPreprocessor.load(self.directory / "preprocessor.json")
        inputs = prediction_rows(self.validation)
        for name, model in self.models.items():
            with self.subTest(model=name):
                first = classical.predict_model(model, self.validation, self.preprocessor, self.hours)
                with ExitStack() as context:
                    if HAS_SKLEARN:
                        context.enter_context(patch("sklearn.linear_model.Ridge.fit", side_effect=AssertionError("Inference refit Ridge")))
                    if HAS_STATSMODELS:
                        context.enter_context(patch("statsmodels.tsa.statespace.sarimax.SARIMAX.fit",
                                                    side_effect=AssertionError("Inference refit ARIMA")))
                    if HAS_LIGHTGBM:
                        context.enter_context(patch("lightgbm.train", side_effect=AssertionError("Inference retrained tree")))
                    second = classical.predict_model(model["artifact_path"], inputs, processor, self.hours)
                np.testing.assert_allclose(first, second, rtol=0, atol=1e-12)
                self.assertTrue(np.isfinite(first).all())
        np.testing.assert_array_equal(classical.predict_model(self.models["persistence"], inputs, processor),
                                      np.zeros(len(inputs)))

    def test_requires_training_split_and_seven_day_label_purge(self):
        invalid = copy.deepcopy(self.training)
        invalid[0]["split"] = "validation"
        with self.assertRaisesRegex(ValueError, "non-purged train"):
            classical.fit_model("persistence", invalid, self.validation, self.preprocessor,
                                output_dir=self.directory / "wrong_split")
        overlap = [self.make_row(1656, "validation")]
        with self.assertRaisesRegex(ValueError, "purge"):
            classical.fit_model("persistence", self.training, overlap, self.preprocessor,
                                output_dir=self.directory / "overlap")

    def test_requires_identical_preprocessor_training_keys(self):
        subset = self.training[:-1]
        with self.assertRaisesRegex(ValueError, "exactly this model's training rows"):
            classical.fit_model("persistence", subset, self.validation, self.preprocessor,
                                output_dir=self.directory / "wrong_preprocessor_keys")

    def test_changed_preprocessing_is_rejected(self):
        state = self.preprocessor.to_dict()
        state["tabular_statistics"]["median"][0] += 1
        changed = TrainOnlyPreprocessor.from_dict(state)
        with self.assertRaisesRegex(ValueError, "preprocessor differs"):
            classical.predict_model(self.models["persistence"], self.validation, changed)

    def test_changed_model_coefficients_fail_hash_verification(self):
        model = classical.fit_model("persistence", self.training, self.validation, self.preprocessor,
                                    output_dir=self.directory / "tamper")
        path = Path(model["artifact_path"]).parent / "parameters.json"
        path.write_text('{"constant_return": 1.0}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            classical.predict_model(model, self.validation, self.preprocessor)

    def test_preserves_existing_artifacts_and_rejects_unseen_items(self):
        with self.assertRaises(FileExistsError):
            classical.fit_model("persistence", self.training, self.validation, self.preprocessor,
                                output_dir=self.directory / "persistence")
        unknown = copy.deepcopy(self.validation)
        unknown[0]["market_hash_name"] = "Unseen item"
        with self.assertRaisesRegex(ValueError, "unseen item"):
            classical.predict_model(self.models["persistence"], unknown, self.preprocessor)

    @unittest.skipUnless(HAS_STATSMODELS, "Optional statsmodels is unavailable")
    def test_arima_ignores_future_hours_and_fits_before_train_cutoff(self):
        model = self.models["auto_arima"]
        metadata, parameters = classical.load_model(model)
        self.assertEqual(metadata["implementation"], "bounded_auto_arima")
        self.assertFalse(metadata["validation_used_for_order_selection"])
        expected_cutoff = max(row["decision_time"] for row in self.training)
        self.assertEqual(parameters["items"][ITEM]["train_cutoff_exclusive"], expected_cutoff)
        inputs = prediction_rows(self.validation[:1])
        before = classical.predict_model(model, inputs, self.preprocessor, self.hours)
        changed = copy.deepcopy(self.hours)
        for row in changed[ITEM]:
            if row["bucket_time"] >= inputs[0]["decision_time"]:
                row["close_cny"] = "9999999999"
        after = classical.predict_model(model, inputs, self.preprocessor, changed)
        np.testing.assert_allclose(before, after, rtol=0, atol=1e-12)

    @unittest.skipUnless(HAS_STATSMODELS, "Optional statsmodels is unavailable")
    def test_arima_nonconvergence_is_an_explicit_failed_fit(self):
        class Nonconverged:
            mle_retvals = {"converged": False}
            params = [1.0]
            aic = 1.0

        directory = self.directory / "nonconverged"
        with patch("statsmodels.tsa.statespace.sarimax.SARIMAX.fit", return_value=Nonconverged()):
            with self.assertRaisesRegex(classical.ModelFitError, "All bounded ARIMA candidates failed"):
                classical.fit_model("auto_arima", self.training, self.validation, self.preprocessor,
                                    self.hours, {"arima_max_train_hours": 672}, directory)
        failure = json.loads((directory / "failure.json").read_text(encoding="utf-8"))
        self.assertEqual(failure["status"], "failed")
        self.assertFalse((directory / "model.json").exists())
        attempts = json.loads((directory / "arima_attempts.json").read_text(encoding="utf-8"))
        self.assertEqual(len(attempts), 4)
        self.assertTrue(all(attempt["status"] == "rejected_nonconverged_or_nonfinite" for attempt in attempts))


if __name__ == "__main__":
    unittest.main()
