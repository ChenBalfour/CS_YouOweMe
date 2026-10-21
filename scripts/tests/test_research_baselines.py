"""Offline behavioral tests; temporary fixtures stay inside the project."""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.research.data import daily_samples as builder
from scripts.research.evaluation import baseline_report as evaluation
from scripts.research.evaluation.costs import break_even
from scripts.research.models.baselines import MODEL_ORDER, predict_path


class BaselineTests(unittest.TestCase):
    def setUp(self):
        base = evaluation.ROOT / "data/local/artifacts"
        base.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="_offline_baselines_", dir=base)
        self.directory = Path(self.temporary.name).resolve()
        self.assertTrue(self.directory.is_relative_to(base.resolve()))
        self.sample_base = self.directory / "samples"
        self.output_base = self.directory / "evaluations"

    def tearDown(self):
        self.temporary.cleanup()

    def fixture(self):
        spec = json.loads((evaluation.ROOT / "scripts/config/cyrex_daily_spec.json").read_text(encoding="utf-8-sig"))
        spec["validation_start_beijing"] = "2026-02-01T10:00:00+08:00"
        spec["test_start_beijing"] = "2026-03-01T10:00:00+08:00"
        start = int(datetime(2025, 12, 1, tzinfo=evaluation.CHINA).timestamp())
        cutoff = int(datetime(2026, 4, 1, 12, tzinfo=evaluation.CHINA).timestamp())
        hours = []
        for index, bucket in enumerate(range(start, cutoff, 3600)):
            price = str(100 + index / 1000)
            hours.append({"version_id": index + 1, "market_hash_name": spec["market_hash_name"],
                          "platform": "YOUPIN", "period": "1h", "style": "", "source_time": bucket,
                          "bucket_time": bucket, "open_cny": price, "close_cny": price,
                          "high_cny": price, "low_cny": price, "source_volume": "3",
                          "source_turnover_cny": "300.0", "source_request": 1})
        samples, sequence, summary = builder.build_rows(hours, spec, cutoff)
        folder = self.sample_base / "fixture"
        (folder / "source").mkdir(parents=True)
        spec_bytes = (json.dumps(spec, ensure_ascii=False) + "\n").encode()
        (folder / "source/cyrex_daily_spec.json").write_bytes(spec_bytes)
        (folder / "source/source_report.json").write_text(json.dumps({"run": {"completed_at": "2026-04-01T12:31:00+08:00"}}), encoding="utf-8")
        for name, rows in (("samples.csv", samples), ("sequence.csv", sequence), ("source_hourly.csv", hours)):
            (folder / name).write_bytes(evaluation._csv_bytes(rows))
        manifest = {"version": "cyrex-daily-samples-1.1", "status": "retrospective_research_candidate",
                    "output_id": "fixture", "created_at_beijing": "2026-04-01T13:00:00+08:00",
                    "training_approved": False, "spec": spec, "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
                    "source_request_cap": 1, "summary": summary,
                    "outputs": {path.relative_to(folder).as_posix(): {"bytes": path.stat().st_size,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                                for path in folder.rglob("*") if path.is_file()}}
        evaluation._dump(folder / "manifest.json", manifest)
        evaluation._dump(self.sample_base / "latest_cyrex.json", {"manifest": "fixture/manifest.json"})
        return folder

    def patches(self):
        return patch.multiple(evaluation, BASE=self.output_base, SAMPLE_BASE=self.sample_base)

    def test_formula_direction_and_day_zero(self):
        features = {"x_reference_close": 100, "x_return_3d": 0.331, "x_return_7d": -0.3, "x_return_14d": 0}
        path = predict_path(features, "log_drift_3d")
        self.assertEqual(path[0], 100)
        self.assertAlmostEqual(path[3], 133.1)
        self.assertLess(predict_path(features, "log_drift_7d")[-1], 100)
        self.assertEqual(predict_path(features, "persistence"), [100] * 8)

    def test_forecasts_do_not_depend_on_labels(self):
        features = {"x_reference_close": 100, "x_return_3d": .1, "x_return_7d": .2, "x_return_14d": .3}
        before = {model: predict_path(features, model) for model in MODEL_ORDER}
        features.update({"y_source_close_7d": object(), "future_observed_hours": -1, "eligible": False})
        self.assertEqual(before, {model: predict_path(features, model) for model in MODEL_ORDER})
        for invalid in (None, True, 0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                predict_path({"x_reference_close": invalid}, "persistence")

    def test_validation_selection_and_tie_priority(self):
        row = {"sample_id": "v", "split": "validation", "eligible": True, "decision_time": 1,
               "target_time": 604801, "target_at_beijing": "fixture", "x_reference_close": 100,
               "x_return_3d": 0, "x_return_7d": .2, "x_return_14d": 0, "y_source_close_7d": 120}
        self.assertEqual(evaluation.select_on_validation([row])[0], "log_drift_7d")
        with self.assertRaises(ValueError):
            evaluation.select_on_validation([{**row, "split": "test", "y_source_close_7d": 999999}])
        self.assertEqual(evaluation.select_on_validation([{**row, "x_return_7d": 0}])[0], "persistence")

    def test_metrics_show_negative_skill_and_not_profit(self):
        values = evaluation.metrics([{"prediction": 200, "actual": 100, "reference_price": 90, "persistence_prediction": 90}])
        self.assertEqual(values["mae_cny"], 100)
        self.assertAlmostEqual(values["relative_mae_skill_vs_persistence"], -9)
        self.assertAlmostEqual(values["return_error_mae_pp"], 100 / 90 * 100)
        self.assertNotIn("profit", values)

    def test_candidate_sha_mismatch_is_rejected(self):
        folder = self.fixture()
        with self.patches():
            self.assertGreater(len(evaluation.load_candidate()["samples"]), 0)
            with (folder / "samples.csv").open("ab") as handle:
                handle.write(b"changed")
            with self.assertRaisesRegex(ValueError, "SHA"):
                evaluation.load_candidate()

    def test_time_label_eligibility_reconstruction(self):
        folder = self.fixture()
        path = folder / "samples.csv"
        data = path.read_bytes().replace(b",train,False,True,", b",test,False,True,", 1)
        path.write_bytes(data)
        manifest_path = folder / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["outputs"]["samples.csv"] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        evaluation._dump(manifest_path, manifest)
        with self.patches(), self.assertRaisesRegex(ValueError, "Reconstructed"):
            evaluation.load_candidate()

    def test_frozen_output_latest_pending_forecast_and_no_source_changes(self):
        folder = self.fixture()
        before = {path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in folder.rglob("*") if path.is_file()}
        with self.patches():
            manifest = evaluation.evaluate(output_id="offline_report")
            self.assertEqual(manifest["forecast"]["origin_label_status"], "pending_future")
            self.assertFalse(manifest["source_database_opened"])
            self.assertTrue(manifest["selected_model_locked_before_test"])
            self.assertEqual(evaluation.status()["output_id"], "offline_report")
            output = Path(manifest["output_dir"])
            forecast = evaluation._read_csv((output / "forecast.csv").read_bytes())
            self.assertEqual(len(forecast), 8)
            self.assertEqual(forecast[0]["origin_time"], forecast[0]["target_time"])
            self.assertEqual(int(forecast[-1]["target_time"]) - int(forecast[0]["origin_time"]), 7 * evaluation.DAY)
            score = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
            self.assertLessEqual(set(score["test"]), {manifest["selected_model"], "persistence"})
            with self.assertRaises(FileExistsError):
                evaluation.evaluate(output_id="offline_report")
        after = {path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in folder.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_costs_missing_are_not_zero_and_explicit_scenario(self):
        self.assertEqual(break_even(232, None, None)["status"], "insufficient_data")
        self.assertAlmostEqual(break_even(100, .02, 1)["break_even_exit_price"], 101 / .98)
        self.assertIsNone(break_even(100, .02, 1)["buy_sell_decision"])
        with self.assertRaises(ValueError):
            break_even(100, 1, 0)

    def test_protocol_cannot_be_changed_silently(self):
        spec = json.loads(evaluation.DEFAULT_SPEC.read_text(encoding="utf-8-sig"))
        evaluation._validate_spec(spec)
        spec["selection_split"] = "test"
        with self.assertRaises(ValueError):
            evaluation._validate_spec(spec)


if __name__ == "__main__":
    unittest.main()
