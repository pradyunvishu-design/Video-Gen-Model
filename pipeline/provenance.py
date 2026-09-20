"""Create a C2PA-ready, human-reviewable provenance sidecar for each episode."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import EpisodeProject


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path_value: str, **extra: Any) -> dict[str, Any]:
    path = Path(path_value)
    record: dict[str, Any] = {"path": str(path), **extra}
    if path.is_file():
        record.update({"sha256": _sha256(path), "bytes": path.stat().st_size})
    else:
        record["missing"] = True
    return record


def build_manifest(project: EpisodeProject, final_video: Path, destination: Path) -> Path:
    sources = [
        {
            "id": source.id,
            "title": source.title,
            "url": str(source.url),
            "publisher": source.publisher,
            "published_at": source.published_at.isoformat() if source.published_at else None,
            "source_type": source.source_type,
            "signal_role": source.signal_role,
            "cluster_id": source.cluster_id,
            "text_sha256": hashlib.sha256(source.text.encode("utf-8")).hexdigest() if source.text else "",
        }
        for source in project.sources
    ]
    media = [
        _file_record(
            asset.path,
            id=asset.id,
            kind=asset.kind,
            source_id=asset.source_id,
            qc_status=asset.qc_status,
            magic_hour_project_id=asset.magic_hour_project_id,
            synthetic=bool(asset.magic_hour_project_id or asset.kind.startswith("generated_")),
        )
        for asset in project.media
    ]
    captures = []
    for record in project.captures:
        for artifact in record.artifacts:
            captures.append(_file_record(
                artifact.path,
                source_id=record.source_id,
                requested_url=record.requested_url,
                final_url=record.final_url,
                captured_at=record.captured_at.isoformat(),
                capture_mode=artifact.capture_mode,
                label=artifact.label,
                quality=artifact.quality,
            ))

    manifest = {
        "schema": "ai-news-provenance/1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "episode_id": project.episode_id,
        "final_video": _file_record(str(final_video), kind="review_master"),
        "sources": sources,
        "media": media,
        "captures": captures,
        "rights": project.rights,
        "synthetic_media": {
            "narrator_profile": project.episode.get("voice_profile_id", ""),
            "disclosure": project.script.disclosure if project.script else "",
            "generated_asset_count": sum(1 for item in media if item.get("synthetic")),
        },
        "content_credentials": {
            "c2pa_sidecar_ready": True,
            "embedded": False,
            "note": "Signing and embedding require a publisher certificate and remain a release-stage action.",
        },
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination
