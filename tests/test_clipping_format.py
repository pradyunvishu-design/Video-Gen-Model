import json

import pytest

from pipeline.clipping_format import ClipFormatRequest, build_clipping_spec
from pipeline.models import EpisodeProject, MediaAsset


def _project(tmp_path, *, basis="creative_commons", quality="accepted") -> EpisodeProject:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"manager-demo-placeholder")
    ledger = tmp_path / "rights.json"
    ledger.write_text(json.dumps({
        "start_seconds": 10,
        "end_seconds": 25,
        "source_url": "https://www.youtube.com/watch?v=abc123",
        "source_webpage_url": "https://www.youtube.com/watch?v=abc123",
        "output_sha256": "hash-123",
        "quality": {"status": quality},
        "rights": {"basis": basis},
    }), encoding="utf-8")
    return EpisodeProject(
        episode_id="episode_demo",
        scheduled_date="2026-08-08",
        media=[MediaAsset(
            id="licensed_clip_demo", kind="licensed_source_clip", path=str(clip),
            sha256="hash-123", qc_status="passed",
        )],
        rights=[{"asset_id": "licensed_clip_demo", "rights_ledger": str(ledger)}],
    )


def _request(**overrides) -> ClipFormatRequest:
    values = {
        "segment_id": "manager_demo",
        "media_asset_id": "licensed_clip_demo",
        "clip_type": "podcast",
        "headline": "The release that changed this week's AI conversation",
        "hook": "The impressive part is not the clip everyone reposted.",
        "context": "The original conversation explains what changed and what remains untested.",
        "key_points": ["The announcement", "The evidence", "The unanswered question"],
        "claim": "The release makes the workflow dramatically faster.",
        "evidence": "The official demonstration supports speed, not reliability across every use case.",
        "why_it_matters": "A repeatable workflow matters more than a single perfect example.",
        "source_label": "LICENSED PODCAST · EXAMPLE CREATOR",
        "target_seconds": 45,
    }
    values.update(overrides)
    return ClipFormatRequest(**values)


def test_builds_six_beat_source_first_segment(tmp_path):
    public = tmp_path / "public"
    spec = build_clipping_spec(_project(tmp_path), _request(), public)
    assert [scene["kind"] for scene in spec["scenes"]] == [
        "title", "source", "activity", "compare", "source", "title",
    ]
    assert spec["scenes"][1]["sourceLabel"].startswith("LICENSED PODCAST")
    assert spec["scenes"][1]["evidenceIds"] == ["asset:licensed_clip_demo"]
    assert spec["scenes"][4]["evidenceIds"] == ["asset:licensed_clip_demo"]
    assert spec["scenes"][4]["sourceStartSeconds"] > 0
    rendered_seconds = sum(scene["durationSeconds"] for scene in spec["scenes"]) - 1
    assert rendered_seconds == pytest.approx(45, abs=0.01)


def test_rejects_asset_without_accepted_rights_qc(tmp_path):
    with pytest.raises(PermissionError, match="did not pass"):
        build_clipping_spec(_project(tmp_path, quality="rejected"), _request(), tmp_path / "public")


def test_rejects_unlicensed_media_kind(tmp_path):
    project = _project(tmp_path)
    project.media[0].kind = "downloaded_video"
    with pytest.raises(PermissionError, match="licensed_source_clip"):
        build_clipping_spec(project, _request(), tmp_path / "public")
