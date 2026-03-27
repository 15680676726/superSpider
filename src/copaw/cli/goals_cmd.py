# -*- coding: utf-8 -*-
"""CLI commands for goal inspection and dispatch."""
from __future__ import annotations

import json
from typing import Optional

import click

from .http import client, print_json


def _base_url(ctx: click.Context, base_url: Optional[str]) -> str:
    if base_url:
        return base_url.rstrip("/")
    host = (ctx.obj or {}).get("host", "127.0.0.1")
    port = (ctx.obj or {}).get("port", 8088)
    return f"http://{host}:{port}"


@click.group("goals")
def goals_group() -> None:
    """Inspect, compile, and dispatch goals via the HTTP API."""


@goals_group.command("list")
@click.option("--status", default=None, help="Filter by goal status")
@click.option("--owner-scope", default=None, help="Filter by owner scope")
@click.option("--base-url", default=None, help="Override API base URL")
@click.pass_context
def list_goals(
    ctx: click.Context,
    status: Optional[str],
    owner_scope: Optional[str],
    base_url: Optional[str],
) -> None:
    params: dict[str, object] = {}
    if status:
        params["status"] = status
    if owner_scope:
        params["owner_scope"] = owner_scope
    with client(_base_url(ctx, base_url)) as c:
        response = c.get("/goals", params=params)
        response.raise_for_status()
        print_json(response.json())


@goals_group.command("compile")
@click.argument("goal_id")
@click.option(
    "--context-json",
    default="{}",
    help="Inline JSON context passed to the compiler",
)
@click.option("--base-url", default=None, help="Override API base URL")
@click.pass_context
def compile_goal(
    ctx: click.Context,
    goal_id: str,
    context_json: str,
    base_url: Optional[str],
) -> None:
    with client(_base_url(ctx, base_url)) as c:
        response = c.post(
            f"/goals/{goal_id}/compile",
            json={"context": json.loads(context_json)},
        )
        response.raise_for_status()
        print_json(response.json())


@goals_group.command("dispatch")
@click.argument("goal_id")
@click.option("--owner-agent-id", default="copaw-operator", help="Kernel owner agent id")
@click.option("--execute/--no-execute", default=False, help="Execute admitted tasks immediately")
@click.option("--activate/--no-activate", default=True, help="Mark the goal active before dispatch")
@click.option(
    "--context-json",
    default="{}",
    help="Inline JSON context merged into compiler context",
)
@click.option("--base-url", default=None, help="Override API base URL")
@click.pass_context
def dispatch_goal(
    ctx: click.Context,
    goal_id: str,
    owner_agent_id: str,
    execute: bool,
    activate: bool,
    context_json: str,
    base_url: Optional[str],
) -> None:
    _ = (ctx, goal_id, owner_agent_id, execute, activate, context_json, base_url)
    raise click.ClickException(
        "`goals dispatch` ????????????????????????????????"
    )
