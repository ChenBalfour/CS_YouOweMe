"""Aggregate source hourly display-price bars, keeping coverage and missingness."""
from collections import defaultdict
from decimal import Decimal

from ..errors import CollectionError


def aggregate_rows(rows, period="1d"):
    if period not in {"4h", "1d"}:
        raise CollectionError("Aggregation period must be 4h or 1d")
    width = 14400 if period == "4h" else 86400
    expected = width // 3600
    # Resolve overlapping observations by latest request, preserving them in bars.
    latest = {}
    for row in rows:
        hour = row["bucket_time"]
        previous = latest.get(hour)
        if previous is None or (row["source_request"], row["source_time"]) > (previous["source_request"], previous["source_time"]):
            latest[hour] = row
    groups = defaultdict(list)
    for hour, row in latest.items():
        bucket = (hour + 28800) // width * width - 28800
        groups[bucket].append(row)
    result = []
    for bucket, sources in sorted(groups.items()):
        sources.sort(key=lambda row: row["bucket_time"])
        null_volume = sum(r["source_volume"] is None for r in sources)
        null_turnover = sum(r["source_turnover_cny"] is None for r in sources)
        complete = len(sources) == expected
        result.append({
            "bucket_time": bucket, "period": period, "open_cny": sources[0]["open_cny"],
            "close_cny": sources[-1]["close_cny"],
            "high_cny": str(max(Decimal(r["high_cny"]) for r in sources)),
            "low_cny": str(min(Decimal(r["low_cny"]) for r in sources)),
            "source_volume": sum(r["source_volume"] for r in sources) if complete and not null_volume else None,
            "source_turnover_cny": str(sum(Decimal(r["source_turnover_cny"]) for r in sources)) if complete and not null_turnover else None,
            "observed_hours": len(sources), "expected_hours": expected, "complete_hours": complete,
            "null_volume_hours": null_volume, "null_turnover_hours": null_turnover,
            "source_request_ids": sorted({r["source_request"] for r in sources}),
        })
    return result


def aggregate(store, name, period="1d", platform="ALL", style="", start=None, end=None):
    terms = ["market_hash_name=?", "period='1h'", "platform=?", "style=?"]
    values = [name, platform, style]
    for term, value in (("bucket_time>=?", start), ("bucket_time<?", end)):
        if value is not None:
            terms.append(term)
            values.append(value)
    rows = store.db.execute("SELECT * FROM bars WHERE " + " AND ".join(terms), values).fetchall()
    return {"name": name, "platform": platform, "style": style,
            "price_basis": "website display-price OHLC, not trade-derived OHLC",
            "aggregation": period, "timezone": "Asia/Shanghai", "last_bucket_may_be_partial": True,
            "rows": aggregate_rows(rows, period)}
