# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from scripts.run_p0_runtime_terminal_gate import build_gate_commands


def test_build_gate_commands_covers_python_ui_and_build_gate() -> None:
    commands = build_gate_commands(Path("D:/word/copaw"))

    names = [command.name for command in commands]
    assert names == [
        "后端主链回归",
        "长跑与删旧回归",
        "前台定向回归",
        "控制台构建",
    ]

    python_gate = commands[0]
    assert python_gate.cwd == Path("D:/word/copaw")
    assert python_gate.command[:3] == ("python", "-m", "pytest")
    assert "tests/app/test_runtime_projection_contracts.py" in python_gate.command
    assert "tests/kernel/test_governance.py" in python_gate.command

    smoke_gate = commands[1]
    assert smoke_gate.command[:3] == ("python", "-m", "pytest")
    assert "tests/app/test_phase_next_autonomy_smoke.py" in smoke_gate.command
    assert "tests/test_goal_capabilities_cmd.py" in smoke_gate.command

    ui_gate = commands[2]
    assert ui_gate.command[:5] == ("cmd", "/c", "npm", "--prefix", "console")
    assert "src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx" in ui_gate.command
    assert "src/components/RuntimeExecutionStrip.test.tsx" in ui_gate.command

    build_gate = commands[3]
    assert build_gate.command == ("cmd", "/c", "npm", "--prefix", "console", "run", "build")
