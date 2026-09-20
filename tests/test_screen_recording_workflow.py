from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from pipeline import production, screen_recording_workflow, worker
from pipeline.models import (
    Brief, CaptureArtifact, CaptureRecord, EpisodeProject, MediaAsset,
    Script, ScriptBeat, Shot, Source,
)
from pipeline.project_store import load_project, save_project


def _project(episode_id: str = "episode_capture") -> EpisodeProject:
    source = Source(id="src_product", title="Official product", url="https://example.com/product")
    return EpisodeProject(
        episode_id=episode_id,
        scheduled_date=date.today().isoformat(),
        sources=[source],
        brief=Brief(
            title="Product workflow", thesis="The workflow changed", episode_format="tool_test",
            source_ids=[source.id], claim_ids=[], why_now="The product launched",
        ),
        script=Script(
            title="Product workflow", description="A source-backed walkthrough",
            tags=["AI"], thumbnail_text="THE WORKFLOW CHANGED",
            beats=[
                ScriptBeat(
                    id="beat_source", narration="The official page shows the workflow.",
                    purpose="evidence", visual_direction="Record the public workflow section.",
                    source_ids=[source.id],
                ),
                ScriptBeat(
                    id="beat_demo", narration="The approved test shows the result.",
                    purpose="model_test", visual_direction="Record the approved product test.",
                    source_ids=[source.id],
                ),
            ],
        ),
        shots=[
            Shot(id="shot_public", beat_id="beat_source", asset_type="screen_recording", source_id=source.id),
            Shot(id="shot_demo", beat_id="beat_demo", asset_type="official_demo", source_id=source.id),
        ],
        episode={"model_test_queue": [{
            "story_id": "story_product", "source_ids": [source.id],
            "goal": "Show the approved product result", "website": "https://example.com/product",
            "allowed_hosts": ["example.com"], "inputs": {"prompt": "A harmless test prompt"},
            "allow_generation": True, "profile": "google_manual", "status": "approved_for_capture",
        }]},
    )


def _accepted_capture(source_id: str, path: Path) -> CaptureRecord:
    return CaptureRecord(
        source_id=source_id,
        requested_url="https://example.com/product",
        final_url="https://example.com/product",
        page_title="Official product",
        artifacts=[CaptureArtifact(
            kind="screen_recording", path=str(path), label="Controlled overview",
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            source_url="https://example.com/product", capture_mode="cinematic_scroll",
            quality={"status": "accepted", "width": 1920, "height": 1080, "fps": 30},
        )],
    )


def test_manifest_requires_episode_owned_qc_accepted_recordings(tmp_path: Path) -> None:
    episode_dir = tmp_path / "episode_capture"
    public_clip = episode_dir / "captures" / "public.mp4"
    demo_clip = episode_dir / "model_tests" / "demo.mp4"
    public_clip.parent.mkdir(parents=True)
    demo_clip.parent.mkdir(parents=True)
    public_clip.write_bytes(b"public-capture")
    demo_clip.write_bytes(b"product-demo")
    project = _project()
    project.shots[0].asset_path = str(public_clip)
    project.shots[1].asset_path = str(demo_clip)
    project.captures = [_accepted_capture("src_product", public_clip)]
    project.media = [MediaAsset(
        id="browser_demo_story_product", kind="browser_demo", path=str(demo_clip),
        source_id="src_product", sha256=hashlib.sha256(demo_clip.read_bytes()).hexdigest(),
        qc_status="passed",
    )]
    project.episode["model_test_queue"][0].update({
        "status": "complete", "video": str(demo_clip),
        "metadata": {
            "video": str(demo_clip),
            "video_sha256": hashlib.sha256(demo_clip.read_bytes()).hexdigest(),
            "quality": {"status": "accepted", "width": 1920, "height": 1080, "fps": 30},
        },
    })

    review = screen_recording_workflow.review_screen_recording_readiness(project, episode_dir)
    manifest = screen_recording_workflow.build_screen_recording_manifest(project, episode_dir)

    assert review == {
        "passed": True, "required_shots": 2, "ready_shots": 2,
        "recording_count": 2, "failures": [],
    }
    assert {item["kind"] for item in manifest["recordings"]} == {"public_source", "product_demo"}
    assert all(len(item["sha256"]) == 64 for item in manifest["recordings"])


def test_manifest_rejects_recording_outside_episode(tmp_path: Path) -> None:
    episode_dir = tmp_path / "episode_capture"
    episode_dir.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"not-owned-by-episode")
    project = _project()
    project.shots[0].asset_path = str(outside)
    project.shots[1].asset_type = "motion_graphic"
    project.captures = [_accepted_capture("src_product", outside)]

    review = screen_recording_workflow.review_screen_recording_readiness(project, episode_dir)

    assert not review["passed"]
    assert any("outside the episode directory" in failure for failure in review["failures"])


def test_episode_capture_stage_assigns_and_persists_manifest(monkeypatch, tmp_path: Path) -> None:
    project = _project()
    episode_dir = tmp_path / project.episode_id
    episode_dir.mkdir()
    save_project(project, episode_dir)
    public_clip = episode_dir / "captures" / "public.mp4"
    demo_clip = episode_dir / "model_tests" / "story_product" / "browser_demo_editorial_1080p.mp4"
    public_clip.parent.mkdir()
    demo_clip.parent.mkdir(parents=True)
    public_clip.write_bytes(b"public-capture")
    demo_clip.write_bytes(b"approved-demo")

    def fake_capture(current, _run_dir, *, canary=False):
        current.shots[0].asset_path = str(public_clip)
        current.captures = [_accepted_capture("src_product", public_clip)]
        return {"src_product": {"recording": str(public_clip)}}

    def fake_tests(current, _run_dir):
        item = current.episode["model_test_queue"][0]
        item.update({
            "status": "complete", "video": str(demo_clip),
            "metadata": {
                "video": str(demo_clip),
                "video_sha256": hashlib.sha256(demo_clip.read_bytes()).hexdigest(),
                "quality": {"status": "accepted", "width": 1920, "height": 1080, "fps": 30},
            },
        })
        return [{"story_id": item["story_id"], "status": "complete", "video": str(demo_clip)}]

    monkeypatch.setattr(production, "EPISODE_DATA_DIR", tmp_path)
    monkeypatch.setattr(production, "_capture_and_assign", fake_capture)
    monkeypatch.setattr(production, "_run_configured_model_tests", fake_tests)

    result = production.acquire_episode_screen_recordings(project.episode_id)
    saved = load_project(episode_dir)

    assert result["status"] == "screen_recordings_ready"
    assert result["qc"]["passed"]
    assert Path(result["manifest"]).is_file()
    assert saved.shots[0].asset_path == str(public_clip)
    assert saved.shots[1].asset_path == str(demo_clip)
    assert saved.artifacts["screen_recording_manifest"] == result["manifest"]


def test_worker_exposes_screen_recording_stage() -> None:
    assert "acquire_screen_recordings" in worker.SUPPORTED_STAGES
