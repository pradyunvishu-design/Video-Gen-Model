from datetime import date

from PIL import Image

from pipeline import remotion_renderer
from pipeline.config import PREMIUM_MOTION_MODELS
from pipeline.models import Brief, EpisodeProject, Script, ScriptBeat, Shot, Source
from pipeline.production import _premium_model_routes


def test_remotion_props_use_real_capture_and_researched_template(monkeypatch, tmp_path):
    remotion_dir = tmp_path / "remotion"
    monkeypatch.setattr(remotion_renderer, "REMOTION_DIR", remotion_dir)
    screenshot = tmp_path / "source.png"
    Image.new("RGB", (1920, 1080), "#19052f").save(screenshot)
    source = Source(
        id="src_1", title="Official product launch", publisher="Magic Hour",
        url="https://magichour.ai/", entities=["Veo 3.1"],
    )
    script = Script(
        title="The new workflow", description="Evidence-led explainer", tags=["AI"],
        thumbnail_text="THE WORKFLOW CHANGED",
        beats=[ScriptBeat(
            id="beat_1", purpose="comparison",
            narration="The product promise is useful, but the captured result defines the real limit.",
            visual_direction="The product promise versus the captured result", source_ids=["src_1"],
        )],
    )
    project = EpisodeProject(
        episode_id="remotion_props", scheduled_date=date.today().isoformat(), sources=[source],
        brief=Brief(
            title="The new workflow", thesis="The workflow changed", episode_format="tool_test",
            source_ids=["src_1"], claim_ids=[], why_now="It launched",
        ),
        script=script,
        shots=[
            Shot(id="shot_001", beat_id="beat_1", asset_type="screenshot", source_id="src_1", asset_path=str(screenshot)),
            Shot(id="shot_002", beat_id="beat_1", asset_type="motion_graphic", prompt="The promise versus the captured result", motion_template="comparison"),
        ],
    )

    props = remotion_renderer.build_props(project, project.shots[1], tmp_path / "scratch")

    assert props["template"] == "comparison"
    assert props["labels"] == ["CLAIM", "EVIDENCE"]
    assert props["sourceLabel"] == "Magic Hour"
    assert props["sourceImage"].startswith("runtime/")
    assert (remotion_dir / "public" / props["sourceImage"]).is_file()


def test_seedance_premium_route_requests_1080p():
    # Magic Hour's current `seedance` route supports the channel's 1080p
    # contract; Seedance 2.0 currently tops out below it.
    assert "seedance:1080p" in PREMIUM_MOTION_MODELS
    assert all("seedance-1.5" not in route for route in PREMIUM_MOTION_MODELS)
    assert all(not route.endswith(":4k") for route in PREMIUM_MOTION_MODELS)


def test_premium_routes_force_one_1080p_contract(monkeypatch):
    monkeypatch.setattr("pipeline.production.PREMIUM_MOTION_MODELS", ("veo3.1:4k", "kling-3.0:720p"))
    assert _premium_model_routes() == [("veo3.1", "1080p"), ("kling-3.0", "1080p")]


def test_remotion_compositions_render_natively_at_1080p():
    source = (remotion_renderer.REMOTION_DIR / "src" / "Composition.tsx").read_text(encoding="utf-8")
    assert "MotionShot1080" in source
    assert "MotionShot4K" not in source
    renderer = (remotion_renderer.REMOTION_DIR.parent / "pipeline" / "remotion_renderer.py").read_text(encoding="utf-8")
    assert '"--scale=0.5"' in renderer
