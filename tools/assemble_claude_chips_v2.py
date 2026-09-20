from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "remotion" / "public" / "episode" / "claude-chips-v2"
OUT = ROOT / "output" / "claude_chips_8m_v2"
OLD_OUT = ROOT / "output" / "claude_chips_8m"
CACHE = OUT / "cut_v2_cache"
FFMPEG = ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"
FPS = 30
SHOT_SECONDS = 5
SHOT_COUNT = 96
WIDTH, HEIGHT = 1920, 1080

INK = "#F6F2EB"
BLACK = "#070709"
PANEL = "#141419"
ORANGE = "#D97745"
YELLOW = "#FFD34E"
RED = "#E34B46"
BLUE = "#6D8DFF"

MOTION_CONCEPTS = [
    {"id": "design_to_test", "eyebrow": "THE WORKFLOW", "left": "DESIGN FILES", "right": "TEST PLAN", "accent": ORANGE},
    {"id": "test_loop", "eyebrow": "THE VALIDATION LOOP", "left": "READ · TEST", "right": "RUN · COMPARE", "accent": BLUE},
    {"id": "speed_claim", "eyebrow": "UST-REPORTED RESULT", "left": "4 DAYS", "right": "48 HOURS", "accent": YELLOW},
    {"id": "digital_twin", "eyebrow": "ONE SYSTEM, TWO SIGNALS", "left": "REAL EQUIPMENT", "right": "DIGITAL TWIN", "accent": BLUE},
    {"id": "agent_chain", "eyebrow": "AN AGENT KEEPS CONTEXT", "left": "GOAL + FILES", "right": "RESULT + RETRY", "accent": ORANGE},
    {"id": "approval_gate", "eyebrow": "THE SAFETY BOUNDARY", "left": "AI DRAFT", "right": "HUMAN APPROVAL", "accent": RED},
    {"id": "audit_trail", "eyebrow": "WHAT MAKES IT USEFUL", "left": "FAST OUTPUT", "right": "EVIDENCE + LOGS", "accent": YELLOW},
]


def run(args: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run([str(value) for value in args], cwd=str(cwd) if cwd else None, check=True)


def duration(path: Path) -> float:
    result = subprocess.check_output([
        str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], text=True).strip()
    return float(result)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def ease_out_quint(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1.0 - (1.0 - value) ** 5


def ease_in_out(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def base_background() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
    pixels = image.load()
    orange = (217, 119, 69)
    blue = (69, 87, 160)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            d1 = math.hypot(x - 1650, y - 130) / 1050
            d2 = math.hypot(x - 180, y - 940) / 1150
            a1 = max(0.0, 1.0 - d1) * 0.18
            a2 = max(0.0, 1.0 - d2) * 0.13
            pixels[x, y] = (
                int(7 + orange[0] * a1 + blue[0] * a2),
                int(7 + orange[1] * a1 + blue[1] * a2),
                int(9 + orange[2] * a1 + blue[2] * a2),
            )
    return image


def label_overlay(text: str, destination: Path) -> None:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    face = font(22, True)
    box = draw.textbbox((0, 0), text, font=face)
    width = box[2] - box[0] + 70
    draw.rounded_rectangle((38, HEIGHT - 86, 38 + width, HEIGHT - 30), radius=28, fill="#08080AE8", outline="#FFFFFF35", width=2)
    draw.ellipse((58, HEIGHT - 65, 72, HEIGHT - 51), fill=ORANGE)
    draw.text((84, HEIGHT - 72), text, font=face, fill=INK)
    image.save(destination)


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int = 74) -> ImageFont.FreeTypeFont:
    size = start
    while size > 36:
        face = font(size, True)
        if draw.textbbox((0, 0), text, font=face)[2] <= max_width:
            return face
        size -= 2
    return font(36, True)


def render_motion_clip(concept: dict, destination: Path, background: Image.Image) -> Path:
    if destination.exists() and duration(destination) >= 4.95:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(FFMPEG), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}",
        "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(destination),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    for frame_index in range(SHOT_SECONDS * FPS):
        t = frame_index / FPS
        image = background.copy()
        draw = ImageDraw.Draw(image)
        eyebrow_p = ease_out_quint((t - 0.08) / 0.55)
        cards_p = ease_out_quint((t - 0.42) / 0.8)
        line_p = ease_in_out((t - 1.12) / 0.7)
        pulse = ease_in_out((t - 2.05) / 0.65) * (1.0 - ease_in_out((t - 3.35) / 0.65))
        draw.ellipse((88, 70, 106, 88), fill=concept["accent"])
        draw.text((126, 60 + int((1 - eyebrow_p) * 20)), concept["eyebrow"], font=font(26, True), fill=INK)
        left_x = int(94 - (1 - cards_p) * 130)
        right_x = int(1046 + (1 - cards_p) * 130)
        y0, y1 = 292, 784
        for x, text_value, active in ((left_x, concept["left"], False), (right_x, concept["right"], True)):
            fill = concept["accent"] if active else PANEL
            ink = BLACK if active and concept["accent"] == YELLOW else INK
            draw.rounded_rectangle((x, y0, x + 780, y1), radius=46, fill=fill, outline="#FFFFFF3D", width=2)
            face = _fit_text(draw, text_value, 650)
            box = draw.textbbox((0, 0), text_value, font=face)
            draw.text((x + 390 - (box[2] - box[0]) / 2, 512 - (box[3] - box[1]) / 2), text_value, font=face, fill=ink)
        line_start, line_end = 875, 1041
        current_end = int(line_start + (line_end - line_start) * line_p)
        draw.line((line_start, 538, current_end, 538), fill=concept["accent"], width=10)
        if line_p > 0.84:
            draw.polygon([(1037, 520), (1070, 538), (1037, 556)], fill=concept["accent"])
        if pulse > 0:
            radius = int(26 + 24 * pulse)
            glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.ellipse((1436 - radius, 220 - radius, 1436 + radius, 220 + radius), fill=concept["accent"] + "75")
            image = Image.alpha_composite(image.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(22))).convert("RGB")
        draw = ImageDraw.Draw(image)
        draw.text((94, 938), "SOURCE-FIRST EXPLAINER · PRIVATE REVIEW CUT", font=font(20, True), fill="#FFFFFF6A")
        process.stdin.write(image.tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"motion render failed: {destination.name}")
    return destination


def frame_hash(source: Path, at: float) -> int:
    raw = subprocess.check_output([
        str(FFMPEG), "-v", "error", "-ss", f"{at:.3f}", "-i", str(source),
        "-frames:v", "1", "-vf", "scale=17:9", "-pix_fmt", "gray", "-f", "rawvideo", "-",
    ])
    if len(raw) < 153:
        return 0
    bits = 0
    bit_index = 0
    for row in range(9):
        offset = row * 17
        for column in range(16):
            if raw[offset + column] > raw[offset + column + 1]:
                bits |= 1 << bit_index
            bit_index += 1
    return bits


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def choose_broll(source_records: list[dict], wanted: int) -> list[dict]:
    candidates: list[dict] = []
    per_source = math.ceil(wanted / len(source_records)) + 10
    for source in source_records:
        total = duration(source["path"])
        spacing = max(6.2, (total - 12.0) / per_source)
        for index in range(per_source):
            start = min(total - SHOT_SECONDS - 0.5, 4.0 + index * spacing)
            candidates.append({**source, "start": round(start, 3), "hash": frame_hash(source["path"], start + 2.4)})
    selected: list[dict] = []
    by_source = {record["id"]: [item for item in candidates if item["id"] == record["id"]] for record in source_records}
    cursors = Counter()
    while len(selected) < wanted:
        progressed = False
        for source in source_records:
            pool = by_source[source["id"]]
            while cursors[source["id"]] < len(pool):
                item = pool[cursors[source["id"]]]
                cursors[source["id"]] += 1
                if item["hash"] and all(hamming(item["hash"], prior["hash"]) >= 10 for prior in selected):
                    selected.append(item)
                    progressed = True
                    break
            if len(selected) >= wanted:
                break
        if not progressed:
            break
    if len(selected) < wanted:
        unused = [item for item in candidates if item not in selected]
        selected.extend(unused[: wanted - len(selected)])
    if len(selected) < wanted:
        raise RuntimeError(f"only {len(selected)} distinct b-roll ranges available; need {wanted}")
    return selected[:wanted]


def stabilize_clip(record: dict, destination: Path, overlay: Path) -> Path:
    if destination.exists() and duration(destination) >= 4.95:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    transform = destination.with_suffix(".trf")
    normalized = f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},fps={FPS},format=yuv420p"
    run([
        str(FFMPEG), "-y", "-ss", f"{record['start']:.3f}", "-i", str(record["path"]),
        "-t", str(SHOT_SECONDS), "-vf",
        f"{normalized},vidstabdetect=shakiness=7:accuracy=12:stepsize=6:mincontrast=0.22:result={transform.name}",
        "-an", "-f", "null", "NUL",
    ], cwd=destination.parent)
    filter_graph = (
        f"[0:v]{normalized},vidstabtransform=input={transform.name}:smoothing=12:zoom=1:optzoom=1:interpol=bicubic,"
        "unsharp=5:5:0.25:3:3:0.10[base];[base][1:v]overlay=0:0:format=auto:shortest=1,format=yuv420p[out]"
    )
    run([
        str(FFMPEG), "-y", "-ss", f"{record['start']:.3f}", "-i", str(record["path"]),
        "-loop", "1", "-i", str(overlay), "-t", str(SHOT_SECONDS),
        "-filter_complex", filter_graph, "-map", "[out]", "-an", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "18", "-g", str(FPS * 2), "-keyint_min", str(FPS * 2),
        "-sc_threshold", "0", "-movflags", "+faststart", str(destination),
    ], cwd=destination.parent)
    return destination


def render_evidence_clip(source: Path, destination: Path, crop: tuple[int, int, int, int], underline: tuple[int, int, int], label: str) -> Path:
    if destination.exists() and duration(destination) >= 4.95:
        return destination
    original = Image.open(source).convert("RGB")
    cropped = original.crop(crop).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    command = [
        str(FFMPEG), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}",
        "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(destination),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    for frame_index in range(SHOT_SECONDS * FPS):
        t = frame_index / FPS
        image = cropped.copy()
        shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shade)
        sd.rectangle((0, HEIGHT - 150, WIDTH, HEIGHT), fill="#0000008A")
        image = Image.alpha_composite(image.convert("RGBA"), shade).convert("RGB")
        draw = ImageDraw.Draw(image)
        progress = ease_out_quint((t - 0.65) / 0.85)
        x0, x1, y = underline
        draw.line((x0, y, int(x0 + (x1 - x0) * progress), y), fill=RED, width=8)
        draw.rounded_rectangle((42, HEIGHT - 92, 662, HEIGHT - 34), radius=28, fill="#08080AE8", outline="#FFFFFF35", width=2)
        draw.ellipse((64, HEIGHT - 71, 78, HEIGHT - 57), fill=RED)
        draw.text((92, HEIGHT - 78), label, font=font(22, True), fill=INK)
        process.stdin.write(image.tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"evidence render failed: {destination.name}")
    return destination


def prepare_evidence() -> list[dict]:
    directory = CACHE / "evidence"
    directory.mkdir(parents=True, exist_ok=True)
    captures = OUT / "captures"
    specs = [
        ("anthropic_story.png", (0, 0, 1920, 1080), (500, 1425, 235), "SOURCE · ANTHROPIC CASE STUDY"),
        ("anthropic_story.png", (250, 65, 1660, 860), (330, 1580, 215), "SOURCE · ANTHROPIC CASE STUDY"),
        ("anthropic_speed_claim.png", (0, 0, 1920, 1080), (635, 1280, 781), "SOURCE · ANTHROPIC / UST"),
        ("anthropic_speed_claim.png", (500, 125, 1375, 1010), (300, 1560, 775), "SOURCE · UST-REPORTED CLAIM"),
        ("intel_presskit.png", (0, 0, 1920, 1080), (585, 1240, 184), "SOURCE · INTEL NEWSROOM"),
        ("intel_presskit.png", (490, 110, 1435, 905), (295, 1575, 890), "SOURCE · INTEL PRESS KIT"),
    ]
    records: list[dict] = []
    for index, (filename, crop, underline, label) in enumerate(specs):
        source = captures / filename
        if not source.exists():
            raise FileNotFoundError(f"approved evidence capture missing: {source}")
        target = directory / f"evidence_{index:02d}.mp4"
        render_evidence_clip(source, target, crop, underline, label)
        records.append({"path": target, "asset_id": f"evidence:{filename}:{index % 2}", "source": filename, "category": "evidence"})
    return records


def copy_inputs() -> list[dict]:
    source_dir = OUT / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    capture_dir = OUT / "captures"
    capture_dir.mkdir(parents=True, exist_ok=True)
    media = [
        ("intel_packaging_broll.mp4", "packaging", "SOURCE · INTEL NEWSROOM", "https://newsroom.intel.com/press-kit/global-manufacturing"),
        ("intel_vision_broll.mp4", "event", "SOURCE · INTEL NEWSROOM", "https://newsroom.intel.com/press-kit/intel-vision-2024"),
    ]
    records: list[dict] = []
    for filename, source_id, label, url in media:
        target = source_dir / filename
        if not target.exists():
            shutil.copy2(OLD_OUT / "sources" / filename, target)
        shutil.copy2(target, PUBLIC / filename)
        records.append({"id": source_id, "path": target, "label": label, "url": url})
    for filename in ("anthropic_story.png", "anthropic_speed_claim.png", "intel_presskit.png"):
        target = capture_dir / filename
        if not target.exists():
            shutil.copy2(OLD_OUT / "captures" / filename, target)
        shutil.copy2(target, PUBLIC / filename)
    return records


def build_timeline(broll: list[dict], evidence: list[dict], motion: list[dict]) -> list[dict]:
    motion_slots = {0, 7, 14, 21, 28, 35, 42, 49, 56, 63, 70, 77, 84, 91}
    evidence_slots = {10, 25, 40, 55, 72, 88}
    timeline: list[dict] = []
    bi = ei = mi = 0
    for slot in range(SHOT_COUNT):
        if slot in motion_slots:
            item = motion[mi]
            mi += 1
        elif slot in evidence_slots:
            item = evidence[ei]
            ei += 1
        else:
            item = broll[bi]
            bi += 1
        timeline.append({**item, "slot": slot, "timeline_start": slot * SHOT_SECONDS})
    return timeline


def assemble() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    source_records = copy_inputs()
    background = base_background()
    motion_dir = CACHE / "motion"
    motion: list[dict] = []
    for repeat in range(2):
        for index, concept in enumerate(MOTION_CONCEPTS):
            target = motion_dir / f"motion_{index:02d}.mp4"
            render_motion_clip(concept, target, background)
            motion.append({"path": target, "asset_id": f"motion:{concept['id']}", "category": "motion", "concept": concept["id"], "repeat": repeat + 1})
    evidence = prepare_evidence()
    selected = choose_broll(source_records, wanted=SHOT_COUNT - len(motion) - len(evidence))
    overlays: dict[str, Path] = {}
    for source in source_records:
        overlay = CACHE / f"overlay_{source['id']}.png"
        label_overlay(source["label"], overlay)
        overlays[source["id"]] = overlay
    stabilized_dir = CACHE / "stabilized_broll"
    stabilized: list[dict | None] = [None] * len(selected)
    with ThreadPoolExecutor(max_workers=min(6, max(1, os.cpu_count() or 4))) as pool:
        futures = {}
        for index, record in enumerate(selected):
            destination = stabilized_dir / f"broll_{index:03d}_{record['id']}.mp4"
            futures[pool.submit(stabilize_clip, record, destination, overlays[record["id"]])] = (index, record)
        for future in as_completed(futures):
            index, record = futures[future]
            path = future.result()
            stabilized[index] = {
                "path": path,
                "asset_id": f"broll:{record['id']}:{record['start']:.3f}",
                "category": "broll", "source": record["id"], "source_start": record["start"],
                "source_url": record["url"], "stabilized": True,
                "perceptual_hash": f"{record['hash']:036x}",
            }
    broll = [item for item in stabilized if item is not None]
    timeline = build_timeline(broll, evidence, motion)
    usage = Counter(item["asset_id"] for item in timeline)
    if max(usage.values()) > 2:
        raise RuntimeError(f"visual reuse cap violated: {usage.most_common(3)}")
    categories = Counter(item["category"] for item in timeline)
    if categories != Counter({"broll": 76, "motion": 14, "evidence": 6}):
        raise RuntimeError(f"unexpected visual mix: {categories}")
    concat_file = CACHE / "timeline.concat.txt"
    concat_file.write_text("".join(f"file '{Path(item['path']).resolve().as_posix()}'\n" for item in timeline), encoding="utf-8")
    visuals = CACHE / "visuals_480s.mp4"
    run([str(FFMPEG), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", "-t", "480", "-movflags", "+faststart", str(visuals)])
    visual_seconds = duration(visuals)
    if visual_seconds < 479.95:
        # Some 29.97 fps source ranges normalize to 149 frames. Fill the small
        # aggregate shortfall with a second use of one already-approved b-roll
        # asset rather than freezing the final frame or adding another graphic.
        filler = next(item for item in reversed(timeline) if item["category"] == "broll")
        filled_concat = CACHE / "timeline_filled.concat.txt"
        filled_concat.write_text(
            f"file '{visuals.resolve().as_posix()}'\nfile '{Path(filler['path']).resolve().as_posix()}'\n",
            encoding="utf-8",
        )
        filled_visuals = CACHE / "visuals_exact_480s.mp4"
        run([
            str(FFMPEG), "-y", "-f", "concat", "-safe", "0", "-i", str(filled_concat),
            "-c", "copy", "-t", "480", "-movflags", "+faststart", str(filled_visuals),
        ])
        timeline.append({
            **filler,
            "slot": len(timeline),
            "timeline_start": round(visual_seconds, 3),
            "effective_duration": round(480.0 - visual_seconds, 3),
            "end_fill": True,
        })
        visuals = filled_visuals
        usage = Counter(item["asset_id"] for item in timeline)
        categories = Counter(item["category"] for item in timeline)
    narration = PUBLIC / "narration.wav"
    if not narration.exists():
        raise FileNotFoundError("v2 narration is missing; run build_claude_chips_episode_v2.py first")
    final = OUT / "claude_tests_computer_chips_8m_v2.mp4"
    run([
        str(FFMPEG), "-y", "-i", str(visuals), "-i", str(narration), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", "480", "-movflags", "+faststart", str(final),
    ])
    ledger = []
    for item in timeline:
        clean = {key: value for key, value in item.items() if key != "path"}
        clean["file"] = str(Path(item["path"]).relative_to(OUT)) if OUT in Path(item["path"]).parents else str(item["path"])
        clean["usage_count"] = usage[item["asset_id"]]
        ledger.append(clean)
    manifest = {
        "output": str(final), "duration": duration(final), "resolution": "1920x1080", "fps": FPS,
        "shot_count": len(timeline), "median_visual_duration_seconds": SHOT_SECONDS,
        "visual_mix": dict(categories), "broll_percentage": round(categories["broll"] / len(timeline) * 100, 1),
        "max_asset_reuse": max(usage.values()),
        "stabilization": "two-pass vidstab, 12-frame smoothing, bicubic transform, 1% optical zoom",
        "motion_design": "seven deterministic Hyperframes-style relationship graphics; each used twice",
        "subtitles": False, "publishing": "disabled",
    }
    (OUT / "shot_ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    (OUT / "render_manifest_v2.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return final


if __name__ == "__main__":
    assemble()
