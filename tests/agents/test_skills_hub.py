# -*- coding: utf-8 -*-
from types import SimpleNamespace

import pytest

from copaw.agents import skills_hub as skills_hub_module


def test_search_hub_skills_prefers_skillhub_results(monkeypatch) -> None:
    monkeypatch.setattr(
        skills_hub_module,
        "search_skillhub_skills",
        lambda query, limit=20, search_url=None: [
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
    monkeypatch.setattr(
        skills_hub_module,
        "_skillhub_bundle_is_installable",
        lambda _url: True,
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
        lambda query, limit=20, search_url=None: [],
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


def test_search_hub_skills_suppresses_non_installable_skillhub_results(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        skills_hub_module,
        "search_skillhub_skills",
        lambda query, limit=20, search_url=None: [
            SimpleNamespace(
                slug="broken-browser",
                name="Broken Browser",
                description="bad bundle",
                version="0.0.1",
                source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/broken-browser.zip",
                source_label="SkillHub 鍟嗗簵",
            ),
            SimpleNamespace(
                slug="agent-browser",
                name="Agent Browser",
                description="good bundle",
                version="0.2.0",
                source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/agent-browser.zip",
                source_label="SkillHub 鍟嗗簵",
            ),
        ],
    )
    monkeypatch.setattr(
        skills_hub_module,
        "_skillhub_bundle_is_installable",
        lambda url: not str(url).endswith("broken-browser.zip"),
        raising=False,
    )

    results = skills_hub_module.search_hub_skills("browser", limit=5)

    assert [item.slug for item in results] == ["agent-browser"]


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


def test_install_skill_from_hub_rejects_non_allowlisted_bundle_url() -> None:
    try:
        skills_hub_module.install_skill_from_hub(
            bundle_url="https://example.com/bundle.json",
        )
    except ValueError as exc:
        assert "supported" in str(exc).lower() or "allowlist" in str(exc).lower()
    else:
        raise AssertionError("Expected unsupported bundle URL to be rejected")


def test_install_skill_from_hub_injects_package_metadata_into_skill_content(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        skills_hub_module,
        "load_skillhub_bundle_from_url",
        lambda url: (
            {
                "files": {
                    "SKILL.md": "---\nname: find-skills\ndescription: test\n---\nbody\n",
                }
            },
            url,
        ),
    )
    monkeypatch.setattr(
        skills_hub_module.SkillService,
        "create_skill",
        lambda name, content, overwrite=False, references=None, scripts=None, extra_files=None: captured.update(
            {
                "name": name,
                "content": content,
            }
        )
        or True,
    )
    monkeypatch.setattr(
        skills_hub_module.SkillService,
        "enable_skill",
        lambda name, force=True: True,
    )

    bundle_url = "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/find-skills.zip"
    skills_hub_module.install_skill_from_hub(
        bundle_url=bundle_url,
        version="2.0.0",
    )

    assert captured["name"] == "find-skills"
    assert f"package_ref: {bundle_url}" in str(captured["content"])
    assert "package_kind: hub-bundle" in str(captured["content"])
    assert "package_version: 2.0.0" in str(captured["content"])


def test_install_skill_from_hub_rejects_unvalidated_http_source(monkeypatch) -> None:
    monkeypatch.setattr(
        skills_hub_module,
        "_http_json_get",
        lambda _url: (_ for _ in ()).throw(
            AssertionError("arbitrary JSON fallback must not run"),
        ),
    )

    with pytest.raises(ValueError, match="Unsupported skill bundle source"):
        skills_hub_module.install_skill_from_hub(
            bundle_url="https://example.com/random-skill.json",
        )


def test_install_skill_from_hub_rejects_invalid_skill_frontmatter(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        skills_hub_module,
        "load_skillhub_bundle_from_url",
        lambda url: (
            {
                "name": "find-skills",
                "files": {
                    "SKILL.md": "---\nname: find-skills\n: broken\n---\nbody\n",
                },
            },
            url,
        ),
    )

    with pytest.raises(ValueError, match="Front Matter|front matter|description"):
        skills_hub_module.install_skill_from_hub(
            bundle_url=(
                "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/"
                "skills/find-skills.zip"
            ),
        )


def test_remote_skill_bundle_is_installable_accepts_github_repo_with_skill(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        skills_hub_module,
        "_fetch_bundle_from_github_url",
        lambda bundle_url, requested_version: (
            {
                "name": "browser_pilot",
                "files": {
                    "SKILL.md": "---\nname: browser_pilot\ndescription: test\n---\nbody\n",
                },
            },
            bundle_url,
        ),
    )

    assert (
        skills_hub_module.remote_skill_bundle_is_installable(
            "https://github.com/acme/browser-pilot",
        )
        is True
    )


def test_fetch_bundle_from_github_url_falls_back_to_raw_skill_md(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        skills_hub_module,
        "_fetch_bundle_from_repo_and_skill_hint",
        lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("GitHub API rate limit exceeded"),
        ),
    )
    monkeypatch.setattr(
        skills_hub_module,
        "_fetch_bundle_from_github_raw_fallback",
        lambda **_kwargs: (
            {
                "name": "teammate-skill",
                "files": {
                    "SKILL.md": "---\nname: teammate-skill\ndescription: raw fallback\n---\nbody\n",
                },
            },
            "https://github.com/LeoYeAI/teammate-skill",
        ),
    )
    monkeypatch.setattr(
        skills_hub_module,
        "_github_get_default_branch",
        lambda owner, repo: "main",
    )

    bundle, source_url = skills_hub_module._fetch_bundle_from_github_url(
        "https://github.com/LeoYeAI/teammate-skill",
        requested_version="",
    )

    assert bundle["name"] == "teammate-skill"
    assert "SKILL.md" in bundle["files"]
    assert source_url == "https://github.com/LeoYeAI/teammate-skill"


def test_fetch_bundle_from_github_raw_fallback_uses_frontmatter_name(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        skills_hub_module,
        "_http_text_get",
        lambda _url, params=None: (
            "---\nname: create-teammate\ndescription: raw fallback\n---\nbody\n"
        ),
    )

    bundle, source_url = skills_hub_module._fetch_bundle_from_github_raw_fallback(
        owner="LeoYeAI",
        repo="teammate-skill",
        path_hint="",
        requested_version="main",
        default_branch="main",
    )

    assert bundle["name"] == "create-teammate"
    assert source_url == "https://github.com/LeoYeAI/teammate-skill"
