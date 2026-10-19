"""Synthetic figure checks; never read market data or create predictions online."""
import csv
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from scripts.research.visualization import forecast_charts as charts


class ForecastChartTests(unittest.TestCase):
    def setUp(self):
        self.origin = 1792360800
        self.history = [{"bucket_time": self.origin - 4 * charts.HOUR, "close_cny": "98"},
                        {"bucket_time": self.origin - charts.HOUR, "close_cny": "100"}]
        self.forecast = [{"origin_time": self.origin, "target_time": self.origin + d * charts.DAY,
                          "horizon_days": d, "selected_model": "log_drift_7d",
                          "prediction": 100 + d, "persistence_prediction": 100,
                          "generated_at_beijing": "2026-10-19T15:00:00+08:00"} for d in range(8)]
        self.test = [{"origin_time": self.origin + d * charts.DAY,
                      "target_time": self.origin + (d + 7) * charts.DAY,
                      "actual": 100 + d, "prediction": 101 + d,
                      "persistence_prediction": 100} for d in (0, 1, 3)]

    def tearDown(self):
        plt.close("all")

    def test_holdout_targets_are_seven_days_after_origins_and_gaps_break(self):
        fig = charts.plot_holdout(self.test, selected_model="log_drift_7d")
        self.assertEqual(len(fig.axes), 2)
        self.assertEqual(len(fig.axes[0].lines), 3)
        line = fig.axes[0].lines[0]
        xs, ys = line.get_xdata(), line.get_ydata()
        self.assertEqual(int(xs[0].timestamp()), self.test[0]["target_time"])
        self.assertTrue(math.isnan(ys[2]))
        self.assertEqual(len(ys), 4)
        self.assertEqual(list(fig.axes[1].lines[0].get_ydata())[:2], [1, 1])

    def test_wrong_horizon_rejected(self):
        self.test[0]["target_time"] += charts.HOUR
        with self.assertRaises(ValueError):
            charts.plot_holdout(self.test, selected_model="persistence")

    def test_projection_has_only_past_actuals_and_daily_forecast_points(self):
        fig = charts.plot_projection(self.history, self.forecast)
        ax = fig.axes[0]
        self.assertEqual(len(ax.lines), 4)  # history, selected, persistence, origin
        history_line, forecast_line, baseline_line, origin_line = ax.lines
        self.assertTrue(math.isnan(history_line.get_ydata()[1]))
        self.assertEqual(max(x.timestamp() for x in history_line.get_xdata()), self.origin)
        self.assertEqual(len(forecast_line.get_xdata()), 8)
        self.assertEqual(int(forecast_line.get_xdata()[-1].timestamp()), self.origin + 7 * charts.DAY)
        self.assertEqual(origin_line.get_xdata()[0].timestamp(), self.origin)
        self.assertEqual(set(baseline_line.get_ydata()), {100})
        self.assertTrue(any("2026-10-19T15:00:00+08:00" in t.get_text() for t in fig.texts))

    def test_future_actuals_rejected(self):
        with self.assertRaises(ValueError):
            charts.plot_projection(self.history + [{"bucket_time": self.origin, "close_cny": 900}], self.forecast)
        with self.assertRaises(ValueError):
            charts.plot_projection(self.history, self.forecast, lookback_days=0)

    def test_duplicate_time_rejected(self):
        with self.assertRaises(ValueError):
            charts.plot_projection(self.history + self.history[:1], self.forecast)

    def test_english_fallback_does_not_require_chinese_font(self):
        with patch.object(charts, "_font", return_value=("DejaVu Sans", False)):
            fig = charts.plot_projection(self.history, self.forecast)
            self.assertIn("Cyrex FN", fig.axes[0].get_title())

    def test_selected_historical_origin_uses_only_past_features_with_locked_rule(self):
        base = charts.ROOT / "data/local/reports"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="chart_origin_test_", dir=base) as temporary:
            directory = Path(temporary).resolve()
            self.assertTrue(directory.is_relative_to(base.resolve()))
            sample = {"decision_time": self.origin, "feature_complete": "True",
                      "x_reference_close": 100, "x_return_7d": .07,
                      "y_source_close_7d": 999999}
            source = [*self.history, {"bucket_time": self.origin + charts.HOUR, "close_cny": 888888}]
            outputs = {}
            for name, rows in (("samples.csv", [sample]), ("source_hourly.csv", source)):
                with (directory / name).open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                outputs[name] = {"sha256": hashlib.sha256((directory / name).read_bytes()).hexdigest()}
            parent = directory / "manifest.json"
            parent.write_text(json.dumps({"outputs": outputs}), encoding="utf-8")
            manifest = {"selected_model": "log_drift_7d", "input_candidate": {
                "manifest": str(parent), "manifest_sha256": hashlib.sha256(parent.read_bytes()).hexdigest()}}
            result = charts.projection_data(manifest, self.origin, loaded={})
            self.assertEqual(len(result["history"]), 2)
            self.assertAlmostEqual(result["forecast"][-1]["prediction"], 107)
            self.assertEqual(result["forecast"][-1]["persistence_prediction"], 100)
            self.assertTrue(all(int(row["bucket_time"]) < self.origin for row in result["history"]))
            with self.assertRaises(ValueError):
                charts.projection_data(manifest, self.origin + charts.DAY, loaded={})

    def test_source_snapshot_includes_actual_local_predictor_and_package_initializers(self):
        default = charts._source_bytes(False)
        custom = charts._source_bytes(True)
        for name in ("scripts/research/visualization/forecast_charts.py",
                     "scripts/research/visualization/__init__.py", "scripts/research/__init__.py"):
            self.assertIn(name, default)
            self.assertIn(name, custom)
        self.assertNotIn("scripts/research/models/baselines.py", default)
        self.assertIn("scripts/research/models/baselines.py", custom)
        self.assertIn("scripts/research/models/__init__.py", custom)
        self.assertTrue(set(default).issubset(custom))

    def test_render_creates_nonempty_pngs_separate_from_evaluation_and_no_overwrite(self):
        base = charts.ROOT / "data/local/reports"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="chart_test_", dir=base) as temporary:
            root = Path(temporary).resolve()
            self.assertTrue(root.is_relative_to(base.resolve()))
            evaluation = root / "evaluation"
            evaluation.mkdir()
            tables = {"history": self.history, "forecast": self.forecast,
                      "test_predictions": self.test}
            files = {}
            outputs = {}
            for key, rows in tables.items():
                filename = f"{key}.csv"
                with (evaluation / filename).open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                files[key] = filename
            (evaluation / "metrics.json").write_text("{}", encoding="utf-8")
            files["metrics"] = "metrics.json"
            for path in evaluation.iterdir():
                outputs[path.name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            before = {p.name: p.read_bytes() for p in evaluation.iterdir()}
            manifest = {"output_id": "synthetic", "output_dir": str(evaluation), "selected_model": "log_drift_7d",
                        "generated_at_beijing": "2026-10-19T15:00:00+08:00", "files": files, "outputs": outputs}
            with patch.object(charts, "OUTPUT_BASE", root / "charts"):
                result = charts.render(manifest, output_id="report")
                for path in result["paths"].values():
                    image = Path(path)
                    self.assertGreater(image.stat().st_size, 1000)
                    self.assertEqual(image.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
                self.assertTrue((Path(result["output_dir"]) / "manifest.json").is_file())
                self.assertEqual(result["manifest"]["version"], "forecast-charts-1.1")
                for source_name, entry in result["manifest"]["source_files"].items():
                    source_path = Path(result["output_dir"]) / "source" / source_name
                    self.assertEqual(hashlib.sha256(source_path.read_bytes()).hexdigest(), entry["sha256"])
                    self.assertIn("source/" + source_name, result["manifest"]["outputs"])
                with self.assertRaises(FileExistsError):
                    charts.render(manifest, output_id="report")
            self.assertEqual(before, {p.name: p.read_bytes() for p in evaluation.iterdir()})
            (evaluation / "history.csv").write_text("corrupt", encoding="utf-8")
            with self.assertRaises(ValueError):
                charts.load_evaluation(manifest)


if __name__ == "__main__":
    unittest.main()
