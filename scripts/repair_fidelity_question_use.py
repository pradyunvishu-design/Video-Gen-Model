"""Apply the integrated loop's question-use-only script repair."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.fidelity_loop import (
    _repair_script_dimension,
    load_fidelity_run,
    save_fidelity_run,
)
from pipeline.project_store import load_project, save_project


EPISODE_DIR = ROOT / "data" / "episodes" / "episode_20260901_03"
RUN_ID = "fidelity_preflight_20260830_v2"


def main() -> None:
    project = load_project(EPISODE_DIR)
    if not project.script:
        raise RuntimeError("episode script is missing")
    run = load_fidelity_run(RUN_ID)
    before = run.scorecards.get("integrated")
    feedback = before.notes.get("question_use", "") if before else ""
    repaired = _repair_script_dimension(project, "question_use", feedback)
    for beat in repaired.beats:
        if beat.narration:
            beat.narration = beat.narration[:1].upper() + beat.narration[1:]
    question_count = repaired.narration.count("?")
    if question_count != 2:
        raise RuntimeError(f"question-use repair expected 2 purposeful questions, found {question_count}")

    locked_seconds = float(project.narration.get("duration_seconds") or 0)
    if locked_seconds <= 0:
        locked_seconds = sum(float(shot.duration_seconds) for shot in project.shots) - 0.024
    project.script = repaired
    overrides = project.editorial_plan.setdefault("fidelity_visual_overrides", {})
    overrides["freeze_storyboard"] = True
    overrides["fidelity_locked_timeline_seconds"] = round(locked_seconds, 3)
    overrides["question_use_contract"] = {
        "question_count": 2,
        "purpose": "open a real information gap and answer it nearby",
        "meta_questions_removed": True,
    }
    for stage in ("script", "narration", "captions", "render"):
        project.episode.setdefault("stage_hashes", {}).pop(stage, None)
    for artifact in ("video", "package", "captions"):
        project.artifacts.pop(artifact, None)
    project.qc.pop("final", None)
    project.qc.pop("review_readiness", None)
    project.qc.pop("fidelity_verification", None)
    project.status = "fidelity_question_use_repair"
    save_project(project, EPISODE_DIR)

    run.status = "integrated_question_use_repair"
    run.stop_reason = ""
    save_fidelity_run(run)
    print(f"queued question-use-only repair with {question_count} purposeful questions")


if __name__ == "__main__":
    main()
