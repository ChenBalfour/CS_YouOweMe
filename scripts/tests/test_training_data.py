"""Synthetic checks for immutable inputs and training-only model adapters."""
from __future__ import annotations

import copy
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

try:
    import numpy as np
    from scripts.research.data import training_data as data
    from scripts.research.data.model_preprocessing import TrainOnlyPreprocessor
except ImportError:
    np = None


ROOT = Path(__file__).resolve().parents[2]
HOUR = 3600
ORIGIN = int(datetime.fromisoformat("2026-01-01T10:00:00+08:00").timestamp())


def sample(index=0, **updates):
    row = {field: float(index + 1) for field in data.FEATURE_FIELDS}
    row.update(market_hash_name=f"Synthetic item {index}", steamdt_item_id=str(100 + index),
               uu_template_id=str(200 + index), decision_time=ORIGIN, split="train", purged=0,
               eligible_point_quality=1, eligible_point_strict=1, x_reference_close=100.0,
               reference_close_cny="100", reference_bucket_time=ORIGIN - HOUR,
               target_time=ORIGIN + 168 * HOUR, target_bucket_time=ORIGIN + 167 * HOUR,
               y_return_7d=0.05, y_reference_close_7d="105", point_label_available=1)
    row.update(updates)
    return row


def hours(rows, gap=None):
    return {row["market_hash_name"]: [
        {"market_hash_name": row["market_hash_name"], "bucket_time": ORIGIN + i * HOUR,
         "close_cny": "100", "high_cny": "101", "low_cny": "99",
         "observed": int(i != gap), "price_valid": int(i != gap)}
        for i in range(-672, 1)] for row in rows}


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outputs(root):
    return {p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": digest(p)}
            for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"}


def sqlite_table(connection, name, rows):
    fields = list(rows[0])
    def kind(value):
        return "INTEGER" if isinstance(value, int) else "REAL" if isinstance(value, float) else "TEXT"
    connection.execute(f'CREATE TABLE "{name}" (' + ",".join(f'"{f}" {kind(rows[0][f])}' for f in fields) + ")")
    marks = ",".join("?" for _ in fields)
    connection.executemany(f'INSERT INTO "{name}" VALUES ({marks})', [[row.get(f) for f in fields] for row in rows])


def frozen_fixture(base):
    """Minimal frozen source built locally; no private production dataset needed."""
    clean_root, sample_root = base / "clean" / "parent", base / "daily" / "sample"
    cutoff = ORIGIN + 193 * HOUR
    item = {"market_hash_name": "Synthetic item 0", "steamdt_item_id": "100", "uu_template_id": "200",
            "name_zh": "Synthetic", "start_time": ORIGIN - 672 * HOUR}
    hourly = [{"market_hash_name": item["market_hash_name"], "bucket_time": time,
               "observed": 1, "price_valid": 1, "close_cny": "100", "high_cny": "101", "low_cny": "99"}
              for time in range(item["start_time"], cutoff, HOUR)]
    for root in (clean_root, sample_root):
        (root / "source/code").mkdir(parents=True)
        (root / "source/code/synthetic.py").write_text("# snapshot only; never executed\n", encoding="utf-8")
    parent_spec = {"purpose": "synthetic"}
    dump(clean_root / "source/spec.json", parent_spec)
    with closing(sqlite3.connect(clean_root / "clean.sqlite")) as connection:
        sqlite_table(connection, "items", [item])
        sqlite_table(connection, "hourly", hourly)
        connection.commit()
    parent = {"version": "steamdt-hourly-cleaning-1.0", "status": "frozen_research_cleaning_candidate",
              "output_id": "parent", "database": "clean.sqlite", "source_cutoff_exclusive": cutoff,
              "source_request_cap": 1, "spec": parent_spec, "spec_sha256": digest(clean_root / "source/spec.json"),
              "code_files": {"synthetic.py": digest(clean_root / "source/code/synthetic.py")},
              "outputs": outputs(clean_root)}
    dump(clean_root / "manifest.json", parent)
    spec = {"platform": "YOUPIN", "period": "1h", "style": "", "lookback_days": 28,
            "horizon_days": 7, "impute_prices": False,
            "validation_start_beijing": "2026-02-01T10:00:00+08:00",
            "test_start_beijing": "2026-03-01T10:00:00+08:00",
            "test_usage": "exploratory_already_viewed_no_new_independent_holdout"}
    dump(sample_root / "source/spec.json", spec)
    (sample_root / "source/parent_manifest.json").write_bytes((clean_root / "manifest.json").read_bytes())
    rows = [sample(), sample(decision_time=ORIGIN + 24 * HOUR, reference_bucket_time=ORIGIN + 23 * HOUR,
                             target_time=ORIGIN + 192 * HOUR, target_bucket_time=ORIGIN + 191 * HOUR)]
    with closing(sqlite3.connect(sample_root / "samples.sqlite")) as connection:
        sqlite_table(connection, "items", [item])
        sqlite_table(connection, "samples", rows)
        connection.commit()
    manifest = {"version": "seven-daily-samples-1.0", "status": "frozen_retrospective_feature_label_candidate",
                "output_id": "sample", "dataset_id": "sample", "database": "samples.sqlite",
                "parent_clean_id": "parent", "parent_manifest_sha256": digest(clean_root / "manifest.json"),
                "parent_database_sha256": digest(clean_root / "clean.sqlite"),
                "source_cutoff_exclusive": cutoff, "source_request_cap": 1, "spec": spec,
                "spec_sha256": digest(sample_root / "source/spec.json"), "feature_fields": list(data.FEATURE_FIELDS),
                "code_files": {"synthetic.py": digest(sample_root / "source/code/synthetic.py")},
                "summary": {"item_count": 1, "samples": 2}, "outputs": outputs(sample_root),
                "historical_available_at_verified": False, "training_approved": False}
    dump(sample_root / "manifest.json", manifest)
    return clean_root.parent, sample_root.parent, sample_root


@unittest.skipIf(np is None, "optional numpy training dependency is not installed")
class TrainingDataTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "data/local").mkdir(parents=True, exist_ok=True)

    def test_train_only_fit_and_transform_cannot_change_training_statistics(self):
        rows = [sample(i) for i in range(7)]
        rows[0]["x_return_1d"] = None
        for row in rows:
            row["x_peer_median_return_7d"] = None
        sequence = data.build_sequences(rows, hours(rows))
        processor = TrainOnlyPreprocessor().fit_rows(rows, sequences=sequence)
        before = processor.to_dict()
        validation = [dict(rows[0], split="validation", x_return_1d=1e8)]
        processor.transform_rows(validation, sequences=sequence[:1])
        self.assertEqual(before, processor.to_dict())
        self.assertEqual(before["tabular_statistics"]["median"][1], 4.5)
        for change in ({"split": "validation"}, {"split": "test"}, {"purged": 1}, {"eligible_point_quality": 0}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                TrainOnlyPreprocessor().fit_rows([dict(rows[0], **change)])
        with self.assertRaises(ValueError):
            processor.fit_rows(rows)
        transformed = processor.transform_rows(rows, sequences=sequence)
        self.assertEqual(transformed["tabular"].shape, (7, 49))
        self.assertEqual(transformed["sequence"].shape, (7, 672, 6))
        self.assertTrue(np.isfinite(transformed["tabular"]).all())
        self.assertTrue(np.isfinite(transformed["sequence"]).all())
        self.assertEqual(transformed["tabular"][0, 22], 1)
        self.assertTrue(before["tabular_statistics"]["all_missing"][19])
        self.assertEqual(before["tabular_statistics"]["median"][19], 0)
        self.assertEqual(processor.transform_tabular(rows, for_tree=True).shape, (7, 28))
        self.assertTrue(np.isnan(processor.transform_tabular(rows, for_tree=True)[:, 19]).all())
        self.assertNotIn("target", transformed)
        with self.assertRaises(ValueError):
            processor.transform_tabular([dict(rows[0], market_hash_name="Unseen")])

    def test_json_roundtrip_and_stored_identity_validation(self):
        rows = [sample()]
        sequence = data.build_sequences(rows, hours(rows))
        processor = TrainOnlyPreprocessor().fit_rows(rows, sequences=sequence)
        with tempfile.TemporaryDirectory(prefix="prp_", dir=ROOT / "data/local") as tmp:
            path = Path(tmp) / "p.json"
            processor.save(path)
            restored = TrainOnlyPreprocessor.load(path)
            np.testing.assert_array_equal(processor.transform_tabular(rows), restored.transform_tabular(rows))
            np.testing.assert_array_equal(processor.transform_sequences(sequence), restored.transform_sequences(sequence))
            with self.assertRaises(FileExistsError):
                processor.save(path)
        state = processor.to_dict()
        state["fit_row_keys"][0][1] += HOUR
        with self.assertRaises(ValueError):
            TrainOnlyPreprocessor.from_dict(state)

    def test_past_sequence_exact_grid_no_gap_return_and_future_isolation(self):
        rows = [sample()]
        series = hours(rows, gap=-200)
        expected = data.build_sequences(rows, series)
        self.assertTrue(np.isnan(expected[0, 0, 1]))
        self.assertTrue(np.isnan(expected[0, 472, :]).all())
        self.assertTrue(np.isnan(expected[0, 473, 1]))
        self.assertTrue(np.isfinite(expected[0, 474, 1]))
        altered = copy.deepcopy(series)
        altered[rows[0]["market_hash_name"]][-1].update(close_cny="999999", high_cny="999999", low_cny="999999")
        poisoned_labels = [dict(rows[0], y_return_7d=9999, target_time=-100)]
        np.testing.assert_array_equal(expected, data.build_sequences(poisoned_labels, altered))
        whitelist = data.prediction_rows(rows)[0]
        self.assertFalse(any(key.startswith(("y_", "target_", "eligible_")) for key in whitelist))
        self.assertNotIn("target", data.prepare_rows(rows))
        self.assertEqual(data.prepare_rows(rows, include_labels=True)["target"][0], .05)

    def test_immutable_loader_hashes_profiles_and_read_only_sqlite(self):
        (ROOT / "data/local").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="td_", dir=ROOT / "data/local") as tmp:
            clean_base, daily_base, sample_root = frozen_fixture(Path(tmp))
            before = {p: digest(p) for p in Path(tmp).rglob("*") if p.is_file()}
            connect = sqlite3.connect
            calls = []
            def checked_connect(database_uri, *args, **kwargs):
                calls.append(database_uri)
                self.assertIn("?mode=ro", database_uri)
                self.assertTrue(kwargs.get("uri"))
                return connect(database_uri, *args, **kwargs)
            with patch.object(data, "BASE", daily_base), patch.object(data, "CLEAN_BASE", clean_base):
                with patch.object(data.sqlite3, "connect", side_effect=checked_connect):
                    bundle = data.load_dataset("sample")
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(bundle["splits"]["train"]), 2)
                self.assertEqual(set(bundle["splits"]), {"train", "validation", "test_exploratory"})
                self.assertFalse(bundle["provenance"]["source_training_approved"])
                self.assertEqual(len(data.load_dataset("sample", profile="strict", include_hourly=False)["rows"]), 2)
                with self.assertRaises(ValueError):
                    data.load_dataset("sample", profile="unsupported")
                with self.assertRaises(ValueError):
                    data.load_dataset("../sample")
                self.assertEqual(before, {p: digest(p) for p in Path(tmp).rglob("*") if p.is_file()})
                (sample_root / "source/code/synthetic.py").write_text("tampered", encoding="utf-8")
                with self.assertRaises(ValueError):
                    data.load_dataset("sample")


if __name__ == "__main__":
    unittest.main()
