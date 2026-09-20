"""Reassemble the five-minute Claude chip episode with the v8 source-depth pack.

The existing licensed source segments and approved narration remain unchanged.
Only the eight six-second motion inserts are re-encoded from the new pack.
Publishing remains disabled in the generated manifest.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import reassemble_claude_chips_semantic_v7 as base


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "output" / "claude_chips_5m_recreate"
CACHE = RUN / "assembly_cache_v6"
MOTION = RUN / "motion_v3_ailabs" / "motion_pack_v8_source_depth.mp4"
OUT_DIR = RUN / "assembly_cache_v8_source_depth"
FINAL = RUN / "claude_chip_validation_5m_source_depth_v8.mp4"
LOCAL_FFMPEG_BIN = ROOT / "tools" / "ffmpeg" / "bin"
HERMES_FFMPEG_BIN = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\tools\ffmpeg\bin")
FFMPEG_BIN = LOCAL_FFMPEG_BIN if (LOCAL_FFMPEG_BIN / "ffmpeg.exe").is_file() else HERMES_FFMPEG_BIN
FFMPEG = FFMPEG_BIN / "ffmpeg.exe"
FFPROBE = FFMPEG_BIN / "ffprobe.exe"


def run(command: list[str | Path]) -> None:
    subprocess.run([str(item) for item in command], check=True)


def main() -> None:
    if not FFMPEG.exists() or not FFPROBE.exists():
        raise FileNotFoundError("Bundled FFmpeg tools are missing")
    if not MOTION.exists():
        raise FileNotFoundError(f"Motion pack is missing: {MOTION}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ledger = json.loads((RUN / "shot_ledger.json").read_text(encoding="utf-8"))
    broll = {Path(item["source"]).stem: Path(item["output"]) for item in ledger if item["kind"] == "b"}
    evidence = {int(item["label"].split("_")[-1]): Path(item["output"]) for item in ledger if item["kind"] == "e"}

    motion_segments: dict[int, Path] = {}
    for scene_index in sorted({int(identifier) for kind, identifier, _ in base.TIMELINE if kind == "m"}):
        destination = OUT_DIR / f"motion_{scene_index:02d}.mp4"
        motion_segments[scene_index] = destination
        if destination.exists():
            continue
        run([
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(scene_index * 6), "-i", MOTION, "-t", "6",
            "-an", "-vf", "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-g", "60",
            "-video_track_timescale", "90000", destination,
        ])

    selected: list[Path] = []
    manifest: list[dict] = []
    last_seen: dict[str, int] = {}
    uses: dict[str, int] = {}
    for slot, (kind, identifier, target) in enumerate(base.TIMELINE):
        if kind == "b":
            path = broll[str(identifier)]
            source_url = base.PACKAGING_URL if str(identifier).endswith("packaging") else base.EVENT_URL
            source_id = "E6"
            key = str(identifier)
        elif kind == "e":
            path = evidence[int(identifier)]
            source_url = base.ANTHROPIC_URL
            source_id = ["E1", "E2", "E2", "E3", "E1", "E7", "E2"][int(identifier)]
            key = f"evidence_{int(identifier):02d}"
        else:
            path = motion_segments[int(identifier)]
            source_url = base.ANTHROPIC_URL
            source_id = "derived_editorial_graphic"
            key = f"motion_{int(identifier):02d}"

        uses[key] = uses.get(key, 0) + 1
        if uses[key] > 2:
            raise RuntimeError(f"asset reuse exceeds two: {key}")
        if key in last_seen and slot - last_seen[key] <= 3:
            raise RuntimeError(f"asset repeats inside three-shot cooldown: {key}")
        last_seen[key] = slot
        selected.append(path)
        manifest.append({
            "slot": slot,
            "timeline_start": slot * 6,
            "duration": 6,
            "kind": kind,
            "asset": str(path),
            "reuse_key": key,
            "use_number": uses[key],
            "semantic_target": target,
            "source_id": source_id,
            "source_url": source_url,
            "source_audio_muted": True,
        })

    concat_file = OUT_DIR / "timeline.concat.txt"
    concat_file.write_text(
        "".join(f"file '{path.as_posix()}'\n" for path in selected),
        encoding="utf-8",
    )
    silent = OUT_DIR / "visuals_300s.mp4"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", silent])
    run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", silent,
        "-i", CACHE / "narration_300s_v2.m4a", "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", FINAL,
    ])

    manifest_path = RUN / "semantic_timeline_v8.json"
    manifest_path.write_text(
        json.dumps({
            "version": "3.0-source-depth-v8",
            "final": str(FINAL),
            "motion_pack": str(MOTION),
            "palette": {
                "ink": "#141817",
                "forest": "#1B2622",
                "paper": "#F2EEE5",
                "sage": "#93A69B",
                "claude_dark": "#E07A57",
                "claude_paper": "#A74730",
            },
            "policy": {
                "max_asset_uses": 2,
                "cooldown_shots": 3,
                "publishing_enabled": False,
                "third_party_audio_muted": True,
            },
            "shots": manifest,
        }, indent=2),
        encoding="utf-8",
    )
    probe = subprocess.check_output([
        str(FFPROBE), "-v", "error",
        "-show_entries", "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json", str(FINAL),
    ], text=True)
    print(probe)


if __name__ == "__main__":
    main()
