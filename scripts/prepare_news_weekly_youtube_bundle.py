"""Create the handoff manifest for the approved YouTube clip service.

This selects the strongest discovered Creative Commons candidate per visual
need.  The service/human editor fills media_file and exact timestamps after
reviewing the actual picture.  Nothing becomes render-eligible until every
record is cleared and the corresponding local media exists.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "output" / "news_weekly_20260822"
DISCOVERY = EPISODE / "broll_research_55_broad" / "broll_candidates.json"
DESTINATION = EPISODE / "youtube_broll_bundle" / "approved_youtube_broll_manifest.json"


def main() -> None:
    discovery = json.loads(DISCOVERY.read_text(encoding="utf-8"))
    candidates = {item["candidate_id"]: item for item in discovery.get("candidates", [])}
    clips: list[dict] = []
    for scene in discovery.get("scenes", []):
        ranked = [candidates[item] for item in scene.get("candidate_ids", []) if item in candidates]
        ranked = [item for item in ranked if item.get("quality_gate_passed")]
        if not ranked:
            raise RuntimeError(f"no quality-gated candidate for {scene.get('scene_id')}")
        selected = max(ranked, key=lambda item: (item.get("semantic_score", 0), item.get("combined_score", 0)))
        slots = [int(str(item).removeprefix("slot_")) for item in scene.get("shot_ids", [])]
        for offset, slot in enumerate(slots):
            clips.append({
                "slot": slot,
                "scene_id": scene.get("scene_id"),
                "visual_need": scene.get("visual_need"),
                "candidate_id": selected.get("candidate_id"),
                "video_id": selected.get("video_id"),
                "title": selected.get("title"),
                "channel": selected.get("channel"),
                "source_url": selected.get("source_url"),
                "license_name": selected.get("license_name"),
                "rights_basis": "creative_commons",
                "rights_status": "pending_media_review",
                "source_start_seconds": offset * 6.0,
                "source_end_seconds": (offset + 1) * 6.0,
                "media_file": "",
                "qc_status": "pending",
                "attribution": f"{selected.get('title')} — {selected.get('channel')}",
            })
    clips.sort(key=lambda item: item["slot"])
    if len(clips) != 55:
        raise RuntimeError(f"expected 55 YouTube slots, prepared {len(clips)}")
    payload = {
        "schema_version": 1,
        "episode_id": "episode_20260822_news_weekly",
        "publishing_enabled": False,
        "instructions": (
            "Supply reviewed local clips and exact timestamps. Set rights_status to approved "
            "and qc_status to passed only after picture, license, and attribution review."
        ),
        "clips": clips,
    }
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"manifest": str(DESTINATION), "clips": len(clips)}, indent=2))


if __name__ == "__main__":
    main()
