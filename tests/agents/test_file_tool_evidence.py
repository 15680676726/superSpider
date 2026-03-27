# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from copaw.agents.tools.evidence_runtime import bind_file_evidence_sink
from copaw.agents.tools.file_io import append_file, edit_file, write_file


def test_write_file_keeps_default_behavior_without_sink(tmp_path) -> None:
    target = tmp_path / "note.txt"

    response = asyncio.run(write_file(str(target), "hello world"))

    assert response.content[0]["text"] == f"Wrote 11 bytes to {target}."
    assert target.read_text(encoding="utf-8") == "hello world"


def test_write_file_emits_success_payload(tmp_path) -> None:
    target = tmp_path / "note.txt"
    payloads: list[dict[str, object]] = []

    async def run() -> None:
        with bind_file_evidence_sink(payloads.append):
            response = await write_file(str(target), "hello world")
        assert response.content[0]["text"] == f"Wrote 11 bytes to {target}."

    asyncio.run(run())

    assert len(payloads) == 1
    assert payloads[0]["tool_name"] == "write_file"
    assert payloads[0]["action"] == "write"
    assert payloads[0]["status"] == "success"
    assert payloads[0]["file_path"] == str(target)
    assert payloads[0]["resolved_path"] == str(target)
    assert payloads[0]["bytes_written"] == 11
    assert "Wrote 11 bytes" in str(payloads[0]["result_summary"])
    assert payloads[0]["started_at"]
    assert payloads[0]["finished_at"]
    assert payloads[0]["duration_ms"] >= 0


def test_edit_file_emits_single_success_payload(tmp_path) -> None:
    target = tmp_path / "edit.txt"
    target.write_text("hello old world", encoding="utf-8")
    payloads: list[dict[str, object]] = []

    async def run() -> None:
        with bind_file_evidence_sink(payloads.append):
            response = await edit_file(str(target), "old", "new")
        assert response.content[0]["text"] == f"Successfully replaced text in {target}."

    asyncio.run(run())

    assert target.read_text(encoding="utf-8") == "hello new world"
    assert len(payloads) == 1
    assert payloads[0]["tool_name"] == "edit_file"
    assert payloads[0]["action"] == "edit"
    assert payloads[0]["status"] == "success"
    assert payloads[0]["metadata"]["replacements"] == 1
    assert payloads[0]["result_summary"]
    assert payloads[0]["duration_ms"] >= 0


def test_append_file_emits_error_payload(tmp_path) -> None:
    payloads: list[dict[str, object]] = []

    async def run() -> None:
        with bind_file_evidence_sink(payloads.append):
            response = await append_file(str(tmp_path), "extra")
        assert response.content[0]["text"].startswith("Error: Append file failed")

    asyncio.run(run())

    assert len(payloads) == 1
    assert payloads[0]["tool_name"] == "append_file"
    assert payloads[0]["action"] == "append"
    assert payloads[0]["status"] == "error"
    assert payloads[0]["resolved_path"] == str(tmp_path)
    assert payloads[0]["metadata"]["error"]
    assert payloads[0]["duration_ms"] >= 0
