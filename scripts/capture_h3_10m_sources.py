"""Capture stable, popup-free source pages for the MiniMax H3 deep dive."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.capture import capture_sources
from pipeline.models import Source


OUTPUT = Path("output/minimax_h3_10m/sources")

SOURCES = [
    Source(
        id="minimax_launch",
        title="MiniMax H3 open-source announcement",
        url="https://www.minimax.io/news/minimax-h3-open-source",
        publisher="MiniMax",
        source_type="primary",
    ),
    Source(
        id="minimax_model",
        title="MiniMax H3 model card and official assets",
        url="https://huggingface.co/MiniMaxAI/MiniMax-H3",
        publisher="MiniMax / Hugging Face",
        source_type="primary",
    ),
    Source(
        id="comfy_workflow",
        title="Official ComfyUI MiniMax H3 image-to-video workflow",
        url="https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_i2v.json",
        publisher="ComfyUI",
        source_type="primary",
    ),
    Source(
        id="comfy_release",
        title="ComfyUI v0.32.0 release",
        url="https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.32.0",
        publisher="ComfyUI",
        source_type="primary",
    ),
]


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = capture_sources(SOURCES, OUTPUT, max_recordings=2)
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
    destination = OUTPUT.parent / "source_manifest.json"
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(destination), "sources": len(manifest)}, indent=2))


if __name__ == "__main__":
    main()
