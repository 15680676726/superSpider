# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.utils.cache import BoundedLRUCache, TTLCache


def test_ttl_cache_expires_entries_and_clear_removes_state() -> None:
    now = 10.0

    def _clock() -> float:
        return now

    cache = TTLCache[str, int](ttl_seconds=5.0, clock=_clock)
    cache.set("alpha", 1)

    assert cache.get("alpha") == 1

    now = 16.0
    assert cache.get("alpha") is None

    cache.set("beta", 2)
    cache.clear()
    assert cache.get("beta") is None


def test_bounded_lru_cache_refreshes_recent_entry_on_get() -> None:
    cache = BoundedLRUCache[str, int](max_entries=2)
    cache.set("alpha", 1)
    cache.set("beta", 2)

    assert cache.get("alpha") == 1

    cache.set("gamma", 3)

    assert cache.get("alpha") == 1
    assert cache.get("beta") is None
    assert cache.get("gamma") == 3
