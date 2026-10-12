import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _support import PROJECT
from cs_youoweme import __version__, config


class CliTests(unittest.TestCase):
    def test_entrypoint_works_outside_repository(self):
        result = subprocess.run(
            [os.sys.executable, str(PROJECT / "scripts/collect.py"), "--version"],
            cwd=PROJECT.parent, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.strip(), f"CS_YouOweMe {__version__}")

    def test_public_configuration_template_is_empty(self):
        text = (PROJECT / "scripts/config/.env.example").read_text(encoding="utf-8-sig")
        assignments = [line.split("=", 1)[1].strip() for line in text.splitlines() if line.startswith("STEAMDT_API_KEY=")]
        self.assertEqual(assignments, [""])

    def test_config_priority_and_no_secret_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cfg = root / "config"
            cfg.mkdir()
            (cfg / ".env").write_text('STEAMDT_API_KEY="test-config-value"\n', encoding="utf-8")
            (root / ".env").write_text("STEAMDT_API_KEY=test-legacy-value\n", encoding="utf-8")
            output = io.StringIO()
            with patch.object(config, "CONFIG", cfg), patch.object(config, "ROOT", root), patch.dict(os.environ, {"STEAMDT_API_KEY": ""}), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self.assertEqual(config.read_key(), "test-config-value")
                with patch.dict(os.environ, {"STEAMDT_API_KEY": "test-environment-value"}):
                    self.assertEqual(config.read_key(), "test-environment-value")
                (cfg / ".env").unlink()
                self.assertEqual(config.read_key(), "test-legacy-value")
            self.assertEqual(output.getvalue(), "")
