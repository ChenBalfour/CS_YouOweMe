"""Run the source-tree CLI without installing dependencies."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cs_youoweme.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
