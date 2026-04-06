# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import json
from urllib.error import HTTPError

from copaw.adapters import skillhub as skillhub_module


def test_load_skillhub_bundle_from_url_falls_back_to_clawhub_api_when_static_zip_is_missing(
    monkeypatch,
) -> None:
    skillhub_module._BUNDLE_VALIDATION_CACHE.clear()
    skillhub_module._BUNDLE_PAYLOAD_CACHE.clear()
    monkeypatch.setattr(
        skillhub_module,
        "_http_bytes_get",
        lambda _url: (_ for _ in ()).throw(RuntimeError("HTTP Error 404: Not Found")),
    )
    monkeypatch.setattr(
        skillhub_module,
        "_http_json_get",
        lambda url, params=None: (
            {
                "skill": {
                    "slug": "outreach-and-prospecting",
                    "displayName": "Outreach And Prospecting",
                    "tags": {"latest": "0.1.0"},
                },
                "latestVersion": {"version": "0.1.0"},
            }
            if url.endswith("/api/v1/skills/outreach-and-prospecting")
            else {
                "version": {
                    "version": "0.1.0",
                    "files": [
                        {
                            "path": "SKILL.md",
                            "contentType": "text/plain",
                        },
                    ],
                },
            }
        ),
    )
    monkeypatch.setattr(
        skillhub_module,
        "_http_text_get",
        lambda url, params=None: (
            "---\n"
            "name: outreach-and-prospecting\n"
            "description: test\n"
            "---\n"
            "body\n"
        )
        if url.endswith("/api/v1/skills/outreach-and-prospecting/file")
        and params == {"path": "SKILL.md", "version": "0.1.0"}
        else (_ for _ in ()).throw(AssertionError(f"unexpected file request: {url} {params}")),
        raising=False,
    )

    payload, source_url = skillhub_module.load_skillhub_bundle_from_url(
        "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/outreach-and-prospecting.zip",
    )

    assert source_url == "https://clawhub.ai/api/v1/skills/outreach-and-prospecting"
    assert "name" not in payload
    assert payload["files"]["SKILL.md"].startswith("---")


def test_load_skillhub_bundle_from_url_retries_rate_limited_clawhub_detail_request(
    monkeypatch,
) -> None:
    skillhub_module._BUNDLE_VALIDATION_CACHE.clear()
    skillhub_module._BUNDLE_PAYLOAD_CACHE.clear()
    attempts = {"detail": 0}

    class _Response:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def read(self) -> bytes:
            return self._body

    def _raise_http(url: str, code: int, message: str) -> None:
        raise HTTPError(url, code, message, hdrs=None, fp=io.BytesIO(b""))

    def _fake_urlopen(request, timeout=None):
        _ = timeout
        url = request.full_url
        if url.endswith("/skills/outreach-and-prospecting.zip"):
            _raise_http(url, 404, "Not Found")
        if url.endswith("/api/v1/skills/outreach-and-prospecting"):
            attempts["detail"] += 1
            if attempts["detail"] == 1:
                _raise_http(url, 429, "Too Many Requests")
            return _Response(
                json.dumps(
                    {
                        "skill": {
                            "slug": "outreach-and-prospecting",
                            "displayName": "Outreach And Prospecting",
                            "tags": {"latest": "0.1.0"},
                        },
                        "latestVersion": {"version": "0.1.0"},
                    }
                ).encode("utf-8")
            )
        if url.endswith("/api/v1/skills/outreach-and-prospecting/versions/0.1.0"):
            return _Response(
                json.dumps(
                    {
                        "version": {
                            "version": "0.1.0",
                            "files": [{"path": "SKILL.md", "contentType": "text/plain"}],
                        }
                    }
                ).encode("utf-8")
            )
        if (
            url.startswith("https://clawhub.ai/api/v1/skills/outreach-and-prospecting/file?")
            and "path=SKILL.md" in url
            and "version=0.1.0" in url
        ):
            return _Response(
                (
                    "---\n"
                    "name: outreach-and-prospecting\n"
                    "description: retry test\n"
                    "---\n"
                    "body\n"
                ).encode("utf-8")
            )
        raise AssertionError(f"unexpected urlopen request: {url}")

    monkeypatch.setattr(skillhub_module, "urlopen", _fake_urlopen)
    monkeypatch.setattr(skillhub_module.time, "sleep", lambda _seconds: None)

    payload, source_url = skillhub_module.load_skillhub_bundle_from_url(
        "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/outreach-and-prospecting.zip",
    )

    assert attempts["detail"] == 2
    assert source_url == "https://clawhub.ai/api/v1/skills/outreach-and-prospecting"
    assert payload["files"]["SKILL.md"].startswith("---")


def test_load_skillhub_bundle_from_url_reuses_recent_bundle_payload_without_refetch(
    monkeypatch,
) -> None:
    detail_calls = {"count": 0}
    bundle_url = (
        "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/"
        "outreach-and-prospecting.zip"
    )
    skillhub_module._BUNDLE_VALIDATION_CACHE.clear()
    skillhub_module._BUNDLE_PAYLOAD_CACHE.clear()

    monkeypatch.setattr(
        skillhub_module,
        "_http_bytes_get",
        lambda _url: (_ for _ in ()).throw(RuntimeError("HTTP Error 404: Not Found")),
    )

    def _fake_json(url, params=None):
        _ = params
        detail_calls["count"] += 1
        if detail_calls["count"] > 2:
            raise AssertionError("bundle payload should have been reused from cache")
        return (
            {
                "skill": {
                    "slug": "outreach-and-prospecting",
                    "displayName": "Outreach And Prospecting",
                    "tags": {"latest": "0.1.0"},
                },
                "latestVersion": {"version": "0.1.0"},
            }
            if url.endswith("/api/v1/skills/outreach-and-prospecting")
            else {
                "version": {
                    "version": "0.1.0",
                    "files": [{"path": "SKILL.md", "contentType": "text/plain"}],
                },
            }
        )

    monkeypatch.setattr(skillhub_module, "_http_json_get", _fake_json)
    monkeypatch.setattr(
        skillhub_module,
        "_http_text_get",
        lambda url, params=None: (
            "---\n"
            "name: outreach-and-prospecting\n"
            "description: cached test\n"
            "---\n"
            "body\n"
        )
        if url.endswith("/api/v1/skills/outreach-and-prospecting/file")
        and params == {"path": "SKILL.md", "version": "0.1.0"}
        else (_ for _ in ()).throw(AssertionError(f"unexpected file request: {url} {params}")),
        raising=False,
    )

    first_payload, first_source_url = skillhub_module.load_skillhub_bundle_from_url(bundle_url)
    second_payload, second_source_url = skillhub_module.load_skillhub_bundle_from_url(bundle_url)

    assert first_source_url == second_source_url
    assert first_payload == second_payload
