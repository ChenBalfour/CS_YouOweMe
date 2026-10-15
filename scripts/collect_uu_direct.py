"""User-run, bounded UU chart HTTP pilot. No browser, login, or automatic retries."""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import csv
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
import urllib.error
import urllib.request
import uuid

try:
    from . import review_uu_chart as chart
except ImportError:
    import review_uu_chart as chart

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/local/staging/uu_charts"
CONTROL = BASE / "direct_control"
AUTH = ROOT / "scripts/config/credentials_uu_chart.json"
AUTH_EXAMPLE = ROOT / "scripts/config/uu_direct_auth.example.json"
ITEMS_EXAMPLE = ROOT / "scripts/config/uu_direct_items.example.json"
ENDPOINT = "https://pc-api.youpin898.com/api/youpin/price/trend/data"
VERSION = "uu-direct-chart-pilot-1.0"
MAX_BODY = 2 * 1024 * 1024
DAILY_LIMIT = 60
HEADERS = {"authorization", "cookie", "deviceid", "deviceuk", "uk", "app-version",
           "appversion", "apptype", "platform", "secret-v", "user-agent"}
SOURCES = (Path(__file__), Path(chart.__file__))


class PilotError(Exception):
    """Only fixed, non-sensitive categories may cross the CLI boundary."""


class RequestFailure(PilotError):
    def __init__(self, reason, *, http_status=None, application_code=None, retry_at=None):
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status
        self.application_code = application_code
        self.retry_at = retry_at


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def save(path, value):
    """Atomic local checkpoint; never accepts authentication configuration."""
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def load_items(path):
    raw = Path(path).read_bytes()
    if len(raw) > 64 * 1024 or re.search(rb"eyJ[A-Za-z0-9_-]{8,}\.", raw):
        raise PilotError("invalid_items_file")
    return validate_items(json.loads(raw.decode("utf-8-sig")))


def validate_items(value):
    if not isinstance(value, dict) or set(value) != {"version", "items"} or value["version"] != "uu-direct-items-1.0":
        raise PilotError("invalid_items_file")
    items = value["items"]
    if not isinstance(items, list) or not 1 <= len(items) <= 3:
        raise PilotError("pilot_requires_one_to_three_items")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"template_id", "item_label", "half_year_day"}:
            raise PilotError("invalid_item_fields")
        template, label, half = item["template_id"], item["item_label"], item["half_year_day"]
        if not isinstance(template, str) or not re.fullmatch(r"[1-9][0-9]{0,11}", template) or template in seen:
            raise PilotError("invalid_or_repeated_template")
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 200 or any(ord(c) < 32 for c in label):
            raise PilotError("invalid_item_label")
        if type(half) is not int or not 90 < half <= 366:
            raise PilotError("half_year_requires_observed_parameter")
        seen.add(template)
    return value


def tasks_for(items):
    result = []
    for item in items["items"]:
        for window, day, order in (("7d", 7, 1), ("7d", 7, 11), ("15d", 15, 11),
                                   ("30d", 30, 1), ("30d", 30, 11), ("90d", 90, 1),
                                   ("half_year", item["half_year_day"], 1)):
            result.append({"task_id": f"{item['template_id']}_{window}_{order}",
                           "template_id": item["template_id"], "window": window,
                           "request_body": {"filterTemplateTypeNames": [], "templateId": item["template_id"],
                                            "orderType": str(order), "day": str(day),
                                            "templateTypeName": "", "customizeDay": False},
                           "status": "pending", "attempts": 0})
    return result


def auth_headers():
    # This is the only credential reader. Values are never returned by plan/status.
    if not AUTH.is_file() or AUTH.stat().st_size > 32 * 1024:
        raise PilotError("private_auth_missing_or_too_large")
    value = json.loads(AUTH.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or set(value) != {"headers"} or not isinstance(value["headers"], dict):
        raise PilotError("invalid_private_auth")
    headers = {"Accept": "application/json", "Accept-Encoding": "identity", "Content-Type": "application/json",
               "Origin": "https://www.youpin898.com", "Referer": "https://www.youpin898.com/",
               "User-Agent": "CS-YouOweMe-Research/uu-direct-chart-pilot-1.0"}
    supplied = value["headers"]
    if set(supplied) - HEADERS:
        raise PilotError("unsupported_auth_header")
    for key, data in supplied.items():
        if not isinstance(data, str) or len(data) > (16384 if key == "cookie" else 4096) or any(ord(c) < 32 or ord(c) > 126 for c in data):
            raise PilotError("invalid_auth_header_value")
        if data:
            headers[key] = data
    if not (supplied.get("cookie") or supplied.get("authorization")):
        raise PilotError("local_login_information_required")
    return headers


def secret_fragments(headers):
    values = []
    for key, value in headers.items():
        if key.lower() in {"authorization", "cookie", "deviceid", "deviceuk", "uk"}:
            values.append(value)
            if key.lower() == "authorization":
                values.append(value.rsplit(" ", 1)[-1])
            if key.lower() == "cookie":
                values.extend(part.strip().partition("=")[2] for part in value.split(";"))
    return [value.encode("ascii") for value in values if len(value) >= 8]


def cooldown(value, current):
    try:
        if isinstance(value, str) and value.isdigit():
            return current + min(int(value), 366 * 86400)
        result = parsedate_to_datetime(value).timestamp()
        return max(current, result) if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # No redirect is followed, including same-host redirects with credentials.
        return None


def request_chart(body, headers, timeout):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200 or response.url != ENDPOINT:
                raise RequestFailure("unexpected_http_response", http_status=response.status)
            raw = response.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                raise RequestFailure("response_too_large", http_status=200)
            return raw
    except urllib.error.HTTPError as error:
        retry_at = cooldown(error.headers.get("Retry-After"), time.time()) if error.headers else None
        status = error.code
        error.close()  # Error bodies/headers are never archived or logged.
        raise RequestFailure("http_error", http_status=status, retry_at=retry_at) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RequestFailure("network_or_timeout") from None


def validate_response(raw, body, headers):
    if any(fragment in raw for fragment in secret_fragments(headers)):
        raise RequestFailure("credential_like_response", http_status=200)
    try:
        value = json.loads(raw)
        if isinstance(value, dict) and type(value.get("code")) is int and value["code"] != 0:
            raise RequestFailure("application_error", http_status=200, application_code=value["code"])
        result = chart.inspect_response(raw, template_id=body["templateId"], order_type=body["orderType"], requested_days=body["day"])
        if not result["points"]:
            raise RequestFailure("empty_series", http_status=200)
        return result
    except RequestFailure:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise RequestFailure("response_schema_error", http_status=200) from None


def control_state():
    path = CONTROL / "state.json"
    if path.exists():
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("version") != VERSION:
            raise PilotError("control_version_differs")
        return value
    legacy = False
    for path in (ROOT / "data/local/recon").glob("*/evidence.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        legacy |= "pc-api.youpin898.com" in value.get("blocked_hosts", [])
    return {"version": VERSION, "blocked": legacy, "reason": "inherited_access_stop" if legacy else None,
            "not_before_epoch": 0, "last_request_epoch": 0, "last_template_id": None,
            "request_epochs": [], "recovery_acknowledgements": []}


def admit(state, confirmed, epoch):
    if epoch < state["not_before_epoch"]:
        raise PilotError("server_cooldown_not_finished")
    if state["blocked"]:
        if not confirmed:
            raise PilotError("access_stopped_confirm_normal_access_locally_before_retry")
        state["recovery_acknowledgements"].append(now())
        state.update(blocked=False, reason=None)
    state["request_epochs"] = [t for t in state["request_epochs"] if t > epoch - 86400]
    if len(state["request_epochs"]) >= DAILY_LIMIT:
        raise PilotError("rolling_24h_request_budget_exhausted")


@contextmanager
def worker_lock():
    CONTROL.mkdir(parents=True, exist_ok=True)
    path = CONTROL / "worker.lock"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise PilotError("worker_lock_exists_check_previous_process") from None
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def source_hashes():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in SOURCES}


def new_run(items, interval, item_gap):
    run_id = "direct_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
    directory = BASE / run_id
    directory.mkdir(parents=True)
    (directory / "raw").mkdir()
    (directory / "source").mkdir()
    for path in SOURCES:
        (directory / "source" / path.name).write_bytes(path.read_bytes())
    manifest = {"version": VERSION, "run_id": run_id, "created_at": now(), "updated_at": now(),
                "source": "uu_direct_http_pilot", "identity_verified": False, "capability_level": "L0",
                "items": items, "source_sha256": source_hashes(), "interval_seconds": interval,
                "item_gap_seconds": item_gap, "status": "ready", "tasks": tasks_for(items)}
    save(directory / "run.json", manifest)
    with closing(sqlite3.connect(directory / "charts.sqlite")) as db, db:
        db.execute("CREATE TABLE points(task_id TEXT, sequence INTEGER, source_time_ms INTEGER, source_trade_price_cny TEXT, source_listing_count INTEGER, collected_at TEXT, historical_available_at TEXT, point_json TEXT NOT NULL, PRIMARY KEY(task_id,sequence))")
    return directory, manifest


def existing_run(name):
    if not re.fullmatch(r"direct_\d{8}T\d{6}Z_[a-f0-9]{8}", name):
        raise PilotError("invalid_run_id")
    directory = BASE / name
    value = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    if value.get("version") != VERSION or value.get("source_sha256") != source_hashes():
        raise PilotError("frozen_source_differs")
    expected = tasks_for(validate_items(value["items"]))
    if len(expected) != len(value["tasks"]):
        raise PilotError("task_plan_differs")
    for original, task in zip(expected, value["tasks"]):
        if any(original[k] != task.get(k) for k in ("task_id", "template_id", "window", "request_body")):
            raise PilotError("task_plan_differs")
        if task.get("status") not in {"pending", "success", "failed", "interrupted_unknown"} or task.get("attempts") != (0 if task["status"] == "pending" else 1):
            raise PilotError("invalid_task_checkpoint")
        if task["status"] == "success":
            raw = (directory / "raw" / (task["task_id"] + ".json")).read_bytes()
            if hashlib.sha256(raw).hexdigest() != task["response_sha256"]:
                raise PilotError("saved_response_differs")
    if not 10 <= value["interval_seconds"] <= 300 or not 30 <= value["item_gap_seconds"] <= 600:
        raise PilotError("invalid_saved_pacing")
    with closing(sqlite3.connect((directory / "charts.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
        for task in value["tasks"]:
            if task["status"] == "success" and db.execute("SELECT count(*) FROM points WHERE task_id=?", (task["task_id"],)).fetchone()[0] != task["point_count"]:
                raise PilotError("saved_database_count_differs")
    return directory, value


def export_results(directory, manifest):
    confirmed = [task["task_id"] for task in manifest["tasks"] if task["status"] == "success"]
    with closing(sqlite3.connect((directory / "charts.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
        query = "SELECT task_id,sequence,source_time_ms,source_trade_price_cny,source_listing_count,collected_at,historical_available_at FROM points WHERE task_id IN (" + ",".join("?" for _ in confirmed) + ") ORDER BY task_id,sequence"
        rows = db.execute(query, confirmed)
        with (directory / "points.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([column[0] for column in rows.description])
            writer.writerows(rows)
    save(directory / "report.json", {**summary(manifest), "source": "uu_direct_http_pilot",
                                      "identity_verified": False, "historical_available_at": None,
                                      "capability_level": "L0", "execution_eligible": False})


def collect(directory, manifest, state, headers, *, maximum, confirmed=False, send=request_chart,
            clock=time.time, monotonic=time.monotonic, sleep=time.sleep):
    admit(state, confirmed, clock())
    save(CONTROL / "state.json", state)
    deadline, attempts = monotonic() + 900, 0
    manifest["status"] = "running"
    try:
        for task in manifest["tasks"]:
            if task["status"] != "pending":
                continue
            if attempts >= maximum:
                break
            admit(state, False, clock())
            gap = manifest["interval_seconds"]
            if state.get("last_template_id") is not None and state["last_template_id"] != task["template_id"]:
                gap = max(gap, manifest["item_gap_seconds"])
            wait = max(0, state["last_request_epoch"] + gap - clock())
            if monotonic() + wait + 1 >= deadline:
                manifest["status"] = "deadline_reached"
                break
            if wait:
                sleep(wait)
            task.update(status="interrupted_unknown", attempts=1, started_at=now())
            attempts += 1
            state["last_request_epoch"] = clock()
            state["last_template_id"] = task["template_id"]
            state["request_epochs"].append(clock())
            save(CONTROL / "state.json", state)
            save(directory / "run.json", manifest)  # Attempt persists before network I/O.
            try:
                raw = send(task["request_body"], headers, min(30, max(1, deadline - monotonic())))
                if len(raw) > MAX_BODY:
                    raise RequestFailure("response_too_large", http_status=200)
                report = validate_response(raw, task["request_body"], headers)
                received = now()
                raw_path = directory / "raw" / (task["task_id"] + ".json")
                with raw_path.open("xb") as handle:
                    handle.write(raw)
                with closing(sqlite3.connect(directory / "charts.sqlite")) as db, db:
                    db.executemany("INSERT INTO points VALUES(?,?,?,?,?,?,?,?)", [
                        (task["task_id"], row["sequence"], row["source_time_ms"], row["source_trade_price_cny"], row["source_listing_count"], received, None, json.dumps(row, ensure_ascii=False)) for row in report["points"]])
                task.update(status="success", http_status=200, received_at=received,
                            response_sha256=hashlib.sha256(raw).hexdigest(), point_count=len(report["points"]), summary=report["summary"])
                print(json.dumps({"event": "saved", "task_id": task["task_id"], "points": len(report["points"])}, ensure_ascii=False), flush=True)
            except RequestFailure as error:
                task.update(status="failed", error=error.reason)
                if error.http_status is not None:
                    task["http_status"] = error.http_status
                if error.application_code is not None:
                    task["application_code"] = error.application_code
                state.update(blocked=True, reason=error.reason,
                             not_before_epoch=error.retry_at or (clock() + 900 if error.http_status == 429 else 0))
                save(CONTROL / "state.json", state)
                manifest["status"] = "access_or_data_stopped"
                break
            manifest["updated_at"] = now()
            save(directory / "run.json", manifest)
    except KeyboardInterrupt:
        manifest["status"] = "user_interrupted"
    except PilotError:
        manifest["status"] = "budget_or_access_stopped"
        raise
    except Exception:
        manifest["status"] = "local_failure"
        raise PilotError("local_failure_check_saved_run") from None
    finally:
        if manifest["status"] == "running":
            manifest["status"] = "completed" if all(t["status"] == "success" for t in manifest["tasks"]) else "partial_no_automatic_retry"
        manifest["updated_at"] = now()
        save(directory / "run.json", manifest)
        export_results(directory, manifest)
    return manifest


def summary(manifest):
    return {"version": VERSION, "run_id": manifest["run_id"], "status": manifest["status"],
            "success": sum(t["status"] == "success" for t in manifest["tasks"]),
            "failed": sum(t["status"] == "failed" for t in manifest["tasks"]),
            "pending": sum(t["status"] == "pending" for t in manifest["tasks"]),
            "interrupted_unknown": sum(t["status"] == "interrupted_unknown" for t in manifest["tasks"]),
            "points": sum(t.get("point_count", 0) for t in manifest["tasks"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-auth", help="Create a blank private file; no network")
    for name in ("plan", "probe"):
        command = commands.add_parser(name)
        command.add_argument("--items", type=Path, default=ITEMS_EXAMPLE)
        command.add_argument("--interval", type=int, default=15)
        command.add_argument("--item-gap", type=int, default=60)
        if name == "probe":
            command.add_argument("--normal-access-confirmed", action="store_true")
    for name in ("resume", "status"):
        command = commands.add_parser(name)
        command.add_argument("--run", required=True)
        if name == "resume":
            command.add_argument("--normal-access-confirmed", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "init-auth":
            AUTH.parent.mkdir(parents=True, exist_ok=True)
            with AUTH.open("xb") as handle:
                handle.write(AUTH_EXAMPLE.read_bytes())
            print("Blank private config created: scripts/config/credentials_uu_chart.json")
            return 0
        if args.command in {"plan", "probe"}:
            if not 10 <= args.interval <= 300 or not 30 <= args.item_gap <= 600:
                raise PilotError("interval_10_to_300_and_item_gap_30_to_600_required")
            items = load_items(args.items)
            if args.command == "plan":
                print(json.dumps({"version": VERSION, "network_requests": 0, "tasks": len(tasks_for(items)),
                                  "probe_attempts": 1, "interval_seconds": args.interval, "item_gap_seconds": args.item_gap,
                                  "rolling_24h_limit": DAILY_LIMIT, "legacy_access_stop": control_state()["blocked"]}, ensure_ascii=False))
                return 0
        if args.command == "status":
            _, manifest = existing_run(args.run)
            print(json.dumps(summary(manifest), ensure_ascii=False))
            return 0
        with worker_lock():
            state = control_state()
            admit(state, args.normal_access_confirmed, time.time())
            headers = auth_headers()
            if args.command == "probe":
                directory, manifest = new_run(items, args.interval, args.item_gap)
                maximum = 1
            else:
                directory, manifest = existing_run(args.run)
                maximum = 21
            result = collect(directory, manifest, state, headers, maximum=maximum)
            print(json.dumps(summary(result), ensure_ascii=False))
            print("Output: data/local/staging/uu_charts/" + manifest["run_id"])
            return 0 if result["status"] in {"completed", "partial_no_automatic_retry"} else 2
    except (PilotError, ValueError, OSError, KeyError, TypeError, sqlite3.Error):
        # Do not print exception strings, request objects, auth contents, or tracebacks.
        import sys
        error = sys.exception()
        reason = str(error) if type(error) is PilotError else "configuration_or_local_io_error"
        print(json.dumps({"event": "stopped", "reason": reason}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
