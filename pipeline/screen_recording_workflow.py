"""Episode-level contracts and gates for automatically acquired screen recordings."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import EpisodeProject


ACCEPTED_CAPTURE_STATUSES = {"accepted", "cached"}
SCREEN_SHOT_TYPES = {"screen_recording", "official_demo"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolved_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _demo_metadata_by_path(project: EpisodeProject) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in project.episode.get("model_test_queue", []):
        path = str(item.get("video", ""))
        if path:
            records[str(Path(path).resolve())] = item
    return records


def build_screen_recording_manifest(project: EpisodeProject, project_dir: Path) -> dict[str, Any]:
    """Describe traceable episode-owned recordings without trusting shot paths alone."""
    root = project_dir.resolve()
    recordings: list[dict[str, Any]] = []
    seen: set[str] = set()

    for record in project.captures:
        for artifact in record.artifacts:
            if artifact.kind != "screen_recording" or not artifact.path:
                continue
            path = Path(artifact.path)
            resolved = str(path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            quality = artifact.quality if isinstance(artifact.quality, dict) else {}
            inside = _resolved_within(path, root)
            exists = inside and path.is_file()
            recordings.append({
                "kind": "public_source",
                "path": str(path),
                "inside_episode_directory": inside,
                "exists": exists,
                "sha256": _sha256(path) if exists else "",
                "source_id": record.source_id,
                "source_url": artifact.source_url or record.final_url or record.requested_url,
                "capture_mode": artifact.capture_mode,
                "label": artifact.label,
                "quality": quality,
                "accepted": quality.get("status") in ACCEPTED_CAPTURE_STATUSES,
            })

    demo_metadata = _demo_metadata_by_path(project)
    for asset in project.media:
        if asset.kind != "browser_demo" or not asset.path:
            continue
        path = Path(asset.path)
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        item = demo_metadata.get(resolved, {})
        metadata = item.get("metadata", {}) if isinstance(item.get("metadata", {}), dict) else {}
        quality = metadata.get("quality", {}) if isinstance(metadata.get("quality", {}), dict) else {}
        inside = _resolved_within(path, root)
        exists = inside and path.is_file()
        recordings.append({
            "kind": "product_demo",
            "path": str(path),
            "inside_episode_directory": inside,
            "exists": exists,
            "sha256": _sha256(path) if exists else "",
            "source_id": asset.source_id,
            "source_url": str(item.get("website", "")),
            "capture_mode": "approved_product_demo",
            "label": str(item.get("goal", "Approved product demonstration")),
            "quality": quality,
            "allow_generation": bool(item.get("allow_generation")),
            "approval_status": str(item.get("status", "")),
            "accepted": asset.qc_status == "passed" and quality.get("status") in ACCEPTED_CAPTURE_STATUSES,
        })

    return {
        "schema": "screen-recording-manifest/1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "episode_id": project.episode_id,
        "recordings": recordings,
    }


def review_screen_recording_readiness(project: EpisodeProject, project_dir: Path) -> dict[str, Any]:
    """Fail closed when a storyboard recording is missing, unregistered, or outside the episode."""
    manifest = build_screen_recording_manifest(project, project_dir)
    by_path = {
        str(Path(item["path"]).resolve()): item
        for item in manifest["recordings"]
        if item.get("path")
    }
    required = [shot for shot in project.shots if shot.asset_type in SCREEN_SHOT_TYPES]
    failures: list[str] = []
    ready = 0
    for shot in required:
        if not shot.asset_path:
            failures.append(f"{shot.id} has no acquired screen-recording clip")
            continue
        path = Path(shot.asset_path)
        if not _resolved_within(path, project_dir):
            failures.append(f"{shot.id} recording is outside the episode directory")
            continue
        item = by_path.get(str(path.resolve()))
        if item is None:
            failures.append(f"{shot.id} recording is not a registered capture")
            continue
        if not item.get("exists"):
            failures.append(f"{shot.id} recording file is missing")
            continue
        if not item.get("accepted"):
            failures.append(f"{shot.id} recording lacks accepted capture QC")
            continue
        ready += 1
    return {
        "passed": not failures,
        "required_shots": len(required),
        "ready_shots": ready,
        "recording_count": len(manifest["recordings"]),
        "failures": failures,
    }


def write_screen_recording_manifest(project: EpisodeProject, project_dir: Path) -> Path:
    destination = project_dir / "screen_recordings" / "manifest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(build_screen_recording_manifest(project, project_dir), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return destination
