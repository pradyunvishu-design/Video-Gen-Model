"""Build the resumable reputable-YouTube capture queue from cached API results.

This is deliberately separate from media acquisition. It lets discovery and
editorial matching stay deterministic when the YouTube search quota is
temporarily exhausted, while the render gate continues to require a local,
QC-passed media file.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "output" / "news_weekly_20260822"
SOURCE = EPISODE / "broll_research_55_broad" / "broll_candidates.json"
DESTINATION = EPISODE / "reputable_youtube_v7" / "review_queue.json"
CONFIG = ROOT / "configs" / "news_weekly_reputable_youtube_v7.json"


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    selection_config = json.loads(CONFIG.read_text(encoding="utf-8"))
    selections = [
        (int(item["slot"]), str(item["candidate_id"]), float(item["start_seconds"]))
        for item in selection_config["selections"]
    ]
    by_id = {item["candidate_id"]: item for item in payload["candidates"]}
    seen_video_ids: set[str] = set()
    seen_slots: set[int] = set()
    clips: list[dict] = []
    for slot, candidate_id, start in selections:
        if slot in seen_slots:
            raise ValueError(f"duplicate target slot: {slot}")
        item = by_id.get(candidate_id)
        if item is None:
            raise ValueError(f"candidate is absent from cached API results: {candidate_id}")
        video_id = str(item["video_id"])
        if video_id in seen_video_ids:
            raise ValueError(f"source video is reused: {video_id}")
        if str(item.get("license_name", "")).casefold() not in {
            "creativecommon", "creative commons",
        }:
            raise ValueError(f"candidate is not Creative Commons: {candidate_id}")
        if not item.get("quality_gate_passed"):
            raise ValueError(f"candidate failed discovery quality gate: {candidate_id}")
        seen_slots.add(slot)
        seen_video_ids.add(video_id)
        clips.append({
            "slot": slot,
            "candidate_id": candidate_id,
            "video_id": video_id,
            "scene_id": item["scene_id"],
            "title": item["title"],
            "channel": item["channel"],
            "source_url": item["source_url"],
            "thumbnail_url": item.get("thumbnail_url", ""),
            "source_start_seconds": start,
            "source_end_seconds": start + 8.0,
            "semantic_score": item.get("semantic_score", 0),
            "source_tier": item.get("source_tier", ""),
            "license_name": item["license_name"],
            "rights_basis": "creative_commons",
            "source_audio": "muted",
            "media_path": "",
            "capture_status": "pending_supported_capture",
            "qc_status": "pending",
            "render_eligible": False,
        })
    manifest = {
        "schema_version": 1,
        "episode_id": "episode_20260822_news_weekly",
        "publishing_enabled": False,
        "policy": {
            "different_source_video_per_slot": True,
            "maximum_uses_per_source": 1,
            "source_audio_muted": True,
            "required_output": "1920x1080 30fps H.264",
            "render_requires_local_media_and_qc": True,
        },
        "clip_count": len(clips),
        "clips": clips,
    }
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    print(json.dumps({"clips": len(clips), "manifest": str(DESTINATION)}, indent=2))


if __name__ == "__main__":
    main()
