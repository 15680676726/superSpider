# -*- coding: utf-8 -*-
from types import SimpleNamespace

from copaw.agents import skills_hub as skills_hub_module


def test_search_hub_skills_prefers_skillhub_results(monkeypatch) -> None:
    monkeypatch.setattr(
        skills_hub_module,
        "search_skillhub_skills",
        lambda query, limit=20: [
            SimpleNamespace(
                slug="vibesku",
                name="Vibesku",
                description="商品图与电商文案生成",
                version="0.2.4",
                source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/vibesku.zip",
                source_label="SkillHub 商店",
            )
        ],
    )
    monkeypatch.setattr(
        skills_hub_module,
        "_legacy_search_hub_skills",
        lambda query, limit=20: (_ for _ in ()).throw(
            AssertionError("legacy search should not run when SkillHub has results")
        ),
    )

    results = skills_hub_module.search_hub_skills("sku", limit=5)

    assert len(results) == 1
    assert results[0].slug == "vibesku"
    assert results[0].source_label == "SkillHub 商店"


def test_search_hub_skills_returns_empty_when_skillhub_empty(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        skills_hub_module,
        "search_skillhub_skills",
        lambda query, limit=20: [],
    )
    monkeypatch.setattr(
        skills_hub_module,
        "_legacy_search_hub_skills",
        lambda query, limit=20: (_ for _ in ()).throw(
            AssertionError("legacy search should not run in SkillHub-only mode")
        ),
    )

    results = skills_hub_module.search_hub_skills("legacy", limit=5)

    assert results == []


def test_install_skill_from_hub_supports_skillhub_zip(monkeypatch) -> None:
    created: dict[str, object] = {}

    monkeypatch.setattr(
        skills_hub_module,
        "load_skillhub_bundle_from_url",
        lambda url: (
            {
                "files": {
                    "SKILL.md": "---\nname: find-skills\ndescription: test\n---\nbody\n",
                    "references/guide.md": "hello",
                }
            },
            url,
        ),
    )
    monkeypatch.setattr(
        skills_hub_module.SkillService,
        "create_skill",
        lambda name, content, overwrite=False, references=None, scripts=None, extra_files=None: created.update(
            {
                "name": name,
                "content": content,
                "references": references or {},
                "scripts": scripts or {},
                "extra_files": extra_files or {},
            }
        )
        or True,
    )
    monkeypatch.setattr(
        skills_hub_module.SkillService,
        "enable_skill",
        lambda name, force=True: True,
    )

    result = skills_hub_module.install_skill_from_hub(
        bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/find-skills.zip"
    )

    assert created["name"] == "find-skills"
    assert created["references"] == {"guide.md": "hello"}
    assert result.name == "find-skills"
    assert result.enabled is True
    assert result.source_url.endswith("/skills/find-skills.zip")
