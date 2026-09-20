from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.youtube_broll_bundle import BrollBundleError, load_approved_youtube_broll_bundle


def _record(media: Path, slot: int = 3) -> dict:
    return {
        "slot": slot,
        "media_file": str(media),
        "source_url": "https://www.youtube.com/watch?v=abc123",
        "source_start_seconds": 1,
        "source_end_seconds": 7,
        "title": "Licensed demo",
        "channel": "Creator",
        "rights_basis": "creative_commons",
        "rights_status": "approved",
        "qc_status": "passed",
    }


def test_loads_complete_approved_bundle(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"0" * 100_001)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"episode_id": "ep", "clips": [_record(media)]}))
    result = load_approved_youtube_broll_bundle(manifest, expected_slots={3}, episode_id="ep")
    assert result[3]["media_file"] == str(media.resolve())


def test_rejects_pending_rights(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"0" * 100_001)
    record = _record(media)
    record["rights_status"] = "pending_media_review"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"episode_id": "ep", "clips": [record]}))
    with pytest.raises(BrollBundleError, match="not rights-approved"):
        load_approved_youtube_broll_bundle(manifest, expected_slots={3}, episode_id="ep")


def test_rejects_missing_slot(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"episode_id": "ep", "clips": []}))
    with pytest.raises(BrollBundleError, match="missing YouTube B-roll slots"):
        load_approved_youtube_broll_bundle(manifest, expected_slots={3}, episode_id="ep")
