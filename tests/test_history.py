"""Synthetic endpoint responses test cursors, crash recovery and source precision."""
import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _support
from cs_youoweme.errors import AccessStopped, CollectionError
from cs_youoweme.history import store as storage
from cs_youoweme.history.catalog import dimensions, search_catalog, sync_catalog
from cs_youoweme.history.jobs import boundary, commit_page, fetch_page, plan, work
from cs_youoweme.history.normalize import bar_record, trade_record
from cs_youoweme.history.query import coverage, trade_query
from cs_youoweme.history.aggregate import aggregate_rows

NAME = "M4A4 | Buzz Kill (Factory New)"
START = boundary("2025-06-01")
END = START + 7200


def source_trade(id="record-1", timestamp=START + 10):
    return {"id": id, "platform": 3, "tradeTime": str(timestamp), "tradePrice": 322,
            "tradeNum": 1, "paintIndex": 632, "paintSeed": 924,
            "wearFlot": "0.0450133271515369", "minSellPrice": None,
            "specialStyle": None, "stickers": [],
            "steamInfo": {"private_user": "excluded-from-normalized-data"}}


class FakeClient:
    def __init__(self, store, pages):
        self.store, self.pages, self.calls = store, iter(pages), []
        self.requests = 0

    def call(self, path, params=None, post=False):
        self.calls.append((path, params, post))
        self.requests += 1
        data = next(self.pages)
        if isinstance(data, Exception):
            raise data
        raw = json.dumps({"success": True, "data": data}).encode()
        request = self.store.archive(path, params, storage.now(), raw, 200, 0)
        return data, request


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.local_patch = patch.object(storage, "LOCAL_DATA", root)
        self.local_patch.start()
        self.store = storage.Store(root / "db/market.sqlite")
        response = {"success": True, "data": [
            {"name": "M4A4 中文", "marketHashName": NAME, "platformList": [{"name": "BUFF", "itemId": "marketplace-id"}]},
            {"name": "刀", "marketHashName": "★ StatTrak™ Butterfly Knife | Doppler (Factory New)", "platformList": []},
            {"name": "手套", "marketHashName": "★ Sport Gloves | Vice (Field-Tested)", "platformList": []},
            {"name": "贴纸", "marketHashName": "Sticker | Example", "platformList": []},
        ]}
        self.source = root / "catalog.json"
        self.source.write_text(json.dumps(response), encoding="utf-8")
        sync_catalog(self.store, self.source)
        with self.store.db:
            self.store.db.execute("UPDATE catalog SET steamdt_item_id='website-id' WHERE market_hash_name=?", (NAME,))

    def tearDown(self):
        self.store.close()
        self.local_patch.stop()
        self.temp.cleanup()

    def job(self, kind="trades"):
        plan(self.store, START, END, [NAME], kinds=[kind])
        return self.store.db.execute("SELECT * FROM jobs").fetchone()

    def test_catalog_identity_and_marketplace_id_separation(self):
        self.assertEqual(dimensions("★ StatTrak™ Butterfly Knife | Doppler (Factory New)")[:5],
                         ("knife", "Butterfly Knife", "Doppler", "stattrak", "Factory New"))
        self.assertEqual(dimensions("★ Bayonet")[0], "knife")
        result = search_catalog(self.store, "M4A4 中文")
        self.assertEqual(result["matched"], 1)
        self.assertEqual(search_catalog(self.store, "%")["matched"], 0)
        knife = search_catalog(self.store, category="knife")["items"][0]
        self.assertIsNone(knife["steamdt_item_id"])
        self.assertEqual(plan(self.store, START, END)["selected_items"], 3)

    def test_catalog_rejects_duplicate_without_destroying_previous_snapshot(self):
        self.source.write_text(json.dumps({"success": True, "data": [{"marketHashName": NAME}] * 2}), encoding="utf-8")
        with self.assertRaises(CollectionError):
            sync_catalog(self.store, self.source)
        self.assertEqual(search_catalog(self.store)["matched"], 4)

    def test_plan_is_idempotent_and_end_date_includes_beijing_day(self):
        self.assertEqual(boundary("2025-06-01", end=True) - START, 86400)
        self.assertEqual(boundary("2025-06-01T00:00:00+08:00", end=True), START)
        self.assertEqual(plan(self.store, START, END, [NAME])["new_jobs"], 2)
        self.assertEqual(plan(self.store, START, END, [NAME])["new_jobs"], 0)

    def test_legacy_trade_job_migration_preserves_saved_cursor(self):
        job = self.job()
        client = FakeClient(self.store, [{"list": [source_trade()], "nextId": "saved-cursor"}])
        work(self.store, max_pages=1, client=client, emit=lambda *a, **kw: None)
        with self.store.db:
            self.store.db.execute("UPDATE jobs SET period='1h'")
            self.store.db.execute("PRAGMA user_version=1")
        path = self.store.path
        self.store.close()
        self.store = storage.Store(path)
        migrated = self.store.db.execute("SELECT * FROM jobs").fetchone()
        self.assertEqual((migrated["job_id"], migrated["cursor"], migrated["pages"], migrated["period"]),
                         (job["job_id"], "saved-cursor", 1, "event"))
        self.assertEqual(plan(self.store, START, END, [NAME], kinds=["trades"])["new_jobs"], 0)
        self.assertEqual(len(coverage(self.store, NAME, kind="trades")["coverage"]), 1)

    def test_invalid_catalog_shape_preserves_directory(self):
        self.source.write_text("[]", encoding="utf-8")
        with self.assertRaises(CollectionError):
            sync_catalog(self.store, self.source)
        self.assertEqual(search_catalog(self.store)["matched"], 4)

    def test_trade_precision_nulls_and_no_identity_export(self):
        row = trade_record(source_trade())
        self.assertEqual(row[7], "0.0450133271515369")
        self.assertIsNone(row[9])
        self.assertNotIn("private_user", str(row))
        steam = source_trade()
        steam["wearFlot"] = ""
        self.assertIsNone(trade_record(steam)[7])
        bad = source_trade()
        bad["wearFlot"] = "NaN"
        with self.assertRaises(CollectionError):
            trade_record(bad)
        bad["wearFlot"] = "1.01"
        with self.assertRaises(CollectionError):
            trade_record(bad)

    def test_hourly_bars_preserve_missing_metrics_and_source_timestamp(self):
        row = bar_record([str(START + 6), 10, 11, 12, 9, None, None], "1h")
        self.assertEqual(row[:2], (START + 6, START))
        self.assertEqual(row[-2:], (None, None))
        with self.assertRaises(CollectionError):
            bar_record([START, 10, 11, 9, 12, 0, 0], "1h")

    def test_resume_commits_overlapping_pages_exactly_once(self):
        self.job()
        first = FakeClient(self.store, [{"list": [source_trade()], "nextId": "opaque,cursor"}])
        work(self.store, max_pages=1, client=first, emit=lambda *a, **kw: None)
        self.assertEqual(self.store.db.execute("SELECT cursor FROM jobs").fetchone()[0], "opaque,cursor")
        second = FakeClient(self.store, [{"list": [source_trade(), source_trade("record-2", START + 9)], "nextId": None}])
        result = work(self.store, max_pages=1, client=second, emit=lambda *a, **kw: None)
        self.assertIsNone(result["stopped"])
        self.assertEqual(second.calls[0][1]["nextId"], "opaque,cursor")
        job = self.store.db.execute("SELECT * FROM jobs").fetchone()
        self.assertEqual((job["state"], job["pages"], job["fetched_rows"], job["inserted_rows"]), ("done", 2, 3, 2))
        self.assertEqual(len(trade_query(self.store, NAME)["rows"]), 2)

    def test_repeated_cursor_stops_without_advancing_checkpoint(self):
        self.job()
        client = FakeClient(self.store, [{"list": [source_trade()], "nextId": "same"},
                                         {"list": [source_trade()], "nextId": "same"}])
        result = work(self.store, max_pages=2, client=client, emit=lambda *a, **kw: None)
        self.assertIn("Repeated", result["stopped"])
        self.assertEqual(self.store.db.execute("SELECT pages FROM jobs").fetchone()[0], 1)

    def test_page_and_checkpoint_roll_back_together(self):
        job = self.job()
        with self.assertRaises(sqlite3.IntegrityError):
            commit_page(self.store, job, [trade_record(source_trade())], "next", None, 9999)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM trades").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT cursor FROM jobs").fetchone()[0], "")

    def test_backward_kline_and_gap_reporting(self):
        job = self.job("bars")
        client = FakeClient(self.store, [[[str(START + 3600), 10, 11, 12, 9, None, None]], []])
        work(self.store, max_pages=2, client=client, emit=lambda *a, **kw: None)
        self.assertEqual(client.calls[1][1]["maxTime"], START + 3599)
        report = coverage(self.store, NAME)["coverage"][0]
        self.assertEqual(report["finish_reason"], "source_history_exhausted")
        self.assertEqual(report["missing_buckets"], 1)
        self.assertFalse(report["complete_buckets"])

    def test_access_stop_blocks_worker_and_requires_explicit_retry(self):
        self.job()
        blocked = FakeClient(self.store, [AccessStopped("Website HTTP 429; worker stopped")])
        work(self.store, client=blocked, emit=lambda *a, **kw: None)
        self.assertEqual(self.store.db.execute("SELECT state FROM jobs").fetchone()[0], "blocked")
        resumed = FakeClient(self.store, [{"list": [], "nextId": None}])
        self.assertEqual(work(self.store, client=resumed, emit=lambda *a, **kw: None)["committed_pages"], 0)
        self.assertEqual(work(self.store, retry_blocked=True, client=resumed, emit=lambda *a, **kw: None)["committed_pages"], 1)

    def test_capacity_stop_keeps_pending_job_and_cursor(self):
        self.job()
        client = FakeClient(self.store, [])
        result = work(self.store, client=client, max_storage_mb=.0001, emit=lambda *a, **kw: None)
        self.assertIn("budget", result["stopped"])
        self.assertEqual(client.requests, 0)
        self.assertEqual(self.store.db.execute("SELECT cursor FROM jobs").fetchone()[0], "")

    def test_compressed_raw_hash_and_os_lock(self):
        request = self.store.db.execute("SELECT * FROM requests LIMIT 1").fetchone()
        raw = gzip.decompress((self.store.path.parent / request["raw_path"]).read_bytes())
        import hashlib
        self.assertEqual(hashlib.sha256(raw).hexdigest(), request["raw_sha256"])
        with self.store.worker_lock():
            with self.assertRaises(AccessStopped):
                with self.store.worker_lock():
                    pass
        with self.store.worker_lock():
            pass

    def test_aggregation_marks_gaps_and_never_zero_fills_null_volume(self):
        rows = [{"bucket_time": START + i*3600, "source_time": START + i*3600,
                 "source_request": 1, "open_cny": "10", "close_cny": "11",
                 "high_cny": "12", "low_cny": "9", "source_volume": None if i == 1 else 2,
                 "source_turnover_cny": "20"} for i in range(4)]
        bar = aggregate_rows(rows, "4h")[0]
        self.assertTrue(bar["complete_hours"])
        self.assertIsNone(bar["source_volume"])
        self.assertEqual(bar["source_turnover_cny"], "80")
        missing = aggregate_rows(rows[:3], "4h")[0]
        self.assertFalse(missing["complete_hours"])
        self.assertIsNone(missing["source_turnover_cny"])
