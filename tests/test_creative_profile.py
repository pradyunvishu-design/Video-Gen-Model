from pathlib import Path

import pytest
from PIL import Image

from pipeline.brand_assets import detect_brand_keys, motion_brand_theme, resolve_brand_assets
from pipeline.creative_profile import (
    HERMES_PROOF_FIRST,
    TOPIC_ARCHETYPE_ROUTES,
    TOPIC_STYLE_ROUTES,
    build_thumbnail_concepts,
    classify_story,
    review_proof_first_spec,
    thumbnail_hypotheses,
)
from pipeline.thumbnail import generate_variants, source_suitability, validate_concepts, validate_variants
from pipeline.thumbnail_automation import STYLE_MODES, build_automation_plan, score_hook


def test_story_router_uses_topic_semantics() -> None:
    assert classify_story("Claude vs Codex on the same task") == "comparison"
    assert classify_story("News Weekly: the top stories") == "weekly-roundup"
    assert classify_story("The launch has one expensive catch") == "failure"
    assert classify_story("A real before and after redesign", source_count=2) == "workflow"
    assert classify_story("A new model research result") == "research"


def test_topic_router_covers_all_authoritative_classes() -> None:
    assert set(TOPIC_ARCHETYPE_ROUTES) == {
        "release", "comparison", "workflow", "failure", "research", "business-policy", "weekly-roundup",
    }
    assert all(len(set(archetypes)) == 4 for archetypes in TOPIC_ARCHETYPE_ROUTES.values())
    assert set(TOPIC_STYLE_ROUTES) == set(TOPIC_ARCHETYPE_ROUTES)
    assert all(set(styles) == set(STYLE_MODES) for styles in TOPIC_STYLE_ROUTES.values())
    assert all(styles[0] == "commercial_collage" for styles in TOPIC_STYLE_ROUTES.values())


def test_concept_contracts_are_truth_bound_and_distinct() -> None:
    concepts = build_thumbnail_concepts(
        topic_class="research", headline="70B ON FOUR GIGS", focal_subject="AirLLM source capture",
        evidence_ids=["src_airllm", "claim_70b"], asset_ids=["capture_01", "capture_02"],
        must_not_imply=["independently verified"],
    )
    assert validate_concepts(concepts)["passed"]
    assert len({concept.archetype for concept in concepts}) == 4
    assert len({concept.style_mode for concept in concepts}) == 4
    assert all(concept.evidence_ids and concept.asset_ids for concept in concepts)


def test_automation_plan_separates_generated_backplate_from_identity_overlay() -> None:
    concepts = build_thumbnail_concepts(
        topic_class="comparison", headline="OPEN WEIGHTS REAL COST", focal_subject="Model launch",
        evidence_ids=["claim-1"], asset_ids=["source-1"], required_logos=["openai", "claude"],
    )
    plan = build_automation_plan(concepts, brand_labels=["OpenAI", "Claude"])
    assert plan["schema_version"] == "thumbnail-automation.v2"
    assert len(set(plan["style_modes"])) == 4
    assert plan["hook_review"]["passed"]
    for candidate in plan["candidates"]:
        final_prompt = candidate["final"]["prompt"]
        assert "BACKPLATE ONLY" in final_prompt
        assert "no words, letters, numbers, logos" in final_prompt
        assert candidate["deterministic_overlay"]["required_logos"] == ["openai", "claude"]
        assert candidate["provider_options"]["magic_hour"]["text_to_image"][0] == "nano-banana-2"


def test_generic_hook_fails_before_credit_spend() -> None:
    review = score_hook("THIS CHANGES EVERYTHING", context="Claude released a new coding workflow")
    assert not review["passed"]
    assert review["script_payoff"] == 1


def test_thumbnail_hypotheses_are_four_distinct_concepts() -> None:
    hypotheses = thumbnail_hypotheses("Claude versus Codex", source_count=2)
    assert len(hypotheses) == 4
    assert len({item.archetype for item in hypotheses}) == 4
    assert hypotheses[0].archetype == "agent_showdown"


def test_proof_first_profile_rejects_silent_uncaptioned_video(tmp_path: Path) -> None:
    spec = {
        "creativeProfile": HERMES_PROOF_FIRST,
        "audioSrc": "",
        "captions": [],
        "scenes": [
            {"kind": kind, "durationSeconds": 5}
            for kind in ("title", "graph", "activity", "source", "source", "compare")
        ],
    }
    review = review_proof_first_spec(spec, tmp_path)
    assert not review["passed"]
    assert any("narration" in failure for failure in review["failures"])
    assert any("captions" in failure for failure in review["failures"])


def test_proof_first_profile_accepts_narrated_six_state_sequence(tmp_path: Path) -> None:
    (tmp_path / "voice.wav").write_bytes(b"voice")
    spec = {
        "creativeProfile": HERMES_PROOF_FIRST,
        "audioSrc": "voice.wav",
        "captions": [
            {"text": f"word{index}", "startMs": index * 400, "endMs": index * 400 + 320, "timestampMs": index * 400, "confidence": 1}
            for index in range(75)
        ],
        "scenes": [
            {"kind": kind, "durationSeconds": 5}
            for kind in ("title", "graph", "activity", "source", "source", "compare")
        ],
    }
    review = review_proof_first_spec(spec, tmp_path)
    assert review["passed"]
    assert review["score"] >= 90
    assert review["speech_wpm"] == 155.17


def test_thumbnail_generator_routes_topic_and_writes_manifest(tmp_path: Path) -> None:
    source_a = tmp_path / "source-a.png"
    source_b = tmp_path / "source-b.png"
    for path, base in ((source_a, (26, 49, 80)), (source_b, (129, 70, 46))):
        image = Image.new("RGB", (1280, 720), base)
        pixels = image.load()
        for y in range(720):
            for x in range(1280):
                pixels[x, y] = tuple(min(255, channel + (x + y) % 90) for channel in base)
        image.save(path)
    output = tmp_path / "thumbnails"
    paths = generate_variants(
        [source_a, source_b], "THE AGENT TEST", output,
        topic_context="Claude versus Codex on the same verified task",
        represented_companies=["Claude", "Codex"],
        brand_asset_overrides={"claude": source_a, "openai": source_b},
    )
    assert len(paths) == 4
    assert all(Image.open(path).size == (1280, 720) for path in paths)
    manifest = (output / "thumbnail_manifest.json").read_text(encoding="utf-8")
    assert '"story_type": "comparison"' in manifest
    assert '"archetype": "agent_showdown"' in manifest
    assert '"algorithm_version": 10' in manifest
    assert '"quality_floor": 88' in manifest
    assert '"generated_backplate_policy": "scene-only-no-text-no-logos-no-product-ui"' in manifest
    assert '"style_mode": "commercial_collage"' in manifest
    assert '"recommended_candidate": 2' in manifest
    assert '"selection_policy": "story-hook-fit-plus-mobile-quality-after-evidence-gate"' in manifest
    assert '"identity_policy": "official-assets-only"' in manifest
    assert '"key": "claude"' in manifest
    assert '"key": "openai"' in manifest
    assert validate_variants(paths, "THE AGENT TEST")["passed"]


def test_thumbnail_source_gate_rejects_blank_block_page(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked.png"
    image = Image.new("RGB", (1280, 720), "white")
    image.save(blocked)
    review = source_suitability(blocked)
    assert not review["passed"]
    assert any("blank" in failure for failure in review["failures"])


def test_brand_detector_prefers_product_identity_and_source_domains() -> None:
    assert detect_brand_keys(["Anthropic", "Claude", "Codex"], context="same coding task") == ["openai", "claude"]
    assert detect_brand_keys([], context="new accelerator", source_urls=["https://www.amd.com/en/newsroom.html"]) == ["amd"]


def test_motion_brand_theme_keeps_rabbits_editorial() -> None:
    claude = motion_brand_theme("Claude Code validates a chip")
    codex = motion_brand_theme("Codex reviews the result")
    assert claude and claude["accent"] == "#D97757"
    assert claude["avatarStatus"] == "channel-owned-editorial-avatar"
    assert codex and codex["accent"] == "#F2F1ED"
    assert codex["markTreatment"] == "official-asset-unmodified"


def test_unresolved_company_asset_stops_thumbnail_generation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="AMD.*missing"):
        resolve_brand_assets(["AMD"], brand_root=tmp_path)


def test_identity_gate_rejects_brandless_thumbnail_package(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    image = Image.new("RGB", (1280, 720), (28, 61, 91))
    pixels = image.load()
    for y in range(720):
        for x in range(1280):
            pixels[x, y] = (28 + (x + y) % 100, 61 + (x // 2 + y) % 80, 91 + (x + y // 3) % 90)
    image.save(source)
    with pytest.raises(ValueError, match="identity gate"):
        generate_variants(
            [source], "THE NEW MODEL", tmp_path / "brandless",
            focal_subject="Unidentified product", require_brand_identity=True,
        )


def test_required_brand_is_visibly_placed_in_every_candidate(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    logo = tmp_path / "logo.png"
    source_image = Image.new("RGB", (1280, 720), (35, 66, 102))
    pixels = source_image.load()
    for y in range(720):
        for x in range(1280):
            pixels[x, y] = (35 + (x + y) % 110, 66 + (x // 3 + y) % 90, 102 + (x + y // 2) % 100)
    source_image.save(source)
    Image.new("RGBA", (256, 256), (20, 20, 20, 255)).save(logo)
    paths = generate_variants(
        [source], "CODEX CHANGED THE JOB", tmp_path / "brand-thumbs",
        represented_companies=["Codex"], brand_asset_overrides={"openai": logo},
    )
    manifest = (tmp_path / "brand-thumbs" / "thumbnail_manifest.json").read_text(encoding="utf-8")
    assert len(paths) == 4
    assert manifest.count('"key": "openai"') >= 8
    assert '"brand_accuracy": 15' in (tmp_path / "brand-thumbs" / "thumbnail_qc.json").read_text(encoding="utf-8")


def test_research_product_and_closeup_render_as_distinct_hypotheses(tmp_path: Path) -> None:
    sources = []
    for index, color in enumerate(((26, 49, 80), (129, 70, 46), (65, 96, 71))):
        path = tmp_path / f"source-{index}.png"
        image = Image.new("RGB", (1280, 720), color)
        pixels = image.load()
        for y in range(720):
            for x in range(1280):
                pixels[x, y] = tuple(min(255, channel + (x * (index + 1) + y) % 110) for channel in color)
        image.save(path)
        sources.append(path)
    paths = generate_variants(
        sources, "70B ON FOUR GIGS", tmp_path / "thumbs",
        topic_class="research", evidence_ids=["claim-1"], asset_ids=[path.stem for path in sources],
    )
    review = validate_variants(paths, "70B ON FOUR GIGS")
    assert review["passed"]
    assert not any("thumbnail_1 and thumbnail_4" in failure for failure in review["failures"])
