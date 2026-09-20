"""Rights-verify and ingest selected cached reputable-channel CC candidates."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.licensed_clips import LicensedClipRequest, ingest_licensed_clip

OUT = ROOT / "output" / "news_weekly_20260822"
DESTINATION = OUT / "reputable_youtube_v7" / "ingested_manifest.json"
CANDIDATES = json.loads((OUT / "broll_research_55_broad" / "broll_candidates.json").read_text(encoding="utf-8"))
BY_ID = {item["candidate_id"]: item for item in CANDIDATES["candidates"]}

SELECTION_CONFIG = json.loads(
    (ROOT / "configs" / "news_weekly_reputable_youtube_v7.json").read_text(encoding="utf-8")
)
# Target narration slot, cached candidate ID, and an eight-second visual range.
# Every row uses a different source video. This gives the editor substantially
# more picture variety while keeping the hard source-repeat cap at one.
SELECTIONS = [
    (int(item["slot"]), str(item["candidate_id"]), float(item["start_seconds"]))
    for item in SELECTION_CONFIG["selections"]
]


def ingest_one(slot: int, candidate_id: str, start: float) -> dict:
    item = BY_ID[candidate_id]
    result = ingest_licensed_clip(LicensedClipRequest(
                clip_id=f"reputable_{candidate_id}", source_id=item["scene_id"],
                url=item["source_url"], start_seconds=start, end_seconds=start + 8,
                rights_basis="creative_commons",
                approved_by="YouTube Data API Creative Commons verification",
                attribution=f"{item['channel']} — {item['title']} — {item['source_url']}",
                keep_audio=False,
            ), OUT / "reputable_youtube_v7" / "ingested")
    return {
        "slot": slot, "candidate_id": candidate_id, "scene_id": item["scene_id"],
        "title": item["title"], "channel": item["channel"],
        "source_url": item["source_url"], "start_seconds": start,
        "end_seconds": start + 8, "semantic_score": item["semantic_score"],
        "clip": result["clip"], "ledger": result["ledger"],
        "quality": result["quality"], "rights": result["rights"],
    }


def main() -> None:
    existing_records: list[dict] = []
    if DESTINATION.is_file():
        previous = json.loads(DESTINATION.read_text(encoding="utf-8"))
        for item in previous.get("clips", []):
            clip = Path(str(item.get("clip") or ""))
            if (item.get("quality") or {}).get("status") == "accepted" and clip.is_file():
                existing_records.append(item)
    completed_ids = {item["candidate_id"] for item in existing_records}
    pending = [item for item in SELECTIONS if item[1] not in completed_ids]
    records, errors = list(existing_records), []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(ingest_one, *selection): selection for selection in pending}
        for future in as_completed(futures):
            slot, candidate_id, _ = futures[future]
            try:
                records.append(future.result())
            except Exception as exc:
                errors.append({"slot": slot, "candidate_id": candidate_id, "error": f"{type(exc).__name__}: {exc}"})
    manifest = {
        "schema_version": 1, "publication_review_required": True,
        "policy": {"source_audio_muted": True, "maximum_uses_per_source": 1},
        "clips": records, "errors": errors,
    }
    DESTINATION.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "ingested": len(records), "reused": len(existing_records),
        "attempted": len(pending), "errors": len(errors), "manifest": str(DESTINATION),
    }, indent=2))


if __name__ == "__main__":
    main()
