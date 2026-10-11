"""Command registration for the catalog and resumable history crawler."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..paths import CHINA
from .catalog import sync_catalog, search_catalog
from .aggregate import aggregate
from .jobs import boundary, plan, work
from .query import coverage, export_table, status, trade_query
from .store import DEFAULT_DB, Store
from .universe import discover, narrow


def register(sub):
    universe = sub.add_parser("universe", help="Select a bounded universe from current source heat and supply")
    universe.add_argument("--db", type=Path, default=DEFAULT_DB)
    selection = universe.add_subparsers(dest="action", required=True)
    scan = selection.add_parser("scan")
    scan.add_argument("--candidate-pages", type=int, default=2)
    scan.add_argument("--enrich-per-sector", type=int, default=20)
    scan.add_argument("--max-items", "--per-sector", dest="max_items", type=int, default=12)
    scan.add_argument("--delay", type=float, default=2.5)
    scan.add_argument("--output", type=Path)
    build = selection.add_parser("narrow", help="Rebuild a weapon-only universe from a saved observation; no network")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--max-items", type=int, default=12)
    catalog = sub.add_parser("catalog", help="Synchronize and search the full source directory")
    catalog.add_argument("--db", type=Path, default=DEFAULT_DB)
    cat = catalog.add_subparsers(dest="action", required=True)
    sync = cat.add_parser("sync")
    sync.add_argument("--source", type=Path, help="Import an already downloaded official base response")
    search = cat.add_parser("search")
    search.add_argument("--query", default="")
    search.add_argument("--category", choices=["weapon", "knife", "glove", "other"])
    search.add_argument("--exterior")
    search.add_argument("--limit", type=int, default=50)
    hist = sub.add_parser("history", help="Plan, resume and inspect market-history collection")
    hist.add_argument("--db", type=Path, default=DEFAULT_DB)
    commands = hist.add_subparsers(dest="action", required=True)
    planning = commands.add_parser("plan")
    planning.add_argument("--start", default="2025-06-01")
    planning.add_argument("--end", help="Date includes that Beijing day; timestamp is an exclusive boundary")
    planning.add_argument("--name", action="append", help="Exact name; repeat for a small pilot")
    planning.add_argument("--universe", type=Path, help="Saved, reviewed selection JSON; no full-catalog default")
    planning.add_argument("--category", choices=["weapon", "knife", "glove"], action="append")
    planning.add_argument("--kind", choices=["bars", "trades"], action="append")
    planning.add_argument("--platform", choices=["ALL", "BUFF", "YOUPIN", "STEAM", "C5", "HALOSKINS"], action="append")
    planning.add_argument("--period", choices=["1h", "1d"], default="1h")
    planning.add_argument("--priority", type=int, default=100, help="Smaller number runs first")
    worker = commands.add_parser("work")
    worker.add_argument("--max-pages", type=int, default=30, help="Committed history pages per invocation; zero drains queue")
    worker.add_argument("--delay", type=float, default=2.5)
    worker.add_argument("--retry-blocked", action="store_true")
    worker.add_argument("--max-storage-mb", type=float, default=2048, help="Stop at local DB/raw budget; default 2 GiB")
    report = commands.add_parser("status")
    report.add_argument("--limit", type=int, default=20)
    cover = commands.add_parser("coverage")
    cover.add_argument("--name", required=True)
    cover.add_argument("--kind", choices=["bars", "trades"], default="bars")
    cover.add_argument("--period", choices=["1h", "1d"], default="1h")
    cover.add_argument("--platform", default="ALL")
    cover.add_argument("--style", default="")
    query = commands.add_parser("trades")
    query.add_argument("--name", required=True)
    query.add_argument("--start")
    query.add_argument("--end")
    query.add_argument("--wear-min", type=float)
    query.add_argument("--wear-max", type=float)
    query.add_argument("--paint-seed", type=int)
    query.add_argument("--limit", type=int, default=100)
    agg = commands.add_parser("aggregate")
    agg.add_argument("--name", required=True)
    agg.add_argument("--period", choices=["4h", "1d"], default="1d")
    agg.add_argument("--platform", default="ALL")
    agg.add_argument("--style", default="")
    agg.add_argument("--start")
    agg.add_argument("--end")
    export = commands.add_parser("export")
    export.add_argument("--table", choices=["catalog", "platform_ids", "styles", "trades", "bars", "jobs"], required=True)
    export.add_argument("--output", type=Path, required=True)


def run(args):
    with Store(args.db) as store:
        if args.command == "universe":
            if args.action == "narrow":
                result = narrow(store, args.source, args.output, args.max_items)
            else:
                result = discover(store, args.candidate_pages, args.enrich_per_sector, args.max_items, args.delay, args.output)
        elif args.command == "catalog":
            if args.action == "sync":
                with store.worker_lock():
                    result = sync_catalog(store, args.source)
            else:
                result = search_catalog(store, args.query, args.category, args.exterior, args.limit)
        elif args.action == "plan":
            start = boundary(args.start)
            end = boundary(args.end, end=True) if args.end else int(datetime.now(CHINA).timestamp())
            if args.name and args.universe:
                raise ValueError("Use --name or --universe, not both")
            names = args.name
            if args.universe:
                profile = json.loads(args.universe.read_text(encoding="utf-8"))
                names = [item["market_hash_name"] if isinstance(item, dict) else item for item in profile["items"]]
            if not names:
                raise ValueError("Select exact --name values or a saved --universe; full-catalog history is disabled by default")
            with store.worker_lock():
                result = plan(store, start, end, names, args.category, args.kind or ("bars", "trades"),
                              args.platform or ("ALL",), args.period, args.priority)
        elif args.action == "work":
            result = work(store, args.max_pages, args.delay, args.retry_blocked, max_storage_mb=args.max_storage_mb)
        elif args.action == "status":
            result = status(store, args.limit)
        elif args.action == "coverage":
            result = coverage(store, args.name, args.kind, args.period, args.platform, args.style)
        elif args.action == "trades":
            result = trade_query(store, args.name, boundary(args.start) if args.start else None,
                                 boundary(args.end, end=True) if args.end else None,
                                 args.wear_min, args.wear_max, args.paint_seed, args.limit)
        elif args.action == "export":
            result = export_table(store, args.table, args.output)
        elif args.action == "aggregate":
            result = aggregate(store, args.name, args.period, args.platform, args.style,
                               boundary(args.start) if args.start else None,
                               boundary(args.end, end=True) if args.end else None)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 1 if result.get("stopped") else 0
