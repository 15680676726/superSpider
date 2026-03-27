# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ...constant import WORKING_DIR
from .evidence_runtime import FileEvidenceEvent, emit_file_evidence
from .utils import truncate_file_output, read_file_safe


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _emit_file_evidence_event(
    *,
    tool_name: str,
    action: str,
    file_path: str,
    resolved_path: str,
    status: str,
    result_summary: str,
    started_at: datetime,
    finished_at: datetime,
    bytes_written: int = 0,
    metadata: dict[str, object] | None = None,
) -> None:
    duration_ms = max(
        0,
        int((finished_at - started_at).total_seconds() * 1000),
    )
    await emit_file_evidence(
        FileEvidenceEvent(
            tool_name=tool_name,
            action=action,
            file_path=file_path,
            resolved_path=resolved_path,
            status=status,
            result_summary=result_summary,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            bytes_written=bytes_written,
            metadata=metadata or {},
        ),
    )


def _resolve_file_path(file_path: str) -> str:
    """Resolve file path: use absolute path as-is,
    resolve relative path from WORKING_DIR.

    Args:
        file_path: The input file path (absolute or relative).

    Returns:
        The resolved absolute file path as string.
    """
    path = Path(file_path)
    if path.is_absolute():
        return str(path)
    else:
        return str(WORKING_DIR / file_path)


async def read_file(  # pylint: disable=too-many-return-statements
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> ToolResponse:
    """Read a file. Relative paths resolve from WORKING_DIR.

    Use start_line/end_line to read a specific line range (output includes
    line numbers). Omit both to read the full file.

    Args:
        file_path (`str`):
            Path to the file.
        start_line (`int`, optional):
            First line to read (1-based, inclusive).
        end_line (`int`, optional):
            Last line to read (1-based, inclusive).
    """

    # Convert start_line/end_line to int if they are strings
    if start_line is not None:
        try:
            start_line = int(start_line)
        except (ValueError, TypeError):
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error: start_line must be an integer, got {start_line!r}.",
                    ),
                ],
            )

    if end_line is not None:
        try:
            end_line = int(end_line)
        except (ValueError, TypeError):
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error: end_line must be an integer, got {end_line!r}.",
                    ),
                ],
            )

    file_path = _resolve_file_path(file_path)

    if not os.path.exists(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The file {file_path} does not exist.",
                ),
            ],
        )

    if not os.path.isfile(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The path {file_path} is not a file.",
                ),
            ],
        )

    try:
        content = read_file_safe(file_path)
        all_lines = content.split("\n")
        total = len(all_lines)

        # Determine read range
        s = max(1, start_line if start_line is not None else 1)
        e = min(total, end_line if end_line is not None else total)

        if s > total:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error: start_line {s} exceeds file length ({total} lines).",
                    ),
                ],
            )

        if s > e:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error: start_line ({s}) > end_line ({e}).",
                    ),
                ],
            )

        # Extract selected lines
        selected_content = "\n".join(all_lines[s - 1 : e])

        # Apply smart truncation (consistent with shell output format)
        text = truncate_file_output(
            selected_content,
            start_line=s,
            total_lines=total,
        )

        # Add continuation hint if partial read without truncation
        if text == selected_content and e < total:
            remaining = total - e
            text = (
                f"{file_path}  (lines {s}-{e} of {total})\n{text}\n\n"
                f"[{remaining} more lines. Use start_line={e + 1} to continue.]"
            )

        return ToolResponse(
            content=[TextBlock(type="text", text=text)],
        )

    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Read file failed due to \n{e}",
                ),
            ],
        )


async def write_file(
    file_path: str,
    content: str,
) -> ToolResponse:
    """Create or overwrite a file. Relative paths resolve from WORKING_DIR.

    Args:
        file_path (`str`):
            Path to the file.
        content (`str`):
            Content to write.
    """

    if not file_path:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="Error: No `file_path` provided.",
                ),
            ],
        )

    original_path = file_path
    file_path = _resolve_file_path(file_path)
    started_at = _utc_now()

    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)
        finished_at = _utc_now()
        await _emit_file_evidence_event(
            tool_name="write_file",
            action="write",
            file_path=original_path,
            resolved_path=file_path,
            status="success",
            result_summary=f"Wrote {len(content)} bytes to {file_path}.",
            started_at=started_at,
            finished_at=finished_at,
            bytes_written=len(content),
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Wrote {len(content)} bytes to {file_path}.",
                ),
            ],
        )
    except Exception as e:
        finished_at = _utc_now()
        await _emit_file_evidence_event(
            tool_name="write_file",
            action="write",
            file_path=original_path,
            resolved_path=file_path,
            status="error",
            result_summary=f"Write file failed for {file_path}: {e}",
            started_at=started_at,
            finished_at=finished_at,
            metadata={"error": str(e)},
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Write file failed due to \n{e}",
                ),
            ],
        )


# pylint: disable=too-many-return-statements
async def edit_file(
    file_path: str,
    old_text: str,
    new_text: str,
) -> ToolResponse:
    """Find-and-replace text in a file. All occurrences of old_text are
    replaced with new_text. Relative paths resolve from WORKING_DIR.

    Args:
        file_path (`str`):
            Path to the file.
        old_text (`str`):
            Exact text to find.
        new_text (`str`):
            Replacement text.
    """

    if not file_path:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="Error: No `file_path` provided.",
                ),
            ],
        )

    original_path = file_path
    resolved_path = _resolve_file_path(file_path)
    started_at = _utc_now()

    if not os.path.exists(resolved_path):
        finished_at = _utc_now()
        await _emit_file_evidence_event(
            tool_name="edit_file",
            action="edit",
            file_path=original_path,
            resolved_path=resolved_path,
            status="error",
            result_summary=f"Edit file failed: {resolved_path} does not exist.",
            started_at=started_at,
            finished_at=finished_at,
            metadata={"error": "file_not_found"},
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The file {resolved_path} does not exist.",
                ),
            ],
        )

    if not os.path.isfile(resolved_path):
        finished_at = _utc_now()
        await _emit_file_evidence_event(
            tool_name="edit_file",
            action="edit",
            file_path=original_path,
            resolved_path=resolved_path,
            status="error",
            result_summary=f"Edit file failed: {resolved_path} is not a file.",
            started_at=started_at,
            finished_at=finished_at,
            metadata={"error": "not_a_file"},
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The path {resolved_path} is not a file.",
                ),
            ],
        )

    try:
        content = read_file_safe(resolved_path)
    except Exception as e:
        finished_at = _utc_now()
        await _emit_file_evidence_event(
            tool_name="edit_file",
            action="edit",
            file_path=original_path,
            resolved_path=resolved_path,
            status="error",
            result_summary=f"Edit file failed while reading {resolved_path}: {e}",
            started_at=started_at,
            finished_at=finished_at,
            metadata={"error": str(e), "stage": "read"},
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Read file failed due to \n{e}",
                ),
            ],
        )

    if old_text not in content:
        finished_at = _utc_now()
        await _emit_file_evidence_event(
            tool_name="edit_file",
            action="edit",
            file_path=original_path,
            resolved_path=resolved_path,
            status="error",
            result_summary=(
                f"Edit file failed: target text was not found in {resolved_path}."
            ),
            started_at=started_at,
            finished_at=finished_at,
            metadata={"error": "old_text_not_found"},
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The text to replace was not found in {file_path}.",
                ),
            ],
        )

    new_content = content.replace(old_text, new_text)
    try:
        with open(resolved_path, "w", encoding="utf-8") as file:
            file.write(new_content)
    except Exception as e:
        finished_at = _utc_now()
        await _emit_file_evidence_event(
            tool_name="edit_file",
            action="edit",
            file_path=original_path,
            resolved_path=resolved_path,
            status="error",
            result_summary=f"Edit file failed while writing {resolved_path}: {e}",
            started_at=started_at,
            finished_at=finished_at,
            metadata={"error": str(e), "stage": "write"},
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Write file failed due to \n{e}",
                ),
            ],
        )

    finished_at = _utc_now()
    replacements = content.count(old_text)
    bytes_written = len(new_content.encode("utf-8"))
    await _emit_file_evidence_event(
        tool_name="edit_file",
        action="edit",
        file_path=original_path,
        resolved_path=resolved_path,
        status="success",
        result_summary=f"Edited {resolved_path}; replaced {replacements} occurrence(s).",
        started_at=started_at,
        finished_at=finished_at,
        bytes_written=bytes_written,
        metadata={
            "replacements": replacements,
            "old_text_length": len(old_text),
            "new_text_length": len(new_text),
        },
    )

    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=f"Successfully replaced text in {file_path}.",
            ),
        ],
    )


async def append_file(
    file_path: str,
    content: str,
) -> ToolResponse:
    """Append content to the end of a file. Relative paths resolve from
    WORKING_DIR.

    Args:
        file_path (`str`):
            Path to the file.
        content (`str`):
            Content to append.
    """

    if not file_path:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="Error: No `file_path` provided.",
                ),
            ],
        )

    original_path = file_path
    file_path = _resolve_file_path(file_path)
    started_at = _utc_now()

    try:
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(content)
        finished_at = _utc_now()
        await _emit_file_evidence_event(
            tool_name="append_file",
            action="append",
            file_path=original_path,
            resolved_path=file_path,
            status="success",
            result_summary=f"Appended {len(content)} bytes to {file_path}.",
            started_at=started_at,
            finished_at=finished_at,
            bytes_written=len(content),
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Appended {len(content)} bytes to {file_path}.",
                ),
            ],
        )
    except Exception as e:
        finished_at = _utc_now()
        await _emit_file_evidence_event(
            tool_name="append_file",
            action="append",
            file_path=original_path,
            resolved_path=file_path,
            status="error",
            result_summary=f"Append file failed for {file_path}: {e}",
            started_at=started_at,
            finished_at=finished_at,
            metadata={"error": str(e)},
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Append file failed due to \n{e}",
                ),
            ],
        )
