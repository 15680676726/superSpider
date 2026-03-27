# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from scripts.reset_autonomy_runtime import reset_autonomy_runtime


def test_reset_autonomy_runtime_removes_legacy_phase1_state(tmp_path: Path) -> None:
    state_db = tmp_path / "state" / "phase1.sqlite3"
    evidence_db = tmp_path / "evidence" / "phase1.sqlite3"
    learning_db = tmp_path / "learning" / "phase1.sqlite3"
    qmd_dir = tmp_path / "memory" / "qmd"

    state_db.parent.mkdir(parents=True)
    evidence_db.parent.mkdir(parents=True)
    learning_db.parent.mkdir(parents=True)
    qmd_dir.mkdir(parents=True)

    state_db.write_text("state", encoding="utf-8")
    evidence_db.write_text("evidence", encoding="utf-8")
    learning_db.write_text("learning", encoding="utf-8")
    (qmd_dir / "manifest.json").write_text("{}", encoding="utf-8")

    result = reset_autonomy_runtime(root=tmp_path, dry_run=False)

    assert result["removed_paths"] == [
        str(state_db),
        str(evidence_db),
        str(learning_db),
        str(qmd_dir),
    ]
    assert not state_db.exists()
    assert not evidence_db.exists()
    assert not learning_db.exists()
    assert not qmd_dir.exists()


def test_reset_autonomy_runtime_dry_run_keeps_files(tmp_path: Path) -> None:
    state_db = tmp_path / "state" / "phase1.sqlite3"
    state_db.parent.mkdir(parents=True)
    state_db.write_text("state", encoding="utf-8")

    result = reset_autonomy_runtime(root=tmp_path, dry_run=True)

    assert result["removed_paths"] == [str(state_db)]
    assert state_db.exists()
