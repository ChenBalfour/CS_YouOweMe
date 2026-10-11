import unittest
import hashlib
import json
from _support import PROJECT, SAMPLE, payload_page
from cs_youoweme.parsing import parse_public
from cs_youoweme.cleaning import numeric, stamp, count, positive_price


class SampleTests(unittest.TestCase):
    def test_saved_run_integrity(self):
        run_dir = SAMPLE
        manifest = json.loads((run_dir / "reports" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["mode"], "public")
        import csv
        with (run_dir / "tables" / "quotes.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), manifest["quote_rows"])
        self.assertEqual(len(rows), len({(row["market_hash_name"], row["platform"]) for row in rows}))
        decoded_by_name = {}
        for row in rows:
            content = (PROJECT / row["raw_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), row["raw_sha256"])
            name = row["market_hash_name"]
            if name not in decoded_by_name:
                decoded_by_name[name] = parse_public(payload_page(PROJECT / row["raw_path"]), name)
            item = decoded_by_name[name][0]
            source_quote = next(q for q in item["sellingPriceList"] if q["platform"].upper() == row["platform"])
            self.assertEqual(row["raw_sell_price"], numeric(source_quote["price"]) or "")
            self.assertEqual(row["source_updated_at"], stamp(source_quote["updateTime"]) or "")
            if row["has_positive_sell_quote"] == "0":
                self.assertEqual(row["sell_price_cny"], "")
        with (run_dir / "tables" / "items.csv").open(encoding="utf-8-sig", newline="") as handle:
            item_rows = list(csv.DictReader(handle))
        self.assertEqual(len(item_rows), manifest["item_rows"])
        self.assertEqual(len(item_rows), len({row["market_hash_name"] for row in item_rows}))
        for row in item_rows:
            item, _, exact = decoded_by_name[row["market_hash_name"]]
            self.assertEqual(row["name_zh"], item["name"])
            self.assertEqual(row["survive_count"], str(count(item["surviveNum"])))
            self.assertEqual(row["holders_count"], str(count(item["holdersNum"])))
            self.assertEqual(row["display_sell_price_cny"], positive_price(exact["sellPrice"]) or "")
        with (run_dir / "tables" / "related_variants.csv").open(encoding="utf-8-sig", newline="") as handle:
            variants = list(csv.DictReader(handle))
        self.assertEqual(len(variants), manifest["related_variant_rows"])
        self.assertEqual(len(variants), len({row["market_hash_name"] for row in variants}))
        for row in variants:
            payload_path = PROJECT / row["raw_path"]
            self.assertEqual(hashlib.sha256(payload_path.read_bytes()).hexdigest(), row["raw_sha256"])
