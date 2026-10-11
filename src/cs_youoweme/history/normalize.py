"""Validate market observations without inventing precision or zero filling."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from ..errors import CollectionError
from .store import compact


def number(value, nullable=False, minimum=0):
    if value is None or (nullable and isinstance(value, str) and not value.strip()):
        if nullable:
            return None
        raise CollectionError("Required numeric field is null")
    if isinstance(value, bool):
        raise CollectionError("Boolean in numeric field")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise CollectionError("Invalid numeric field") from None
    if not result.is_finite() or result < minimum:
        raise CollectionError("Non-finite or negative numeric field")
    return str(result)


def integer(value, nullable=False):
    text = number(value, nullable=nullable)
    if text is None:
        return None
    decimal = Decimal(text)
    if decimal != decimal.to_integral_value():
        raise CollectionError("Fractional value in integer field")
    return int(decimal)


def seconds(value):
    result = integer(value)
    if result > 10_000_000_000:
        if result % 1000:
            raise CollectionError("Unexpected subsecond event timestamp")
        result //= 1000
    if result <= 0:
        raise CollectionError("Invalid event timestamp")
    return result


def trade_record(row):
    if not isinstance(row, dict) or not row.get("id") or row.get("platform") is None:
        raise CollectionError("Trade ID or platform is missing; cannot safely deduplicate")
    wear = number(row.get("wearFlot"), nullable=True)
    if wear is not None and Decimal(wear) > 1:
        raise CollectionError("Wear value outside [0,1]")
    stickers = row.get("stickers")
    if stickers is not None and not isinstance(stickers, list):
        raise CollectionError("Unexpected sticker array")
    return (str(row["id"]), str(row["platform"]), seconds(row.get("tradeTime")),
            number(row.get("tradePrice")), integer(row.get("tradeNum"), nullable=True),
            integer(row.get("paintIndex"), nullable=True), integer(row.get("paintSeed"), nullable=True),
            wear, float(wear) if wear is not None else None,
            number(row.get("minSellPrice"), nullable=True),
            compact(row.get("specialStyle")), compact(stickers))


def bar_record(row, period):
    if not isinstance(row, list) or len(row) != 7:
        raise CollectionError("K-line row must contain the verified seven fields")
    timestamp = seconds(row[0])
    opening, close, high, low = (number(v) for v in row[1:5])
    if Decimal(low) > min(Decimal(opening), Decimal(close)) or Decimal(high) < max(Decimal(opening), Decimal(close)) or Decimal(low) > Decimal(high):
        raise CollectionError("Inconsistent source OHLC")
    # Keep original source_time; do not silently alter anomalous source timestamps.
    width = {"1h": 3600, "1d": 86400}[period]
    offset = 28800 if period == "1d" else 0
    bucket = (timestamp + offset) // width * width - offset
    return (timestamp, bucket, opening, close, high, low,
            integer(row[5], nullable=True), number(row[6], nullable=True))
