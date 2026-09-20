from __future__ import annotations

import json
import math
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "remotion" / "public" / "episode" / "claude-chips"
OUT = ROOT / "output" / "claude_chips_8m"
CACHE = OUT / "fast_render_cache"
FFMPEG = ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"
FPS = 30
SHOT_SECONDS = 6
SHOT_COUNT = 80
WIDTH, HEIGHT = 1920, 1080

COLORS = {
    "black": "#080809",
    "board": "#111114",
    "paper": "#F4F0E8",
    "muted": "#B9B2A8",
    "orange": "#D97745",
    "yellow": "#FFD24A",
    "red": "#E84D47",
    "blue": "#5B8CFF",
}


def run(args: list[str]) -> None:
    subprocess.run([str(value) for value in args], check=True)


def duration(path: Path) -> float:
    try:
        result = subprocess.check_output([
            str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(path),
        ], text=True, stderr=subprocess.DEVNULL).strip()
        return float(result)
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def rounded_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, color: str) -> None:
    x, y = xy
    face = font(23, True)
    box = draw.textbbox((0, 0), text, font=face)
    width = box[2] - box[0] + 42
    draw.rounded_rectangle((x, y, x + width, y + 54), radius=27, fill="#080809DD", outline="#FFFFFF44", width=2)
    draw.ellipse((x + 15, y + 18, x + 28, y + 31), fill=color)
    draw.text((x + 35, y + 12), text, font=face, fill=COLORS["paper"])


def source_overlay(text: str, destination: Path) -> None:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    rounded_label(draw, (48, HEIGHT - 92), text, COLORS["orange"])
    image.save(destination)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=face)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_board(chapter: dict, variant: int, destination: Path) -> None:
    base = Image.new("RGB", (WIDTH, HEIGHT), COLORS["black"])
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((1280, -220, 2130, 640), fill="#D9774538")
    glow = glow.filter(ImageFilter.GaussianBlur(95))
    base = Image.alpha_composite(base.convert("RGBA"), glow)
    draw = ImageDraw.Draw(base)

    draw.ellipse((74, 65, 94, 85), fill=COLORS["orange"])
    draw.text((112, 57), "AI MEDIA BRIEF", font=font(24, True), fill=COLORS["paper"])
    draw.text((1540, 59), "CLAUDE × CHIPS", font=font(22, True), fill=COLORS["muted"])
    draw.text((96, 160), chapter["kicker"], font=font(25, True), fill=COLORS["orange"])

    if variant == 0:
        title_face = font(86 if len(chapter["title"]) < 26 else 72, True)
        lines = wrap_text(draw, chapter["title"], title_face, 1150)
        y = 220
        for line in lines:
            draw.text((96, y), line, font=title_face, fill=COLORS["paper"], stroke_width=1)
            y += title_face.size + 10
        draw.rounded_rectangle((96, y + 30, 310, y + 38), radius=4, fill=COLORS["red"])
        cards = ["READ", "TEST", "RUN", "VERIFY"]
        left = 96
        for index, label in enumerate(cards):
            x = left + index * 420
            fill = COLORS["yellow"] if index == 2 else COLORS["board"]
            ink = COLORS["black"] if index == 2 else COLORS["paper"]
            draw.rounded_rectangle((x, 690, x + 350, 910), radius=28, fill=fill, outline="#FFFFFF33", width=2)
            bbox = draw.textbbox((0, 0), label, font=font(43, True))
            draw.text((x + 175 - (bbox[2] - bbox[0]) / 2, 770), label, font=font(43, True), fill=ink)
            if index < 3:
                draw.text((x + 365, 755), "→", font=font(62, True), fill=COLORS["orange"])
    else:
        metric_map = {
            "cold_open": ("CHATBOT", "ENGINEERING TOOL"),
            "validation_101": ("LOOKS RIGHT", "PROVES IT WORKS"),
            "what_claude_does": ("REAL EQUIPMENT", "DIGITAL TWIN"),
            "speed_claim": ("4 DAYS", "48 HOURS"),
            "why_now": ("ONE PROMPT", "A LONG TASK"),
            "failure_modes": ("AI OUTPUT", "HUMAN APPROVAL"),
            "physical_ai": ("NO ROBOT ARMS", "STILL PHYSICAL AI"),
            "who_should_care": ("GENERIC AI", "SPECIFIC WORKFLOW"),
            "verdict": ("SOUNDS SMART", "FEWER SURPRISES"),
        }
        left_text, right_text = metric_map.get(chapter["id"], ("CLAIM", "EVIDENCE"))
        draw.text((96, 210), chapter["title"], font=font(68, True), fill=COLORS["paper"])
        draw.rounded_rectangle((96, 360, 760, 760), radius=34, fill=COLORS["board"], outline="#FFFFFF33", width=2)
        draw.rounded_rectangle((1160, 360, 1824, 760), radius=34, fill=COLORS["yellow"], outline=COLORS["black"], width=3)
        draw.rounded_rectangle((835, 505, 1085, 615), radius=55, fill=COLORS["red"])
        draw.text((911, 508), "→", font=font(70, True), fill=COLORS["black"])
        for text, box, ink in ((left_text, (96, 360, 760, 760), COLORS["paper"]), (right_text, (1160, 360, 1824, 760), COLORS["black"])):
            face = font(55 if len(text) < 15 else 43, True)
            lines = wrap_text(draw, text, face, box[2] - box[0] - 90)
            total = len(lines) * (face.size + 10)
            y = (box[1] + box[3] - total) / 2
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=face)
                x = (box[0] + box[2] - (bbox[2] - bbox[0])) / 2
                draw.text((x, y), line, font=face, fill=ink)
                y += face.size + 10
        draw.text((96, 842), "ATTRIBUTION STAYS ATTACHED", font=font(27, True), fill=COLORS["red"])

    draw.text((96, 1005), "PRIVATE QUALITY CANARY · NO SUBTITLES", font=font(19, True), fill="#FFFFFF66")
    base.convert("RGB").save(destination, quality=96)


def normalize_broll(source: Path, prefix: str, overlay: Path) -> list[Path]:
    directory = CACHE / "broll"
    directory.mkdir(parents=True, exist_ok=True)
    existing = sorted(directory.glob(f"{prefix}_*.mp4"))
    # Only cache complete six-second segments. Comparing against the source
    # duration also prevents a stale encode with a looping overlay from being
    # mistaken for valid source footage.
    expected_complete = math.floor(duration(source) / SHOT_SECONDS)
    valid_existing = [path for path in existing if duration(path) >= 5.85]
    if len(existing) == expected_complete and len(valid_existing) == expected_complete:
        return valid_existing
    for old in existing:
        old.unlink()
    output_pattern = directory / f"{prefix}_%03d.mp4"
    filter_graph = (
        f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},fps={FPS},format=yuv420p[base];"
        "[base][1:v]overlay=0:0:format=auto:shortest=1,format=yuv420p[out]"
    )
    run([
        str(FFMPEG), "-y", "-i", str(source), "-loop", "1", "-i", str(overlay),
        "-filter_complex", filter_graph, "-map", "[out]", "-an", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "18", "-g", str(FPS * 2), "-keyint_min", str(FPS * 2),
        "-sc_threshold", "0", "-force_key_frames", f"expr:gte(t,n_forced*{SHOT_SECONDS})",
        "-shortest", "-f", "segment", "-segment_time", str(SHOT_SECONDS),
        "-reset_timestamps", "1", str(output_pattern),
    ])
    return [path for path in sorted(directory.glob(f"{prefix}_*.mp4")) if duration(path) >= 5.85]


def image_clip(image: Path, destination: Path, direction: int) -> Path:
    if destination.exists() and duration(destination) >= 5.95:
        return destination
    zoom = "min(zoom+0.00022,1.045)"
    x = "iw/2-(iw/zoom/2)" if direction % 2 == 0 else "max(0,(iw-iw/zoom)*(on/180))"
    vf = (
        f"scale=2100:1182:force_original_aspect_ratio=increase,crop=2100:1182,"
        f"zoompan=z='{zoom}':x='{x}':y='ih/2-(ih/zoom/2)':d={SHOT_SECONDS * FPS}:"
        f"s={WIDTH}x{HEIGHT}:fps={FPS},format=yuv420p"
    )
    run([
        str(FFMPEG), "-y", "-loop", "1", "-i", str(image), "-t", str(SHOT_SECONDS),
        "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-g", str(FPS * 2), "-keyint_min", str(FPS * 2), "-sc_threshold", "0", str(destination),
    ])
    return destination


def prepare_image_clips(episode: dict) -> tuple[list[Path], list[Path]]:
    boards_dir = CACHE / "boards"
    clips_dir = CACHE / "image_clips"
    boards_dir.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)
    board_images: list[Path] = []
    for chapter in episode["chapters"]:
        for variant in (0, 1):
            target = boards_dir / f"{chapter['id']}_{variant}.png"
            draw_board(chapter, variant, target)
            board_images.append(target)
    capture_images = [PUBLIC / record["file"] for record in episode.get("captures", []) if record.get("status") == "captured" and (PUBLIC / record.get("file", "")).is_file()]
    tasks: list[tuple[Path, Path, int, str]] = []
    for index, image in enumerate(board_images):
        tasks.append((image, clips_dir / f"board_{index:02d}.mp4", index, "board"))
    for index, image in enumerate(capture_images):
        tasks.append((image, clips_dir / f"capture_{index:02d}.mp4", index, "capture"))
    results: dict[str, list[Path]] = {"board": [], "capture": []}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(image_clip, image, destination, direction): kind for image, destination, direction, kind in tasks}
        for future in as_completed(futures):
            results[futures[future]].append(future.result())
    return sorted(results["board"]), sorted(results["capture"])


def assemble() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    episode = json.loads((PUBLIC / "episode.json").read_text(encoding="utf-8"))
    overlay_packaging = CACHE / "overlay_packaging.png"
    overlay_event = CACHE / "overlay_event.png"
    source_overlay("SOURCE · INTEL NEWSROOM", overlay_packaging)
    source_overlay("SOURCE · INTEL NEWSROOM", overlay_event)

    packaging = normalize_broll(PUBLIC / "intel_packaging_broll.mp4", "packaging", overlay_packaging)
    event = normalize_broll(PUBLIC / "intel_vision_broll.mp4", "event", overlay_event)
    boards, captures = prepare_image_clips(episode)
    if not packaging or not event or not boards:
        raise RuntimeError("Fast render cache did not produce enough normalized media")

    timeline: list[Path] = []
    board_cursor = capture_cursor = packaging_cursor = event_cursor = 0
    for slot in range(SHOT_COUNT):
        pattern = slot % 5
        if slot == 0 or pattern == 1:
            timeline.append(boards[board_cursor % len(boards)])
            board_cursor += 1
        elif pattern == 0:
            timeline.append(packaging[packaging_cursor % len(packaging)])
            packaging_cursor += 1
        elif pattern == 2 and captures:
            timeline.append(captures[capture_cursor % len(captures)])
            capture_cursor += 1
        elif pattern == 3:
            timeline.append(event[event_cursor % len(event)])
            event_cursor += 1
        else:
            timeline.append(boards[board_cursor % len(boards)])
            board_cursor += 1

    concat_file = CACHE / "timeline.concat.txt"
    concat_file.write_text("".join(f"file '{path.resolve().as_posix()}'\n" for path in timeline), encoding="utf-8")
    visuals = CACHE / "visuals_480s.mp4"
    run([
        str(FFMPEG), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy", "-t", "480", str(visuals),
    ])
    final = OUT / "claude_tests_computer_chips_8m.mp4"
    narration = PUBLIC / "narration.wav"
    run([
        str(FFMPEG), "-y", "-i", str(visuals), "-i", str(narration), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", "480",
        "-movflags", "+faststart", str(final),
    ])
    manifest = {
        "output": str(final),
        "duration": duration(final),
        "resolution": "1920x1080",
        "fps": FPS,
        "shots": SHOT_COUNT,
        "median_visual_duration_seconds": SHOT_SECONDS,
        "subtitles": False,
        "official_broll_segments": {"packaging": len(packaging), "event": len(event)},
        "capture_clips": len(captures),
        "graphic_clips": len(boards),
        "assembly": "normalized cached segments + concat stream copy",
    }
    (OUT / "render_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return final


if __name__ == "__main__":
    assemble()
