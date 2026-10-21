"""Use the source tree and a shared anonymous saved payload, offline."""
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "scripts" / "src"))
SAMPLE = PROJECT / "data/samples/pilot_20261011"
PAYLOAD = SAMPLE / "raw/item_001.nuxt.json"


def payload_page(path=PAYLOAD):
    return '<script id="__NUXT_DATA__" type="application/json">' + path.read_text(encoding="utf-8") + '</script>'
