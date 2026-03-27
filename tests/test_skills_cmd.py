# -*- coding: utf-8 -*-
from __future__ import annotations

from click.testing import CliRunner

import copaw.cli.skills_cmd as skills_cmd_module


class FakeCapabilityService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def list_skill_specs(self) -> list[dict[str, object]]:
        return [
            {
                "name": "alpha",
                "source": "builtin",
                "content": "alpha",
                "path": "/skills/alpha",
                "references": {},
                "scripts": {},
                "enabled": False,
            },
            {
                "name": "beta",
                "source": "customized",
                "content": "beta",
                "path": "/skills/beta",
                "references": {},
                "scripts": {},
                "enabled": True,
            },
        ]

    def set_capability_enabled(
        self,
        capability_id: str,
        *,
        enabled: bool,
    ) -> dict[str, object]:
        self.calls.append((capability_id, enabled))
        return {"id": capability_id, "enabled": enabled}


def test_configure_skills_interactive_uses_capability_service(monkeypatch) -> None:
    service = FakeCapabilityService()
    monkeypatch.setattr(skills_cmd_module, "_capability_service", lambda: service)
    monkeypatch.setattr(
        skills_cmd_module,
        "prompt_checkbox",
        lambda *args, **kwargs: ["alpha"],
    )
    monkeypatch.setattr(
        skills_cmd_module,
        "prompt_confirm",
        lambda *args, **kwargs: True,
    )

    skills_cmd_module.configure_skills_interactive()

    assert service.calls == [
        ("skill:alpha", True),
        ("skill:beta", False),
    ]


def test_skills_list_command_uses_capability_service(monkeypatch) -> None:
    service = FakeCapabilityService()
    monkeypatch.setattr(skills_cmd_module, "_capability_service", lambda: service)

    result = CliRunner().invoke(skills_cmd_module.skills_group, ["list"])

    assert result.exit_code == 0
    assert "alpha" in result.output
    assert "beta" in result.output
