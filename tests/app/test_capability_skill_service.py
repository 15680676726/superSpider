from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import frontmatter
import pytest
from fastapi.testclient import TestClient

from copaw.capabilities import CapabilityMount, CapabilityService, CapabilityRegistry
from copaw.capabilities.remote_skill_contract import RemoteSkillCandidate
from copaw.capabilities.skill_service import CapabilitySkillService
from copaw.capabilities.system_skill_handlers import SystemSkillCapabilityFacade
from copaw.evidence.models import EvidenceRecord
from copaw.state import (
    AgentProfileOverrideRecord,
    PredictionCaseRecord,
    PredictionRecommendationRecord,
    TaskRecord,
    TaskRuntimeRecord,
)
from tests.app.test_predictions_api import (
    _build_predictions_app,
    _create_prediction_case,
    _execute_prediction_recommendation_direct,
)


class _StaticRegistry(CapabilityRegistry):
    def __init__(self, mounts: list[CapabilityMount]) -> None:
        self._mounts = mounts

    def list_capabilities(self) -> list[CapabilityMount]:
        return list(self._mounts)


class _FakeSkillService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def list_all_skills(self) -> list[object]:
        return [
            SimpleNamespace(
                name="research",
                content="# research",
                source="customized",
                path="/tmp/research",
                references={},
                scripts={},
            ),
        ]

    def list_available_skill_names(self) -> list[str]:
        return ["research"]

    def list_available_skills(self) -> list[object]:
        return self.list_all_skills()

    def find_skill(self, skill_name: str) -> object | None:
        for skill in self.list_all_skills():
            if skill.name == skill_name:
                return skill
        return None

    def read_skill_package_binding(self, skill: object) -> dict[str, str | None]:
        _ = skill
        return {
            "package_ref": None,
            "package_kind": None,
            "package_version": None,
        }

    def enable_skill(self, skill_name: str) -> None:
        self.calls.append(("enable", skill_name))

    def disable_skill(self, skill_name: str) -> None:
        self.calls.append(("disable", skill_name))

    def delete_skill(self, skill_name: str) -> bool:
        self.calls.append(("delete", skill_name))
        return True

    def create_skill(self, **kwargs: object) -> object:
        self.calls.append(("create", kwargs))
        return True

    def install_skill_from_hub(self, **kwargs: object) -> object:
        self.calls.append(("install", kwargs))
        return SimpleNamespace(
            name="research",
            enabled=True,
            source_url="https://example.com/research",
        )

    def load_skill_file(
        self,
        *,
        skill_name: str,
        file_path: str,
        source: str,
    ) -> str | None:
        self.calls.append(("load_file", (skill_name, file_path, source)))
        return "file-body"

    def sync_to_working_dir(
        self,
        *,
        skill_names: list[str] | None = None,
        force: bool = False,
    ) -> tuple[int, int]:
        self.calls.append(("sync", (skill_names, force)))
        return (1, 0)


def test_capability_service_skill_service_handles_skill_toggle_and_delete() -> None:
    skill_service = _FakeSkillService()
    service = CapabilityService(
        registry=_StaticRegistry(
            [
                CapabilityMount(
                    id="skill:research",
                    name="research",
                    summary="Research skill",
                    kind="skill-bundle",
                    source_kind="skill",
                    risk_level="guarded",
                    enabled=True,
                ),
            ],
        ),
        skill_service=skill_service,
    )

    toggle_result = service.set_capability_enabled("skill:research", enabled=False)
    delete_result = service.delete_capability("skill:research")

    assert toggle_result["enabled"] is False
    assert delete_result["deleted"] is True
    assert ("disable", "research") in skill_service.calls
    assert ("delete", "research") in skill_service.calls


def test_capability_service_skill_service_handles_file_load_and_sync() -> None:
    skill_service = _FakeSkillService()
    service = CapabilityService(skill_service=skill_service)

    content = service.load_skill_file(
        skill_name="research",
        file_path="references/brief.md",
        source="customized",
    )
    sync_result = service.sync_skills_to_working_dir(skill_names=["research"])

    assert content == "file-body"
    assert sync_result == (1, 0)
    assert ("load_file", ("research", "references/brief.md", "customized")) in skill_service.calls
    assert ("sync", (["research"], False)) in skill_service.calls


def test_capability_service_get_capability_reads_injected_skill_service() -> None:
    skill_service = _FakeSkillService()
    service = CapabilityService(skill_service=skill_service)

    mount = service.get_capability("skill:research")

    assert mount is not None
    assert mount.id == "skill:research"
    assert mount.enabled is True


def test_capability_skill_service_install_hub_skill_persists_package_binding(
    monkeypatch,
    tmp_path,
) -> None:
    skill_dir = tmp_path / "research"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: research
description: Research skill
---
# Research
""",
        encoding="utf-8",
    )
    skill = SimpleNamespace(
        name="research",
        content=skill_md.read_text(encoding="utf-8"),
        source="customized",
        path=str(skill_dir),
        references={},
        scripts={},
    )

    monkeypatch.setattr(
        "copaw.capabilities.skill_service.install_skill_from_hub",
        lambda **_kwargs: SimpleNamespace(
            name="research",
            enabled=True,
            source_url="https://example.com/research-pack.zip",
        ),
    )

    service = CapabilitySkillService()
    monkeypatch.setattr(
        service,
        "find_skill",
        lambda skill_name: skill if skill_name == "research" else None,
    )

    result = service.install_skill_from_hub(
        bundle_url="https://example.com/research-pack.zip",
        version="1.2.3",
        enable=True,
    )
    updated = skill_md.read_text(encoding="utf-8")

    assert getattr(result, "source_url") == "https://example.com/research-pack.zip"
    assert "package_ref: https://example.com/research-pack.zip" in updated
    assert "package_kind: hub-bundle" in updated
    assert "package_version: 1.2.3" in updated


def test_capability_skill_service_install_hub_skill_persists_upgrade_lifecycle_metadata(
    monkeypatch,
    tmp_path,
) -> None:
    skill_dir = tmp_path / "research"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: research
description: Research skill
---
# Research
""",
        encoding="utf-8",
    )
    skill = SimpleNamespace(
        name="research",
        content=skill_md.read_text(encoding="utf-8"),
        source="customized",
        path=str(skill_dir),
        references={},
        scripts={},
    )

    monkeypatch.setattr(
        "copaw.capabilities.skill_service.install_skill_from_hub",
        lambda **_kwargs: SimpleNamespace(
            name="research",
            enabled=True,
            source_url="https://example.com/research-pack.zip",
        ),
    )

    service = CapabilitySkillService()
    monkeypatch.setattr(
        service,
        "find_skill",
        lambda skill_name: skill if skill_name == "research" else None,
    )

    result = service.install_skill_from_hub(
        bundle_url="https://example.com/research-pack.zip",
        version="1.2.3",
        enable=True,
        lifecycle_stage="trial",
        next_lifecycle_stage="rollout",
        replacement_target_ids=["skill:legacy_research"],
        rollback_target_ids=["skill:legacy_research"],
        target_agent_id="industry-solution-lead-demo",
        target_role_id="solution-lead",
        target_seat_ref="env-browser-primary",
        rollout_scope="single-seat",
        role_budget_limit=12,
        seat_budget_limit=4,
    )
    updated = frontmatter.loads(skill_md.read_text(encoding="utf-8"))

    assert updated["lifecycle_stage"] == "trial"
    assert updated["next_lifecycle_stage"] == "rollout"
    assert updated["replacement_target_ids"] == ["skill:legacy_research"]
    assert updated["rollback_target_ids"] == ["skill:legacy_research"]
    assert updated["target_agent_id"] == "industry-solution-lead-demo"
    assert updated["target_role_id"] == "solution-lead"
    assert updated["target_seat_ref"] == "env-browser-primary"
    assert updated["rollout_scope"] == "single-seat"
    assert updated["role_budget_limit"] == 12
    assert updated["seat_budget_limit"] == 4
    assert getattr(result, "lifecycle_stage") == "trial"
    assert getattr(result, "target_seat_ref") == "env-browser-primary"


def test_capability_skill_service_install_hub_skill_tolerates_missing_local_skill_binding_target(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "copaw.capabilities.skill_service.install_skill_from_hub",
        lambda **_kwargs: SimpleNamespace(
            name="research",
            enabled=True,
            source_url="https://example.com/research-pack.zip",
        ),
    )

    service = CapabilitySkillService()
    monkeypatch.setattr(service, "find_skill", lambda _skill_name: None)

    result = service.install_skill_from_hub(
        bundle_url="https://example.com/research-pack.zip",
        version="1.2.3",
        enable=True,
    )

    assert getattr(result, "name") == "research"
    assert getattr(result, "source_url") == "https://example.com/research-pack.zip"


def test_capability_skill_service_materializes_local_fallback_only_when_resolver_requires_it(
    monkeypatch,
    tmp_path,
) -> None:
    builtin_dir = tmp_path / "builtin"
    customized_dir = tmp_path / "customized"
    active_dir = tmp_path / "active"
    builtin_dir.mkdir()
    customized_dir.mkdir()
    active_dir.mkdir()
    monkeypatch.setattr("copaw.skill_service.get_builtin_skills_dir", lambda: builtin_dir)
    monkeypatch.setattr("copaw.skill_service.get_customized_skills_dir", lambda: customized_dir)
    monkeypatch.setattr("copaw.skill_service.get_active_skills_dir", lambda: active_dir)

    service = CapabilitySkillService(
        skill_evolution_service=SimpleNamespace(
            resolve_candidate_path=lambda **_kwargs: {
                "resolution_kind": "author_local_fallback",
                "fallback_required": True,
                "package_form": "skill",
            },
        ),
    )

    result = service.materialize_fallback_skill_artifact(
        candidate_kind="skill",
        candidate_source_kind="local_authored",
        candidate_source_ref="local://industry/private-gap",
        candidate_source_version="draft-v1",
        skill_name="private_gap",
        content="---\nname: private_gap\ndescription: Private gap\n---\n# Private gap\n",
    )

    assert result["created"] is True
    assert result["resolution_kind"] == "author_local_fallback"
    assert (customized_dir / "private_gap" / "SKILL.md").exists()


def test_capability_skill_service_skips_local_fallback_when_reuse_resolution_exists(
    monkeypatch,
    tmp_path,
) -> None:
    builtin_dir = tmp_path / "builtin"
    customized_dir = tmp_path / "customized"
    active_dir = tmp_path / "active"
    builtin_dir.mkdir()
    customized_dir.mkdir()
    active_dir.mkdir()
    monkeypatch.setattr("copaw.skill_service.get_builtin_skills_dir", lambda: builtin_dir)
    monkeypatch.setattr("copaw.skill_service.get_customized_skills_dir", lambda: customized_dir)
    monkeypatch.setattr("copaw.skill_service.get_active_skills_dir", lambda: active_dir)

    service = CapabilitySkillService(
        skill_evolution_service=SimpleNamespace(
            resolve_candidate_path=lambda **_kwargs: {
                "resolution_kind": "reuse_existing_candidate",
                "fallback_required": False,
                "selected_candidate_id": "cand-reuse",
                "package_form": "mcp-bundle",
            },
        ),
    )

    result = service.materialize_fallback_skill_artifact(
        candidate_kind="mcp-bundle",
        candidate_source_kind="external_catalog",
        candidate_source_ref="registry://browser-runtime",
        candidate_source_version="2026.04.04",
        skill_name="should_not_exist",
        content="---\nname: should_not_exist\ndescription: no-op\n---\n# no-op\n",
    )

    assert result["created"] is False
    assert result["resolution_kind"] == "reuse_existing_candidate"
    assert not (customized_dir / "should_not_exist").exists()


@pytest.mark.asyncio
async def test_system_trial_remote_skill_assignment_attaches_candidate_to_selected_seat_scope_without_apply_role() -> None:
    class _FakeSkillService:
        @staticmethod
        def install_skill_from_hub(**_kwargs: object) -> object:
            return SimpleNamespace(
                name="nextgen_outreach",
                enabled=True,
                source_url="https://example.com/nextgen-outreach.zip",
            )

    class _FakeAgentProfileService:
        @staticmethod
        def get_agent_detail(_agent_id: str) -> dict[str, object]:
            return {
                "runtime": {
                    "industry_role_id": "solution-lead",
                    "metadata": {
                        "selected_seat_ref": "env-browser-primary",
                        "capability_layers": {
                            "schema_version": "industry-seat-capability-layers-v1",
                            "role_prototype_capability_ids": ["tool:read_file"],
                            "seat_instance_capability_ids": ["skill:legacy_outreach"],
                            "cycle_delta_capability_ids": [],
                            "session_overlay_capability_ids": [],
                        },
                    },
                },
            }

        @staticmethod
        def get_capability_surface(_agent_id: str) -> dict[str, object]:
            return {
                "baseline_capabilities": ["tool:read_file"],
                "effective_capabilities": [
                    "tool:read_file",
                    "skill:legacy_outreach",
                ],
            }

    apply_calls: list[dict[str, object]] = []
    attach_calls: list[dict[str, object]] = []

    async def _attach_trial(**payload: object) -> dict[str, object]:
        attach_calls.append(dict(payload))
        return {
            "success": True,
            "trial_id": "trial-nextgen-seat-1",
            "selected_scope": "seat",
            "scope_type": "seat",
            "scope_ref": "env-browser-primary",
            "attached_capability_ids": ["skill:nextgen_outreach"],
        }

    async def _apply_role(payload: dict[str, object]) -> dict[str, object]:
        apply_calls.append(dict(payload))
        return {"success": True}

    facade = SystemSkillCapabilityFacade(
        skill_service=_FakeSkillService(),
        get_capability_fn=lambda capability_id: CapabilityMount(
            id=capability_id,
            name=capability_id,
            summary=f"Mount for {capability_id}",
            kind="skill-bundle",
            source_kind="skill" if capability_id.startswith("skill:") else "tool",
            risk_level="guarded",
        ),
        agent_profile_service=_FakeAgentProfileService(),
        apply_role_handler=_apply_role,
        trial_scope_handler=_attach_trial,
    )

    result = await facade.handle_trial_remote_skill_assignment(
        {
            "candidate": {
                "candidate_key": "hub:nextgen-outreach",
                "source_kind": "hub",
                "source_label": "SkillHub",
                "title": "NextGen Outreach",
                "description": "Guarded outreach skill",
                "bundle_url": "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/nextgen-outreach.zip",
                "source_url": "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/nextgen-outreach.zip",
                "version": "1.0.0",
                "install_name": "nextgen_outreach",
                "capability_ids": ["skill:nextgen_outreach"],
                "review_required": False,
            },
            "candidate_id": "candidate-nextgen-outreach",
            "target_agent_id": "industry-solution-lead-demo",
            "capability_ids": ["skill:nextgen_outreach"],
            "replacement_capability_ids": ["skill:legacy_outreach"],
            "capability_assignment_mode": "replace",
            "selected_seat_ref": "env-browser-primary",
            "trial_scope": "single-seat",
            "target_role_id": "solution-lead",
        },
    )

    assert result["success"] is True
    assert result["trial_attachment"]["trial_id"] == "trial-nextgen-seat-1"
    assert result["trial_attachment"]["selected_scope"] == "seat"
    assert result["trial_attachment"]["scope_ref"] == "env-browser-primary"
    assert attach_calls[0]["candidate_id"] == "candidate-nextgen-outreach"
    assert attach_calls[0]["selected_scope"] == "seat"
    assert attach_calls[0]["scope_ref"] == "env-browser-primary"
    assert attach_calls[0]["target_role_id"] == "solution-lead"
    assert apply_calls == []


def test_capability_skill_service_bind_skill_package_metadata_canonicalizes_filesystem_binding(
    monkeypatch,
    tmp_path,
) -> None:
    skill_dir = tmp_path / "skills" / "research"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: research
description: Research skill
---
# Research
""",
        encoding="utf-8",
    )
    skill = SimpleNamespace(
        name="research",
        content=skill_md.read_text(encoding="utf-8"),
        source="customized",
        path=str(skill_dir),
        references={},
        scripts={},
    )
    non_canonical_ref = str(skill_dir.parent / "nested" / ".." / "research")

    service = CapabilitySkillService()
    monkeypatch.setattr(
        service,
        "find_skill",
        lambda skill_name: skill if skill_name == "research" else None,
    )

    assert (
        service.bind_skill_package_metadata(
            skill_name="research",
            package_ref=non_canonical_ref,
            package_kind=" Filesystem ",
            package_version=" 2026.04 ",
        )
        is True
    )

    updated = frontmatter.loads(skill_md.read_text(encoding="utf-8"))

    assert updated["package_ref"] == str(Path(non_canonical_ref).resolve())
    assert updated["package_kind"] == "filesystem"
    assert str(updated["package_version"]) == "2026.04"


def test_capability_skill_service_read_skill_package_binding_rejects_invalid_frontmatter() -> None:
    service = CapabilitySkillService()
    skill = SimpleNamespace(
        name="broken",
        content="---\nname: [broken\n---\n# Broken\n",
        source="customized",
        path="/tmp/broken",
        references={},
        scripts={},
    )

    try:
        service.read_skill_package_binding(skill)
    except ValueError as exc:
        assert "front matter" in str(exc).lower() or "frontmatter" in str(exc).lower()
    else:
        raise AssertionError("Expected invalid frontmatter to be rejected")


def test_capability_skill_service_bind_skill_package_metadata_rejects_duplicate_identity(
    monkeypatch,
    tmp_path,
) -> None:
    target_dir = tmp_path / "skills" / "target"
    target_dir.mkdir(parents=True)
    target_md = target_dir / "SKILL.md"
    target_md.write_text(
        """---
name: target
description: Target skill
---
# Target
""",
        encoding="utf-8",
    )
    existing_dir = tmp_path / "skills" / "existing"
    existing_dir.mkdir(parents=True)
    existing_md = existing_dir / "SKILL.md"
    existing_md.write_text(
        """---
name: existing
description: Existing skill
package_ref: https://github.com/acme/skills/tree/main/research
package_kind: hub-bundle
package_version: 1.0.0
---
# Existing
""",
        encoding="utf-8",
    )
    target_skill = SimpleNamespace(
        name="target",
        content=target_md.read_text(encoding="utf-8"),
        source="customized",
        path=str(target_dir),
        references={},
        scripts={},
    )
    existing_skill = SimpleNamespace(
        name="existing",
        content=existing_md.read_text(encoding="utf-8"),
        source="customized",
        path=str(existing_dir),
        references={},
        scripts={},
    )
    service = CapabilitySkillService()
    monkeypatch.setattr(
        service,
        "find_skill",
        lambda skill_name: target_skill if skill_name == "target" else None,
    )
    monkeypatch.setattr(
        service,
        "list_all_skills",
        lambda: [target_skill, existing_skill],
    )

    assert (
        service.bind_skill_package_metadata(
            skill_name="target",
            package_ref="https://github.com/acme/skills/tree/main/research",
            package_kind="hub-bundle",
            package_version="1.0.0",
        )
        is False
    )


def test_capability_service_list_skill_specs_suppresses_duplicate_package_identity() -> None:
    class _ScopedDuplicateSkillService:
        def list_all_skills(self) -> list[object]:
            content = """---
name: research_enabled
description: Research skill
package_ref: https://example.com/skills/research-pack.zip
package_kind: hub-bundle
package_version: 1.2.3
target_scope: seat
target_role_id: researcher
target_seat_ref: seat-1
---
# Research
"""
            duplicate_content = content.replace(
                "research_enabled",
                "research_duplicate",
            )
            return [
                SimpleNamespace(
                    name="research_enabled",
                    content=content,
                    source="customized",
                    path="/tmp/research_enabled",
                    references={},
                    scripts={},
                ),
                SimpleNamespace(
                    name="research_duplicate",
                    content=duplicate_content,
                    source="customized",
                    path="/tmp/research_duplicate",
                    references={},
                    scripts={},
                ),
            ]

        def list_available_skill_names(self) -> list[str]:
            return ["research_enabled"]

        def read_skill_package_binding(self, skill: object) -> dict[str, str | None]:
            _ = skill
            return {
                "package_ref": "https://example.com/skills/research-pack.zip",
                "package_kind": "hub-bundle",
                "package_version": "1.2.3",
            }

    service = CapabilityService(
        registry=_StaticRegistry(
            [
                CapabilityMount(
                    id="skill:research_enabled",
                    name="research_enabled",
                    summary="Research skill",
                    kind="skill-bundle",
                    source_kind="skill",
                    risk_level="guarded",
                    enabled=True,
                    package_ref="https://example.com/skills/research-pack.zip",
                    package_kind="hub-bundle",
                    package_version="1.2.3",
                ),
                CapabilityMount(
                    id="skill:research_duplicate",
                    name="research_duplicate",
                    summary="Duplicate research skill",
                    kind="skill-bundle",
                    source_kind="skill",
                    risk_level="guarded",
                    enabled=False,
                    package_ref="https://example.com/skills/research-pack.zip",
                    package_kind="hub-bundle",
                    package_version="1.2.3",
                ),
            ],
        ),
        skill_service=_ScopedDuplicateSkillService(),
    )

    specs = service.list_skill_specs()

    assert len(specs) == 1
    assert specs[0]["name"] == "research_enabled"
    assert specs[0]["enabled"] is True
    assert specs[0]["metadata_summary"]["activation_scope_key"] == "seat:researcher:seat-1"
    assert specs[0]["metadata_summary"]["path_scoped_activation"] is True


def test_capability_skill_service_read_binding_rejects_invalid_frontmatter() -> None:
    service = CapabilitySkillService()
    skill = SimpleNamespace(
        name="broken",
        content="---\nname: broken\n: broken\n---\nbody\n",
        source="customized",
        path="/tmp/broken",
        references={},
        scripts={},
    )

    with pytest.raises(ValueError, match="Front Matter|front matter|description"):
        service.read_skill_package_binding(skill)


def test_capability_skill_service_read_skill_package_binding_reanchors_filesystem_identity(
    tmp_path,
) -> None:
    skill_dir = tmp_path / "skills" / "research"
    skill_dir.mkdir(parents=True)
    escaped_ref = str(tmp_path / "other-skill")
    skill = SimpleNamespace(
        name="research",
        content=(
            "---\n"
            "name: research\n"
            "description: Research skill\n"
            f"package_ref: {escaped_ref}\n"
            "package_kind: filesystem\n"
            "package_version: 2026.04\n"
            "---\n"
            "# Research\n"
        ),
        source="customized",
        path=str(skill_dir),
        references={},
        scripts={},
    )

    binding = CapabilitySkillService().read_skill_package_binding(skill)

    assert binding == {
        "package_ref": str(skill_dir.resolve()),
        "package_kind": "filesystem",
        "package_version": "2026.04",
    }


def _patch_prediction_runtime_detail(
    monkeypatch,
    app,
    *,
    seat_refs: dict[str, str],
    seat_capability_ids: dict[str, list[str]],
) -> None:
    profile_service = app.state.agent_profile_service
    original = profile_service.get_agent_detail

    def _patched(agent_id: str):
        detail = original(agent_id) or {"runtime": None}
        payload = dict(detail)
        runtime = dict(payload.get("runtime") or {})
        metadata = dict(runtime.get("metadata") or {})
        seat_ref = seat_refs.get(agent_id)
        if seat_ref is not None:
            metadata["selected_seat_ref"] = seat_ref
        metadata["capability_layers"] = {
            "schema_version": "industry-seat-capability-layers-v1",
            "role_prototype_capability_ids": ["tool:read_file"],
            "seat_instance_capability_ids": list(seat_capability_ids.get(agent_id, [])),
            "cycle_delta_capability_ids": [],
            "session_overlay_capability_ids": [],
        }
        runtime["industry_role_id"] = runtime.get("industry_role_id") or "solution-lead"
        runtime["metadata"] = metadata
        payload["runtime"] = runtime
        return payload

    monkeypatch.setattr(profile_service, "get_agent_detail", _patched)


def test_prediction_service_rollout_recommendation_uses_single_seat_trial_metadata(
    tmp_path,
    monkeypatch,
) -> None:
    app = _build_predictions_app(
        tmp_path,
        enable_remote_curated_search=True,
    )
    client = TestClient(app)
    capability_service = app.state.capability_service
    skill_service = capability_service._skill_service
    skill_service.create_skill(
        name="legacy_outreach",
        content=(
            "---\n"
            "name: legacy_outreach\n"
            "description: Legacy outreach skill\n"
            "---\n"
            "Legacy outreach skill"
        ),
        overwrite=True,
    )
    skill_service.enable_skill("legacy_outreach")
    app.state.agent_profile_override_repository.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="industry-solution-lead-demo",
            name="Solution Lead",
            role_name="Solution Lead",
            role_summary="Own guarded outreach execution and follow-up.",
            industry_instance_id="industry-demo",
            industry_role_id="solution-lead",
            capabilities=["skill:legacy_outreach"],
            reason="seed legacy capability",
        ),
    )
    app.state.agent_profile_override_repository.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="industry-ops-demo",
            name="Ops Seat",
            role_name="Ops Seat",
            role_summary="Runs the second outreach seat.",
            industry_instance_id="industry-demo",
            industry_role_id="solution-lead",
            capabilities=["skill:legacy_outreach"],
            reason="seed legacy capability on second seat",
        ),
    )
    _patch_prediction_runtime_detail(
        monkeypatch,
        app,
        seat_refs={
            "industry-solution-lead-demo": "env-browser-primary",
            "industry-ops-demo": "env-browser-secondary",
        },
        seat_capability_ids={
            "industry-solution-lead-demo": ["skill:legacy_outreach"],
            "industry-ops-demo": ["skill:legacy_outreach"],
        },
    )
    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-legacy-outreach-1",
            title="Legacy outreach run failed",
            summary="Desktop outreach failed and needed operator takeover.",
            task_type="execution",
            status="failed",
            owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-legacy-outreach-1",
            runtime_status="terminated",
            current_phase="failed",
            risk_level="guarded",
            last_result_summary="Legacy outreach stalled.",
            last_error_summary="Operator had to intervene.",
            last_owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id="task-legacy-outreach-1",
            actor_ref="industry-solution-lead-demo",
            capability_ref="skill:legacy_outreach",
            risk_level="guarded",
            action_summary="legacy outreach run",
            result_summary="failed and required operator takeover",
        ),
    )

    def _fake_search(_query: str, **_kwargs):
        return [
            RemoteSkillCandidate(
                candidate_key="hub:nextgen-outreach",
                source_kind="hub",
                source_label="SkillHub",
                title="NextGen Outreach",
                description="A remote outreach skill optimized for guarded desktop follow-up.",
                bundle_url=(
                    "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/"
                    "skills/nextgen-outreach.zip"
                ),
                source_url=(
                    "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/"
                    "skills/nextgen-outreach.zip"
                ),
                slug="nextgen-outreach",
                version="1.0.0",
                install_name="nextgen_outreach",
                capability_ids=["skill:nextgen_outreach"],
                capability_tags=["skill", "remote"],
                review_required=False,
                search_query=_query,
            ),
        ]

    monkeypatch.setattr(
        "copaw.predictions.service.search_allowlisted_remote_skill_candidates",
        _fake_search,
    )

    def _fake_install_skill_from_hub(
        *,
        bundle_url: str,
        version: str = "",
        enable: bool = True,
        overwrite: bool = False,
    ):
        _ = version, overwrite
        skill_service.create_skill(
            name="nextgen_outreach",
            content=(
                "---\n"
                "name: nextgen_outreach\n"
                "description: NextGen outreach skill\n"
                "---\n"
                f"Installed from {bundle_url}"
            ),
            overwrite=True,
        )
        if enable:
            skill_service.enable_skill("nextgen_outreach")
        return SimpleNamespace(
            name="nextgen_outreach",
            enabled=enable,
            source_url=bundle_url,
        )

    capability_service._system_handler._skills._skill_service.install_skill_from_hub = (
        _fake_install_skill_from_hub
    )

    created = _create_prediction_case(client)
    case_id = created["case"]["case_id"]
    trial_recommendation = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["metadata"].get("gap_kind")
        == "underperforming_capability"
    )
    trial_metadata = trial_recommendation["recommendation"]["metadata"]

    assert trial_metadata["lifecycle_stage"] == "candidate"
    assert trial_metadata["next_lifecycle_stage"] == "trial"
    assert trial_metadata["trial_scope"] == "single-seat"
    assert trial_metadata["selected_seat_ref"] == "env-browser-primary"
    assert trial_metadata["replacement_target_ids"] == ["skill:legacy_outreach"]

    execution_payload = _execute_prediction_recommendation_direct(
        app,
        case_id=case_id,
        recommendation_id=trial_recommendation["recommendation"]["recommendation_id"],
    )
    assert execution_payload["execution"]["phase"] == "completed"

    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-nextgen-outreach-1",
            title="NextGen outreach completed",
            summary="Guarded desktop outreach completed without operator takeover.",
            task_type="execution",
            status="completed",
            owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-nextgen-outreach-1",
            runtime_status="terminated",
            current_phase="completed",
            risk_level="guarded",
            last_result_summary="NextGen outreach completed cleanly.",
            last_error_summary=None,
            last_owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id="task-nextgen-outreach-1",
            actor_ref="industry-solution-lead-demo",
            capability_ref="skill:nextgen_outreach",
            risk_level="guarded",
            action_summary="nextgen outreach run",
            result_summary="completed without operator intervention",
        ),
    )

    second_case = client.post(
        "/predictions",
        json={
            "title": "Remote rollout review",
            "question": "Should we expand the replacement to the next seat now?",
            "summary": "Review the completed remote skill trial.",
            "owner_scope": "industry-demo-scope",
            "industry_instance_id": "industry-demo",
        },
    )
    assert second_case.status_code == 200
    rollout = next(
        item
        for item in second_case.json()["recommendations"]
        if item["recommendation"]["metadata"].get("gap_kind") == "capability_rollout"
    )
    rollout_metadata = rollout["recommendation"]["metadata"]

    assert rollout["recommendation"]["target_agent_id"] == "industry-ops-demo"
    assert rollout["recommendation"]["action_kind"] == "system:apply_capability_lifecycle"
    assert rollout["recommendation"]["action_payload"]["decision_kind"] == (
        "promote_to_role"
    )
    assert rollout["recommendation"]["action_payload"]["capability_assignment_mode"] == (
        "replace"
    )
    assert rollout["recommendation"]["action_payload"]["selected_scope"] == "seat"
    assert rollout["recommendation"]["action_payload"]["selected_seat_ref"] == (
        "env-browser-secondary"
    )
    assert rollout_metadata["lifecycle_stage"] == "rollout"
    assert rollout_metadata["candidate_lifecycle_stage"] == "active"
    assert rollout_metadata["replacement_target_stage"] == "deprecated"
    assert rollout_metadata["trial_scope"] == "single-seat"
    assert rollout_metadata["source_trial_seat_ref"] == "env-browser-primary"


def test_prediction_service_recommends_rollback_when_trial_candidate_underperforms(
    tmp_path,
    monkeypatch,
) -> None:
    app = _build_predictions_app(
        tmp_path,
        seed_cases=[
            PredictionCaseRecord(
                case_id="case-trial-history",
                title="Trial history",
                summary="Seed case for rollback follow-up.",
                industry_instance_id="industry-demo",
                owner_scope="industry-demo-scope",
            ),
        ],
        seed_recommendations=[
            PredictionRecommendationRecord(
                recommendation_id="trial-nextgen-outreach",
                case_id="case-trial-history",
                recommendation_type="capability_recommendation",
                title="Trial nextgen outreach",
                summary="Executed governed trial for the new outreach candidate.",
                action_kind="system:trial_remote_skill_assignment",
                executable=True,
                status="executed",
                target_agent_id="industry-solution-lead-demo",
                target_capability_ids=[
                    "skill:legacy_outreach",
                    "skill:nextgen_outreach",
                ],
                action_payload={
                    "candidate": {"install_name": "nextgen_outreach"},
                    "target_agent_id": "industry-solution-lead-demo",
                    "capability_ids": ["skill:nextgen_outreach"],
                    "replacement_capability_ids": ["skill:legacy_outreach"],
                    "capability_assignment_mode": "replace",
                },
                metadata={
                    "gap_kind": "underperforming_capability",
                    "optimization_stage": "trial",
                    "industry_instance_id": "industry-demo",
                    "candidate_id": "candidate-nextgen-outreach",
                    "target_agent_id": "industry-solution-lead-demo",
                    "replacement_capability_ids": ["skill:legacy_outreach"],
                    "replacement_capability_id": "skill:legacy_outreach",
                    "installed_capability_ids": ["skill:nextgen_outreach"],
                    "selected_seat_ref": "env-browser-primary",
                    "trial_scope": "single-seat",
                    "resolved_candidate": {"install_name": "nextgen_outreach"},
                    "last_execution_output": {
                        "installed_capability_ids": ["skill:nextgen_outreach"],
                    },
                },
            ),
        ],
    )
    client = TestClient(app)
    skill_service = app.state.capability_service._skill_service
    seeded_candidate = app.state.capability_candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="solution-lead",
        target_seat_ref="env-browser-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="hub:nextgen-outreach",
        candidate_source_version="1.0.0",
        candidate_source_lineage="hub:nextgen-outreach",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="nextgen_outreach",
        summary="Seed trial candidate for rollback follow-up.",
        industry_instance_id="industry-demo",
        status="candidate",
        lifecycle_stage="trial",
        metadata={"seeded_for_test": True},
    )
    app.state.capability_candidate_service._upsert_record(  # pylint: disable=protected-access
        seeded_candidate.model_copy(
            update={
                "candidate_id": "candidate-nextgen-outreach",
                "lineage_root_id": "candidate-nextgen-outreach",
            },
        ),
    )
    skill_service.create_skill(
        name="legacy_outreach",
        content=(
            "---\n"
            "name: legacy_outreach\n"
            "description: Legacy outreach skill\n"
            "---\n"
            "Legacy outreach skill"
        ),
        overwrite=True,
    )
    skill_service.enable_skill("legacy_outreach")
    skill_service.create_skill(
        name="nextgen_outreach",
        content=(
            "---\n"
            "name: nextgen_outreach\n"
            "description: NextGen outreach skill\n"
            "---\n"
            "NextGen outreach skill"
        ),
        overwrite=True,
    )
    skill_service.enable_skill("nextgen_outreach")
    app.state.agent_profile_override_repository.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="industry-solution-lead-demo",
            name="Solution Lead",
            role_name="Solution Lead",
            role_summary="Own guarded outreach execution and follow-up.",
            industry_instance_id="industry-demo",
            industry_role_id="solution-lead",
            capabilities=["skill:nextgen_outreach"],
            reason="trial replacement currently active",
        ),
    )
    _patch_prediction_runtime_detail(
        monkeypatch,
        app,
        seat_refs={"industry-solution-lead-demo": "env-browser-primary"},
        seat_capability_ids={
            "industry-solution-lead-demo": ["skill:nextgen_outreach"],
        },
    )
    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-legacy-outreach-success",
            title="Legacy outreach completed",
            summary="Legacy outreach completed successfully before the trial.",
            task_type="execution",
            status="completed",
            owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-legacy-outreach-success",
            runtime_status="terminated",
            current_phase="completed",
            risk_level="guarded",
            last_result_summary="Legacy outreach completed cleanly.",
            last_error_summary=None,
            last_owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id="task-legacy-outreach-success",
            actor_ref="industry-solution-lead-demo",
            capability_ref="skill:legacy_outreach",
            risk_level="guarded",
            action_summary="legacy outreach run",
            result_summary="completed without operator intervention",
        ),
    )
    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-nextgen-outreach-failed",
            title="NextGen outreach failed",
            summary="The candidate regressed during the trial seat run.",
            task_type="execution",
            status="failed",
            owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-nextgen-outreach-failed",
            runtime_status="terminated",
            current_phase="failed",
            risk_level="guarded",
            last_result_summary="NextGen outreach regressed.",
            last_error_summary="Operator had to intervene again.",
            last_owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id="task-nextgen-outreach-failed",
            actor_ref="industry-solution-lead-demo",
            capability_ref="skill:nextgen_outreach",
            risk_level="guarded",
            action_summary="nextgen outreach run",
            result_summary="failed and required operator takeover",
        ),
    )

    created = client.post(
        "/predictions",
        json={
            "title": "Remote rollback review",
            "question": "Should we roll back the trial candidate before wider rollout?",
            "summary": "Review the failed single-seat remote skill trial.",
            "owner_scope": "industry-demo-scope",
            "industry_instance_id": "industry-demo",
        },
    )
    assert created.status_code == 200
    rollback = next(
        item
        for item in created.json()["recommendations"]
        if item["recommendation"]["metadata"].get("gap_kind") == "capability_rollback"
    )
    rollback_metadata = rollback["recommendation"]["metadata"]
    rollback_payload = rollback["recommendation"]["action_payload"]

    assert rollback["recommendation"]["action_kind"] == "system:apply_capability_lifecycle"
    assert rollback_payload["decision_kind"] == "rollback"
    assert rollback_payload["candidate_id"] == rollback_metadata["candidate_id"]
    assert rollback_payload["capability_assignment_mode"] == "replace"
    assert rollback_payload["selected_scope"] == "seat"
    assert rollback_payload["selected_seat_ref"] == "env-browser-primary"
    assert rollback_payload["rollback_target_ids"] == ["skill:legacy_outreach"]
    assert rollback_payload["capability_ids"] == ["skill:nextgen_outreach"]
    assert rollback_metadata["lifecycle_stage"] == "blocked"
    assert rollback_metadata["candidate_lifecycle_stage"] == "deprecated"
    assert rollback_metadata["replacement_target_stage"] == "active"
    assert rollback_metadata["rollback_target_ids"] == ["skill:legacy_outreach"]
    assert rollback_metadata["source_trial_seat_ref"] == "env-browser-primary"
