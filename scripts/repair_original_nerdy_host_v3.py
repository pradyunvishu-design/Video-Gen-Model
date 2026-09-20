"""Repair the v3 opening evidence match and protect the final spoken tail."""
from __future__ import annotations

from pathlib import Path

from pipeline.models import EpisodeProject
from pipeline.project_store import save_project
from pipeline.render_v2 import render_shot
import scripts.rebuild_original_nerdy_host_v3 as v3
import scripts.repair_manager_feedback_v2_assembly as assembly


def main() -> None:
    build = v3.build
    project = EpisodeProject.model_validate_json(
        build.PROJECT_PATH.read_text(encoding="utf-8")
    )
    intro_1, intro_2, intro_3 = project.shots[:3]
    intro_1.prompt = (
        "Official Gemini Omni 1.1 Flash Partner Node output showing a generated clip and "
        "reference-image workflow inside the ComfyUI graph."
    )
    intro_2.prompt = (
        "Official Gemini Omni 1.1 Flash output showing scene extension and shot editing "
        "without leaving the ComfyUI Partner Node workflow."
    )

    comfy_source = next(source for source in project.sources if source.id == "src_09022b345bc4")
    intro_3.source_id = comfy_source.id
    intro_3.asset_path = str(
        build.EPISODE
        / "captures"
        / "verified_source_frames"
        / "comfy-source-excerpt-01-shot_003.png"
    )
    intro_3.prompt = (
        "Exact ComfyUI source excerpt naming Gemini Omni 1.1 Flash, its Partner Node, "
        "and the generate, reference, edit, and extend workflow inside one graph."
    )
    intro_3.rights_note = "Exact verified ComfyUI article text; publication review required."

    # Encoder frame rounding consumed the intended 350 ms hold. Add a deliberate
    # visual-only tail to the final official demo without stretching the narration.
    project.shots[-1].duration_seconds = max(project.shots[-1].duration_seconds, 11.858)
    save_project(project, build.EPISODE)

    # Render the changed source screenshot directly. The general resume pass can
    # safely reuse it because its measured duration matches the updated project.
    segment = build.SEGMENT_DIR / "002.mp4"
    render_shot(
        intro_3,
        Path(intro_3.asset_path),
        segment,
        source_label="ComfyUI",
        color_profile="earthy_neutral_source_v1",
    )
    (build.SEGMENT_DIR / f"{len(project.shots) - 1:03d}.mp4").unlink(missing_ok=True)
    for index in (88, 89):
        (build.SEGMENT_DIR / f"{index:03d}.mp4").unlink(missing_ok=True)

    # v3 imported first, so assembly.revision is the same configured build module.
    assembly.main()


if __name__ == "__main__":
    main()
