from pipeline.clip_alignment import review_project_clip_alignment, score_alignment
from pipeline.models import EpisodeProject, Script, ScriptBeat, Shot, Source


def _project(paths: list[str]) -> EpisodeProject:
    source = Source(
        id="src_chip", title="Claude helps validate semiconductor chips",
        publisher="Anthropic", url="https://example.com/chips",
    )
    beat = ScriptBeat(
        id="beat_chip",
        narration="Claude reads chip test results and helps an engineer rerun validation.",
        purpose="evidence",
        visual_direction="Show a semiconductor lab, wafer test, and engineer review.",
        source_ids=["src_chip"],
    )
    shots = [
        Shot(
            id=f"shot_{index}", beat_id="beat_chip", asset_type="official_demo",
            source_id="src_chip", prompt="Semiconductor wafer validation lab",
            semantic_target=f"{beat.narration} {beat.visual_direction}",
            asset_path=path, duration_seconds=4,
        )
        for index, path in enumerate(paths, 1)
    ]
    return EpisodeProject(
        episode_id="alignment_test", scheduled_date="2026-08-22",
        sources=[source], script=Script(
            title="Chip validation", description="test", tags=["ai", "chips"],
            thumbnail_text="CLAUDE TESTS CHIPS",
            beats=[beat],
        ), shots=shots,
    )


def test_semantic_alignment_prefers_the_clip_that_depicts_the_sentence():
    good = score_alignment(
        "engineer validates a semiconductor chip in a lab",
        "official semiconductor wafer validation lab with engineer and test equipment",
    )
    bad = score_alignment(
        "engineer validates a semiconductor chip in a lab",
        "audience arrives at a generic conference keynote stage",
    )
    assert good["score"] >= 65
    assert good["score"] > bad["score"]


def test_review_rejects_nearby_and_excessive_asset_repetition():
    review = review_project_clip_alignment(_project(["same.mp4", "same.mp4", "same.mp4"]))
    assert not review["passed"]
    assert any("limit 2" in failure for failure in review["failures"])
    assert any("cooldown" in failure for failure in review["failures"])


def test_review_accepts_distinct_semantically_linked_clips():
    review = review_project_clip_alignment(_project(["wafer.mp4", "lab.mp4", "review.mp4"]))
    assert review["passed"], review["failures"]


def test_review_caps_different_excerpts_from_one_broll_source():
    project = _project(["excerpt_00.mp4", "excerpt_01.mp4", "excerpt_02.mp4"])
    for shot in project.shots:
        shot.visual_category = "youtube_broll"
        shot.reuse_group = "youtube:one-master-video"
    review = review_project_clip_alignment(project)
    assert not review["passed"]
    assert any("B-roll source" in failure and "limit 2" in failure for failure in review["failures"])
