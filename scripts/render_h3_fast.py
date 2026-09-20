"""Fast, deterministic 1080p assembly for the MiniMax H3 review episode."""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

from pipeline.config import LOCAL_FFMPEG_BIN, PROJECT_ROOT
from pipeline.thumbnail import _font


RUN_DIR = PROJECT_ROOT / "output" / "minimax_h3_10m"
PUBLIC_DIR = PROJECT_ROOT / "remotion" / "public"
EPISODE_PATH = PUBLIC_DIR / "episode" / "h3-10m" / "episode.json"
NARRATION = PUBLIC_DIR / "episode" / "h3-10m" / "narration.wav"
SEGMENT_DIR = RUN_DIR / "fast_segments"
CARD_DIR = RUN_DIR / "fast_cards"
OVERLAY_DIR = RUN_DIR / "fast_overlays"
MOTION_PACK_MANIFEST = RUN_DIR / "motion_pack" / "manifest.json"
STYLE_PROFILE_PATH = PROJECT_ROOT / "configs" / "visual_style_profiles" / "ai-news-editorial-v4.json"
OUTPUT = RUN_DIR / "minimax_h3_10m_review.mp4"
FFMPEG = str(LOCAL_FFMPEG_BIN / "ffmpeg.exe")
FFPROBE = str(LOCAL_FFMPEG_BIN / "ffprobe.exe")
WIDTH, HEIGHT, FPS = 1920, 1080, 30
SHOT_SECONDS = 5
SHOT_COUNT = 120
CHAPTER_BEATS = {0, 6, 10, 16, 20, 26}
STYLE_PROFILE = json.loads(STYLE_PROFILE_PATH.read_text(encoding="utf-8"))


def run(command: list[str]) -> None:
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode:
        tail = "\n".join(process.stderr.splitlines()[-24:])
        raise RuntimeError(f"command failed: {' '.join(command[:10])}\n{tail}")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:14]


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        box = draw.textbbox((0, 0), candidate, font=font)
        if current and box[2] - box[0] > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def overlay_for(beat: dict, label: str) -> Path:
    key = digest({"v": 4, "id": beat["id"], "overlay": beat["overlay"], "accent": beat["accent"], "label": label})
    destination = OVERLAY_DIR / f"{key}.png"
    if destination.is_file():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    title_font = _font(42)
    accent_font = _font(18)
    badge_font = _font(15)
    title_lines = wrap(draw, beat["overlay"], title_font, 760)[:2]
    title_height = len(title_lines) * 49
    box_height = 34 + title_height + 42
    x, y, box_width = 76, HEIGHT - 64 - box_height, 860
    draw.rounded_rectangle((x, y, x + box_width, y + box_height), radius=12, fill=(7, 8, 8, 214), outline=(70, 72, 72, 190), width=1)
    draw.rectangle((x, y, x + 4, y + box_height), fill=(215, 123, 89, 255))
    cursor_y = y + 18
    for line in title_lines:
        draw.text((x + 24, cursor_y), line, font=title_font, fill=(242, 241, 237, 255))
        cursor_y += 49
    accent = beat["accent"]
    draw.text((x + 24, y + box_height - 31), accent, font=accent_font, fill=(154, 158, 156, 255))
    badge_text = f"SOURCE · {label.upper()}"
    badge_box = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_width = badge_box[2] - badge_box[0] + 26
    bx, by = WIDTH - badge_width - 48, 38
    draw.rounded_rectangle((bx, by, bx + badge_width, by + 34), radius=7, fill=(0, 0, 0, 202), outline=(255, 255, 255, 55), width=1)
    draw.text((bx + 13, by + 8), badge_text, font=badge_font, fill=(242, 241, 237, 255))
    image.save(destination)
    return destination


def full_card(beat: dict, kind: str, index: int) -> Path:
    key = digest({"v": 3, "beat": beat["id"], "kind": kind, "index": index})
    destination = CARD_DIR / f"{key}.png"
    if destination.is_file():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (WIDTH, HEIGHT), "#050505")
    draw = ImageDraw.Draw(image)
    small = _font(20)
    title_font = _font(90 if kind == "chapter" else 78)
    item_font = _font(35)
    kicker = f"CHAPTER {index + 1:02d}" if kind == "chapter" else "MINIMAX H3 · EVIDENCE CHECK"
    draw.text((126, 112), kicker, font=small, fill="#8E9B95")
    lines = wrap(draw, beat["overlay"], title_font, 1560)[:3]
    y = 165
    for line in lines:
        draw.text((126, y), line, font=title_font, fill="#f7f5ef")
        y += 94
    draw.rounded_rectangle((126, y + 28, 292, y + 34), radius=3, fill="#ef4a52")
    if kind != "chapter":
        facts = {
            "hardware": ["123.6 GB", "66% LESS", "42.5 GB"],
            "workflow": ["PREVIEW LOW", "LOCK REFERENCES", "FINISH HIGH"],
            "creator_test": ["ONE SUBJECT", "ONE MOVE", "ONE SOUND CUE"],
            "decision": ["CONTROL", "PRIVACY", "SPEED"],
            "sample_limits": ["VISIBLE RESULT", "PICKED DEMOS", "UNKNOWN FAILURE RATE"],
            "resolution": ["SMALL DRAFT", "SECOND PASS", "2K OUTPUT"],
            "not_fully_local": ["LOCAL WEIGHTS", "HOSTED PLANNER", "HOSTED 2K"],
        }.get(beat["purpose"], ["WHAT SHIPPED", "WHAT WORKS", "WHAT REMAINS"])
        top = 660
        gap = 24
        card_width = (WIDTH - 252 - gap * 2) // 3
        for item_index, item in enumerate(facts):
            left = 126 + item_index * (card_width + gap)
            fill = "#15110a" if item_index == 1 else "#101010"
            stroke = "#ef4a52" if item_index == 1 else "#343434"
            draw.rounded_rectangle((left, top, left + card_width, top + 250), radius=10, fill=fill, outline=stroke, width=3)
            item_lines = wrap(draw, item, item_font, card_width - 48)[:3]
            item_y = top + 150
            for item_line in item_lines:
                draw.text((left + 24, item_y), item_line, font=item_font, fill="#f7f5ef")
                item_y += 42
    draw.text((126, HEIGHT - 70), beat["accent"], font=small, fill="#b8b8b8")
    image.save(destination, quality=95)
    return destination


def media_path(value: str) -> Path:
    return PUBLIC_DIR / value


def media_duration(path: Path) -> float:
    process = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(process.stdout.strip())


def encode_segment(source: Path, overlay: Path | None, destination: Path, offset: float = 0.0) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    image_source = source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    command = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    if image_source:
        command.extend(["-loop", "1", "-i", str(source)])
        base = (
            f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={WIDTH}:{HEIGHT},fps={FPS},setsar=1,format=yuv420p[base]"
        )
    else:
        command.extend(["-stream_loop", "-1", "-ss", f"{offset:.3f}", "-i", str(source)])
        base = (
            f"[0:v]setpts=PTS-STARTPTS,scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={WIDTH}:{HEIGHT},fps={FPS},format=yuv420p[base]"
        )
    if overlay:
        command.extend(["-loop", "1", "-i", str(overlay)])
        graph = (
            base
            + ";[1:v]format=rgba,fade=t=in:st=0.24:d=0.28:alpha=1,"
            + "fade=t=out:st=4.58:d=0.24:alpha=1[overlay];"
            + "[base][overlay]overlay=x='-18+18*min(t/0.42,1)':y=0:format=auto,format=yuv420p[out]"
        )
    else:
        graph = base + ";[base]null[out]"
    command.extend([
        "-filter_complex", graph, "-map", "[out]", "-an", "-t", str(SHOT_SECONDS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-threads", "2",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(destination),
    ])
    run(command)
    return destination


def main() -> None:
    episode = json.loads(EPISODE_PATH.read_text(encoding="utf-8"))
    beats = episode["beats"]
    beat_starts = [float(beat["startMs"]) / 1000 for beat in beats]
    motion_clips: dict[str, Path] = {}
    if MOTION_PACK_MANIFEST.is_file():
        motion_manifest = json.loads(MOTION_PACK_MANIFEST.read_text(encoding="utf-8"))
        motion_clips = {purpose: Path(path) for purpose, path in motion_manifest.get("clips", {}).items()}

    def active_beat(second: float) -> tuple[int, dict]:
        index = 0
        for candidate, start in enumerate(beat_starts):
            if start <= second:
                index = candidate
            else:
                break
        return index, beats[index]

    usage: defaultdict[str, int] = defaultdict(int)
    last_source: Path | None = None
    plans: list[dict] = []
    for index in range(SHOT_COUNT):
        start = index * SHOT_SECONDS
        beat_index, beat = active_beat(start + SHOT_SECONDS / 2)
        near_beat_start = 0 <= start - beat_starts[beat_index] < SHOT_SECONDS
        chapter = beat_index in CHAPTER_BEATS and near_beat_start
        evidence = index % 5 == 4
        if chapter or evidence:
            source = motion_clips.get(beat["purpose"])
            if source is None or not source.is_file():
                source = full_card(beat, "chapter" if chapter else "evidence", beat_index)
            overlay = None
            label = "editorial motion"
        else:
            choices: list[tuple[Path, str]] = []
            for asset_id in beat.get("broll", []):
                relative = episode["broll"].get(asset_id)
                if relative:
                    choices.append((media_path(relative), "Official MiniMax H3 sample"))
            for source_id in beat.get("source_ids", []):
                relative = episode["assets"].get(source_id, {}).get("viewport")
                if relative:
                    publisher = episode["sources"].get(source_id, {}).get("publisher", "Primary source")
                    choices.append((media_path(relative), publisher))
            if not choices:
                source = full_card(beat, "evidence", beat_index)
                overlay = None
                label = "editorial card"
            else:
                ranked = sorted(
                    choices,
                    key=lambda choice: (
                        choice[0] == last_source,
                        usage[str(choice[0])],
                        digest({"index": index, "path": str(choice[0])}),
                    ),
                )
                source, label = ranked[0]
                overlay = overlay_for(beat, label) if index % 3 != 0 else None
        usage[str(source)] += 1
        last_source = source
        plans.append({
            "index": index,
            "beat": beat,
            "source": source,
            "overlay": overlay,
            "label": label,
        })

    def render_one(plan: dict) -> Path:
        index = int(plan["index"])
        beat = plan["beat"]
        source = Path(plan["source"])
        overlay = plan["overlay"]
        label = plan["label"]
        payload = {
            "v": 6, "profile": STYLE_PROFILE["version"], "index": index, "beat": beat["id"],
            "source": str(source), "source_mtime": source.stat().st_mtime_ns,
            "overlay": str(overlay), "label": label,
        }
        destination = SEGMENT_DIR / f"{index:03d}_{digest(payload)}.mp4"
        if destination.is_file() and destination.stat().st_size > 100_000:
            return destination
        offset = 0.0
        if source.suffix.lower() == ".mp4":
            duration = media_duration(source)
            offset = max(0.0, min(duration - SHOT_SECONDS, ((index * 1.7) % max(SHOT_SECONDS, duration)) / 2))
        return encode_segment(source, overlay, destination, offset)

    SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as executor:
        segments = list(executor.map(render_one, plans))
    listing = RUN_DIR / "fast_segments.ffconcat"
    listing.write_text(
        "ffconcat version 1.0\n" + "".join(f"file '{segment.resolve().as_posix()}'\n" for segment in segments),
        encoding="utf-8",
    )
    silent = RUN_DIR / "minimax_h3_10m_silent.mp4"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(silent)])
    run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(silent), "-i", str(NARRATION),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", "600", "-movflags", "+faststart", str(OUTPUT),
    ])
    receipt = {
        "output": str(OUTPUT), "duration_seconds": 600, "resolution": "1920x1080", "fps": FPS,
        "segments": len(segments), "shot_seconds": SHOT_SECONDS, "publishing_enabled": False,
        "visual_style_profile": STYLE_PROFILE["version"],
        "camera_policy": STYLE_PROFILE["cameraPolicy"],
        "motion_pack_used": bool(motion_clips),
    }
    (RUN_DIR / "fast_render_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
