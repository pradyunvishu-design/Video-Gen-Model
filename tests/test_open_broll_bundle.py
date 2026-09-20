from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "output" / "news_weekly_20260822" / "open_broll" / "approved_open_broll_manifest.json"


def test_approved_open_broll_bundle_has_55_reviewed_slots() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    clips = payload["clips"]
    assert len(clips) == 55
    assert len({item["slot"] for item in clips}) == 55
    assert all(item["rights_status"] == "reviewed_for_private_preview" for item in clips)
    assert all(item["qc_status"].startswith("passed_") for item in clips)


def test_approved_open_broll_bundle_repeats_identical_range_at_most_twice() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ranges = [
        (item["media_file"], item["source_start_seconds"], item["source_end_seconds"])
        for item in payload["clips"]
    ]
    assert max(ranges.count(item) for item in set(ranges)) <= 2


def test_approved_open_broll_files_exist() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert all(Path(item["media_file"]).is_file() for item in payload["clips"])
