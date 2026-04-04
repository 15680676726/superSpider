# -*- coding: utf-8 -*-
from __future__ import annotations

import io

from copaw.capabilities import mcp_registry


class _FakeResponse(io.StringIO):
    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def test_registry_request_uses_cache_until_cleared(monkeypatch) -> None:
    call_count = 0

    def _fake_urlopen(request, timeout=0.0):  # type: ignore[no-untyped-def]
        nonlocal call_count
        _ = (request, timeout)
        call_count += 1
        return _FakeResponse('{"items": []}')

    monkeypatch.setattr(mcp_registry, "urlopen", _fake_urlopen)
    mcp_registry.clear_mcp_registry_cache()

    first = mcp_registry._registry_request("https://example.com/registry")
    second = mcp_registry._registry_request("https://example.com/registry")

    assert first == {"items": []}
    assert second == {"items": []}
    assert call_count == 1

    mcp_registry.clear_mcp_registry_cache()
    third = mcp_registry._registry_request("https://example.com/registry")

    assert third == {"items": []}
    assert call_count == 2
