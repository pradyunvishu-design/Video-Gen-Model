from datetime import date

import pytest
from PIL import Image

from pipeline import production
from pipeline.models import (
    Brief, CaptureRecord, EpisodeProject, Script, ScriptBeat, Shot, Source,
)
from pipeline.motion_graphics import (
    render_concept_end_plate, render_motion_graphic, render_motion_plate, render_motion_video,
)
from pipeline.render_v2 import duration
from pipeline.storyboard import motion_template_for


def _project() -> EpisodeProject:
    source = Source(id="src_1", title="Official launch", url="https://example.com/launch")
    brief = Brief(
        title="What changed", thesis="The workflow became simpler", episode_format="deep_dive",
        source_ids=["src_1"], claim_ids=[], why_now="It launched",
    )
    script = Script(
        title="What changed", description="A clear explanation", tags=["AI"], thumbnail_text="THE WORKFLOW CHANGED",
        beats=[ScriptBeat(
            id="beat_1", narration="This is the evidence we need to examine.", purpose="analysis",
            visual_direction="A three step workflow becoming one connected system", source_ids=["src_1"],
        )],
    )
    return EpisodeProject(
        episode_id="episode_visual", scheduled_date=date.today().isoformat(), sources=[source], brief=brief,
        script=script, shots=[
            Shot(id="shot_001", beat_id="beat_1", asset_type="screenshot", source_id="src_1"),
            Shot(id="shot_002", beat_id="beat_1", asset_type="screen_recording", source_id="src_1"),
            Shot(id="shot_003", beat_id="beat_1", asset_type="generated_video", source_id="src_1"),
        ],
    )


def test_capture_assignment_does_not_overwrite_generated_video(monkeypatch, tmp_path):
    project = _project()
    still = tmp_path / "still.png"
    recording = tmp_path / "recording.mp4"
    still.write_bytes(b"png")
    recording.write_bytes(b"video")

    def fake_capture_sources(*args, **kwargs):
        return [{
            "source_id": "src_1", "screenshots": [str(still)], "editorial_stills": [str(still)],
            "provenance_stills": [], "recording": str(recording), "errors": [],
            "record": CaptureRecord(source_id="src_1", requested_url="https://example.com/launch"),
        }]

    monkeypatch.setattr(production, "capture_sources", fake_capture_sources)
    production._capture_and_assign(project, tmp_path)
    assert project.shots[0].asset_path == str(still)
    assert project.shots[1].asset_path == str(recording)
    assert project.shots[2].asset_path == ""


def test_local_motion_graphic_is_full_hd(tmp_path):
    project = _project()
    shot = Shot(
        id="shot_004", beat_id="beat_1", asset_type="motion_graphic",
        prompt="Three separate tools become one connected workflow",
    )
    path = render_motion_graphic(project, shot, tmp_path / "graphic.png")
    with Image.open(path) as image:
        assert image.size == (1920, 1080)


def test_magic_hour_anchor_is_a_local_text_free_motion_plate(tmp_path):
    project = _project()
    shot = Shot(id="shot_005", beat_id="beat_1", asset_type="generated_video", prompt="Connected workflow")
    path = render_motion_plate(project, shot, tmp_path / "plate.png")
    with Image.open(path) as image:
        assert image.size == (1920, 1080)


def test_seedance_anchor_uses_neutral_horizontal_editorial_palette(tmp_path):
    project = _project()
    shot = Shot(
        id="shot_seedance", beat_id="beat_1", asset_type="generated_video",
        motion_template="seedance_editorial", prompt="A workflow routes through three stages",
    )
    path = render_motion_plate(project, shot, tmp_path / "seedance_plate.png")
    with Image.open(path).convert("RGB") as image:
        assert image.size == (1920, 1080)
        colors = {color for _count, color in image.getcolors(maxcolors=50)}
        assert (240, 242, 240) in colors
        assert (181, 111, 85) in colors
        assert all(not (blue > red + 45 and blue > green + 35) for red, green, blue in colors)


def test_concept_animation_uses_a_distinct_teaching_plate(tmp_path):
    project = _project()
    hero = Shot(id="shot_hero", beat_id="beat_1", asset_type="generated_video", prompt="Connected workflow")
    concept = Shot(id="shot_concept", beat_id="beat_1", asset_type="concept_animation", prompt="Input becomes output")
    hero_path = render_motion_plate(project, hero, tmp_path / "hero.png")
    concept_path = render_motion_plate(project, concept, tmp_path / "concept.png")
    assert hero_path.read_bytes() != concept_path.read_bytes()
    with Image.open(concept_path) as image:
        assert image.size == (1920, 1080)


def test_concept_animation_has_distinct_start_and_completed_whiteboards(tmp_path):
    project = _project()
    shot = Shot(id="shot_concept", beat_id="beat_1", asset_type="concept_animation", prompt="Input becomes output")
    start = render_motion_plate(project, shot, tmp_path / "start.png")
    end = render_concept_end_plate(project, shot, tmp_path / "end.png")
    assert start.read_bytes() != end.read_bytes()
    with Image.open(start) as start_image, Image.open(end) as end_image:
        assert start_image.getpixel((700, 535)) != end_image.getpixel((700, 535))


def test_magic_hour_video_prompt_forbids_shake_and_generated_text():
    prompt = production._video_prompt("a luminous model core processing video frames")
    assert "no shake" in prompt.casefold()
    assert "no text" in prompt.casefold()
    assert "temporal consistency" in prompt.casefold()
    assert "motion graphic" in prompt.casefold()
    assert "generic ai-art aesthetic" in prompt.casefold()


def test_concept_animation_prompt_is_teaching_first_and_not_evidence():
    prompt = production._concept_video_prompt("an input moving through a three-stage model pipeline")
    lowered = prompt.casefold()
    assert "cause-and-effect" in lowered
    assert "must teach the mechanism" in lowered
    assert "no text" in lowered
    assert "no handheld motion" in lowered
    assert "not documentary evidence" in lowered


def test_concept_animation_routes_are_1080p(monkeypatch):
    monkeypatch.setattr(production, "CONCEPT_ANIMATION_MODELS", ("kling-3.0:4k", "veo3.1:1080p"))
    assert production._concept_model_routes() == [("kling-3.0", "1080p"), ("veo3.1", "1080p")]


def test_seedance_editorial_prompt_is_horizontal_stable_and_text_free():
    prompt = production._seedance_editorial_prompt("A request moving through three model stages")
    lowered = prompt.casefold()
    assert "16:9 horizontal" in lowered
    assert "one semantic action" in lowered
    assert "no text" in lowered
    assert "no shake" in lowered
    assert "no audio" in lowered
    assert "purple-blue gradient" in lowered
    assert "deterministically" in lowered


def test_seedance_routes_use_current_1080p_model_and_skip_720p_only_route(monkeypatch):
    monkeypatch.setattr(
        production,
        "SEEDANCE_MOTION_MODELS",
        ("seedance-2.0:720p", "seedance:1080p", "kling-3.0:720p"),
    )
    assert production._seedance_model_routes() == [
        ("seedance", "1080p"), ("kling-3.0", "1080p"),
    ]


def test_exact_motion_video_is_full_hd_and_timed(tmp_path):
    project = _project()
    shot = Shot(
        id="shot_006", beat_id="beat_1", asset_type="motion_graphic",
        prompt="Evidence becomes a clear decision", duration_seconds=1,
        motion_template="step_flow",
    )
    path = render_motion_video(project, shot, tmp_path / "exact_motion.mp4", duration=1, fps=4)
    assert path.is_file()
    assert 0.9 <= duration(path) <= 1.2


def test_motion_template_matches_narrative_job():
    assert motion_template_for("chart", "evidence") == "stat_reveal"
    assert motion_template_for("motion_graphic", "comparison") == "comparison"
    assert motion_template_for("motion_graphic", "analysis") == "orbit_map"


def test_no_ai_still_policy_rejects_timeline_shot():
    project = _project()
    project.shots[0].asset_type = "generated_image"
    with pytest.raises(RuntimeError, match="no-AI-still"):
        production._assert_no_generated_stills(project)
