"""Collector errors suitable for safe CLI messages."""
from __future__ import annotations




class CollectionError(RuntimeError):
    pass


class AccessStopped(CollectionError):
    """Authentication, denial, or rate limit. Do not attempt to bypass."""
