from copaw.capabilities.remote_skill_presentation import (
    localize_remote_skill_text,
    present_remote_skill_name,
)


def test_present_remote_skill_name_avoids_generic_verb_title_from_summary() -> None:
    title = present_remote_skill_name(
        slug="powerpoint-pptx",
        name="Powerpoint / PPTX",
        summary=(
            "Create, inspect, and edit Microsoft PowerPoint presentations.\n"
            "创建、检查和编辑 Microsoft PowerPoint 演示文稿及 PPTX 文件。"
        ),
        curated=True,
    )

    assert title != "创建"
    assert "Powerpoint" in title or "PPTX" in title


def test_present_remote_skill_name_strips_legacy_brand_tokens() -> None:
    title = present_remote_skill_name(
        slug="openclaw-github-assistant",
        name="OpenClaw GitHub Assistant",
        summary="Query and manage GitHub repositories.",
    )

    assert "OpenClaw" not in title
    assert "GitHub" in title


def test_localize_remote_skill_text_repairs_mojibake_chinese() -> None:
    mojibake = "?????????????????".encode("utf-8").decode("latin1")
    localized = localize_remote_skill_text(mojibake)

    assert localized == "?????????????????"
