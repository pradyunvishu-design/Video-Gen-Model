from __future__ import annotations

"""Freeze every article shot at its already-settled evidence position."""

from collections import Counter
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import build_news_weekly_20260822_video as episode

OUT = ROOT / "output" / "news_weekly_20260822"
SOURCE_MANIFEST = OUT / "semantic_v5" / "render_manifest.json"
WORK = OUT / "static_articles_v6"
FRAMES = WORK / "article_frames"
SEGMENTS = WORK / "segments"
NARRATION = OUT / "audio" / "narration_master.m4a"
CAPTIONS = OUT / "captions_monochrome.ass"
FINAL = OUT / "the_week_in_ai_2026-08-22_10min_static_articles_v6.mp4"
FFMPEG, FFPROBE = episode.FFMPEG, episode.FFPROBE


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def freeze_article(slot: int, source: Path) -> Path:
    frame = FRAMES / f"{slot:03d}.png"
    destination = SEGMENTS / f"{slot:03d}_article_static.mp4"
    if destination.exists() and destination.stat().st_size > 60_000:
        return destination
    FRAMES.mkdir(parents=True, exist_ok=True)
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    # Source sequences finish their deterministic positioning before 2.2s.
    # Sampling at 3s produces the landed evidence view without a visible search.
    subprocess.run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-ss", "3",
        "-i", str(source), "-frames:v", "1", "-vf", "scale=1920:1080", str(frame),
    ], check=True)
    subprocess.run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(frame),
        "-t", "6", "-an", "-r", "30", "-vf", "format=yuv420p", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "18", "-g", "60", str(destination),
    ], check=True)
    return destination


def main() -> None:
    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    ledger = [dict(item) for item in source_manifest["shot_ledger"]]
    article_records = [item for item in ledger if item["kind"] == "article_source"]
    replacements: dict[int, Path] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(freeze_article, int(item["slot"]), Path(item["file"])): int(item["slot"])
            for item in article_records
        }
        for future in as_completed(futures):
            replacements[futures[future]] = future.result()

    timeline = []
    for item in ledger:
        slot = int(item["slot"])
        if slot in replacements:
            original = item["file"]
            item.update({
                "file": str(replacements[slot]), "source": str(replacements[slot]),
                "original_article_sequence": original,
                "article_presentation": "static_prepositioned_evidence",
                "visible_scroll": False,
            })
        path = Path(item["file"])
        if not path.exists() or path.stat().st_size < 60_000:
            raise FileNotFoundError(path)
        timeline.append(path.resolve())

    concat = WORK / "timeline.concat.txt"
    concat.write_text("".join(f"file '{path.as_posix()}'\n" for path in timeline), encoding="utf-8")
    visuals = WORK / "visuals_600s.mp4"
    subprocess.run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat), "-c", "copy", "-t", "600", str(visuals),
    ], check=True)
    ass_path = str(CAPTIONS.resolve()).replace("\\", "/").replace(":", "\\:")
    subprocess.run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-i", str(visuals), "-i", str(NARRATION),
        "-vf", f"ass='{ass_path}'", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-ac", "2", "-t", "600", "-movflags", "+faststart", str(FINAL),
    ], check=True)

    broll_counts = Counter(
        item.get("source_url", "") for item in ledger
        if item["kind"] in {"reviewed_broll", "reputable_youtube_broll"}
    )
    if "" in broll_counts or max(broll_counts.values(), default=0) > 2:
        raise RuntimeError("B-roll repetition gate regressed during article revision")
    manifest = {
        "final": str(FINAL), "sha256": sha256(FINAL), "duration_seconds": 600,
        "resolution": "1920x1080", "fps": 30, "publishing_enabled": False,
        "static_article_shots": len(article_records), "visible_article_scrolls": 0,
        "visual_mix": dict(Counter(item["kind"] for item in ledger)),
        "maximum_broll_source_uses": max(broll_counts.values(), default=0),
        "shot_ledger": ledger,
    }
    (WORK / "render_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "shot_ledger"}, indent=2))


if __name__ == "__main__":
    main()
