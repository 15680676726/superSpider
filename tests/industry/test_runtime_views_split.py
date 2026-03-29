from pathlib import Path


def test_runtime_views_mixin_owns_instance_detail_builder() -> None:
    runtime_views = Path("src/copaw/industry/service_runtime_views.py").read_text(
        encoding="utf-8",
    )
    service_strategy = Path("src/copaw/industry/service_strategy.py").read_text(
        encoding="utf-8",
    )

    assert "class _IndustryRuntimeViewsMixin:" in runtime_views
    assert "def _build_instance_detail(" in runtime_views
    assert "def _build_instance_detail(" in service_strategy
    assert "_IndustryRuntimeViewsMixin._build_instance_detail(" in service_strategy
