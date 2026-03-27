# -*- coding: utf-8 -*-
from __future__ import annotations

from ..state import FixedSopTemplateRecord


def builtin_fixed_sop_templates() -> list[FixedSopTemplateRecord]:
    return [
        FixedSopTemplateRecord(
            template_id="fixed-sop-webhook-writeback",
            name="Webhook Intake Writeback",
            summary="Receive a webhook, run a low-judgment guard, and write the result back into the main chain.",
            source_kind="builtin",
            owner_role_id="execution-core",
            suggested_role_ids=["execution-core"],
            industry_tags=["automation", "intake"],
            capability_tags=["writeback"],
            node_graph=[
                {"node_id": "trigger-webhook", "kind": "trigger"},
                {"node_id": "guard-payload", "kind": "guard"},
                {"node_id": "writeback-summary", "kind": "writeback"},
            ],
        ),
        FixedSopTemplateRecord(
            template_id="fixed-sop-http-routine-bridge",
            name="HTTP to Routine Bridge",
            summary="Call an API, dispatch a UI routine when needed, wait for the callback, then normalize output.",
            source_kind="builtin",
            owner_role_id="execution-core",
            suggested_role_ids=["execution-core"],
            industry_tags=["automation", "bridge"],
            capability_tags=["http", "routine"],
            node_graph=[
                {"node_id": "trigger-manual", "kind": "trigger"},
                {"node_id": "fetch-http", "kind": "http_request"},
                {"node_id": "call-capability", "kind": "capability_call"},
                {"node_id": "call-routine", "kind": "routine_call"},
                {"node_id": "wait-callback", "kind": "wait_callback"},
                {"node_id": "writeback-result", "kind": "writeback"},
            ],
        ),
    ]
