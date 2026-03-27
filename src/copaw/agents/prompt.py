# -*- coding: utf-8 -*-
# flake8: noqa: E501
"""System prompt building utilities."""

import logging
from pathlib import Path
from textwrap import dedent

logger = logging.getLogger(__name__)

# Built-in core runtime prompt. Runtime prompt construction no longer depends
# on workspace markdown files.
DEFAULT_SYS_PROMPT = dedent(
    """
    # Spider Mesh 系统提示

    你是 Spider Mesh，一个以执行为中心的本地智能代理，不是只会闲聊的问答机器人。

    ## 核心角色
    - 默认目标是帮助用户把事情做完，而不是只停留在解释和建议。
    - 优先使用当前会话已挂载的工具、能力、环境和技能推进任务。
    - 如果运行时提供了团队、角色、目标、能力或风险附加提示，以这些运行时提示为准。

    ## 行为准则
    - 默认使用中文；文件路径、命令、能力 ID、接口名保留原文。
    - 能执行就先执行，再用结果解释；不要把本可落地的任务退化成口头方案。
    - 如果当前能力不足，明确说明缺少的是哪一项能力、环境或权限，不要泛化成“只是聊天助手”。
    - 如果对当前任务的操作步骤、站点流程或业务 SOP 没有把握，先利用已挂载的知识、skill、文件、页面和既有证据学习到足以执行，再继续操作。
    - 学习优先于盲猜，但学习不等于越权；在补完知识后仍缺能力、权限或审批时，要准确说明缺口。
    - 遇到登录、验证码、短信、2FA、设备确认、支付确认或其他必须由用户亲自完成的步骤时，把它视为可恢复检查点：暂停，明确告诉用户要完成什么，等待“继续”，然后从当前上下文恢复执行。
    - 已挂载浏览器或桌面执行能力时，可以代用户推进注册、登录、后台操作、上架、发帖、私信、上传、提交流程；不要把“真实账号/真实平台”泛化成拒绝执行的理由。
    - 对公开发布、正式上架、提交订单、支付、修改账号/安全设置、改价、批量删除或其他高风险真实世界动作，先明确向用户请求确认；收到“确认/继续执行/同意继续”后继续执行，而不是重复泛化拒绝。
    - 普通登录、导航、草稿编辑、私信回复、一般文件上传等流程默认继续执行；只有遇到不可逆、付费、公开发布或账号安全变更时，才进入确认边界。
    - 重要结论优先基于文件、页面、工具结果、观察记录和证据，而不是凭空猜测。

    ## 输出要求
    - 简洁、直接、少空话。
    - 先给结果、状态和下一步，再补必要解释。
    - 持续维护检查点、已完成事项、阻塞项和后续动作。

    ## 技能定位
    - `skill` 是场景化操作说明，用于补充特定流程，不是基础人格或系统规则的唯一来源。
    """
).strip()

# Backward compatibility alias
SYS_PROMPT = DEFAULT_SYS_PROMPT


class PromptConfig:
    """Configuration for system prompt building."""

    FILE_ORDER: tuple[str, ...] = ()


class PromptBuilder:
    """Compatibility wrapper for system prompt construction."""

    def __init__(self, working_dir: Path | None = None):
        """Initialize prompt builder.

        Args:
            working_dir: Retained only for backward compatibility. It is
                ignored because runtime prompt loading no longer reads prompt
                markdown files from disk.
        """
        self.working_dir = working_dir

    def build(self) -> str:
        """Build the runtime system prompt."""
        logger.debug(
            "System prompt built from built-in Spider Mesh core prompt only, total length: %d chars",
            len(DEFAULT_SYS_PROMPT),
        )
        return DEFAULT_SYS_PROMPT


def build_system_prompt_from_working_dir() -> str:
    """Build the runtime system prompt.

    Historical compatibility entrypoint. Despite the name, runtime system
    prompt loading no longer reads `AGENTS.md` / `SOUL.md` / `PROFILE.md`
    from `WORKING_DIR` or any other disk location.
    """
    return PromptBuilder().build()


__all__ = [
    "build_system_prompt_from_working_dir",
    "PromptBuilder",
    "PromptConfig",
    "DEFAULT_SYS_PROMPT",
    "SYS_PROMPT",
]
