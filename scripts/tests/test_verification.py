import unittest
from pathlib import Path
import json
import sys
import tempfile
import urllib.error
from unittest.mock import patch

import _support
from cs_youoweme.errors import CollectionError
from cs_youoweme.history.verification import source_trade, trade_venue, uu_snapshot
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_public_evidence


class VerificationTests(unittest.TestCase):
    def test_blocked_origin_is_persisted_and_not_retried(self):
        class BlockedOpener:
            calls = 0

            def open(self, req, timeout):
                self.calls += 1
                raise urllib.error.HTTPError(req.full_url, 429, "limited", {"Retry-After": "120"}, None)

        opener = BlockedOpener()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(verify_public_evidence, "ROOT", root), patch.object(verify_public_evidence, "BASE", root), \
                 patch.object(verify_public_evidence.urllib.request, "build_opener", return_value=opener), \
                 patch.object(verify_public_evidence.time, "sleep"):
                verify_public_evidence.capture("p03_20261013_test", ["https://pc-api.youpin898.com/first"])
                with self.assertRaises(ValueError):
                    verify_public_evidence.capture("p03_20261013_test", ["https://pc-api.youpin898.com/second"])
            report = json.loads((root / "p03_20261013_test/evidence.json").read_text())
            self.assertEqual(opener.calls, 1)
            self.assertEqual(report["requests"][0]["retry_after"], "120")
            self.assertEqual(report["blocked_hosts"], ["pc-api.youpin898.com"])

    def test_third_party_codes_cannot_become_uu(self):
        self.assertEqual(trade_venue(1), "STEAM")
        for code in [0, 2, 3]:
            self.assertEqual(trade_venue(code), "third_party_unknown")
        self.assertEqual(trade_venue(99), "unknown")

    def test_crossed_quote_retained_but_cannot_be_executed(self):
        row = {"platform": "youpin", "platformName": "悠悠", "sellPrice": "2388.00",
               "biddingPrice": "3400.00", "sellCount": 643, "biddingCount": 48,
               "updateTime": 1791897848,
               "link": "https://www.youpin898.com/market/goods-list?templateId=46298&gameId=730"}
        result = uu_snapshot(row, "2026-10-13T13:33:00+00:00", 5)
        self.assertEqual(result["source_bidding_price_cny"], "3400.00")
        self.assertIn("crossed_source_quotes", result["quality_flags"])
        self.assertFalse(result["execution_eligible"])

    def test_missing_count_is_not_zero_filled(self):
        row = {"platform": "YOUPIN", "platformName": "悠悠", "sellPrice": 100, "biddingPrice": 0,
               "sellCount": None, "biddingCount": 0,
               "link": "https://www.youpin898.com/market/goods-list?templateId=113014&gameId=730"}
        result = uu_snapshot(row, "2026-10-13T00:00:00+00:00", 3)
        self.assertIsNone(result["source_sell_count"])
        self.assertEqual(result["source_bidding_count"], 0)
        self.assertIn("source_time_missing", result["quality_flags"])

    def test_same_named_non_uu_row_rejected(self):
        with self.assertRaises(CollectionError):
            uu_snapshot({"platform": "buff", "platformName": "悠悠"}, "2026-10-13T00:00:00+00:00", 1)

    def test_zero_attributes_and_sticker_null_are_distinct(self):
        row = {"id": "test", "platform": 2, "tradeTime": 1791849600,
               "tradePrice": "20.10", "paintIndex": 0, "paintSeed": 0, "wearFlot": "0.00000000"}
        result = source_trade(row, 4)
        self.assertEqual(result["paint_seed"], 0)
        self.assertEqual(result["wear_decimal"], "0E-8")
        self.assertEqual(result["stickers_state"], "missing")
        row["stickers"] = None
        self.assertEqual(source_trade(row, 4)["stickers_state"], "null")
        row["stickers"] = []
        self.assertEqual(source_trade(row, 4)["stickers_state"], "empty_array")
        self.assertFalse(source_trade(row, 4)["execution_eligible"])
