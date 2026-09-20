from datetime import date

from pipeline.models import Brief, EpisodeProject, Script, ScriptBeat, Source
from pipeline import storyboard
from pipeline.storyboard import (
    build_shot_plan, concept_animation_score, shot_limit, validate_shot_plan,
)


def project(beat_count=20, *, with_sources=True):
    sources = [Source(id="src_1", title="Source", url="https://example.com/story")] if with_sources else []
    source_ids = ["src_1"] if with_sources else []
    brief = Brief(title="Brief", thesis="Thesis", episode_format="deep_dive", source_ids=source_ids, claim_ids=[], why_now="Now")
    beats = [ScriptBeat(
        id=f"beat_{i:02d}", narration="narration", purpose="hook" if i == 0 else "analysis",
        visual_direction="show the source", source_ids=source_ids,
    ) for i in range(beat_count)]
    script = Script(title="Title", description="Description", tags=[], thumbnail_text="THE BIG CHANGE", beats=beats)
    return EpisodeProject(episode_id="episode_test", scheduled_date=date.today().isoformat(), sources=sources, brief=brief, script=script)


def test_ten_minute_storyboard_meets_pacing_contract():
    shots = build_shot_plan(project(), 600)
    result = validate_shot_plan(shots, 600)
    assert result["passed"], result["failures"]
    assert 70 <= len(shots) <= 110
    assert all(shot.source_id == "src_1" or shot.asset_type in {"generated_video", "concept_animation", "motion_graphic", "chart", "chapter_card"} for shot in shots)
    assert not any(shot.asset_type == "generated_image" for shot in shots)


def test_twelve_minute_storyboard_puts_excess_only_in_motion():
    shots = build_shot_plan(project(), 720)
    assert round(sum(shot.duration_seconds for shot in shots)) == 720
    assert all(shot.duration_seconds <= shot_limit(shot.asset_type) for shot in shots)
    assert all(shot.duration_seconds <= 8 for shot in shots if shot.asset_type == "generated_video")
    assert validate_shot_plan(shots, 720)["passed"]


def test_storyboard_routes_half_of_motion_slots_to_seedance_and_varies_cadence():
    shots = build_shot_plan(project(28), 600)
    motion = [shot for shot in shots if shot.visual_category == "motion_graphics"]
    seedance = [shot for shot in motion if shot.motion_template == "seedance_editorial"]
    assert len(seedance) == int(len(motion) * 0.5 + 0.5)
    assert all(shot.asset_type == "generated_video" for shot in seedance)
    assert len({round(shot.duration_seconds, 1) for shot in shots}) >= 4
    durations = sorted(shot.duration_seconds for shot in shots)
    assert durations[len(durations) // 2] <= 6


def test_storyboard_can_opt_in_to_generated_hero_video(monkeypatch):
    monkeypatch.setattr(storyboard, "GENERATIVE_VISUALS_ENABLED", True)
    shots = build_shot_plan(project(28, with_sources=False), 600)
    heroes = [index for index, shot in enumerate(shots) if shot.asset_type == "generated_video"]
    assert len(heroes) == 5
    assert heroes[0] < len(shots) * 0.2
    assert heroes[-1] > len(shots) * 0.7


def test_cited_online_assets_beat_generated_heroes_except_planned_motion_inserts(monkeypatch):
    monkeypatch.setattr(storyboard, "GENERATIVE_VISUALS_ENABLED", True)
    shots = build_shot_plan(project(28), 600)
    generated = [shot for shot in shots if shot.asset_type == "generated_video"]
    assert generated
    assert all(shot.motion_template == "seedance_editorial" for shot in generated)
    assert all(shot.visual_category == "motion_graphics" and shot.source_id is None for shot in generated)


def test_screenshots_are_full_bleed_with_controlled_push_ins():
    screenshots = [shot for shot in build_shot_plan(project(), 600) if shot.asset_type == "screenshot"]
    assert screenshots
    assert all(shot.presentation == "full_bleed" for shot in screenshots)
    assert all(shot.motion_style == "push_in" for shot in screenshots)
    assert all((shot.focus_x, shot.focus_y) == (0.5, 0.5) for shot in screenshots)


def test_concept_animation_score_prefers_invisible_mechanisms_over_specs():
    mechanism = concept_animation_score(
        "First the request moves through a router, then it transforms into a finished clip.",
        "Explain how the pipeline passes work from input to output.",
        "analysis",
    )
    specification = concept_animation_score(
        "The benchmark reached 68.4% at 1080p in 8 seconds.",
        "Show the official results table.",
        "evidence",
    )
    assert mechanism >= 4
    assert mechanism > specification


def test_storyboard_uses_restrained_source_anchored_concept_animations(monkeypatch):
    monkeypatch.setattr(storyboard, "CONCEPT_ANIMATIONS_ENABLED", True)
    item = project(20)
    for beat in item.script.beats:
        beat.narration = "First the input moves through a pipeline, then the process transforms it into the result."
        beat.visual_direction = "Explain how the workflow passes through three steps."
        beat.purpose = "analysis"
    shots = build_shot_plan(item, 600)
    concepts = [(index, shot) for index, shot in enumerate(shots) if shot.asset_type == "concept_animation"]
    assert 1 <= len(concepts) <= 3
    for index, shot in concepts:
        assert shot.source_id is None
        assert shot.motion_style == "locked"
        assert "not source evidence" in shot.rights_note.casefold()
        neighbors = shots[max(0, index - 2):index] + shots[index + 1:index + 3]
        assert any(neighbor.source_id for neighbor in neighbors)
    assert validate_shot_plan(shots, 600)["passed"]
