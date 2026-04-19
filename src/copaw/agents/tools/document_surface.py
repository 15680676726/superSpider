# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ...environments.surface_execution.owner import (
    GuidedDocumentSurfaceIntent,
    build_guided_document_surface_owner,
)
from ...environments.surface_execution.document import DocumentObservation

_DOCUMENT_FAMILY_BY_SUFFIX = {
    ".csv": "spreadsheets",
    ".doc": "documents",
    ".docx": "documents",
    ".md": "documents",
    ".ppt": "presentations",
    ".pptx": "presentations",
    ".rtf": "documents",
    ".tsv": "spreadsheets",
    ".txt": "documents",
    ".xls": "spreadsheets",
    ".xlsx": "spreadsheets",
}


def _tool_response(payload: dict[str, object]) -> ToolResponse:
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=json.dumps(payload, ensure_ascii=False, indent=2),
            ),
        ],
    )


def _normalize_document_family(
    document_path: str,
    explicit_family: str = "",
) -> str:
    normalized_family = str(explicit_family or "").strip()
    if normalized_family:
        return normalized_family
    suffix = Path(document_path).suffix.lower()
    return _DOCUMENT_FAMILY_BY_SUFFIX.get(suffix, "documents")


def _revision_token(path: Path) -> str:
    if not path.exists():
        return "missing"
    stat = path.stat()
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _read_document_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_document_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _replace_document_text(path: Path, find_text: str, replace_text: str) -> None:
    content = _read_document_text(path)
    if find_text not in content:
        raise ValueError(f"Text not found in document: {find_text}")
    _write_document_text(path, content.replace(find_text, replace_text))


def _verify_document_assertion(
    observation: DocumentObservation,
    *,
    success_assertion: dict[str, str],
) -> tuple[bool, dict[str, str]]:
    observed_text = str(observation.content_text or "")
    readback = {
        "observed_text": observed_text,
        "normalized_text": observed_text.strip(),
    }
    expected_contains = str(success_assertion.get("contains_text") or "")
    expected_normalized = str(success_assertion.get("normalized_text") or "")
    verification_passed = True
    if expected_contains:
        verification_passed = expected_contains in observed_text
    if expected_normalized:
        verification_passed = (
            verification_passed and readback["normalized_text"] == expected_normalized
        )
    return verification_passed, readback


def _build_document_step_payload(
    *,
    intent_kind: str,
    desired_content: str,
    find_text: str,
    replace_text: str,
) -> tuple[str, dict[str, str], dict[str, str]]:
    if intent_kind == "replace_text":
        target_text = desired_content or replace_text
        return (
            "edit_document_file",
            {"find_text": find_text, "replace_text": replace_text},
            {"contains_text": target_text},
        )
    return (
        "write_document_file",
        {"content": desired_content},
        {"contains_text": desired_content},
    )


def _document_path_payload(document_path: str) -> str:
    return str(Path(document_path))


def _observe_guided_document_surface(
    *,
    session_mount_id: str,
    document_path: str,
    document_family: str = "",
) -> DocumentObservation:
    _ = session_mount_id
    normalized_path = _document_path_payload(document_path)
    family = _normalize_document_family(normalized_path, document_family)
    if not normalized_path.strip():
        return DocumentObservation(
            document_path="",
            document_family=family,
            blockers=["document-path-required"],
        )
    path = Path(normalized_path)
    if not path.exists():
        return DocumentObservation(
            document_path=normalized_path,
            document_family=family,
            content_text="",
            revision_token="missing",
        )
    try:
        content_text = _read_document_text(path)
    except Exception as exc:
        return DocumentObservation(
            document_path=normalized_path,
            document_family=family,
            revision_token=_revision_token(path),
            blockers=[f"document-read-failed:{exc}"],
        )
    return DocumentObservation(
        document_path=normalized_path,
        document_family=family,
        content_text=content_text,
        revision_token=_revision_token(path),
    )


def _run_guided_document_action(
    *,
    action: str,
    session_mount_id: str,
    document_path: str,
    document_family: str = "",
    content: str = "",
    find_text: str = "",
    replace_text: str = "",
) -> dict[str, object]:
    _ = session_mount_id, document_family
    normalized_path = _document_path_payload(document_path)
    try:
        path = Path(normalized_path)
        if action == "write_document_file":
            _write_document_text(path, content)
            return {
                "ok": True,
                "action": action,
                "document_path": normalized_path,
                "content": content,
            }
        if action == "edit_document_file":
            _replace_document_text(path, find_text, replace_text)
            return {
                "ok": True,
                "action": action,
                "document_path": normalized_path,
                "find_text": find_text,
                "replace_text": replace_text,
            }
        return {
            "ok": False,
            "error": f"Unsupported document action: {action}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "action": action,
            "document_path": normalized_path,
        }


async def _action_guided_surface(
    *,
    session_mount_id: str,
    document_path: str,
    content: str,
    find_text: str = "",
    replace_text: str = "",
    document_family: str = "",
    max_steps: int = 4,
) -> ToolResponse:
    normalized_path = _document_path_payload(document_path)
    family = _normalize_document_family(normalized_path, document_family)
    observation = _observe_guided_document_surface(
        session_mount_id=session_mount_id,
        document_path=normalized_path,
        document_family=family,
    )
    owner = build_guided_document_surface_owner(
        formal_session_id=session_mount_id or "default",
        surface_thread_id=normalized_path,
        intent=GuidedDocumentSurfaceIntent(
            desired_content=content,
            find_text=find_text,
            replace_text=replace_text,
        ),
    )
    history: list[object] = []
    stop_reason = "planner-stop"
    blocker_kind = ""
    for _ in range(max(1, int(max_steps or 0))):
        checkpoint = owner.build_checkpoint(
            surface_kind="document",
            step_index=len(history),
            history=history,
        )
        step = owner.plan(
            observation=observation,
            history=history,
            checkpoint=checkpoint,
        )
        if step is None:
            if observation.blockers:
                stop_reason = "blocker-stop"
                blocker_kind = str(observation.blockers[0])
            break
        action_name, action_payload, success_assertion = _build_document_step_payload(
            intent_kind=step.intent_kind,
            desired_content=str(step.payload.get("content") or content),
            find_text=str(step.payload.get("find_text") or find_text),
            replace_text=str(step.payload.get("replace_text") or replace_text),
        )
        result = _run_guided_document_action(
            action=action_name,
            session_mount_id=session_mount_id,
            document_path=normalized_path,
            document_family=family,
            content=str(action_payload.get("content") or ""),
            find_text=str(action_payload.get("find_text") or ""),
            replace_text=str(action_payload.get("replace_text") or ""),
        )
        if not bool(result.get("ok")):
            stop_reason = "step-failed"
            blocker_kind = str(result.get("error") or "document-action-failed").strip()
            history.append(
                type(
                    "_DocumentStep",
                    (),
                    {
                        "intent_kind": step.intent_kind,
                        "status": "failed",
                        "blocker_kind": blocker_kind,
                        "target_slot": "",
                        "readback": {},
                    },
                )()
            )
            break
        observation = _observe_guided_document_surface(
            session_mount_id=session_mount_id,
            document_path=normalized_path,
            document_family=family,
        )
        verification_passed, readback = _verify_document_assertion(
            observation,
            success_assertion=success_assertion,
        )
        step_status = "succeeded" if verification_passed else "failed"
        if not verification_passed:
            stop_reason = "step-failed"
            blocker_kind = "verification-failed"
        history.append(
            type(
                "_DocumentStep",
                (),
                {
                    "intent_kind": step.intent_kind,
                    "status": step_status,
                    "blocker_kind": blocker_kind if step_status != "succeeded" else "",
                    "target_slot": "",
                    "readback": readback,
                },
            )()
        )
        if not verification_passed:
            break
    operation_checkpoint = owner.build_checkpoint(
        surface_kind="document",
        step_index=len(history),
        history=history,
    )
    ok = stop_reason in {"planner-stop", "max-steps"} and not blocker_kind
    if not history and not observation.blockers:
        ok = True
    payload = {
        "ok": ok,
        "action": "guided_surface",
        "session_mount_id": session_mount_id,
        "document_path": normalized_path,
        "document_family": family,
        "steps": [str(getattr(item, "intent_kind", "") or "") for item in history],
        "stop_reason": stop_reason,
        "blocker_kind": blocker_kind,
        "operation_checkpoint": operation_checkpoint.model_dump(mode="json"),
        "final_observation": observation.model_dump(mode="json"),
    }
    if not ok:
        payload["error"] = blocker_kind or stop_reason
    return _tool_response(payload)


async def document_surface(
    *,
    action: str = "guided_surface",
    session_mount_id: str = "",
    document_path: str = "",
    document_family: str = "",
    content: str = "",
    find_text: str = "",
    replace_text: str = "",
    max_steps: int = 4,
) -> ToolResponse:
    """Operate on a document thread through a guided or direct document frontdoor."""
    normalized_action = str(action or "").strip().lower() or "guided_surface"
    normalized_path = _document_path_payload(document_path)
    family = _normalize_document_family(normalized_path, document_family)
    if normalized_action == "observe":
        observation = _observe_guided_document_surface(
            session_mount_id=session_mount_id,
            document_path=normalized_path,
            document_family=family,
        )
        return _tool_response(
            {
                "ok": not bool(observation.blockers),
                "action": normalized_action,
                "observation": observation.model_dump(mode="json"),
            }
        )
    if normalized_action == "guided_surface":
        return await _action_guided_surface(
            session_mount_id=session_mount_id,
            document_path=normalized_path,
            content=content,
            find_text=find_text,
            replace_text=replace_text,
            document_family=family,
            max_steps=max_steps,
        )
    if normalized_action in {"write_document", "replace_text"}:
        if normalized_action == "write_document":
            result = _run_guided_document_action(
                action="write_document_file",
                session_mount_id=session_mount_id,
                document_path=normalized_path,
                document_family=family,
                content=content,
            )
            success_assertion = {"contains_text": content}
        else:
            result = _run_guided_document_action(
                action="edit_document_file",
                session_mount_id=session_mount_id,
                document_path=normalized_path,
                document_family=family,
                find_text=find_text,
                replace_text=replace_text,
            )
            success_assertion = {"contains_text": replace_text or content}
        observation = _observe_guided_document_surface(
            session_mount_id=session_mount_id,
            document_path=normalized_path,
            document_family=family,
        )
        verification_passed, readback = _verify_document_assertion(
            observation,
            success_assertion=success_assertion,
        )
        ok = bool(result.get("ok")) and verification_passed and not observation.blockers
        payload = {
            "ok": ok,
            "action": normalized_action,
            "document_path": normalized_path,
            "document_family": family,
            "readback": readback,
            "observation": observation.model_dump(mode="json"),
        }
        if not ok:
            payload["error"] = str(result.get("error") or "document-action-failed")
        return _tool_response(payload)
    return _tool_response(
        {
            "ok": False,
            "error": f"Unsupported document_surface action: {normalized_action}",
        }
    )


__all__ = ["document_surface"]
