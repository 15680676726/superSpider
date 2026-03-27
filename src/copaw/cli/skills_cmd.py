# -*- coding: utf-8 -*-
"""CLI skill: list and interactively enable/disable skills."""
from __future__ import annotations

import click

from ..capabilities import CapabilityService
from .utils import prompt_checkbox, prompt_confirm


def _capability_service() -> CapabilityService:
    return CapabilityService()


def _list_skill_specs(service: CapabilityService) -> list[dict[str, object]]:
    return list(service.list_skill_specs())


# pylint: disable=too-many-branches
def configure_skills_interactive() -> None:
    """Interactively select which skills to enable (multi-select)."""
    service = _capability_service()
    all_skills = _list_skill_specs(service)
    if not all_skills:
        click.echo("No skills found. Nothing to configure.")
        return

    available = {
        str(skill.get("name") or "")
        for skill in all_skills
        if skill.get("enabled")
    }
    all_names = {
        str(skill.get("name") or "")
        for skill in all_skills
        if str(skill.get("name") or "")
    }

    # Default to all skills if nothing is currently active (first time)
    default_checked = available if available else all_names

    options: list[tuple[str, str]] = []
    for skill in sorted(all_skills, key=lambda item: str(item.get("name") or "")):
        name = str(skill.get("name") or "")
        if not name:
            continue
        status = "enabled" if name in available else "disabled"
        source = str(skill.get("source") or "unknown")
        options.append((f"{name} [{status}] ({source})", name))

    click.echo("\n=== Skills Configuration ===")
    click.echo("Use arrow keys to move, <space> to toggle, <enter> to confirm.\n")

    selected = prompt_checkbox(
        "Select skills to enable:",
        options=options,
        checked=default_checked,
        select_all_option=False,
    )

    if selected is None:
        click.echo("\n\nOperation cancelled.")
        return

    selected_set = set(selected)

    to_enable = selected_set - available
    to_disable = (all_names & available) - selected_set

    if not to_enable and not to_disable:
        click.echo("\nNo changes needed.")
        return

    click.echo()
    if to_enable:
        click.echo(
            click.style(
                f"  + Enable:  {', '.join(sorted(to_enable))}",
                fg="green",
            ),
        )
    if to_disable:
        click.echo(
            click.style(
                f"  - Disable: {', '.join(sorted(to_disable))}",
                fg="red",
            ),
        )

    save = prompt_confirm("Apply changes?", default=True)
    if not save:
        click.echo("Skipped. No changes applied.")
        return

    for name in sorted(to_enable):
        result = service.set_capability_enabled(f"skill:{name}", enabled=True)
        if result.get("error") is None and result.get("enabled") is True:
            click.echo(f"  Enabled: {name}")
        else:
            click.echo(click.style(f"  Failed to enable: {name}", fg="red"))

    for name in sorted(to_disable):
        result = service.set_capability_enabled(f"skill:{name}", enabled=False)
        if result.get("error") is None and result.get("enabled") is False:
            click.echo(f"  Disabled: {name}")
        else:
            click.echo(click.style(f"  Failed to disable: {name}", fg="red"))

    click.echo("\nSkills configuration updated.")


@click.group("skills")
def skills_group() -> None:
    """Manage skills (list / configure)."""


@skills_group.command("list")
def list_cmd() -> None:
    """Show all skills and their enabled/disabled status."""
    service = _capability_service()
    all_skills = _list_skill_specs(service)
    available = {
        str(skill.get("name") or "")
        for skill in all_skills
        if skill.get("enabled")
    }

    if not all_skills:
        click.echo("No skills found.")
        return

    click.echo(f"\n{'-' * 50}")
    click.echo(f"  {'Skill Name':<30s} {'Source':<12s} Status")
    click.echo(f"{'-' * 50}")

    for skill in sorted(all_skills, key=lambda item: str(item.get("name") or "")):
        name = str(skill.get("name") or "")
        source = str(skill.get("source") or "unknown")
        status = (
            click.style("enabled", fg="green")
            if name in available
            else click.style("disabled", fg="red")
        )
        click.echo(f"  {name:<30s} {source:<12s} {status}")

    click.echo(f"{'-' * 50}")
    enabled_count = sum(
        1
        for skill in all_skills
        if str(skill.get("name") or "") in available
    )
    click.echo(
        f"  Total: {len(all_skills)} skills, "
        f"{enabled_count} enabled, "
        f"{len(all_skills) - enabled_count} disabled\n",
    )


@skills_group.command("config")
def configure_cmd() -> None:
    configure_skills_interactive()
