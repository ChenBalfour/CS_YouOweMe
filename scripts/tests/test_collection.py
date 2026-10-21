import contextlib
import csv
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from _support import payload_page
from cs_youoweme import storage
from cs_youoweme.cli import main
from cs_youoweme.collectors import public


class CollectionTests(unittest.TestCase):
    def test_saved_page_runs_through_cli_tables_reports_and_database(self):
        """Exercise the complete export pipeline without network access or a key."""
        content = payload_page().encode("utf-8")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / "data/local"
            seeds = root / "seeds.json"
            seeds.write_text(json.dumps(["AK-47 | Redline (Field-Tested)"]), encoding="utf-8")
            with patch.object(storage, "ROOT", root), patch.object(storage, "LOCAL_DATA", local), patch.object(public, "request_bytes", return_value=(content, "text/html")) as request, contextlib.redirect_stdout(io.StringIO()):
                result = main(["public", "--seeds", str(seeds), "--limit", "1"])
            self.assertEqual(result, 0)
            request.assert_called_once()
            pointer = json.loads((local / "latest_run.json").read_text(encoding="utf-8"))
            run = root / pointer["path"]
            self.assertTrue(run.is_relative_to(local / "runs"))
            self.assertFalse((run / "quotes.csv").exists())
            manifest = json.loads((run / "reports/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["quote_rows"], 9)
            with (run / "tables/quotes.csv").open(encoding="utf-8-sig", newline="") as handle:
                quotes = list(csv.DictReader(handle))
            self.assertEqual(len(quotes), 9)
            for row in quotes:
                raw = root / row["raw_path"]
                self.assertEqual(raw.parent, run / "raw")
                self.assertEqual(raw.read_bytes(), content)
                self.assertEqual(row["raw_sha256"], hashlib.sha256(content).hexdigest())
            self.assertTrue((run / "reports/quality_report.md").is_file())
            with closing(sqlite3.connect(local / "steamdt.sqlite")) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM items").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM quotes").fetchone()[0], 9)

    def test_wrong_product_preserves_evidence_and_marks_partial(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / "data/local"
            seeds = root / "seeds.json"
            seeds.write_text(json.dumps(["AWP | Asiimov (Field-Tested)"]), encoding="utf-8")
            with patch.object(storage, "ROOT", root), patch.object(storage, "LOCAL_DATA", local), patch.object(public, "request_bytes", return_value=(payload_page().encode(), "text/html")), contextlib.redirect_stdout(io.StringIO()):
                result = main(["public", "--seeds", str(seeds), "--limit", "1"])
            self.assertEqual(result, 2)
            run = next((local / "runs").iterdir())
            manifest = json.loads((run / "reports/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "partial")
            self.assertEqual(manifest["quote_rows"], 0)
            self.assertEqual(len(manifest["errors"]), 1)
            self.assertTrue((run / "raw/item_001.html").is_file())
