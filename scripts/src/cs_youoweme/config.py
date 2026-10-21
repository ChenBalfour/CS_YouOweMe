"""Load the seed universe and ignored local API configuration."""
from __future__ import annotations

import json
import os
from .cleaning import identity
from .errors import CollectionError
from .paths import ROOT, CONFIG


def load_names(path, limit):
    names = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(names, list) or not names or any(not isinstance(x, str) for x in names):
        raise CollectionError("Seed file must be a nonempty JSON array of exact marketHashName strings")
    if len(set(names)) != len(names):
        raise CollectionError("Duplicate seeds; fix seed list first")
    for name in names:
        identity(name)
    if limit < 1:
        raise CollectionError("Limit must be positive")
    return names[:limit]


def read_key():
    key = os.environ.get("STEAMDT_API_KEY", "").strip()
    for path in (CONFIG / ".env", ROOT / ".env"):
        if key:
            break
        if path.exists():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                name, sep, value = line.partition("=")
                if sep and name.strip() == "STEAMDT_API_KEY":
                    key = value.strip().strip("\"'")
    if not key:
        raise CollectionError("API key missing. Copy scripts/config/.env.example to scripts/config/.env and fill STEAMDT_API_KEY locally.")
    return key
