from pipeline.creative_profile import build_thumbnail_concepts
from pipeline.thumbnail_prompt_lab import build_prompt_set, review_prompt_set


def test_prompt_lab_builds_distinct_faceless_original_contracts() -> None:
    concepts = build_thumbnail_concepts(
        topic_class="comparison",
        headline="OPEN MODEL CAUGHT UP",
        focal_subject="Verified model launch",
        evidence_ids=["claim-1"],
        asset_ids=["source-1"],
        required_logos=["minimax", "github"],
    )
    prompt_set = build_prompt_set(concepts)
    assert review_prompt_set(prompt_set)["passed"]
    assert len(prompt_set) == 4
    assert len({item["prompt"] for item in prompt_set}) == 4
    assert [item["generation_mode"] for item in prompt_set].count("nano-banana-2") == 3
    assert [item["generation_mode"] for item in prompt_set].count("local_deterministic") == 1
    for item in prompt_set:
        prompt = item["prompt"].casefold()
        assert "people, human faces" in prompt
        assert "gears, circuit boards" in prompt
        assert "exact official logos" in prompt
        assert "ai labs" not in prompt
        assert "dubibubi" not in prompt
        assert "jack roberts" not in prompt
