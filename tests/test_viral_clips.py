from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from pipeline.viral_clips import (
    CaptionCue, ClipApproval, ClipCandidate, ClipMoment, build_licensed_request,
    _discover_entries, classify_clip_kind, rank_caption_moments, score_video_metadata,
)


def test_recent_high_velocity_video_outscores_old_slow_video():
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    recent = score_video_metadata({
        "title": "New AI model launch", "upload_date": "20260814", "view_count": 120_000,
        "like_count": 6_000, "comment_count": 900,
    }, ["ai", "model"], now)
    old = score_video_metadata({
        "title": "AI model discussion", "upload_date": "20260701", "view_count": 150_000,
        "like_count": 2_000, "comment_count": 100,
    }, ["ai", "model"], now)

    assert recent["viral_score"] > old["viral_score"]
    assert recent["views_per_day"] > old["views_per_day"]


def test_caption_ranking_prefers_topic_claim_and_avoids_sponsor_read():
    cues = [
        CaptionCue(start_seconds=0, end_seconds=8, text="Subscribe and use our sponsor discount code."),
        CaptionCue(start_seconds=8, end_seconds=16, text="The new open source video model launched today."),
        CaptionCue(start_seconds=16, end_seconds=24, text="It is twice as fast and this means local creators can test it."),
        CaptionCue(start_seconds=24, end_seconds=32, text="The benchmark is surprising, but there is one problem."),
        CaptionCue(start_seconds=48, end_seconds=56, text="Thanks for watching and smash the like button."),
    ]

    moments = rank_caption_moments(cues, ["open source", "video model"], max_moments=1)

    assert len(moments) == 1
    assert moments[0].start_seconds == 8
    assert "open source video model" in moments[0].transcript_excerpt.casefold()


def test_clip_kind_recognizes_keynotes_and_podcasts():
    assert classify_clip_kind("Opening keynote — AI Developer Conference") == "keynote"
    assert classify_clip_kind("The full podcast episode with the founder") == "podcast"


def test_search_uses_supported_yt_dlp_prefix(monkeypatch):
    captured = {}

    def fake_run(command, timeout=240):
        captured["source"] = command[-1]
        return {"entries": []}

    monkeypatch.setattr("pipeline.viral_clips._run_json", fake_run)

    assert _discover_entries("AI model keynote", 7) == []
    assert captured["source"] == "ytsearch7:AI model keynote"


def _candidate() -> ClipCandidate:
    return ClipCandidate(
        candidate_id="clip_123456789abc", video_id="abc123",
        source_url="https://www.youtube.com/watch?v=abc123", title="AI launch keynote",
        viral_score=80, relevance_score=90, combined_score=84,
        moments=[ClipMoment(
            start_seconds=30, end_seconds=52, score=92,
            transcript_excerpt="We are launching the model today.", reason="Strong topic match",
        )],
    )


def test_approved_cc_candidate_becomes_existing_ingest_contract():
    request = build_licensed_request(_candidate(), ClipApproval(
        rights_status="approved", rights_basis="creative_commons", approved_by="Editor",
        attribution="Example Company — AI launch keynote",
    ))

    assert request.clip_id == "clip_123456789abc"
    assert request.start_seconds == 30
    assert request.end_seconds == 52
    assert request.rights_basis == "creative_commons"


def test_written_permission_still_requires_proof_file():
    with pytest.raises(ValidationError, match="rights_proof_file"):
        build_licensed_request(_candidate(), ClipApproval(
            rights_status="approved", rights_basis="written_permission", approved_by="Editor",
            attribution="Example Company — AI launch keynote",
        ))


def test_missing_ranked_timestamp_cannot_be_ingested():
    candidate = _candidate().model_copy(update={"moments": []})
    with pytest.raises(ValueError, match="moment_index"):
        build_licensed_request(candidate, ClipApproval(
            rights_status="approved", rights_basis="creative_commons", approved_by="Editor",
            attribution="Example Company — AI launch keynote",
        ))
