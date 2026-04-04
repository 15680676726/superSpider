# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import time
from typing import Callable, Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class CacheStats:
    hits: int = 0
    misses: int = 0
    writes: int = 0
    evictions: int = 0
    clears: int = 0


@dataclass(slots=True)
class _TTLCacheEntry(Generic[V]):
    expires_at: float
    value: V


class TTLCache(Generic[K, V]):
    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._ttl_seconds = max(0.0, float(ttl_seconds))
        self._max_entries = max_entries if max_entries is None else max(1, int(max_entries))
        self._clock = clock or time.monotonic
        self._entries: OrderedDict[K, _TTLCacheEntry[V]] = OrderedDict()
        self.stats = CacheStats()

    def get(self, key: K) -> V | None:
        entry = self._entries.get(key)
        if entry is None:
            self.stats.misses += 1
            return None
        now = self._clock()
        if entry.expires_at <= now:
            self._entries.pop(key, None)
            self.stats.misses += 1
            return None
        self._entries.move_to_end(key)
        self.stats.hits += 1
        return entry.value

    def set(self, key: K, value: V) -> V:
        expires_at = self._clock() + self._ttl_seconds
        self._entries[key] = _TTLCacheEntry(expires_at=expires_at, value=value)
        self._entries.move_to_end(key)
        self.stats.writes += 1
        self._evict_if_needed()
        return value

    def clear(self) -> None:
        self._entries.clear()
        self.stats.clears += 1

    def _evict_if_needed(self) -> None:
        if self._max_entries is None:
            return
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
            self.stats.evictions += 1


class BoundedLRUCache(Generic[K, V]):
    def __init__(self, *, max_entries: int) -> None:
        self._max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[K, V] = OrderedDict()
        self.stats = CacheStats()

    def get(self, key: K) -> V | None:
        if key not in self._entries:
            self.stats.misses += 1
            return None
        value = self._entries.pop(key)
        self._entries[key] = value
        self.stats.hits += 1
        return value

    def set(self, key: K, value: V) -> V:
        if key in self._entries:
            self._entries.pop(key)
        self._entries[key] = value
        self.stats.writes += 1
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
            self.stats.evictions += 1
        return value

    def clear(self) -> None:
        self._entries.clear()
        self.stats.clears += 1

