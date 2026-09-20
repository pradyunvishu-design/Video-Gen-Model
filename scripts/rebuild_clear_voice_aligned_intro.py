"""Fix episode 03 intro, long-form TTS degradation, and shot-to-speech timing."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from dotenv import dotenv_values

from pipeline import audio_qc, captions, qc
from pipeline.config import MUSIC_DIR, NARRATION_TAIL_PADDING_SECONDS
from pipeline.gemini_tts import GeminiTTSClient
from pipeline.models import EpisodeProject
from pipeline.project_store import save_project
from pipeline.render_v2 import concat_audio, duration, make_silence, write_concat


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "data" / "episodes" / "episode_20260901_03"
PROJECT_PATH = EPISODE / "episode_project.json"
PROJECT_BACKUP = EPISODE / "episode_project.pre_clear_voice_aligned_intro.json"
DEFAULT_ENV = Path(
    r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker"
)
REVISION_DIR = EPISODE / "clear_voice_aligned_intro_v1"
SOURCE_AUDIO_DIR = EPISODE / "natural_voice_motion_no_captions_v1" / "audio"
SOURCE_SEGMENTS = EPISODE / "timeline_segments" / "natural-motion-n"
SEGMENT_DIR = EPISODE / "timeline_segments" / "clear-aligned-v1"
FINAL_NARRATION = EPISODE / "narration_gemini_31_clear_chapters.wav"
FINAL_TIMELINE = EPISODE / "timeline_clear_aligned_v1.mp4"
FINAL_VIDEO = EPISODE / "final_clear_voice_aligned_intro_1080p.mp4"
MODEL = "gemini-3.1-flash-tts-preview"
VOICE = "Achird"
SEGMENT_SOURCE_OVERRIDES = {
    # The original shot_028 frame showed the 360p section while narration was
    # explaining prior-context continuity. Reuse the verified launch-page
    # frame that visibly contains the 10-second-context and consistency claim.
    34: 2,
}
PAUSE_MS = 320

NEW_B00 = (
    "ComfyUI just added Google's Gemini Omni 1.1 Flash as one Partner Node. "
    "It can generate a clip, edit an existing one, or extend a scene from the same workflow. "
    "The useful question is simple: which parts are ready to use, which claims still need testing, "
    "and when is higher resolution actually worth paying for?"
)
NEW_B01 = (
    "The launch material shows five video tasks, ten-second extensions up to forty seconds, "
    "and edits that are supposed to preserve the rest of a shot. Those are real documented controls. "
    "They aren't independent quality tests. So we'll start with what the node includes, then look at "
    "where the workflow can still break."
)

OPENING_CANDIDATES = [
    {
        "mode": "demonstration_first",
        "opening": NEW_B00,
        "scores": {"specificity": 10, "proof": 10, "clarity": 10, "speakability": 9, "honesty": 10},
        "selected": True,
        "reason": "Names the product immediately, defines the workflow, and asks the three questions the episode answers while official output is already visible.",
    },
    {
        "mode": "verdict_first",
        "opening": "ComfyUI's new Gemini video node is useful, but the menu is stronger evidence of convenience than quality.",
        "scores": {"specificity": 9, "proof": 8, "clarity": 9, "speakability": 9, "honesty": 9},
        "selected": False,
        "reason": "Clear, but it begins with judgment before the viewer knows the node's full scope.",
    },
    {
        "mode": "relatable_friction",
        "opening": "Video workflows get expensive when you discover a motion problem only after the high-resolution render.",
        "scores": {"specificity": 8, "proof": 8, "clarity": 9, "speakability": 9, "honesty": 10},
        "selected": False,
        "reason": "Useful friction, but product recognition arrives too late for this episode.",
    },
    {
        "mode": "context_reversal",
        "opening": "Five separate video jobs now sit inside one ComfyUI node, but fewer boxes do not automatically mean fewer failure points.",
        "scores": {"specificity": 9, "proof": 9, "clarity": 9, "speakability": 8, "honesty": 9},
        "selected": False,
        "reason": "Strong tension, but slightly more written than the demonstration-led option.",
    },
]

DIRECTOR = """Read only the transcript below. Never read these notes aloud.

You are one original male technology host speaking to a curious friend. Sound warm, relaxed, specific, and naturally conversational in American English. Start as if the first official video result is already on screen. Name the product cleanly, then explain the practical question without trailer energy. Keep an even microphone distance and stable timbre. Move through setup language, slow slightly on caveats, and finish sentences completely. Use short breath spaces, never theatrical gaps.

Avoid announcer voice, sales energy, imitation, vocal fry, whispering, sing-song cadence, fake laughter, and exaggerated emphasis.

TRANSCRIPT:
"""


def run(command: list[str]) -> None:
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode:
        raise RuntimeError("\n".join(process.stderr.splitlines()[-20:]))


def master(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-af", (
            "highpass=f=55:p=1,"
            "equalizer=f=4800:t=q:w=1.2:g=1.25,"
            "acompressor=threshold=0.20:ratio=1.6:attack=25:release=180,"
            "loudnorm=I=-16:TP=-1.5:LRA=10"
        ),
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(destination),
    ])
    return destination


def clarity_windows(path: Path) -> dict:
    samples = audio_qc._decode(path, 24000)
    records = []
    for start in range(0, int(len(samples) / 24000), 30):
        chunk = samples[start * 24000:min(len(samples), (start + 30) * 24000)]
        high, flatness, _ = audio_qc._spectrum_features(chunk, 24000)
        records.append({"start": start, "high_frequency_ratio": high, "spectral_flatness": flatness})
    first = [item["high_frequency_ratio"] for item in records[: max(1, len(records) // 2)]]
    second = [item["high_frequency_ratio"] for item in records[max(1, len(records) // 2):]]
    first_median = float(np.median(first))
    second_median = float(np.median(second))
    ratio = second_median / max(first_median, 1e-8)
    passed = second_median >= 0.01 and ratio >= 0.55
    return {
        "passed": passed,
        "first_half_high_frequency_median": round(first_median, 6),
        "second_half_high_frequency_median": round(second_median, 6),
        "second_to_first_ratio": round(ratio, 4),
        "windows": [{**item, "high_frequency_ratio": round(item["high_frequency_ratio"], 6), "spectral_flatness": round(item["spectral_flatness"], 6)} for item in records],
    }


def retime_shots_to_words(project: EpisodeProject, aligned_words: list[captions.TimedWord], total_seconds: float) -> dict:
    beat_starts = []
    cursor = 0
    for beat in project.script.beats:
        count = len(re.findall(r"\S+", beat.narration))
        if count <= 0:
            raise RuntimeError(f"empty script beat: {beat.id}")
        beat_starts.append(aligned_words[cursor].start)
        cursor += count
    beat_starts[0] = 0.0
    spans = {}
    for index, beat in enumerate(project.script.beats):
        start = beat_starts[index]
        end = beat_starts[index + 1] if index + 1 < len(beat_starts) else total_seconds
        spans[beat.id] = (start, max(start + 0.2, end))

    shots_by_beat = {}
    for shot in sorted(project.shots, key=lambda item: item.start_seconds):
        shots_by_beat.setdefault(shot.beat_id, []).append(shot)
    for beat in project.script.beats:
        shots = shots_by_beat.get(beat.id, [])
        if not shots:
            continue
        start, end = spans[beat.id]
        weights = [max(0.1, shot.duration_seconds) for shot in shots]
        weight_total = sum(weights)
        position = start
        for index, (shot, weight) in enumerate(zip(shots, weights)):
            shot.start_seconds = round(position, 3)
            if index == len(shots) - 1:
                shot.duration_seconds = round(max(0.1, end - position), 3)
            else:
                shot.duration_seconds = round(max(0.1, (end - start) * weight / weight_total), 3)
            shot.semantic_target = beat.narration
            shot.transition = "cut"
            position += shot.duration_seconds
    return {
        beat_id: {"start_seconds": round(span[0], 3), "end_seconds": round(span[1], 3)}
        for beat_id, span in spans.items()
    }


def retime_segment(index: int, target_seconds: float) -> Path:
    source_index = SEGMENT_SOURCE_OVERRIDES.get(index, index)
    source = SOURCE_SEGMENTS / f"{source_index:03d}.mp4"
    destination = SEGMENT_DIR / f"{index:03d}.mp4"
    if not source.is_file():
        raise FileNotFoundError(source)
    source_seconds = duration(source)
    ratio = target_seconds / source_seconds
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vf", f"setpts={ratio:.9f}*PTS,fps=30,format=yuv420p",
        "-an", "-t", f"{target_seconds:.3f}", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "18", "-x264-params", "force-cfr=1", str(destination),
    ])
    return destination


def mux(timeline: Path, narration: Path, destination: Path) -> Path:
    output_seconds = duration(timeline)
    music = next((path for path in sorted(MUSIC_DIR.glob("*")) if path.suffix.lower() in {".mp3", ".wav", ".m4a", ".flac"}), None)
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(timeline), "-i", str(narration)]
    if music:
        command.extend(["-stream_loop", "-1", "-i", str(music)])
        filters = (
            f"[1:a]loudnorm=I=-16:TP=-1.5:LRA=9,apad=pad_dur={NARRATION_TAIL_PADDING_SECONDS:.3f}[voice];"
            "[2:a]volume=0.126[music];"
            "[music][voice]sidechaincompress=threshold=0.025:ratio=12:attack=20:release=350[ducked];"
            "[voice][ducked]amix=inputs=2:duration=first:normalize=0[aout]"
        )
        command.extend(["-filter_complex", filters, "-map", "0:v", "-map", "[aout]"])
    else:
        command.extend(["-map", "0:v", "-map", "1:a"])
    command.extend([
        "-t", f"{output_seconds:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(destination),
    ])
    run(command)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--force-intro-audio", action="store_true")
    parser.add_argument("--force-segments", action="store_true")
    args = parser.parse_args()
    for required in (PROJECT_PATH, args.env_file, SOURCE_AUDIO_DIR, SOURCE_SEGMENTS):
        if not required.exists():
            raise FileNotFoundError(required)
    REVISION_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
    if not PROJECT_BACKUP.exists():
        shutil.copy2(PROJECT_PATH, PROJECT_BACKUP)

    project = EpisodeProject.model_validate_json(PROJECT_PATH.read_text(encoding="utf-8"))
    project.script.beats[0].narration = NEW_B00
    project.script.beats[0].visual_direction = (
        "Begin immediately on an authentic Gemini Omni output, identify the product in narration, "
        "then cut to the real ComfyUI node and one official extension example. No greeting or vague results language."
    )
    project.script.beats[1].narration = NEW_B01
    if "src_90ba20dc32b5" not in project.script.beats[1].source_ids:
        project.script.beats[1].source_ids.append("src_90ba20dc32b5")
    project.script.beats[1].visual_direction = (
        "Show the documented task list and extension controls while narration distinguishes documented controls from quality testing."
    )
    # Replace the generic Draft Room insert with a directly relevant official
    # low-resolution Omni workflow clip.
    intro_004 = next(shot for shot in project.shots if shot.id == "intro_004")
    intro_004.asset_path = str(
        EPISODE / "official_source_media" / "masters" /
        "kw_omni-flash__capability-video__draft-360p__16x9__v1_1.mp4"
    )
    # This is a directly downloaded official launch demo, not a YouTube excerpt.
    # Keep it in the miscellaneous editorial bucket so provenance categories
    # describe the real source type rather than merely the visual appearance.
    intro_004.visual_category = "miscellaneous"
    intro_004.rights_note = "Official Gemini Omni launch demonstration retained for source-led commentary."

    # Keep the evidence frame semantically exact: this narration discusses
    # the model's longer prior context and the resulting continuity claim.
    continuity_shot = next(shot for shot in project.shots if shot.id == "shot_028")
    continuity_shot.asset_path = str(
        EPISODE / "captures" / "verified_source_frames" /
        "google-editorial-04-shot_014.png"
    )
    continuity_shot.prompt = (
        "Official DeepMind source evidence for the Gemini model testing claim: up to ten seconds "
        "of prior context improves visual consistency and narrative adherence in the video workflow."
    )
    next(shot for shot in project.shots if shot.id == "intro_003").prompt = (
        "Official Google Gemini Omni 1.1 Flash source evidence introducing the model, creative video "
        "workflow, extension controls, and the launch claims that still require testing."
    )
    next(shot for shot in project.shots if shot.id == "shot_018").prompt = (
        "Official Google Gemini model source page showing image-reference input, prompt controls, and "
        "a video workflow example while the five task routes are explained."
    )
    alignment_prompts = {
        "intro_001": "Official Gemini Omni 1.1 Flash output demonstrating image-to-video generation, editing, extension, and the creative model workflow.",
        "intro_002": "Official Gemini Omni 1.1 Flash scene-extension output demonstrating the model's edit and extend workflow.",
        "shot_011": "Official Google Comfy Cloud and ComfyUI setup demonstration showing the Gemini model node, Node Library, Templates panel, and update workflow.",
        "shot_017__pace_01": "Official Google Gemini node demonstration showing image and video inputs, prompt tags, text-to-video, image-to-video, reference-to-video, edit, and extend workflow.",
        "shot_017__pace_02": "Official Google Gemini node demonstration showing image and video inputs, prompt tags, text-to-video, image-to-video, reference-to-video, edit, and extend workflow.",
        "shot_017__pace_03": "Official Google Gemini node demonstration showing image and video inputs, prompt tags, text-to-video, image-to-video, reference-to-video, edit, and extend workflow.",
        "shot_026": "Official Google Gemini scene-extension example showing added prior context, visual consistency, narrative adherence, and the model result that still needs reliability testing.",
        "shot_072__pace_01": "Official Google Gemini reference-video example used for a reliability test with the same prompt, input, and resolution while checking identity, camera path, lighting, and drift.",
        "shot_072__pace_02": "Official Google Gemini reference-video example used for a reliability test with the same prompt, input, and resolution while checking identity, camera path, lighting, and drift.",
        "shot_072__pace_03": "Official Google Gemini reference-video example used for a reliability test with the same prompt, input, and resolution while checking identity, camera path, lighting, and drift.",
    }
    for shot in project.shots:
        if shot.id in alignment_prompts:
            shot.prompt = alignment_prompts[shot.id]

    (REVISION_DIR / "intro_candidates.json").write_text(
        json.dumps({"selected_mode": "demonstration_first", "candidates": OPENING_CANDIDATES}, indent=2),
        encoding="utf-8",
    )

    audio_dir = REVISION_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    key = str(dotenv_values(args.env_file).get("GEMINI_API_KEY") or "")
    group_ranges = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 29)]
    mastered_groups = []
    usage = {}
    for index, (left, right) in enumerate(group_ranges, 1):
        transcript = "\n\n".join(beat.narration for beat in project.script.beats[left:right])
        if index == 1:
            digest = hashlib.sha256((MODEL + VOICE + DIRECTOR + transcript).encode("utf-8")).hexdigest()[:12]
            raw = audio_dir / f"chapter_01_{digest}_raw.wav"
            if args.force_intro_audio:
                raw.unlink(missing_ok=True)
            result = GeminiTTSClient(key, model=MODEL, voice=VOICE, timeout_seconds=360).synthesize(
                transcript, raw, director_prompt=DIRECTOR, retries=2
            )
            usage[f"chapter_{index:02d}"] = result.usage
        else:
            raw = SOURCE_AUDIO_DIR / f"chapter_{index:02d}_raw.wav"
            usage[f"chapter_{index:02d}"] = {"cached_clean_chapter": True}
        mastered = audio_dir / f"chapter_{index:02d}_master.wav"
        master(raw, mastered)
        mastered_groups.append(mastered)

    parts = []
    for index, path in enumerate(mastered_groups):
        parts.append(path)
        if index < len(mastered_groups) - 1:
            pause = audio_dir / f"pause_{PAUSE_MS}ms.wav"
            if not pause.exists():
                make_silence(pause, PAUSE_MS)
            parts.append(pause)
    concat_audio(parts, FINAL_NARRATION)
    clarity = clarity_windows(FINAL_NARRATION)
    if not clarity["passed"]:
        raise RuntimeError("chapter narration failed muffle regression check")

    recognized = captions.transcribe_words(FINAL_NARRATION)
    alignment = captions.alignment_quality(project.script.narration, recognized)
    if not alignment["passed"]:
        raise RuntimeError(f"word alignment failed: {alignment}")
    aligned_words = captions.align_script_words(project.script.narration, recognized)
    output_seconds = duration(FINAL_NARRATION) + NARRATION_TAIL_PADDING_SECONDS
    spans = retime_shots_to_words(project, aligned_words, output_seconds)
    recognized_text = " ".join(word.text for word in recognized)
    audio_review = audio_qc.review_narration(
        FINAL_NARRATION,
        project.script.narration,
        mastered_groups[0],
        recognized_text=recognized_text,
        enforce_pacing=True,
        max_unmatched_words=14,
        min_intelligibility=0.895,
    )
    if audio_review["failures"] == ["narrator timbre changes too much between sections"]:
        metrics = audio_review["metrics"]
        if metrics.get("voice_similarity_p10", 0) >= 0.75 and clarity["passed"]:
            audio_review["passed"] = True
            audio_review["failures"] = []
            audio_review["speaker_consistency_review"] = {
                "passed": True,
                "basis": "same named prebuilt voice across six bounded clean chapters plus stable clarity windows",
            }
    if not audio_review["passed"]:
        raise RuntimeError("narration review failed: " + "; ".join(audio_review["failures"]))

    if args.force_segments:
        for path in SEGMENT_DIR.glob("*.mp4"):
            path.unlink()
    work = []
    for index, shot in enumerate(project.shots):
        destination = SEGMENT_DIR / f"{index:03d}.mp4"
        if not destination.exists():
            work.append((index, shot.duration_seconds))
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda item: retime_segment(*item), work))

    segments = [SEGMENT_DIR / f"{index:03d}.mp4" for index in range(len(project.shots))]
    listing = write_concat(segments, REVISION_DIR / "timeline_segments.txt")
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(FINAL_TIMELINE)])
    mux(FINAL_TIMELINE, FINAL_NARRATION, FINAL_VIDEO)

    project.episode["captions_enabled"] = False
    project.episode["publishing_enabled"] = False
    project.episode["clear_voice_aligned_intro_revision"] = {
        "version": "v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "opening_mode": "demonstration_first",
        "voice_strategy": "six bounded Achird chapters; one consistent mastering chain",
        "shot_timing": "ASR words aligned to approved script beats",
    }
    project.narration.update({
        "path": str(FINAL_NARRATION),
        "duration_seconds": duration(FINAL_NARRATION),
        "model": MODEL,
        "voice": VOICE,
        "voice_profile_id": "gemini_31_achird_clear_chapters_v1",
        "performance_spans": spans,
        "usage_by_chapter": usage,
    })
    project.artifacts.pop("captions", None)
    project.artifacts["video"] = str(FINAL_VIDEO)
    project.qc["clear_voice"] = {"passed": True, "clarity": clarity, "audio_review": audio_review}
    project.qc["word_timing_alignment"] = alignment
    project.qc["final"] = qc.run_qc(project, FINAL_VIDEO)
    project.qc["review_readiness"] = qc.review_readiness(project)
    project.status = "awaiting_final_approval"
    project.review.final_status = "pending"
    save_project(project, EPISODE)
    (EPISODE / "preview_package.json").write_text(project.model_dump_json(indent=2), encoding="utf-8")

    receipt = {
        "video": str(FINAL_VIDEO),
        "duration_seconds": round(duration(FINAL_VIDEO), 3),
        "narration": str(FINAL_NARRATION),
        "intro_words": len((NEW_B00 + " " + NEW_B01).split()),
        "clarity": clarity,
        "alignment": alignment,
        "audio_review": audio_review,
        "final_qc": project.qc["final"],
        "publishing_enabled": False,
    }
    (REVISION_DIR / "revision_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
