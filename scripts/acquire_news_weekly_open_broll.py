"""Acquire real, reusable footage for the 2026-08-22 weekly episode.

This follows the same source pattern used by the Claude-chip episode: footage
comes from official/open media libraries rather than generated imagery.  Every
download keeps its provider URL and creator metadata for the rights ledger.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
OPENMONTAGE = ROOT / "external" / "OpenMontage"
sys.path.insert(0, str(OPENMONTAGE))

from tools.video.direct_clip_search import DirectClipSearch  # noqa: E402


OUT = ROOT / "output" / "news_weekly_20260822" / "open_broll"

QUERIES = [
    {"slot_id": "cyber_soc", "query": "cybersecurity operations center server monitoring", "kind": "video"},
    {"slot_id": "cyber_code", "query": "software developer reviewing security code", "kind": "video"},
    {"slot_id": "cyber_servers", "query": "secure data center server racks engineers", "kind": "video"},
    {"slot_id": "cyber_response", "query": "computer security incident response analyst", "kind": "video"},
    {"slot_id": "agent_browser", "query": "person using web browser laptop office", "kind": "video"},
    {"slot_id": "agent_terminal", "query": "programmer terminal coding laptop", "kind": "video"},
    {"slot_id": "agent_workflow", "query": "business workflow automation computer", "kind": "video"},
    {"slot_id": "video_editor", "query": "professional video editor editing timeline", "kind": "video"},
    {"slot_id": "creative_team", "query": "creative team editing video studio", "kind": "video"},
    {"slot_id": "film_production", "query": "film production camera crew studio", "kind": "video"},
    {"slot_id": "chatbot_user", "query": "person using chatbot on laptop", "kind": "video"},
    {"slot_id": "student_ai", "query": "student studying with laptop classroom", "kind": "video"},
    {"slot_id": "digital_ads", "query": "digital advertising analytics dashboard", "kind": "video"},
    {"slot_id": "data_center_build", "query": "data center construction cranes industrial campus", "kind": "video"},
    {"slot_id": "gpu_racks", "query": "GPU servers data center racks", "kind": "video"},
    {"slot_id": "power_grid", "query": "electrical substation power grid", "kind": "video"},
    {"slot_id": "cooling", "query": "industrial cooling equipment data center", "kind": "video"},
    {"slot_id": "construction_workers", "query": "construction workers industrial site", "kind": "video"},
    {"slot_id": "model_hub", "query": "developer browsing code repository laptop", "kind": "video"},
    {"slot_id": "local_model", "query": "small computer electronics developer", "kind": "video"},
    {"slot_id": "open_source", "query": "open source software developers collaboration", "kind": "video"},
    {"slot_id": "software_release", "query": "programmer publishing software release", "kind": "video"},
]


def main() -> None:
    result = DirectClipSearch().execute({
        "output_dir": str(OUT),
        "queries": QUERIES,
        "sources": [
            "coverr", "mixkit", "wikimedia", "nasa", "nara", "pond5_pd",
            "loc", "esa", "noaa", "dareful", "jaxa",
        ],
        "clips_per_query": 1,
        "filters": {
            "min_duration": 6,
            "max_duration": 300,
            "orientation": "landscape",
            "min_width": 1280,
        },
        "extract_thumbnails": True,
        "skip_existing": True,
        "timeout_seconds": 900,
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
