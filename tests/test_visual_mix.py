from pipeline.models import EpisodeProject, Script, ScriptBeat, Shot, Source
from pipeline.visual_mix import apply_house_mix, apply_seedance_motion_split, review_visual_mix


def _base_project(shots: list[Shot]) -> EpisodeProject:
    source = Source(id="src", title="Evidence", url="https://example.com/article")
    beat = ScriptBeat(
        id="beat", narration="A company demonstrated a new model.", purpose="evidence",
        visual_direction="Show the launch and the reported evidence.", source_ids=["src"],
    )
    return EpisodeProject(
        episode_id="mix", scheduled_date="2026-08-22", sources=[source],
        script=Script(
            title="Mix", description="test", tags=["ai"], thumbnail_text="THIS WEEK CHANGED AI",
            beats=[beat],
        ),
        shots=shots,
    )


def test_house_mix_is_duration_weighted_55_20_15_10():
    shots = [
        Shot(
            id=f"shot_{index:03d}", beat_id="beat", asset_type="screenshot",
            source_id="src", prompt="launch evidence", duration_seconds=4,
        )
        for index in range(110)
    ]
    apply_house_mix(shots, 600)
    project = _base_project(shots)
    report = review_visual_mix(project, require_assets=False)

    assert report["passed"], report["failures"]
    assert report["categories"]["youtube_broll"]["seconds"] == 330
    assert report["categories"]["article_evidence"]["seconds"] == 120
    assert report["categories"]["motion_graphics"]["seconds"] == 90
    assert report["categories"]["miscellaneous"]["seconds"] == 60
    assert max(shot.duration_seconds for shot in shots if shot.visual_category == "motion_graphics") <= 8


def test_motion_heavy_plan_is_rejected():
    shots = [
        Shot(
            id=f"shot_{index:03d}", beat_id="beat", asset_type="motion_graphic",
            visual_category="motion_graphics", fallback_reason="no_relevant_rights_cleared_footage",
            duration_seconds=5,
        )
        for index in range(20)
    ]
    report = review_visual_mix(_base_project(shots), require_assets=False)

    assert not report["passed"]
    assert any("motion_graphics is 100.0%" in failure for failure in report["failures"])


def test_half_of_motion_slots_route_to_seedance_without_changing_house_mix():
    shots = [
        Shot(
            id=f"shot_{index:03d}", beat_id="beat", asset_type="motion_graphic",
            visual_category="motion_graphics", prompt=(
                "Show the workflow routing through three connected stages"
                if index % 2 == 0 else "Show the exact benchmark table"
            ), fallback_reason="no_relevant_rights_cleared_footage", duration_seconds=6,
        )
        for index in range(10)
    ]
    apply_seedance_motion_split(shots, share=0.5, enabled=True)

    seedance = [shot for shot in shots if shot.motion_template == "seedance_editorial"]
    assert len(seedance) == 5
    assert all(shot.asset_type == "generated_video" for shot in seedance)
    assert all(shot.motion_style == "locked" and shot.transition == "cut" for shot in seedance)
    assert all(shot.visual_category == "motion_graphics" for shot in shots)
    assert sum(shot.duration_seconds for shot in shots) == 60
    assert sum("workflow" in shot.prompt.casefold() for shot in seedance) == 5


def test_render_ready_mix_requires_rights_alignment_and_unique_youtube_assets():
    shots: list[Shot] = []
    for index in range(11):
        shots.append(Shot(
            id=f"yt_{index}", beat_id="beat", asset_type="official_demo",
            visual_category="youtube_broll", asset_path=f"clip_{index}.mp4",
            alignment_score=80, duration_seconds=5,
        ))
    for index in range(4):
        shots.append(Shot(
            id=f"article_{index}", beat_id="beat", asset_type="screenshot",
            visual_category="article_evidence", source_id="src", asset_path=f"article_{index}.png",
            duration_seconds=5,
        ))
    for index in range(3):
        shots.append(Shot(
            id=f"motion_{index}", beat_id="beat", asset_type="motion_graphic",
            visual_category="motion_graphics", fallback_reason="no_relevant_rights_cleared_footage",
            duration_seconds=5,
        ))
    for index in range(2):
        shots.append(Shot(
            id=f"misc_{index}", beat_id="beat", asset_type="screen_recording",
            visual_category="miscellaneous", asset_path=f"misc_{index}.mp4", duration_seconds=5,
        ))
    project = _base_project(shots)
    project.rights = [
        {
            "asset_path": f"clip_{index}.mp4",
            "source_url": f"https://www.youtube.com/watch?v=video{index}",
            "capture_mode": "licensed_timestamped_excerpt",
            "rights_basis": "creative_commons",
            "muted": True,
        }
        for index in range(11)
    ]

    report = review_visual_mix(project, require_assets=True)
    assert report["passed"], report["failures"]

    project.rights[0]["rights_basis"] = ""
    failed = review_visual_mix(project, require_assets=True)
    assert not failed["passed"]
    assert any("yt_0 lacks" in failure for failure in failed["failures"])
