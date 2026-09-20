from datetime import datetime, timedelta, timezone

from pipeline.models import Brief, DeliveryDirection, EpisodeProject, Script, ScriptBeat, Source
from pipeline import production, product_demo
from pipeline.production import _narration_blocks
from pipeline.storyboard import build_shot_plan
from pipeline.weekly_news import _validate_plan, rank_clusters, score_cluster


def _source(source_id: str, title: str, *, cluster: str = "", role: str = "primary_evidence", source_type: str = "primary") -> Source:
    return Source(
        id=source_id,
        title=title,
        url=f"https://example.com/{source_id}",
        publisher=source_id,
        published_at=datetime.now(timezone.utc) - timedelta(hours=6),
        source_type=source_type,
        signal_role=role,
        cluster_id=cluster,
        entities=[title.split()[0], title.split()[1]],
        trend_score=25,
    )


def test_weekly_clustering_joins_independent_coverage_but_not_unrelated_news():
    sources = [
        _source("a", "OpenAI releases Nova video model"),
        _source("b", "OpenAI Nova video model launches", role="independent_reporting", source_type="secondary"),
        _source("c", "NVIDIA announces a new inference chip"),
        _source("d", "NVIDIA inference chip reaches developers", role="independent_reporting", source_type="secondary"),
    ]
    clusters = rank_clusters(sources)
    assert len(clusters) == 2
    assert sorted(len(item["source_ids"]) for item in clusters) == [2, 2]


def test_significance_rewards_confirmed_multi_source_news():
    confirmed = [
        _source("primary", "Acme launches a major video model"),
        _source("report", "Acme major video model launches", role="independent_reporting", source_type="secondary"),
    ]
    noisy = [
        _source("newsletter", "Rumor about an Acme model", role="newsletter_lead", source_type="secondary"),
        _source("community", "People discuss an Acme rumor", role="community_signal", source_type="community"),
    ]
    assert score_cluster(confirmed)["score"] > score_cluster(noisy)["score"]


def test_weekly_radar_marks_the_reference_three_day_hot_window():
    now = datetime.now(timezone.utc)
    fresh = _source("fresh", "Acme launches a major video model")
    old = _source("old", "Acme launches a major video model")
    fresh.published_at = now - timedelta(hours=48)
    old.published_at = now - timedelta(days=6)

    fresh_score = score_cluster([fresh], now)
    old_score = score_cluster([old], now)

    assert fresh_score["inside_72h_hot_window"] is True
    assert old_score["inside_72h_hot_window"] is False
    assert fresh_score["score"] > old_score["score"]


def test_weekly_plan_requires_evidence_and_keeps_model_tests_limited():
    sources = []
    stories = []
    for index in range(5):
        cluster = f"cluster_{index}"
        left = _source(f"p{index}", f"Company{index} launches model update", cluster=cluster)
        right = _source(
            f"r{index}", f"Company{index} model update launches", cluster=cluster,
            role="independent_reporting", source_type="secondary",
        )
        sources.extend([left, right])
        stories.append({
            "story_id": f"story_{index}", "headline": f"Story {index}",
            "source_ids": [left.id, right.id], "why_it_matters": "It changes a real workflow.",
            "category": ["model_release", "open_source", "product", "research", "hardware"][index],
            "segment_seconds": 80, "model_test_candidate": index == 0,
            "demo_goal": "Compare one harmless prompt" if index == 0 else "", "humor_angle": "",
        })
    plan = {
        "show_title": "NEWS WEEKLY", "episode_title": "This Week in AI",
        "thumbnail_text": "THE WEEK CHANGED", "cold_open": "Five changes matter.",
        "throughline": "AI products are becoming easier to test.", "stories": stories,
    }
    assert _validate_plan(plan, sources) == plan


def test_narration_blocks_merge_short_beats_for_a_more_consistent_performance():
    beats = [
        ScriptBeat(
            id=f"beat_{index}", narration="This is a natural sentence that continues the same story.",
            purpose="analysis", visual_direction="Show evidence",
            delivery=DeliveryDirection(pause_after_ms=350),
        )
        for index in range(4)
    ]
    blocks = _narration_blocks(beats)
    assert len(blocks) == 1
    assert blocks[0]["beat_ids"] == ["beat_0", "beat_1", "beat_2", "beat_3"]
    assert "\n\n" not in blocks[0]["text"]


def test_weekly_storyboard_contains_the_branded_news_intro():
    source = _source("src", "Company launches model update", cluster="cluster")
    brief = Brief(
        title="Weekly", thesis="The week", episode_format="weekly_roundup",
        source_ids=[source.id], claim_ids=[], why_now="Now",
    )
    beats = [
        ScriptBeat(id="hook", narration="The biggest changes arrived together this week.", purpose="hook", visual_direction="Show top stories", source_ids=[source.id]),
        ScriptBeat(id="intro", narration="Welcome to News Weekly, the news worth knowing.", purpose="show_intro", visual_direction="News Weekly", source_ids=[]),
    ] + [
        ScriptBeat(id=f"beat_{index}", narration="One useful explanation follows from the source.", purpose="analysis", visual_direction="Explain the change", source_ids=[source.id])
        for index in range(18)
    ]
    project = EpisodeProject(
        episode_id="weekly", scheduled_date="2026-08-08", episode={"format": "weekly_roundup"},
        brief=brief, sources=[source],
        script=Script(title="Weekly", description="Weekly", tags=[], thumbnail_text="THE WEEK CHANGED", beats=beats),
    )
    shots = build_shot_plan(project, 600)
    assert any(shot.beat_id == "intro" and shot.motion_template == "news_intro" for shot in shots)


def test_approved_model_test_runs_inside_episode_production_stage(monkeypatch, tmp_path):
    project = EpisodeProject(
        episode_id="weekly_demo", scheduled_date="2026-08-08",
        episode={"model_test_queue": [{
            "story_id": "story_demo", "website": "https://example.com/demo",
            "goal": "Show the public product demo clearly", "profile": "public_isolated",
            "allowed_hosts": ["example.com"], "inputs": {}, "allow_generation": False,
            "status": "approved_for_capture", "source_ids": ["src"],
        }]},
    )
    clip = tmp_path / "demo.mp4"
    clip.write_bytes(b"video")
    monkeypatch.setattr(product_demo, "generate_demo", lambda spec, output: {
        "video": str(clip), "quality": {"status": "accepted"},
    })

    result = production._run_configured_model_tests(project, tmp_path)

    assert result[0]["status"] == "complete"
    assert project.episode["model_test_queue"][0]["video"] == str(clip)
    assert project.episode["model_test_queue"][0]["status"] == "complete"
