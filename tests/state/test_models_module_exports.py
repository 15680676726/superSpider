# -*- coding: utf-8 -*-
from __future__ import annotations


def test_assignment_record_reexports_from_state_models() -> None:
    from copaw.state.models import AssignmentRecord

    assert AssignmentRecord.__name__ == "AssignmentRecord"


def test_split_state_modules_export_expected_records() -> None:
    from copaw.state.models_agents_runtime import AgentRuntimeRecord
    from copaw.state.models_core import RiskLevel
    from copaw.state.models_goals_tasks import AssignmentRecord
    from copaw.state.models_governance import GovernanceControlRecord
    from copaw.state.models_industry import IndustryInstanceRecord
    from copaw.state.models_prediction import PredictionCaseRecord
    from copaw.state.models_reporting import ReportRecord
    from copaw.state.models_workflows import WorkflowTemplateRecord

    assert AgentRuntimeRecord.__name__ == "AgentRuntimeRecord"
    assert AssignmentRecord.__name__ == "AssignmentRecord"
    assert GovernanceControlRecord.__name__ == "GovernanceControlRecord"
    assert IndustryInstanceRecord.__name__ == "IndustryInstanceRecord"
    assert PredictionCaseRecord.__name__ == "PredictionCaseRecord"
    assert ReportRecord.__name__ == "ReportRecord"
    assert WorkflowTemplateRecord.__name__ == "WorkflowTemplateRecord"
    assert "auto" in RiskLevel.__args__


def test_state_package_keeps_compatibility_exports_after_split() -> None:
    from copaw.state import AssignmentRecord, WorkflowTemplateRecord

    assert AssignmentRecord.__name__ == "AssignmentRecord"
    assert WorkflowTemplateRecord.__name__ == "WorkflowTemplateRecord"
