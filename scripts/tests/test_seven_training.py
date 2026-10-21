"""Small synthetic end-to-end tests; no private dataset or market request."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from scripts.research.data.training_data import FEATURE_FIELDS
from scripts.research.evaluation import seven_training as runner


def fixture():
    start = 1767225600 // 3600 * 3600
    origins = [start + i * 86400 for i in range(16)] + [start + (24 + i) * 86400 for i in range(2)]
    hours = []
    for i, when in enumerate(range(start - 672 * 3600, origins[-1], 3600)):
        value = 100 + i * .01 + np.sin(i / 20)
        hours.append(dict(market_hash_name="Synthetic A", bucket_time=when, observed=1, price_valid=1,
                          close_cny=str(value), high_cny=str(value + .5), low_cny=str(value - .5)))
    by_time = {r["bucket_time"]: r for r in hours}
    rows = []
    for i, when in enumerate(origins):
        reference = float(by_time[when - 3600]["close_cny"])
        row = {field: .01 * (i + 1) for field in FEATURE_FIELDS}
        row.update(market_hash_name="Synthetic A", steamdt_item_id="1", uu_template_id="2", decision_time=when,
                   decision_at_beijing="synthetic", split="train" if i < 16 else "validation",
                   purged=0, eligible_point_quality=1, target_time=when + 168 * 3600,
                   x_reference_close=reference, reference_close_cny=str(reference),
                   reference_bucket_time=when - 3600, y_return_7d=.01 + i * .001,
                   y_reference_close_7d=str(reference * (1.01 + i * .001)))
        rows.append(row)
    return dict(rows=rows, all_rows=rows, splits={"train": rows[:16], "validation": rows[16:], "test_exploratory": rows[16:]},
                feature_fields=list(FEATURE_FIELDS), items=[{"market_hash_name": "Synthetic A"}],
                hourly_by_item={"Synthetic A": hours}, provenance={"eligibility_field": "eligible_point_quality", "synthetic": True})


class SevenTrainingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.bundle = fixture()
        for target, value in (("BASE", self.base / "a"), ("REPORTS", self.base / "r")):
            mock = patch.object(runner, target, value); mock.start(); self.addCleanup(mock.stop)
        mock = patch.object(runner, "load_dataset", return_value=self.bundle)
        mock.start(); self.addCleanup(mock.stop)

    def test_prepare_fit_reload_without_any_fit_then_charts(self):
        prepared = runner.prepare("synthetic", "p")
        self.assertEqual(prepared["split_counts"]["train"], 16)
        result = runner.train("p", ["persistence", "ridge"], "f", device="cpu")
        self.assertEqual(result["status"], "complete", result)
        self.assertFalse(result["test_evaluated"])
        self.assertIn(result["selected_model"], ("persistence", "ridge"))
        with patch("sklearn.linear_model.Ridge.fit", side_effect=AssertionError("Evaluation refitted")), \
             patch.object(runner.TrainOnlyPreprocessor, "fit_rows", side_effect=AssertionError("Evaluation rescaled")):
            report = runner.evaluate("f", report_id="r1", device="cpu")
        self.assertEqual(report["fit_calls"], 0)
        self.assertEqual(len(report["charts"]), 1)
        self.assertTrue((self.base / "r/r1/item_1.png").is_file())
        runner.verify(self.base / "r", "r1", "evaluation")
        with self.assertRaisesRegex(ValueError, "exploratory"):
            runner.evaluate("f", split="test_exploratory")

    def test_reject_overwrite_tamper_and_paths(self):
        runner.prepare("synthetic", "p")
        with self.assertRaises(FileExistsError):
            runner.prepare("synthetic", "p")
        with self.assertRaises(ValueError):
            runner.prepare("synthetic", "../outside")
        real_sha = runner._sha
        changed_file = runner.ROOT / "scripts/research/models/neural.py"
        with patch.object(runner, "_sha", side_effect=lambda p: "changed" if Path(p) == changed_file else real_sha(p)):
            with self.assertRaisesRegex(ValueError, "Runtime source differs"):
                runner.train("p", ["persistence"], "drift")
        target = self.base / "a/prepared/p/preprocessor.json"
        target.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            runner.train("p", ["persistence"], "f")

    def test_failed_model_stays_partial_and_cannot_be_evaluated(self):
        runner.prepare("synthetic", "p")
        with patch("scripts.research.models.classical.fit_model", side_effect=ValueError("synthetic failure")):
            result = runner.train("p", ["persistence"], "failed")
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["selected_model"])
        self.assertFalse((self.base / "a/latest.json").exists())
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            runner.evaluate("failed")

    def test_evaluation_explicit_and_metrics_do_not_clip_invalid_prices(self):
        score = runner.metrics(self.bundle["rows"][:1], [-2])
        self.assertEqual(score["invalid_nonpositive_price_count"], 1)
        with self.assertRaises(ValueError):
            runner.metrics([], [])
        with self.assertRaises(ValueError):
            runner.train("unused", ["unknown"])


if __name__ == "__main__":
    unittest.main()
