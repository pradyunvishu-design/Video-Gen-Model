from datetime import date

from pipeline import production
from pipeline.models import EpisodeProject, MediaAsset, Shot
from pipeline.production import _meet_magic_hour_quality_floor, _reconcile_credits


def test_final_magic_hour_charge_reconciles_submission_estimate():
    project = EpisodeProject(episode_id="episode_test", scheduled_date=date.today().isoformat())
    project.costs["magic_hour_credits"] = 25

    charged = _reconcile_credits(project, {"credits_charged": 25}, {"credits_charged": 40})

    assert charged == 40
    assert project.costs["magic_hour_credits"] == 40


def test_quality_floor_upgrades_a_hero_take_instead_of_buying_filler(monkeypatch, tmp_path):
    still = tmp_path / "hero.png"
    still.write_bytes(b"image")
    rendered = tmp_path / "premium.mp4"
    project = EpisodeProject(
        episode_id="episode_quality_floor", scheduled_date=date.today().isoformat(),
        episode={"minimum_magic_hour_credits": 100, "credit_limit": 200},
        shots=[Shot(id="shot_001", beat_id="beat_01", asset_type="generated_video", prompt="AI chip", asset_path="old.mp4")],
        media=[MediaAsset(id="motion_plate_shot_001", kind="motion_plate", path=str(still), credits=0)],
        costs={"magic_hour_credits": 50},
    )
    monkeypatch.setattr(production, "save_project", lambda *_: None)
    monkeypatch.setattr(production.magichour, "upload_file", lambda *_: "api/hero.png")
    monkeypatch.setattr(
        production.magichour, "image_to_video",
        lambda *_args, **_kwargs: {"id": "video_1", "credits_charged": 50},
    )
    monkeypatch.setattr(
        production.magichour, "wait_video",
        lambda *_: {"id": "video_1", "credits_charged": 50},
    )
    monkeypatch.setattr(production.magichour, "download_all", lambda *_: [rendered])
    monkeypatch.setattr(
        production.visual_qc, "inspect_motion",
        lambda *_: {"passed": True, "notes": ["clean motion"]},
    )

    result = _meet_magic_hour_quality_floor(project, tmp_path)

    assert result["passed"]
    assert result["actual"] == 100
    assert project.shots[0].asset_path == str(rendered)
    assert any(asset.id == "premium_motion_shot_001_1" for asset in project.media)
