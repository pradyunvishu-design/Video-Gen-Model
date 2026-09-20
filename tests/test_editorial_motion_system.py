from pathlib import Path

from pipeline.editorial_motion_system import (
    MOTION_PATTERN_IDS,
    MOTION_PATTERNS_BY_SCENE,
    build_editorial_spec,
    validate_editorial_spec,
)
from pipeline.models import EpisodeProject, Script, ScriptBeat


def _scene(scene_id: str, *, kind: str = "title", anchor: str = "left") -> dict:
    return {
        "id": scene_id, "kind": kind, "durationSeconds": 4, "anchor": anchor,
        "accent": "#F2F1ED", "logos": [], "messages": [],
    }


def test_editorial_spec_rejects_missing_source_asset(tmp_path: Path) -> None:
    spec = {"episodeId": "test", "scenes": [{**_scene("source", kind="source"), "sourceAsset": "missing.png", "sourceLabel": "Official", "sourceUrl": "https://example.com/source", "evidenceIds": ["src-1"]}]}
    report = validate_editorial_spec(spec, tmp_path)
    assert not report.passed
    assert any("missing source asset" in error for error in report.errors)


def test_editorial_spec_reports_duration_and_repetition(tmp_path: Path) -> None:
    spec = {"episodeId": "test", "scenes": [_scene("a"), _scene("b"), _scene("c")]}
    report = validate_editorial_spec(spec, tmp_path)
    assert report.passed
    assert report.duration_seconds == 11.6
    assert report.warnings


def test_episode_project_converts_to_editorial_spec(tmp_path: Path) -> None:
    project = EpisodeProject(
        episode_id="episode-1", scheduled_date="2026-08-08",
        script=Script(
            title="Test", description="Test", tags=[], thumbnail_text="Three useful AI updates",
            beats=[ScriptBeat(
                id="hook", narration="This is the useful part of the launch.", purpose="hook",
                visual_direction="Show the result, then explain the evidence.",
            )],
        ),
    )
    spec = build_editorial_spec(project, tmp_path)
    assert spec["episodeId"] == "episode-1"
    assert spec["scenes"][0]["kind"] == "title"
    assert spec["scenes"][0]["motionPattern"] in MOTION_PATTERNS_BY_SCENE["title"]
    assert validate_editorial_spec(spec, tmp_path).passed


def test_motion_catalog_has_at_least_fifty_routable_patterns() -> None:
    assert len(MOTION_PATTERN_IDS) >= 50
    assert all(len(patterns) >= 6 for patterns in MOTION_PATTERNS_BY_SCENE.values())
    assert "terminal-diff-apply" in MOTION_PATTERN_IDS
    assert "terminal-tool-call" in MOTION_PATTERN_IDS


def test_editorial_spec_rejects_pattern_from_wrong_family(tmp_path: Path) -> None:
    spec = {"episodeId": "test", "scenes": [{**_scene("wrong"), "motionPattern": "terminal-command-run"}]}
    report = validate_editorial_spec(spec, tmp_path)
    assert not report.passed
    assert any("does not match scene kind" in error for error in report.errors)


def test_editorial_spec_rejects_compare_without_claim_and_evidence(tmp_path: Path) -> None:
    spec = {"episodeId": "test", "scenes": [{**_scene("compare", kind="compare"), "claim": "", "evidence": ""}]}
    report = validate_editorial_spec(spec, tmp_path)
    assert not report.passed
    assert any("require both claim and evidence" in error for error in report.errors)


def test_editorial_spec_rejects_decorative_yellow_and_vibe_purple(tmp_path: Path) -> None:
    for accent in ("#E8E32D", "#A855F7"):
        spec = {"episodeId": "test", "scenes": [{**_scene("bad-accent"), "accent": accent}]}
        report = validate_editorial_spec(spec, tmp_path)
        assert not report.passed
        assert any("yellow and purple accents are forbidden" in error for error in report.errors)


def test_editorial_spec_rejects_source_focus_outside_capture(tmp_path: Path) -> None:
    capture = tmp_path / "source.png"
    capture.write_bytes(b"placeholder")
    spec = {
        "episodeId": "test",
        "scenes": [{
            **_scene("source", kind="source"),
            "sourceAsset": "source.png",
            "sourceLabel": "Official",
            "sourceUrl": "https://example.com/source",
            "evidenceIds": ["src-1"],
            "sourceFocus": {"x": .8, "y": .2, "width": .3, "height": .2, "label": "Claim"},
        }],
    }
    report = validate_editorial_spec(spec, tmp_path)
    assert not report.passed
    assert any("extends outside" in error for error in report.errors)


def test_editorial_spec_rejects_source_without_evidence_reference(tmp_path: Path) -> None:
    capture = tmp_path / "source.png"
    capture.write_bytes(b"placeholder")
    spec = {"episodeId": "test", "scenes": [{
        **_scene("source", kind="source"), "sourceAsset": "source.png", "sourceLabel": "Official",
        "sourceUrl": "https://example.com/source", "evidenceIds": [],
    }]}
    report = validate_editorial_spec(spec, tmp_path)
    assert not report.passed
    assert any("evidence ID" in error for error in report.errors)
