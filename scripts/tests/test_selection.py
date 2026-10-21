import copy
import json
import sys
import unittest

from _support import PROJECT
sys.path.insert(0, str(PROJECT))
from scripts.select_uu_research import choose, uu_quote


def candidate(name, weapon, price, hours=100, errors=None, heat=1):
    return {"market_hash_name": name, "weapon": weapon, "family": name, "uu_price_cny": str(price), "price_hours": 168, "volume_hours": hours, "turnover_hours": hours, "heat_position": heat, "exclusion_reasons": errors or []}


class SelectionTests(unittest.TestCase):
    def test_other_platform_minimum_cannot_become_uu_price(self):
        item = {"sellingPriceList": [{"platform": "buff", "price": 1, "updateTime": 20}, {"platform": "youpin", "price": "123.45", "updateTime": 30, "platformName": "悠悠"}]}
        self.assertEqual(uu_quote(item, 40), ("123.45", 30, "悠悠"))

    def test_reasons_do_not_mutate_original_exclusion_evidence(self):
        row = candidate("outside", "AK-47", 50, errors=["outside-price-band"], heat=2)
        original = copy.deepcopy(row["exclusion_reasons"])
        choose([row])
        self.assertEqual(row["exclusion_reasons"], original)
        self.assertEqual(row["role"], "excluded")

    def test_high_price_and_family_duplicates_remain_reserves(self):
        rows = [candidate("ak-ft", "AK-47", 500), candidate("ak-mw", "AK-47", 1000, hours=90), candidate("m4", "M4A4", 2000), candidate("usp", "USP-S", 200), candidate("high", "AWP", 7200)]
        rows[1]["family"] = rows[0]["family"]
        main, reserve = choose(rows)
        self.assertEqual({row["market_hash_name"] for row in main}, {"ak-ft", "m4", "usp"})
        self.assertEqual({row["market_hash_name"] for row in reserve}, {"ak-mw", "high"})

    def test_watchlist_uses_verified_oligarch_identity(self):
        names = json.loads((PROJECT / "scripts/config/watchlist.json").read_text(encoding="utf-8"))
        self.assertIn("AK-47 | The Oligarch (Field-Tested)", names)
        self.assertFalse(any("Gold Arabesque" in name for name in names))


if __name__ == "__main__":
    unittest.main()
