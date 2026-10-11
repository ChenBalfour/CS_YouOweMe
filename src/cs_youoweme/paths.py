"""Repository paths, independent of the process working directory."""
from pathlib import Path
from datetime import timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
LOCAL_DATA = ROOT / "data" / "local"
CHINA = timezone(timedelta(hours=8))
