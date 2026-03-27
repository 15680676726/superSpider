# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403


class _WorkflowServiceBuiltinMixin:
    def _builtin_templates(self) -> list[WorkflowTemplateRecord]:
        now = _utc_now()
        return [
            WorkflowTemplateRecord(
                template_id="industry-daily-control-loop",
                title="行业日常经营闭环",
                summary="发起每日执行中枢复盘，并安排协作角色完成证据信号扫描。",
                category="operations",
                status="active",
                version="v1",
                industry_tags=["general", "operations"],
                team_modes=["industry"],
                dependency_capability_ids=[
                    "system:dispatch_query",
                    "tool:browser_use",
                ],
                suggested_role_ids=[
                    EXECUTION_CORE_ROLE_ID,
                    "solution-lead",
                    "researcher",
                ],
                owner_role_id=EXECUTION_CORE_ROLE_ID,
                parameter_schema={
                    "fields": [
                        {
                            "id": "business_goal",
                            "label": "经营目标",
                            "type": "string",
                            "required": True,
                            "default": "稳定下一步经营动作",
                        },
                        {
                            "id": "daily_review_time",
                            "label": "每日复盘 Cron",
                            "type": "string",
                            "required": False,
                            "default": "0 9 * * *",
                        },
                        {
                            "id": "timezone",
                            "label": "时区",
                            "type": "string",
                            "required": False,
                            "default": "UTC",
                        },
                    ]
                },
                step_specs=[
                    {
                        "id": "control-goal",
                        "kind": "goal",
                        "execution_mode": "control",
                        "owner_role_id": EXECUTION_CORE_ROLE_ID,
                        "title": "{industry_label} 每日执行中枢循环",
                        "summary": "复核今日目标：{business_goal}",
                        "required_capability_ids": ["system:dispatch_query"],
                        "plan_steps": [
                            "复核当前证据与风险。",
                            "确定下一步协同动作。",
                            "返回简洁的经营简报。",
                        ],
                    },
                    {
                        "id": "research-goal",
                        "kind": "goal",
                        "execution_mode": "leaf",
                        "owner_role_id": "solution-lead",
                        "owner_role_candidates": [
                            "solution-lead",
                            "researcher",
                            EXECUTION_CORE_ROLE_ID,
                        ],
                        "title": "{industry_label} 证据信号扫描",
                        "summary": "收集支撑当前经营目标“{business_goal}”的关键信号",
                        "required_capability_ids": [
                            "system:dispatch_query",
                            "tool:browser_use",
                        ],
                        "plan_steps": [
                            "扫描当前市场与渠道信号。",
                            "提炼高信号发现，反馈给执行中枢。",
                        ],
                    },
                    {
                        "id": "daily-control-schedule",
                        "kind": "schedule",
                        "execution_mode": "control",
                        "owner_role_id": EXECUTION_CORE_ROLE_ID,
                        "title": "{industry_label} 每日执行复盘",
                        "summary": "围绕“{business_goal}”的执行中枢定期复盘",
                        "required_capability_ids": ["system:dispatch_query"],
                        "cron": "{daily_review_time}",
                        "timezone": "{timezone}",
                        "request_input": "请执行 {industry_label} 的每日中枢复盘。目标：{business_goal}",
                        "dispatch_channel": "console",
                        "dispatch_mode": "final",
                    },
                ],
                metadata={"builtin": True},
                created_at=now,
                updated_at=now,
            ),
            WorkflowTemplateRecord(
                template_id="industry-weekly-research-synthesis",
                title="行业周度信号综述",
                summary="执行周度信号综述，并产出可直接进入执行的经营简报。",
                category="signals",
                status="active",
                version="v1",
                industry_tags=["general", "signals"],
                team_modes=["industry"],
                dependency_capability_ids=[
                    "system:dispatch_query",
                    "tool:browser_use",
                ],
                suggested_role_ids=["solution-lead", "researcher", EXECUTION_CORE_ROLE_ID],
                owner_role_id="solution-lead",
                parameter_schema={
                    "fields": [
                        {
                            "id": "focus_area",
                            "label": "关注主题",
                            "type": "string",
                            "required": True,
                            "default": "市场定位",
                        },
                        {
                            "id": "weekly_review_cron",
                            "label": "每周复盘 Cron",
                            "type": "string",
                            "required": False,
                            "default": "0 10 * * 1",
                        },
                        {
                            "id": "timezone",
                            "label": "时区",
                            "type": "string",
                            "required": False,
                            "default": "UTC",
                        },
                    ]
                },
                step_specs=[
                    {
                        "id": "weekly-research-goal",
                        "kind": "goal",
                        "execution_mode": "leaf",
                        "owner_role_id": "solution-lead",
                        "owner_role_candidates": [
                            "solution-lead",
                            "researcher",
                            EXECUTION_CORE_ROLE_ID,
                        ],
                        "title": "{industry_label} 周度信号综述",
                        "summary": "总结围绕“{focus_area}”的最新证据",
                        "required_capability_ids": [
                            "system:dispatch_query",
                            "tool:browser_use",
                        ],
                        "plan_steps": [
                            "收集本周最强信号。",
                            "综合分析这些信号对团队的含义。",
                        ],
                    },
                    {
                        "id": "weekly-control-brief",
                        "kind": "goal",
                        "execution_mode": "control",
                        "owner_role_id": EXECUTION_CORE_ROLE_ID,
                        "title": "{industry_label} 执行简报",
                        "summary": "把信号综述转化为下一步经营简报。",
                        "required_capability_ids": ["system:dispatch_query"],
                        "plan_steps": [
                            "复核信号综述结果。",
                            "确定下一步经营建议。",
                        ],
                    },
                    {
                        "id": "weekly-research-schedule",
                        "kind": "schedule",
                        "execution_mode": "leaf",
                        "owner_role_id": "solution-lead",
                        "owner_role_candidates": [
                            "solution-lead",
                            "researcher",
                            EXECUTION_CORE_ROLE_ID,
                        ],
                        "title": "{industry_label} 周度信号综述",
                        "summary": "围绕“{focus_area}”的周度信号综述",
                        "required_capability_ids": [
                            "system:dispatch_query",
                            "tool:browser_use",
                        ],
                        "cron": "{weekly_review_cron}",
                        "timezone": "{timezone}",
                        "request_input": "请执行 {industry_label} 的周度信号综述。关注点：{focus_area}",
                        "dispatch_channel": "console",
                        "dispatch_mode": "final",
                    },
                ],
                metadata={"builtin": True},
                created_at=now,
                updated_at=now,
            ),
            WorkflowTemplateRecord(
                template_id="desktop-outreach-smoke",
                title="桌面外联演练流程",
                summary=(
                    "规划并追踪一次受控的 Windows 桌面跟进行动，同时不把执行中枢降级成默认叶子执行者。"
                ),
                category="desktop-ops",
                status="active",
                version="v1",
                industry_tags=["general", "desktop"],
                team_modes=["industry", "operator"],
                dependency_capability_ids=[
                    "system:dispatch_query",
                    "mcp:desktop_windows",
                ],
                suggested_role_ids=[
                    EXECUTION_CORE_ROLE_ID,
                    "solution-lead",
                ],
                owner_role_id=EXECUTION_CORE_ROLE_ID,
                parameter_schema={
                    "fields": [
                        {
                            "id": "target_application",
                            "label": "目标应用",
                            "type": "string",
                            "required": True,
                            "default": "桌面应用",
                        },
                        {
                            "id": "recipient_name",
                            "label": "接收对象",
                            "type": "string",
                            "required": True,
                            "default": "目标联系人",
                        },
                        {
                            "id": "message_text",
                            "label": "消息内容",
                            "type": "string",
                            "required": True,
                            "default": "待发送消息",
                        },
                    ]
                },
                step_specs=[
                    {
                        "id": "desktop-control-brief",
                        "kind": "goal",
                        "execution_mode": "control",
                        "owner_role_id": EXECUTION_CORE_ROLE_ID,
                        "title": "{industry_label} 桌面外联简报",
                        "summary": (
                            "复核目标桌面动作，并为 {recipient_name} 确认最终消息内容。"
                        ),
                        "required_capability_ids": ["system:dispatch_query"],
                        "plan_steps": [
                            "确认目标应用、接收对象与消息内容。",
                            "判断是否需要由专业角色执行桌面动作。",
                            "返回简洁的受控执行简报。",
                        ],
                    },
                    {
                        "id": "desktop-leaf-action",
                        "kind": "goal",
                        "execution_mode": "leaf",
                        "owner_role_id": "solution-lead",
                        "title": "在 {target_application} 中准备桌面跟进动作",
                        "summary": (
                            "打开 {target_application}，聚焦 {recipient_name}，并准备待发送消息：{message_text}"
                        ),
                        "required_capability_ids": [
                            "system:dispatch_query",
                            "mcp:desktop_windows",
                        ],
                        "plan_steps": [
                            "启动或聚焦目标桌面应用。",
                            "定位目标接收对象的会话窗口。",
                            "准备待发送消息，等待受控发送确认。",
                        ],
                    },
                ],
                metadata={
                    "builtin": True,
                    "dependency_install_templates": {
                        "mcp:desktop_windows": ["desktop-windows"],
                    },
                },
                created_at=now,
                updated_at=now,
            ),
        ]
