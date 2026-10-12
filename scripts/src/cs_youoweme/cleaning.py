"""Normalize identities, prices, counts, times and platform quotes."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from .errors import CollectionError
from .paths import CHINA


def numeric(value):
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return str(result) if result.is_finite() else None
    except InvalidOperation:
        return None


def positive_price(value):
    number = numeric(value)
    return number if number is not None and Decimal(number) > 0 else None


def count(value):
    number = numeric(value)
    if number is None:
        return None
    decimal = Decimal(number)
    return int(decimal) if decimal >= 0 and decimal == decimal.to_integral_value() else None


def stamp(value):
    """Support both Unix seconds and milliseconds. No guessed date strings."""
    number = numeric(value)
    if number is None or Decimal(number) <= 0:
        return None
    epoch = float(number)
    if epoch >= 1e12:
        epoch /= 1000
    try:
        return datetime.fromtimestamp(epoch, CHINA).isoformat(timespec="seconds")
    except (OverflowError, ValueError, OSError):
        return None


def identity(market_hash_name):
    quality = "normal"
    name = market_hash_name
    if name.startswith("StatTrak™ "):
        quality, name = "stattrak", name.removeprefix("StatTrak™ ")
    elif name.startswith("Souvenir "):
        quality, name = "souvenir", name.removeprefix("Souvenir ")
    match = re.fullmatch(r"(.+?) \| (.+?) \((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)", name)
    if not match:
        raise CollectionError(f"Not a supported weapon skin: {market_hash_name}")
    weapon, skin, exterior = match.groups()
    return {"weapon": weapon, "skin_en": skin, "quality": quality, "exterior": exterior}


def quote_row(common, market_name, quote, observed, source, api_currency=None):
    public = source == "public_html"
    raw_sell = quote.get("price") if public else quote.get("sellPrice")
    raw_bid = None if public else quote.get("biddingPrice")
    update_raw = quote.get("updateTime")
    updated = stamp(update_raw)
    age = (observed - datetime.fromisoformat(updated)).total_seconds() / 3600 if updated else None
    currency = "CNY" if public else api_currency
    return {
        **common, "market_hash_name": market_name,
        "platform": str(quote.get("platform", "")).upper(),
        "platform_name": quote.get("platformName"), "platform_item_id": quote.get("platformItemId"),
        "currency": currency, "raw_sell_price": numeric(raw_sell),
        "sell_price_cny": positive_price(raw_sell) if currency == "CNY" else None,
        "has_positive_sell_quote": int(positive_price(raw_sell) is not None),
        "sell_count": None if public else count(quote.get("sellCount")),
        "raw_bid_price": numeric(raw_bid), "bid_price_cny": positive_price(raw_bid) if currency == "CNY" else None,
        "bid_count": None if public else count(quote.get("biddingCount")),
        "source_update_time_raw": update_raw, "source_updated_at": updated,
        "quote_age_hours": round(age, 4) if age is not None else None,
        "is_stale_24h": int(age > 24) if age is not None else None,
        "market_url": quote.get("link"),
    }
