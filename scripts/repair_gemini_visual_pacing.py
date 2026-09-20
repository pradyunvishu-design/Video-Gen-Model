"""Repair visual holds after the Gemini narration pacing revision.

This stage is deliberately media-only: it reuses the approved narration and
captions, splits just the overlong shots, preserves provenance, and renders a
new review master without making another paid TTS request.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import qc
from pipeline.project_store import load_project, save_project
from pipeline.render_v2 import render_project
from pipeline.storyboard import shot_limit


EPISODE = ROOT / "data" / "episodes" / "episode_20260901_03"
PROJECT_PATH = EPISODE / "episode_project.json"
BACKUP_PATH = EPISODE / "episode_project.pre_gemini_visual_pacing.json"
NARRATION = EPISODE / "narration_gemini_human_presenter.wav"
CAPTIONS = EPISODE / "captions_gemini_human_presenter.ass"
FINAL_VIDEO = EPISODE / "final_gemini_human_presenter_pacing_fixed_cbr.mp4"
REVISION_DIR = EPISODE / "gemini_human_presenter_revision"
MAX_SPLIT_SECONDS = 5.8


def _duration(path: Path) -> float | None:
    if path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}:
        return None
    process = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return float(process.stdout.strip()) if process.returncode == 0 else None
    except ValueError:
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _needs_split(shot) -> bool:
    # A 12-second editorial ceiling prevents the slower narration from turning
    # even an allowed long product demonstration into a perceptual freeze.
    return shot.duration_seconds > min(12.0, shot_limit(shot.asset_type))


def _safe_source_offset(
    original_offset: float,
    elapsed: float,
    part_seconds: float,
    media_seconds: float | None,
) -> float:
    if not media_seconds:
        return 0.0
    end_guard = 0.25
    latest = max(0.0, media_seconds - end_guard - part_seconds)
    candidate = original_offset + elapsed
    if candidate <= latest:
        return round(candidate, 3)
    # Restart at a deterministic, content-bearing point rather than allowing
    # FFmpeg's tpad to freeze the final frame for the rest of the shot.
    usable = max(0.25, latest - 0.25)
    wrapped = 0.25 + ((candidate - 0.25) % usable)
    return round(min(latest, wrapped), 3)


def _clone_rights(rights_by_shot: dict[str, list[dict]], source_id: str, new_id: str) -> list[dict]:
    records = rights_by_shot.get(source_id, [])
    cloned = []
    for record in records:
        item = copy.deepcopy(record)
        item["shot_id"] = new_id
        if item.get("asset_id"):
            item["asset_id"] = f"{item['asset_id']}__{new_id}"
        cloned.append(item)
    return cloned


def main() -> None:
    if not NARRATION.exists() or not CAPTIONS.exists():
        raise FileNotFoundError("Completed Gemini narration and captions are required")

    project = load_project(EPISODE)
    if not BACKUP_PATH.exists():
        shutil.copy2(PROJECT_PATH, BACKUP_PATH)

    # Idempotency: if a prior interrupted run already applied the split plan,
    # do not split the derived shots a second time.
    if any("__pace_" in shot.id for shot in project.shots):
        repaired_shots = project.shots
        split_originals: list[str] = []
    else:
        rights_by_shot: dict[str, list[dict]] = {}
        rights_without_shot: list[dict] = []
        for record in project.rights:
            shot_id = str(record.get("shot_id") or "")
            if shot_id:
                rights_by_shot.setdefault(shot_id, []).append(record)
            else:
                rights_without_shot.append(record)

        repaired_shots = []
        repaired_rights = list(rights_without_shot)
        split_originals = []
        still_styles = ("push_in", "pull_out", "push_in")
        for shot in project.shots:
            if not _needs_split(shot):
                repaired_shots.append(shot)
                repaired_rights.extend(rights_by_shot.get(shot.id, []))
                continue

            split_originals.append(shot.id)
            part_count = math.ceil(shot.duration_seconds / MAX_SPLIT_SECONDS)
            part_seconds = shot.duration_seconds / part_count
            media_seconds = _duration(Path(shot.asset_path)) if shot.asset_path else None
            cursor = shot.start_seconds
            for index in range(part_count):
                part = shot.model_copy(deep=True)
                part.id = f"{shot.id}__pace_{index + 1:02d}"
                part.start_seconds = round(cursor, 3)
                if index == part_count - 1:
                    consumed = part_seconds * (part_count - 1)
                    part.duration_seconds = round(shot.duration_seconds - consumed, 3)
                else:
                    part.duration_seconds = round(part_seconds, 3)
                part.transition = "cut"
                if media_seconds is None:
                    part.motion_style = still_styles[index % len(still_styles)]
                    part.source_in_seconds = 0.0
                else:
                    part.source_in_seconds = _safe_source_offset(
                        shot.source_in_seconds,
                        part_seconds * index,
                        part.duration_seconds,
                        media_seconds,
                    )
                repaired_shots.append(part)
                repaired_rights.extend(_clone_rights(rights_by_shot, shot.id, part.id))
                cursor += part.duration_seconds
        project.shots = repaired_shots
        project.rights = repaired_rights

    durations = [shot.duration_seconds for shot in repaired_shots]
    project.qc["gemini_visual_pacing_repair"] = {
        "passed": True,
        "split_original_shots": split_originals,
        "shot_count": len(repaired_shots),
        "maximum_shot_seconds": round(max(durations), 3),
        "median_shot_seconds": round(sorted(durations)[len(durations) // 2], 3),
        "gemini_audio_regenerated": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    project.qc.pop("final", None)
    project.qc.pop("review_readiness", None)
    project.status = "rendering"
    save_project(project, EPISODE)

    plan_hash = hashlib.sha256(
        json.dumps(
            [
                {
                    "id": shot.id,
                    "duration": shot.duration_seconds,
                    "source_in": shot.source_in_seconds,
                    "motion": shot.motion_style,
                }
                for shot in project.shots
            ],
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    cache_key = f"gemini-pacing-{plan_hash}"
    rendered = render_project(project, EPISODE, NARRATION, CAPTIONS, cache_key)
    if rendered.resolve() != FINAL_VIDEO.resolve():
        shutil.copy2(rendered, FINAL_VIDEO)

    project.artifacts["video"] = str(FINAL_VIDEO)
    project.status = "awaiting_final_approval"
    project.qc["final"] = qc.run_qc(project, FINAL_VIDEO)
    project.qc["review_readiness"] = qc.review_readiness(project)
    save_project(project, EPISODE)
    package = Path(project.artifacts.get("package") or EPISODE / "preview_package.json")
    package.write_text(project.model_dump_json(indent=2), encoding="utf-8")

    receipt = {
        "final_video": str(FINAL_VIDEO),
        "sha256": _sha256(FINAL_VIDEO),
        "duration_seconds": qc.probe(FINAL_VIDEO)["format"].get("duration"),
        "shot_count": len(project.shots),
        "gemini_audio_regenerated": False,
        "visual_pacing_repair": project.qc["gemini_visual_pacing_repair"],
        "final_qc": project.qc["final"],
        "review_readiness": project.qc["review_readiness"],
        "publishing_enabled": False,
    }
    (REVISION_DIR / "visual_pacing_receipt.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
