"""Second, precision-oriented pass for reusable documentary footage.

The first pass intentionally searched broadly.  This pass uses short visible-
subject queries against public archives so metadata matching is less likely to
confuse a narration concept with an unrelated title.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
OPENMONTAGE = ROOT / "external" / "OpenMontage"
sys.path.insert(0, str(OPENMONTAGE))

from tools.video.direct_clip_search import DirectClipSearch  # noqa: E402


OUT = ROOT / "output" / "news_weekly_20260822" / "open_broll_pass2"

QUERIES = [
    {"slot_id": "security_analyst", "query": "cyber defense exercise", "kind": "video"},
    {"slot_id": "developer", "query": "computer programmer", "kind": "video"},
    {"slot_id": "server_room", "query": "computer server room", "kind": "video"},
    {"slot_id": "browser_work", "query": "person using computer", "kind": "video"},
    {"slot_id": "video_editing", "query": "video editing studio", "kind": "video"},
    {"slot_id": "film_camera", "query": "film camera crew", "kind": "video"},
    {"slot_id": "student_laptop", "query": "student laptop", "kind": "video"},
    {"slot_id": "data_center", "query": "data center", "kind": "video"},
    {"slot_id": "electricity", "query": "electrical power station", "kind": "video"},
    {"slot_id": "construction", "query": "industrial construction site", "kind": "video"},
    {"slot_id": "computer_lab", "query": "computer laboratory", "kind": "video"},
    {"slot_id": "software_team", "query": "software development team", "kind": "video"},
]


def main() -> None:
    result = DirectClipSearch().execute({
        "output_dir": str(OUT),
        "queries": QUERIES,
        "sources": ["archive_org", "wikimedia", "nasa", "nara", "loc"],
        "clips_per_query": 1,
        "filters": {
            "min_duration": 6,
            "max_duration": 180,
            "orientation": "landscape",
            "min_width": 960,
        },
        "extract_thumbnails": True,
        "skip_existing": True,
        "timeout_seconds": 1200,
    })
    payload = {
        "success": result.success,
        "error": result.error,
        "data": result.data,
        "duration_seconds": result.duration_seconds,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "acquisition_result.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        "success": result.success,
        "error": result.error,
        "clips": len((result.data or {}).get("clips", [])),
        "output": str(OUT),
    }, indent=2))
    if not result.success and not (result.data or {}).get("clips"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
