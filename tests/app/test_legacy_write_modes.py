# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib

import pytest


def test_legacy_write_policy_module_is_retired() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("copaw.app.legacy")
