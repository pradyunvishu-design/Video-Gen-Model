from pipeline.art_direction import direct_scene, review_art_direction_plan
from pipeline.visual_style_profile import load_visual_style_profile


def _scene(scene_id: str, kind: str, intent: str, seed: str, prior: list[str] | None = None) -> dict:
    direction = direct_scene(
        scene_id=scene_id,
        kind=kind,
        intent=intent,
        context=seed,
        accent="#D97757",
        prior_concepts=prior,
    )
    return {"id": scene_id, "kind": kind, "artDirection": direction}


def test_director_produces_renderer_neutral_semantic_contract() -> None:
    scene = _scene("proof-1", "source", "proof", "The official benchmark reports a 42 percent gain.")
    direction = scene["artDirection"]
    assert direction["composition"] == "proof-dominant"
    assert direction["cameraPolicy"] == "locked"
    assert set(direction["motionIntents"]) <= {"micro", "enter", "connect", "emphasize"}
    assert len(direction["focalIdea"].split()) <= 12


def test_director_avoids_adjacent_concept_repeat() -> None:
    first = _scene("proof-1", "source", "proof", "One official result")
    concept = first["artDirection"]["conceptFamily"]
    second = _scene("proof-2", "source", "proof", "A second official result", [concept])
    assert second["artDirection"]["conceptFamily"] != concept


def test_review_rejects_generic_ai_art_direction() -> None:
    profile = load_visual_style_profile("ai-news-editorial-v6")
    scene = _scene("proof-1", "source", "proof", "Verified result")
    scene["artDirection"]["decorationPolicy"] = "floating glass card with random glow"
    report = review_art_direction_plan([scene], profile)
    assert not report["passed"]
    assert any("decorative motion" in item or "forbidden aesthetic" in item for item in report["failures"])


def test_director_compares_three_concepts_and_rejects_invented_mascots() -> None:
    profile = load_visual_style_profile("ai-news-editorial-v6")
    scene = _scene("proof-1", "source", "proof", "The source names the validation workflow.")
    direction = scene["artDirection"]
    assert len(direction["conceptCandidates"]) == 3
    assert len({item["conceptFamily"] for item in direction["conceptCandidates"]}) == 3
    assert direction["compositionStrategy"] == "intentional-asymmetry"
    assert direction["inventedMascotAllowed"] is False
    assert review_art_direction_plan([scene], profile)["passed"]

    direction["inventedMascotAllowed"] = True
    report = review_art_direction_plan([scene], profile)
    assert not report["passed"]
    assert any("invented mascots" in item for item in report["failures"])
