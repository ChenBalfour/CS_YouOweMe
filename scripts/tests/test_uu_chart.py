import json
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from scripts import review_uu_chart as chart


def response(values=("1112.00", "1203.00"), gap=14400000):
    return {"code": 0, "msg": "success", "timestamp": 1791953107780,
            "data": {"tradeDataList": [{"time": 1790622000000 + i * gap, "price": v,
                                        "sourceType": 0} for i, v in enumerate(values)],
                     "tradePriceList": ["0.00", "1078.00", "1485.50", "1893.00"], "blockNum": 5}}


def inspect(value, order=11):
    return chart.inspect_response(json.dumps(value).encode(), template_id="980", order_type=str(order), requested_days="15")


class ChartTests(unittest.TestCase):
    def test_metric_context_separates_same_price_field(self):
        quantity = inspect(response())
        price = inspect(response(), 1)
        self.assertEqual(quantity["points"][0]["source_listing_count"], 1112)
        self.assertIsNone(quantity["points"][0]["source_trade_price_cny"])
        self.assertEqual(price["points"][0]["source_trade_price_cny"], "1112.00")
        self.assertIsNone(price["points"][0]["source_listing_count"])
        self.assertFalse(quantity["execution_eligible"])

    def test_fractional_count_is_not_silently_truncated(self):
        with self.assertRaises(ValueError):
            inspect(response(("1112.50",)))

    def test_null_and_zero_are_distinct(self):
        report = inspect(response((None, "0.00")))
        self.assertIsNone(report["points"][0]["source_listing_count"])
        self.assertEqual(report["points"][1]["source_listing_count"], 0)
        self.assertEqual(report["summary"]["null_values"], 1)

    def test_real_interval_not_blocknum_controls_cadence(self):
        report = inspect(response())
        self.assertEqual(report["summary"]["constant_interval_ms"], 14400000)
        self.assertEqual(report["chart_auxiliary_fields"]["blockNum"], 5)
        self.assertEqual(report["points"][0]["source_time_beijing"], "2026-09-29T03:00:00.000+08:00")
        self.assertEqual(report["points"][0]["source_type_raw"], 0)

    def test_seconds_and_nonfinite_values_are_rejected(self):
        value = response()
        value["data"]["tradeDataList"][0]["time"] //= 1000
        with self.assertRaises(ValueError):
            inspect(value)
        for bad in ("NaN", "Infinity", "-1.00", True):
            with self.assertRaises(ValueError):
                inspect(response((bad,)))

    def test_conflicting_duplicates_are_preserved_and_flagged(self):
        value = response()
        value["data"]["tradeDataList"][1]["time"] = value["data"]["tradeDataList"][0]["time"]
        report = inspect(value)
        self.assertEqual(report["summary"]["rows"], 2)
        self.assertIn("conflicting_duplicate_time", report["summary"]["quality_flags"])

    def test_request_headers_and_failed_envelopes_are_rejected(self):
        value = response()
        value["headers"] = {"authorization": "test-only-placeholder"}
        with self.assertRaises(ValueError):
            inspect(value)
        value = response()
        value["code"] = 1
        with self.assertRaises(ValueError):
            inspect(value)

    def test_offline_export_keeps_counts_in_integer_sql_column(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = json.dumps(response()).encode()
            report = chart.inspect_response(raw, template_id="980", order_type=11, requested_days=15)
            with patch.object(chart, "REVIEWS", root):
                chart.write_review(raw, report, root / "run")
                with self.assertRaises(ValueError):
                    chart.write_review(raw, report, root / "run")
            with closing(sqlite3.connect((root / "run/chart_review.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
                self.assertEqual(db.execute("SELECT source_trade_price_cny,source_listing_count FROM points ORDER BY sequence").fetchall(), [(None, 1112), (None, 1203)])
            self.assertEqual((root / "run/response_input.json").read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
