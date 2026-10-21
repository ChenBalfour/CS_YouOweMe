"""Independent synthetic checks for the cleaned multi-item sample pipeline."""
from __future__ import annotations

import copy
from contextlib import closing
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import statistics
import tempfile
import unittest
from unittest.mock import patch

from scripts.research.data import clean_hourly as cleaner
from scripts.research.data import seven_samples as builder


ROOT = Path(__file__).resolve().parents[2]
HOUR, DAY = 3600, 86400


def epoch(value):
    return int(datetime.fromisoformat(value).timestamp())


START = epoch("2026-06-01T10:00:00+08:00")
CUTOFF = START + 42 * DAY
DECISION = epoch("2026-07-04T10:00:00+08:00")
ITEMS = [
    {"market_hash_name": "Synthetic item A (Factory New)", "steamdt_item_id": "101",
     "uu_template_id": "201", "name_zh": "合成商品甲", "history_start": "2026-06-01", "enabled": True},
    {"market_hash_name": "Synthetic item B (Field-Tested)", "steamdt_item_id": "102",
     "uu_template_id": "202", "name_zh": "合成商品乙", "history_start": "2026-06-01", "enabled": True},
]


def raw_rows(item, multiplier=1):
    result = []
    for index, bucket in enumerate(range(START, CUTOFF, HOUR)):
        price = multiplier * (100 + index / 100)
        result.append({
            "version_id": index + 1 + (0 if multiplier == 1 else 10000),
            "market_hash_name": item["market_hash_name"], "platform": "YOUPIN", "period": "1h", "style": "",
            "bucket_time": bucket, "source_time": bucket, "source_request": 1,
            "open_cny": str(price), "close_cny": str(price),
            "high_cny": str(price + 0.2), "low_cny": str(price - 0.2),
            "source_volume": None, "source_turnover_cny": None,
        })
    return result


def mask_hour(rows, bucket):
    result = copy.deepcopy(rows)
    row = next(row for row in result if row["bucket_time"] == bucket)
    row.update(observed=0, price_valid=0, open_cny=None, close_cny=None,
               high_cny=None, low_cny=None, source_volume=None, source_turnover_cny=None,
               volume_missing=1, turnover_missing=1)
    return result


def set_price(row, value):
    row.update(open_cny=str(value), close_cny=str(value),
               high_cny=str(value), low_cny=str(value))


class SevenSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hours = [cleaner.clean_rows(raw_rows(item, index + 1), item, START, CUTOFF,
                                        copy.deepcopy(cleaner.EXPECTED_SPEC))
                     for index, item in enumerate(ITEMS)]

    def rows(self, hours=None, *, item=0, cutoff=CUTOFF, spec=None):
        hours = self.hours[item] if hours is None else hours
        return builder.compute_item_samples(
            [row for row in hours if row["bucket_time"] < cutoff],
            {**ITEMS[item], "start_time": START},
            copy.deepcopy(builder.EXPECTED_SPEC) if spec is None else spec, cutoff)

    def at(self, rows, decision=DECISION):
        matches = [row for row in rows if row["decision_time"] == decision]
        self.assertEqual(len(matches), 1, "A decision must be retained once per item")
        return matches[0]

    def features(self, row):
        return {key: row.get(key) for key in builder.FEATURE_FIELDS}

    def test_future_prices_do_not_change_past_features_or_input_quality(self):
        before = self.at(self.rows())
        changed = copy.deepcopy(self.hours[0])
        for row in changed:
            if row["bucket_time"] >= DECISION:
                set_price(row, 9000)
        after = self.at(self.rows(changed))
        self.assertEqual(self.features(before), self.features(after))
        self.assertEqual(before["strict_input_complete"], after["strict_input_complete"])
        self.assertEqual(before["input_quality_pass"], after["input_quality_pass"])
        self.assertNotEqual(before["y_reference_close_7d"], after["y_reference_close_7d"])

    def test_complete_features_use_exact_hourly_prices_and_past_windows(self):
        row = self.at(self.rows())
        lookup = {hour["bucket_time"]: hour for hour in self.hours[0]}
        reference = float(lookup[DECISION - HOUR]["close_cny"])
        self.assertEqual(row["x_reference_close"], reference)
        for days in (1, 3, 7, 14):
            old = float(lookup[DECISION - days * DAY - HOUR]["close_cny"])
            self.assertAlmostEqual(row[f"x_return_{days}d"], reference / old - 1)
        for days in (7, 14, 28):
            prices = [float(lookup[bucket]["close_cny"])
                      for bucket in range(DECISION - days * DAY, DECISION, HOUR)]
            self.assertAlmostEqual(row[f"x_ma_ratio_{days}d"], reference / statistics.mean(prices) - 1)
        self.assertEqual(row["x_price_coverage_28d"], 1)
        self.assertEqual(row["x_longest_missing_hours_28d"], 0)
        self.assertEqual(row["x_price_age_hours"], 0)

    def test_hourly_returns_and_volatility_do_not_bridge_missing_hours(self):
        missing = DECISION - 70 * HOUR
        changed = mask_hour(self.hours[0], missing)
        for bucket, price in ((missing - HOUR, 100), (missing + HOUR, 500)):
            set_price(next(row for row in changed if row["bucket_time"] == bucket), price)
        sample = self.at(self.rows(changed))
        week = [row for row in changed if DECISION - 7 * DAY <= row["bucket_time"] < DECISION]
        pairs = [(left, right) for left, right in zip(week, week[1:])
                 if left["price_valid"] and right["price_valid"]]
        returns = [float(right["close_cny"]) / float(left["close_cny"]) - 1 for left, right in pairs]
        log_returns = [math.log(float(right["close_cny"]) / float(left["close_cny"]))
                       for left, right in pairs]
        self.assertEqual(len(pairs), 165)
        self.assertAlmostEqual(sample["x_adjacent_return_coverage_7d"], 165 / 167)
        self.assertAlmostEqual(sample["x_vol_7d"], statistics.stdev(log_returns))
        self.assertAlmostEqual(sample["x_min_hourly_return_7d"], min(returns))
        self.assertAlmostEqual(sample["x_max_hourly_return_7d"], max(returns))

    def test_sparse_window_has_no_invented_volatility_or_leading_price(self):
        changed = copy.deepcopy(self.hours[0])
        for hour in changed:
            if DECISION - 28 * DAY <= hour["bucket_time"] < DECISION - 2 * HOUR:
                hour.update(observed=0, price_valid=0, open_cny=None, close_cny=None,
                            high_cny=None, low_cny=None, source_volume=None, source_turnover_cny=None)
        sample = self.at(self.rows(changed))
        self.assertIsNone(sample["x_vol_7d"])
        self.assertIsNone(sample["x_vol_14d"])
        self.assertIsNone(sample["x_return_1d"])
        self.assertEqual(sample["x_longest_missing_hours_28d"], 670)
        self.assertFalse(sample["input_quality_pass"])
        changed = mask_hour(mask_hour(changed, DECISION - 2 * HOUR), DECISION - HOUR)
        sample = self.at(self.rows(changed))
        for key in ("x_reference_close", "x_ma_ratio_7d", "x_ma_ratio_28d", "x_price_age_hours"):
            self.assertIsNone(sample[key], key)
        self.assertEqual(sample["x_longest_missing_hours_28d"], 672)

    def test_endpoint_label_is_independent_of_complete_path_label(self):
        changed = mask_hour(self.hours[0], DECISION + 10 * HOUR)
        row = self.at(self.rows(changed))
        endpoint = next(hour for hour in changed if hour["bucket_time"] == DECISION + 7 * DAY - HOUR)
        self.assertEqual(row["target_time"], DECISION + 7 * DAY)
        self.assertEqual(row["target_bucket_time"], DECISION + 7 * DAY - HOUR)
        self.assertEqual(row["point_label_status"], "available")
        self.assertEqual(row["path_label_status"], "incomplete_path")
        self.assertTrue(row["point_label_available"])
        self.assertFalse(row["path_label_available"])
        self.assertEqual(float(row["y_reference_close_7d"]), float(endpoint["close_cny"]))
        self.assertIsNone(row["y_path_min_low_7d"])
        self.assertIsNone(row["y_path_max_high_7d"])
        self.assertIsNone(row["y_path_min_return_7d"])
        self.assertIsNone(row["y_path_max_return_7d"])
        self.assertTrue(row["eligible_point_strict"])
        self.assertFalse(row["eligible_path_strict"])

    def test_missing_endpoint_is_not_replaced_by_neighbor_or_interpolation(self):
        changed = mask_hour(self.hours[0], DECISION + 7 * DAY - HOUR)
        row = self.at(self.rows(changed))
        self.assertEqual(row["point_label_status"], "missing_endpoint")
        self.assertEqual(row["path_label_status"], "incomplete_path")
        self.assertIsNone(row["y_reference_close_7d"])
        self.assertIsNone(row["y_return_7d"])
        self.assertFalse(row["eligible_point_quality"])

    def test_pending_future_is_retained_and_never_imputed(self):
        row = self.at(self.rows(cutoff=DECISION + 7 * DAY - HOUR))
        self.assertEqual(row["point_label_status"], "pending")
        self.assertEqual(row["path_label_status"], "pending")
        for key in ("y_reference_close_7d", "y_return_7d", "y_path_min_low_7d",
                    "y_path_max_high_7d", "y_path_min_return_7d", "y_path_max_return_7d"):
            self.assertIsNone(row[key], key)
        self.assertFalse(row["eligible_point_quality"])
        self.assertFalse(row["eligible_path_quality"])

    def test_full_path_extreme_prices_are_retained_in_risk_labels(self):
        changed = copy.deepcopy(self.hours[0])
        for bucket, value in ((DECISION + HOUR, 1), (DECISION + 2 * HOUR, 10000)):
            set_price(next(row for row in changed if row["bucket_time"] == bucket), value)
        row = self.at(self.rows(changed))
        self.assertEqual(row["path_label_status"], "available")
        self.assertEqual(float(row["y_path_min_low_7d"]), 1)
        self.assertEqual(float(row["y_path_max_high_7d"]), 10000)

    def test_input_gap_threshold_and_recent_complete_gate_are_separate(self):
        for missing, quality in ((30, True), (34, False)):
            changed = copy.deepcopy(self.hours[0])
            first = DECISION - 28 * DAY
            for index in range(missing):
                changed = mask_hour(changed, first + index * HOUR)
            row = self.at(self.rows(changed))
            self.assertFalse(row["strict_input_complete"])
            self.assertEqual(bool(row["input_quality_pass"]), quality)
            self.assertFalse(row["eligible_point_strict"])
            self.assertEqual(bool(row["eligible_point_quality"]), quality)
        recent = self.at(self.rows(mask_hour(self.hours[0], DECISION - 2 * HOUR)))
        self.assertFalse(recent["input_quality_pass"])
        self.assertFalse(recent["eligible_point_quality"])

    def test_missing_reference_never_borrows_a_future_price(self):
        changed = mask_hour(self.hours[0], DECISION - HOUR)
        before = self.at(self.rows(changed))
        for hour in changed:
            if hour["bucket_time"] >= DECISION:
                set_price(hour, 9999)
        after = self.at(self.rows(changed))
        self.assertEqual(self.features(before), self.features(after))
        self.assertIsNone(before["y_return_7d"])
        self.assertFalse(before["input_quality_pass"])
        self.assertFalse(before["eligible_point_quality"])

    def test_flows_and_source_provenance_are_not_price_predictors(self):
        changed = copy.deepcopy(self.hours[0])
        for hour in changed:
            hour.update(source_volume=0, source_turnover_cny="0.00", volume_missing=0,
                        turnover_missing=0, source_request=999, source_version_id=999,
                        version_count=12, missing_kind="after_last_observation")
        before, after = self.at(self.rows()), self.at(self.rows(changed))
        self.assertEqual(self.features(before), self.features(after))
        self.assertFalse(any(any(word in key for word in ("volume", "turnover", "source_request",
                                                         "version_count", "missing_kind"))
                             for key in builder.FEATURE_FIELDS))

    def test_split_and_purge_boundaries_depend_on_date_not_item(self):
        spec = copy.deepcopy(builder.EXPECTED_SPEC)
        spec["validation_start_beijing"] = "2026-07-08T10:00:00+08:00"
        spec["test_start_beijing"] = "2026-07-16T10:00:00+08:00"
        cases = (("2026-06-30T10:00:00+08:00", "train", False),
                 ("2026-07-01T10:00:00+08:00", "train", True),
                 ("2026-07-08T10:00:00+08:00", "validation", False),
                 ("2026-07-09T10:00:00+08:00", "validation", True),
                 ("2026-07-16T10:00:00+08:00", "test", False))
        for time, split, purged in cases:
            with self.subTest(time=time):
                self.assertEqual(builder.split_for(epoch(time), spec), (split, purged))
        left, right = self.rows(spec=spec), self.rows(item=1, spec=spec)
        for row_a, row_b in zip(left, right):
            self.assertEqual((row_a["decision_time"], row_a["split"], row_a["purged"]),
                             (row_b["decision_time"], row_b["split"], row_b["purged"]))

    def test_peer_features_ignore_other_items_future_labels_and_maturity(self):
        originals = self.rows() + self.rows(item=1)
        before = builder.add_peer_features(originals)
        changed = copy.deepcopy(originals)
        for row in changed:
            if row["market_hash_name"] == ITEMS[1]["market_hash_name"]:
                row.update(point_label_status="pending", path_label_status="pending",
                           point_label_available=False, path_label_available=False,
                           y_reference_close_7d=None, y_return_7d=None,
                           y_path_min_low_7d=None, y_path_max_high_7d=None,
                           y_path_min_return_7d=None, y_path_max_return_7d=None,
                           eligible_point_strict=False, eligible_point_quality=False,
                           eligible_path_strict=False, eligible_path_quality=False)
        after = builder.add_peer_features(changed)
        self.assertTrue(any("peer" in field for field in builder.FEATURE_FIELDS))
        for left, right in zip(before, after):
            self.assertEqual(self.features(left), self.features(right))
        self.assertEqual(originals, self.rows() + self.rows(item=1),
                         "Peer construction must not mutate input records")
        # Changing a different item's prices at/after t must also leave t's features unchanged.
        changed_hours = copy.deepcopy(self.hours[1])
        for row in changed_hours:
            if row["bucket_time"] >= DECISION:
                set_price(row, 99999)
        revised = builder.add_peer_features(self.rows() + self.rows(changed_hours, item=1))
        before_at = {(row["market_hash_name"], row["decision_time"]): self.features(row)
                     for row in before if row["decision_time"] == DECISION}
        after_at = {(row["market_hash_name"], row["decision_time"]): self.features(row)
                    for row in revised if row["decision_time"] == DECISION}
        self.assertEqual(before_at, after_at)
        left, right = self.at(self.rows()), self.at(self.rows(item=1))
        left["x_return_7d"], right["x_return_7d"] = 0.1, 0.4
        other_date = dict(right, decision_time=DECISION + DAY, x_return_7d=99)
        peers = builder.add_peer_features([left, right, other_date])
        self.assertEqual(peers[0]["x_peer_median_return_7d"], 0.4)
        self.assertEqual(peers[1]["x_peer_median_return_7d"], 0.1)
        self.assertEqual(peers[0]["x_peer_count_7d"], 1)
        self.assertIsNone(peers[2]["x_peer_median_return_7d"])
        self.assertEqual(peers[2]["x_peer_count_7d"], 0)
        with self.assertRaises(ValueError):
            builder.add_peer_features([left, left])

    def test_protocol_cannot_enable_imputation_or_flow_predictors_silently(self):
        for key in ("impute_prices", "use_source_flows_as_features", "training_approved",
                    "historical_available_at_verified"):
            spec = copy.deepcopy(builder.EXPECTED_SPEC)
            spec[key] = True
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    self.rows(spec=spec)
        with self.assertRaises(ValueError):
            self.rows(self.hours[0][1:])

    def make_parent(self, temporary):
        """Create a genuine frozen cleaner version from anonymous synthetic data."""
        root = Path(temporary)
        source = root / "s/research_test"
        source.mkdir(parents=True)
        report = {"workspace_http_attempts_archived": 1, "integrity": "ok",
                  "run": {"status": "completed", "end_exclusive": CUTOFF}}
        (source / "report.json").write_text(json.dumps(report), encoding="utf-8")
        (source / "latest_report.json").write_text(json.dumps({"report": "report.json"}), encoding="utf-8")
        (source / "registry.json").write_text(json.dumps({
            "version": "steamdt-research-registry-1.0", "items": ITEMS}), encoding="utf-8")
        with closing(sqlite3.connect(source / "research.sqlite")) as connection:
            versions = raw_rows(ITEMS[0]) + raw_rows(ITEMS[1], 2)
            cleaner._table(connection, "research_bar_versions", versions, cleaner.SOURCE_FIELDS)
            connection.executescript("""
                CREATE TABLE catalog(market_hash_name TEXT, steamdt_item_id TEXT, metadata_request INTEGER);
                CREATE TABLE platform_ids(market_hash_name TEXT, platform TEXT, platform_item_id TEXT);
                CREATE TABLE requests(request_id INTEGER, endpoint TEXT, params_json TEXT, collected_at TEXT,
                  http_status INTEGER, error_code INTEGER, raw_path TEXT, raw_sha256 TEXT);
            """)
            for item in ITEMS:
                connection.execute("INSERT INTO catalog VALUES(?,?,1)",
                                   (item["market_hash_name"], item["steamdt_item_id"]))
                connection.execute("INSERT INTO platform_ids VALUES(?,'YOUPIN',?)",
                                   (item["market_hash_name"], item["uu_template_id"]))
            connection.execute("INSERT INTO requests VALUES(1,'kline','{}','2026-07-13',200,0,NULL,NULL)")
            connection.commit()
        # Copy exactly the declared dependencies: no production data or local configuration.
        names = set(cleaner.CODE_FILES) | set(builder.CODE_FILES)
        names |= {"docs/research/DATA_METHODS_20261019.md", "scripts/config/seven_daily_spec.json"}
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())
        with patch.multiple(cleaner, ROOT=root, SOURCE_BASE=root / "s", BASE=root / "c"):
            cleaner.build("research_test", "p", ROOT / "scripts/config/steamdt_cleaning_spec.json")
        return root

    def test_frozen_parent_read_only_hashes_no_overwrite_and_path_safety(self):
        # Short project-local paths work in Windows and in a fresh public clone.
        parent = ROOT / "data/local"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ss_", dir=parent) as temporary:
            root = self.make_parent(temporary)
            database = root / "c/p/clean.sqlite"
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            parent_manifest = (root / "c/p/manifest.json").read_bytes()
            spec_path = root / "scripts/config/seven_daily_spec.json"
            connections = []
            connect = sqlite3.connect

            def record_connect(database_path, *args, **kwargs):
                connections.append((str(database_path), kwargs.get("uri", False)))
                return connect(database_path, *args, **kwargs)

            with patch.multiple(builder, ROOT=root, CLEAN_BASE=root / "c", BASE=root / "o"):
                with patch.object(builder.sqlite3, "connect", side_effect=record_connect):
                    result = builder.build_samples("p", "first", spec_path)
                self.assertTrue(any("clean.sqlite?mode=ro" in path and uri
                                    for path, uri in connections))
                self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
                self.assertEqual((root / "c/p/manifest.json").read_bytes(), parent_manifest)
                self.assertFalse(result["historical_available_at_verified"])
                self.assertFalse(result["training_approved"])
                self.assertEqual(set(result["code_files"]), set(builder.CODE_FILES))
                output = Path(result["output_dir"])
                for relative, expected_sha in result["code_files"].items():
                    snapshot = output / "source/code" / relative
                    self.assertEqual(snapshot.read_bytes(), (root / relative).read_bytes())
                    self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(), expected_sha)
                for relative, expected in result["outputs"].items():
                    file = output / relative
                    self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), expected["sha256"])
                with (output / "features.csv").open(encoding="utf-8", newline="") as handle:
                    headers = next(csv.reader(handle))
                self.assertEqual(headers, [*builder.KEY_FIELDS, *builder.FEATURE_FIELDS])
                self.assertFalse(any(field.startswith("y_") or "label" in field or "eligible" in field
                                     for field in headers))
                with closing(sqlite3.connect((output / "samples.sqlite").as_uri() + "?mode=ro", uri=True)) as connection:
                    self.assertEqual(connection.execute("SELECT count(*) FROM samples").fetchone()[0], 30)
                    declared_features = json.loads(connection.execute(
                        "SELECT value_json FROM metadata WHERE key='feature_fields'").fetchone()[0])
                    self.assertEqual(declared_features, list(builder.FEATURE_FIELDS))
                self.assertEqual(builder.status()["output_id"], "first")
                csv_bytes = (output / "features.csv").read_bytes()
                (output / "features.csv").write_bytes(csv_bytes + b"changed")
                with self.assertRaises(ValueError):
                    builder.status("first")
                (output / "features.csv").write_bytes(csv_bytes)
                with self.assertRaises(FileExistsError):
                    builder.build_samples("p", "first", spec_path)
                for clean_id, output_id in (("../outside", "bad"), ("p", "../outside"), ("p", "NUL")):
                    with self.subTest(clean_id=clean_id, output_id=output_id):
                        with self.assertRaises((ValueError, FileNotFoundError)):
                            builder.build_samples(clean_id, output_id, spec_path)
                # A changed frozen parent must be refused, even if SQLite still opens.
                original = database.read_bytes()
                database.write_bytes(original + b"corrupt")
                with self.assertRaises(ValueError):
                    builder.build_samples("p", "tampered", spec_path)
                database.write_bytes(original)
                self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
                # Manifest output names cannot escape their frozen dataset directory.
                escaped = json.loads(parent_manifest)
                escaped["outputs"]["../outside.txt"] = {"bytes": 1, "sha256": hashlib.sha256(b"x").hexdigest()}
                (root / "c/outside.txt").write_bytes(b"x")
                (root / "c/p/manifest.json").write_text(json.dumps(escaped), encoding="utf-8")
                with self.assertRaises(ValueError):
                    builder.build_samples("p", "escaped", spec_path)
                (root / "c/p/manifest.json").write_bytes(parent_manifest)


if __name__ == "__main__":
    unittest.main()
