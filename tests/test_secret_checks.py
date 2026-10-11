import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from tools import check_secrets


class SecretCheckTests(unittest.TestCase):
    def test_plain_and_encoded_known_value_are_detected(self):
        encoded = check_secrets.secret_encodings(["unit-test-sensitive-value"])
        for value in encoded:
            self.assertIn("Known local credential or encoded form", check_secrets.inspect_blob(b"prefix:" + value + b":suffix", encoded))

    def test_empty_template_is_allowed_but_filled_template_is_blocked(self):
        self.assertEqual(check_secrets.inspect_blob(b"STEAMDT_API_KEY=\n", set()), [])
        self.assertEqual(check_secrets.inspect_blob(b"STEAMDT_API_KEY=\"\"\n", set()), [])
        findings = check_secrets.inspect_blob(b"STEAMDT_API_KEY=unit-test-value\n", set())
        self.assertIn("Nonempty credential assignment", findings)

    def test_private_paths_are_blocked(self):
        for path in [".env", ".env.local", "nested/.env.backup", "env.example", "data/api_cache/base.json", "private.pem"]:
            self.assertTrue(check_secrets.sensitive_path(path))
        for path in [".env.example", "collect.py", "samples/pilot_20261011/quotes.csv"]:
            self.assertFalse(check_secrets.sensitive_path(path))


if __name__ == "__main__":
    unittest.main()
