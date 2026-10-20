"""CLI and Notebook API: cleaned hourly data to seven-item daily samples."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.research.data import seven_samples as _implementation
from scripts.research.data.seven_samples import build_samples, status


def __getattr__(name):
    return getattr(_implementation, name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Build one immutable offline sample version")
    build.add_argument("--clean-id", default="seven_clean_20261019_v1")
    build.add_argument("--dataset-id")
    build.add_argument("--spec", type=Path, default=_implementation.DEFAULT_SPEC)
    view = commands.add_parser("status", help="Read an existing sample manifest; no build")
    view.add_argument("--dataset-id")
    args = parser.parse_args(argv)
    try:
        result = (build_samples(args.clean_id, args.dataset_id, args.spec)
                  if args.command == "build" else status(args.dataset_id))
        print(json.dumps({k: v for k, v in result.items() if k != "outputs"},
                         ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        print(json.dumps({"version": _implementation.VERSION, "status": "stopped",
                          "reason": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
