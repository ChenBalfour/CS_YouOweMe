"""Compatibility CLI for offline fixed-rule price evaluation."""
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.research.evaluation.baseline_report import evaluate, main, status

if __name__ == "__main__":
    raise SystemExit(main())
