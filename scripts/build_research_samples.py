"""Compatibility CLI and Notebook API for the offline daily sample builder."""
from __future__ import annotations

from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.research.data import daily_samples as _implementation
from scripts.research.data.daily_samples import (
    build, build_rows, main, predictive_features, status,
)


def __getattr__(name):
    """Keep existing read-only constants/helpers available to older callers."""
    return getattr(_implementation, name)


if __name__ == "__main__":
    raise SystemExit(main())
