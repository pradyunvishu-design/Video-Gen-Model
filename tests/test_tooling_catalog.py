from __future__ import annotations

from pipeline.tooling_catalog import (
    catalog_sha256,
    load_video_production_sources,
    method_provenance_for,
    production_stack_receipt,
)


def test_catalog_covers_required_repository_inputs() -> None:
    catalog = load_video_production_sources()
    identifiers = {item["id"] for item in catalog["sources"]}
    assert {
        "openmontage",
        "hyperframes",
        "recreate-video-motion-framework",
        "video-script-content-system",
        "youtube-script-writer",
        "creator-studio-script-writer",
        "openreels-script-critic",
        "ai-labs-script-formats",
        "eachlabs-skills",
        "video-use",
        "vidrush",
    } <= identifiers


def test_recreate_video_is_routed_to_motion_only() -> None:
    sources = {item["source"] for item in method_provenance_for("motion")}
    assert "https://github.com/li-yunshen-alec/recreate-video" in sources
    script_sources = {item["source"] for item in method_provenance_for("script")}
    assert "https://github.com/li-yunshen-alec/recreate-video" not in script_sources


def test_script_provenance_is_stage_scoped() -> None:
    sources = {item["source"] for item in method_provenance_for("script")}
    assert "https://github.com/azizaeffendi/video-script-content-system" in sources
    assert "https://github.com/rahulanand1103/youtube-script-writer" in sources
    assert "https://github.com/SkillMedev/creator-studio" in sources
    assert "https://github.com/tsensei/OpenReels" in sources
    assert "https://github.com/ailabs-393/ai-labs-claude-skills" in sources
    assert "https://github.com/calesthio/OpenMontage" not in sources


def test_production_receipt_is_stable_and_secret_free() -> None:
    receipt = production_stack_receipt()
    assert receipt["catalog_sha256"] == catalog_sha256()
    serialized = str(receipt).casefold()
    assert "api_key" not in serialized
    assert "secret" not in serialized
    assert all(str(item["source"]).startswith("https://") for item in receipt["sources"])
