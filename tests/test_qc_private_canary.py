from pathlib import Path

from pipeline import qc
from pipeline.models import EpisodeProject, Script, ScriptBeat, Shot, Source


def _project() -> EpisodeProject:
    words = " ".join(f"word{index}" for index in range(70))
    project = EpisodeProject(
        episode_id="private-canary-test",
        scheduled_date="2026-08-13",
        episode={"private_canary": True, "target_minutes": 0.5, "script_word_min": 65, "script_word_max": 80},
        sources=[Source(id="source", title="Primary source", url="https://example.com/source")],
        script=Script(
            title="Canary", description="Test", tags=[], thumbnail_text="70B ON FOUR GIGS",
            beats=[ScriptBeat(id="beat", narration=words, purpose="evidence", visual_direction="Show proof", source_ids=["source"])],
        ),
        shots=[
            Shot(
                id=f"shot-{index}", beat_id="beat", asset_type="screenshot", source_id="source",
                duration_seconds=4.5, rights_note="Public source captured for commentary.",
            )
            for index in range(7)
        ],
        rights=[{"source_id": "source", "basis": "commentary"}],
        artifacts={"captions": "captions.json", "thumbnails": "thumbnails"},
        qc={"thumbnails": {"passed": True}},
    )
    return project


def test_run_qc_accepts_exact_thirty_second_private_canary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(qc, "probe", lambda _: {
        "format": {"duration": "30.000", "bit_rate": "4000000"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "30/1", "bit_rate": "3500000"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    })
    monkeypatch.setattr(qc, "analyze_media", lambda *_args, **_kwargs: {"passed": True, "failures": [], "warnings": []})
    report = qc.run_qc(_project(), tmp_path / "canary.mp4")
    assert report["passed"]
    assert report["duration_seconds"] == 30.0
    assert report["shot_count"] == 7


def test_run_qc_rejects_private_canary_outside_exact_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(qc, "probe", lambda _: {
        "format": {"duration": "30.200", "bit_rate": "4000000"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "30/1", "bit_rate": "3500000"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    })
    monkeypatch.setattr(qc, "analyze_media", lambda *_args, **_kwargs: {"passed": True, "failures": [], "warnings": []})
    report = qc.run_qc(_project(), tmp_path / "canary.mp4")
    assert not report["passed"]
    assert any("runtime" in failure for failure in report["failures"])
