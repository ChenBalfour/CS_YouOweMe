"""Synthetic, past-only cleaning checks; never contact market services."""
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

from scripts.research.data import clean_hourly as cleaner

ROOT = Path(__file__).resolve().parents[2]
SPEC = copy.deepcopy(cleaner.EXPECTED_SPEC)
START = int(datetime.fromisoformat("2026-06-01T10:00:00+08:00").timestamp())
HOUR = 3600
ITEM = {"market_hash_name": "USP-S | Cyrex (Factory New)", "steamdt_item_id": "293069649",
        "uu_template_id": "228", "name_zh": "次时代崭新", "history_start": "2026-06-01", "enabled": True}


def source(index, price="100", *, request=1, version=None, offset=0):
    return {"version_id": index + 1 if version is None else version, "market_hash_name": ITEM["market_hash_name"],
            "platform": "YOUPIN", "period": "1h", "style": "", "bucket_time": START + index * HOUR,
            "source_time": START + index * HOUR + offset, "source_request": request,
            "open_cny": str(price), "close_cny": str(price), "high_cny": str(price), "low_cny": str(price),
            "source_volume": None, "source_turnover_cny": None}


class HourlyCleaningTests(unittest.TestCase):
    def clean(self, data, hours=None):
        hours = hours if hours is not None else max((r["bucket_time"] - START) // HOUR for r in data) + 1
        return cleaner.clean_rows(data, ITEM, START, START + hours * HOUR, SPEC)

    def test_missing_grid_retains_nulls_masks_age_and_gap_class(self):
        rows = self.clean([source(1), source(3)], hours=5)
        self.assertEqual([r["observed"] for r in rows], [0, 1, 0, 1, 0])
        self.assertEqual([r["missing_kind"] for r in rows], ["before_first_observation", None, "internal_gap", None, "after_last_observation"])
        self.assertIsNone(rows[0]["price_age_hours"])
        self.assertEqual(rows[2]["price_age_hours"], 1)
        for index in (0, 2, 4):
            self.assertTrue(all(rows[index][k] is None for k in ("open_cny", "close_cny", "high_cny", "low_cny", "source_volume", "source_turnover_cny")))
        self.assertEqual(sum(g["hours"] for g in cleaner.gap_rows(rows)), 3)

    def test_real_crash_and_rally_preserved_without_capping(self):
        data = [source(0, "100"), source(1, "1000"), source(2, "10")]
        rows = self.clean(data)
        self.assertEqual([r["close_cny"] for r in rows], ["100", "1000", "10"])
        self.assertTrue(all(r["price_valid"] for r in rows))
        self.assertEqual(rows[1]["large_up_move"], 1)
        self.assertEqual(rows[2]["large_down_move"], 1)
        self.assertNotIn("manipulation", rows[1]["quality_flags"])

    def test_impossible_ohlc_and_invalid_flows_quarantined_not_rewritten(self):
        bad = source(0)
        bad.update(high_cny="90", source_volume=-1, source_turnover_cny="NaN")
        original = copy.deepcopy(bad)
        row = self.clean([bad])[0]
        self.assertEqual(bad, original)
        self.assertEqual(row["observed"], 1)
        self.assertEqual(row["price_valid"], 0)
        self.assertTrue(all(row[k] is None for k in ("open_cny", "close_cny", "high_cny", "low_cny", "source_volume", "source_turnover_cny")))
        self.assertEqual(set(json.loads(row["quality_flags"])), {"invalid_price_or_ohlc", "invalid_volume", "invalid_turnover"})

    def test_reported_zero_and_unknown_flows_remain_distinct(self):
        a, b = source(0), source(1)
        a.update(source_volume=0, source_turnover_cny="0.00")
        rows = self.clean([a, b])
        self.assertEqual(rows[0]["source_volume"], 0)
        self.assertEqual(rows[0]["source_turnover_cny"], "0.00")
        self.assertEqual(rows[0]["volume_missing"], 0)
        self.assertIsNone(rows[1]["source_volume"])
        self.assertEqual(rows[1]["volume_missing"], 1)

    def test_no_single_hour_return_is_calculated_across_missing_hour(self):
        rows = self.clean([source(0, "100"), source(2, "500")])
        self.assertEqual(rows[2]["large_up_move"], 0)
        self.assertIsNone(rows[2]["robust_score"])
        self.assertEqual(rows[2]["robust_reference_returns"], 0)

    def test_latest_version_and_offset_preserve_original_sources(self):
        old, new = source(0, "100"), source(0, "120", request=2, version=2, offset=27)
        data = [new, old]
        row = self.clean(data)[0]
        self.assertEqual(row["close_cny"], "120")
        self.assertEqual(row["source_offset_seconds"], 27)
        self.assertEqual(row["version_count"], 2)
        self.assertEqual(data[1]["close_cny"], "100")

    def test_timestamp_contract_mismatch_stops_instead_of_moving_prices(self):
        bad = source(0)
        bad["bucket_time"] += HOUR
        with self.assertRaises(ValueError):
            cleaner.select_versions([bad], ITEM["market_hash_name"], START, START + 3 * HOUR)

    def test_robust_scores_use_only_past_returns_and_have_no_future_dependency(self):
        data = [source(i, str(100 + i / 10 + (i % 5) / 10)) for i in range(100)]
        original = self.clean(data)
        changed = copy.deepcopy(data)
        for row in changed[80:]:
            row.update(open_cny="10000", close_cny="10000", high_cny="10000", low_cny="10000")
        revised = self.clean(changed)
        self.assertEqual(original[:80], revised[:80])
        self.assertEqual(original[80]["robust_reference_returns"], 79)
        self.assertIsNotNone(original[80]["robust_score"])

    def test_zero_mad_is_not_divided_by_an_invented_small_constant(self):
        rows = self.clean([source(i, "100" if i < 60 else "1000") for i in range(61)])
        self.assertIsNone(rows[-1]["robust_score"])
        self.assertEqual(rows[-1]["robust_reference_zero_mad"], 1)
        self.assertEqual(rows[-1]["large_up_move"], 1)

    def test_coverage_gate_and_recent_24h_gate_are_independent(self):
        for missing, should_pass in ((set(range(30)), 1), (set(range(34)), 0), ({671}, 0)):
            data = [source(i) for i in range(672) if i not in missing]
            rows = self.clean(data, hours=672)
            w = cleaner.quality_windows(rows, START, START + 672 * HOUR, SPEC)[0]
            self.assertEqual(w["input_quality_pass"], should_pass)
            self.assertEqual(w["missing_or_invalid_price_hours"], len(missing))
            self.assertFalse(w["strict_input_complete"])
            self.assertFalse(any(key.startswith(("x_", "y_")) for key in w))

    def test_cannot_silently_enable_imputation_or_remove_extremes(self):
        for key in ("impute_prices", "impute_flows", "remove_extreme_moves"):
            spec = copy.deepcopy(SPEC)
            spec[key] = True
            with self.assertRaises(ValueError):
                cleaner.clean_rows([source(0)], ITEM, START, START + HOUR, spec)

    def test_snapshot_cap_read_only_immutable_outputs_and_status(self):
        parent = ROOT / "data/local/artifacts"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="_offline_cleaning_", dir=parent) as temporary:
            temp = Path(temporary)
            sources, outputs = temp / "sources", temp / "outputs"
            workspace = sources / "research_test"
            workspace.mkdir(parents=True)
            report = {"workspace_http_attempts_archived": 1, "integrity": "ok",
                      "run": {"status": "completed", "end_exclusive": START + 40 * 24 * HOUR}}
            (workspace / "report.json").write_text(json.dumps(report), encoding="utf-8")
            (workspace / "latest_report.json").write_text(json.dumps({"report": "report.json"}), encoding="utf-8")
            # Registry date is midnight; source observations start at 10:00.
            (workspace / "registry.json").write_text(json.dumps({"version": "steamdt-research-registry-1.0", "items": [ITEM]}), encoding="utf-8")
            database = workspace / "research.sqlite"
            data = [source(i) for i in range(40 * 24)]
            data.append(source(2, "9999", request=2, version=2000))
            with closing(sqlite3.connect(database)) as db:
                cleaner._table(db, "research_bar_versions", data, cleaner.SOURCE_FIELDS)
                db.executescript("CREATE TABLE catalog(market_hash_name TEXT,steamdt_item_id TEXT,metadata_request INTEGER); CREATE TABLE platform_ids(market_hash_name TEXT,platform TEXT,platform_item_id TEXT); CREATE TABLE requests(request_id INTEGER,endpoint TEXT,params_json TEXT,collected_at TEXT,http_status INTEGER,error_code INTEGER,raw_path TEXT,raw_sha256 TEXT);")
                db.execute("INSERT INTO catalog VALUES(?,?,1)", (ITEM["market_hash_name"], ITEM["steamdt_item_id"]))
                db.execute("INSERT INTO platform_ids VALUES(?,'YOUPIN',?)", (ITEM["market_hash_name"], ITEM["uu_template_id"]))
                db.execute("INSERT INTO requests VALUES(1,'kline','{}','2026-07-01',200,0,NULL,NULL)")
                db.commit()
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.object(cleaner, "SOURCE_BASE", sources), patch.object(cleaner, "BASE", outputs):
                result = cleaner.build("research_test", "clean_test")
                self.assertEqual(result["source_request_cap"], 1)
                self.assertTrue(result["source_database_unchanged"])
                self.assertEqual(cleaner.status()["output_id"], "clean_test")
                with self.assertRaises(FileExistsError):
                    cleaner.build("research_test", "clean_test")
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
            directory = outputs / "clean_test"
            for relative, expected in result["outputs"].items():
                payload = (directory / relative).read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(), expected["sha256"])
            with closing(sqlite3.connect((directory / "clean.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
                self.assertEqual(db.execute("SELECT close_cny FROM hourly WHERE bucket_time=?", (START + 2 * HOUR,)).fetchone()[0], "100")
                self.assertEqual(db.execute("SELECT count(*) FROM source_versions").fetchone()[0], 960)
                self.assertEqual(db.execute("SELECT count(*) FROM hourly WHERE observed=0").fetchone()[0], 10)
            self.assertEqual(result["summary"]["prices_imputed"], 0)
            self.assertFalse(result["summary"]["new_labels_built"])
            self.assertEqual(set(result["code_files"]), set(cleaner.CODE_FILES))


if __name__ == "__main__":
    unittest.main()
