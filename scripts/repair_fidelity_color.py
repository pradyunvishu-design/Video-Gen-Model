"""Apply the integrated loop's color-palette-only repair."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.fidelity_loop import load_fidelity_run, save_fidelity_run
from pipeline.project_store import load_project, save_project


EPISODE_DIR = ROOT / "data" / "episodes" / "episode_20260901_03"
RUN_ID = "fidelity_preflight_20260830_v2"


def main() -> None:
    project = load_project(EPISODE_DIR)
    overrides = project.editorial_plan.setdefault("fidelity_visual_overrides", {})
    overrides["color_profile"] = "earthy_neutral_source_v1"
    overrides["color_contract"] = {
        "base": "neutral charcoal and warm off-white",
        "source_footage": "restrained saturation, slightly warm midtones, subtle edge falloff",
        "brand_exception": "authored company logos and brand accents retain official colors",
        "forbidden": ["neon yellow", "vibe purple", "blanket duotone", "synthetic gradient wash"],
    }
    project.episode.setdefault("stage_hashes", {}).pop("render", None)
    project.artifacts.pop("video", None)
    project.artifacts.pop("package", None)
    project.qc.pop("final", None)
    project.qc.pop("review_readiness", None)
    save_project(project, EPISODE_DIR)

    run = load_fidelity_run(RUN_ID)
    run.status = "integrated_color_palette_repair"
    run.stop_reason = ""
    save_fidelity_run(run)
    print("queued color-palette-only rerender")


if __name__ == "__main__":
    main()
