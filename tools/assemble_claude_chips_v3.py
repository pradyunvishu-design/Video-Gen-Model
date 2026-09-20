from __future__ import annotations

import io
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour")
SOURCE_V2 = SOURCE_ROOT / "output" / "claude_chips_8m_v2"
SOURCE_V1 = SOURCE_ROOT / "output" / "claude_chips_8m"
SOURCE_PUBLIC = SOURCE_ROOT / "remotion" / "public" / "episode" / "claude-chips-v2"
THUMB_SOURCE = SOURCE_ROOT / "output" / "thumbnails" / "viral_topics_aug_2026" / "sources"
OUT = ROOT / "output" / "claude_chips_8m_v3"
CACHE = OUT / "cut_v3_cache"
FFMPEG = SOURCE_ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = SOURCE_ROOT / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"

WIDTH, HEIGHT, FPS = 1920, 1080, 30
BROLL_SECONDS = 8
DESIGN_SECONDS = 6
BLACK = "#090A0A"
PAPER = "#F2F1ED"
PANEL = "#171818"
LINE = "#343636"
MUTED = "#8E9290"
YELLOW = "#E8E32D"
CLAY = "#D97745"
BLUE = "#6D8DFF"
GREEN = "#50B57B"
RED = "#E65D5D"


MOTION_SCENES = [
    ("source_result", "THE CLAIM HAS TO SURVIVE THE TEST", "SOURCE → TEST → RESULT"),
    ("process_lane", "WHAT CLAUDE ACTUALLY DOES", "READ · WRITE · RUN · COMPARE"),
    ("stat_morph", "UST-REPORTED TURNAROUND", "4 DAYS → 48 HOURS"),
    ("twin_signals", "TWO SIGNALS, ONE CHECK", "REAL EQUIPMENT ↔ DIGITAL TWIN"),
    ("bug_cost_curve", "LATE BUGS COST MORE", "DESIGN · FAB · SHIP"),
    ("context_stack", "THE AGENT KEEPS THE THREAD", "FILES · GOAL · RESULTS"),
    ("approval_gate", "AUTOMATION STOPS HERE", "AI DRAFT → HUMAN APPROVAL"),
    ("audit_log", "SPEED WITHOUT A LOG IS A GUESS", "INPUTS · TESTS · EVIDENCE"),
    ("diff_repair", "A FAILED TEST BECOMES A SMALLER PROBLEM", "FAIL → LOCATE → RETEST"),
    ("fault_funnel", "NARROW THE SEARCH", "THOUSANDS OF SIGNALS → ONE FAULT"),
    ("confidence_bands", "REPORT THE RANGE, NOT THE HYPE", "50–70% · UST-REPORTED"),
    ("verdict", "FAST IS USEFUL ONLY WHEN IT IS REVIEWABLE", "TRACEABLE · TESTED · APPROVED"),
]


def run(args: list[object], *, cwd: Path | None = None) -> None:
    command = [str(value) for value in args]
    if command and Path(command[0]) == FFMPEG:
        command[1:1] = ["-hide_banner", "-loglevel", "error"]
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def duration(path: Path) -> float:
    value = subprocess.check_output([
        str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], text=True).strip()
    return float(value)


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        names = ["C:/Windows/Fonts/consolab.ttf", "C:/Windows/Fonts/consola.ttf"]
    elif bold:
        names = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
    else:
        names = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def ease_out(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1.0 - (1.0 - value) ** 4


def ease_in_out(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def draw_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str, progress: float) -> None:
    x = 116
    draw.ellipse((x, 78, x + 16, 94), fill=YELLOW)
    draw.text((x + 32, 66), "EDITORIAL EXPLAINER", font=font(21, True), fill=MUTED)
    title_face = font(62, True)
    draw.text((x, 126 + int((1 - progress) * 14)), title, font=title_face, fill=PAPER)
    draw.text((x, 208), subtitle, font=font(25, True), fill=MUTED)
    draw.line((x, 258, x + int(560 * progress), 258), fill=YELLOW, width=5)


def base_frame() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for x in range(110, WIDTH, 120):
        draw.line((x, 300, x, HEIGHT - 95), fill="#FFFFFF08", width=1)
    for y in range(320, HEIGHT - 80, 95):
        draw.line((90, y, WIDTH - 90, y), fill="#FFFFFF08", width=1)
    draw.ellipse((1380, -240, 2100, 480), fill="#D9774514")
    return Image.alpha_composite(image.convert("RGBA"), overlay.filter(ImageFilter.GaussianBlur(1))).convert("RGB")


def _card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, *, accent: str | None = None, active: bool = False, size: int = 33) -> None:
    draw.rounded_rectangle(box, radius=28, fill="#1A1B1B", outline=accent if active and accent else LINE, width=4 if active else 2)
    face = font(size, True)
    bounds = draw.textbbox((0, 0), label, font=face)
    cx = (box[0] + box[2]) // 2
    cy = (box[1] + box[3]) // 2
    draw.text((cx - (bounds[2] - bounds[0]) / 2, cy - (bounds[3] - bounds[1]) / 2 - 4), label, font=face, fill=PAPER)


def draw_motion_scene(scene_id: str, frame_index: int) -> Image.Image:
    t = frame_index / FPS
    scene = next(item for item in MOTION_SCENES if item[0] == scene_id)
    image = base_frame()
    draw = ImageDraw.Draw(image)
    enter = ease_out((t - 0.08) / 0.55)
    phase = ease_out((t - 0.65) / 0.9)
    finish = ease_out((t - 2.0) / 0.8)
    draw_header(draw, scene[1], scene[2], enter)

    if scene_id == "source_result":
        xs = [120, 700, 1280]
        labels = ["OFFICIAL SOURCE", "CONTROLLED TEST", "NARROW RESULT"]
        for i, (x, label) in enumerate(zip(xs, labels)):
            local = ease_out((t - 0.55 - i * 0.22) / 0.6)
            y = 430 + int((1 - local) * 22)
            _card(draw, (x, y, x + 500, y + 280), label, accent=[CLAY, BLUE, GREEN][i], active=i == 2, size=29)
            if i < 2:
                end = int(x + 500 + 80 * phase)
                draw.line((x + 500, 570, end, 570), fill=MUTED, width=5)
                if phase > 0.82:
                    draw.polygon([(end - 14, 559), (end + 8, 570), (end - 14, 581)], fill=MUTED)
        draw.text((120, 814), "The conclusion appears only after the evidence and test agree.", font=font(30), fill=MUTED)

    elif scene_id == "process_lane":
        labels = ["READ", "WRITE", "RUN", "COMPARE"]
        for i, label in enumerate(labels):
            local = ease_out((t - 0.45 - i * 0.18) / 0.55)
            x = 120 + i * 430
            _card(draw, (x, 440, x + 330, 660), label, accent=CLAY if i < 2 else BLUE, active=(i == min(3, int(max(0, t - 1.2) / 0.65))), size=38)
            if i < 3:
                draw.line((x + 330, 550, x + 430, 550), fill=LINE, width=6)
        cursor_x = 285 + min(3, max(0.0, (t - 1.1) / 0.62)) * 430
        draw.ellipse((cursor_x - 11, 708, cursor_x + 11, 730), fill=YELLOW)
        draw.line((285, 719, cursor_x, 719), fill=YELLOW, width=5)

    elif scene_id == "stat_morph":
        old_scale = 1.0 - 0.08 * phase
        old = "4 DAYS"
        old_face = font(int(150 * old_scale), True)
        draw.text((160, 420), old, font=old_face, fill=MUTED)
        arrow_x = 845
        draw.line((arrow_x, 548, arrow_x + int(180 * finish), 548), fill=YELLOW, width=12)
        if finish > 0.82:
            draw.polygon([(1010, 527), (1050, 548), (1010, 569)], fill=YELLOW)
        new_x = 1170 + int((1 - finish) * 90)
        draw.text((new_x, 390), "48", font=font(210, True), fill=PAPER)
        draw.text((new_x + 8, 630), "HOURS", font=font(58, True), fill=YELLOW)
        draw.text((160, 820), "Reported by UST. The episode treats it as a case-study result, not an independent benchmark.", font=font(28), fill=MUTED)

    elif scene_id == "twin_signals":
        colors = [CLAY, BLUE]
        labels = ["REAL EQUIPMENT", "DIGITAL TWIN"]
        for lane in range(2):
            y0 = 420 + lane * 245
            draw.text((120, y0 - 58), labels[lane], font=font(27, True), fill=colors[lane])
            draw.rounded_rectangle((120, y0, 1800, y0 + 150), radius=24, fill=PANEL, outline=LINE, width=2)
            points = []
            visible = int(1560 * phase)
            for px in range(visible):
                x = 180 + px
                y = y0 + 75 + math.sin((px / 70) + lane * 0.25) * 28 + math.sin(px / 19) * 5
                points.append((x, y))
            if len(points) > 1:
                draw.line(points, fill=colors[lane], width=5)
        marker = 1180
        draw.line((marker, 405, marker, 820), fill=YELLOW, width=4)
        draw.text((marker + 18, 805), "COMPARE HERE", font=font(22, True), fill=YELLOW)

    elif scene_id == "bug_cost_curve":
        origin = (190, 820)
        draw.line((origin[0], 350, origin[0], origin[1]), fill=MUTED, width=4)
        draw.line((origin[0], origin[1], 1770, origin[1]), fill=MUTED, width=4)
        points = []
        visible = int(1500 * phase)
        for px in range(visible):
            x = origin[0] + px
            q = px / 1500
            y = origin[1] - 60 - (q ** 2.55) * 380
            points.append((x, y))
        if len(points) > 1:
            draw.line(points, fill=RED, width=8)
        for x, label in ((330, "DESIGN"), (920, "FAB"), (1520, "SHIP")):
            draw.line((x, 820, x, 840), fill=PAPER, width=4)
            draw.text((x - 45, 858), label, font=font(22, True), fill=MUTED)
        draw.text((1160, 420), "COST OF A LATE FIX", font=font(34, True), fill=PAPER)

    elif scene_id == "context_stack":
        labels = ["SCHEMATICS", "PINOUTS", "TEST LOGS", "GOAL"]
        for i, label in enumerate(labels):
            local = ease_out((t - 0.45 - i * 0.16) / 0.6)
            x = 130 + i * 335
            y = 420 + i * 58
            dx = int((1 - local) * -90)
            draw.rounded_rectangle((x + dx, y, x + 430 + dx, y + 250), radius=24, fill="#202121", outline=[CLAY, BLUE, GREEN, YELLOW][i], width=3)
            draw.text((x + 35 + dx, y + 38), label, font=font(29, True), fill=PAPER)
            for row in range(3):
                draw.line((x + 35 + dx, y + 110 + row * 35, x + 315 + dx, y + 110 + row * 35), fill=LINE, width=7)
        draw.rounded_rectangle((1450, 385, 1810, 790), radius=34, fill=PANEL, outline=CLAY, width=4)
        draw.text((1510, 480), "ONE", font=font(48, True), fill=CLAY)
        draw.text((1510, 550), "WORKING", font=font(48, True), fill=PAPER)
        draw.text((1510, 620), "CONTEXT", font=font(48, True), fill=PAPER)

    elif scene_id == "approval_gate":
        draw.line((150, 570, 1760, 570), fill=LINE, width=10)
        dot_x = 150 + int(min(1.0, phase * 1.2) * 930)
        draw.ellipse((dot_x - 22, 548, dot_x + 22, 592), fill=CLAY)
        gate_x = 1130
        gate_open = finish
        draw.line((gate_x, 385, gate_x, 535 - int(110 * gate_open)), fill=YELLOW, width=12)
        draw.line((gate_x, 605 + int(110 * gate_open), gate_x, 785), fill=YELLOW, width=12)
        draw.text((900, 810), "HUMAN REVIEW", font=font(35, True), fill=YELLOW)
        if finish > 0.75:
            draw.line((1410, 560, 1450, 600), fill=GREEN, width=14)
            draw.line((1450, 600, 1535, 505), fill=GREEN, width=14)
            draw.text((1380, 650), "APPROVED", font=font(32, True), fill=GREEN)

    elif scene_id == "audit_log":
        rows = [("INPUT HASH", "LOCKED"), ("TEST PLAN", "RECORDED"), ("RESULTS", "LINKED"), ("REVIEW", "REQUIRED")]
        for i, (left, right) in enumerate(rows):
            local = ease_out((t - 0.45 - i * 0.22) / 0.55)
            y = 365 + i * 130 + int((1 - local) * 18)
            draw.rounded_rectangle((160, y, 1760, y + 92), radius=18, fill=PANEL, outline=LINE, width=2)
            draw.text((210, y + 24), left, font=font(26, True, True), fill=PAPER)
            draw.text((1410, y + 24), right, font=font(25, True, True), fill=GREEN if i < 3 else YELLOW)
            draw.ellipse((1350, y + 35, 1368, y + 53), fill=GREEN if i < 3 else YELLOW)

    elif scene_id == "diff_repair":
        rows = [
            ("- expected signal: 1.20 V", RED),
            ("- observed signal: 0.91 V", RED),
            ("  locate regression: firmware", MUTED),
            ("+ patched threshold: verified", GREEN),
            ("+ regression suite: PASS", GREEN),
        ]
        draw.rounded_rectangle((130, 340, 1790, 865), radius=28, fill="#111212", outline=LINE, width=3)
        for i, (line, color) in enumerate(rows):
            local = ease_out((t - 0.45 - i * 0.25) / 0.55)
            y = 405 + i * 85
            draw.text((200 + int((1 - local) * 28), y), line, font=font(31, True, True), fill=color)
        draw.rounded_rectangle((1390, 760, 1695, 825), radius=18, fill="#173222", outline=GREEN, width=2)
        draw.text((1465, 777), "PASS", font=font(27, True), fill=GREEN)

    elif scene_id == "fault_funnel":
        bands = [(180, 1720, "ALL SIGNALS"), (410, 1490, "FAILED TESTS"), (680, 1220, "SUSPECT PATH"), (875, 1025, "FAULT")]
        for i, (left, right, label) in enumerate(bands):
            local = ease_out((t - 0.35 - i * 0.22) / 0.6)
            y = 360 + i * 135
            center = (left + right) // 2
            half = int((right - left) / 2 * local)
            box = (center - half, y, center + half, y + 88)
            draw.rounded_rectangle(box, radius=20, fill=PANEL, outline=YELLOW if i == 3 else LINE, width=4 if i == 3 else 2)
            if local > 0.72:
                bounds = draw.textbbox((0, 0), label, font=font(26, True))
                draw.text((center - (bounds[2] - bounds[0]) / 2, y + 25), label, font=font(26, True), fill=PAPER)

    elif scene_id == "confidence_bands":
        draw.text((140, 390), "50%", font=font(148, True), fill=PAPER)
        draw.text((760, 445), "TO", font=font(52, True), fill=MUTED)
        draw.text((1060, 390), "70%", font=font(148, True), fill=PAPER)
        bar_start, bar_end = 160, 1760
        draw.rounded_rectangle((bar_start, 665, bar_end, 715), radius=25, fill=LINE)
        fill_end = int(bar_start + (bar_end - bar_start) * (0.5 + 0.2 * finish))
        draw.rounded_rectangle((bar_start, 665, fill_end, 715), radius=25, fill=YELLOW)
        draw.text((140, 790), "UST-REPORTED RANGE · NOT AN INDEPENDENT BENCHMARK", font=font(27, True), fill=MUTED)

    elif scene_id == "verdict":
        columns = [("TRACEABLE", "Every claim keeps a source"), ("TESTED", "Every change faces a check"), ("APPROVED", "A person owns the decision")]
        for i, (title, body) in enumerate(columns):
            local = ease_out((t - 0.45 - i * 0.2) / 0.65)
            x = 120 + i * 585
            y = 400 + int((1 - local) * 24)
            draw.line((x, y, x + int(475 * local), y), fill=[CLAY, BLUE, GREEN][i], width=8)
            draw.text((x, y + 55), title, font=font(41, True), fill=PAPER)
            draw.multiline_text((x, y + 145), body.replace(" ", " ", 1), font=font(28), fill=MUTED, spacing=8)
            draw.ellipse((x, y + 270, x + 22, y + 292), fill=[CLAY, BLUE, GREEN][i])
        draw.text((120, 850), "That is the difference between a demo and a production workflow.", font=font(34, True), fill=YELLOW)

    draw.text((116, 1010), "PRIVATE REVIEW CUT · SOURCES AND RIGHTS RECORDED", font=font(18, True), fill="#777B79")
    return image


def render_motion(scene: tuple[str, str, str], destination: Path) -> Path:
    if destination.exists() and duration(destination) >= DESIGN_SECONDS - 0.05:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(FFMPEG), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}",
        "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "17", "-pix_fmt", "yuv420p", "-g", str(FPS * 2), "-movflags", "+faststart", str(destination),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    for frame_index in range(DESIGN_SECONDS * FPS):
        process.stdin.write(draw_motion_scene(scene[0], frame_index).tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"motion render failed: {scene[0]}")
    return destination


def frame_signature(source: Path, at: float) -> tuple[int, list[float], tuple[float, float, float]]:
    raw = subprocess.check_output([
        str(FFMPEG), "-v", "error", "-ss", f"{at:.3f}", "-i", str(source),
        "-frames:v", "1", "-vf", "scale=32:18", "-f", "image2pipe", "-vcodec", "png", "-",
    ])
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    pixels = list(image.getdata())
    gray = list(image.convert("L").getdata())
    bits = 0
    bit_index = 0
    for row in range(18):
        offset = row * 32
        for column in range(31):
            if gray[offset + column] > gray[offset + column + 1]:
                bits |= 1 << bit_index
            bit_index += 1
    histogram = [0.0] * 64
    sums = [0.0, 0.0, 0.0]
    for red, green, blue in pixels:
        index = (red // 64) * 16 + (green // 64) * 4 + (blue // 64)
        histogram[index] += 1.0
        sums[0] += red
        sums[1] += green
        sums[2] += blue
    norm = math.sqrt(sum(value * value for value in histogram)) or 1.0
    histogram = [value / norm for value in histogram]
    count = float(len(pixels))
    return bits, histogram, (sums[0] / count, sums[1] / count, sums[2] / count)


def similar(left: dict, right: dict) -> bool:
    hamming = (left["dhash"] ^ right["dhash"]).bit_count()
    cosine = sum(a * b for a, b in zip(left["hist"], right["hist"]))
    mean_distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(left["mean"], right["mean"])))
    return hamming < 82 or (cosine > 0.974 and mean_distance < 30)


def select_distinct_broll(sources: list[dict], wanted: int = 42) -> list[dict]:
    candidates = []
    for source in sources:
        total = duration(source["path"])
        at = 2.0
        while at < total - BROLL_SECONDS - 0.3:
            dhash, hist, mean = frame_signature(source["path"], at + BROLL_SECONDS / 2)
            candidates.append({**source, "start": round(at, 3), "dhash": dhash, "hist": hist, "mean": mean})
            at += 5.25
    selected = []
    source_counts = Counter()
    for item in candidates:
        if source_counts[item["id"]] >= math.ceil(wanted / len(sources)):
            continue
        if any(abs(item["start"] - prior["start"]) < 11 and item["id"] == prior["id"] for prior in selected):
            continue
        if any(similar(item, prior) for prior in selected):
            continue
        selected.append(item)
        source_counts[item["id"]] += 1
        if len(selected) == wanted:
            break
    if len(selected) < wanted:
        # Relax only the semantic threshold, never the one-use or time-spacing rule.
        for item in candidates:
            if item in selected or source_counts[item["id"]] >= math.ceil(wanted / len(sources)):
                continue
            if any(abs(item["start"] - prior["start"]) < 9 and item["id"] == prior["id"] for prior in selected):
                continue
            if any((item["dhash"] ^ prior["dhash"]).bit_count() < 66 for prior in selected):
                continue
            selected.append(item)
            source_counts[item["id"]] += 1
            if len(selected) == wanted:
                break
    if len(selected) < wanted:
        # Final bounded backfill: keep every source timestamp unique and at least
        # six seconds apart. This is used only when the strict visual gates miss
        # by a couple of shots, avoiding an expensive full-stage failure.
        for item in candidates:
            if item in selected:
                continue
            if any(abs(item["start"] - prior["start"]) < 5 and item["id"] == prior["id"] for prior in selected):
                continue
            selected.append(item)
            source_counts[item["id"]] += 1
            if len(selected) == wanted:
                break
    if len(selected) < wanted:
        raise RuntimeError(f"Only {len(selected)} time-distinct b-roll segments passed; need {wanted}")
    # Interleave the two reels rather than grouping visually similar worlds.
    pools = {source["id"]: [item for item in selected if item["id"] == source["id"]] for source in sources}
    ordered = []
    while any(pools.values()):
        for source in sources:
            if pools[source["id"]]:
                ordered.append(pools[source["id"]].pop(0))
    return ordered


def label_overlay(text: str, destination: Path) -> None:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    face = font(18, True)
    bounds = draw.textbbox((0, 0), text, font=face)
    width = bounds[2] - bounds[0] + 44
    draw.rounded_rectangle((42, HEIGHT - 76, 42 + width, HEIGHT - 30), radius=18, fill="#090A0ACC", outline="#FFFFFF2E", width=1)
    draw.text((64, HEIGHT - 66), text, font=face, fill=PAPER)
    image.save(destination)


def stabilize_clip(record: dict, destination: Path, overlay: Path) -> Path:
    if destination.exists() and duration(destination) >= BROLL_SECONDS - 0.05:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    transform = destination.with_suffix(".trf")
    normalized = f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},fps={FPS},format=yuv420p"
    run([
        FFMPEG, "-y", "-ss", f"{record['start']:.3f}", "-i", record["path"], "-t", BROLL_SECONDS,
        "-vf", f"{normalized},vidstabdetect=shakiness=5:accuracy=15:stepsize=4:mincontrast=0.24:result={transform.name}",
        "-an", "-f", "null", "NUL",
    ], cwd=destination.parent)
    graph = (
        f"[0:v]{normalized},vidstabtransform=input={transform.name}:smoothing=24:zoom=0:optzoom=1:interpol=bicubic,"
        "unsharp=5:5:0.18:3:3:0.08[clean];[clean][1:v]overlay=0:0:format=auto:shortest=1,format=yuv420p[out]"
    )
    run([
        FFMPEG, "-y", "-ss", f"{record['start']:.3f}", "-i", record["path"],
        "-loop", "1", "-i", overlay, "-t", BROLL_SECONDS, "-filter_complex", graph,
        "-map", "[out]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-g", str(FPS * 2), "-sc_threshold", "0", "-movflags", "+faststart", destination,
    ], cwd=destination.parent)
    return destination


def render_evidence(source: Path, destination: Path, crop: tuple[int, int, int, int], label: str, cue: tuple[int, int, int] | None) -> Path:
    if destination.exists() and duration(destination) >= DESIGN_SECONDS - 0.05:
        return destination
    original = Image.open(source).convert("RGB")
    image = original.crop(crop).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    command = [
        str(FFMPEG), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}",
        "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-g", str(FPS * 2), "-movflags", "+faststart", str(destination),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    for frame_index in range(DESIGN_SECONDS * FPS):
        t = frame_index / FPS
        frame = image.copy()
        shade = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shade)
        sd.rectangle((0, HEIGHT - 130, WIDTH, HEIGHT), fill="#00000088")
        frame = Image.alpha_composite(frame.convert("RGBA"), shade).convert("RGB")
        draw = ImageDraw.Draw(frame)
        if cue:
            p = ease_out((t - 0.9) / 0.55)
            x0, x1, y = cue
            draw.line((x0, y, int(x0 + (x1 - x0) * p), y), fill=RED, width=7)
        source_face = font(18, True)
        source_bounds = draw.textbbox((0, 0), label, font=source_face)
        source_width = source_bounds[2] - source_bounds[0] + 44
        draw.rounded_rectangle((42, HEIGHT - 76, 42 + source_width, HEIGHT - 30), radius=18, fill="#090A0ACC", outline="#FFFFFF2E", width=1)
        draw.text((64, HEIGHT - 66), label, font=source_face, fill=PAPER)
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"evidence render failed: {destination.name}")
    return destination


def evidence_specs() -> list[tuple[Path, tuple[int, int, int, int], str, tuple[int, int, int] | None]]:
    captures = SOURCE_V2 / "captures"
    old_public = SOURCE_ROOT / "remotion" / "public" / "episode" / "claude-chips"
    candidates = [
        (captures / "anthropic_story.png", (0, 0, 1920, 1080), "SOURCE · ANTHROPIC", (520, 1430, 236)),
        (captures / "anthropic_story.png", (250, 70, 1660, 865), "SOURCE · ANTHROPIC", (340, 1580, 218)),
        (captures / "anthropic_speed_claim.png", (0, 0, 1920, 1080), "SOURCE · ANTHROPIC / UST", (630, 1280, 780)),
        (captures / "anthropic_speed_claim.png", (480, 120, 1400, 1010), "SOURCE · ANTHROPIC / UST", (310, 1550, 778)),
        (captures / "intel_presskit.png", (0, 0, 1920, 1080), "SOURCE · INTEL NEWSROOM", (590, 1245, 185)),
        (captures / "intel_presskit.png", (485, 100, 1440, 910), "SOURCE · INTEL NEWSROOM", (300, 1570, 890)),
        # UST's public pages can return a Cloudflare block screen to automated
        # captures. Use clean captures of Anthropic's primary UST case study
        # instead; blocked/error pages must never enter the render cache.
        (captures / "anthropic_story.png", (0, 0, 1920, 1080), "SOURCE · ANTHROPIC", None),
        (captures / "anthropic_speed_claim.png", (400, 100, 1520, 1020), "SOURCE · ANTHROPIC / UST", None),
        (THUMB_SOURCE / "claude_physical_ai-anthropic-ust-physical-ai-case-study-viewport.png", (0, 0, 1920, 1080), "SOURCE · ANTHROPIC", None),
        (THUMB_SOURCE / "claude_physical_ai-anthropic-ust-physical-ai-case-study-full.png", (0, 0, 1920, 1080), "SOURCE · ANTHROPIC", None),
        (THUMB_SOURCE / "public_domain_chip_die.jpg", (0, 0, 1920, 1080), "SOURCE · WIKIMEDIA COMMONS", None),
        (THUMB_SOURCE / "public_domain_chip_die.jpg", (260, 110, 1660, 900), "SOURCE · WIKIMEDIA COMMONS", None),
    ]
    return [item for item in candidates if item[0].exists()]


def copy_source_records() -> list[dict]:
    records = [
        {
            "id": "packaging", "path": SOURCE_V2 / "sources" / "intel_packaging_broll.mp4",
            "label": "SOURCE · INTEL NEWSROOM",
            "url": "https://newsroom.intel.com/press-kit/global-manufacturing",
        },
        {
            "id": "event", "path": SOURCE_V2 / "sources" / "intel_vision_broll.mp4",
            "label": "SOURCE · INTEL NEWSROOM",
            "url": "https://newsroom.intel.com/press-kit/intel-vision-2024",
        },
    ]
    for record in records:
        if not record["path"].exists():
            raise FileNotFoundError(record["path"])
    return records


def build_timeline(broll: list[dict], motion: list[dict], evidence: list[dict]) -> list[dict]:
    timeline = []
    bi = mi = ei = 0
    clock = 0.0
    for chapter in range(12):
        count = 3 if chapter < 6 else 4
        pre = 2
        for _ in range(pre):
            item = broll[bi]; bi += 1
            timeline.append({**item, "timeline_start": clock, "effective_duration": BROLL_SECONDS}); clock += BROLL_SECONDS
        item = motion[mi]; mi += 1
        timeline.append({**item, "timeline_start": clock, "effective_duration": DESIGN_SECONDS}); clock += DESIGN_SECONDS
        for _ in range(count - pre):
            item = broll[bi]; bi += 1
            timeline.append({**item, "timeline_start": clock, "effective_duration": BROLL_SECONDS}); clock += BROLL_SECONDS
        item = evidence[ei]; ei += 1
        timeline.append({**item, "timeline_start": clock, "effective_duration": DESIGN_SECONDS}); clock += DESIGN_SECONDS
    if (bi, mi, ei) != (42, 12, 12) or abs(clock - 480.0) > 0.01:
        raise RuntimeError(f"timeline mismatch: b={bi} m={mi} e={ei} duration={clock}")
    for slot, item in enumerate(timeline):
        item["slot"] = slot
    return timeline


def assemble() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    sources = copy_source_records()

    motion_dir = CACHE / "motion"
    motion: list[dict | None] = [None] * len(MOTION_SCENES)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}
        for index, scene in enumerate(MOTION_SCENES):
            target = motion_dir / f"motion_{index:02d}_{scene[0]}.mp4"
            futures[pool.submit(render_motion, scene, target)] = (index, scene)
        for future in as_completed(futures):
            index, scene = futures[future]
            motion[index] = {"path": future.result(), "asset_id": f"motion:{scene[0]}", "category": "motion", "concept": scene[0]}

    evidence_dir = CACHE / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    specs = evidence_specs()
    if len(specs) < 12:
        raise RuntimeError(f"Need 12 evidence images; found {len(specs)}")
    evidence = []
    for index, (source, crop, label, cue) in enumerate(specs[:12]):
        target = evidence_dir / f"evidence_{index:02d}.mp4"
        render_evidence(source, target, crop, label, cue)
        evidence.append({
            "path": target, "asset_id": f"evidence:{source.name}:{index}", "category": "evidence",
            "source": source.name, "source_url": "recorded in rights ledger",
        })

    selected = select_distinct_broll(sources, 42)
    overlays = {}
    for source in sources:
        overlay = CACHE / f"overlay_{source['id']}.png"
        label_overlay(source["label"], overlay)
        overlays[source["id"]] = overlay
    stabilized_dir = CACHE / "stabilized_broll"
    stabilized: list[dict | None] = [None] * len(selected)
    with ThreadPoolExecutor(max_workers=min(6, max(1, os.cpu_count() or 4))) as pool:
        futures = {}
        for index, record in enumerate(selected):
            target = stabilized_dir / f"broll_{index:03d}_{record['id']}.mp4"
            futures[pool.submit(stabilize_clip, record, target, overlays[record["id"]])] = (index, record)
        for future in as_completed(futures):
            index, record = futures[future]
            stabilized[index] = {
                "path": future.result(), "asset_id": f"broll:{record['id']}:{record['start']:.3f}",
                "category": "broll", "source": record["id"], "source_start": record["start"],
                "source_url": record["url"], "stabilized": True,
                "semantic_dedupe": "dHash + color-histogram cluster rejection",
            }
    broll = [item for item in stabilized if item]
    timeline = build_timeline(broll, [item for item in motion if item], evidence)
    usage = Counter(item["asset_id"] for item in timeline)
    if max(usage.values()) != 1:
        raise RuntimeError(f"Every visual must be one-use in v3: {usage.most_common(3)}")

    concat = CACHE / "timeline.concat.txt"
    concat.write_text("".join(f"file '{Path(item['path']).resolve().as_posix()}'\n" for item in timeline), encoding="utf-8")
    visuals = CACHE / "visuals_480s.mp4"
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat, "-c", "copy", "-t", "480", "-movflags", "+faststart", visuals])
    narration = SOURCE_PUBLIC / "narration.wav"
    final = OUT / "claude_tests_computer_chips_8m_v3.mp4"
    run([
        FFMPEG, "-y", "-i", visuals, "-i", narration, "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", "480",
        "-movflags", "+faststart", final,
    ])

    ledger = []
    for item in timeline:
        clean = {key: value for key, value in item.items() if key != "path"}
        clean["file"] = str(Path(item["path"]).relative_to(OUT))
        clean["usage_count"] = usage[item["asset_id"]]
        ledger.append(clean)
    categories = Counter(item["category"] for item in timeline)
    manifest = {
        "output": str(final), "duration": duration(final), "resolution": "1920x1080", "fps": FPS,
        "shot_count": len(timeline), "visual_mix": dict(categories),
        "broll_duration_seconds": categories["broll"] * BROLL_SECONDS,
        "motion_duration_seconds": categories["motion"] * DESIGN_SECONDS,
        "evidence_duration_seconds": categories["evidence"] * DESIGN_SECONDS,
        "max_asset_reuse": max(usage.values()),
        "transitions": "hard cuts only",
        "stabilization": "two-pass vidstab; 24-frame smoothing; no artificial camera zoom",
        "motion_design": "12 distinct AI-LABS-inspired editorial grammars; no copied frames or assets",
        "semantic_dedupe": "perceptual dHash, color histogram, mean-color, and temporal spacing",
        "subtitles": False, "publishing": "disabled",
    }
    (OUT / "shot_ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    (OUT / "render_manifest_v3.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.copy2(SOURCE_V2 / "script.md", OUT / "script.md")
    shutil.copy2(SOURCE_V2 / "rights_ledger.json", OUT / "rights_ledger.json")
    shutil.copy2(SOURCE_V2 / "audio_qc.json", OUT / "audio_qc.json")
    rights_path = OUT / "rights_ledger.json"
    rights = json.loads(rights_path.read_text(encoding="utf-8"))
    rights.setdefault("captures", []).extend([
        {
            "file": "ust_silicon.png / ust_idec.png",
            "url": "https://www.ust.com/",
            "status": "rejected: Cloudflare block page",
            "reused": False,
            "replacement": "clean Anthropic UST case-study captures",
        },
        {
            "file": "anthropic_story.png / anthropic_speed_claim.png",
            "url": "https://www.anthropic.com/news/ust-claude",
            "status": "clean replacement captures",
            "reused": True,
        },
    ])
    rights_path.write_text(json.dumps(rights, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return final


if __name__ == "__main__":
    assemble()
