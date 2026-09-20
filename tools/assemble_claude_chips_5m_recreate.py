from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"C:\Youtube Automation for Magic hour")
OUT = ROOT / "output" / "claude_chips_5m_recreate"
CACHE = OUT / "assembly_cache_v6"
SEGMENTS = CACHE / "segments"
SOURCE_EPISODE = ROOT / "output" / "claude_chips_8m_v3" / "claude_tests_computer_chips_8m_v3.mp4"
SOURCE_CACHE = ROOT / "output" / "claude_chips_8m_v3" / "cut_v3_cache"
MOTION_PACK = OUT / "motion_v3_ailabs" / "motion_pack_v6_news_cuts.mp4"
FFMPEG = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\tools\ffmpeg\bin\ffmpeg.exe")
FFPROBE = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\tools\ffmpeg\bin\ffprobe.exe")
FINAL = OUT / "claude_chip_validation_5m_news_cut_script_v3.mp4"
SCRIPT_NEWS = OUT / "script_news_v3.json"
AUDIO_MASTER = OUT / "audio_news_v3" / "narration_news_v3_master.m4a"
SOURCE_ROOT = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour")
RAW_BROLL = {
    "packaging": SOURCE_ROOT / "output" / "claude_chips_8m_v2" / "sources" / "intel_packaging_broll.mp4",
    "event": SOURCE_ROOT / "output" / "claude_chips_8m_v2" / "sources" / "intel_vision_broll.mp4",
}
SOURCE_LEDGER = ROOT / "output" / "claude_chips_8m_v3" / "shot_ledger.json"
CLEAN_BROLL = CACHE / "clean_source_broll"
CLEAN_EVIDENCE = CACHE / "clean_evidence"

# Five coherent chapters from the approved 8-minute narration. The retained
# voice is relaxed to a natural explainer pace and lands at 4:57 plus a
# three-second end hold.
AUDIO_WINDOWS = [
    (0.000, 50.403, "cold_open"),
    (100.797, 150.252, "what_claude_does"),
    (150.252, 202.757, "speed_claim"),
    (255.184, 309.262, "failure_modes"),
    (418.641, 477.000, "verdict"),
]

BROLL_INDEXES = list(range(30)) + [33, 37, 31, 40, 41]
EVIDENCE_INDEXES = list(range(7))


def run(args: list[str], *, cwd: Path | None = None) -> None:
    print("RUN", subprocess.list2cmdline(args), flush=True)
    subprocess.run(args, check=True, cwd=str(cwd) if cwd else None)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def encode_segment(source: Path, output: Path, start: float, duration: float) -> None:
    if output.exists() and output.stat().st_size > 100_000:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{duration:.3f}",
        "-an", "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-threads", "2",
        "-profile:v", "high", "-level:v", "4.1", "-video_track_timescale", "90000",
        str(output),
    ])


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        ROOT / "assets" / "fonts" / "Inter-Bold.ttf",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def build_source_only_overlay(destination: Path) -> Path:
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    label = "SOURCE · INTEL NEWSROOM"
    face = _font(18)
    bounds = draw.textbbox((0, 0), label, font=face)
    width = bounds[2] - bounds[0] + 44
    draw.rounded_rectangle(
        (42, 1004, 42 + width, 1050), radius=18,
        fill=(9, 10, 10, 204), outline=(255, 255, 255, 46), width=1,
    )
    draw.text((64, 1014), label, font=face, fill=(240, 242, 240, 255))
    image.save(destination)
    return destination


def _source_records_by_broll_index() -> dict[int, dict]:
    records = json.loads(SOURCE_LEDGER.read_text(encoding="utf-8"))
    mapped: dict[int, dict] = {}
    for record in records:
        if record.get("category") != "broll":
            continue
        match = re.search(r"broll_(\d{3})_", str(record.get("file", "")))
        if match:
            mapped[int(match.group(1))] = record
    return mapped


def build_clean_broll(index: int, record: dict, overlay: Path) -> Path:
    source_kind = str(record["source"])
    destination = CLEAN_BROLL / f"broll_{index:03d}_{source_kind}.mp4"
    if destination.exists() and destination.stat().st_size > 500_000:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    transform_dir = SOURCE_CACHE / "stabilized_broll"
    transform_name = f"broll_{index:03d}_{source_kind}.trf"
    transform = transform_dir / transform_name
    raw = RAW_BROLL[source_kind]
    for required in (raw, transform):
        if not required.exists():
            raise FileNotFoundError(required)
    normalized = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p"
    graph = (
        f"[0:v]{normalized},vidstabtransform=input={transform_name}:smoothing=24:zoom=0:optzoom=1:interpol=bicubic,"
        "unsharp=5:5:0.18:3:3:0.08[clean];"
        "[clean][1:v]overlay=0:0:format=auto:shortest=1,format=yuv420p[out]"
    )
    run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{float(record['source_start']):.3f}", "-i", str(raw),
        "-loop", "1", "-i", str(overlay), "-t", "8.0", "-filter_complex", graph,
        "-map", "[out]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-g", "60", "-sc_threshold", "0", "-movflags", "+faststart", str(destination),
    ], cwd=transform_dir)
    return destination


def prepare_clean_sources() -> None:
    overlay = build_source_only_overlay(CACHE / "source_intel_newsroom.png")
    records = _source_records_by_broll_index()
    with ThreadPoolExecutor(max_workers=min(4, max(1, os.cpu_count() or 4))) as pool:
        futures = [pool.submit(build_clean_broll, index, records[index], overlay) for index in BROLL_INDEXES]
        for future in as_completed(futures):
            future.result()

    try:
        from tools.assemble_claude_chips_v3 import evidence_specs, render_evidence
    except ModuleNotFoundError:
        # Support both `python -m tools...` and direct script execution.
        from assemble_claude_chips_v3 import evidence_specs, render_evidence
    CLEAN_EVIDENCE.mkdir(parents=True, exist_ok=True)
    specs = evidence_specs()
    for index in EVIDENCE_INDEXES:
        source, crop, label, cue = specs[index]
        render_evidence(source, CLEAN_EVIDENCE / f"evidence_{index:02d}.mp4", crop, label, cue)


def build_audio() -> Path:
    if not AUDIO_MASTER.exists() or AUDIO_MASTER.stat().st_size < 1_000_000:
        raise FileNotFoundError(
            f"Generate the revised narration first: python tools/generate_claude_chips_5m_news_voice.py ({AUDIO_MASTER})"
        )
    return AUDIO_MASTER


def build_shot_plan() -> list[dict]:
    records = _source_records_by_broll_index()
    broll = [
        CLEAN_BROLL / f"broll_{i:03d}_{records[i]['source']}.mp4"
        for i in BROLL_INDEXES
    ]
    evidence = [CLEAN_EVIDENCE / f"evidence_{i:02d}.mp4" for i in EVIDENCE_INDEXES]
    motion_starts = [0.0, 6.0, 12.0, 18.0, 24.0, 30.0, 36.0, 42.0]
    motion = [(MOTION_PACK, start) for start in motion_starts]

    # Editorial rhythm: real footage carries the episode; evidence and motion
    # interrupt it only when the narration needs proof or explanation.
    motion_slots = {2, 8, 14, 20, 27, 34, 40, 47}
    evidence_slots = {5, 11, 17, 24, 31, 38, 44}
    pattern = ["m" if i in motion_slots else "e" if i in evidence_slots else "b" for i in range(50)]
    pools = {"b": iter(broll), "e": iter(evidence), "m": iter(motion)}
    shots: list[dict] = []
    cursor = 0.0
    counters = {"b": 0, "e": 0, "m": 0}
    for kind in pattern:
        duration = 6.0
        item = next(pools[kind])
        if kind == "m":
            source, source_start = item
            label = f"motion_news_cut_{counters[kind]:02d}"
        else:
            source = item
            source_start = 1.0 if kind == "b" else 0.0
            label = f"{'broll' if kind == 'b' else 'evidence'}_{counters[kind]:02d}"
        output = SEGMENTS / f"{len(shots):03d}_{label}.mp4"
        shots.append({
            "order": len(shots), "kind": kind, "label": label,
            "source": str(source), "source_start": source_start,
            "duration": duration, "timeline_start": cursor, "output": str(output),
        })
        counters[kind] += 1
        cursor += duration
    assert abs(cursor - 300.0) < 0.001, cursor
    return shots


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    for required in (FFMPEG, FFPROBE, MOTION_PACK, SCRIPT_NEWS):
        if not required.exists():
            raise FileNotFoundError(required)

    prepare_clean_sources()
    audio = build_audio()
    shots = build_shot_plan()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(
                encode_segment, Path(shot["source"]), Path(shot["output"]),
                float(shot["source_start"]), float(shot["duration"]),
            ) for shot in shots
        ]
        for future in as_completed(futures):
            future.result()

    concat_file = CACHE / "timeline.concat.txt"
    concat_file.write_text("".join(f"file '{Path(s['output']).as_posix()}'\n" for s in shots), encoding="utf-8")
    visuals = CACHE / "visuals_300s.mp4"
    run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file), "-c", "copy", "-t", "300", str(visuals),
    ])
    run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-i", str(visuals), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-ac", "2", "-t", "300",
        "-movflags", "+faststart", str(FINAL),
    ])

    original_rights = ROOT / "output" / "claude_chips_8m_v3" / "rights_ledger.json"
    if original_rights.exists():
        rights = json.loads(original_rights.read_text(encoding="utf-8"))
        for media in rights.get("media", []):
            publisher = str(media.get("publisher") or "SOURCE").upper()
            media["label"] = f"SOURCE · {publisher}"
        (OUT / "rights_ledger.json").write_text(json.dumps(rights, indent=2), encoding="utf-8")
    (OUT / "shot_ledger.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    script_data = json.loads(SCRIPT_NEWS.read_text(encoding="utf-8"))
    script_lines = [f"# {script_data['title']}", "", "Private review draft. Publishing disabled. No captions requested.", ""]
    for section in script_data["sections"]:
        script_lines.extend([
            f"## {section['id'].replace('_', ' ').title()}", "", section["narration"], "",
            f"Evidence: {', '.join(section['evidence'])}", "",
        ])
    (OUT / "script.md").write_text("\n".join(script_lines), encoding="utf-8")
    manifest = {
        "version": "1.3-news-cuts-script-v3", "publishing_enabled": False, "duration_seconds": 300,
        "resolution": "1920x1080", "fps": 30,
        "motion_framework": "original AI-news editorial system + motion-framework primitives + HyperFrames",
        "motion_pack": str(MOTION_PACK), "final": str(FINAL), "sha256": sha256(FINAL),
        "color_system": {
            "neutral_structure": ["#FFFFFF", "#F0F2F0", "#C8CEC9", "#4A4F4B", "#121513"],
            "claude_accent": "#D97757",
            "codex_openai_treatment": "official monochrome mark; no recoloring",
            "optional_chart_palette": "MetBrewer/Egypt",
        },
        "brand_policy": "Company colors are localized to official marks, brand-owned UI, channel-owned avatar containers, and one active emphasis. Editorial avatars are not official mascots.",
        "on_screen_source_policy": "Viewer-facing badges contain only SOURCE · PUBLISHER. Footage type, rights status, and production method remain in the private ledger.",
        "transition_policy": "Hard cuts between scenes; 4-8 frame opacity/translation reveals inside a scene; no 3D rotation or camera transitions.",
        "script": str(SCRIPT_NEWS),
        "narration": str(AUDIO_MASTER),
        "shot_counts": {"rights_recorded_broll": 35, "evidence": 7, "motion": 8},
        "rights_note": "Unlicensed YouTube candidate footage was excluded. The reused media follows the prior episode rights ledger.",
        "license_note": "The motion layouts and animation sequences are original to this project. The external motion framework is used for private evaluation because no repository license was visible at integration time.",
    }
    (OUT / "render_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(FINAL)


if __name__ == "__main__":
    main()
