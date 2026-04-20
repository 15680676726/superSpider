# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]{2,}")


@dataclass(slots=True)
class CodeChunk:
    file_path: str
    start_line: int
    end_line: int
    text: str
    tokens: set[str]


def tokenize_text(value: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_PATTERN.finditer(value or "")}


def chunk_text_file(
    *,
    relative_path: str,
    text: str,
    window_size: int = 40,
    overlap: int = 10,
) -> list[CodeChunk]:
    lines = (text or "").splitlines()
    if not lines:
        return []
    chunks: list[CodeChunk] = []
    step = max(1, window_size - max(0, overlap))
    for start in range(0, len(lines), step):
        window = lines[start : start + window_size]
        if not window:
            continue
        chunk_text = "\n".join(window).strip()
        if not chunk_text:
            continue
        chunks.append(
            CodeChunk(
                file_path=relative_path,
                start_line=start + 1,
                end_line=start + len(window),
                text=chunk_text,
                tokens=tokenize_text(chunk_text),
            )
        )
        if start + window_size >= len(lines):
            break
    return chunks


def chunk_file(path: Path, *, workspace_root: Path) -> list[CodeChunk]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    relative_path = path.relative_to(workspace_root).as_posix()
    return chunk_text_file(relative_path=relative_path, text=text)


__all__ = ["CodeChunk", "chunk_file", "chunk_text_file", "tokenize_text"]
