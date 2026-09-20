from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.editorial_style import draw_source_credit
from scripts import build_news_weekly_20260822_video as episode

OUT = ROOT / "output" / "news_weekly_20260822"
WORK = OUT / "balanced_v4"
SEGMENTS = WORK / "segments"
OVERLAYS = WORK / "overlays"
MOTION_MANIFEST = OUT / "custom_motion_v3" / "motion_manifest.json"
OPEN_MANIFEST = OUT / "open_broll" / "approved_open_broll_manifest.json"
NARRATION = OUT / "audio" / "narration_master.m4a"
CAPTIONS = OUT / "captions_monochrome.ass"
FINAL = OUT / "the_week_in_ai_2026-08-22_10min_balanced_v4.mp4"
FFMPEG, FFPROBE = episode.FFMPEG, episode.FFPROBE

KEEP_MOTION = {0, 12, 17, 32, 36, 44, 56, 62, 74, 82}
BROLL_PLAN = {
    1: (3, 45), 2: (22, 96), 7: (40, 65),
    43: (39, 145), 45: (42, 115), 47: (40, 85), 48: (39, 165),
    49: (42, 135), 50: (40, 105), 52: (39, 185), 55: (42, 155),
    59: (53, 36), 60: (23, 60), 61: (53, 48), 63: (22, 108),
}
ARTICLE_PLAN = {
    10: ("Anthropic", "anthropic_mythos_defense*full.png"),
    15: ("Anthropic", "anthropic_mythos_defense*recording-01.mp4"),
    16: ("Anthropic", "anthropic_mythos_defense*full.png"),
    20: ("Anthropic", "anthropic_mythos_defense*viewport.png"),
    28: ("Anthropic", "anthropic_computer_use*full.png"),
    29: ("Anthropic", "anthropic_computer_use*recording-01.mp4"),
    31: ("Anthropic", "anthropic_computer_use*full.png"),
    35: ("Anthropic", "anthropic_computer_use*viewport.png"),
    37: ("Anthropic", "anthropic_computer_use*full.png"),
    41: ("Anthropic", "anthropic_computer_use*recording-01.mp4"),
    90: ("Hugging Face", "hf_open_models_report*full.png"),
    91: ("Hugging Face", "hf_open_models_report*viewport.png"),
    92: ("Hugging Face", "hf_open_models_report*full.png"),
    93: ("Hugging Face", "hf_open_models_report*full.png"),
    94: ("Hugging Face", "hf_open_models_report*viewport.png"),
    95: ("Anthropic", "anthropic_mythos_defense*full.png"),
    96: ("Anthropic", "anthropic_computer_use*full.png"),
    97: ("NVIDIA", "nvidia_ports_pike*full.png"),
    98: ("Hugging Face", "hf_open_models_report*full.png"),
    99: ("Anthropic", "anthropic_computer_use*recording-01.mp4"),
}
assert len(KEEP_MOTION) == 10 and len(BROLL_PLAN) == 15 and len(ARTICLE_PLAN) == 20
assert not (KEEP_MOTION & BROLL_PLAN.keys() or KEEP_MOTION & ARTICLE_PLAN.keys() or BROLL_PLAN.keys() & ARTICLE_PLAN.keys())


def duration(path: Path) -> float:
    return float(subprocess.check_output([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                                          "-of", "default=nw=1:nk=1", str(path)], text=True).strip())


def source_overlay(slot: int, publisher: str) -> Path:
    destination = OVERLAYS / f"{slot:03d}_{publisher.lower().replace(' ', '_')}_neutral_v2.png"
    if destination.exists():
        return destination
    OVERLAYS.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    draw_source_credit(
        draw, publisher, label_font=episode.font(13, True),
        publisher_font=episode.font(18, True), x=42, y=996,
    )
    image.save(destination)
    return destination


def open_records() -> dict[int, dict]:
    payload = json.loads(OPEN_MANIFEST.read_text(encoding="utf-8"))
    return {int(item["slot"]): item for item in payload["clips"]}


def render_broll(target: int, donor: dict, start: float) -> Path:
    destination = SEGMENTS / f"{target:03d}_broll.mp4"
    if destination.exists() and destination.stat().st_size > 80_000:
        return destination
    source = Path(donor["media_file"])
    start = min(float(start), max(0.0, duration(source) - 6.1))
    overlay = source_overlay(target, donor.get("publisher", "Source"))
    graph = (
        "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,unsharp=3:3:0.25,fps=30,format=rgba[base];"
        "[1:v]format=rgba,fade=t=in:st=0.35:d=0.25:alpha=1,fade=t=out:st=5.55:d=0.25:alpha=1[ol];"
        "[base][ol]overlay=0:0:shortest=1,format=yuv420p[v]"
    )
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start), "-stream_loop", "-1", "-i", str(source),
                    "-loop", "1", "-i", str(overlay), "-filter_complex", graph, "-map", "[v]", "-t", "6", "-an", "-r", "30",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-g", "60", str(destination)], check=True)
    return destination


def render_article(target: int, publisher: str, source: Path, ordinal: int) -> Path:
    destination = SEGMENTS / f"{target:03d}_article.mp4"
    if destination.exists() and destination.stat().st_size > 70_000:
        return destination
    overlay = source_overlay(target, publisher)
    if source.suffix.lower() == ".mp4":
        inputs = ["-stream_loop", "-1", "-i", str(source)]
        base = "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=rgba[base]"
    else:
        with Image.open(source) as image:
            sw, sh = image.size
        scaled_h = max(1080, round(sh * 1920 / sw))
        max_y = max(0, scaled_h - 1080)
        start_y = int(max_y * ((ordinal % 8) / 9))
        end_y = min(max_y, start_y + min(460, max_y // 4))
        inputs = ["-loop", "1", "-i", str(source)]
        base = (f"[0:v]scale=1920:{scaled_h},crop=1920:1080:0:'{start_y}+({end_y-start_y})*min(t/1.6,1)',"
                "fps=30,format=rgba[base]") if max_y else (
                "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=rgba[base]")
    graph = base + ";[1:v]format=rgba,fade=t=in:st=0.35:d=0.25:alpha=1[ol];[base][ol]overlay=0:0:shortest=1,format=yuv420p[v]"
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", *inputs, "-loop", "1", "-i", str(overlay),
                    "-filter_complex", graph, "-map", "[v]", "-t", "6", "-an", "-r", "30", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-g", "60", str(destination)], check=True)
    return destination


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    records = open_records()
    source_root = OUT / "sources"
    jobs = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for target, (donor_slot, start) in BROLL_PLAN.items():
            jobs[pool.submit(render_broll, target, records[donor_slot], start)] = (target, "reviewed_broll")
        for ordinal, (target, (publisher, pattern)) in enumerate(ARTICLE_PLAN.items()):
            source = next(iter(sorted(source_root.glob(pattern))), None)
            if source is None:
                raise FileNotFoundError(pattern)
            jobs[pool.submit(render_article, target, publisher, source, ordinal)] = (target, "article_source")
        replacements = {}
        for future in as_completed(jobs):
            slot, kind = jobs[future]
            replacements[slot] = (future.result(), kind)

    base_ledger = json.loads((OUT / "shot_ledger.json").read_text(encoding="utf-8"))
    motion = {int(slot): Path(path) for slot, path in json.loads(MOTION_MANIFEST.read_text(encoding="utf-8"))["slots"].items()}
    timeline, ledger = [], []
    for record in base_ledger:
        slot = int(record["slot"])
        revised = dict(record)
        if slot in KEEP_MOTION:
            path, kind = motion[slot], "custom_explainer_motion"
        elif slot in replacements:
            path, kind = replacements[slot]
        else:
            path, kind = Path(record["file"]), record["kind"]
        if not path.exists() or path.stat().st_size < 60_000:
            raise FileNotFoundError(path)
        timeline.append(path.resolve())
        revised.update({"file": str(path), "source": str(path), "kind": kind})
        ledger.append(revised)

    concat = WORK / "timeline.concat.txt"
    concat.write_text("".join(f"file '{path.as_posix()}'\n" for path in timeline), encoding="utf-8")
    visuals = WORK / "visuals_600s.mp4"
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-c", "copy", "-t", "600", str(visuals)], check=True)
    ass_path = str(CAPTIONS.resolve()).replace("\\", "/").replace(":", "\\:")
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-i", str(visuals), "-i", str(NARRATION),
                    "-vf", f"ass='{ass_path}'", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-t", "600", "-movflags", "+faststart", str(FINAL)], check=True)
    mix = {kind: sum(item["kind"] == kind for item in ledger) for kind in {item["kind"] for item in ledger}}
    manifest = {"final": str(FINAL), "sha256": sha256(FINAL), "duration_seconds": 600, "resolution": "1920x1080", "fps": 30,
                "publishing_enabled": False, "one_use_motion_slots": sorted(KEEP_MOTION), "visual_mix": mix, "shot_ledger": ledger}
    (WORK / "render_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "shot_ledger"}, indent=2))


if __name__ == "__main__":
    main()
