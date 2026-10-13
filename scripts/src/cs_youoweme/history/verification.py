"""Conservative interpretations of evidence verified during the finite P03 run."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from ..errors import CollectionError
from .normalize import integer, number, seconds


def trade_venue(platform_code):
    """The SteamDT table labels code 1 Steam, and 0/2/3 only third-party.

    Evidence: BHvVoeIz.js (2026-10-13 capture). This is a source display mapping,
    not a claim that a source-observed record is a settled exchange transaction.
    """
    code = str(platform_code)
    return "STEAM" if code == "1" else "third_party_unknown" if code in {"0", "2", "3"} else "unknown"


def uu_snapshot(row, observed_at, source_request):
    if not isinstance(row, dict) or str(row.get("platform", "")).upper() != "YOUPIN" or row.get("platformName") != "悠悠":
        raise CollectionError("Market row lacks verified UU identity")
    link = urlsplit(row.get("link") or "")
    params = parse_qs(link.query)
    if link.scheme != "https" or link.netloc != "www.youpin898.com" or params.get("gameId") != ["730"] or len(params.get("templateId", [])) != 1:
        raise CollectionError("UU template link identity missing")
    sell, bid = (number(row.get(key), nullable=True) for key in ("sellPrice", "biddingPrice"))
    updated = seconds(row["updateTime"]) if row.get("updateTime") is not None else None
    observed = datetime.fromisoformat(observed_at).astimezone(timezone.utc).timestamp()
    age = observed - updated if updated else None
    flags = []
    if sell is not None and bid is not None and Decimal(bid) > Decimal(sell):
        flags.append("crossed_source_quotes")
    if age is None:
        flags.append("source_time_missing")
    elif age < 0:
        flags.append("source_time_future")
    elif age > 3600:
        flags.append("stale_over_1h")
    if sell in {None, "0"} or bid in {None, "0"}:
        flags.append("side_missing_or_zero")
    return {"source": "steamdt", "venue": "UU", "capability_level": "L0",
            "template_id": params["templateId"][0], "source_sell_price_cny": sell,
            "source_bidding_price_cny": bid, "source_sell_count": integer(row.get("sellCount"), nullable=True),
            "source_bidding_count": integer(row.get("biddingCount"), nullable=True),
            "source_update_time": updated, "observed_at_utc": observed_at, "age_seconds": age,
            "source_request": source_request, "quality_flags": flags,
            "single_item_depth_verified": False, "attribute_comparability_verified": False,
            "execution_eligible": False}


def source_trade(row, source_request):
    if not isinstance(row, dict) or row.get("id") is None or row.get("platform") is None:
        raise CollectionError("Source trade identity missing")
    wear = number(row.get("wearFlot"), nullable=True)
    if wear is not None and Decimal(wear) > 1:
        raise CollectionError("Source wear exceeds 1")
    stickers = row.get("stickers")
    if stickers is not None and not isinstance(stickers, list):
        raise CollectionError("Unexpected source stickers")
    state = "missing" if "stickers" not in row else "null" if stickers is None else "empty_array" if not stickers else "populated"
    return {"source_trade_id": str(row["id"]), "platform_code": str(row["platform"]),
            "venue": trade_venue(row["platform"]), "trade_time": seconds(row.get("tradeTime")),
            "source_price_cny": number(row.get("tradePrice")),
            "source_trade_num": integer(row.get("tradeNum"), nullable=True),
            "paint_index": integer(row.get("paintIndex"), nullable=True),
            "paint_seed": integer(row.get("paintSeed"), nullable=True), "wear_decimal": wear,
            "stickers_state": state, "source_sticker_count": len(stickers) if isinstance(stickers, list) else None,
            "source_min_sell_price_cny": number(row.get("minSellPrice"), nullable=True),
            "source_request": source_request, "record_semantics": "source_observation_not_verified_order",
            "execution_eligible": False}
