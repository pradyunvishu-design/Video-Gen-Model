from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.licensed_clips import LicensedClipRequest, ingest_licensed_clip  # noqa: E402


OUT = ROOT / "output" / "news_weekly_20260822"
candidates = json.loads((OUT / "broll_api_manual" / "candidates.json").read_text(encoding="utf-8-sig"))
by_id = {item["id"]: item for item in candidates}
selections = {
    "V8lD0q29wAk": (245.0, 253.0, "computer_use"),
    "TZ6bvYydog4": (5.0, 13.0, "chatgpt_platform"),
    "7rxt2aDnejI": (45.0, 53.0, "open_models"),
    "gsN_CJJDy_o": (60.0, 68.0, "ports_pike"),
}
records = []
errors = []
for video_id, (start, end, scene_id) in selections.items():
    item = by_id[video_id]
    request = LicensedClipRequest(
        clip_id=f"ytcc_{video_id.lower()}", source_id=scene_id, url=item["url"],
        start_seconds=start, end_seconds=end, rights_basis="creative_commons",
        approved_by="Automated Creative Commons verification",
        attribution=f"{item['channel']} — {item['title']} — {item['url']}", keep_audio=False,
    )
    try:
        result = ingest_licensed_clip(request, OUT / "broll_api_manual" / "ingested")
        records.append({
            "video_id": video_id, "scene_id": scene_id, "title": item["title"],
            "channel": item["channel"], "source_url": item["url"],
            "start_seconds": start, "end_seconds": end,
            "clip": result["clip"], "ledger": result["ledger"], "quality": result["quality"],
        })
    except Exception as exc:
        errors.append({"video_id": video_id, "scene_id": scene_id, "error": f"{type(exc).__name__}: {exc}"})

manifest = {"clips": records, "errors": errors, "publication_review_required": True}
path = OUT / "broll_api_manual" / "ingested_manifest.json"
path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"ingested": len(records), "errors": len(errors), "manifest": str(path)}, indent=2))
