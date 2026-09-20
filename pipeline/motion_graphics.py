"""Deterministic branded graphics for exact typography, charts, and comparisons."""
from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from .config import FFMPEG_PRESET, FFMPEG_THREADS_PER_JOB, VIDEO_FPS, VIDEO_H, VIDEO_W
from .models import EpisodeProject, Shot
from .thumbnail import _font


_GRADIENT_BASE: Image.Image | None = None


def _gradient() -> Image.Image:
    global _GRADIENT_BASE
    if _GRADIENT_BASE is not None:
        return _GRADIENT_BASE.copy()
    image = Image.new("RGB", (VIDEO_W, VIDEO_H))
    pixels = image.load()
    for y in range(VIDEO_H):
        for x in range(VIDEO_W):
            pink = x / VIDEO_W
            blue = 1 - pink
            glow = max(0.0, 1 - (((x - 960) / 1100) ** 2 + ((y - 470) / 800) ** 2))
            pixels[x, y] = (
                int(239 + 11 * pink + 4 * glow),
                int(244 + 5 * glow),
                int(255 - 8 * pink),
            )
    _GRADIENT_BASE = image
    return image.copy()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int, max_lines: int = 3) -> list[str]:
    words = text.strip().split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(" ".join(lines).split()) < len(words):
        lines[-1] = lines[-1].rstrip(".,") + "…"
    return lines


def _pill(draw: ImageDraw.ImageDraw, label: str) -> None:
    font = _font(26)
    text = label.upper().replace("_", " ")[:26]
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0] + 78
    x = (VIDEO_W - width) // 2
    draw.rounded_rectangle((x, 54, x + width, 112), radius=29, fill=(255, 255, 255), outline=(225, 226, 244), width=2)
    draw.ellipse((x + 20, 72, x + 36, 88), fill=(155, 92, 246))
    draw.text((x + 50, 68), text, font=font, fill=(74, 72, 92))


def _headline(draw: ImageDraw.ImageDraw, text: str, y: int = 150) -> int:
    font = _font(64)
    lines = _wrap(draw, text.upper(), font, 1420, 2)
    for index, line in enumerate(lines):
        box = draw.textbbox((0, 0), line, font=font)
        x = (VIDEO_W - (box[2] - box[0])) // 2
        fill = (42, 39, 63) if index == 0 else (87, 123, 238)
        draw.text((x, y), line, font=font, fill=fill)
        y += 78
    return y


def _comparison(draw: ImageDraw.ImageDraw, text: str, top: int) -> None:
    halves = re.split(r"\b(?:versus|vs\.?|but|while)\b", text, maxsplit=1, flags=re.IGNORECASE)
    if len(halves) == 1:
        halves = ["What the claim suggests", "What the evidence actually shows"]
    colors = [(255, 236, 241), (233, 247, 255)]
    labels = ["THE CLAIM", "THE EVIDENCE"]
    for index, body in enumerate(halves[:2]):
        x1 = 120 + index * 855
        x2 = x1 + 735
        draw.rounded_rectangle((x1, top + 40, x2, 860), radius=38, fill=colors[index], outline=(224, 224, 241), width=3)
        draw.text((x1 + 52, top + 84), labels[index], font=_font(28), fill=(108, 94, 146))
        lines = _wrap(draw, body.strip(), _font(45), 625, 5)
        y = top + 155
        for line in lines:
            draw.text((x1 + 52, y), line, font=_font(45), fill=(39, 37, 58))
            y += 62


def _stat(draw: ImageDraw.ImageDraw, project: EpisodeProject, shot: Shot, top: int) -> None:
    beat = next((item for item in project.script.beats if item.id == shot.beat_id), None) if project.script else None
    claim = next((item for item in project.claims if beat and item.id in beat.claim_ids and item.kind == "number"), None)
    text = claim.text if claim else shot.prompt
    match = re.search(r"(?:\$?[\d,.]+(?:%|x|×|[KMB])?|\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b)", text, re.I)
    number = match.group(0) if match else "KEY POINT"
    draw.rounded_rectangle((300, top + 30, 1620, 870), radius=48, fill=(255, 255, 255), outline=(218, 220, 241), width=3)
    number_font = _font(126 if len(number) < 10 else 82)
    box = draw.textbbox((0, 0), number, font=number_font)
    draw.text(((VIDEO_W - (box[2] - box[0])) / 2, top + 95), number, font=number_font, fill=(108, 85, 232))
    lines = _wrap(draw, text, _font(42), 1120, 4)
    y = top + 290
    for line in lines:
        box = draw.textbbox((0, 0), line, font=_font(42))
        draw.text(((VIDEO_W - (box[2] - box[0])) / 2, y), line, font=_font(42), fill=(54, 52, 72))
        y += 58


def _flow(draw: ImageDraw.ImageDraw, text: str, top: int) -> None:
    terms = [part.strip() for part in re.split(r"[,;:]|\bthen\b|\bto\b", text, flags=re.I) if part.strip()]
    if len(terms) < 2:
        terms = ["SOURCE", "ANALYSIS", "TAKEAWAY"]
    else:
        terms = (terms + ["RESULT"])[:3]
    for index, term in enumerate(terms):
        x = 130 + index * 590
        draw.rounded_rectangle((x, top + 150, x + 470, top + 400), radius=34, fill=(255, 255, 255), outline=(206, 212, 239), width=3)
        lines = _wrap(draw, term, _font(34), 380, 3)
        y = top + 215
        for line in lines:
            draw.text((x + 46, y), line, font=_font(34), fill=(45, 43, 64))
            y += 46
        if index < 2:
            draw.line((x + 486, top + 275, x + 570, top + 275), fill=(99, 125, 232), width=8)
            draw.polygon([(x + 570, top + 275), (x + 548, top + 261), (x + 548, top + 289)], fill=(99, 125, 232))


def render_motion_graphic(project: EpisodeProject, shot: Shot, destination: Path) -> Path:
    """Render exact, legible graphics locally so generative video never has to spell UI text."""
    image = _gradient()
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((28, 24, VIDEO_W - 28, VIDEO_H - 24), radius=46, outline=(255, 255, 255), width=3)
    beat = next((item for item in project.script.beats if item.id == shot.beat_id), None) if project.script else None
    purpose = beat.purpose if beat else shot.asset_type
    _pill(draw, purpose)
    top = _headline(draw, shot.prompt[:150])
    if shot.asset_type == "chart":
        _stat(draw, project, shot, top)
    elif purpose == "comparison":
        _comparison(draw, shot.prompt, top)
    else:
        _flow(draw, shot.prompt, top)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, quality=96)
    return destination


def _draw_concept_plate(*, completed: bool) -> Image.Image:
    """Create a text-free whiteboard start or completed teaching plate."""
    image = Image.new("RGB", (VIDEO_W, VIDEO_H), (246, 241, 226))
    draw = ImageDraw.Draw(image)
    for y in range(55, VIDEO_H, 72):
        draw.line((0, y, VIDEO_W, y + 2), fill=(234, 232, 224), width=1)
    ink = (42, 42, 43)
    muted = (116, 113, 106)
    accent = (221, 91, 62)

    if not completed:
        # One real action cue only. The final geometry arrives as a constrained
        # end frame, so the video model does not invent the explanation.
        draw.polygon([(210, 785), (360, 862), (338, 905), (182, 824)], fill=(34, 35, 37))
        draw.polygon([(182, 824), (151, 838), (168, 804), (210, 785)], fill=(15, 15, 16))
        draw.ellipse((143, 832, 157, 846), fill=ink)
        return image

    # Completed board: messy input becomes orderly output through three stages.
    for index in range(22):
        x = 235 + (index * 47) % 260
        y = 390 + (index * 83) % 290
        radius = 5 + index % 4
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=muted)
    draw.ellipse((180, 330, 545, 740), outline=ink, width=9)

    stages = [(700, 390, 900, 680), (975, 390, 1175, 680), (1250, 390, 1450, 680)]
    for stage_index, (x1, y1, x2, y2) in enumerate(stages):
        draw.rounded_rectangle((x1, y1, x2, y2), radius=24, outline=ink, width=8)
        count = 15 - stage_index * 5
        for dot in range(count):
            angle = dot / max(1, count) * math.tau
            radius = 64 - stage_index * 14
            x = (x1 + x2) / 2 + math.cos(angle) * radius
            y = (y1 + y2) / 2 + math.sin(angle) * radius
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=ink)

    for start_x, end_x in ((565, 670), (915, 955), (1190, 1230), (1470, 1560)):
        draw.line((start_x, 535, end_x, 535), fill=ink, width=9)
        draw.line((end_x, 535, end_x - 24, 517), fill=ink, width=9)
        draw.line((end_x, 535, end_x - 24, 553), fill=ink, width=9)
    draw.polygon([(1580, 500), (1765, 445), (1690, 610)], outline=ink)
    draw.line((1580, 500, 1690, 545, 1765, 445), fill=ink, width=9)
    draw.ellipse((1705, 265, 1775, 335), outline=accent, width=10)
    draw.arc((1570, 700, 1820, 790), start=190, end=350, fill=accent, width=11)
    return image


def render_motion_plate(project: EpisodeProject, shot: Shot, destination: Path) -> Path:
    """Render a text-free design plate for Magic Hour to animate.

    The plate uses exact local geometry rather than an AI-generated hero image. It is
    intentionally free of faces, fake interfaces, logos, and typography so a video
    model cannot turn those details into recognizable AI-artifacts.
    """
    if shot.asset_type == "concept_animation":
        image = _draw_concept_plate(completed=False)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, quality=96)
        return destination

    if shot.motion_template == "seedance_editorial":
        image = _draw_seedance_editorial_plate(shot)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, quality=96)
        return destination

    image = _gradient()
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((28, 24, VIDEO_W - 28, VIDEO_H - 24), radius=46, outline=(255, 255, 255), width=3)
    draw.ellipse((760, 250, 1160, 650), fill=(236, 239, 255), outline=(113, 122, 226), width=5)
    draw.ellipse((850, 340, 1070, 560), fill=(255, 255, 255), outline=(128, 98, 224), width=4)
    nodes = [(250, 290), (250, 690), (1470, 290), (1470, 690)]
    for index, (x, y) in enumerate(nodes):
        fill = (255, 255, 255) if index % 2 == 0 else (241, 246, 255)
        draw.rounded_rectangle((x, y, x + 210, y + 120), radius=30, fill=fill, outline=(190, 201, 237), width=4)
        start_x = x + 210 if x < VIDEO_W / 2 else x
        end_x = 800 if x < VIDEO_W / 2 else 1120
        draw.line((start_x, y + 60, end_x, 450), fill=(111, 133, 226), width=7)
    draw.arc((720, 210, 1200, 690), start=15, end=155, fill=(239, 112, 167), width=9)
    draw.arc((720, 210, 1200, 690), start=195, end=335, fill=(82, 168, 230), width=9)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, quality=96)
    return destination


def _draw_seedance_editorial_plate(shot: Shot) -> Image.Image:
    """Create a neutral 16:9 anchor with one clear explanatory metaphor."""
    paper = (240, 242, 240)
    ink = (18, 21, 19)
    line = (108, 116, 110)
    clay = (181, 111, 85)
    moss = (102, 124, 109)
    shadow = (207, 211, 207)
    image = Image.new("RGB", (VIDEO_W, VIDEO_H), paper)
    draw = ImageDraw.Draw(image)
    idea = f"{shot.prompt} {shot.semantic_target}".casefold()

    # Quiet paper structure keeps the plate tactile without an ambient gradient.
    for y in range(80, VIDEO_H, 120):
        draw.line((92, y, VIDEO_W - 92, y), fill=(233, 235, 233), width=2)

    if any(token in idea for token in ("versus", "compare", "before", "after")):
        # Two unequal proof objects and one decisive seam; no card grid.
        draw.rounded_rectangle((202, 230, 862, 870), radius=38, fill=shadow)
        draw.rounded_rectangle((184, 210, 844, 850), radius=38, fill=(255, 255, 255), outline=ink, width=5)
        draw.ellipse((352, 380, 676, 704), fill=moss)
        draw.rounded_rectangle((1066, 154, 1738, 826), radius=38, fill=shadow)
        draw.rounded_rectangle((1048, 134, 1720, 806), radius=38, fill=(255, 255, 255), outline=ink, width=5)
        draw.polygon([(1224, 664), (1372, 346), (1538, 664)], fill=clay)
        draw.line((956, 190, 956, 884), fill=ink, width=7)
        return image

    if any(token in idea for token in ("timeline", "sequence", "chronology", "over time", "four step")):
        # A readable left-to-right sequence with one emphasized destination.
        y = 548
        draw.line((218, y, 1690, y), fill=ink, width=8)
        positions = [286, 708, 1130, 1552]
        for index, x in enumerate(positions):
            radius = 78 if index < 3 else 118
            draw.ellipse((x - radius + 14, y - radius + 18, x + radius + 14, y + radius + 18), fill=shadow)
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=clay if index == 3 else (255, 255, 255), outline=ink, width=6,
            )
            if index < 3:
                draw.ellipse((x - 22, y - 22, x + 22, y + 22), fill=moss)
        return image

    # Default mechanism: small inputs converge into one dominant resolved object.
    input_centers = [(680, 380), (680, 720)]
    merge = (1060, 550)
    for x, y in input_centers:
        draw.ellipse((x - 82 + 12, y - 82 + 14, x + 82 + 12, y + 82 + 14), fill=shadow)
        draw.ellipse((x - 82, y - 82, x + 82, y + 82), fill=(255, 255, 255), outline=ink, width=5)
        draw.ellipse((x - 22, y - 22, x + 22, y + 22), fill=moss)
        draw.line((x + 84, y, merge[0], merge[1]), fill=line, width=8)
    draw.line((merge[0], merge[1], 1240, merge[1]), fill=ink, width=10)
    draw.polygon([(1240, merge[1]), (1200, merge[1] - 27), (1200, merge[1] + 27)], fill=ink)
    draw.rounded_rectangle((1302, 224, 1780, 850), radius=54, fill=shadow)
    draw.rounded_rectangle((1280, 202, 1758, 828), radius=54, fill=(255, 255, 255), outline=ink, width=6)
    draw.ellipse((1380, 362, 1658, 640), fill=clay)
    draw.arc((1354, 336, 1684, 666), start=18, end=292, fill=ink, width=9)
    return image


def render_concept_end_plate(project: EpisodeProject, shot: Shot, destination: Path) -> Path:
    """Render the constrained completed board for a Magic Hour whiteboard shot."""
    image = _draw_concept_plate(completed=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, quality=96)
    return destination


def _ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def _template(project: EpisodeProject, shot: Shot) -> str:
    if shot.motion_template != "auto":
        return shot.motion_template
    beat = next((item for item in project.script.beats if item.id == shot.beat_id), None) if project.script else None
    purpose = beat.purpose if beat else "analysis"
    if shot.asset_type == "chapter_card":
        return "chapter_title"
    if shot.asset_type == "chart":
        return "stat_reveal"
    if purpose == "comparison":
        return "comparison"
    if purpose in {"evidence", "observation", "test_setup"}:
        return "evidence_focus"
    if purpose in {"implication", "analysis"}:
        return "orbit_map"
    return "step_flow"


def _reference_image(project: EpisodeProject, shot: Shot) -> Image.Image | None:
    for candidate in project.shots:
        if candidate.beat_id != shot.beat_id or not candidate.asset_path:
            continue
        path = Path(candidate.asset_path)
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"} or not path.is_file():
            continue
        try:
            return Image.open(path).convert("RGB")
        except OSError:
            continue
    return None


def _fit_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / image.width, height / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _paste_rounded(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int], radius: int = 36) -> None:
    x1, y1, x2, y2 = box
    fitted = _fit_cover(image, x2 - x1, y2 - y1)
    mask = Image.new("L", fitted.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, fitted.width, fitted.height), radius=radius, fill=255)
    canvas.paste(fitted, (x1, y1), mask)


def _center_text(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill=(42, 39, 63)) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((VIDEO_W - (box[2] - box[0])) / 2, y), text, font=font, fill=fill)


def _animated_frame(project: EpisodeProject, shot: Shot, progress: float) -> Image.Image:
    template = _template(project, shot)
    if template == "seedance_editorial":
        return _animated_seedance_editorial_frame(shot, progress)
    image = _gradient()
    draw = ImageDraw.Draw(image)
    reveal = _ease(min(1.0, progress / 0.28))
    accent = (231, 58, 74)
    ink = (35, 34, 54)
    draw.rounded_rectangle((28, 24, VIDEO_W - 28, VIDEO_H - 24), radius=46, outline=(255, 255, 255), width=3)

    if template == "chapter_title":
        y = round(470 - 45 * (1 - reveal))
        _center_text(draw, shot.prompt[:68].upper(), y, _font(76), ink)
        width = round(560 * _ease(max(0, (progress - 0.18) / 0.32)))
        draw.rounded_rectangle((960 - width // 2, y + 112, 960 + width // 2, y + 119), radius=4, fill=accent)
        return image

    if template in {"ui_stage", "evidence_focus"}:
        reference = _reference_image(project, shot)
        if reference is not None:
            x = round(170 + 70 * (1 - reveal))
            box = (x, 176, x + 1580, 962)
            draw.rounded_rectangle((box[0] - 10, box[1] - 48, box[2] + 10, box[3] + 10), radius=42, fill=(40, 37, 50))
            draw.ellipse((box[0] + 22, box[1] - 31, box[0] + 42, box[1] - 11), fill=(255, 95, 104))
            draw.ellipse((box[0] + 54, box[1] - 31, box[0] + 74, box[1] - 11), fill=(255, 197, 72))
            draw.ellipse((box[0] + 86, box[1] - 31, box[0] + 106, box[1] - 11), fill=(78, 207, 109))
            _paste_rounded(image, reference, box, radius=30)
            underline = round(440 * _ease(max(0, (progress - 0.34) / 0.25)))
            draw.rounded_rectangle((box[0] + 140, box[3] - 110, box[0] + 140 + underline, box[3] - 104), radius=3, fill=accent)
            if progress > 0.6:
                arrow = _ease((progress - 0.6) / 0.25)
                x2 = round(box[2] - 330 * arrow)
                y2 = box[1] + 230
                draw.line((box[2] - 105, box[1] + 105, x2, y2), fill=accent, width=7)
                draw.polygon([(x2, y2), (x2 + 24, y2 - 5), (x2 + 11, y2 - 24)], fill=accent)
            return image
        template = "step_flow"

    if template == "orbit_map":
        center = (960, 545)
        radius = 310
        for start in range(0, 360, 18):
            draw.arc((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), start, start + 9, fill=(179, 180, 200), width=4)
        draw.rounded_rectangle((690, 485, 1230, 605), radius=60, fill=(255, 255, 255), outline=(210, 211, 226), width=3)
        _center_text(draw, "THE CORE IDEA", 516, _font(34), ink)
        labels = ["SOURCE", "MODEL", "TOOL", "RESULT"]
        for index, label in enumerate(labels):
            phase = index * math.pi / 2 + progress * 0.35
            x = center[0] + round(radius * math.cos(phase))
            y = center[1] + round(radius * math.sin(phase))
            draw.ellipse((x - 74, y - 74, x + 74, y + 74), fill=(255, 255, 255), outline=(104, 117, 222), width=4)
            box = draw.textbbox((0, 0), label, font=_font(23))
            draw.text((x - (box[2] - box[0]) / 2, y - 14), label, font=_font(23), fill=ink)
        return image

    if template == "comparison":
        halves = re.split(r"\b(?:versus|vs\.?|but|while)\b", shot.prompt, maxsplit=1, flags=re.I)
        halves = halves if len(halves) == 2 else ["What the claim suggests", "What the evidence changes"]
        for index, body in enumerate(halves):
            local = _ease(max(0, min(1, progress * 2.2 - index * 0.3)))
            x = round((120 if index == 0 else 1015) + (1 - local) * (-100 if index == 0 else 100))
            draw.rounded_rectangle((x, 235, x + 785, 860), radius=42, fill=(255, 255, 255), outline=(216, 218, 237), width=3)
            draw.text((x + 58, 292), "CLAIM" if index == 0 else "EVIDENCE", font=_font(28), fill=(108, 94, 146))
            y = 385
            for line in _wrap(draw, body.strip(), _font(43), 665, 5):
                draw.text((x + 58, y), line, font=_font(43), fill=ink)
                y += 60
        return image

    if template == "stat_reveal":
        match = re.search(r"(?:\$?[\d,.]+(?:%|x|×|[KMB])?)", shot.prompt, re.I)
        number = match.group(0) if match else "PROOF"
        shown = number if progress > 0.24 else ""
        _center_text(draw, shown, 300, _font(142 if len(number) < 9 else 92), (105, 82, 228))
        bar = round(1180 * _ease(max(0, (progress - 0.18) / 0.5)))
        draw.rounded_rectangle((370, 610, 370 + bar, 654), radius=22, fill=(105, 82, 228))
        _center_text(draw, shot.prompt[:92], 720, _font(38), ink)
        return image

    terms = [part.strip() for part in re.split(r"[,;:]|\bthen\b|\bto\b", shot.prompt, flags=re.I) if part.strip()]
    terms = (terms + ["EVIDENCE", "MEANING", "DECISION"])[:3]
    for index, term in enumerate(terms):
        local = _ease(max(0, min(1, progress * 2.0 - index * 0.28)))
        x = 140 + index * 585
        y = round(390 + 70 * (1 - local))
        draw.rounded_rectangle((x, y, x + 455, y + 270), radius=36, fill=(255, 255, 255), outline=(205, 211, 238), width=3)
        for line_index, line in enumerate(_wrap(draw, term, _font(34), 365, 3)):
            draw.text((x + 44, y + 76 + line_index * 46), line, font=_font(34), fill=ink)
        if index < 2 and local > 0.75:
            draw.line((x + 475, y + 135, x + 555, y + 135), fill=(99, 125, 232), width=7)
            draw.polygon([(x + 555, y + 135), (x + 534, y + 121), (x + 534, y + 149)], fill=(99, 125, 232))
    return image


def _animated_seedance_editorial_frame(shot: Shot, progress: float) -> Image.Image:
    """Exact fallback for a Seedance insert that fails temporal QC."""
    image = _draw_seedance_editorial_plate(shot)
    draw = ImageDraw.Draw(image)
    ink = (18, 21, 19)
    clay = (181, 111, 85)
    moss = (102, 124, 109)
    muted = (77, 84, 79)
    idea = f"{shot.prompt} {shot.semantic_target}".casefold()

    title_reveal = _ease(min(1.0, progress / 0.12))
    title_y = round(108 + 16 * (1 - title_reveal))
    draw.rectangle((104, title_y - 24, 170, title_y - 18), fill=clay)
    draw.text((104, title_y), "HOW AI ROUTING WORKS", font=_font(28), fill=muted)
    if "input" in idea and any(token in idea for token in ("result", "output")):
        draw.text((104, title_y + 40), "TWO INPUTS.", font=_font(72), fill=ink)
        draw.text((104, title_y + 118), "ONE RESULT.", font=_font(72), fill=clay)
    else:
        words = [word.upper().strip(".,:;()") for word in shot.prompt.split() if word.strip(".,:;()")]
        headline = " ".join(words[:5]) or "HOW IT WORKS"
        draw.text((104, title_y + 52), headline, font=_font(60), fill=ink)

    # The authored geometry never moves. Signals travel along it and disappear.
    def point(start: tuple[int, int], end: tuple[int, int], value: float) -> tuple[int, int]:
        return (
            round(start[0] + (end[0] - start[0]) * value),
            round(start[1] + (end[1] - start[1]) * value),
        )

    merge = (1060, 550)
    signal_specs = [((764, 380), merge, 0.18, 0.43), ((764, 720), merge, 0.34, 0.59)]
    for start, end, begin, finish in signal_specs:
        local = (progress - begin) / max(0.001, finish - begin)
        if 0.0 <= local <= 1.0:
            x, y = point(start, end, _ease(local))
            draw.ellipse((x - 18, y - 18, x + 18, y + 18), fill=moss, outline=ink, width=3)

    output_local = (progress - 0.52) / 0.18
    if 0.0 <= output_local <= 1.0:
        x, y = point(merge, (1240, 550), _ease(output_local))
        draw.ellipse((x - 19, y - 19, x + 19, y + 19), fill=clay, outline=ink, width=3)

    result_reveal = _ease(max(0.0, min(1.0, (progress - 0.66) / 0.12)))
    if result_reveal > 0:
        radius = round(142 + 18 * math.sin(result_reveal * math.pi))
        center = (1519, 501)
        draw.arc(
            (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius),
            start=-90, end=-90 + round(360 * result_reveal), fill=clay, width=12,
        )
    return image


def render_motion_video(
    project: EpisodeProject, shot: Shot, destination: Path, duration: float | None = None, fps: int = VIDEO_FPS,
) -> Path:
    """Render transcript-aligned exact motion locally; no generative pixels or invented UI."""
    seconds = float(duration or shot.duration_seconds)
    frames = max(2, round(seconds * fps))
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VIDEO_W}x{VIDEO_H}",
        "-r", str(fps), "-i", "-", "-an", "-vf",
        "tpad=stop_mode=clone:stop_duration=1,format=yuv420p",
        "-t", f"{seconds:.3f}", "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", "18",
        "-threads", str(FFMPEG_THREADS_PER_JOB),
        "-movflags", "+faststart", str(destination),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert process.stdin is not None
        for index in range(frames):
            progress = index / max(1, frames - 1)
            process.stdin.write(_animated_frame(project, shot, progress).tobytes())
        process.stdin.close()
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        return_code = process.wait()
        if return_code:
            raise RuntimeError("motion render failed: " + "\n".join(stderr.splitlines()[-12:]))
    finally:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
    return destination
