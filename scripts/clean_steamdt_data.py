"""CLI for offline, versioned SteamDT hourly cleaning."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.research.data.clean_hourly import build, main, status


if __name__ == "__main__":
    raise SystemExit(main())
