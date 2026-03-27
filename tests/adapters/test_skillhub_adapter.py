# -*- coding: utf-8 -*-
import io
import zipfile

from copaw.adapters import skillhub as skillhub_module


def _build_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def test_search_skillhub_skills_parses_remote_results(monkeypatch) -> None:
    monkeypatch.setattr(
        skillhub_module,
        "_http_json_get",
        lambda url, params=None: {
            "results": [
                {
                    "slug": "vibesku",
                    "displayName": "Vibesku",
                    "summary": "商品图与电商文案生成",
                    "version": "0.2.4",
                }
            ]
        },
    )

    results = skillhub_module.search_skillhub_skills("sku", limit=5)

    assert len(results) == 1
    assert results[0].slug == "vibesku"
    assert results[0].name == "素材创意助手"
    assert results[0].description == "把素材加工成视觉内容和配套文案。"
    assert results[0].version == "0.2.4"
    assert results[0].source_url.endswith("/skills/vibesku.zip")
    assert results[0].source_label == "SkillHub 商店"


def test_load_skillhub_bundle_from_url_extracts_zip_tree(monkeypatch) -> None:
    bundle = _build_zip(
        {
            "find-skills/SKILL.md": "---\nname: find-skills\ndescription: test\n---\nbody\n",
            "find-skills/references/guide.md": "hello",
            "find-skills/scripts/run.sh": "echo ok",
        }
    )
    monkeypatch.setattr(skillhub_module, "_http_bytes_get", lambda url: bundle)

    payload, source_url = skillhub_module.load_skillhub_bundle_from_url(
        "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/find-skills.zip"
    )

    assert source_url.endswith("/skills/find-skills.zip")
    assert payload["files"]["SKILL.md"].startswith("---")
    assert payload["files"]["references/guide.md"] == "hello"
    assert payload["files"]["scripts/run.sh"] == "echo ok"
