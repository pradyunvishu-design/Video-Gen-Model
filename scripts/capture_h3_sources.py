"""Capture a small, source-backed visual package for the MiniMax H3 news draft."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.capture import capture_sources
from pipeline.models import Source


OUTPUT = Path("output/viral_h3_2m30/sources")

SOURCES = [
    Source(
        id="minimax_launch",
        title="MiniMax H3 official launch",
        url="https://minimaxi.com/blog/minimax-h3",
        publisher="MiniMax",
        source_type="primary",
    ),
    Source(
        id="minimax_repo",
        title="MiniMax H3 official repository and model details",
        url="https://github.com/MiniMax-AI/MiniMax-H3",
        publisher="MiniMax",
        source_type="primary",
    ),
    Source(
        id="comfy_day_zero",
        title="ComfyUI day-zero MiniMax H3 workflows",
        url="https://www.reddit.com/r/StableDiffusion/comments/1ve1756/day_0_minimax_support_for_comfyui/",
        publisher="ComfyUI / r/StableDiffusion",
        source_type="community",
    ),
    Source(
        id="community_speed",
        title="Community H3 generation-time report",
        url="https://www.reddit.com/r/comfyui/comments/1vg8tyt/comfyui_breakthrough_release_minimax_h3_the_new/",
        publisher="r/comfyui",
        source_type="community",
    ),
]


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = capture_sources(SOURCES, OUTPUT, max_recordings=3)
    manifest = []
    for source, result in zip(SOURCES, results):
        manifest.append({
            "id": source.id,
            "title": source.title,
            "url": str(source.url),
            "publisher": source.publisher,
            "screenshots": [str(path) for path in result["screenshots"]],
            "recordings": [str(path) for path in result["recordings"]],
            "errors": result["errors"],
        })
    path = OUTPUT.parent / "source_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(path), "sources": len(manifest)}, indent=2))


if __name__ == "__main__":
    main()
