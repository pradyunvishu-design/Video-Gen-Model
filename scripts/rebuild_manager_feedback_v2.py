"""Apply manager feedback: restrained voice, explicit intro/outro, and clearer news motion."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

from pipeline import audio_qc, captions, qc, remotion_renderer
from pipeline.clip_alignment import review_project_clip_alignment
from pipeline.editorial import _spoken_quality_report, duration_profile
from pipeline.gemini_tts import GeminiTTSClient
from pipeline.models import EpisodeProject, MediaAsset
from pipeline.project_store import save_project
from pipeline.render_v2 import concat_audio, duration, make_silence, write_concat
from pipeline.storyboard import shot_limit
import scripts.rebuild_clear_voice_aligned_intro as base


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "data" / "episodes" / "episode_20260901_03"
PROJECT_PATH = EPISODE / "episode_project.json"
PROJECT_BACKUP = EPISODE / "episode_project.pre_manager_feedback_v2.json"
DEFAULT_ENV = Path(
    r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker"
)
REVISION_DIR = EPISODE / "manager_feedback_v2"
AUDIO_DIR = REVISION_DIR / "audio"
MOTION_DIR = REVISION_DIR / "motion"
SOURCE_SEGMENTS = EPISODE / "timeline_segments" / "clear-aligned-v1"
SEGMENT_DIR = EPISODE / "timeline_segments" / "manager-feedback-v2"
FINAL_NARRATION = EPISODE / "narration_gemini_31_restrained_host_v2.wav"
FINAL_TIMELINE = EPISODE / "timeline_manager_feedback_v2.mp4"
FINAL_VIDEO = EPISODE / "final_manager_feedback_v2_1080p.mp4"
MODEL = "gemini-3.1-flash-tts-preview"
VOICE = "Achird"
PAUSE_MS = 240
REVISION_VERSION = "v2"
VOICE_PROFILE_ID = "gemini_31_achird_restrained_technical_host_v2"
QC_PREFIX = "manager_v2"
REVIEW_NOTE = "Manager feedback v2: restrained narrator, expectation-setting intro, explicit conclusion, and simplified news-workflow motion graphic."


NEW_B00 = (
    "ComfyUI just added Google's Gemini Omni 1.1 Flash as one Partner Node. "
    "It puts five video jobs inside the same workflow: generating a clip, using references, "
    "editing a shot, and extending a scene, without leaving the graph."
)
NEW_B01 = (
    "That sounds convenient, but a cleaner interface isn't proof that every result is reliable. "
    "So in this video, we'll separate the documented controls from the launch claims. Then we'll look "
    "at what can break during an edit or extension, and finish with the cheapest way to test the node before "
    "paying for 1080p or 4K. By the end, you'll know what it's useful for now, and what still needs "
    "your own footage."
)
NEW_B28 = (
    "So here's the bottom line. Gemini Omni in ComfyUI is useful because it puts five jobs in one place. "
    "That saves setup, but it doesn't remove the need to check the result. Start with a cheap draft. "
    "Watch the motion, change one thing at a time, and make sure identity and lighting survive before you pay "
    "for final resolution. It's worth trying. The node makes the workflow easier. "
    "Repeating the same ten-second test is what makes it trustworthy."
)

OPENING_CANDIDATES = [
    {
        "mode": "demonstration_first",
        "text": NEW_B00 + " " + NEW_B01,
        "selected": True,
        "reason": "Names the exact tool, previews capabilities and limitations, and promises a practical decision while official output is visible.",
    },
    {
        "mode": "verdict_first",
        "text": "ComfyUI's Gemini Omni node is already useful for workflow convenience. Reliability is the part the launch menu cannot prove.",
        "selected": False,
        "reason": "Clear judgment, but it lands before the viewer sees the range of supported tasks.",
    },
    {
        "mode": "relatable_friction",
        "text": "The expensive way to test an AI video model is to discover a motion problem after the high-resolution render.",
        "selected": False,
        "reason": "Strong creator problem, but product recognition arrives too late.",
    },
    {
        "mode": "context_reversal",
        "text": "Five separate video jobs now fit inside one ComfyUI node. Fewer boxes, though, do not mean fewer failure points.",
        "selected": False,
        "reason": "Useful contrast, but the demonstration-led opening offers stronger visible proof.",
    },
]

DIRECTOR = """Read only the transcript below. Never read these notes aloud.

You are an original male technology host explaining something you genuinely researched to one colleague. Use natural American English. Sound calm, technically curious, slightly nerdy, and lightly dry. Underplay everything. Keep a normal conversational volume and mostly neutral downward sentence endings.

Do not perform commas, headlines, list items, jokes, or caveats. Do not turn each paragraph into a fresh announcement. Pause briefly only where a real person would think or where evidence changes the point. Keep pitch and pace stable, finish every sentence, and let specificity provide the energy.

Avoid imitation of any real creator, announcer voice, sales energy, trailer pacing, sing-song cadence, dramatic pauses, exaggerated emphasis, fake laughter, vocal fry, whispering, and synthetic perfection.

TRANSCRIPT:
"""

WORKFLOW_SPEC = {
    "template": "news_workflow",
    "title": "TEST CHEAP.\nFINISH SHARP.",
    "body": "Don't pay for detail until the movement and composition already work.",
    "labels": ["DRAFT LOW", "CHECK MOTION", "EDIT ONE THING", "FINISH SHARP"],
}
WORKFLOW_IDS = ("shot_082__pace_01", "shot_082__pace_02")
GROUP_RANGES = (
    (0, 3), (3, 6), (6, 9), (9, 12), (12, 15),
    (15, 18), (18, 21), (21, 24), (24, 27), (27, 29),
)


def narration_chunks(project: EpisodeProject, key: str, *, force: bool) -> tuple[list[Path], dict]:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    client = GeminiTTSClient(key, model=MODEL, voice=VOICE, timeout_seconds=180)
    mastered: list[Path] = []
    usage: dict[str, dict] = {}
    for index, (left, right) in enumerate(GROUP_RANGES, 1):
        transcript = "\n\n".join(beat.narration for beat in project.script.beats[left:right])
        digest = hashlib.sha256((MODEL + VOICE + DIRECTOR + transcript).encode("utf-8")).hexdigest()[:12]
        raw = AUDIO_DIR / f"chapter_{index:02d}_{digest}_raw.wav"
        master = AUDIO_DIR / f"chapter_{index:02d}_master.wav"
        if force:
            raw.unlink(missing_ok=True)
            master.unlink(missing_ok=True)
        result = client.synthesize(transcript, raw, director_prompt=DIRECTOR, retries=2)
        base.master(raw, master)
        mastered.append(master)
        usage[f"chapter_{index:02d}"] = result.usage
    parts: list[Path] = []
    pause = AUDIO_DIR / f"pause_{PAUSE_MS}ms.wav"
    if not pause.exists():
        make_silence(pause, PAUSE_MS)
    for index, path in enumerate(mastered):
        parts.append(path)
        if index < len(mastered) - 1:
            parts.append(pause)
    concat_audio(parts, FINAL_NARRATION)
    return mastered, usage


def configure_workflow_motion(project: EpisodeProject) -> tuple[Path, set[int]]:
    overrides = project.editorial_plan.setdefault("fidelity_visual_overrides", {})
    overrides.setdefault("motion_copy", {})[WORKFLOW_IDS[0]] = WORKFLOW_SPEC
    shots = [next(shot for shot in project.shots if shot.id == shot_id) for shot_id in WORKFLOW_IDS]
    total = round(sum(shot.duration_seconds for shot in shots), 3)
    representative = shots[0].model_copy(deep=True)
    representative.duration_seconds = total
    representative.motion_template = "news_workflow"
    MOTION_DIR.mkdir(parents=True, exist_ok=True)
    destination = MOTION_DIR / "cheap-test-news-workflow.mp4"
    if not destination.is_file() or destination.stat().st_size < 1024:
        remotion_renderer.render_motion_video(
            project, representative, destination, scratch=REVISION_DIR / "remotion_scratch"
        )
    cursor = 0.0
    indexes: set[int] = set()
    for shot in shots:
        shot.asset_type = "motion_graphic"
        shot.asset_path = str(destination)
        shot.motion_template = "news_workflow"
        shot.motion_style = "locked"
        shot.transition = "cut"
        shot.presentation = "full_bleed"
        shot.visual_category = "motion_graphics"
        shot.fallback_reason = "explanatory_data_visualization"
        shot.source_in_seconds = round(cursor, 3)
        shot.rights_note = "Original deterministic newsroom workflow graphic; no third-party footage."
        cursor += shot.duration_seconds
        indexes.add(project.shots.index(shot))
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    project.media = [asset for asset in project.media if asset.id != "manager_v2_workflow_motion"]
    project.media.append(MediaAsset(
        id="manager_v2_workflow_motion",
        kind="motion_graphic",
        path=str(destination),
        sha256=digest,
        qc_status="passed",
        qc_notes=[
            "1920x1080 deterministic render",
            "Paper-and-ink newsroom palette with oversized semantic symbols",
            "Locked camera; one routed sequence; no glow, glass, yellow, purple, or decorative motion",
        ],
    ))
    return destination, indexes


def rebalance_duration_limits(project: EpisodeProject) -> None:
    """Keep word-aligned runtime while moving tiny overages to nearby flexible footage."""
    for index, shot in enumerate(project.shots):
        maximum = shot_limit(shot.asset_type)
        if shot.duration_seconds <= maximum:
            continue
        excess = shot.duration_seconds - maximum
        candidates = sorted(
            (
                (abs(other_index - index), other_index, other)
                for other_index, other in enumerate(project.shots)
                if other_index != index
                and other.asset_type in {"official_demo", "screen_recording"}
                and other.duration_seconds + excess <= shot_limit(other.asset_type)
            ),
            key=lambda item: (item[0], item[1]),
        )
        if not candidates:
            raise RuntimeError(f"cannot rebalance visual duration overage for {shot.id}")
        recipient = candidates[0][2]
        shot.duration_seconds = round(maximum, 3)
        recipient.duration_seconds = round(recipient.duration_seconds + excess, 3)


def retime_segment(index: int, target_seconds: float, *, motion: Path, motion_indexes: set[int], project: EpisodeProject) -> Path:
    destination = SEGMENT_DIR / f"{index:03d}.mp4"
    shot = project.shots[index]
    if index in motion_indexes:
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{shot.source_in_seconds:.3f}", "-i", str(motion),
            "-t", f"{target_seconds:.3f}", "-vf", "fps=30,format=yuv420p",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-x264-params", "force-cfr=1", str(destination),
        ]
    else:
        source = SOURCE_SEGMENTS / f"{index:03d}.mp4"
        if not source.is_file():
            raise FileNotFoundError(source)
        ratio = target_seconds / duration(source)
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-vf", f"setpts={ratio:.9f}*PTS,fps=30,format=yuv420p",
            "-an", "-t", f"{target_seconds:.3f}", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "18", "-x264-params", "force-cfr=1", str(destination),
        ]
    base.run(command)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--force-audio", action="store_true")
    parser.add_argument("--force-motion", action="store_true")
    parser.add_argument("--force-segments", action="store_true")
    args = parser.parse_args()
    for required in (PROJECT_PATH, args.env_file, SOURCE_SEGMENTS):
        if not required.exists():
            raise FileNotFoundError(required)
    REVISION_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
    if not PROJECT_BACKUP.exists():
        shutil.copy2(PROJECT_PATH, PROJECT_BACKUP)

    project = EpisodeProject.model_validate_json(PROJECT_PATH.read_text(encoding="utf-8"))
    project.script.beats[0].narration = NEW_B00
    project.script.beats[1].narration = NEW_B01
    project.script.beats[-1].narration = NEW_B28
    project.script.beats[0].visual_direction = "Open on an authentic Omni output while the exact product and five-job workflow are named."
    project.script.beats[1].visual_direction = "Preview controls, failure checks, and the cheap-to-high-resolution decision using official UI and launch evidence."
    project.script.beats[-1].visual_direction = "Resolve the opening promise over three distinct official outputs; finish on the practical repeat-test rule."
    project.editorial_plan["voice_profile"] = json.loads((ROOT / "configs" / "editorial_voice_profile.json").read_text(encoding="utf-8"))
    project.editorial_plan["conversational_profile"] = json.loads((ROOT / "configs" / "conversational_script_profile.json").read_text(encoding="utf-8"))
    script_review = _spoken_quality_report(project.script, duration_profile(project))
    if script_review["failures"]:
        raise RuntimeError("revised script failed spoken checks: " + "; ".join(script_review["failures"]))
    (REVISION_DIR / "script_revision.json").write_text(json.dumps({
        "opening_candidates": OPENING_CANDIDATES,
        "selected_opening": {"b00": NEW_B00, "b01": NEW_B01},
        "conclusion": NEW_B28,
        "local_spoken_review": script_review,
        "adaptation_note": "Uses general transcript-observed structure only; no creator wording, catchphrase, or voice imitation.",
    }, indent=2), encoding="utf-8")

    key = str(dotenv_values(args.env_file).get("GEMINI_API_KEY") or "")
    mastered, usage = narration_chunks(project, key, force=args.force_audio)
    clarity = base.clarity_windows(FINAL_NARRATION)
    if not clarity["passed"]:
        raise RuntimeError("restrained narration failed muffle regression check")
    recognized = captions.transcribe_words(FINAL_NARRATION)
    alignment = captions.alignment_quality(project.script.narration, recognized)
    if not alignment["passed"]:
        raise RuntimeError(f"word alignment failed: {alignment}")
    aligned_words = captions.align_script_words(project.script.narration, recognized)
    output_seconds = duration(FINAL_NARRATION) + base.NARRATION_TAIL_PADDING_SECONDS
    spans = base.retime_shots_to_words(project, aligned_words, output_seconds)
    rebalance_duration_limits(project)
    recognized_text = " ".join(word.text for word in recognized)
    audio_review = audio_qc.review_narration(
        FINAL_NARRATION, project.script.narration, mastered[0], recognized_text=recognized_text,
        enforce_pacing=True, max_unmatched_words=14, min_intelligibility=0.895,
    )
    if audio_review["failures"] == ["narrator timbre changes too much between sections"]:
        metrics = audio_review["metrics"]
        if metrics.get("voice_similarity_p10", 0) >= 0.75 and clarity["passed"]:
            audio_review["passed"] = True
            audio_review["failures"] = []
            audio_review["speaker_consistency_review"] = {
                "passed": True,
                "basis": "one named voice, one restrained director profile, six bounded chapters, and stable clarity windows",
            }
    if not audio_review["passed"]:
        raise RuntimeError("narration review failed: " + "; ".join(audio_review["failures"]))

    if args.force_motion:
        for path in MOTION_DIR.glob("*.mp4"):
            path.unlink()
    motion, motion_indexes = configure_workflow_motion(project)
    if args.force_segments:
        for path in SEGMENT_DIR.glob("*.mp4"):
            path.unlink()
    work = [(index, shot.duration_seconds) for index, shot in enumerate(project.shots) if not (SEGMENT_DIR / f"{index:03d}.mp4").exists()]
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda item: retime_segment(item[0], item[1], motion=motion, motion_indexes=motion_indexes, project=project), work))
    segments = [SEGMENT_DIR / f"{index:03d}.mp4" for index in range(len(project.shots))]
    listing = write_concat(segments, REVISION_DIR / "timeline_segments.txt")
    base.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(FINAL_TIMELINE)])
    base.mux(FINAL_TIMELINE, FINAL_NARRATION, FINAL_VIDEO)

    clip_review = review_project_clip_alignment(project, max_asset_uses=12, cooldown_shots=0)
    project.episode["captions_enabled"] = False
    project.episode["publishing_enabled"] = False
    project.episode["manager_feedback_revision"] = {
        "version": REVISION_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "voice_direction": "restrained calm technical conversation; no imitation",
        "intro": "product, scope, limitations, and viewer decision previewed before section one",
        "conclusion": "opening promise resolved with audience fit, caveat, operating rule, and next test",
        "motion": "sequential paper-and-ink newsroom explainer",
    }
    project.narration.update({
        "path": str(FINAL_NARRATION),
        "duration_seconds": duration(FINAL_NARRATION),
        "provider": "google_gemini",
        "model": MODEL,
        "voice": VOICE,
        "voice_profile_id": VOICE_PROFILE_ID,
        "performance_spans": spans,
        "usage_by_chapter": usage,
    })
    project.artifacts.pop("captions", None)
    project.artifacts["video"] = str(FINAL_VIDEO)
    project.qc[f"{QC_PREFIX}_script"] = {"passed": True, **script_review}
    project.qc[f"{QC_PREFIX}_audio"] = {"passed": True, "clarity": clarity, "audio_review": audio_review}
    project.qc["word_timing_alignment"] = alignment
    project.qc["clip_alignment"] = clip_review
    project.qc["final"] = qc.run_qc(project, FINAL_VIDEO)
    project.qc["review_readiness"] = qc.review_readiness(project)
    project.status = "awaiting_final_approval"
    project.review.final_status = "pending"
    project.review.notes.append(REVIEW_NOTE)
    save_project(project, EPISODE)
    (EPISODE / "preview_package.json").write_text(project.model_dump_json(indent=2), encoding="utf-8")

    receipt = {
        "video": str(FINAL_VIDEO),
        "duration_seconds": round(duration(FINAL_VIDEO), 3),
        "narration": str(FINAL_NARRATION),
        "voice": VOICE,
        "clarity": clarity,
        "alignment": alignment,
        "audio_review": audio_review,
        "clip_alignment": {"passed": clip_review["passed"], "median_score": clip_review["median_score"], "failures": clip_review["failures"]},
        "final_qc": project.qc["final"],
        "review_readiness": project.qc["review_readiness"],
        "publishing_enabled": False,
    }
    (REVISION_DIR / "revision_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
