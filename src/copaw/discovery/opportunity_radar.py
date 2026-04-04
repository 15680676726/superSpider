# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from .models import OpportunityRadarItem


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class OpportunityRadarService:
    def __init__(
        self,
        *,
        feeds: dict[str, Callable[[], Iterable[OpportunityRadarItem]]] | None = None,
    ) -> None:
        self._feeds = dict(feeds or {})

    def collect(
        self,
        *,
        limit: int = 10,
        feed_names: Sequence[str] | None = None,
        ecosystem_allowlist: Sequence[str] | None = None,
    ) -> list[OpportunityRadarItem]:
        selected_feeds = list(feed_names or self._feeds.keys())
        allowlist = {
            item.strip().lower()
            for item in list(ecosystem_allowlist or [])
            if isinstance(item, str) and item.strip()
        }
        deduped: dict[str, OpportunityRadarItem] = {}
        for feed_name in selected_feeds:
            loader = self._feeds.get(feed_name)
            if not callable(loader):
                continue
            for item in list(loader() or []):
                if allowlist and item.ecosystem.strip().lower() not in allowlist:
                    continue
                dedupe_key = (
                    _string(item.canonical_package_id)
                    or _string(item.source_ref)
                    or _string(item.title)
                    or item.item_id
                )
                if dedupe_key is None:
                    continue
                existing = deduped.get(dedupe_key)
                if existing is None or (item.score, item.published_at) > (
                    existing.score,
                    existing.published_at,
                ):
                    deduped[dedupe_key] = item
        ranked = sorted(
            deduped.values(),
            key=lambda item: (-float(item.score), item.published_at, item.title.lower()),
            reverse=False,
        )
        return ranked[: max(1, int(limit))]


__all__ = ["OpportunityRadarService"]

