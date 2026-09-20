from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from pipeline import identity_arena_thumbnail, magichour, visual_qc
from pipeline.thumbnail_automation import run_brief
from pipeline.thumbnail_formula import (
    build_universal_thumbnail_brief,
    classify_thumbnail_route,
    split_headline,
)


def test_headline_split_balances_short_hooks() -> None:
    assert split_headline("SLACK FOR AI AGENTS?") == ("SLACK FOR", "AI AGENTS?")
    first, second = split_headline("WHO ACTUALLY RUNS THE AGENTS?")
    assert first and second
    assert f"{first} {second}" == "WHO ACTUALLY RUNS THE AGENTS?"


def test_route_uses_identity_arena_only_when_the_interaction_is_the_hook() -> None:
    arena = classify_thumbnail_route(
        "WHO RUNS THE AGENTS?", "A workspace coordinates several coding agents.",
        identity_count=4, source_count=2,
    )
    assert arena.hero_template == "identity_arena"
    assert arena.hook_class == "control"
    receipt = classify_thumbnail_route(
        "THE PRICE HAS A CATCH", "The documented pricing table changes the result.",
        identity_count=2, source_count=2,
    )
    assert receipt.hero_template == "source_package"
    assert receipt.evidence_display == "required"
    comparison = classify_thumbnail_route(
        "CLAUDE VS CODEX", "Both products run the same verified task.",
        identity_count=2, source_count=2,
    )
    assert comparison.hero_template == "source_package"
    assert comparison.hook_class == "comparison_proof"


def test_universal_planner_builds_four_brand_safe_identity_contracts() -> None:
    planned = build_universal_thumbnail_brief({
        "schema_version": "thumbnail-request.v1",
        "headline": "SLACK FOR AI AGENTS?",
        "topic_context": "Buzz coordinates Codex, Claude Code, and Goose in one workspace.",
        "represented_companies": ["Buzz", "Block", "Codex", "Claude", "Goose"],
        "focal_subject": "Buzz workspace",
        "focal_identity_key": "buzz",
        "owner_identity_keys": ["block"],
        "source_images": [],
        "evidence_ids": ["official-launch"],
    })
    assert planned["hero_template"] == "identity_arena"
    assert planned["background_mode"] == "generated_identity_plates"
    assert planned["identity_keys"] == ["buzz", "block", "openai", "claude", "goose"]
    plan = planned["identity_arena_plan"]
    assert plan["focal_identity_key"] == "buzz"
    assert plan["owner_identity_keys"] == ["block"]
    assert plan["mascot_count"] == 4
    assert len(plan["candidates"]) == 4
    for candidate in plan["candidates"]:
        prompt = candidate["prompt"]
        assert "BACKGROUND PLATE" in prompt
        assert "negative space" in prompt
        assert "exact official logos" in prompt
        assert "STRICTLY EXCLUDE" in prompt
        assert all(name not in prompt.casefold() for name in ("buzz", "openai", "claude", "goose", "block"))
        panel = candidate["panel_spec"]
        assert {"buzz", "block", "openai", "claude", "goose"}.issubset(panel)
        assert panel["block"]["badge"] is True


def test_universal_planner_routes_receipts_to_authentic_sources() -> None:
    planned = build_universal_thumbnail_brief({
        "headline": "THE BENCHMARK HAS A CATCH",
        "topic_context": "A verified benchmark chart exposes the pricing limit.",
        "represented_companies": ["OpenAI", "Claude"],
        "source_images": ["benchmark.png"],
        "evidence_ids": ["benchmark-source"],
    })
    assert planned["hero_template"] == "source_package"
    assert planned["route_decision"]["evidence_display"] == "required"


def test_creative_ideation_reuses_reasoning_not_one_visual_template() -> None:
    planned = build_universal_thumbnail_brief({
        "headline": "CLAUDE VS CODEX",
        "topic_context": "Both products face the same verified coding task.",
        "topic_class": "comparison",
        "represented_companies": ["Claude", "Codex"],
        "source_images": ["same-task-left.png", "same-task-right.png"],
        "evidence_ids": ["same-task-test"],
    })
    ideation = planned["creative_ideation"]
    assert ideation["candidate_count"] == 4
    assert len({item["archetype"] for item in ideation["candidates"]}) == 4
    assert len({item["visual_mechanism"] for item in ideation["candidates"]}) == 4
    assert ideation["reference_policy"].startswith("reuse the quality bar")
    assert planned["hero_template"] == "source_package"


def test_explicit_topic_class_controls_ideation_family() -> None:
    planned = build_universal_thumbnail_brief({
        "headline": "GITHUB MODELS IS GONE",
        "topic_context": "GitHub retired the model catalog and inference API.",
        "topic_class": "failure",
        "represented_companies": ["GitHub"],
        "source_images": ["retirement.png"],
        "evidence_ids": ["official-retirement"],
    })
    assert planned["creative_ideation"]["story_type"] == "failure"
    assert planned["creative_ideation"]["candidates"][0]["archetype"] == "broken_assumption"


def test_recent_identity_style_rotates_to_evidence_when_sources_exist() -> None:
    planned = build_universal_thumbnail_brief({
        "headline": "WHO RUNS THE AGENTS?",
        "topic_context": "A workspace coordinates four coding agents.",
        "represented_companies": ["Buzz", "Codex", "Claude", "Goose"],
        "source_images": ["launch-page.png"],
        "evidence_ids": ["launch-page"],
        "recent_thumbnail_archetypes": ["identity_arena"],
    })
    assert planned["hero_template"] == "source_package"
    assert planned["route_decision"]["hook_class"] == "diversity_rotation"


@pytest.mark.parametrize(
    ("companies", "focal", "expected_mascots"),
    [
        (["Claude"], "claude", 1),
        (["Claude", "Codex"], "claude", 2),
        (["Claude", "Codex", "Goose"], "claude", 3),
        (["Buzz", "Codex", "Claude", "Goose"], "buzz", 4),
    ],
)
def test_identity_layouts_scale_from_one_to_four_mascots(
    companies: list[str], focal: str, expected_mascots: int,
) -> None:
    planned = build_universal_thumbnail_brief({
        "headline": "WHO RUNS THE AGENTS?",
        "topic_context": "A workspace coordinates multiple coding agents.",
        "represented_companies": companies,
        "focal_identity_key": focal,
        "source_images": [],
        "evidence_ids": ["official-launch"],
    })
    plan = planned["identity_arena_plan"]
    assert plan["mascot_count"] == expected_mascots
    for candidate in plan["candidates"]:
        mascot_panels = [
            key for key, value in candidate["panel_spec"].items()
            if isinstance(value, dict)
            and key != "headline"
            and "size" in value
            and not value.get("badge", False)
        ]
        assert len(mascot_panels) == expected_mascots
        assert len(set(mascot_panels)) == expected_mascots


def test_two_company_showdown_uses_balanced_left_right_anchors() -> None:
    planned = build_universal_thumbnail_brief({
        "headline": "CLAUDE VS CODEX",
        "topic_context": "Claude and Codex face the same verified coding task.",
        "represented_companies": ["Claude", "Codex"],
        "focal_identity_key": "claude",
        "source_images": [],
        "evidence_ids": ["same-task-test"],
    })
    showdown = next(
        item for item in planned["identity_arena_plan"]["candidates"]
        if item["style_mode"] == "equal_showdown"
    )
    panels = showdown["panel_spec"]
    centers = sorted(panels[key]["x"] for key in ("claude", "openai"))
    assert centers == [350, 930]
    assert panels["claude"]["size"] == panels["openai"]["size"]


def test_roundup_prefers_source_stack_and_identity_cap_is_enforced() -> None:
    roundup = build_universal_thumbnail_brief({
        "headline": "AI NEWS IN 10 MINUTES",
        "topic_context": "A weekly roundup of several unrelated launches and papers.",
        "episode_format": "weekly roundup",
        "represented_companies": ["OpenAI", "Claude", "Google"],
        "source_images": ["launch-page.png"],
        "evidence_ids": ["launch-page"],
    })
    assert roundup["hero_template"] == "source_package"
    with pytest.raises(ValueError, match="five"):
        build_universal_thumbnail_brief({
            "headline": "EVERY AGENT IN ONE APP?",
            "topic_context": "A workspace coordinates six agent providers.",
            "represented_companies": [
                "Buzz", "Block", "Codex", "Claude", "Goose", "Google",
            ],
            "source_images": [],
            "evidence_ids": ["official-launch"],
        })


def test_auto_request_renders_identity_package_without_handwritten_layout(
    tmp_path: Path, monkeypatch,
) -> None:
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "schema_version": "thumbnail-request.v1",
        "hero_template": "auto",
        "headline": "CLAUDE VS CODEX",
        "topic_context": "Claude versus Codex on one verified coding task.",
        "represented_companies": ["Claude", "Codex"],
        "focal_subject": "Claude versus Codex",
        "focal_identity_key": "claude",
        "source_images": [],
        "evidence_ids": ["same-task-test"],
    }), encoding="utf-8")
    calls: list[dict[str, object]] = []

    def fake_generate(prompt: str, name: str, **kwargs):
        calls.append({"prompt": prompt, "name": name, **kwargs})
        return {"id": f"project-{len(calls)}", "credits_charged": 50}

    def fake_download(_job, directory: Path, stem: str):
        path = directory / f"{stem}.png"
        Image.new("RGB", (2048, 1152), (18 + len(calls) * 3, 21, 28)).save(path)
        return [path]

    monkeypatch.setattr(magichour, "image_generate", fake_generate)
    monkeypatch.setattr(magichour, "wait_image", lambda project_id: {
        "id": project_id, "status": "complete", "credits_charged": 50,
    })
    monkeypatch.setattr(magichour, "download_all", fake_download)
    monkeypatch.setattr(visual_qc, "inspect_thumbnail_backplate", lambda *_args, **_kwargs: {
        "passed": True, "unwanted_text": False, "logos_or_ui": False,
        "people_or_faces": False, "generic_ai_aesthetic": False,
        "severe_distortion": False, "usable_negative_space": True,
        "professional_art_direction": True, "notes": [],
    })
    monkeypatch.setattr(visual_qc, "inspect_identity_arena_backplate", lambda *_args, **_kwargs: {
        "passed": True, "unwanted_text": False, "logos_or_ui": False,
        "people_or_faces": False, "generic_ai_aesthetic": False,
        "severe_distortion": False, "usable_negative_space": True,
        "professional_art_direction": True, "notes": [],
    })
    monkeypatch.setattr(identity_arena_thumbnail, "validate_variants", lambda *_args, **_kwargs: {
        "passed": True, "failures": [], "scores": [],
    })
    output = tmp_path / "package"
    paths = run_brief(request, output)
    assert len(paths) == 4
    assert len(calls) == 4
    planned = json.loads((output / "planned_thumbnail_brief.json").read_text(encoding="utf-8"))
    assert planned["hero_template"] == "identity_arena"
    assert planned["identity_keys"] == ["claude", "openai"]
    manifest = json.loads((output / "thumbnail_manifest.json").read_text(encoding="utf-8"))
    assert manifest["headline"] == "CLAUDE VS CODEX"
    assert manifest["represented_companies"] == ["claude", "openai"]
    assert manifest["route_decision"]["hook_class"] == "showdown"
    assert manifest["recommended_candidate"] == 2
    assert manifest["recommended_style"] == "equal_showdown"
