"""Rebuild the current episode with one natural narration pace and cleaner audio.

This revision deliberately reuses the approved narration performances and the
already-approved visual edit.  It removes the artificial full-body slowdown,
applies one conservative cleanup/mastering chain to both intro and body, and
retimes the two visual sections independently so burned captions stay aligned.
No provider calls or new credits are required.
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

from pipeline import audio_qc, qc
from pipeline.models import EpisodeProject
from pipeline.project_store import save_project


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "data" / "episodes" / "episode_20260901_03"
PROJECT_PATH = EPISODE / "episode_project.json"
PROJECT_BACKUP = EPISODE / "episode_project.pre_uniform_voice.json"
SOURCE_VIDEO = EPISODE / "final_with_slow_introduction_cbr.mp4"
BODY_SOURCE = EPISODE / "narration_master_dc765ce77c172f88.wav"
VOICE_REFERENCE = ROOT / "assets" / "voices" / "channel_narrator_approved_english_clean.wav"
OLD_CAPTIONS = EPISODE / "captions_with_slow_introduction.ass"
REVISION_DIR = EPISODE / "uniform_human_voice_revision"
INTRO_SOURCE = EPISODE / "slow_intro_revision" / "intro_voice_4fe1f68a08effce2_master.wav"

INTRO_CLEAN = REVISION_DIR / "intro_uniform_clean.wav"
BODY_CLEAN = REVISION_DIR / "body_uniform_clean.wav"
FULL_NARRATION = EPISODE / "narration_uniform_human_clean.wav"
FULL_CAPTIONS = EPISODE / "captions_uniform_human_clean.ass"
FINAL_VIDEO = EPISODE / "final_uniform_human_voice_clean_cbr.mp4"
RECEIPT = REVISION_DIR / "revision_receipt.json"

TARGET_WPM = 169.0
TAIL_SECONDS = 0.45

# The same chain is used on both performances. There is intentionally no noise
# gate: gates can swallow quiet consonants and sentence endings. The 60 Hz hum
# is removed by the high-pass; two mild notches suppress harmonics; adaptive FFT
# denoising handles the remaining steady buzz without making the voice watery.
CLEANUP_FILTER = (
    "highpass=f=82:p=2,"
    "equalizer=f=120:t=q:w=12:g=-9,"
    "equalizer=f=240:t=q:w=10:g=-4,"
    "afftdn=nr=10:nf=-50:tn=1:tr=1:ad=0.35:rf=-55,"
    "deesser=i=0.16:m=0.35:f=0.52,"
    "acompressor=threshold=-20dB:ratio=1.65:attack=18:release=190:makeup=1.5dB,"
    "loudnorm=I=-16:TP=-1.5:LRA=8"
)


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def duration(path: Path) -> float:
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


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?", text))


def clean_and_retime(source: Path, destination: Path, target_seconds: float) -> float:
    source_seconds = duration(source)
    tempo = source_seconds / target_seconds
    if not 0.5 <= tempo <= 2.0:
        raise ValueError(f"unsupported atempo {tempo:.4f} for {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-af", f"{CLEANUP_FILTER},atempo={tempo:.8f}",
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(destination),
        ]
    )
    return tempo


def concatenate_audio(intro: Path, body: Path, destination: Path) -> None:
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(intro), "-i", str(body),
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
            "-map", "[a]", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le",
            str(destination),
        ]
    )


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


def map_time(value: float, old_intro: float, new_intro: float, body_scale: float) -> float:
    if value <= old_intro:
        return value * new_intro / old_intro
    return new_intro + (value - old_intro) * body_scale


def retime_ass(
    source: Path, destination: Path, old_intro: float, new_intro: float, body_scale: float,
) -> None:
    lines: list[str] = []
    for line in source.read_text(encoding="utf-8-sig").splitlines(keepends=True):
        fields = line.rstrip("\r\n").split(",", 9)
        if len(fields) == 10 and fields[0].startswith("Dialogue"):
            fields[1] = ass_time(map_time(parse_ass_time(fields[1]), old_intro, new_intro, body_scale))
            fields[2] = ass_time(map_time(parse_ass_time(fields[2]), old_intro, new_intro, body_scale))
            newline = "\r\n" if line.endswith("\r\n") else "\n"
            line = ",".join(fields) + newline
        lines.append(line)
    destination.write_text("".join(lines), encoding="utf-8-sig")


def render_retimed_video(
    old_intro: float, new_intro: float, old_body_audio: float, new_body: float,
) -> None:
    source_total = duration(SOURCE_VIDEO)
    source_body_visual = source_total - old_intro
    target_body_visual = new_body + TAIL_SECONDS
    intro_scale = new_intro / old_intro
    body_visual_scale = target_body_visual / source_body_visual
    target_total = new_intro + target_body_visual
    video_filter = (
        f"[0:v]trim=start=0:end={old_intro:.6f},setpts=(PTS-STARTPTS)*{intro_scale:.9f},fps=30[v0];"
        f"[0:v]trim=start={old_intro:.6f},setpts=(PTS-STARTPTS)*{body_visual_scale:.9f},fps=30[v1];"
        "[v0][v1]concat=n=2:v=1:a=0[v]"
    )
    audio_filter = f"[1:a]apad=pad_dur={TAIL_SECONDS:.3f}[a]"
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(SOURCE_VIDEO), "-i", str(FULL_NARRATION),
            "-filter_complex", video_filter + ";" + audio_filter,
            "-map", "[v]", "-map", "[a]", "-t", f"{target_total:.6f}",
            "-c:v", "libx264", "-preset", "fast", "-b:v", "4000k",
            "-minrate", "4000k", "-maxrate", "4000k", "-bufsize", "8000k",
            "-x264-params", "nal-hrd=cbr:force-cfr=1", "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(FINAL_VIDEO),
        ]
    )


def update_project(
    project: EpisodeProject,
    old_intro: float,
    new_intro: float,
    old_body_audio: float,
    new_body: float,
    audio_review: dict,
    before_metrics: dict,
    after_metrics: dict,
) -> None:
    intro_scale = new_intro / old_intro
    body_scale = new_body / old_body_audio
    for shot in project.shots:
        if shot.start_seconds < old_intro or shot.id.startswith("intro_"):
            shot.start_seconds = round(shot.start_seconds * intro_scale, 3)
            shot.duration_seconds = round(shot.duration_seconds * intro_scale, 3)
        else:
            shot.start_seconds = round(new_intro + (shot.start_seconds - old_intro) * body_scale, 3)
            shot.duration_seconds = round(shot.duration_seconds * body_scale, 3)

    final_seconds = duration(FINAL_VIDEO)
    project.narration.update(
        {
            "path": str(FULL_NARRATION),
            "duration_seconds": duration(FULL_NARRATION),
            "intro_path": str(INTRO_CLEAN),
            "intro_duration_seconds": new_intro,
            "body_path": str(BODY_CLEAN),
            "body_duration_seconds": new_body,
            "uniform_delivery_target_wpm": TARGET_WPM,
            "cleanup_profile": "hum-safe-natural-v1",
        }
    )
    project.episode["target_duration_seconds"] = round(final_seconds - TAIL_SECONDS, 3)
    project.episode["uniform_voice_revision"] = {
        "version": "uniform-human-delivery-v1",
        "target_wpm": TARGET_WPM,
        "noise_gate_used": False,
        "provider_calls": 0,
        "credits_charged": 0,
        "source_body": str(BODY_SOURCE),
        "rendered_at": datetime.now(timezone.utc).isoformat(),
        "publishing_enabled": False,
    }
    project.artifacts["captions"] = str(FULL_CAPTIONS)
    project.artifacts["video"] = str(FINAL_VIDEO)
    project.qc["uniform_voice_audio"] = audio_review
    project.qc["uniform_voice_noise_comparison"] = {
        "before": before_metrics,
        "after": after_metrics,
    }
    project.status = "awaiting_final_approval"
    project.review.final_status = "pending"
    project.review.notes.append(
        "Rebuilt the full episode at one natural delivery pace and applied voice-safe hum/static cleanup; publishing remains disabled."
    )
    project.qc["final"] = qc.run_qc(project, FINAL_VIDEO)
    project.qc["review_readiness"] = qc.review_readiness(project)
    save_project(project, EPISODE)
    package = Path(project.artifacts.get("package") or (EPISODE / "preview_package.json"))
    package.write_text(project.model_dump_json(indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    for path in [PROJECT_PATH, SOURCE_VIDEO, BODY_SOURCE, INTRO_SOURCE, VOICE_REFERENCE, OLD_CAPTIONS]:
        if not path.is_file():
            raise FileNotFoundError(path)
    REVISION_DIR.mkdir(parents=True, exist_ok=True)
    if not PROJECT_BACKUP.exists():
        shutil.copy2(PROJECT_PATH, PROJECT_BACKUP)

    project = EpisodeProject.model_validate_json(PROJECT_PATH.read_text(encoding="utf-8"))
    intro_beat = next(beat for beat in project.script.beats if beat.id == "b00")
    body_text = "\n\n".join(beat.narration for beat in project.script.beats if beat.id != "b00")
    intro_words = word_count(intro_beat.narration)
    body_words = word_count(body_text)
    target_intro = intro_words / TARGET_WPM * 60
    target_body = body_words / TARGET_WPM * 60
    old_intro = float(project.narration.get("intro_duration_seconds") or duration(INTRO_SOURCE))
    old_body_audio = duration(EPISODE / "narration_master_dc765ce77c172f88_fidelity_481976ms.wav")

    if args.force or not INTRO_CLEAN.exists():
        intro_tempo = clean_and_retime(INTRO_SOURCE, INTRO_CLEAN, target_intro)
    else:
        intro_tempo = duration(INTRO_SOURCE) / duration(INTRO_CLEAN)
    if args.force or not BODY_CLEAN.exists():
        body_tempo = clean_and_retime(BODY_SOURCE, BODY_CLEAN, target_body)
    else:
        body_tempo = duration(BODY_SOURCE) / duration(BODY_CLEAN)
    new_intro = duration(INTRO_CLEAN)
    new_body = duration(BODY_CLEAN)
    concatenate_audio(INTRO_CLEAN, BODY_CLEAN, FULL_NARRATION)
    body_scale = new_body / old_body_audio
    retime_ass(OLD_CAPTIONS, FULL_CAPTIONS, old_intro, new_intro, body_scale)
    render_retimed_video(old_intro, new_intro, old_body_audio, new_body)

    before_metrics = audio_qc.technical_metrics(
        EPISODE / "narration_with_slow_introduction.wav", VOICE_REFERENCE
    )
    after_metrics = audio_qc.technical_metrics(FULL_NARRATION, VOICE_REFERENCE)
    audio_review = audio_qc.review_narration(
        FULL_NARRATION,
        project.script.narration,
        VOICE_REFERENCE,
        enforce_pacing=True,
        max_unmatched_words=18,
        min_intelligibility=0.88,
    )
    update_project(
        project, old_intro, new_intro, old_body_audio, new_body,
        audio_review, before_metrics, after_metrics,
    )
    receipt = {
        "final_video": str(FINAL_VIDEO),
        "sha256": hashlib.sha256(FINAL_VIDEO.read_bytes()).hexdigest(),
        "duration_seconds": duration(FINAL_VIDEO),
        "target_wpm": TARGET_WPM,
        "intro_words": intro_words,
        "body_words": body_words,
        "intro_tempo": intro_tempo,
        "body_tempo": body_tempo,
        "intro_duration_seconds": new_intro,
        "body_duration_seconds": new_body,
        "provider_calls": 0,
        "credits_charged": 0,
        "audio_review": audio_review,
        "noise_before": before_metrics,
        "noise_after": after_metrics,
        "final_qc": project.qc["final"],
        "review_readiness": project.qc["review_readiness"],
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
