from __future__ import annotations

import logging
from pathlib import Path

import pytest

from copaw.utils.logging import LOG_NAMESPACE, add_copaw_file_handler


def test_add_copaw_file_handler_absorbs_permission_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logger = logging.getLogger(LOG_NAMESPACE)
    original_handlers = list(logger.handlers)

    class _DeniedFileHandler:
        def __init__(self, *args, **kwargs) -> None:
            raise PermissionError("denied")

    monkeypatch.setattr(
        logging.handlers,
        "RotatingFileHandler",
        _DeniedFileHandler,
    )

    try:
        add_copaw_file_handler(tmp_path / "copaw.log")
    finally:
        logger.handlers = original_handlers
