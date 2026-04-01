# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long
"""The shell command tool."""

import asyncio
import locale
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from copaw.constant import WORKING_DIR
from .evidence_runtime import ShellEvidenceEvent, emit_shell_evidence
from .shell_safety import validate_shell_command
from .utils import truncate_shell_output


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _classify_shell_status(returncode: int, stderr: str) -> str:
    if returncode == 0:
        return "success"

    normalized = (stderr or "").lower()
    if returncode == -1 and (
        "timeout" in normalized or "exceeded the timeout" in normalized
    ):
        return "timeout"

    return "error"


async def _emit_shell_evidence_event(
    *,
    command: str,
    cwd: Path,
    timeout: int,
    returncode: int,
    stdout: str,
    stderr: str,
    started_at: datetime,
    finished_at: datetime,
    status_override: str | None = None,
    rule_id: str | None = None,
) -> None:
    status = status_override or _classify_shell_status(returncode, stderr)
    duration_ms = max(
        0,
        int((finished_at - started_at).total_seconds() * 1000),
    )
    await emit_shell_evidence(
        ShellEvidenceEvent(
            command=command,
            cwd=str(cwd),
            timeout_seconds=timeout,
            status=status,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            timed_out=(status == "timeout"),
            rule_id=rule_id,
        ),
    )


def _execute_subprocess_sync(
    cmd: str,
    cwd: str,
    timeout: int,
) -> tuple[int, str, str]:
    """Execute subprocess synchronously in a thread.

    This function runs in a separate thread to avoid Windows asyncio
    subprocess limitations.

    Args:
        cmd (`str`):
            The shell command to execute.
        cwd (`str`):
            The working directory for the command execution.
        timeout (`int`):
            The maximum time (in seconds) allowed for the command to run.

    Returns:
        `tuple[int, str, str]`:
            A tuple containing the return code, standard output, and
            standard error of the executed command. If timeout occurs, the
            return code will be -1 and stderr will contain timeout information.
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            encoding=locale.getpreferredencoding(False) or "utf-8",
            errors="replace",
            check=True,
        )
        return (
            result.returncode,
            result.stdout.strip("\n"),
            result.stderr.strip("\n"),
        )
    except subprocess.TimeoutExpired:
        return (
            -1,
            "",
            f"Command execution exceeded the timeout of {timeout} seconds.",
        )
    except Exception as e:
        return -1, "", str(e)


# pylint: disable=too-many-branches, too-many-statements
async def execute_shell_command(
    command: str,
    timeout: int = 60,
    cwd: Optional[Path] = None,
) -> ToolResponse:
    """Execute given command and return the return code, standard output and
    error within <returncode></returncode>, <stdout></stdout> and
    <stderr></stderr> tags.

    Args:
        command (`str`):
            The shell command to execute.
        timeout (`int`, defaults to `10`):
            The maximum time (in seconds) allowed for the command to run.
            Default is 60 seconds.
        cwd (`Optional[Path]`, defaults to `None`):
            The working directory for the command execution.
            If None, defaults to WORKING_DIR.

    Returns:
        `ToolResponse`:
            The tool response containing the return code, standard output, and
            standard error of the executed command. If timeout occurs, the
            return code will be -1 and stderr will contain timeout information.
    """

    cmd = (command or "").strip()

    # Set working directory
    working_dir = cwd if cwd is not None else WORKING_DIR
    started_at = _utc_now()
    decision = validate_shell_command(cmd)

    if not decision.allowed:
        finished_at = _utc_now()
        denial_reason = decision.reason or "Blocked by shell safety policy."
        stderr_str = truncate_shell_output(denial_reason)
        await _emit_shell_evidence_event(
            command=cmd,
            cwd=working_dir,
            timeout=timeout,
            returncode=-1,
            stdout="",
            stderr=stderr_str,
            started_at=started_at,
            finished_at=finished_at,
            status_override="blocked",
            rule_id=decision.rule_id,
        )
        response_text = (
            f"Blocked by shell safety policy: {cmd}\n"
            f"Reason: {denial_reason}"
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=response_text,
                ),
            ],
        )

    try:
        if sys.platform == "win32":
            # Windows: use thread pool to avoid asyncio subprocess limitations
            returncode, stdout_str, stderr_str = await asyncio.to_thread(
                _execute_subprocess_sync,
                cmd,
                str(working_dir),
                timeout,
            )
        else:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                bufsize=0,
                cwd=str(working_dir),
            )

            try:
                # Apply timeout to communicate directly; wait()+communicate()
                # can hang if descendants keep stdout/stderr pipes open.
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
                encoding = locale.getpreferredencoding(False) or "utf-8"
                stdout_str = stdout.decode(encoding, errors="replace").strip(
                    "\n",
                )
                stderr_str = stderr.decode(encoding, errors="replace").strip(
                    "\n",
                )
                returncode = proc.returncode

            except asyncio.TimeoutError:
                # Handle timeout
                stderr_suffix = (
                    f"⚠️ TimeoutError: The command execution exceeded "
                    f"the timeout of {timeout} seconds. "
                    f"Please consider increasing the timeout value if this command "
                    f"requires more time to complete."
                )
                returncode = -1
                try:
                    proc.terminate()
                    # Wait a bit for graceful termination
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=1)
                    except asyncio.TimeoutError:
                        # Force kill if graceful termination fails
                        proc.kill()
                        await proc.wait()

                    # Avoid hanging forever while draining pipes after timeout.
                    try:
                        stdout, stderr = await asyncio.wait_for(
                            proc.communicate(),
                            timeout=1,
                        )
                    except asyncio.TimeoutError:
                        stdout, stderr = b"", b""
                    encoding = locale.getpreferredencoding(False) or "utf-8"
                    stdout_str = stdout.decode(
                        encoding,
                        errors="replace",
                    ).strip(
                        "\n",
                    )
                    stderr_str = stderr.decode(
                        encoding,
                        errors="replace",
                    ).strip(
                        "\n",
                    )
                    if stderr_str:
                        stderr_str += f"\n{stderr_suffix}"
                    else:
                        stderr_str = stderr_suffix
                except ProcessLookupError:
                    stdout_str = ""
                    stderr_str = stderr_suffix

        # Apply output truncation
        stdout_str = truncate_shell_output(stdout_str)
        stderr_str = truncate_shell_output(stderr_str)
        finished_at = _utc_now()
        await _emit_shell_evidence_event(
            command=cmd,
            cwd=working_dir,
            timeout=timeout,
            returncode=returncode,
            stdout=stdout_str,
            stderr=stderr_str,
            started_at=started_at,
            finished_at=finished_at,
        )

        # Format the response in a human-friendly way
        if returncode == 0:
            # Success case: just show the output
            if stdout_str:
                response_text = stdout_str
            else:
                response_text = "Command executed successfully (no output)."
        else:
            # Error case: show detailed information
            response_parts = [f"Command failed with exit code {returncode}."]
            if stdout_str:
                response_parts.append(f"\n[stdout]\n{stdout_str}")
            if stderr_str:
                response_parts.append(f"\n[stderr]\n{stderr_str}")
            response_text = "".join(response_parts)

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=response_text,
                ),
            ],
        )

    except Exception as e:
        finished_at = _utc_now()
        await _emit_shell_evidence_event(
            command=cmd,
            cwd=working_dir,
            timeout=timeout,
            returncode=-1,
            stdout="",
            stderr=str(e),
            started_at=started_at,
            finished_at=finished_at,
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Shell command execution failed due to \n{e}",
                ),
            ],
        )
