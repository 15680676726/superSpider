# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


@dataclass(frozen=True)
class GateCommand:
    name: str
    command: tuple[str, ...]
    cwd: Path


def build_gate_commands(repo_root: Path) -> list[GateCommand]:
    root = repo_root.resolve()
    return [
        GateCommand(
            name="后端主链回归",
            cwd=root,
            command=(
                "python",
                "-m",
                "pytest",
                "tests/app/test_runtime_projection_contracts.py",
                "tests/app/test_cron_executor.py",
                "tests/fixed_sops/test_service.py",
                "tests/app/test_fixed_sop_kernel_api.py",
                "tests/app/test_workflow_templates_api.py",
                "tests/app/runtime_center_api_parts/detail_environment.py",
                "tests/app/runtime_center_api_parts/overview_governance.py",
                "tests/app/test_runtime_center_api.py",
                "tests/app/test_runtime_query_services.py",
                "tests/kernel/test_governance.py",
                "-q",
            ),
        ),
        GateCommand(
            name="长跑与删旧回归",
            cwd=root,
            command=(
                "python",
                "-m",
                "pytest",
                "tests/app/industry_api_parts/runtime_updates.py",
                "tests/app/test_phase_next_autonomy_smoke.py",
                "tests/app/test_goals_api.py",
                "tests/test_goal_capabilities_cmd.py",
                "-q",
            ),
        ),
        GateCommand(
            name="前台定向回归",
            cwd=root,
            command=(
                "cmd",
                "/c",
                "npm",
                "--prefix",
                "console",
                "run",
                "test",
                "--",
                "src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx",
                "src/components/RuntimeExecutionStrip.test.tsx",
                "src/pages/Predictions/index.test.ts",
                "src/pages/Knowledge/index.test.tsx",
            ),
        ),
        GateCommand(
            name="控制台构建",
            cwd=root,
            command=("cmd", "/c", "npm", "--prefix", "console", "run", "build"),
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    commands = build_gate_commands(repo_root)
    if "--list" in args:
        for item in commands:
            print(f"[{item.name}] {' '.join(item.command)}")
        return 0
    for item in commands:
        print(f"==> {item.name}")
        completed = subprocess.run(item.command, cwd=item.cwd, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
