from datetime import datetime, timezone

from pipeline.models import Brief, EpisodeProject, Script, ScriptBeat, Shot, Source
from pipeline.youtube_broll import (
    BrollDiscoveryRequest,
    BrollScene,
    _iso_duration_seconds,
    _candidate,
    build_project_broll_request,
    discover_project_broll,
    plan_scene_queries,
)


def _project() -> EpisodeProject:
    source = Source(
        id="src_1",
        title="Example model launch",
        url="https://example.com/launch",
        publisher="Example AI",
        source_type="primary",
    )
    beat = ScriptBeat(
        id="beat_1",
        narration="The company showed its new video model generating a coherent product demo.",
        purpose="evidence",
        visual_direction="Show the official product demo and its generation interface.",
        source_ids=["src_1"],
    )
    return EpisodeProject(
        episode_id="episode_test",
        scheduled_date="2026-08-18",
        brief=Brief(
            title="Example",
            thesis="A useful test",
            episode_format="deep_dive",
            source_ids=["src_1"],
            claim_ids=[],
            why_now="New launch",
            approved=True,
        ),
        sources=[source],
        script=Script(
            title="Example AI launch",
            description="A test episode",
            tags=["ai"],
            thumbnail_text="THIS CHANGES VIDEO",
            beats=[beat],
        ),
        shots=[Shot(
            id="shot_1",
            beat_id="beat_1",
            asset_type="motion_graphic",
            prompt="Explain the product demo",
            start_seconds=0,
            duration_seconds=8,
        )],
    )


def _video(video_id: str, title: str, views: int) -> dict:
    return {
        "id": video_id,
        "snippet": {
            "title": title,
            "description": "Official launch demo for the new AI video model.",
            "channelTitle": "Example AI",
            "channelId": "channel_1",
            "publishedAt": "2026-08-17T12:00:00Z",
            "thumbnails": {"high": {"url": f"https://img.example/{video_id}.jpg"}},
        },
        "contentDetails": {"duration": "PT12M4S", "definition": "hd"},
        "statistics": {"viewCount": str(views), "likeCount": "900", "commentCount": "80"},
        "status": {"license": "creativeCommon", "embeddable": True},
    }


def test_iso_duration_parses_youtube_content_details():
    assert _iso_duration_seconds("PT1H2M3S") == 3723
    assert _iso_duration_seconds("PT12M4S") == 724


def test_query_planner_has_no_key_fallback():
    scene = BrollScene(
        scene_id="scene_1",
        beat_id="beat_1",
        narration="A company launched a video model.",
        visual_need="Show the official launch demo.",
        source_hints=["Example AI"],
    )

    plans, planner = plan_scene_queries([scene], api_key="")

    assert planner == "deterministic_fallback"
    assert plans[0]["scene_id"] == "scene_1"
    assert "official" in plans[0]["query"].casefold()


def test_project_request_keeps_scene_and_target_shot():
    request = build_project_broll_request(_project())

    assert len(request.scenes) == 1
    assert request.scenes[0].beat_id == "beat_1"
    assert request.scenes[0].shot_ids == ["shot_1"]
    assert "Example AI" in request.scenes[0].source_hints


def test_discovery_returns_exactly_three_candidates_and_downloads_nothing(monkeypatch, tmp_path):
    project = _project()
    request = BrollDiscoveryRequest(
        scenes=build_project_broll_request(project).scenes,
        candidates_per_scene=3,
        caption_candidates_per_scene=0,
        min_semantic_score=25,
    )
    monkeypatch.setattr(
        "pipeline.youtube_broll.plan_scene_queries",
        lambda scenes, api_key="": ([{
            "scene_id": scenes[0].scene_id,
            "query": "Example AI official launch demo",
            "visual_target": scenes[0].visual_need,
            "avoid": "reuploads",
        }], "openai_structured"),
    )
    monkeypatch.setattr(
        "pipeline.youtube_broll._search_video_ids",
        lambda query, request, api_key="": ["v1", "v2", "v3", "v4"],
    )
    monkeypatch.setattr(
        "pipeline.youtube_broll._video_details",
        lambda video_ids, api_key="": [
            _video("v1", "Official AI launch keynote", 120_000),
            _video("v2", "Official model product demo", 90_000),
            _video("v3", "Engineer explains the model", 70_000),
            _video("v4", "Unrelated reaction", 500_000),
        ],
    )
    monkeypatch.setattr(
        "pipeline.youtube_broll._channel_details",
        lambda channel_ids, api_key="": {
            "channel_1": {"subscriber_count": 500_000, "channel_title": "Example AI"}
        },
    )

    result = discover_project_broll(project, tmp_path, request)

    assert result["scene_count"] == 1
    assert result["candidate_count"] == 3
    manifest = (tmp_path / "broll_candidates.json").read_text(encoding="utf-8")
    assert "https://www.youtube.com/watch?v=" in manifest
    assert '"discovery_downloads_video": false' in manifest
    assert '"require_reputable_or_viral": true' in manifest
    assert not list(tmp_path.rglob("*.mp4"))


def test_discovery_rejects_small_nonviral_unofficial_channel(monkeypatch, tmp_path):
    project = _project()
    project.sources[0].publisher = "Different Company"
    request = BrollDiscoveryRequest(
        scenes=build_project_broll_request(project).scenes,
        candidates_per_scene=3,
        caption_candidates_per_scene=0,
    )
    monkeypatch.setattr(
        "pipeline.youtube_broll.plan_scene_queries",
        lambda scenes, api_key="": ([{
            "scene_id": scenes[0].scene_id,
            "query": "AI demo",
            "visual_target": scenes[0].visual_need,
            "avoid": "reuploads",
        }], "deterministic_fallback"),
    )
    monkeypatch.setattr(
        "pipeline.youtube_broll._search_video_ids",
        lambda query, request, api_key="": ["small"],
    )
    monkeypatch.setattr(
        "pipeline.youtube_broll._video_details",
        lambda video_ids, api_key="": [_video("small", "Random AI demo", 8_000)],
    )
    monkeypatch.setattr(
        "pipeline.youtube_broll._channel_details",
        lambda channel_ids, api_key="": {
            "channel_1": {"subscriber_count": 2_000, "channel_title": "Small Channel"}
        },
    )

    result = discover_project_broll(project, tmp_path, request)

    assert result["candidate_count"] == 0


def test_product_name_in_tutorial_channel_is_not_treated_as_official():
    scene = BrollScene(
        scene_id="scene_1",
        beat_id="beat_1",
        narration="Anthropic demonstrated Claude Code.",
        visual_need="Show the Claude Code interface.",
        source_hints=["Anthropic", "Claude Code launch"],
        publisher_hints=["Anthropic"],
    )
    raw = _video("tutorial", "Claude Code tutorial", 1_000)
    raw["snippet"]["channelTitle"] = "Learn Claude Code"
    raw["snippet"]["publishedAt"] = "2026-01-01T12:00:00Z"
    candidate = _candidate(
        scene,
        {"query": "Claude Code", "visual_target": scene.visual_need},
        raw,
        datetime.now(timezone.utc),
        BrollDiscoveryRequest(scenes=[scene]),
        {"subscriber_count": 20_000},
    )

    assert candidate.official_channel_match is False
    assert candidate.quality_gate_passed is False


def test_recognized_publishers_only_rejects_large_unofficial_creator():
    scene = BrollScene(
        scene_id="scene_1", beat_id="beat_1",
        narration="A browser agent completed the task.",
        visual_need="Show a browser agent completing a form.",
        publisher_hints=["Chrome for Developers"],
    )
    raw = _video("creator", "Browser agents are wild", 2_000_000)
    raw["snippet"]["channelTitle"] = "Huge AI Creator"
    candidate = _candidate(
        scene,
        {"query": "browser agent", "visual_target": scene.visual_need},
        raw,
        datetime.now(timezone.utc),
        BrollDiscoveryRequest(
            scenes=[scene], recognized_publishers_only=True,
            recognized_publishers=["Chrome for Developers", "GitLab"],
        ),
        {"subscriber_count": 2_000_000},
    )

    assert candidate.viral_video is True
    assert candidate.recognized_publisher_match is False
    assert candidate.quality_gate_passed is False
    assert "not_recognized_publisher" in candidate.quality_gate_reasons


def test_recognized_organization_can_pass_below_subscriber_floor():
    scene = BrollScene(
        scene_id="scene_1", beat_id="beat_1",
        narration="GitLab scanned the pipeline.",
        visual_need="Show a CI pipeline security scan.",
        publisher_hints=["Different publisher"],
    )
    raw = _video("gitlab", "Add security scanning to CI/CD", 10_000)
    raw["snippet"]["channelTitle"] = "GitLab"
    candidate = _candidate(
        scene,
        {"query": "GitLab security scan", "visual_target": scene.visual_need},
        raw,
        datetime.now(timezone.utc),
        BrollDiscoveryRequest(
            scenes=[scene], recognized_publishers_only=True,
            recognized_publishers=["GitLab"], min_channel_subscribers=250_000,
        ),
        {"subscriber_count": 47_700},
    )

    assert candidate.official_channel_match is False
    assert candidate.recognized_publisher_match is True
    assert candidate.source_tier == "recognized_organization"
    assert candidate.quality_gate_passed is True
