from pathlib import Path

import copaw.app._app as app_module


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
