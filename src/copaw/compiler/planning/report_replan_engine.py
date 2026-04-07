# -*- coding: utf-8 -*-
"""Translate report synthesis pressure into a stable formal replan decision."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import ReportReplanDecision, build_planning_shell_payload


_UUID_SUFFIX_RE = re.compile(
    r"^report-synthesis:needs-replan:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object | None) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            items.extend(_string_list(item))
            continue
        if (text := _string(item)) is not None:
            items.append(text)
    return items


def _dict_list(value: object | None) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [
        dict(item)
        for item in value
        if isinstance(item, Mapping)
    ]


def _mapping(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _unique_strings(*values: object | None) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        for text in _string_list(value):
            if text in seen:
                continue
            seen.add(text)
            items.append(text)
    return items


def _append_unique(items: list[str], *values: object | None) -> list[str]:
    return _unique_strings(items, *values)


def _latest_finding_report_ids(value: object | None) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return _unique_strings(
        [item.get("report_id") for item in value if isinstance(item, Mapping)],
    )


class _ReportReplanRawDecision(BaseModel):
    """Typed raw synthesis decision payload before promotion into formal fields."""

    model_config = ConfigDict(from_attributes=True)

    decision_id: str | None = None
    status: str | None = None
    decision_kind: str | None = None
    summary: str | None = None
    reason_ids: list[str] = Field(default_factory=list)
    source_report_ids: list[str] = Field(default_factory=list)
    topic_keys: list[str] = Field(default_factory=list)
    trigger_family: str | None = None
    trigger_families: list[str] = Field(default_factory=list)
    trigger_rule_ids: list[str] = Field(default_factory=list)
    affected_lane_ids: list[str] = Field(default_factory=list)
    affected_uncertainty_ids: list[str] = Field(default_factory=list)
    rationale: dict[str, Any] = Field(default_factory=dict)
    trigger_context: dict[str, Any] = Field(default_factory=dict)
    strategy_change_context: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_value(
        cls,
        value: object | None,
    ) -> _ReportReplanRawDecision | None:
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            return None
        return cls(
            decision_id=_string(value.get("decision_id")),
            status=_string(value.get("status")),
            decision_kind=_string(value.get("decision_kind")),
            summary=_string(value.get("summary")),
            reason_ids=_string_list(value.get("reason_ids")),
            source_report_ids=_string_list(value.get("source_report_ids")),
            topic_keys=_string_list(value.get("topic_keys")),
            trigger_family=_string(value.get("trigger_family")),
            trigger_families=_string_list(value.get("trigger_families")),
            trigger_rule_ids=_string_list(value.get("trigger_rule_ids")),
            affected_lane_ids=_string_list(value.get("affected_lane_ids")),
            affected_uncertainty_ids=_string_list(value.get("affected_uncertainty_ids")),
            rationale=_mapping(value.get("rationale")),
            trigger_context=_mapping(value.get("trigger_context")),
            strategy_change_context=_mapping(value.get("strategy_change_context")),
        )


class _ReportReplanSynthesisInput(BaseModel):
    """Typed boundary wrapper for report synthesis -> replan compilation."""

    model_config = ConfigDict(from_attributes=True)

    needs_replan: bool = False
    summary: str = ""
    replan_reasons: list[str] = Field(default_factory=list)
    replan_decision: _ReportReplanRawDecision | None = None
    replan_directives: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
    activation: dict[str, Any] = Field(default_factory=dict)
    strategy_change_context: dict[str, Any] = Field(default_factory=dict)
    latest_findings: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_value(
        cls,
        value: object | None,
    ) -> _ReportReplanSynthesisInput | None:
        if not isinstance(value, Mapping):
            return None
        return cls(
            needs_replan=bool(value.get("needs_replan")),
            summary=_string(value.get("summary")) or "",
            replan_reasons=_string_list(value.get("replan_reasons")),
            replan_decision=_ReportReplanRawDecision.from_value(value.get("replan_decision")),
            replan_directives=_dict_list(value.get("replan_directives")),
            recommended_actions=_dict_list(value.get("recommended_actions")),
            activation=_mapping(value.get("activation")),
            strategy_change_context=_mapping(value.get("strategy_change_context")),
            latest_findings=_dict_list(value.get("latest_findings")),
        )


def _first_summary(entries: Sequence[Mapping[str, Any]], *, fallback: str) -> str:
    for entry in entries:
        if (summary := _string(entry.get("summary"))) is not None:
            return summary
    return fallback


def _strategy_context(
    synthesis: _ReportReplanSynthesisInput,
    raw_decision: _ReportReplanRawDecision,
) -> dict[str, Any]:
    context = dict(raw_decision.strategy_change_context)
    context.update(dict(synthesis.strategy_change_context))
    return context


def _decision_summary(decision_kind: str, rationale: str) -> str:
    prefix = {
        "follow_up_backlog": "Follow-up backlog required",
        "cycle_rebalance": "Cycle rebalance required",
        "lane_reweight": "Lane reweight required",
        "strategy_review_required": "Strategy review required",
    }.get(decision_kind, "Replan decision required")
    return f"{prefix}: {rationale}"


def _normalize_decision_kind(value: object | None) -> str | None:
    text = _string(value)
    if text in {
        "clear",
        "follow_up_backlog",
        "cycle_rebalance",
        "lane_reweight",
        "strategy_review_required",
    }:
        return text
    return None


def _trigger_rule_ids(
    *,
    raw_decision: _ReportReplanRawDecision,
    context: Mapping[str, Any],
    strategy_change: Mapping[str, Any],
) -> list[str]:
    return _unique_strings(
        raw_decision.trigger_rule_ids,
        context.get("trigger_rule_ids"),
        [
            item.get("rule_id")
            for item in _dict_list(strategy_change.get("trigger_evidence"))
        ],
    )


def _trigger_context(
    *,
    raw_decision: _ReportReplanRawDecision,
    context: Mapping[str, Any],
    strategy_change: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(raw_decision.trigger_context)
    payload.update(_mapping(context.get("trigger_context")))
    trigger_families = _unique_strings(
        payload.get("trigger_families"),
        [strategy_change.get("trigger_family")],
    )
    if trigger_families:
        payload["trigger_families"] = trigger_families
    return payload


def _build_strategy_change_payload(
    *,
    decision_kind: str,
    trigger_family: str,
    rationale: str,
    trigger_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "decision_kind": decision_kind,
        "trigger_family": trigger_family,
        "rationale": rationale,
        "trigger_evidence": trigger_evidence,
    }


def _trigger_evidence_lane_ids(trigger_evidence: Sequence[Mapping[str, Any]]) -> list[str]:
    return _unique_strings(
        [item.get("lane_id") for item in trigger_evidence],
        [item.get("lane_ids") for item in trigger_evidence],
    )


def _trigger_evidence_uncertainty_ids(
    trigger_evidence: Sequence[Mapping[str, Any]],
    reason_ids: Sequence[str],
) -> list[str]:
    return _unique_strings(
        [item.get("uncertainty_id") for item in trigger_evidence],
        [item.get("uncertainty_ids") for item in trigger_evidence],
        [reason_id for reason_id in reason_ids if reason_id.startswith("uncertainty:")],
    )


def _promote_strategy_change_payload(
    strategy_change: Mapping[str, Any],
    *,
    trigger_rule_ids: Sequence[str],
    trigger_context: Mapping[str, Any],
    relation_projection: Mapping[str, list[str]],
) -> dict[str, Any]:
    payload = dict(strategy_change)
    if trigger_rule_ids:
        payload["trigger_rule_ids"] = list(trigger_rule_ids)
    if trigger_context:
        payload["trigger_context"] = dict(trigger_context)
    if relation_projection.get("relation_ids"):
        payload["affected_relation_ids"] = list(relation_projection["relation_ids"])
    if relation_projection.get("relation_kinds"):
        payload["affected_relation_kinds"] = list(relation_projection["relation_kinds"])
    if relation_projection.get("source_refs"):
        payload["relation_source_refs"] = list(relation_projection["source_refs"])
    return payload


def _relation_projection(
    activation: Mapping[str, Any],
    strategy_change: Mapping[str, Any] | None = None,
) -> dict[str, list[str]]:
    relation_evidence = _dict_list(activation.get("top_relation_evidence"))
    if isinstance(strategy_change, Mapping):
        relation_evidence.extend(_dict_list(strategy_change.get("relation_evidence")))
    return {
        "relation_ids": _unique_strings(
            [item.get("relation_id") for item in relation_evidence],
            *[item.get("affected_relation_ids") for item in relation_evidence],
        ),
        "relation_kinds": _unique_strings(
            [item.get("relation_kind") for item in relation_evidence],
            *[item.get("affected_relation_kinds") for item in relation_evidence],
        ),
        "source_refs": _unique_strings(
            *[item.get("source_refs") for item in relation_evidence],
            [item.get("source_ref") for item in relation_evidence],
        ),
    }


class ReportReplanEngine:
    """Compile report synthesis output into a typed replan surface."""

    @staticmethod
    def _planning_shell(decision: ReportReplanDecision) -> dict[str, str]:
        source_report_id = next(iter(decision.source_report_ids or []), "latest")
        decision_kind = _normalize_decision_kind(decision.decision_kind) or (
            "follow_up_backlog" if decision.status == "needs-replan" else "clear"
        )
        plan_id = decision.decision_id
        if _UUID_SUFFIX_RE.match(plan_id):
            plan_id = "report-synthesis:needs-replan"
        return build_planning_shell_payload(
            mode="report-replan-shell",
            scope="report-replan",
            plan_id=plan_id,
            resume_key=f"report:{source_report_id}",
            fork_key=f"decision:{decision_kind}",
            verify_reminder=(
                "Verify synthesis pressure before mutating backlog, cycle, lane, or strategy truth."
            ),
        )

    def compile(
        self,
        synthesis: Mapping[str, Any] | None,
    ) -> ReportReplanDecision:
        payload = _ReportReplanSynthesisInput.from_value(synthesis)
        if payload is None:
            return ReportReplanDecision()
        raw_decision = payload.replan_decision
        decision: ReportReplanDecision
        if raw_decision is not None:
            raw_decision_kind = _normalize_decision_kind(raw_decision.decision_kind)
            raw_trigger_family = raw_decision.trigger_family
            decision = ReportReplanDecision(
                decision_id=raw_decision.decision_id or "report-synthesis:clear",
                status=(
                    "needs-replan"
                    if raw_decision.status == "needs-replan"
                    else "clear"
                ),
                decision_kind=raw_decision_kind or "clear",
                summary=(
                    raw_decision.summary
                    or "No unresolved report synthesis pressure."
                ),
                reason_ids=list(raw_decision.reason_ids),
                source_report_ids=list(raw_decision.source_report_ids),
                topic_keys=list(raw_decision.topic_keys),
                strategy_change_decision=(
                    raw_decision_kind
                    if raw_decision_kind in {
                        "follow_up_backlog",
                        "cycle_rebalance",
                        "lane_reweight",
                        "strategy_review_required",
                    }
                    else None
                ),
                trigger_family=raw_trigger_family,
                trigger_families=_unique_strings(
                    raw_decision.trigger_families,
                    [raw_trigger_family] if raw_trigger_family is not None else [],
                ),
                trigger_rule_ids=list(raw_decision.trigger_rule_ids),
                affected_lane_ids=list(raw_decision.affected_lane_ids),
                affected_uncertainty_ids=list(raw_decision.affected_uncertainty_ids),
                directives=list(payload.replan_directives),
                recommended_actions=list(payload.recommended_actions),
                activation=dict(payload.activation),
                rationale=dict(raw_decision.rationale),
                trigger_context=dict(raw_decision.trigger_context),
            )
        elif payload.needs_replan:
            decision = ReportReplanDecision(
                decision_id="report-synthesis:needs-replan",
                status="needs-replan",
                decision_kind="follow_up_backlog",
                summary=(
                    payload.summary
                    or "Report synthesis still requires main-brain review."
                ),
                strategy_change_decision="follow_up_backlog",
                source_report_ids=_latest_finding_report_ids(payload.latest_findings),
                directives=list(payload.replan_directives),
                recommended_actions=list(payload.recommended_actions),
                activation=dict(payload.activation),
                trigger_context={},
            )
        else:
            return ReportReplanDecision()

        strategy_change = self._classify_strategy_change(
            synthesis=payload,
            raw_decision=raw_decision,
            decision=decision,
        )
        activation = dict(decision.activation)
        if strategy_change is not None:
            context = _strategy_context(payload, raw_decision or _ReportReplanRawDecision())
            trigger_rule_ids = _trigger_rule_ids(
                raw_decision=raw_decision or _ReportReplanRawDecision(),
                context=context,
                strategy_change=strategy_change,
            )
            trigger_context = _trigger_context(
                raw_decision=raw_decision or _ReportReplanRawDecision(),
                context=context,
                strategy_change=strategy_change,
            )
            relation_projection = _relation_projection(activation, strategy_change)
            promoted_strategy_change = _promote_strategy_change_payload(
                strategy_change,
                trigger_rule_ids=trigger_rule_ids,
                trigger_context=trigger_context,
                relation_projection=relation_projection,
            )
            activation["strategy_change"] = promoted_strategy_change
            summary = decision.summary
            if strategy_change["decision_kind"] != "follow_up_backlog":
                summary = _decision_summary(
                    str(strategy_change["decision_kind"]),
                    str(strategy_change["rationale"]),
                )
            decision = decision.model_copy(
                update={
                    "summary": summary,
                    "source_report_ids": _append_unique(
                        list(decision.source_report_ids),
                        _latest_finding_report_ids(payload.latest_findings),
                        *(
                            item.get("source_report_ids")
                            for item in strategy_change["trigger_evidence"]
                            if isinstance(item, Mapping)
                        ),
                    ),
                    "topic_keys": _append_unique(
                        list(decision.topic_keys),
                        [
                            _string(item.get("topic_key"))
                            or _string(item.get("objective_key"))
                            or _string(item.get("blocker_key"))
                            or _string(item.get("uncertainty_key"))
                            for item in strategy_change["trigger_evidence"]
                            if isinstance(item, Mapping)
                        ],
                    ),
                    "activation": activation,
                    "trigger_context": trigger_context,
                    "strategy_change": promoted_strategy_change,
                    "affected_relation_ids": relation_projection["relation_ids"],
                    "affected_relation_kinds": relation_projection["relation_kinds"],
                    "relation_source_refs": relation_projection["source_refs"],
                },
            )
        elif activation:
            decision = decision.model_copy(update={"activation": activation})

        strategy_change_payload = _mapping(activation.get("strategy_change"))
        trigger_evidence = _dict_list(strategy_change_payload.get("trigger_evidence"))
        typed_decision_kind = (
            _normalize_decision_kind(strategy_change_payload.get("decision_kind"))
            or _normalize_decision_kind(decision.decision_kind)
            or ("follow_up_backlog" if decision.status == "needs-replan" else "clear")
        )
        trigger_family = (
            _string(strategy_change_payload.get("trigger_family"))
            or _string(decision.trigger_family)
        )
        trigger_families = _unique_strings(
            decision.trigger_families,
            strategy_change_payload.get("trigger_families"),
            [trigger_family] if trigger_family is not None else [],
        )
        trigger_rule_ids = _unique_strings(
            decision.trigger_rule_ids,
            strategy_change_payload.get("trigger_rule_ids"),
        )
        relation_projection = _relation_projection(activation, strategy_change_payload)
        affected_lane_ids = _unique_strings(
            decision.affected_lane_ids,
            strategy_change_payload.get("affected_lane_ids"),
            _trigger_evidence_lane_ids(trigger_evidence),
            [item.get("lane_id") for item in decision.directives],
        )
        affected_uncertainty_ids = _unique_strings(
            decision.affected_uncertainty_ids,
            strategy_change_payload.get("affected_uncertainty_ids"),
            _trigger_evidence_uncertainty_ids(trigger_evidence, decision.reason_ids),
        )
        rationale = dict(decision.rationale)
        if strategy_change_payload:
            rationale["strategy_change"] = strategy_change_payload
        if raw_decision:
            rationale["raw_decision"] = raw_decision.model_dump(mode="json", exclude_none=True)
        decision = decision.model_copy(
            update={
                "decision_kind": typed_decision_kind,
                "strategy_change_decision": (
                    typed_decision_kind
                    if typed_decision_kind != "clear"
                    else None
                ),
                "trigger_family": trigger_family,
                "trigger_families": trigger_families,
                "trigger_rule_ids": trigger_rule_ids,
                "affected_lane_ids": affected_lane_ids,
                "affected_uncertainty_ids": affected_uncertainty_ids,
                "affected_relation_ids": relation_projection["relation_ids"],
                "affected_relation_kinds": relation_projection["relation_kinds"],
                "relation_source_refs": relation_projection["source_refs"],
                "rationale": rationale,
                "activation": activation,
                "trigger_context": _mapping(strategy_change_payload.get("trigger_context")),
                "strategy_change": dict(strategy_change_payload),
            },
        )
        return decision.model_copy(
            update={
                "planning_shell": self._planning_shell(decision),
            },
        )

    def compile_exception_absorption_replan(
        self,
        *,
        case_kind: str,
        scope_ref: str | None = None,
        owner_agent_id: str | None = None,
        summary: str | None = None,
    ) -> ReportReplanDecision:
        normalized_case_kind = _string(case_kind) or "internal-exception"
        rationale = _string(summary) or "Internal exception pressure requires main-brain replan."
        decision_kind = {
            "repeated-blocker-same-scope": "cycle_rebalance",
            "progressless-runtime": "cycle_rebalance",
            "retry-loop": "lane_reweight",
        }.get(normalized_case_kind, "follow_up_backlog")
        trigger_family = {
            "cycle_rebalance": "repeated_blocker_across_cycles",
            "lane_reweight": "repeated_assignment_miss_same_lane_objective",
        }.get(decision_kind, "local_follow_up_pressure")
        trigger_evidence = [
            {
                "blocker_key": normalized_case_kind,
                "scope_ref": _string(scope_ref),
                "owner_agent_id": _string(owner_agent_id),
                "summary": rationale,
            },
        ]
        strategy_change_context: dict[str, Any]
        if decision_kind == "cycle_rebalance":
            strategy_change_context = {"repeated_blockers": trigger_evidence}
        elif decision_kind == "lane_reweight":
            strategy_change_context = {"assignment_misses": trigger_evidence}
        else:
            strategy_change_context = {}
        return self.compile(
            {
                "needs_replan": True,
                "summary": rationale,
                "replan_reasons": [rationale],
                "replan_decision": {
                    "decision_id": f"report-synthesis:needs-replan:{normalized_case_kind}",
                    "status": "needs-replan",
                    "decision_kind": decision_kind,
                    "summary": rationale,
                    "reason_ids": [f"absorption:{normalized_case_kind}"],
                    "trigger_family": trigger_family,
                    "strategy_change_context": strategy_change_context,
                },
                "strategy_change_context": strategy_change_context,
            },
        )

    def _classify_strategy_change(
        self,
        *,
        synthesis: _ReportReplanSynthesisInput,
        raw_decision: _ReportReplanRawDecision | None,
        decision: ReportReplanDecision,
    ) -> dict[str, Any] | None:
        if decision.status != "needs-replan":
            return None
        context = _strategy_context(
            synthesis,
            raw_decision or _ReportReplanRawDecision(),
        )
        contradictions = _dict_list(
            context.get("evidence_contradictions") or context.get("repeated_contradictions"),
        )
        if contradictions:
            return _build_strategy_change_payload(
                decision_kind="strategy_review_required",
                trigger_family="repeated_evidence_contradiction",
                rationale=_first_summary(
                    contradictions,
                    fallback="Repeated contradiction across synthesis, activation, and report evidence requires strategy review.",
                ),
                trigger_evidence=contradictions,
            )
        activation = dict(synthesis.activation)
        contradiction_count = activation.get("contradiction_count")
        if isinstance(contradiction_count, int) and contradiction_count > 0:
            contradiction_sources = ["activation"]
            latest_findings = list(synthesis.latest_findings)
            report_ids = _append_unique(
                list(decision.source_report_ids),
                [item.get("report_id") for item in latest_findings],
            )
            if report_ids:
                contradiction_sources.append("report")
            if any(not reason_id.startswith("activation:") for reason_id in decision.reason_ids):
                contradiction_sources.insert(0, "synthesis")
            if len(contradiction_sources) >= 2:
                rationale = (
                    list(synthesis.replan_reasons)[0]
                    if synthesis.replan_reasons
                    else "Contradictory activation and report evidence requires strategy review."
                )
                return _build_strategy_change_payload(
                    decision_kind="strategy_review_required",
                    trigger_family="repeated_evidence_contradiction",
                    rationale=rationale,
                    trigger_evidence=[
                        {
                            "contradiction_count": contradiction_count,
                            "source_families": contradiction_sources,
                            "source_report_ids": report_ids,
                            "topic_keys": list(decision.topic_keys),
                            "summary": rationale,
                        },
                    ],
                )
        uncertainty_collapses = _dict_list(
            context.get("uncertainty_collapses") or context.get("confidence_collapses"),
        )
        if uncertainty_collapses:
            return _build_strategy_change_payload(
                decision_kind="strategy_review_required",
                trigger_family="confidence_collapse_tracked_uncertainty",
                rationale=_first_summary(
                    uncertainty_collapses,
                    fallback="Confidence collapsed on a tracked uncertainty and now requires strategy review.",
                ),
                trigger_evidence=uncertainty_collapses,
            )
        assignment_misses = _dict_list(
            context.get("assignment_misses") or context.get("repeated_assignment_misses"),
        )
        if assignment_misses:
            return _build_strategy_change_payload(
                decision_kind="lane_reweight",
                trigger_family="repeated_assignment_miss_same_lane_objective",
                rationale=_first_summary(
                    assignment_misses,
                    fallback="Repeated assignment misses against the same lane objective require lane reweight.",
                ),
                trigger_evidence=assignment_misses,
            )
        repeated_blockers = _dict_list(
            context.get("repeated_blockers") or context.get("blockers_across_cycles"),
        )
        if repeated_blockers:
            return _build_strategy_change_payload(
                decision_kind="cycle_rebalance",
                trigger_family="repeated_blocker_across_cycles",
                rationale=_first_summary(
                    repeated_blockers,
                    fallback="Repeated blocker pressure across cycles requires cycle rebalance.",
                ),
                trigger_evidence=repeated_blockers,
            )
        return _build_strategy_change_payload(
            decision_kind="follow_up_backlog",
            trigger_family="local_follow_up_pressure",
            rationale=decision.summary,
            trigger_evidence=[
                {
                    "reason_ids": list(decision.reason_ids),
                    "source_report_ids": list(decision.source_report_ids),
                    "topic_keys": list(decision.topic_keys),
                    "directive_ids": _unique_strings(
                        [item.get("directive_id") for item in decision.directives],
                    ),
                    "recommended_action_ids": _unique_strings(
                        [item.get("action_id") for item in decision.recommended_actions],
                    ),
                    "summary": decision.summary,
                },
            ],
        )
