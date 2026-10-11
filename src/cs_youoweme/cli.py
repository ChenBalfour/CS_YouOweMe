"""Collect public quotes, official API snapshots or raw K-line history."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from . import __version__
from .paths import CONFIG
from .errors import CollectionError
from .collectors.public import collect_public
from .collectors.official import collect_api, collect_kline


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"CS_YouOweMe {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for mode in ("public", "api"):
        cmd = sub.add_parser(mode)
        cmd.add_argument("--seeds", type=Path, default=CONFIG / "seeds.json")
        cmd.add_argument("--limit", type=int, default=20)
        if mode == "public":
            cmd.add_argument("--delay", type=float, default=2.5)
        else:
            cmd.add_argument("--with-base", action="store_true")
            cmd.add_argument("--currency", choices=["CNY"], help="Only set after independently confirming API prices are CNY")
    kline = sub.add_parser("kline")
    kline.add_argument("--name", required=True)
    kline.add_argument("--type", type=int, required=True, help="Use a platform-confirmed period value; no guessed default")
    kline.add_argument("--platform", required=True)
    kline.add_argument("--special-style", default="")
    args = parser.parse_args(argv)
    try:
        return {"public": collect_public, "api": collect_api, "kline": collect_kline}[args.command](args)
    except (CollectionError, OSError, ValueError) as error:
        print(f"Collection stopped: {error}", file=sys.stderr)
        return 1
