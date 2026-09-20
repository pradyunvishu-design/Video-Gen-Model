from pathlib import Path

from pipeline import qc
from pipeline.models import EpisodeProject, Script, ScriptBeat, Shot, Source


def _project() -> EpisodeProject:
    words = " ".join(f"word{index}" for index in range(305))
    return EpisodeProject(
        episode_id="short-news-test",
        scheduled_date="2026-08-14",
        episode={
            "short_news_special": True, "target_minutes": 2,
            "script_word_min": 285, "script_word_max": 325,
            "shot_min": 20, "shot_max": 30,
        },
        sources=[Source(id="source", title="Primary source", url="https://example.com/source")],
        script=Script(
            title="Buzz", description="Test", tags=[], thumbnail_text="AGENTS WITH RECEIPTS",
            beats=[ScriptBeat(
                id="beat", narration=words, purpose="evidence", visual_direction="Show proof",
                source_ids=["source"],
            )],
        ),
        shots=[
            Shot(
                id=f"shot-{index}", beat_id="beat", asset_type="screenshot", source_id="source",
                duration_seconds=5, rights_note="Public source captured for commentary.",
            )
            for index in range(24)
        ],
        rights=[{"source_id": "source", "basis": "commentary"}],
        artifacts={"captions": "captions.json", "thumbnails": "thumbnails"},
        qc={"thumbnails": {"passed": True}},
    )


def _probe(duration: str) -> dict:
    return {
        "format": {"duration": duration, "bit_rate": "4000000"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
             "avg_frame_rate": "30/1", "bit_rate": "3500000"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }


def test_run_qc_accepts_exact_two_minute_short_news(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(qc, "probe", lambda _: _probe("120.000"))
    monkeypatch.setattr(qc, "analyze_media", lambda *_args, **_kwargs: {"passed": True, "failures": [], "warnings": []})
    report = qc.run_qc(_project(), tmp_path / "buzz.mp4")
    assert report["passed"]
    assert report["duration_seconds"] == 120.0
    assert report["shot_count"] == 24


def test_run_qc_rejects_two_minute_short_news_outside_exact_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(qc, "probe", lambda _: _probe("120.200"))
    monkeypatch.setattr(qc, "analyze_media", lambda *_args, **_kwargs: {"passed": True, "failures": [], "warnings": []})
    report = qc.run_qc(_project(), tmp_path / "buzz.mp4")
    assert not report["passed"]
    assert any("runtime" in failure for failure in report["failures"])
