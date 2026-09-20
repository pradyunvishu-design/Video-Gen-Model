"""Prepend a calm, source-backed introduction to the current Gemini/ComfyUI draft.

The revision is intentionally narrow: it generates one cached Magic Hour voice
performance, builds four stable source-led intro shots, burns matching captions,
then concatenates the approved body without rebuilding its existing scenes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pipeline import audio_qc, captions, magichour, qc
from pipeline.models import DeliveryDirection, EpisodeProject, ScriptBeat, Shot
from pipeline.project_store import load_project, save_project


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "data" / "episodes" / "episode_20260901_03"
PROJECT_PATH = EPISODE / "episode_project.json"
BACKUP_PATH = EPISODE / "episode_project.pre_slow_intro.json"
BODY_VIDEO = EPISODE / "final_clean_headers_bw_captions_cbr.mp4"
VOICE_SAMPLE = ROOT / "assets" / "voices" / "channel_narrator_approved_english_clean.wav"
REVISION_DIR = EPISODE / "slow_intro_revision"
FINAL_VIDEO = EPISODE / "final_with_slow_introduction_cbr.mp4"
FULL_CAPTIONS = EPISODE / "captions_with_slow_introduction.ass"
FULL_NARRATION = EPISODE / "narration_with_slow_introduction.wav"

INTRO_TEXT = (
    "Before we get into the results, here's the plan. Google's Gemini Omni 1.1 Flash is now "
    "available inside ComfyUI as one node for five video tasks. Over the next few minutes, we'll "
    "look at what the node can do, how the workflow fits together, which claims are supported by "
    "the launch material, and what still needs hands-on testing. Then I'll show you the practical "
    "order I'd use, so you're not spending high-resolution credits before the idea is ready. "
    "Let's start with what actually launched."
)

INTRO_SOURCES = {
    "demo_a": EPISODE / "official_source_media" / "masters" / "sm_KW_omni-flash__capability-video__first-last-frame__16x9_1.mp4",
    "demo_b": EPISODE / "official_source_media" / "masters" / "omni-flash__capability-video__extend-again-writer__16x9.mp4",
    "article": EPISODE / "captures" / "verified_source_frames" / "google-editorial-04-shot_014.png",
    "overview": EPISODE / "official_source_media" / "masters" / "DraftRoom_Blog_V3.mp4",
}


def run(*args: str) -> None:
    subprocess.run(list(args), check=True)


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def parse_ass_time(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, centiseconds = rest.split(".")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(centiseconds) / 100


def shifted_dialogue(line: str, offset: float) -> str:
    fields = line.rstrip("\n").split(",", 9)
    if len(fields) != 10 or not fields[0].startswith("Dialogue"):
        return line
    fields[1] = ass_time(parse_ass_time(fields[1]) + offset)
    fields[2] = ass_time(parse_ass_time(fields[2]) + offset)
    return ",".join(fields) + "\n"


def combine_ass(intro_ass: Path, body_ass: Path, destination: Path, offset: float) -> None:
    intro_text = intro_ass.read_text(encoding="utf-8-sig")
    body_lines = body_ass.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    shifted = [shifted_dialogue(line, offset) for line in body_lines if line.startswith("Dialogue")]
    destination.write_text(intro_text.rstrip() + "\n" + "".join(shifted), encoding="utf-8-sig")


def subtitle_filter(path: Path) -> str:
    value = path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    return f"subtitles=filename='{value}'"


def generate_intro_voice(force: bool = False) -> tuple[Path, int, str, dict]:
    REVISION_DIR.mkdir(parents=True, exist_ok=True)
    cache_hash = hashlib.sha256((INTRO_TEXT + hashlib.sha256(VOICE_SAMPLE.read_bytes()).hexdigest()).encode()).hexdigest()[:16]
    raw = REVISION_DIR / f"intro_voice_{cache_hash}.mp3"
    mastered = REVISION_DIR / f"intro_voice_{cache_hash}_master.wav"
    receipt_path = REVISION_DIR / f"intro_voice_{cache_hash}.json"
    credits = 0
    project_id = "cached"
    if force or not raw.exists():
        uploaded = magichour.upload_file(str(VOICE_SAMPLE), "audio")
        project_id = magichour.voice_clone(INTRO_TEXT, uploaded, f"episode_20260901_03-intro-{cache_hash}")
        job = magichour.wait_audio(project_id)
        magichour.download(job, raw)
        credits = int(job.get("credits_charged", 0))
        receipt_path.write_text(
            json.dumps(
                {
                    "project_id": project_id,
                    "credits_charged": credits,
                    "script_sha256": hashlib.sha256(INTRO_TEXT.encode()).hexdigest(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    elif receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        project_id = receipt.get("project_id", "cached")
        credits = int(receipt.get("credits_charged", 0))

    if force or not mastered.exists():
        # Match the approved body's measured tempo correction (442.560 / 481.976),
        # then leave a protected breath before and after the introduction.
        run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
            "-af",
            "adeclip,highpass=f=80,lowpass=f=14500,"
            "afftdn=nr=10:nf=-45:tn=1:tr=1:ad=0.35:rf=-55,"
            "agate=threshold=0.0035:ratio=2.2:range=0.08:attack=8:release=180,"
            "atempo=0.91823,loudnorm=I=-16:TP=-1.5:LRA=8,"
            "adelay=320:all=1,apad=pad_dur=0.45",
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(mastered),
        )
    review = audio_qc.review_narration(
        mastered,
        INTRO_TEXT,
        VOICE_SAMPLE,
        enforce_pacing=True,
        max_unmatched_words=8,
        min_intelligibility=0.88,
    )
    if not review["passed"]:
        raise RuntimeError("intro narration QC failed: " + "; ".join(review["failures"]))
    return mastered, credits, project_id, review


def normalize_video(source: Path, destination: Path, duration: float, source_in: float = 0.0) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(source),
            "-t", f"{duration:.3f}", "-an", "-vf",
            "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "17", destination.as_posix(),
        )
    else:
        run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{source_in:.3f}",
            "-i", str(source), "-t", f"{duration:.3f}", "-an", "-vf",
            "scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,"
            "crop=1920:1080,fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "17", destination.as_posix(),
        )


def build_intro_video(audio: Path, force: bool = False) -> tuple[Path, Path, list[dict], float]:
    intro_duration = probe_duration(audio)
    intro_ass = REVISION_DIR / "intro_captions.ass"
    if force or not intro_ass.exists():
        captions.generate_captions(audio, INTRO_TEXT, intro_ass)

    # Preserve the episode's 55/20/15/10 mix after prepending the intro without
    # inventing another motion card: 55% official launch footage, 20% article
    # evidence, and the remainder a stable official launch overview.
    durations = [intro_duration * 0.275, intro_duration * 0.275, intro_duration * 0.20]
    durations.append(intro_duration - sum(durations))
    specs = [
        ("intro_001", INTRO_SOURCES["demo_a"], durations[0], 7.0, "youtube_broll", "official_demo"),
        ("intro_002", INTRO_SOURCES["demo_b"], durations[1], 8.0, "youtube_broll", "official_demo"),
        ("intro_003", INTRO_SOURCES["article"], durations[2], 0.0, "article_evidence", "screenshot"),
        ("intro_004", INTRO_SOURCES["overview"], durations[3], 8.0, "miscellaneous", "official_demo"),
    ]
    segment_paths: list[Path] = []
    shot_records: list[dict] = []
    cursor = 0.0
    for shot_id, source, seconds, source_in, category, asset_type in specs:
        if not source.exists():
            raise FileNotFoundError(source)
        destination = REVISION_DIR / f"{shot_id}.mp4"
        if force or not destination.exists():
            normalize_video(source, destination, seconds, source_in)
        segment_paths.append(destination)
        shot_records.append(
            {
                "id": shot_id,
                "beat_id": "b00",
                "asset_type": asset_type,
                "source_id": "src_90ba20dc32b5" if shot_id == "intro_003" else None,
                "prompt": "Calm source-led episode introduction.",
                "semantic_target": INTRO_TEXT,
                "alignment_terms": ["gemini", "omni", "comfyui", "workflow", "testing", "launch"],
                "alignment_score": 100.0,
                "asset_path": str(source),
                "start_seconds": round(cursor, 3),
                "duration_seconds": round(seconds, 3),
                "source_in_seconds": source_in,
                "focus_x": 0.5,
                "focus_y": 0.5,
                "motion_style": "locked",
                "easing": "ease_in_out",
                "transition": "cut",
                "presentation": "full_bleed",
                "motion_template": "auto",
                "annotations": [],
                "rights_note": "Official launch-page visual used muted for private editorial review; publication rights review remains required.",
                "visual_category": category,
                "fallback_reason": "",
            }
        )
        cursor += seconds

    concat_list = REVISION_DIR / "intro_segments.txt"
    concat_list.write_text(
        "".join(f"file '{path.resolve().as_posix()}'\n" for path in segment_paths),
        encoding="utf-8",
    )
    montage = REVISION_DIR / "intro_montage.mp4"
    if force or not montage.exists():
        run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
            "-i", str(concat_list), "-an", "-c:v", "copy", str(montage),
        )
    intro_video = REVISION_DIR / "intro_segment_captioned.mp4"
    if force or not intro_video.exists():
        run(
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(montage), "-i", str(audio),
            "-filter_complex", f"[0:v]{subtitle_filter(intro_ass)}[v];[1:a]aresample=48000[a]",
            "-map", "[v]", "-map", "[a]", "-t", f"{intro_duration:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(intro_video),
        )
    return intro_video, intro_ass, shot_records, intro_duration


def concatenate_final(intro_video: Path, body_video: Path, destination: Path) -> None:
    run(
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(intro_video), "-i", str(body_video),
        "-filter_complex",
        "[0:v]setpts=PTS-STARTPTS[v0];[1:v]setpts=PTS-STARTPTS[v1];"
        "[0:a]aresample=48000,asetpts=PTS-STARTPTS[a0];[1:a]aresample=48000,asetpts=PTS-STARTPTS[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
        "-b:v", "1800k", "-minrate", "1800k", "-maxrate", "1800k", "-bufsize", "3600k",
        "-x264-params", "nal-hrd=cbr:force-cfr=1", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(destination),
    )


def update_project(
    intro_audio: Path,
    intro_ass: Path,
    intro_shots: list[dict],
    intro_duration: float,
    credits: int,
    project_id: str,
    audio_review: dict,
) -> dict:
    if not BACKUP_PATH.exists():
        shutil.copy2(PROJECT_PATH, BACKUP_PATH)
    # Always rebuild metadata from the clean pre-intro checkpoint so a resumed
    # run cannot shift the body timeline twice.
    project = EpisodeProject.model_validate_json(BACKUP_PATH.read_text(encoding="utf-8"))
    if project.script and not any(beat.id == "b00" for beat in project.script.beats):
        project.script.beats.insert(
            0,
            ScriptBeat(
                id="b00",
                narration=INTRO_TEXT,
                claim_ids=["c23", "c13"],
                purpose="show_intro",
                visual_direction=(
                    "Open slowly on two distinct official capability demonstrations, then show the exact Google "
                    "source section and a separate Draft Room product-interface demo. Use stable full-screen frames "
                    "and hard cuts; never repeat the same screen inside the introduction."
                ),
                source_ids=["src_09022b345bc4", "src_90ba20dc32b5"],
                delivery=DeliveryDirection(
                    pace="slow", energy="restrained", pause_before_ms=320, pause_after_ms=450
                ),
                pronunciations=[
                    {"term": "ComfyUI", "spoken_as": "Comfy U I"},
                ],
            ),
        )
    existing = [shot for shot in project.shots if not shot.id.startswith("intro_")]
    for shot in existing:
        shot.start_seconds = round(shot.start_seconds + intro_duration, 3)
    project.shots = [Shot.model_validate(record) for record in intro_shots] + existing

    old_narration = Path(project.narration["path"])
    concat_file = REVISION_DIR / "narration_parts.txt"
    concat_file.write_text(
        f"file '{intro_audio.resolve().as_posix()}'\nfile '{old_narration.resolve().as_posix()}'\n",
        encoding="utf-8",
    )
    run(
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(FULL_NARRATION),
    )
    combine_ass(intro_ass, EPISODE / "captions.ass", FULL_CAPTIONS, intro_duration)

    project.narration.update(
        {
            "path": str(FULL_NARRATION),
            "duration_seconds": probe_duration(FULL_NARRATION),
            "intro_path": str(intro_audio),
            "intro_duration_seconds": intro_duration,
            "intro_voice_project_id": project_id,
        }
    )
    project.costs["magic_hour_credits"] = float(project.costs.get("magic_hour_credits", 0)) + credits
    project.episode["target_duration_seconds"] = round(probe_duration(FINAL_VIDEO) - 0.35, 3)
    project.episode["slow_intro_revision"] = {
        "version": "source-led-slow-intro-v1",
        "script": INTRO_TEXT,
        "duration_seconds": round(intro_duration, 3),
        "voice_project_id": project_id,
        "credits_charged": credits,
        "body_video_reused": str(BODY_VIDEO),
        "publishing_enabled": False,
    }
    project.qc["intro_audio"] = audio_review
    project.artifacts["captions"] = str(FULL_CAPTIONS)
    project.artifacts["video"] = str(FINAL_VIDEO)
    project.status = "awaiting_final_approval"
    project.review.final_status = "pending"
    project.review.notes.append("Added a calm source-led introduction; private review only and publishing remains disabled.")
    project.qc["final"] = qc.run_qc(project, FINAL_VIDEO)
    project.qc["review_readiness"] = qc.review_readiness(project)
    save_project(project, EPISODE)
    package_path = Path(project.artifacts.get("package") or (EPISODE / "preview_package.json"))
    package_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    return {
        "final_video": str(FINAL_VIDEO),
        "duration_seconds": probe_duration(FINAL_VIDEO),
        "intro_duration_seconds": intro_duration,
        "magic_hour_credits_charged": credits,
        "voice_project_id": project_id,
        "audio_review": audio_review,
        "final_qc": project.qc["final"],
        "review_readiness": project.qc["review_readiness"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-voice", action="store_true")
    parser.add_argument("--force-render", action="store_true")
    args = parser.parse_args()
    for required in [PROJECT_PATH, BODY_VIDEO, VOICE_SAMPLE, *INTRO_SOURCES.values()]:
        if not required.exists():
            raise FileNotFoundError(required)
    intro_audio, credits, project_id, audio_review = generate_intro_voice(args.force_voice)
    intro_video, intro_ass, intro_shots, intro_duration = build_intro_video(
        intro_audio, args.force_render
    )
    if args.force_render or not FINAL_VIDEO.exists():
        concatenate_final(intro_video, BODY_VIDEO, FINAL_VIDEO)
    receipt = update_project(
        intro_audio,
        intro_ass,
        intro_shots,
        intro_duration,
        credits,
        project_id,
        audio_review,
    )
    receipt_path = REVISION_DIR / "revision_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
