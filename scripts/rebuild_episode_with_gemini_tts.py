"""Replace the current episode narration with an original Gemini TTS presenter."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

from pipeline import audio_qc, captions, qc
from pipeline.gemini_tts import DEFAULT_MODEL, GeminiTTSClient
from pipeline.models import EpisodeProject
from pipeline.project_store import save_project
from pipeline.render_v2 import concat_audio, duration, make_silence, render_project


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "data" / "episodes" / "episode_20260901_03"
PROJECT_PATH = EPISODE / "episode_project.json"
PROJECT_BACKUP = EPISODE / "episode_project.pre_gemini_tts.json"
DEFAULT_ENV = Path(
    r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker"
)
VOICE = "Charon"
VOICE_PROFILE_ID = "gemini_charon_original_tech_presenter_v1"
VOICE_REFERENCE = (
    ROOT / "output" / "voice_canary" / "gemini_original_presenter" /
    "charon_canary_v3_paragraphs.wav"
)
FINAL_VIDEO = EPISODE / "final_gemini_human_presenter_cbr.mp4"
FINAL_NARRATION = EPISODE / "narration_gemini_human_presenter.wav"
FINAL_CAPTIONS = EPISODE / "captions_gemini_human_presenter.ass"
REVISION_DIR = EPISODE / "gemini_human_presenter_revision"
TARGET_MIN_SECONDS = 481.0
DEFAULT_POST_BEAT_PAUSE_MS = 750


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def speech_text(text: str) -> str:
    """Paragraph breaks encourage human sentence separation without changing words."""
    return "\n\n".join(re.split(r"(?<=[.!?])\s+", text.strip()))


def master_chunk(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-af", (
            "highpass=f=70:p=2,lowpass=f=15000,"
            "deesser=i=0.10:m=0.25:f=0.52,"
            "loudnorm=I=-16:TP=-1.5:LRA=8"
        ),
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(destination),
    ])
    return destination


def retime_shots(project: EpisodeProject, spans: dict[str, tuple[float, float]]) -> None:
    shots_by_beat: dict[str, list] = {}
    for shot in sorted(project.shots, key=lambda item: item.start_seconds):
        shots_by_beat.setdefault(shot.beat_id, []).append(shot)
    for beat_id, (start, end) in spans.items():
        shots = shots_by_beat.get(beat_id, [])
        if not shots:
            continue
        available = max(0.1, end - start)
        weights = [max(0.1, shot.duration_seconds) for shot in shots]
        total_weight = sum(weights)
        cursor = start
        for index, (shot, weight) in enumerate(zip(shots, weights)):
            shot.start_seconds = round(cursor, 3)
            if index == len(shots) - 1:
                shot.duration_seconds = round(max(0.1, end - cursor), 3)
            else:
                shot.duration_seconds = round(max(0.1, available * weight / total_weight), 3)
            cursor += shot.duration_seconds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--force-audio", action="store_true")
    parser.add_argument("--force-render", action="store_true")
    args = parser.parse_args()
    for required in [PROJECT_PATH, args.env_file, VOICE_REFERENCE]:
        if not required.is_file():
            raise FileNotFoundError(required)
    REVISION_DIR.mkdir(parents=True, exist_ok=True)
    if not PROJECT_BACKUP.exists():
        shutil.copy2(PROJECT_PATH, PROJECT_BACKUP)

    project = EpisodeProject.model_validate_json(PROJECT_PATH.read_text(encoding="utf-8"))
    if not project.script:
        raise RuntimeError("episode has no approved script")
    key = str(dotenv_values(args.env_file).get("GEMINI_API_KEY") or "")
    client = GeminiTTSClient(key, model=DEFAULT_MODEL, voice=VOICE)
    script_hash = hashlib.sha256(
        (project.script.narration + DEFAULT_MODEL + VOICE).encode("utf-8")
    ).hexdigest()[:16]
    audio_dir = REVISION_DIR / script_hash
    audio_dir.mkdir(parents=True, exist_ok=True)

    def generate_beat(beat) -> tuple[str, Path, dict]:
        raw = audio_dir / f"{beat.id}_raw.wav"
        mastered = audio_dir / f"{beat.id}_master.wav"
        if args.force_audio:
            raw.unlink(missing_ok=True)
            mastered.unlink(missing_ok=True)
        result = client.synthesize(speech_text(beat.narration), raw)
        if not mastered.exists():
            master_chunk(raw, mastered)
        words = len(re.findall(r"[A-Za-z0-9]+", beat.narration))
        seconds = duration(mastered)
        if seconds < max(1.0, words / 300 * 60) or seconds > words / 70 * 60 + 4:
            raise RuntimeError(f"implausible Gemini duration for {beat.id}: {seconds:.2f}s")
        return beat.id, mastered, result.usage

    generated: dict[str, Path] = {}
    usage_by_beat: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="gemini-tts") as executor:
        futures = [executor.submit(generate_beat, beat) for beat in project.script.beats]
        for future in as_completed(futures):
            beat_id, path, usage = future.result()
            generated[beat_id] = path
            usage_by_beat[beat_id] = usage

    voice_seconds = sum(duration(generated[beat.id]) for beat in project.script.beats)
    base_pauses = [
        max(DEFAULT_POST_BEAT_PAUSE_MS, int(beat.delivery.pause_after_ms))
        for beat in project.script.beats
    ]
    base_pause_seconds = sum(base_pauses) / 1000
    extra_needed = max(0.0, TARGET_MIN_SECONDS - voice_seconds - base_pause_seconds)
    adjustable = max(1, len(base_pauses) - 1)
    extra_each_ms = round(extra_needed * 1000 / adjustable)
    pauses = [
        value + (extra_each_ms if index < len(base_pauses) - 1 else 0)
        for index, value in enumerate(base_pauses)
    ]

    parts: list[Path] = []
    spans: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    for index, beat in enumerate(project.script.beats):
        beat_audio = generated[beat.id]
        start = cursor
        parts.append(beat_audio)
        cursor += duration(beat_audio)
        pause = audio_dir / f"{beat.id}_pause_{pauses[index]}ms.wav"
        if not pause.exists():
            make_silence(pause, pauses[index])
        parts.append(pause)
        cursor += pauses[index] / 1000
        spans[beat.id] = (start, cursor)
    concat_audio(parts, FINAL_NARRATION)
    narration_seconds = duration(FINAL_NARRATION)
    if not 480 <= narration_seconds <= 720:
        raise RuntimeError(f"Gemini narration runtime {narration_seconds:.2f}s is outside 8-12 minutes")

    audio_review = audio_qc.review_narration(
        FINAL_NARRATION,
        project.script.narration,
        VOICE_REFERENCE,
        enforce_pacing=True,
        max_unmatched_words=14,
        min_intelligibility=0.9,
    )
    if not audio_review["passed"]:
        raise RuntimeError("Gemini narration QC failed: " + "; ".join(audio_review["failures"]))
    captions.generate_captions(FINAL_NARRATION, project.script.narration, FINAL_CAPTIONS)

    retime_shots(project, spans)
    project.episode["target_duration_seconds"] = round(narration_seconds, 3)
    project.episode["voice_profile_id"] = VOICE_PROFILE_ID
    project.episode["gemini_tts_revision"] = {
        "provider": "google_gemini",
        "model": DEFAULT_MODEL,
        "voice": VOICE,
        "profile_id": VOICE_PROFILE_ID,
        "style": "original warm conversational technology journalist",
        "imitation_target": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "publishing_enabled": False,
    }
    project.narration = {
        "path": str(FINAL_NARRATION),
        "duration_seconds": narration_seconds,
        "provider": "google_gemini",
        "model": DEFAULT_MODEL,
        "voice": VOICE,
        "voice_profile_id": VOICE_PROFILE_ID,
        "voice_reference": str(VOICE_REFERENCE),
        "prebuilt_voice": True,
        "performance_spans": {
            key: {"start_seconds": round(value[0], 3), "end_seconds": round(value[1], 3)}
            for key, value in spans.items()
        },
        "usage_by_beat": usage_by_beat,
    }
    project.qc["gemini_tts_audio"] = audio_review
    project.artifacts["captions"] = str(FINAL_CAPTIONS)
    project.status = "rendering"
    project.review.final_status = "pending"
    save_project(project, EPISODE)

    cache_key = f"gemini-{script_hash}-{VOICE.casefold()}"
    rendered = EPISODE / f"final_{cache_key[:16]}.mp4"
    if args.force_render:
        rendered.unlink(missing_ok=True)
    if not rendered.exists():
        rendered = render_project(project, EPISODE, FINAL_NARRATION, FINAL_CAPTIONS, cache_key)
    if rendered.resolve() != FINAL_VIDEO.resolve():
        shutil.copy2(rendered, FINAL_VIDEO)

    project.artifacts["video"] = str(FINAL_VIDEO)
    project.status = "awaiting_final_approval"
    project.review.notes.append(
        "Replaced narration with an original Gemini prebuilt presenter voice; no creator voice was cloned or impersonated."
    )
    project.qc["final"] = qc.run_qc(project, FINAL_VIDEO)
    project.qc["review_readiness"] = qc.review_readiness(project)
    save_project(project, EPISODE)
    package = Path(project.artifacts.get("package") or (EPISODE / "preview_package.json"))
    package.write_text(project.model_dump_json(indent=2), encoding="utf-8")

    receipt = {
        "final_video": str(FINAL_VIDEO),
        "sha256": hashlib.sha256(FINAL_VIDEO.read_bytes()).hexdigest(),
        "duration_seconds": duration(FINAL_VIDEO),
        "narration_seconds": narration_seconds,
        "provider": "google_gemini",
        "model": DEFAULT_MODEL,
        "voice": VOICE,
        "voice_profile_id": VOICE_PROFILE_ID,
        "audio_review": audio_review,
        "final_qc": project.qc["final"],
        "review_readiness": project.qc["review_readiness"],
        "publishing_enabled": False,
    }
    (REVISION_DIR / "revision_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
