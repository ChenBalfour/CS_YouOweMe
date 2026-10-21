import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

import _support
from cs_youoweme.history import store as storage, universe
from cs_youoweme.history.catalog import sync_catalog
from cs_youoweme.history.universe import fresh_price, rank_candidates, sector_types, narrow
from cs_youoweme.errors import CollectionError


class UniverseTests(unittest.TestCase):
    def test_price_band_cap_keeps_hundred_yuan_candidates_in_scope(self):
        rows = [{"market_hash_name": str(i), "category": "weapon", "family": str(i),
                 "source_heat_rank": i+1, "survive_count": 100+i,
                 "recent_known_volume": 100, "observed_recent_hours": 168,
                 "price_cny": 2000 if i < 10 else 200} for i in range(13)]
        selected, reserves, rejected = rank_candidates(rows)
        self.assertEqual(sum(r["price_band"] == "thousands" for r in selected), 8)
        self.assertEqual(sum(r["price_band"] == "hundreds" for r in selected), 3)
        self.assertEqual(len(reserves), 2)
        self.assertEqual(rejected, [])

    def test_narrow_snapshot_preserves_observation_time_and_sql_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(storage, "LOCAL_DATA", root), patch.object(universe, "LOCAL_DATA", root):
                with storage.Store(root / "db/market.sqlite") as store:
                    names = ["AK-47 | Test (Factory New)", "★ Bayonet"]
                    source = root / "source.json"
                    source.write_text(json.dumps({"success": True, "data": [{"marketHashName": n} for n in names]}))
                    sync_catalog(store, source)
                    rows = [{"market_hash_name": n, "category": c, "family": n,
                             "source_heat_rank": 1, "survive_count": 100, "recent_known_volume": 20,
                             "observed_recent_hours": 168, "price_cny": 200} for n, c in zip(names, ["weapon", "knife"])]
                    source.write_text(json.dumps({"selected_at": "2026-10-11T16:00:00+00:00",
                        "criteria": {}, "items": rows, "reserves": [], "rejected": []}))
                    output = root / "weapon.json"
                    first = narrow(store, source, output)
                    result = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual(result["selected_at"], "2026-10-11T16:00:00+00:00")
                    self.assertEqual(result["scope"], "weapon")
                    self.assertEqual(first["selected_items"], 1)
                    self.assertEqual(store.db.execute("SELECT market_hash_name,role FROM universe_members").fetchone()[:],
                                     (names[0], "selected"))
                    self.assertEqual(store.db.execute("SELECT count(*) FROM jobs").fetchone()[0], 0)
    def test_recent_quote_filters_zero_stale_and_steam_wallet(self):
        item = {"sellingPriceList": [{"platform": "buff", "price": 100, "updateTime": 9000},
                                     {"platform": "youpin", "price": 90, "lastUpdate": 9900},
                                     {"platform": "steam", "price": 50, "updateTime": 9900},
                                     {"platform": "c5", "price": 0, "updateTime": 9900},
                                     {"platform": "haloskins", "price": 10, "updateTime": 1}]}
        self.assertEqual(fresh_price(item, 10000), 90)
        self.assertIsNone(fresh_price(item, 20000))

    def test_heat_supply_activity_scored_within_sector_and_family_cap(self):
        rows = [{"market_hash_name": str(i), "category": "weapon", "family": "same" if i < 3 else "other",
                 "source_heat_rank": i+1, "survive_count": 100+i*100,
                 "recent_known_volume": 100-i*10, "observed_recent_hours": 168, "price_cny": 100}
                for i in range(4)]
        selected, reserves, rejected = rank_candidates(rows, per_sector=3)
        self.assertEqual([r["market_hash_name"] for r in selected], ["0", "1", "3"])
        self.assertEqual(len(reserves), 1)
        self.assertEqual(rejected, [])
        bad = {**rows[0], "recent_known_volume": 0, "survive_count": 0}
        self.assertEqual(len(rank_candidates([bad])[2]), 1)

    def test_source_dictionary_keys_are_used_without_guessing(self):
        attributes = [{"key": "Type", "list": [{"alias": "Knife", "key": "observed-knife"},
                      {"alias": "Gloves", "key": "observed-gloves"}, {"alias": "Rifle", "key": "observed-rifle"}]}]
        self.assertEqual(sector_types(attributes)["knife"], ["observed-knife"])
        with self.assertRaises(CollectionError):
            sector_types([])
