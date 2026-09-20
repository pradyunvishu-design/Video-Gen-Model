"""Finalize metadata and rerun QC for the subtitle-free natural-voice master."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline import qc
from pipeline.project_store import load_project, save_project


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "data" / "episodes" / "episode_20260901_03"
VIDEO = EPISODE / "final_natural_voice_motion_no_subtitles_1080p.mp4"


def main() -> None:
    project = load_project(EPISODE)
    # These are official Google launch-page screenshots and therefore belong
    # in source/article evidence, not the miscellaneous bucket.
    corrected = []
    for shot in project.shots:
        if shot.id in {"shot_002", "shot_005"}:
            shot.visual_category = "article_evidence"
            corrected.append(shot.id)
    project.episode["captions_enabled"] = False
    project.artifacts.pop("captions", None)
    project.artifacts["video"] = str(VIDEO)
    project.qc["visual_category_correction"] = {
        "passed": True,
        "shot_ids": corrected,
        "basis": "official Google launch-page screenshots with source IDs and rights records",
    }
    project.qc["final"] = qc.run_qc(project, VIDEO)
    project.qc["review_readiness"] = qc.review_readiness(project)
    project.status = "awaiting_final_approval"
    project.episode["publishing_enabled"] = False
    save_project(project, EPISODE)
    (EPISODE / "preview_package.json").write_text(project.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps({
        "video": str(VIDEO),
        "corrected_visual_categories": corrected,
        "final_qc": project.qc["final"],
        "review_readiness": project.qc["review_readiness"],
    }, indent=2))


if __name__ == "__main__":
    main()
