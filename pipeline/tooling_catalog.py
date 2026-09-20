"""Read-only provenance for external methods used by the video pipeline."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

from .config import PROJECT_ROOT


CATALOG_PATH = PROJECT_ROOT / "configs" / "video_production_sources.json"


@lru_cache(maxsize=1)
def load_video_production_sources() -> dict[str, Any]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported video production source catalog version")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("video production source catalog is empty")
    identifiers = [str(item.get("id", "")) for item in sources]
    if any(not value for value in identifiers) or len(identifiers) != len(set(identifiers)):
        raise ValueError("video production source IDs must be non-empty and unique")
    return payload


def catalog_sha256() -> str:
    return hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()


def method_provenance_for(*stages: str) -> list[dict[str, str]]:
    requested = {stage.casefold() for stage in stages}
    output: list[dict[str, str]] = []
    for item in load_video_production_sources()["sources"]:
        item_stages = {str(stage).casefold() for stage in item.get("stages", [])}
        if requested and not requested.intersection(item_stages):
            continue
        output.append({
            "source": str(item["source"]),
            "adapted_pattern": str(item["adapted_pattern"]),
        })
    return output


def production_stack_receipt() -> dict[str, Any]:
    catalog = load_video_production_sources()
    return {
        "catalog": catalog["catalog_name"],
        "catalog_sha256": catalog_sha256(),
        "sources": [
            {
                "id": item["id"],
                "source": item["source"],
                "stages": item["stages"],
                "integration": item["integration"],
                "license": item["license"],
            }
            for item in catalog["sources"]
        ],
        "policy": "route stage-specific skills; do not load or execute every repository at once",
    }
