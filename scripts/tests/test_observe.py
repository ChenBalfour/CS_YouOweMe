"""Offline acceptance checks for the user-started forward observer."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import _support
from cs_youoweme.collectors.website import ITEM, MARKET_COMPARISON, SYSTEM
from cs_youoweme.errors import AccessStopped, CollectionError
from cs_youoweme.history import observe, store as store_module


class FakeClock:
    def __init__(self):
        self.time = 1791849600.0

    def __call__(self):
        return self.time

    def sleep(self, seconds):
        self.time += seconds


class FakeFactory:
    """No network: every simulated HTTP must still use the production guard."""
    def __init__(self, clock, *, blocked=False, change=None, transport_fail=False, pacing_jump=0):
        self.clock = clock
        self.blocked = blocked
        self.change = change
        self.transport_fail = transport_fail
        self.pacing_jump = pacing_jump
        self.calls = []

    def __call__(self, archive, **kwargs):
        factory = self

        class Client:
            synced_at = None

            def send(self, endpoint, params):
                if endpoint == MARKET_COMPARISON and factory.pacing_jump:
                    factory.clock.time += factory.pacing_jump
                    factory.pacing_jump = 0
                kwargs["before_request"](endpoint, params)
                factory.calls.append((endpoint, dict(params), factory.clock()))
                if factory.blocked:
                    archive(endpoint, params, observe.utc(factory.clock()), b"", 429, None)
                    raise AccessStopped("Website HTTP 429; worker stopped")
                if endpoint == SYSTEM:
                    data = {"systemTime": int(factory.clock() * 1000)}
                elif endpoint == ITEM:
                    item = next(i for i in observe.SPECIMENS if i["name"] == params["marketHashName"])
                    data = {"marketHashName": item["name"], "itemId": item["item_id"],
                            "sellingPriceList": [{"platform": "youpin", "platformName": "悠悠",
                                                  "price": "250.00", "updateTime": int(factory.clock())}]}
                elif endpoint == MARKET_COMPARISON:
                    if factory.transport_fail:
                        archive(endpoint, params, observe.utc(factory.clock()), b"", None, None)
                        raise CollectionError("Website network failure; checkpoint retained")
                    item = next(i for i in observe.SPECIMENS if i["item_id"] == params["itemId"])
                    row = {"platform": "youpin", "platformName": "悠悠", "sellPrice": "250.00",
                           "biddingPrice": "240.00", "sellCount": 20, "biddingCount": None,
                           "updateTime": int(factory.clock()),
                           "link": "https://www.youpin898.com/market/goods-list?templateId=" + item["template_id"] + "&gameId=730"}
                    if factory.change:
                        factory.change(row, item)
                    data = {"platformMarket": [row]}
                else:
                    raise AssertionError("Unexpected simulated endpoint")
                raw = json.dumps({"success": True, "errorCode": 0, "data": data}, ensure_ascii=False).encode()
                request = archive(endpoint, params, observe.utc(factory.clock()), raw, 200, 0)
                return data, request

            def call(self, endpoint, params=None, post=False):
                if endpoint != SYSTEM and (self.synced_at is None or factory.clock() - self.synced_at > 240):
                    self.send(SYSTEM, {})
                    self.synced_at = factory.clock()
                return self.send(endpoint, params or {})

        return Client()


class ObserveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        local = self.root / "data/local"
        self.clock = FakeClock()
        self.patches = [patch.object(observe, "ROOT", self.root),
                        patch.object(observe, "RUNS", local / "staging/steamdt"),
                        patch.object(observe, "POINTER", local / "manifests/last.json"),
                        patch.object(observe, "_source_hashes", return_value={}),
                        patch.object(store_module, "LOCAL_DATA", local)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self.temporary.cleanup)

    def create(self, hours=2):
        return observe.create_run(hours=hours, _clock=self.clock)

    def collect(self, path, factory=None, progress=lambda value: None):
        self.factory = factory or FakeFactory(self.clock)
        return observe.collect(path, progress=progress, _clock=self.clock,
                               _sleep=self.clock.sleep, _client_factory=self.factory)

    def read_rows(self, path):
        with closing(sqlite3.connect((path / "observations.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
            return db.execute("SELECT slot,item,state,snapshot_json FROM observer_samples ORDER BY slot,item").fetchall()

    def test_24_hour_fixed_schedule_completes_without_live_http(self):
        started = self.clock()
        path = self.create(hours=24)
        self.assertEqual(observe.load_last_run(), path)
        result = self.collect(path)
        self.assertEqual(self.clock(), started + 24 * 3600)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sample_states"], {"success": 48})
        self.assertEqual(result["http_attempts"], 120)
        self.assertEqual(len(self.factory.calls), 120)
        self.assertTrue(all(t < started + 24 * 3600 for _, _, t in self.factory.calls))
        self.assertEqual({endpoint for endpoint, _, _ in self.factory.calls}, {SYSTEM, ITEM, MARKET_COMPARISON})
        self.assertFalse(result["execution_eligible"])
        self.assertTrue((path / "tables/source_snapshots.csv").is_file())
        self.assertTrue((path / "reports/summary.md").is_file())

    def test_interrupt_and_resume_do_not_repeat_success_or_extend_deadline(self):
        started = self.clock()
        path = self.create()

        def interrupt_after_success(message):
            if message.startswith("Slot 1/2:"):
                raise KeyboardInterrupt

        first = self.collect(path, progress=interrupt_after_success)
        self.assertEqual(first["status"], "interrupted")
        self.assertEqual(first["sample_states"], {"pending": 3, "success": 1})
        first_name = observe.SPECIMENS[0]["name"]
        first_http = list(self.factory.calls)
        second = self.collect(path)
        self.assertEqual(second["status"], "completed")
        self.assertEqual(second["sample_states"], {"success": 4})
        self.assertEqual(self.clock(), started + 2 * 3600)
        first_slot_item_calls = [call for call in first_http + self.factory.calls
                                 if call[0] == ITEM and call[1]["marketHashName"] == first_name and call[2] < started + 3600]
        self.assertEqual(len(first_slot_item_calls), 1)
        self.assertEqual(json.loads((path / "manifest.json").read_text())["end_epoch"], started + 2 * 3600)

    def test_downtime_is_missed_and_resume_after_deadline_has_zero_requests(self):
        path = self.create()
        self.clock.time += 5400
        result = self.collect(path)
        self.assertEqual(result["sample_states"], {"missed": 2, "success": 2})
        path2 = self.create()
        self.clock.time += 2 * 3600 + 1
        stopped = self.collect(path2)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["sample_states"], {"missed": 4})
        self.assertEqual(self.factory.calls, [])

    def test_first_system_429_blocks_target_and_all_resumes(self):
        path = self.create()
        blocked = FakeFactory(self.clock, blocked=True)
        result = self.collect(path, blocked)
        self.assertEqual(result["status"], "access_blocked")
        self.assertEqual([call[0] for call in blocked.calls], [SYSTEM])
        resumed = FakeFactory(self.clock)
        result = self.collect(path, resumed)
        self.assertEqual(result["status"], "access_blocked")
        self.assertEqual(resumed.calls, [])
        self.assertEqual(result["http_attempts"], 1)

    def test_crossed_stale_and_formatted_zero_are_retained_as_l0(self):
        def change(row, item):
            row["updateTime"] = int(self.clock()) - 3601
            row["sellPrice"] = "0.00"
            row["biddingPrice"] = "3400.00"

        path = self.create(hours=1)
        result = self.collect(path, FakeFactory(self.clock, change=change))
        self.assertEqual(result["sample_states"], {"success": 2})
        snapshots = [json.loads(row[3]) for row in self.read_rows(path)]
        for row in snapshots:
            self.assertEqual(row["source_sell_price_cny"], "0.00")
            self.assertEqual(row["source_bidding_price_cny"], "3400.00")
            self.assertIsNone(row["source_bidding_count"])
            self.assertTrue({"crossed_source_quotes", "stale_over_1h", "side_missing_or_zero"}.issubset(row["quality_flags"]))
            self.assertFalse(row["execution_eligible"])

    def test_template_mismatch_stops_and_cannot_resume(self):
        def change(row, item):
            row["link"] = "https://www.youpin898.com/market/goods-list?templateId=999&gameId=730"

        path = self.create()
        result = self.collect(path, FakeFactory(self.clock, change=change))
        self.assertEqual(result["status"], "access_blocked")
        self.assertNotIn("success", result["sample_states"])
        resumed = FakeFactory(self.clock)
        self.collect(path, resumed)
        self.assertEqual(resumed.calls, [])

    def test_transport_failures_wait_for_next_slot_without_immediate_retry(self):
        path = self.create()
        failing = FakeFactory(self.clock, transport_fail=True)
        result = self.collect(path, failing)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sample_states"], {"failed": 4})
        comparisons = [row for row in failing.calls if row[0] == MARKET_COMPARISON]
        self.assertEqual(len(comparisons), 4)
        self.assertEqual(len(set(t for _, _, t in comparisons)), 2)

    def test_request_and_storage_budgets_stop_before_http(self):
        path = self.create()
        manifest = json.loads((path / "manifest.json").read_text())
        with closing(sqlite3.connect(path / "observations.sqlite")) as db, db:
            db.executemany("INSERT INTO observer_attempts(slot,item,endpoint,reserved_at) VALUES(0,NULL,?,?)",
                           [(SYSTEM, observe.utc(self.clock()))] * manifest["max_http_requests"])
        result = self.collect(path)
        self.assertEqual(result["status"], "request_budget")
        self.assertEqual(self.factory.calls, [])
        path2 = self.create()
        manifest = json.loads((path2 / "manifest.json").read_text())
        with (path2 / "budget-test.bin").open("wb") as handle:
            handle.truncate(manifest["soft_storage_bytes"])
        result = self.collect(path2)
        self.assertEqual(result["status"], "storage_budget")
        self.assertEqual(self.factory.calls, [])

    def test_changed_source_cannot_resume_and_invalid_inputs_create_no_run(self):
        path = self.create()
        with patch.object(observe, "_source_hashes", return_value={"changed.py": "x"}):
            with self.assertRaises(CollectionError):
                self.collect(path)
        self.assertEqual(self.factory.calls, [])
        with self.assertRaises(CollectionError):
            observe.create_run(hours=True, _clock=self.clock)
        with self.assertRaises(CollectionError):
            observe.create_run(interval_minutes=10, _clock=self.clock)

    def test_pacing_crosses_slot_and_deadline_without_late_http(self):
        path = self.create()
        started = self.clock()
        delayed = FakeFactory(self.clock, pacing_jump=3600)
        result = self.collect(path, delayed)
        self.assertEqual(result["sample_states"], {"missed": 2, "success": 2})
        compared = [call for call in delayed.calls if call[0] == MARKET_COMPARISON]
        self.assertEqual(len(compared), 2)
        self.assertTrue(all(call[2] == started + 3600 for call in compared))
        path2 = self.create()
        started = self.clock()
        delayed = FakeFactory(self.clock, pacing_jump=2 * 3600)
        result = self.collect(path2, delayed)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sample_states"], {"missed": 4})
        self.assertEqual([call[0] for call in delayed.calls], [SYSTEM, ITEM])
        self.assertTrue(all(call[2] < started + 2 * 3600 for call in delayed.calls))

    def test_backward_clock_durably_stops_instead_of_extending_wait(self):
        path = self.create()
        steps = []

        def backward_sleep(seconds):
            steps.append(seconds)
            self.clock.time += seconds if len(steps) == 1 else -10

        factory = FakeFactory(self.clock)
        result = observe.collect(path, progress=lambda value: None, _clock=self.clock,
                                 _sleep=backward_sleep, _client_factory=factory)
        self.assertEqual(result["status"], "safe_error")
        self.assertEqual(result["sample_states"], {"pending": 2, "success": 2})
        resumed = FakeFactory(self.clock)
        self.collect(path, resumed)
        self.assertEqual(resumed.calls, [])


if __name__ == "__main__":
    unittest.main()
