"""Capture stable public source evidence for the August 22 News Weekly episode."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.capture import capture_sources
from pipeline.models import Source


OUTPUT = Path("output/news_weekly_20260822/sources")
EVIDENCE = Path("output/news_weekly_20260822/evidence.json")


def main() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    sources = [
        Source(
            id=item["id"],
            title=item["title"],
            url=item["url"],
            publisher=item["publisher"],
            source_type="primary" if item["source_type"].startswith("primary") else "secondary",
        )
        for item in evidence["sources"]
        if item["source_type"].startswith("primary")
    ]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = capture_sources(sources, OUTPUT, max_recordings=6)
    manifest = []
    for source, result in zip(sources, results):
        manifest.append({
            "id": source.id,
            "title": source.title,
            "url": str(source.url),
            "publisher": source.publisher,
            "screenshots": result["screenshots"],
            "recordings": result["recordings"],
            "errors": result["errors"],
        })
    destination = OUTPUT.parent / "source_manifest.json"
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({
        "manifest": str(destination),
        "sources": len(manifest),
        "with_editorial_stills": sum(bool(item["screenshots"]) for item in manifest),
        "with_recordings": sum(bool(item["recordings"]) for item in manifest),
        "errors": {item["id"]: item["errors"] for item in manifest if item["errors"]},
    }, indent=2))


if __name__ == "__main__":
    main()
