from __future__ import annotations

from copaw.kernel.buddy_onboarding_reasoner import (
    BuddyOnboardingBacklogSeed,
    BuddyOnboardingGrowthPlan,
    BuddyOnboardingReasonedTurn,
)
from copaw.kernel.buddy_onboarding_service import (
    _CREATOR_DIRECTION,
    _HEALTH_DIRECTION,
    _STOCKS_DIRECTION,
)


class DeterministicBuddyReasoner:
    def plan_turn(
        self,
        *,
        profile,
        transcript,
        question_count: int,
        tightened: bool,
    ) -> BuddyOnboardingReasonedTurn:
        _ = tightened
        direction = self._resolve_direction(profile=profile, transcript=transcript)
        finished = question_count >= self._finish_after(profile=profile, transcript=transcript)
        return BuddyOnboardingReasonedTurn(
            finished=finished,
            next_question="" if finished else self._next_question(direction),
            candidate_directions=[direction],
            recommended_direction=direction,
        )

    def build_growth_plan(
        self,
        *,
        profile,
        transcript,
        selected_direction: str,
    ) -> BuddyOnboardingGrowthPlan:
        _ = (profile, transcript)
        direction = selected_direction.strip() or _CREATOR_DIRECTION
        final_goal, why_it_matters, backlog_items = self._growth_plan(direction)
        return BuddyOnboardingGrowthPlan(
            primary_direction=direction,
            final_goal=final_goal,
            why_it_matters=why_it_matters,
            backlog_items=backlog_items,
        )

    def _resolve_direction(self, *, profile, transcript) -> str:
        source = " ".join(
            str(item or "")
            for item in [
                profile.profession,
                profile.current_stage,
                profile.goal_intention,
                *list(profile.interests or []),
                *list(profile.strengths or []),
                *list(profile.constraints or []),
                *list(transcript or []),
            ]
        ).lower()
        if any(token in source for token in ("stock", "stocks", "trading", "trade", "invest", "股票", "交易", "投资", "炒股")):
            return _STOCKS_DIRECTION
        if any(token in source for token in ("health", "fitness", "workout", "健身", "健康", "减脂", "训练")):
            return _HEALTH_DIRECTION
        if any(token in source for token in ("writing", "writer", "content", "video", "creator", "小说", "写作", "内容", "视频", "创作", "ip")):
            return _CREATOR_DIRECTION
        return _CREATOR_DIRECTION

    def _next_question(self, direction: str) -> str:
        if direction == _STOCKS_DIRECTION:
            return "你更想先明确交易边界，还是先搭第一版复盘框架？"
        if direction == _HEALTH_DIRECTION:
            return "你更想先收饮食节奏，还是先把训练频率固定下来？"
        return "你更想先确定持续输出方向，还是先完成第一份可发布作品？"

    def _finish_after(self, *, profile, transcript) -> int:
        source = " ".join(
            str(item or "")
            for item in [
                profile.goal_intention,
                *list(transcript or []),
            ]
        ).lower()
        if any(token in source for token in ("lost", "confused", "迷茫", "不确定", "找方向")):
            return 3
        return 2

    def _growth_plan(
        self,
        direction: str,
    ) -> tuple[str, str, list[BuddyOnboardingBacklogSeed]]:
        if direction == _STOCKS_DIRECTION:
            return (
                "Build a disciplined stock trading system with real risk control and review evidence.",
                "Turn trading into a durable operating path with clear rules instead of impulse.",
                [
                    BuddyOnboardingBacklogSeed(
                        lane_hint="growth-focus",
                        title="Define trading boundaries",
                        summary="Lock the market scope, holding period, risk limit, and stop-loss rules.",
                        priority=3,
                        source_key="trading-boundary",
                    ),
                    BuddyOnboardingBacklogSeed(
                        lane_hint="proof-of-work",
                        title="Produce the first trade review",
                        summary="Finish one evidence-backed review of a real or simulated trade sample.",
                        priority=2,
                        source_key="trading-review",
                    ),
                ],
            )
        if direction == _HEALTH_DIRECTION:
            return (
                "Build a repeatable health routine with visible weekly evidence.",
                "Turn health from a wish into a durable weekly operating rhythm.",
                [
                    BuddyOnboardingBacklogSeed(
                        lane_hint="growth-focus",
                        title="Lock the weekly routine",
                        summary="Define the minimum viable meal and workout rhythm for the week.",
                        priority=3,
                        source_key="health-routine",
                    ),
                    BuddyOnboardingBacklogSeed(
                        lane_hint="proof-of-work",
                        title="Record the first weekly checkpoint",
                        summary="Capture a first weekly evidence checkpoint for training and recovery.",
                        priority=2,
                        source_key="health-checkpoint",
                    ),
                ],
            )
        return (
            "Build a durable writing and publishing path with visible proof-of-work.",
            "Turn expression into an accumulative path that can keep producing real artifacts.",
            [
                BuddyOnboardingBacklogSeed(
                    lane_hint="growth-focus",
                    title="Define the first publishing lane",
                    summary="Choose the topic, cadence, and minimum shippable unit for the first cycle.",
                    priority=3,
                    source_key="writing-direction",
                ),
                BuddyOnboardingBacklogSeed(
                    lane_hint="proof-of-work",
                    title="Ship the first publishable artifact",
                    summary="Finish the first chapter or draft and move it into a real publish-ready state.",
                    priority=2,
                    source_key="writing-first-artifact",
                ),
            ],
        )
