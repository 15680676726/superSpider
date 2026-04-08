from pathlib import Path

import copaw.app._app as app_module


def test_resolve_console_static_dir_finds_repo_dist_without_repo_cwd(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    fake_app_file = repo_root / "src" / "copaw" / "app" / "_app.py"
    fake_app_file.parent.mkdir(parents=True, exist_ok=True)
    fake_app_file.write_text("# fake app", encoding="utf-8")
    dist_dir = repo_root / "console" / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<html>runtime</html>", encoding="utf-8")
    outside_cwd = tmp_path / "outside"
    outside_cwd.mkdir(parents=True, exist_ok=True)

    monkeypatch.delenv(app_module._CONSOLE_STATIC_ENV, raising=False)
    monkeypatch.setattr(app_module, "__file__", str(fake_app_file))
    monkeypatch.chdir(outside_cwd)

    resolved = app_module._resolve_console_static_dir()

    assert resolved == str(dist_dir)


def test_read_root_disables_cache_for_console_index(
    monkeypatch,
    tmp_path: Path,
) -> None:
    index_file = tmp_path / "index.html"
    index_file.write_text("<html>baize</html>", encoding="utf-8")
    monkeypatch.setattr(app_module, "_CONSOLE_INDEX", index_file)

    response = app_module.read_root()

    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"


def test_console_spa_disables_cache_for_console_index(
    monkeypatch,
    tmp_path: Path,
) -> None:
    index_file = tmp_path / "index.html"
    index_file.write_text("<html>baize</html>", encoding="utf-8")
    monkeypatch.setattr(app_module, "_CONSOLE_INDEX", index_file)

    response = app_module._console_spa("runtime/actors")

    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
