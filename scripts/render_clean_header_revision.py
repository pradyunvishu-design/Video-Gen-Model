"""Rerender an episode after motion-header and caption-style changes.

Only exact local motion shots, captions, and the final assembly are rebuilt.
All approved research, narration, captures, B-roll, and rights records are reused.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline import captions, qc, remotion_renderer
from pipeline.project_store import canonical_hash, load_project, mark_stage, save_project
from pipeline.render_v2 import render_project


STYLE_VERSION = "clean-editorial-headers-monochrome-captions-v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode_dir", type=Path)
    parser.add_argument("--skip-motion", action="store_true")
    parser.add_argument("--reuse-caption-timings", action="store_true")
    parser.add_argument("--adopt-final", type=Path)
    parser.add_argument("--selected-thumbnail", type=Path)
    args = parser.parse_args()
    run_dir = args.episode_dir.resolve()
    project = load_project(run_dir)

    motion_shots = [
        shot
        for shot in project.shots
        if shot.asset_type == "motion_graphic"
        and shot.asset_path
        and Path(shot.asset_path).suffix.lower() == ".mp4"
    ]

    def rerender(shot):
        destination = Path(shot.asset_path)
        remotion_renderer.render_motion_video(
            project,
            shot,
            destination,
            scratch=run_dir / "generated" / "remotion_scratch",
        )
        return shot.id

    rendered = [shot.id for shot in motion_shots]
    if not args.skip_motion:
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(rerender, motion_shots))

    narration = Path(str(project.narration.get("path") or ""))
    if not narration.is_file():
        raise FileNotFoundError(f"Narration master is missing: {narration}")
    caption_file = run_dir / "captions.ass"
    if not args.reuse_caption_timings or not caption_file.is_file():
        captions.generate_captions(narration, project.script.narration, caption_file)
    caption_input = {
        "style_version": STYLE_VERSION,
        "narration": str(narration),
        "script": project.script.narration,
    }
    mark_stage(project, "captions", caption_input)

    render_input = {
        "renderer_version": 9,
        "style_version": STYLE_VERSION,
        "shots": [shot.model_dump(mode="json") for shot in project.shots],
        "motion_shots_rerendered": rendered,
        "narration": str(narration),
        "captions": str(caption_file),
    }
    final = args.adopt_final.resolve() if args.adopt_final else render_project(
        project, run_dir, narration, caption_file, canonical_hash(render_input)
    )
    if not final.is_file():
        raise FileNotFoundError(f"Final video is missing: {final}")
    mark_stage(project, "render", render_input)

    project.artifacts["captions"] = str(caption_file)
    project.artifacts["video"] = str(final)
    if args.selected_thumbnail:
        selected_thumbnail = args.selected_thumbnail.resolve()
        if not selected_thumbnail.is_file():
            raise FileNotFoundError(f"Selected thumbnail is missing: {selected_thumbnail}")
        project.artifacts["thumbnail_selected"] = str(selected_thumbnail)
    project.qc["final"] = qc.run_qc(project, final)
    project.qc["clean_header_revision"] = {
        "style_version": STYLE_VERSION,
        "motion_shots_rerendered": rendered,
        "editorial_headers_visible": False,
        "caption_style": "52px white, black outline, monochrome karaoke",
    }
    project.status = "awaiting_final_approval"
    project.episode["publishing_enabled"] = False
    package_file = run_dir / "preview_package.json"
    project.artifacts["package"] = str(package_file)
    package_file.write_text(
        json.dumps(project.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    save_project(project, run_dir)
    print(json.dumps({
        "video": str(final),
        "captions": str(caption_file),
        "motion_shots_rerendered": rendered,
        "qc": project.qc["final"],
    }, indent=2))


if __name__ == "__main__":
    main()
