"""Review a manually exported UU chart response offline; never send requests."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = ROOT / "data/local/staging/uu_charts"
REVIEW_VERSION = "uu-chart-review-1.0"
CHINA = timezone(timedelta(hours=8))
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
METRICS = {1: ("source_trade_price_cny", "CNY"), 11: ("source_listing_count", "source_listing_units")}


def whole(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    raise ValueError("Expected an integer context or timestamp")


def ms_time(value):
    stamp = whole(value)
    if not 10**12 <= stamp < 10**13:
        raise ValueError("Expected a millisecond timestamp; seconds are not accepted")
    return stamp


def iso(stamp, zone=CHINA):
    return (EPOCH + timedelta(milliseconds=stamp)).astimezone(zone).isoformat(timespec="milliseconds")


def number(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("Invalid chart value type")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid numeric chart value") from None
    if not result.is_finite() or result < 0:
        raise ValueError("Expected a finite nonnegative chart value")
    return result


def fields(value, allowed):
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("Unexpected response structure; no content archived")


def reject_constant(_):
    raise ValueError("Nonstandard JSON numeric constant")


def inspect_response(raw, *, template_id, order_type, requested_days):
    """Metric meaning comes from the request context, never the field name price."""
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Offline response exceeds 2 MiB")
    text = raw.decode("utf-8-sig")
    if re.search(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}", text):
        raise ValueError("Credential-like material detected; no content archived")
    payload = json.loads(text, parse_float=Decimal, parse_constant=reject_constant)
    fields(payload, {"code", "msg", "timestamp", "data"})
    if type(payload.get("code")) is not int or payload["code"] != 0:
        raise ValueError("Response does not indicate success")
    order, days = whole(order_type), whole(requested_days)
    template = str(whole(template_id))
    if order not in METRICS or not 1 <= days <= 366 or int(template) < 1:
        raise ValueError("Unsupported chart request context")
    metric, unit = METRICS[order]
    server_time = ms_time(payload.get("timestamp"))
    data = payload.get("data")
    fields(data, {"tradeDataList", "tradePriceList", "blockNum"})
    source = data.get("tradeDataList")
    if not isinstance(source, list):
        raise ValueError("Missing tradeDataList")
    auxiliary = data.get("tradePriceList")
    if auxiliary is not None:
        if not isinstance(auxiliary, list):
            raise ValueError("Unexpected tradePriceList")
        for value in auxiliary:
            number(value)
    if data.get("blockNum") is not None:
        whole(data["blockNum"])
    rows, flags = [], set()
    for sequence, point in enumerate(source):
        fields(point, {"time", "price", "localDate", "proportion", "sourceType"})
        stamp = ms_time(point.get("time"))
        value = number(point.get("price"))
        if order == 11 and value is not None and value != value.to_integral_value():
            raise ValueError("Listing count is fractional; check request context")
        date = point.get("localDate")
        if date is not None and (not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)):
            raise ValueError("Invalid localDate field")
        source_type = point.get("sourceType")
        if source_type is not None and type(source_type) is not int:
            raise ValueError("Unexpected sourceType; do not infer a venue")
        proportion = number(point.get("proportion"))
        row_flags = []
        if value is None:
            row_flags.append("source_value_missing")
        if stamp > server_time:
            row_flags.append("point_after_response_time")
        if date is not None and date != iso(stamp)[:10]:
            row_flags.append("source_local_date_mismatch")
        flags.update(row_flags)
        rows.append({"sequence": sequence, "template_id": template, "order_type": order,
                     "metric": metric, "unit": unit, "source_time_ms": stamp,
                     "source_time_beijing": iso(stamp),
                     "value_raw": None if point.get("price") is None else str(point["price"]),
                     "source_trade_price_cny": str(value) if order == 1 and value is not None else None,
                     "source_listing_count": int(value) if order == 11 and value is not None else None,
                     "source_local_date": date, "source_type_raw": source_type,
                     "source_proportion_raw": str(proportion) if proportion is not None else None,
                     "quality_flags": row_flags, "execution_eligible": False})
    times = [r["source_time_ms"] for r in rows]
    ordered = sorted(set(times))
    gaps = [b - a for a, b in zip(ordered, ordered[1:])]
    if len(ordered) != len(times):
        flags.add("duplicate_source_time")
    seen = {}
    for row in rows:
        stamp = row["source_time_ms"]
        if stamp in seen and seen[stamp] != row["value_raw"]:
            flags.add("conflicting_duplicate_time")
        seen[stamp] = row["value_raw"]
    ascending = all(a <= b for a, b in zip(times, times[1:]))
    if not ascending:
        flags.add("source_points_not_sorted")
    per_day = Counter(iso(t)[:10] for t in times)
    interval_counts = Counter(gaps)
    values = [number(r["value_raw"]) for r in rows if r["value_raw"] is not None]
    summary = {"rows": len(rows), "unique_timestamps": len(ordered),
               "min_value": str(min(values)) if values else None,
               "max_value": str(max(values)) if values else None,
               "first_time_beijing": iso(ordered[0]) if ordered else None,
               "last_time_beijing": iso(ordered[-1]) if ordered else None,
               "ascending_as_received": ascending,
               "null_values": sum(r["value_raw"] is None for r in rows),
               "points_per_calendar_day": dict(sorted(per_day.items())),
               "interval_ms_counts": {str(k): v for k, v in sorted(interval_counts.items())},
               "constant_interval_ms": gaps[0] if gaps and len(interval_counts) == 1 else None,
               "min_interval_ms": min(gaps) if gaps else None,
               "max_interval_ms": max(gaps) if gaps else None,
               "quality_flags": sorted(flags)}
    return {"review_version": REVIEW_VERSION, "source": "user_exported_uu_chart",
            "venue": "UU", "capability_level": "L0", "execution_eligible": False,
            "request_context": {"template_id": template, "order_type": order, "requested_days": days},
            "context_origin": "caller_supplied_not_embedded_in_response",
            "item_identity_verified": False, "statistical_price_semantics_verified": False,
            "metric": metric, "unit": unit, "source_response_time_ms": server_time,
            "source_response_time_beijing": iso(server_time),
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "chart_auxiliary_fields": {"tradePriceList": data.get("tradePriceList"), "blockNum": data.get("blockNum")},
            "summary": summary, "points": rows}


def write_review(raw, report, output, *, input_kind="user_supplied_file_not_transport_capture"):
    """Write a new independent review; no Store migrations or existing-run writes."""
    output = Path(output).resolve()
    if input_kind not in {"user_supplied_file_not_transport_capture", "manual_projection_not_original_response"}:
        raise ValueError("Unexpected input provenance")
    if not output.is_relative_to(REVIEWS.resolve()) or output == REVIEWS.resolve() or output.exists():
        raise ValueError("Choose a new private directory under data/local/staging/uu_charts")
    # Validate bytes again before archive creation; caller cannot archive unreviewed input.
    context = report["request_context"]
    if inspect_response(raw, **context) != report:
        raise ValueError("Input and report differ")
    output.mkdir(parents=True)
    (output / "response_input.json").write_bytes(raw)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    points = report["points"]
    if points:
        with (output / "points.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(points[0]))
            writer.writeheader()
            writer.writerows({**row, "quality_flags": json.dumps(row["quality_flags"])} for row in points)
    with closing(sqlite3.connect(output / "chart_review.sqlite")) as db, db:
        db.execute("CREATE TABLE points(sequence INTEGER PRIMARY KEY, template_id TEXT, order_type INTEGER, metric TEXT, source_time_ms INTEGER, value_raw TEXT, source_trade_price_cny TEXT, source_listing_count INTEGER, point_json TEXT NOT NULL)")
        db.executemany("INSERT INTO points VALUES(?,?,?,?,?,?,?,?,?)", [
            (r["sequence"], r["template_id"], r["order_type"], r["metric"], r["source_time_ms"], r["value_raw"], r["source_trade_price_cny"], r["source_listing_count"], json.dumps(r, ensure_ascii=False)) for r in points])
    (output / "review_source.py").write_bytes(Path(__file__).read_bytes())
    (output / "manifest.json").write_text(json.dumps({"review_version": REVIEW_VERSION,
        "input_sha256": report["input_sha256"], "review_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "request_context": context, "input_kind": input_kind,
        "market_requests_sent": 0, "validated_use": "finite offline source chart review only"}, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--order-type", required=True, choices=["1", "11"])
    parser.add_argument("--days", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--input-kind", choices=["user_supplied_file_not_transport_capture", "manual_projection_not_original_response"], default="user_supplied_file_not_transport_capture")
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        report = inspect_response(raw, template_id=args.template_id, order_type=args.order_type, requested_days=args.days)
        write_review(raw, report, args.output, input_kind=args.input_kind)
    except (ValueError, UnicodeError, OSError, sqlite3.Error):
        print("Offline review failed; no response or credential values printed.")
        return 1
    print(json.dumps({"metric": report["metric"], "rows": report["summary"]["rows"],
                      "constant_interval_ms": report["summary"]["constant_interval_ms"], "market_requests_sent": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
