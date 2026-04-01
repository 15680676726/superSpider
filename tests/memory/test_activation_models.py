# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.memory.activation_models import ActivationInput, ActivationResult, KnowledgeNeuron


def test_knowledge_neuron_defaults_and_required_fields() -> None:
    neuron = KnowledgeNeuron(
        neuron_id="entity:industry-1:outbound",
        kind="entity",
        scope_type="industry",
        scope_id="industry-1",
        title="Outbound",
    )

    assert neuron.kind == "entity"
    assert neuron.activation_score == 0.0
    assert neuron.entity_keys == []


def test_activation_input_accepts_runtime_scope_signals() -> None:
    payload = ActivationInput(
        query_text="review outbound execution failure",
        work_context_id="ctx-1",
        task_id="task-1",
        capability_ref="tool:execute_shell_command",
    )

    assert payload.work_context_id == "ctx-1"
    assert payload.limit == 12


def test_activation_result_can_hold_neurons_and_support_refs() -> None:
    result = ActivationResult(
        query="review outbound execution failure",
        scope_type="work_context",
        scope_id="ctx-1",
    )

    assert result.activated_neurons == []
    assert result.support_refs == []
