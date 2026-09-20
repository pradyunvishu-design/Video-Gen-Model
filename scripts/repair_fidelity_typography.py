"""Repair only the integrated fidelity loop's typography dimension."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.project_store import load_project, save_project


EPISODE_DIR = ROOT / "data" / "episodes" / "episode_20260901_03"


MOTION_COPY = {
    "shot_004": {"kicker": "THE QUESTION", "title": "FIVE TASKS. ONE NODE.", "body": "The menu is useful. The proof still matters."},
    "shot_008": {"kicker": "THE WORKFLOW", "title": "ONE NODE. FIVE TASKS.", "body": "Text, image, reference, edit, and extend."},
    "shot_015": {"kicker": "THE SETUP", "title": "THE VERIFIED INTERFACE", "body": "Choose the model, task, frame, and inputs."},
    "shot_019": {"kicker": "THE INPUT", "title": "TAG EACH IMAGE", "body": "Mark the first frame. Label visual references."},
    "shot_027": {"kicker": "THE CLAIM", "title": "TEST CONTINUITY", "body": "Watch identity, lighting, and texture."},
    "shot_031": {"kicker": "THE CHECK", "title": "THREE THINGS TO WATCH", "body": "Face. Clothes. Lighting."},
    "shot_037": {"kicker": "THE EDIT", "title": "CHANGE ONE THING", "body": "The source claims the rest should stay intact."},
    "shot_041": {"kicker": "THE FOLLOW-UP", "title": "EDIT THE EDIT", "body": "A second instruction should build on the first."},
    "shot_051": {"kicker": "THE WORKFLOW", "title": "DRAFT FIRST. FINISH LATER.", "body": "360p for decisions. Higher resolution for delivery."},
    "shot_060": {"kicker": "THE LIMITS", "title": "KNOW THE BOUNDARIES", "body": "Forty seconds. Two aspect ratios."},
    "shot_069": {"kicker": "THE CAVEAT", "title": "CLAIMS AREN'T TESTS", "body": "Launch numbers still need controlled checks."},
    "shot_082": {"kicker": "THE RULE", "title": "START CHEAP", "body": "Prove the shot before buying pixels."},
}


def main() -> None:
    project = load_project(EPISODE_DIR)
    overrides = project.editorial_plan.setdefault("fidelity_visual_overrides", {})
    overrides["typography_profile"] = "large_editorial"
    overrides["motion_copy"] = MOTION_COPY
    overrides["typography_contract"] = {
        "dominant_statement_max_words": 5,
        "supporting_copy_max_words": 9,
        "source_credit_only": True,
        "production_directions_visible": False,
    }
    for shot in project.shots:
        if shot.id not in MOTION_COPY:
            continue
        if shot.asset_path:
            old_path = shot.asset_path
            for asset in project.media:
                if asset.path == old_path and asset.kind == "motion_graphic":
                    asset.qc_status = "rejected"
                    asset.qc_notes.append("Superseded by the typography-only fidelity repair.")
        shot.asset_path = ""
        shot.asset_fingerprint = ""
    project.episode.setdefault("stage_hashes", {}).pop("media", None)
    project.episode.setdefault("stage_hashes", {}).pop("visual_qc", None)
    project.episode.setdefault("stage_hashes", {}).pop("render", None)
    project.artifacts.pop("video", None)
    project.artifacts.pop("package", None)
    project.qc.pop("final", None)
    project.qc.pop("review_readiness", None)
    save_project(project, EPISODE_DIR)
    print(f"queued {len(MOTION_COPY)} motion scenes for typography-only rerender")


if __name__ == "__main__":
    main()
