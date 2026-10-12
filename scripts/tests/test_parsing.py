import unittest
from _support import payload_page
from cs_youoweme.errors import CollectionError
from cs_youoweme.parsing import parse_public


class ParsingTests(unittest.TestCase):
    def test_public_saved_live_payload(self):
        page = payload_page()
        item, variants, exact = parse_public(page, "AK-47 | Redline (Field-Tested)")
        self.assertEqual(item["name"], "AK-47 | 红线 (久经沙场)")
        self.assertEqual(item["itemId"], exact["itemId"])
        self.assertGreater(len(item["sellingPriceList"]), 0)
        self.assertGreater(len(variants), 1)
        self.assertTrue(all(row["platform"] for row in item["sellingPriceList"]))

    def test_wrong_product_does_not_silently_succeed(self):
        page = payload_page()
        with self.assertRaises(CollectionError):
            parse_public(page, "AWP | Asiimov (Field-Tested)")
        with self.assertRaises(CollectionError):
            parse_public("<html>Login required</html>", "AK-47 | Redline (Field-Tested)")
