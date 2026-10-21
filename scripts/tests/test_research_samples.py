"""Offline checks for causal daily samples; no network or production database."""

from __future__ import annotations

import copy
from contextlib import closing
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
import statistics
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts.research.data import daily_samples as sample_builder


ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "scripts/config/cyrex_daily_spec.json").read_text(encoding="utf-8"))
HOUR = 3600
DAY = 24 * HOUR


def epoch(value: str) -> int:
    return int(datetime.fromisoformat(value).timestamp())


class DailySampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = epoch("2026-06-01T10:00:00+08:00")
        cls.cutoff = epoch("2026-07-25T10:00:00+08:00")
        cls.decision = epoch("2026-07-04T10:00:00+08:00")
        cls.hour_rows = []
        for number, bucket in enumerate(range(cls.start, cls.cutoff, HOUR)):
            close = 100 + number / 100
            cls.hour_rows.append({
                "bucket_time": bucket,
                "open_cny": str(close - 0.1),
                "close_cny": str(close),
                "high_cny": str(close + 0.3),
                "low_cny": str(close - 0.4),
                "source_volume": 2,
                "source_turnover_cny": str(close * 2),
            })
        cls.by_time = {row["bucket_time"]: row for row in cls.hour_rows}

    def build_rows(self, rows=None, spec=None, cutoff=None):
        return sample_builder.build_rows(
            self.hour_rows if rows is None else rows,
            copy.deepcopy(SPEC) if spec is None else spec,
            self.cutoff if cutoff is None else cutoff,
        )

    def sample_at(self, samples, decision=None):
        selected = self.decision if decision is None else decision
        matches = [row for row in samples if row["decision_time"] == selected]
        self.assertEqual(len(matches), 1, "Each daily decision must be retained exactly once")
        return matches[0]

    def sample_sequence(self, sequence, sample):
        return sorted(
            (row for row in sequence if row["sample_id"] == sample["sample_id"]),
            key=lambda row: row["sequence_index"],
        )

    def test_past_only_exact_hour_boundaries_and_feature_values(self):
        samples, sequences, _ = self.build_rows()
        row = self.sample_at(samples)
        reference = float(self.by_time[self.decision - HOUR]["close_cny"])
        self.assertTrue(row["feature_complete"])
        self.assertAlmostEqual(row["x_reference_close"], reference)
        for days in (1, 3, 7, 14):
            earlier = float(self.by_time[self.decision - days * DAY - HOUR]["close_cny"])
            self.assertAlmostEqual(row[f"x_return_{days}d"], reference / earlier - 1)
        for days in (7, 14, 28):
            closes = [float(self.by_time[self.decision - day * DAY - HOUR]["close_cny"])
                      for day in range(days)]
            self.assertAlmostEqual(row[f"x_ma_ratio_{days}d"], reference / (sum(closes) / len(closes)) - 1)
        for days in (7, 14):
            closes = [float(self.by_time[self.decision - day * DAY - HOUR]["close_cny"])
                      for day in reversed(range(days + 1))]
            returns = [math.log(later / earlier) for earlier, later in zip(closes, closes[1:])]
            self.assertAlmostEqual(row[f"x_vol_{days}d"], statistics.pstdev(returns))
        range_hours = [self.by_time[bucket] for bucket in range(self.decision - 7 * DAY, self.decision, HOUR)]
        self.assertAlmostEqual(row["x_range_7d"],
                               max(float(hour["high_cny"]) for hour in range_hours)
                               / min(float(hour["low_cny"]) for hour in range_hours) - 1)
        seq = self.sample_sequence(sequences, row)
        self.assertEqual(len(seq), 28)
        self.assertEqual([part["sequence_index"] for part in seq], list(range(28)))
        self.assertEqual(seq[0]["period_start"], self.decision - 28 * DAY)
        self.assertEqual(seq[-1]["period_end"], self.decision)
        self.assertTrue(all(part["observed_hours"] == 24 for part in seq))

    def test_future_changes_do_not_change_predictors_or_past_sequence(self):
        original, original_sequence, _ = self.build_rows()
        changed = copy.deepcopy(self.hour_rows)
        for hour in changed:
            if hour["bucket_time"] >= self.decision:
                hour.update(open_cny="8000", close_cny="9000", high_cny="10000", low_cny="7000")
        revised, revised_sequence, _ = self.build_rows(changed)
        before, after = self.sample_at(original), self.sample_at(revised)
        self.assertEqual({key: value for key, value in before.items() if key.startswith("x_")},
                         {key: value for key, value in after.items() if key.startswith("x_")})
        self.assertEqual(self.sample_sequence(original_sequence, before),
                         self.sample_sequence(revised_sequence, after))
        self.assertNotEqual(before["y_source_close_7d"], after["y_source_close_7d"])

    def test_label_uses_full_future_window_and_last_completed_hour(self):
        target = self.decision + 7 * DAY
        samples, _, _ = self.build_rows(cutoff=target)
        row = self.sample_at(samples)
        reference = float(self.by_time[self.decision - HOUR]["close_cny"])
        target_close = float(self.by_time[target - HOUR]["close_cny"])
        future_low = min(float(self.by_time[bucket]["low_cny"])
                         for bucket in range(self.decision, target, HOUR))
        self.assertEqual(row["target_time"], target)
        self.assertEqual(row["label_status"], "ready")
        self.assertAlmostEqual(row["y_source_close_7d"], target_close)
        self.assertAlmostEqual(row["y_source_return_7d"], target_close / reference - 1)
        self.assertAlmostEqual(row["y_min_source_low_return_7d"], future_low / reference - 1)

    def test_pending_decision_is_retained_and_future_input_cannot_mature_it(self):
        target = self.decision + 7 * DAY
        samples, _, _ = self.build_rows(cutoff=target - HOUR)
        row = self.sample_at(samples)
        self.assertTrue(row["feature_complete"])
        self.assertEqual(row["label_status"], "pending_future")
        self.assertFalse(row["eligible"])
        for field in ("y_source_close_7d", "y_source_return_7d", "y_min_source_low_return_7d"):
            self.assertIsNone(row[field])
        samples_at_end, _, _ = self.build_rows()
        current = self.sample_at(samples_at_end, self.cutoff)
        self.assertEqual(current["label_status"], "pending_future")

    def test_missing_past_hour_blanks_predictors_and_affected_segment(self):
        rows = [row for row in self.hour_rows if row["bucket_time"] != self.decision - 10 * HOUR]
        samples, sequence, _ = self.build_rows(rows)
        row = self.sample_at(samples)
        self.assertFalse(row["feature_complete"])
        self.assertFalse(row["eligible"])
        for field, value in row.items():
            if field.startswith("x_"):
                self.assertIsNone(value, field)
        last = self.sample_sequence(sequence, row)[-1]
        self.assertEqual(last["observed_hours"], 23)
        for field in ("open_cny", "close_cny", "high_cny", "low_cny", "source_volume", "source_turnover_cny"):
            self.assertIsNone(last[field], field)

    def test_missing_future_hour_is_gap_instead_of_a_fabricated_label(self):
        rows = [row for row in self.hour_rows if row["bucket_time"] != self.decision + 10 * HOUR]
        samples, _, _ = self.build_rows(rows)
        row = self.sample_at(samples)
        self.assertTrue(row["feature_complete"])
        self.assertEqual(row["label_status"], "future_gap")
        self.assertFalse(row["eligible"])
        for field in ("y_source_close_7d", "y_source_return_7d", "y_min_source_low_return_7d"):
            self.assertIsNone(row[field])

    def test_missing_reference_hour_cannot_produce_a_return_label(self):
        rows = [row for row in self.hour_rows if row["bucket_time"] != self.decision - HOUR]
        samples, _, _ = self.build_rows(rows)
        row = self.sample_at(samples)
        self.assertFalse(row["feature_complete"])
        self.assertEqual(row["label_status"], "reference_gap")
        self.assertFalse(row["eligible"])
        for field in ("y_source_close_7d", "y_source_return_7d", "y_min_source_low_return_7d"):
            self.assertIsNone(row[field])

    def test_unknown_flow_remains_null_without_polluting_price_features(self):
        rows = copy.deepcopy(self.hour_rows)
        for hour in rows:
            if hour["bucket_time"] == self.decision - 2 * HOUR:
                hour["source_volume"] = None
                hour["source_turnover_cny"] = None
        original, _, _ = self.build_rows()
        samples, sequence, _ = self.build_rows(rows)
        row, before = self.sample_at(samples), self.sample_at(original)
        self.assertTrue(row["feature_complete"])
        self.assertEqual({key: value for key, value in before.items() if key.startswith("x_")},
                         {key: value for key, value in row.items() if key.startswith("x_")})
        self.assertFalse(any("volume" in key or "turnover" in key for key in row if key.startswith("x_")))
        last = self.sample_sequence(sequence, row)[-1]
        self.assertEqual(last["observed_hours"], 24)
        self.assertEqual(last["known_volume_hours"], 23)
        self.assertEqual(last["known_turnover_hours"], 23)
        self.assertIsNone(last["source_volume"])
        self.assertIsNone(last["source_turnover_cny"])

    def test_chronological_splits_purge_labels_crossing_next_boundary(self):
        spec = copy.deepcopy(SPEC)
        spec["validation_start_beijing"] = "2026-07-08T10:00:00+08:00"
        spec["test_start_beijing"] = "2026-07-16T10:00:00+08:00"
        samples, _, _ = self.build_rows(spec=spec)
        expected = [
            ("2026-06-30T10:00:00+08:00", "train", False),
            ("2026-07-01T10:00:00+08:00", "train", True),
            ("2026-07-08T10:00:00+08:00", "validation", False),
            ("2026-07-09T10:00:00+08:00", "validation", True),
            ("2026-07-16T10:00:00+08:00", "test", False),
        ]
        for time, split, purged in expected:
            with self.subTest(time=time):
                row = self.sample_at(samples, epoch(time))
                self.assertEqual(row["split"], split)
                self.assertEqual(row["purged"], purged)
                self.assertEqual(row["eligible"], not purged)

    def test_frozen_request_cap_read_only_build_and_no_overwrite(self):
        temporary_root = ROOT / "data/local/staging/research_samples"
        temporary_root.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="_offline_test_", dir=temporary_root)
        temporary_path = Path(temporary.name).resolve()
        self.assertTrue(temporary_path.is_relative_to(temporary_root.resolve()))
        try:
            source_root = temporary_path / "sources"
            workspace = source_root / "research_fixture"
            workspace.mkdir(parents=True)
            database = workspace / "research.sqlite"
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript("""
                    CREATE TABLE requests(request_id INTEGER PRIMARY KEY);
                    INSERT INTO requests VALUES(1);
                    CREATE TABLE research_bar_versions(
                        version_id INTEGER PRIMARY KEY,
                        market_hash_name TEXT, platform TEXT, period TEXT, style TEXT,
                        source_time INTEGER, bucket_time INTEGER,
                        open_cny TEXT, close_cny TEXT, high_cny TEXT, low_cny TEXT,
                        source_volume INTEGER, source_turnover_cny TEXT, source_request INTEGER);
                """)
                connection.executemany("INSERT INTO research_bar_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                    (number, SPEC["market_hash_name"], "YOUPIN", "1h", "", row["bucket_time"],
                     row["bucket_time"], row["open_cny"], row["close_cny"], row["high_cny"],
                     row["low_cny"], row["source_volume"], row["source_turnover_cny"], 1)
                    for number, row in enumerate(self.hour_rows, 1)
                ])
                connection.commit()
            (workspace / "latest_report.json").write_text(json.dumps({"report": "report.json"}), encoding="utf-8")
            (workspace / "report.json").write_text(json.dumps({
                "workspace_http_attempts_archived": 1,
                "integrity": "ok",
                "run": {"end_exclusive": self.cutoff, "status": "completed"},
            }), encoding="utf-8")
            digest_before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.multiple(sample_builder, BASE=temporary_path / "outputs", SOURCE_BASE=source_root):
                first = sample_builder.build("research_fixture", "first", ROOT / "scripts/config/cyrex_daily_spec.json")
                self.assertEqual(first["version"], "cyrex-daily-samples-1.1")
                self.assertEqual(set(first["code_files"]), set(sample_builder.CODE_FILES))
                self.assertEqual(first["code_sha256"], first["code_files"][sample_builder.CODE_PATH]["sha256"])
                for relative, item in first["code_files"].items():
                    snapshot = Path(first["output_dir"]) / item["snapshot"]
                    self.assertEqual(snapshot.read_bytes(), (ROOT / relative).read_bytes())
                    self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(), item["sha256"])
                    self.assertIn(item["snapshot"], first["outputs"])
                self.assertTrue(first["source_database_unchanged"])
                self.assertFalse(first["training_approved"])
                self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), digest_before)
                first_csv = (Path(first["output_dir"]) / "source_hourly.csv").read_bytes()
                with self.assertRaises(FileExistsError):
                    sample_builder.build("research_fixture", "first", ROOT / "scripts/config/cyrex_daily_spec.json")
                self.assertEqual((Path(first["output_dir"]) / "source_hourly.csv").read_bytes(), first_csv)
                with closing(sqlite3.connect(database)) as connection:
                    connection.execute("INSERT INTO requests VALUES(2)")
                    connection.execute("""INSERT INTO research_bar_versions
                        SELECT 999999,market_hash_name,platform,period,style,source_time,bucket_time,
                               '9000','9000','9000','9000',source_volume,source_turnover_cny,2
                        FROM research_bar_versions WHERE version_id=1""")
                    connection.commit()
                revised_digest = hashlib.sha256(database.read_bytes()).hexdigest()
                second = sample_builder.build("research_fixture", "second", ROOT / "scripts/config/cyrex_daily_spec.json")
                self.assertEqual(second["source_request_cap"], 1)
                self.assertEqual((Path(second["output_dir"]) / "source_hourly.csv").read_bytes(), first_csv)
                self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), revised_digest)
                self.assertEqual(sample_builder.status()["output_id"], "second")
        finally:
            self.assertTrue(temporary_path.is_relative_to(temporary_root.resolve()))
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
