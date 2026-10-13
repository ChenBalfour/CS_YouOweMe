"""Explicit local-user entry point for the bounded UU forward observation."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from cs_youoweme.history.observe import collect, create_run, inspect_run
from cs_youoweme.errors import CollectionError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--new", action="store_true", help="Create and run a new 24-hour observation")
    mode.add_argument("--resume", metavar="RUN_DIR", help="Resume until the original fixed deadline")
    mode.add_argument("--status", metavar="RUN_DIR", help="Read status without network or collection")
    args = parser.parse_args()
    try:
        result = inspect_run(args.status) if args.status else collect(create_run() if args.new else args.resume)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (CollectionError, ValueError, OSError):
        print("Observation input/source validation failed; no credentials or response body printed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
