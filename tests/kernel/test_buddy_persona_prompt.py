from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel import main_brain_chat_service as main_brain_chat_module
from copaw.kernel import query_execution_prompt as query_prompt_module
from copaw.kernel.buddy_persona_prompt import build_buddy_persona_prompt


def test_build_buddy_persona_prompt_returns_shared_lines_and_signature() -> None:
    surface = SimpleNamespace(
        profile=SimpleNamespace(
            profile_id="profile-buddy",
            display_name="阿澄",
            profession="自由创作者",
            current_stage="重建期",
        ),
        growth_target=SimpleNamespace(
            primary_direction="建立长期创作与收入系统",
        ),
        relationship=SimpleNamespace(
            encouragement_style="old-friend",
        ),
        presentation=SimpleNamespace(
            buddy_name="小澄",
            current_goal_summary="建立可持续的创作事业与独立成长轨道",
            current_task_summary="写出第一篇真正代表自己的案例文章",
            why_now_summary="因为这是把长期方向从想象拉进现实的第一份证据。",
            single_next_action_summary="现在先打开文档，写下标题和三条核心观点。",
            companion_strategy_summary="先接住情绪，再把任务缩成一个最小动作。",
        ),
    )

    lines, signature = build_buddy_persona_prompt(surface=surface, heading="##")

    assert lines[0] == "## Buddy 对外人格"
    assert "- 伙伴名：小澄" in lines
    assert any(line.endswith("阿澄 / 自由创作者 / 重建期") for line in lines)
    assert any(line.endswith("建立可持续的创作事业与独立成长轨道") for line in lines)
    assert any(line.endswith("写出第一篇真正代表自己的案例文章") for line in lines)
    assert any(line.endswith("现在先打开文档，写下标题和三条核心观点。") for line in lines)
    assert any("先接住情绪，再把任务缩成一个最小动作。" in line for line in lines)
    assert signature == (
        "buddy:profile-buddy|小澄|建立可持续的创作事业与独立成长轨道|"
        "写出第一篇真正代表自己的案例文章|因为这是把长期方向从想象拉进现实的第一份证据。|"
        "现在先打开文档，写下标题和三条核心观点。|先接住情绪，再把任务缩成一个最小动作。"
    )


def test_main_brain_buddy_block_uses_shared_helper(monkeypatch) -> None:
    seen: list[tuple[object, str]] = []

    def _fake_builder(*, surface, heading: str = "##"):
        seen.append((surface, heading))
        return ["## Buddy 对外人格", "- 伙伴名：小澄"], "buddy:sig"

    monkeypatch.setattr(main_brain_chat_module, "build_buddy_persona_prompt", _fake_builder)
    surface = SimpleNamespace(profile=SimpleNamespace(profile_id="profile-buddy"))
    fake_self = SimpleNamespace(
        _buddy_projection_service=SimpleNamespace(
            build_chat_surface=lambda profile_id: surface,
        ),
    )
    request = SimpleNamespace(buddy_profile_id="profile-buddy")

    block, signature = main_brain_chat_module.MainBrainChatService._build_buddy_persona_block(
        fake_self,
        request=request,
    )

    assert seen == [(surface, "##")]
    assert block == "## Buddy 对外人格\n- 伙伴名：小澄"
    assert signature == "buddy:sig"


def test_query_execution_buddy_lines_use_shared_helper(monkeypatch) -> None:
    seen: list[tuple[object, str]] = []

    def _fake_builder(*, surface, heading: str = "##"):
        seen.append((surface, heading))
        return ["# Buddy 对外人格", "- 伙伴名：小澄"], "buddy:sig"

    monkeypatch.setattr(query_prompt_module, "build_buddy_persona_prompt", _fake_builder)
    surface = SimpleNamespace(profile=SimpleNamespace(profile_id="profile-buddy"))
    fake_self = SimpleNamespace(
        _buddy_projection_service=SimpleNamespace(
            build_chat_surface=lambda profile_id: surface,
        ),
    )
    request = SimpleNamespace(buddy_profile_id="profile-buddy")

    lines = query_prompt_module._QueryExecutionPromptMixin._build_buddy_persona_lines(
        fake_self,
        request=request,
    )

    assert seen == [(surface, "#")]
    assert lines == ["# Buddy 对外人格", "- 伙伴名：小澄"]
