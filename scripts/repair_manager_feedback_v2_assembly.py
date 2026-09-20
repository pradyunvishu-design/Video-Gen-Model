"""Resume and verify the manager-feedback v2 local assembly without new API calls."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline import qc
from pipeline.clip_alignment import review_project_clip_alignment
from pipeline.models import EpisodeProject
from pipeline.project_store import save_project
from pipeline.render_v2 import duration, write_concat
import scripts.rebuild_clear_voice_aligned_intro as base
import scripts.rebuild_manager_feedback_v2 as revision


def segment_is_valid(path: Path, target_seconds: float) -> bool:
    if not path.is_file() or path.stat().st_size < 1024:
        return False
    try:
        measured = duration(path)
    except Exception:
        return False
    return abs(measured - target_seconds) <= 0.12


def main() -> None:
    project = EpisodeProject.model_validate_json(
        revision.PROJECT_PATH.read_text(encoding="utf-8")
    )
    project.script.beats[0].narration = revision.NEW_B00
    project.script.beats[1].narration = revision.NEW_B01
    project.script.beats[-1].narration = revision.NEW_B28
    revision.rebalance_duration_limits(project)
    motion, motion_indexes = revision.configure_workflow_motion(project)
    revision.SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
    work = [
        (index, shot.duration_seconds)
        for index, shot in enumerate(project.shots)
        if not segment_is_valid(
            revision.SEGMENT_DIR / f"{index:03d}.mp4", shot.duration_seconds
        )
    ]
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(
            executor.map(
                lambda item: revision.retime_segment(
                    item[0],
                    item[1],
                    motion=motion,
                    motion_indexes=motion_indexes,
                    project=project,
                ),
                work,
            )
        )
    invalid = [
        index
        for index, shot in enumerate(project.shots)
        if not segment_is_valid(
            revision.SEGMENT_DIR / f"{index:03d}.mp4", shot.duration_seconds
        )
    ]
    if invalid:
        raise RuntimeError(f"invalid segments after repair: {invalid}")

    segments = [
        revision.SEGMENT_DIR / f"{index:03d}.mp4"
        for index in range(len(project.shots))
    ]
    listing = write_concat(segments, revision.REVISION_DIR / "timeline_segments.txt")
    base.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c", "copy", str(revision.FINAL_TIMELINE),
        ]
    )
    base.mux(revision.FINAL_TIMELINE, revision.FINAL_NARRATION, revision.FINAL_VIDEO)

    clip_review = review_project_clip_alignment(
        project, max_asset_uses=12, cooldown_shots=0
    )
    project.episode["captions_enabled"] = False
    project.episode["publishing_enabled"] = False
    project.narration["path"] = str(revision.FINAL_NARRATION)
    project.narration["duration_seconds"] = duration(revision.FINAL_NARRATION)
    project.artifacts.pop("captions", None)
    project.artifacts["video"] = str(revision.FINAL_VIDEO)
    project.qc["clip_alignment"] = clip_review
    project.qc["final"] = qc.run_qc(project, revision.FINAL_VIDEO)
    project.qc["review_readiness"] = qc.review_readiness(project)
    project.status = "awaiting_final_approval"
    project.review.final_status = "pending"
    save_project(project, revision.EPISODE)
    (revision.EPISODE / "preview_package.json").write_text(
        project.model_dump_json(indent=2), encoding="utf-8"
    )
    receipt = {
        "video": str(revision.FINAL_VIDEO),
        "duration_seconds": round(duration(revision.FINAL_VIDEO), 3),
        "segments_repaired": [index for index, _ in work],
        "segment_count": len(segments),
        "clip_alignment": {
            "passed": clip_review["passed"],
            "median_score": clip_review["median_score"],
            "failures": clip_review["failures"],
        },
        "final_qc": project.qc["final"],
        "review_readiness": project.qc["review_readiness"],
        "publishing_enabled": False,
    }
    (revision.REVISION_DIR / "assembly_repair_receipt.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
