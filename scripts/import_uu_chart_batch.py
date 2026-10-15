"""Import the user's browser chart download offline; never send market requests."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3

try:
    from . import review_uu_chart as chart
except ImportError:
    import review_uu_chart as chart

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "data/local/staging/uu_charts"
VERSION = "uu-chart-batch-import-1.0"
COLLECTOR_VERSION = "uu-browser-charts-1.0"


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Missing browser timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("Browser timestamp needs timezone")
    return value


def inspect_batch(raw):
    if len(raw) > 40 * 1024 * 1024:
        raise ValueError("Batch exceeds 40 MiB")
    text = raw.decode("utf-8-sig")
    if re.search(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}", text):
        raise ValueError("Credential-like input; nothing archived")
    batch = json.loads(text)
    chart.fields(batch, {"format", "collector_version", "collector_source", "run_id", "created_at", "updated_at", "template_id", "item_label", "half_year_day", "identity_verified", "status", "tasks"})
    if batch.get("format") != "uu-chart-batch-1.0" or batch.get("collector_version") != COLLECTOR_VERSION or batch.get("identity_verified") is not False:
        raise ValueError("Unsupported browser batch")
    source = (ROOT / "scripts/collect_uu_charts.js").read_text(encoding="utf-8")
    known_source = source[source.index("(function UUChartCollector()") :]
    if not isinstance(batch.get("collector_source"), str) or batch["collector_source"].replace("\r\n", "\n") != known_source:
        raise ValueError("Collector source/version differs")
    run_id = batch.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"uu_charts_[A-Za-z0-9_-]{8,100}", run_id):
        raise ValueError("Invalid batch id")
    template = str(chart.whole(batch.get("template_id")))
    half = chart.whole(batch.get("half_year_day"))
    if int(template) < 1 or not 90 < half <= 366:
        raise ValueError("Half-year parameter not confirmed")
    if not isinstance(batch.get("item_label"), str) or not 1 <= len(batch["item_label"].strip()) <= 200:
        raise ValueError("Missing user item description")
    if not isinstance(batch.get("status"), str) or not re.fullmatch(r"[a-z0-9_]{1,80}", batch["status"]):
        raise ValueError("Invalid batch status")
    timestamp(batch.get("created_at"))
    timestamp(batch.get("updated_at"))
    source_tasks = batch.get("tasks")
    if not isinstance(source_tasks, list) or len(source_tasks) != 8:
        raise ValueError("Expected four windows times two metrics")
    expected = {f"{window}_{order}": (window, day, order) for window, day in (("7d", 7), ("15d", 15), ("90d", 90), ("half_year", half)) for order in (1, 11)}
    seen, tasks, points, counts = set(), [], [], Counter()
    for task in source_tasks:
        chart.fields(task, {"id", "window", "request_body", "status", "attempts", "origin", "started_at", "received_at", "http_status", "response_text", "error"})
        key = task.get("id")
        if key not in expected or key in seen:
            raise ValueError("Unknown or repeated task")
        seen.add(key)
        window, day, order = expected[key]
        body = task.get("request_body")
        chart.fields(body, {"templateId", "orderType", "day", "customizeDay", "filterTemplateTypeNames", "templateTypeName"})
        if task.get("window") != window or str(chart.whole(body.get("templateId"))) != template or chart.whole(body.get("orderType")) != order or chart.whole(body.get("day")) != day or body.get("customizeDay") is not False or body.get("filterTemplateTypeNames") != [] or body.get("templateTypeName") != "":
            raise ValueError("Request identity/window/filter mismatch")
        state, attempts = task.get("status"), task.get("attempts")
        if state not in {"pending", "success", "failed", "interrupted_unknown"} or type(attempts) is not int or attempts != (0 if state == "pending" else 1):
            raise ValueError("Invalid task checkpoint")
        row = {"task_id": key, "window": window, "requested_days": day, "order_type": order, "status": state, "attempts": attempts}
        if attempts:
            timestamp(task.get("started_at"))
            if task.get("origin") not in {"user_triggered_page_request", "explicit_user_batch"}:
                raise ValueError("Unknown request provenance")
        if state == "success":
            timestamp(task.get("received_at"))
            if type(task.get("http_status")) is not int or task["http_status"] != 200 or not isinstance(task.get("response_text"), str):
                raise ValueError("Successful task needs an exact response text")
            report = chart.inspect_response(task["response_text"].encode("utf-8"), template_id=template, order_type=order, requested_days=day)
            if not report["points"]:
                raise ValueError("Empty source series")
            row.update(browser_received_at=task["received_at"], source_response_time_ms=report["source_response_time_ms"], response_text_sha256=report["input_sha256"], summary=report["summary"])
            for point in report["points"]:
                points.append({"task_id": key, "window": window, "requested_days": day, "browser_received_at": task["received_at"], "historical_available_at": None, **point})
        elif "response_text" in task:
            raise ValueError("Unsuccessful task cannot supply successful data")
        counts[state] += 1
        tasks.append(row)
    if batch["status"] == "completed" and counts["success"] != 8:
        raise ValueError("Incomplete batch cannot claim completion")
    return {"import_version": VERSION, "collector_version": COLLECTOR_VERSION, "run_id": run_id, "template_id": template, "item_label": batch["item_label"], "half_year_day": half, "item_identity_verified": False, "capability_level": "L0", "execution_eligible": False, "source": "user_browser_chart_export", "input_sha256": hashlib.sha256(raw).hexdigest(), "source_text_kind": "browser_decoded_or_xhr_json_reserialized_not_transport_bytes", "market_requests_sent_by_importer": 0, "status_counts": dict(counts), "complete": counts["success"] == 8, "tasks": tasks, "points": points}


def import_batch(raw, output):
    report = inspect_batch(raw)  # Validate every task before creating any output.
    output = Path(output).resolve()
    if not output.is_relative_to(DESTINATION.resolve()) or output == DESTINATION.resolve() or output.exists():
        raise ValueError("Use a new private directory under data/local/staging/uu_charts")
    output.mkdir(parents=True)
    (output / "batch_input.json").write_bytes(raw)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["points"]:
        with (output / "points.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(report["points"][0]))
            writer.writeheader()
            writer.writerows({**r, "quality_flags": json.dumps(r["quality_flags"])} for r in report["points"])
    with closing(sqlite3.connect(output / "chart_batch.sqlite")) as db, db:
        db.execute("CREATE TABLE tasks(task_id TEXT PRIMARY KEY, window TEXT, requested_days INTEGER, order_type INTEGER, status TEXT, attempts INTEGER, task_json TEXT NOT NULL)")
        db.execute("CREATE TABLE points(task_id TEXT, sequence INTEGER, source_time_ms INTEGER, source_trade_price_cny TEXT, source_listing_count INTEGER, browser_received_at TEXT, historical_available_at TEXT, point_json TEXT NOT NULL, PRIMARY KEY(task_id,sequence), FOREIGN KEY(task_id) REFERENCES tasks(task_id))")
        db.executemany("INSERT INTO tasks VALUES(?,?,?,?,?,?,?)", [(r["task_id"], r["window"], r["requested_days"], r["order_type"], r["status"], r["attempts"], json.dumps(r, ensure_ascii=False)) for r in report["tasks"]])
        db.executemany("INSERT INTO points VALUES(?,?,?,?,?,?,?,?)", [(r["task_id"], r["sequence"], r["source_time_ms"], r["source_trade_price_cny"], r["source_listing_count"], r["browser_received_at"], None, json.dumps(r, ensure_ascii=False)) for r in report["points"]])
    snapshots = {}
    for filename in ("import_uu_chart_batch.py", "review_uu_chart.py", "collect_uu_charts.js"):
        content = (ROOT / "scripts" / filename).read_bytes()
        (output / filename).write_bytes(content)
        snapshots[filename] = hashlib.sha256(content).hexdigest()
    manifest = {k: v for k, v in report.items() if k not in {"points", "tasks", "item_label"}}
    manifest.update(source_sha256=snapshots, immutable_windows=True, overlap_policy="retain each window and source timestamp; never overwrite cross-window values", historical_available_at="unknown; browser receipt is only current availability")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = import_batch(args.input.read_bytes(), args.output)
    except (ValueError, TypeError, UnicodeError, OSError, sqlite3.Error):
        print("Offline batch import failed; no input or credential values printed.")
        return 1
    print(json.dumps({"complete": report["complete"], "status_counts": report["status_counts"], "points": len(report["points"]), "market_requests_sent": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
