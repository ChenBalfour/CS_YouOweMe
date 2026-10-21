from contextlib import closing, redirect_stdout
import copy
from io import StringIO
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import collect_uu_direct as direct


def response(body, *, value=None):
    if value is None:
        value = "1112.00" if body["orderType"] == "11" else "32.39"
    return json.dumps({"code": 0, "msg": "成功", "timestamp": 1791953107780,
                       "data": {"tradeDataList": [{"time": 1790622000000, "price": value}],
                                "tradePriceList": [], "blockNum": 5}}, ensure_ascii=False).encode()


class FakeClock:
    def __init__(self):
        self.value = 1800000000.0
        self.waits = []

    def current(self):
        return self.value

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.value += seconds


class DirectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.patches = [patch.object(direct, "BASE", self.base),
                        patch.object(direct, "CONTROL", self.base / "direct_control"),
                        patch.object(direct, "AUTH", self.base / "credentials_uu_chart.json")]
        for value in self.patches:
            value.start(); self.addCleanup(value.stop)
        direct.CONTROL.mkdir()
        self.items = direct.load_items(direct.ITEMS_EXAMPLE)
        self.clock = FakeClock()
        self.state = {"version": direct.VERSION, "blocked": False, "reason": None,
                      "not_before_epoch": 0, "last_request_epoch": 0, "last_template_id": None,
                      "request_epochs": [], "recovery_acknowledgements": []}

    def run_collect(self, directory, manifest, maximum, send):
        with redirect_stdout(StringIO()):
            return direct.collect(directory, manifest, self.state, {}, maximum=maximum,
                                  send=send, clock=self.clock.current, monotonic=self.clock.current,
                                  sleep=self.clock.sleep)

    def test_seven_metric_windows_and_repeated_items_rejected(self):
        tasks = direct.tasks_for(self.items)
        self.assertEqual([(t["request_body"]["day"], t["request_body"]["orderType"]) for t in tasks],
                         [("7", "1"), ("7", "11"), ("15", "11"), ("30", "1"), ("30", "11"), ("90", "1"), ("180", "1")])
        invalid = copy.deepcopy(self.items); invalid["items"] *= 2
        path = self.base / "items.json"; path.write_text(json.dumps(invalid), encoding="utf-8")
        with self.assertRaises(direct.PilotError): direct.load_items(path)

    def test_probe_then_resume_skips_success_and_preserves_sql_precision(self):
        directory, manifest = direct.new_run(self.items, 15, 60)
        calls = []
        def send(body, headers, timeout):
            calls.append(copy.deepcopy(body)); return response(body)
        self.run_collect(directory, manifest, 1, send)
        self.assertEqual(len(calls), 1)
        self.assertEqual(direct.summary(manifest)["pending"], 6)
        self.assertEqual(direct.existing_run(manifest["run_id"])[1], manifest)
        self.run_collect(directory, manifest, 21, send)
        self.assertEqual(len(calls), 7)
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(self.clock.waits, [15] * 6)
        with closing(sqlite3.connect((directory / "charts.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
            rows = db.execute("SELECT source_trade_price_cny,source_listing_count,historical_available_at FROM points").fetchall()
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(sum(r[0] == "32.39" for r in rows), 4)
        self.assertEqual(sum(r[1] == 1112 for r in rows), 3)
        self.assertTrue(all(r[2] is None for r in rows))
        self.assertTrue((directory / "points.csv").is_file())

    def test_new_product_and_new_run_respect_global_item_gap(self):
        self.state.update(last_request_epoch=self.clock.current(), last_template_id="999")
        directory, manifest = direct.new_run(self.items, 15, 60)
        self.run_collect(directory, manifest, 1, lambda b, h, t: response(b))
        self.assertEqual(self.clock.waits, [60])

    def test_http_429_stops_and_future_runs_cannot_clear_cooldown(self):
        directory, manifest = direct.new_run(self.items, 15, 60)
        def stopped(*_):
            raise direct.RequestFailure("http_error", http_status=429, retry_at=self.clock.current() + 120)
        self.run_collect(directory, manifest, 21, stopped)
        self.assertEqual(direct.summary(manifest)["failed"], 1)
        self.assertEqual(direct.summary(manifest)["pending"], 6)
        self.assertTrue(self.state["blocked"])
        with self.assertRaisesRegex(direct.PilotError, "cooldown"):
            direct.admit(self.state, True, self.clock.current())
        with self.assertRaisesRegex(direct.PilotError, "confirm_normal_access"):
            direct.admit(self.state, False, self.clock.current() + 121)
        self.assertEqual(list((directory / "raw").iterdir()), [])

    def test_business_error_and_empty_series_stop_without_archiving(self):
        for raw in (b'{"code":2002,"msg":"not logged in"}',
                    b'{"code":0,"timestamp":1791953107780,"data":{"tradeDataList":[]}}'):
            with self.assertRaises(direct.RequestFailure): direct.validate_response(raw, direct.tasks_for(self.items)[0]["request_body"], {})

    def test_unknown_attempt_is_not_retried(self):
        directory, manifest = direct.new_run(self.items, 15, 60)
        task = manifest["tasks"][0]; task.update(status="interrupted_unknown", attempts=1)
        calls = []
        self.run_collect(directory, manifest, 21, lambda b, h, t: calls.append(b) or response(b))
        self.assertEqual(len(calls), 6)
        self.assertEqual(manifest["status"], "partial_no_automatic_retry")
        self.assertEqual(task["status"], "interrupted_unknown")

    def test_quota_and_exclusive_lock(self):
        self.state["request_epochs"] = [self.clock.current()] * direct.DAILY_LIMIT
        with self.assertRaisesRegex(direct.PilotError, "budget"):
            direct.admit(self.state, False, self.clock.current())
        with direct.worker_lock():
            with self.assertRaisesRegex(direct.PilotError, "lock"):
                with direct.worker_lock(): pass
        self.assertFalse((direct.CONTROL / "worker.lock").exists())

    def test_private_auth_only_accepts_whitelist_and_rejects_injection(self):
        for headers in ({"authorization": "example\r\nInjected: yes"}, {"host": "elsewhere"}, {}):
            direct.AUTH.write_text(json.dumps({"headers": headers}), encoding="utf-8")
            with self.assertRaises(direct.PilotError): direct.auth_headers()
        direct.AUTH.write_text(json.dumps({"headers": {"cookie": "session=offline-placeholder-only"}}), encoding="utf-8")
        self.assertIn("cookie", direct.auth_headers())

    def test_credential_echo_never_passes_validator(self):
        marker = "offline-placeholder-only"
        with self.assertRaisesRegex(direct.RequestFailure, "credential_like"):
            direct.validate_response(("echo " + marker).encode(), {}, {"cookie": "session=" + marker})

    def test_redirects_are_not_followed(self):
        self.assertIsNone(direct.NoRedirect().redirect_request(None, None, 307, None, None, "https://elsewhere.invalid/"))
        self.assertEqual(direct.cooldown("120", 1000), 1120)
        self.assertIsNone(direct.cooldown("not-a-date", 1000))

    def test_plan_does_not_read_auth_or_send_network(self):
        with patch.object(sys, "argv", ["script", "plan"]), patch.object(direct, "auth_headers", side_effect=AssertionError), patch.object(direct, "request_chart", side_effect=AssertionError), redirect_stdout(StringIO()) as text:
            self.assertEqual(direct.main(), 0)
        self.assertEqual(json.loads(text.getvalue())["network_requests"], 0)

    def test_resume_rejects_tampered_saved_items_and_missing_database_rows(self):
        directory, manifest = direct.new_run(self.items, 15, 60)
        self.run_collect(directory, manifest, 1, lambda b, h, t: response(b))
        with closing(sqlite3.connect(directory / "charts.sqlite")) as db, db:
            db.execute("DELETE FROM points")
        with self.assertRaisesRegex(direct.PilotError, "database_count"):
            direct.existing_run(manifest["run_id"])
        manifest["items"]["items"][0]["template_id"] = "../invalid"
        direct.save(directory / "run.json", manifest)
        with self.assertRaisesRegex(direct.PilotError, "template"):
            direct.existing_run(manifest["run_id"])

    def test_attempt_is_checkpointed_before_send_and_auth_never_archived(self):
        directory, manifest = direct.new_run(self.items, 15, 60)
        def interrupted(body, headers, timeout):
            saved = json.loads((directory / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["tasks"][0]["status"], "interrupted_unknown")
            self.assertEqual(len(json.loads((direct.CONTROL / "state.json").read_text())["request_epochs"]), 1)
            raise KeyboardInterrupt()
        self.run_collect(directory, manifest, 21, interrupted)
        self.assertEqual(manifest["status"], "user_interrupted")
        self.assertEqual(direct.summary(manifest)["interrupted_unknown"], 1)
        self.assertEqual(list((directory / "raw").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
