# -*- coding: utf-8 -*-
"""CLI commands for capability discovery and execution."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from .http import client, print_json


def _base_url(ctx: click.Context, base_url: Optional[str]) -> str:
    if base_url:
        return base_url.rstrip("/")
    host = (ctx.obj or {}).get("host", "127.0.0.1")
    port = (ctx.obj or {}).get("port", 8088)
    return f"http://{host}:{port}"


@click.group("capabilities")
def capabilities_group() -> None:
    """Inspect and execute unified capabilities via the HTTP API."""


@capabilities_group.command("list")
@click.option("--kind", default=None, help="Filter by capability kind")
@click.option("--enabled-only", is_flag=True, help="Only show enabled capabilities")
@click.option("--base-url", default=None, help="Override API base URL")
@click.pass_context
def list_capabilities(
    ctx: click.Context,
    kind: Optional[str],
    enabled_only: bool,
    base_url: Optional[str],
) -> None:
    params: dict[str, object] = {}
    if kind:
        params["kind"] = kind
    if enabled_only:
        params["enabled_only"] = True
    with client(_base_url(ctx, base_url)) as c:
        response = c.get("/capabilities", params=params)
        response.raise_for_status()
        print_json(response.json())


@capabilities_group.command("execute")
@click.argument("capability_id")
@click.option("--title", default=None, help="Override kernel task title")
@click.option("--environment-ref", default=None, help="Attach an environment ref")
@click.option("--owner-agent-id", default="copaw-operator", help="Kernel owner agent id")
@click.option(
    "--payload-json",
    default="{}",
    help="Inline JSON payload passed to the capability",
)
@click.option(
    "--payload-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Load payload JSON from file",
)
@click.option("--base-url", default=None, help="Override API base URL")
@click.pass_context
def execute_capability(
    ctx: click.Context,
    capability_id: str,
    title: Optional[str],
    environment_ref: Optional[str],
    owner_agent_id: str,
    payload_json: str,
    payload_file: Optional[Path],
    base_url: Optional[str],
) -> None:
    _ = (
        ctx,
        capability_id,
        title,
        environment_ref,
        owner_agent_id,
        payload_json,
        payload_file,
        base_url,
    )
    raise click.ClickException(
        "capabilities execute 已退役；请直接在主脑聊天窗口描述需求，由主脑决定是否编排执行。",
    )
