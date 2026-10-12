"""Searchable catalog snapshots; SteamDT IDs are distinct from marketplace IDs."""
from __future__ import annotations

import json
import re
from collections import Counter

from ..collectors.official import OfficialClient
from ..collectors.website import ITEM, OVERVIEW, VARIANTS
from ..config import read_key
from ..errors import CollectionError
from .store import compact, now

WEAPONS = {
    "AK-47", "AUG", "AWP", "CZ75-Auto", "Desert Eagle", "Dual Berettas",
    "FAMAS", "Five-SeveN", "G3SG1", "Galil AR", "Glock-18", "M249",
    "M4A1-S", "M4A4", "MAC-10", "MAG-7", "MP5-SD", "MP7", "MP9", "Negev",
    "Nova", "P2000", "P250", "P90", "PP-Bizon", "R8 Revolver", "SCAR-20",
    "SG 553", "SSG 08", "Sawed-Off", "Tec-9", "UMP-45", "USP-S", "XM1014",
    "Zeus x27",
}
GLOVES = {"Bloodhound Gloves", "Broken Fang Gloves", "Driver Gloves", "Hand Wraps",
          "Hydra Gloves", "Moto Gloves", "Specialist Gloves", "Sport Gloves"}
KNIVES = {"Bayonet", "Bowie Knife", "Butterfly Knife", "Classic Knife", "Falchion Knife",
          "Flip Knife", "Gut Knife", "Huntsman Knife", "Karambit", "Kukri Knife",
          "M9 Bayonet", "Navaja Knife", "Nomad Knife", "Paracord Knife", "Shadow Daggers",
          "Skeleton Knife", "Stiletto Knife", "Survival Knife", "Talon Knife", "Ursus Knife"}
EXTERIORS = {"Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"}
TARGETS = {"weapon", "knife", "glove"}


def dimensions(name):
    base = name.removeprefix("★ ")
    quality = "normal"
    for prefix, tag in (("StatTrak™ ", "stattrak"), ("Souvenir ", "souvenir")):
        if base.startswith(prefix):
            base, quality = base[len(prefix):], tag
            break
    exterior = None
    match = re.search(r" \(([^()]*)\)$", base)
    if match and match[1] in EXTERIORS:
        exterior = match[1]
        base = base[:match.start()]
    weapon, sep, skin = base.partition(" | ")
    if weapon in WEAPONS and sep:
        category = "weapon"
    elif weapon in GLOVES:
        category = "glove"
    elif weapon in KNIVES:
        category = "knife"
    else:
        category = "other"
    return (category, weapon, skin or None, quality, exterior, base)


def upsert_item(db, row, request_id):
    name = row.get("marketHashName")
    if not isinstance(name, str) or not name.strip():
        raise CollectionError("Catalog record missing marketHashName")
    category, weapon, skin, quality, exterior, family = dimensions(name)
    stamp = now()
    db.execute("""
        INSERT INTO catalog(market_hash_name,name_zh,category,weapon,skin,quality,exterior,family,
                            first_seen,last_seen,source_request)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(market_hash_name) DO UPDATE SET name_zh=excluded.name_zh,
            active=1,last_seen=excluded.last_seen,source_request=excluded.source_request
    """, (name, row.get("name"), category, weapon, skin, quality, exterior, family, stamp, stamp, request_id))
    for platform in row.get("platformList", []):
        if not platform.get("name") or not platform.get("itemId"):
            raise CollectionError("Catalog platform ID is missing")
        db.execute("INSERT OR REPLACE INTO platform_ids VALUES(?,?,?)",
                   (name, platform["name"], str(platform["itemId"])))


def sync_catalog(store, source=None):
    if source:
        raw = source.read_bytes()
        cached = True
    else:
        raw, cached = OfficialClient(read_key()).base()
    response = json.loads(raw)
    rows = response.get("data") if isinstance(response, dict) else None
    if not isinstance(response, dict) or response.get("success") is not True or not isinstance(rows, list) or not rows:
        raise CollectionError("Invalid catalog response; existing directory preserved")
    names = [r.get("marketHashName") for r in rows]
    if any(not isinstance(n, str) or not n.strip() for n in names) or len(set(names)) != len(names):
        raise CollectionError("Missing or duplicate catalog names; existing directory preserved")
    request_id = store.archive("https://open.steamdt.com/open/cs2/v1/base", {}, now(), raw, 200, 0)
    with store.db:
        store.db.execute("UPDATE catalog SET active=0")
        store.db.execute("DELETE FROM platform_ids")
        for row in rows:
            upsert_item(store.db, row, request_id)
    counts = Counter(dimensions(n)[0] for n in names)
    return {"source_rows": len(rows), "categories": dict(counts), "cached_or_imported": cached,
            "catalog_scope": "current source catalog; delisted historical items may be absent"}


def search_catalog(store, query="", category=None, exterior=None, limit=50):
    if not 1 <= limit <= 1000:
        raise CollectionError("Search limit must be between 1 and 1000")
    terms, values = [], []
    for token in query.split():
        pattern = "%" + token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        terms.append("(market_hash_name LIKE ? ESCAPE '\\' OR name_zh LIKE ? ESCAPE '\\')")
        values.extend((pattern, pattern))
    for column, value in (("category", category), ("exterior", exterior)):
        if value:
            terms.append(column + "=?")
            values.append(value)
    where = " WHERE " + " AND ".join(terms) if terms else ""
    count = store.db.execute("SELECT count(*) FROM catalog" + where, values).fetchone()[0]
    rows = store.db.execute("SELECT market_hash_name,name_zh,category,weapon,skin,quality,exterior,steamdt_item_id,active FROM catalog"
                            + where + " ORDER BY market_hash_name LIMIT ?", (*values, limit)).fetchall()
    return {"matched": count, "items": [dict(row) for row in rows]}


def resolve_item(store, client, name):
    params = {"appId": 730, "marketHashName": name}
    item, request_id = client.call(ITEM, params, post=True)
    if not isinstance(item, dict) or item.get("marketHashName") != name or not item.get("itemId"):
        raise CollectionError("Website item identity mismatch")
    with store.db:
        store.db.execute("UPDATE catalog SET steamdt_item_id=?,metadata_request=? WHERE market_hash_name=?",
                         (str(item["itemId"]), request_id, name))
        store.db.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?,?)", (name, request_id, compact(item)))
    variants, variant_request = client.call(VARIANTS, params, post=True)
    if not isinstance(variants, dict) or not isinstance(variants.get("all"), list):
        raise CollectionError("Unexpected related-variant response")
    with store.db:
        for row in variants["all"]:
            other_name = row.get("marketHashName")
            if not other_name or not row.get("itemId"):
                raise CollectionError("Related-variant identity is missing")
            if not store.db.execute("SELECT 1 FROM catalog WHERE market_hash_name=?", (other_name,)).fetchone():
                upsert_item(store.db, row, variant_request)
            store.db.execute("UPDATE catalog SET steamdt_item_id=?,metadata_request=? WHERE market_hash_name=?",
                             (str(row["itemId"]), variant_request, other_name))
    return str(item["itemId"])


def discover_styles(store, client, name, item_id):
    data, request_id = client.call(OVERVIEW, {"itemId": item_id})
    if not isinstance(data, dict) or not isinstance(data.get("specialStyles"), list):
        raise CollectionError("Unexpected special-style directory")
    with store.db:
        for row in data["specialStyles"]:
            if not isinstance(row, dict) or not row.get("value"):
                raise CollectionError("Special style missing value")
            store.db.execute("INSERT OR REPLACE INTO styles VALUES(?,?,?,?)",
                             (name, str(row["value"]), row.get("name"), request_id))
    return [str(r["value"]) for r in data["specialStyles"]]
