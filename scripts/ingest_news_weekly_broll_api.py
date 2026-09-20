from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.licensed_clips import LicensedClipRequest, ingest_licensed_clip  # noqa: E402


OUT = ROOT / "output" / "news_weekly_20260822"
manifest = json.loads((OUT / "broll_api" / "broll_candidates.json").read_text(encoding="utf-8"))
by_id = {item["candidate_id"]: item for item in manifest["candidates"]}

# These ranges are bounded review excerpts. Source audio is always removed.
selections = {
    "broll_a780fcb71fe06e": (22.1, 30.1),
}

records = []
for candidate_id, (start, end) in selections.items():
    item = by_id[candidate_id]
    request = LicensedClipRequest(
        clip_id=candidate_id,
        source_id=item["scene_id"],
        url=item["source_url"],
        start_seconds=start,
        end_seconds=end,
        rights_basis="creative_commons",
        approved_by="Automated Creative Commons verification",
        attribution=f"{item['channel']} — {item['title']} — {item['source_url']}",
        keep_audio=False,
    )
    result = ingest_licensed_clip(request, OUT / "broll_api" / "ingested")
    records.append({
        "candidate_id": candidate_id,
        "scene_id": item["scene_id"],
        "title": item["title"],
        "channel": item["channel"],
        "source_url": item["source_url"],
        "start_seconds": start,
        "end_seconds": end,
        "clip": result["clip"],
        "ledger": result["ledger"],
        "quality": result["quality"],
    })

(OUT / "broll_api" / "ingested_manifest.json").write_text(
    json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(json.dumps({"ingested": len(records), "manifest": str(OUT / 'broll_api' / 'ingested_manifest.json')}, indent=2))
