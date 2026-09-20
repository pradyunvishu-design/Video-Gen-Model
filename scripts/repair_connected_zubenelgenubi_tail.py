"""Protect the final spoken word by extending only the last visual frame."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline import qc
from pipeline.config import NARRATION_TAIL_PADDING_SECONDS
from pipeline.models import EpisodeProject
from pipeline.project_store import save_project
from pipeline.render_v2 import duration, write_concat
import scripts.rebuild_clear_voice_aligned_intro as base


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "data" / "episodes" / "episode_20260901_03"
PROJECT_PATH = EPISODE / "episode_project.json"
REVISION_DIR = EPISODE / "connected_zubenelgenubi_v4"
TIMELINE = EPISODE / "timeline_connected_zubenelgenubi_v4.mp4"
PADDED_TIMELINE = EPISODE / "timeline_connected_zubenelgenubi_v4_padded.mp4"
NARRATION = EPISODE / "narration_gemini_31_zubenelgenubi_connected_v4.wav"
FINAL_VIDEO = EPISODE / "final_connected_zubenelgenubi_v4_1080p.mp4"


def main() -> None:
    project = EpisodeProject.model_validate_json(PROJECT_PATH.read_text(encoding="utf-8"))
    required_seconds = duration(NARRATION) + NARRATION_TAIL_PADDING_SECONDS
    timeline_seconds = duration(TIMELINE)
    tail_seconds = max(0.0, required_seconds - timeline_seconds + 0.10)
    if tail_seconds > 0:
        frame = REVISION_DIR / "protected_tail_frame.png"
        tail = REVISION_DIR / "protected_tail.mp4"
        base.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-sseof", "-0.10", "-i", str(TIMELINE), "-frames:v", "1", str(frame),
        ])
        base.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-i", str(frame), "-t", f"{tail_seconds:.3f}",
            "-vf", "fps=30,format=yuv420p", "-an", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "18", "-x264-params", "force-cfr=1",
            str(tail),
        ])
        listing = write_concat([TIMELINE, tail], REVISION_DIR / "padded_timeline_segments.txt")
        base.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat",
            "-safe", "0", "-i", str(listing), "-c", "copy", str(PADDED_TIMELINE),
        ])
    else:
        PADDED_TIMELINE.write_bytes(TIMELINE.read_bytes())

    base.mux(PADDED_TIMELINE, NARRATION, FINAL_VIDEO)
    project.artifacts["video"] = str(FINAL_VIDEO)
    project.qc["final"] = qc.run_qc(project, FINAL_VIDEO)
    project.qc["review_readiness"] = qc.review_readiness(project)
    project.status = "awaiting_final_approval"
    project.review.final_status = "pending"
    save_project(project, EPISODE)
    (EPISODE / "preview_package.json").write_text(project.model_dump_json(indent=2), encoding="utf-8")

    receipt_path = REVISION_DIR / "revision_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.update({
        "video": str(FINAL_VIDEO),
        "duration_seconds": round(duration(FINAL_VIDEO), 3),
        "tail_repair_seconds": round(tail_seconds, 3),
        "final_qc": project.qc["final"],
        "review_readiness": project.qc["review_readiness"],
    })
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({
        "video": str(FINAL_VIDEO),
        "duration_seconds": round(duration(FINAL_VIDEO), 3),
        "tail_repair_seconds": round(tail_seconds, 3),
        "final_qc_passed": project.qc["final"]["passed"],
        "final_qc_failures": project.qc["final"]["failures"],
        "review_readiness": project.qc["review_readiness"],
    }, indent=2))


if __name__ == "__main__":
    main()
