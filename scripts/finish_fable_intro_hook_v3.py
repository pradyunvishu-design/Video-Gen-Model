"""Finish the Fable/Mythos review cut with a short hook and roadmap intro.

Only the opening is regenerated. The approved body visuals and narration are
reused from the clean no-music master, then the selected music bed is mixed
under one continuous narrator track. Publishing remains disabled.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.gemini_tts import GeminiTTSClient


EPISODE = ROOT / "data/episodes/episode_20260902_fable_mythos_v8_explained"
WORK = EPISODE / "revisions/intro_hook_v5"
SOURCE = EPISODE / "Claude_Fable_Mythos_Explained_1080p_no_music_1487390023.mp4"
NARRATION_SOURCE = EPISODE / "narration_zubenelgenubi.wav"
ANTHROPIC_OPEN = EPISODE / "revisions/anthropic_intro_2s_fast.mp4"
MUSIC_SOURCE = Path(
    r"C:\Users\kanag\Downloads\YTDown.com_YouTube_songs-to-retire-your-parents-to-playlist_Media_G5FmN1B7-TU_001_1080p.mp4"
)
ENV_FILE = Path(
    r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker"
)
FINAL = EPISODE / "Claude_Fable_Mythos_Explained_1080p_publish_review_intro_v5.mp4"

HOOK = (
    "Anthropic just gave one Claude model two rulebooks: Fable for general access, "
    "Mythos for restricted research. Here's what changed in the benchmarks, the science demos, and the price."
)

DIRECTOR = """Read only the transcript below. Never read these notes aloud.

Use the same original Zubenelgenubi male American technology-host voice as the rest of this episode. Sound like a well-informed person in his twenties explaining one surprising detail to a friend. Start immediately and conversationally. Keep the pace near 172 to 178 words per minute. Underplay the delivery: no radio voice, trailer drama, sales energy, sing-song phrasing, breathy endings, forced bass, exaggerated smiles, or artificial pauses. Connect clauses naturally, emphasize only the contrast between one model and two rulebooks, and finish every sentence cleanly. One speaker only. Clear English. No music, effects, static, or background voices.

TRANSCRIPT:
"""


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print(" ".join(command[:8]), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def probe_duration(path: Path, stream: str | None = None) -> float:
    selector = ["-select_streams", stream] if stream else []
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            *selector,
            "-show_entries",
            "stream=duration" if stream else "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    values = [line.strip() for line in result.stdout.splitlines() if line.strip() and line.strip() != "N/A"]
    return float(values[0])


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def make_voice() -> tuple[Path, float, dict]:
    WORK.mkdir(parents=True, exist_ok=True)
    raw = WORK / "hook_raw.wav"
    master = WORK / "hook_master.wav"
    key = str(dotenv_values(ENV_FILE).get("GEMINI_API_KEY") or "")
    client = GeminiTTSClient(
        key,
        model="gemini-3.1-flash-tts-preview",
        voice="Zubenelgenubi",
        timeout_seconds=240,
    )
    result = client.synthesize(HOOK, raw, director_prompt=DIRECTOR, retries=2)
    if not master.exists():
        run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
                "-af", "highpass=f=65,loudnorm=I=-17:TP=-1.5:LRA=5",
                "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(master),
            ]
        )
    seconds = probe_duration(master)
    receipt = {
        "script": HOOK,
        "voice": "Zubenelgenubi",
        "model": "gemini-3.1-flash-tts-preview",
        "duration_seconds": seconds,
        "usage": result.usage,
        "prompt_hash": result.prompt_hash,
    }
    write_json(WORK / "hook_voice_receipt.json", receipt)
    return master, seconds, receipt


def render_roadmap(seconds: float) -> Path:
    # Keep the roadmap itself brief. The hook's last beat plays over source
    # evidence so the opening does not feel like a held presentation slide.
    roadmap_seconds = max(3.0, min(6.25, seconds - 2.0))
    props = {
        "kind": "intro-roadmap",
        "title": "Same model. Different rules.",
        "subtitle": "",
        "labels": [],
        "values": [],
        "images": [],
        "logo": "fable-mythos/Claude Spark - Clay.png",
        "source": "Anthropic launch and Claude Platform docs · September 2026",
        "seconds": roadmap_seconds,
        "dark": True,
    }
    source_hash = hashlib.sha256((ROOT / "remotion/src/fable-mythos-entry.tsx").read_bytes()).hexdigest()
    render_hash = hashlib.sha256((source_hash + json.dumps(props, sort_keys=True)).encode()).hexdigest()[:16]
    props_path = WORK / f"roadmap_{render_hash}.props.json"
    frames = WORK / f"roadmap_frames_{render_hash}"
    movie = WORK / f"roadmap_{render_hash}.mp4"
    write_json(props_path, props)
    expected = round(roadmap_seconds * 30)
    frames.mkdir(parents=True, exist_ok=True)
    if len(list(frames.glob("*.png"))) != expected:
        remotion = ROOT / "remotion/node_modules/.bin/remotion.cmd"
        run(
            [
                str(remotion), "render", "src/fable-mythos-entry.tsx", "FableMythosGraphic", str(frames.resolve()),
                f"--props={props_path.resolve()}",
                r"--browser-executable=C:\Program Files\Google\Chrome\Application\chrome.exe",
                "--sequence", "--image-format=png", "--concurrency=3", "--muted",
            ],
            cwd=ROOT / "remotion",
        )
    pictures = sorted(frames.glob("*.png"))
    if len(pictures) != expected:
        raise RuntimeError(f"Roadmap frame count mismatch: {len(pictures)} != {expected}")
    listing = frames / "sequence.txt"
    listing.write_text(
        "".join(f"file '{picture.resolve().as_posix()}'\nduration 0.033333333333\n" for picture in pictures),
        encoding="utf-8",
    )
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
            "-an", "-r", "30", "-t", f"{roadmap_seconds:.6f}", "-c:v", "libx264", "-preset", "fast", "-crf", "17",
            "-pix_fmt", "yuv420p", str(movie),
        ]
    )
    return movie


def assemble(hook_voice: Path, hook_seconds: float, roadmap: Path) -> None:
    timing = json.loads((EPISODE / "paragraph_timing.json").read_text(encoding="utf-8"))
    body_start = float(next(row["start"] for row in timing if row["id"] == "access_0"))
    narration_unpadded = WORK / "narration_hook_plus_body_unpadded.wav"
    narration = WORK / "narration_hook_plus_body.wav"
    exact_open = WORK / "anthropic_exact_2s.mp4"
    teaser_video = WORK / "evidence_teaser.mp4"
    body_video = WORK / "body_video_copy.mp4"
    packet_visual = WORK / "visual_hook_plus_body_v3.mp4"
    visual = WORK / "visual_hook_plus_body_cfr.mp4"
    music_stem = WORK / "music_instrumental_side.wav"

    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(hook_voice), "-i", str(NARRATION_SOURCE),
            "-filter_complex",
            f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono[a0];"
            f"[1:a]atrim=start={body_start:.6f},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono[a1];"
            "[a0][a1]concat=n=2:v=0:a=1[out]",
            "-map", "[out]", "-c:a", "pcm_s16le", str(narration_unpadded),
        ]
    )
    roadmap_seconds = probe_duration(roadmap)
    teaser_seconds = max(0.0, hook_seconds - 2.0 - roadmap_seconds)
    expected_intro = 2.0 + roadmap_seconds + teaser_seconds
    if abs(expected_intro - hook_seconds) > 0.08:
        raise RuntimeError(f"Intro picture/audio mismatch: {expected_intro:.3f}s vs {hook_seconds:.3f}s")

    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(ANTHROPIC_OPEN), "-t", "2",
        "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-r", "30",
        "-video_track_timescale", "15360", "-pix_fmt", "yuv420p", str(exact_open),
    ])
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{body_start:.6f}", "-i", str(SOURCE),
        "-map", "0:v:0", "-an", "-c", "copy", str(body_video),
    ])
    if teaser_seconds > 0.04:
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{body_start-teaser_seconds:.6f}", "-i", str(SOURCE), "-t", f"{teaser_seconds:.6f}",
            "-map", "0:v:0", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-r", "30", "-video_track_timescale", "15360", "-pix_fmt", "yuv420p", str(teaser_video),
        ])
    concat_list = WORK / "visual_concat_v3.txt"
    visual_parts = [exact_open, roadmap]
    if teaser_seconds > 0.04:
        visual_parts.append(teaser_video)
    visual_parts.append(body_video)
    concat_list.write_text(
        "".join(f"file '{path.resolve().as_posix()}'\n" for path in visual_parts),
        encoding="utf-8",
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", "-movflags", "+faststart", str(packet_visual),
    ])
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-fflags", "+genpts", "-i", str(packet_visual),
        "-vf", "fps=30,format=yuv420p", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-fps_mode", "cfr", "-video_track_timescale", "15360", "-movflags", "+faststart", str(visual),
    ])
    visual_seconds = probe_duration(visual)
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(narration_unpadded),
        "-af", f"apad,atrim=duration={visual_seconds:.6f}", "-ar", "48000", "-ac", "1",
        "-c:a", "pcm_s16le", str(narration),
    ])
    narration_seconds = probe_duration(narration)

    if not music_stem.exists():
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(MUSIC_SOURCE),
            "-t", f"{narration_seconds:.6f}", "-vn",
            "-af", "pan=mono|c0=0.5*c0-0.5*c1,highpass=f=45,lowpass=f=12000,loudnorm=I=-24:TP=-3:LRA=8",
            "-ar", "48000", "-c:a", "pcm_s16le", str(music_stem),
        ])

    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(visual), "-i", str(narration), "-i", str(music_stem),
            "-filter_complex",
            f"[1:a]aresample=48000,highpass=f=65,loudnorm=I=-16:TP=-1.5:LRA=5,asplit=2[nsc][nmix];"
            f"[2:a]aresample=48000,highpass=f=45,lowpass=f=12000,volume=0.22,atrim=duration={narration_seconds:.6f},"
            f"afade=t=in:st=0:d=1.0,afade=t=out:st={max(0.0, narration_seconds-2.0):.6f}:d=2.0[m];"
            "[m][nsc]sidechaincompress=threshold=0.045:ratio=7:attack=18:release=480:makeup=1[ducked];"
            "[nmix][ducked]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.92[outa]",
            "-map", "0:v:0", "-map", "[outa]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(FINAL),
        ]
    )

    report = {
        "status": "review_required",
        "publishing_enabled": False,
        "source_master": str(SOURCE),
        "body_start_seconds": body_start,
        "new_intro_seconds": hook_seconds,
        "roadmap_screen_seconds": roadmap_seconds,
        "evidence_teaser_seconds": teaser_seconds,
        "removed_intro_seconds": body_start,
        "visual_seconds": probe_duration(FINAL, "v:0"),
        "audio_seconds": probe_duration(FINAL, "a:0"),
        "format_seconds": probe_duration(FINAL),
        "resolution": "1920x1080",
        "fps": 30,
        "subtitles": False,
        "voice": "Zubenelgenubi",
        "music_source": str(MUSIC_SOURCE),
        "music_gain": 0.22,
        "music_pre_normalized_lufs": -24,
        "music_center_channel_removed": True,
        "music_speech_qc": "local Whisper detected zero words in the full instrumental stem",
        "source_clip_audio_included": False,
        "intro_structure": [
            "0.00-2.00 official Anthropic launch bumper",
            "rapid three-beat roadmap capped at 6.25 seconds",
            "last hook beat plays over relevant source evidence before the body",
            "approved body resumes at access explanation",
        ],
    }
    report["duration_delta_seconds"] = abs(report["visual_seconds"] - report["audio_seconds"])
    write_json(WORK / "assembly_receipt.json", report)
    if report["duration_delta_seconds"] > 0.30:
        raise RuntimeError(f"Final A/V duration mismatch: {report['duration_delta_seconds']:.3f}s")
    print(json.dumps(report, indent=2), flush=True)
    print(FINAL, flush=True)


def main() -> None:
    for required in (SOURCE, NARRATION_SOURCE, ANTHROPIC_OPEN, MUSIC_SOURCE, ENV_FILE):
        if not required.exists():
            raise FileNotFoundError(required)
    voice, seconds, _ = make_voice()
    roadmap = render_roadmap(seconds)
    assemble(voice, seconds, roadmap)


if __name__ == "__main__":
    main()
