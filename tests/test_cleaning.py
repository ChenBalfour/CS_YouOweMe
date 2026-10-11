import unittest
from datetime import datetime
from _support import PROJECT
from cs_youoweme.cleaning import positive_price, quote_row, stamp, identity
from cs_youoweme.paths import CHINA


class CleaningTests(unittest.TestCase):
    def test_zero_quote_is_missing_not_free(self):
        self.assertIsNone(positive_price(0))
        self.assertIsNone(positive_price(-1))
        self.assertIsNone(positive_price(None))
        self.assertIsNone(positive_price("NaN"))
        self.assertEqual(positive_price("172.50"), "172.50")
        row = quote_row({}, "test", {"price": 0, "platform": "buff"}, datetime.now(CHINA), "public_html")
        self.assertEqual(row["raw_sell_price"], "0")
        self.assertIsNone(row["sell_price_cny"])
        self.assertEqual(row["has_positive_sell_quote"], 0)
        self.assertIsNone(row["sell_count"])

    def test_timestamp_units_and_staleness(self):
        self.assertEqual(stamp(1791727752), stamp(1791727752000))
        self.assertIsNone(stamp(0))
        observed = datetime.fromisoformat("2026-10-11T22:00:00+08:00")
        old = datetime.fromisoformat("2026-10-09T21:00:00+08:00")
        row = quote_row({}, "test", {"price": 10, "platform": "buff", "updateTime": old.timestamp()}, observed, "public_html")
        self.assertEqual(row["is_stale_24h"], 1)
        self.assertEqual(row["quote_age_hours"], 49)

    def test_quality_is_part_of_identity(self):
        normal = identity("AK-47 | Redline (Field-Tested)")
        st = identity("StatTrak™ AK-47 | Redline (Field-Tested)")
        souvenir = identity("Souvenir AK-47 | Redline (Field-Tested)")
        self.assertEqual([normal["quality"], st["quality"], souvenir["quality"]], ["normal", "stattrak", "souvenir"])
        self.assertEqual(normal["exterior"], "Field-Tested")

    def test_api_currency_must_be_confirmed(self):
        observed = datetime.now(CHINA)
        quote = {"platform": "BUFF", "sellPrice": 123.5, "sellCount": 7, "biddingPrice": 120, "biddingCount": 2}
        unverified = quote_row({}, "test", quote, observed, "official_api")
        confirmed = quote_row({}, "test", quote, observed, "official_api", "CNY")
        self.assertIsNone(unverified["currency"])
        self.assertIsNone(unverified["sell_price_cny"])
        self.assertEqual(unverified["raw_sell_price"], "123.5")
        self.assertEqual(confirmed["sell_price_cny"], "123.5")
        self.assertEqual(confirmed["sell_count"], 7)
