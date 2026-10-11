import hashlib
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import collect


def payload_page(path):
    return '<script id="__NUXT_DATA__" type="application/json">' + path.read_text(encoding="utf-8") + '</script>'


class CollectorChecks(unittest.TestCase):
    def test_public_saved_live_payload(self):
        page = payload_page(PROJECT / "tests/fixtures/ak47_redline_ft.nuxt.json")
        item, variants, exact = collect.parse_public(page, "AK-47 | Redline (Field-Tested)")
        self.assertEqual(item["name"], "AK-47 | 红线 (久经沙场)")
        self.assertEqual(item["itemId"], exact["itemId"])
        self.assertGreater(len(item["sellingPriceList"]), 0)
        self.assertGreater(len(variants), 1)
        self.assertTrue(all(row["platform"] for row in item["sellingPriceList"]))

    def test_wrong_product_does_not_silently_succeed(self):
        page = payload_page(PROJECT / "tests/fixtures/ak47_redline_ft.nuxt.json")
        with self.assertRaises(collect.CollectionError):
            collect.parse_public(page, "AWP | Asiimov (Field-Tested)")
        with self.assertRaises(collect.CollectionError):
            collect.parse_public("<html>Login required</html>", "AK-47 | Redline (Field-Tested)")

    def test_zero_quote_is_missing_not_free(self):
        self.assertIsNone(collect.positive_price(0))
        self.assertIsNone(collect.positive_price(-1))
        self.assertIsNone(collect.positive_price(None))
        self.assertIsNone(collect.positive_price("NaN"))
        self.assertEqual(collect.positive_price("172.50"), "172.50")
        row = collect.quote_row({}, "test", {"price": 0, "platform": "buff"}, datetime.now(collect.CHINA), "public_html")
        self.assertEqual(row["raw_sell_price"], "0")
        self.assertIsNone(row["sell_price_cny"])
        self.assertEqual(row["has_positive_sell_quote"], 0)
        self.assertIsNone(row["sell_count"])

    def test_timestamp_units_and_staleness(self):
        self.assertEqual(collect.stamp(1791727752), collect.stamp(1791727752000))
        self.assertIsNone(collect.stamp(0))
        observed = datetime.fromisoformat("2026-10-11T22:00:00+08:00")
        old = datetime.fromisoformat("2026-10-09T21:00:00+08:00")
        row = collect.quote_row({}, "test", {"price": 10, "platform": "buff", "updateTime": old.timestamp()}, observed, "public_html")
        self.assertEqual(row["is_stale_24h"], 1)
        self.assertEqual(row["quote_age_hours"], 49)

    def test_quality_is_part_of_identity(self):
        normal = collect.identity("AK-47 | Redline (Field-Tested)")
        st = collect.identity("StatTrak™ AK-47 | Redline (Field-Tested)")
        souvenir = collect.identity("Souvenir AK-47 | Redline (Field-Tested)")
        self.assertEqual([normal["quality"], st["quality"], souvenir["quality"]], ["normal", "stattrak", "souvenir"])
        self.assertEqual(normal["exterior"], "Field-Tested")

    def test_api_currency_must_be_confirmed(self):
        observed = datetime.now(collect.CHINA)
        quote = {"platform": "BUFF", "sellPrice": 123.5, "sellCount": 7, "biddingPrice": 120, "biddingCount": 2}
        unverified = collect.quote_row({}, "test", quote, observed, "official_api")
        confirmed = collect.quote_row({}, "test", quote, observed, "official_api", "CNY")
        self.assertIsNone(unverified["currency"])
        self.assertIsNone(unverified["sell_price_cny"])
        self.assertEqual(unverified["raw_sell_price"], "123.5")
        self.assertEqual(confirmed["sell_price_cny"], "123.5")
        self.assertEqual(confirmed["sell_count"], 7)

    def test_redirect_does_not_forward_secret_to_other_host(self):
        handler = collect.SameOriginRedirect()
        req = collect.urllib.request.Request("https://open.steamdt.com/open/cs2/v1/base", headers={"Authorization": "Bearer test-only"})
        with self.assertRaises(collect.AccessStopped):
            handler.redirect_request(req, None, 302, "", {}, "https://example.com/")

    def test_saved_run_integrity(self):
        run_dir = PROJECT / "samples/pilot_20261011"
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["mode"], "public")
        import csv
        with (run_dir / "quotes.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), manifest["quote_rows"])
        self.assertEqual(len(rows), len({(row["market_hash_name"], row["platform"]) for row in rows}))
        decoded_by_name = {}
        for row in rows:
            content = (PROJECT / row["raw_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), row["raw_sha256"])
            name = row["market_hash_name"]
            if name not in decoded_by_name:
                decoded_by_name[name] = collect.parse_public(payload_page(PROJECT / row["raw_path"]), name)
            item = decoded_by_name[name][0]
            source_quote = next(q for q in item["sellingPriceList"] if q["platform"].upper() == row["platform"])
            self.assertEqual(row["raw_sell_price"], collect.numeric(source_quote["price"]) or "")
            self.assertEqual(row["source_updated_at"], collect.stamp(source_quote["updateTime"]) or "")
            if row["has_positive_sell_quote"] == "0":
                self.assertEqual(row["sell_price_cny"], "")
        with (run_dir / "items.csv").open(encoding="utf-8-sig", newline="") as handle:
            item_rows = list(csv.DictReader(handle))
        self.assertEqual(len(item_rows), manifest["item_rows"])
        self.assertEqual(len(item_rows), len({row["market_hash_name"] for row in item_rows}))
        for row in item_rows:
            item, _, exact = decoded_by_name[row["market_hash_name"]]
            self.assertEqual(row["name_zh"], item["name"])
            self.assertEqual(row["survive_count"], str(collect.count(item["surviveNum"])))
            self.assertEqual(row["holders_count"], str(collect.count(item["holdersNum"])))
            self.assertEqual(row["display_sell_price_cny"], collect.positive_price(exact["sellPrice"]) or "")
        with (run_dir / "related_variants.csv").open(encoding="utf-8-sig", newline="") as handle:
            variants = list(csv.DictReader(handle))
        self.assertEqual(len(variants), manifest["related_variant_rows"])
        self.assertEqual(len(variants), len({row["market_hash_name"] for row in variants}))
        for row in variants:
            payload_path = PROJECT / row["raw_path"]
            self.assertEqual(hashlib.sha256(payload_path.read_bytes()).hexdigest(), row["raw_sha256"])

    def test_version_metadata_matches_cli(self):
        self.assertEqual((PROJECT / "VERSION").read_text(encoding="utf-8").strip(), collect.VERSION)

    def test_public_configuration_template_is_empty(self):
        text = (PROJECT / ".env.example").read_text(encoding="utf-8-sig")
        assignments = [line.split("=", 1)[1].strip() for line in text.splitlines() if line.startswith("STEAMDT_API_KEY=")]
        self.assertEqual(assignments, [""])


if __name__ == "__main__":
    unittest.main()
