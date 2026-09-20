"""Professional, evidence-first screenshot framing and annotation overlays."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .config import VIDEO_H, VIDEO_W
from .models import Shot, VisualAnnotation
from .thumbnail import _font


BACKGROUND_TOP = "#07101E"
BACKGROUND_BOTTOM = "#140B21"
CARD = "#111827"
CARD_BAR = "#182235"
MUTED = "#9BA8BD"


def _background() -> Image.Image:
    top = Image.new("RGB", (VIDEO_W, VIDEO_H), BACKGROUND_TOP)
    bottom = Image.new("RGB", (VIDEO_W, VIDEO_H), BACKGROUND_BOTTOM)
    gradient = Image.linear_gradient("L").resize((VIDEO_W, VIDEO_H))
    canvas = Image.composite(bottom, top, gradient).convert("RGBA")
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    draw.ellipse((-260, -360, 760, 660), fill=(31, 174, 255, 35))
    draw.ellipse((1390, 650, 2240, 1440), fill=(170, 83, 255, 32))
    return Image.alpha_composite(canvas, glow.filter(ImageFilter.GaussianBlur(90)))


def _short_source(label: str) -> str:
    clean = " ".join(label.split()).strip()
    return clean[:54] + ("…" if len(clean) > 54 else "")


def _map_region(annotation: VisualAnnotation, image_box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    left, top, right, bottom = image_box
    width, height = right - left, bottom - top
    x1 = round(left + annotation.x * width)
    y1 = round(top + annotation.y * height)
    x2 = round(left + (annotation.x + annotation.width) * width)
    y2 = round(top + (annotation.y + annotation.height) * height)
    return x1, y1, x2, y2


def _draw_annotation(canvas: Image.Image, annotation: VisualAnnotation, image_box: tuple[int, int, int, int]) -> None:
    if annotation.style == "cursor":
        # The animated editorial cursor is composited later; never bake a box or label into the page.
        return
    region = _map_region(annotation, image_box)
    x1, y1, x2, y2 = region
    color = "#B84D45" if annotation.style == "underline" else annotation.color
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    draw = ImageDraw.Draw(canvas)

    if annotation.style == "spotlight":
        shade = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shade_draw = ImageDraw.Draw(shade)
        shade_draw.rectangle(image_box, fill=(2, 6, 14, 145))
        hole = Image.new("L", canvas.size, 0)
        hole_draw = ImageDraw.Draw(hole)
        hole_draw.rounded_rectangle((x1 - 12, y1 - 12, x2 + 12, y2 + 12), radius=22, fill=255)
        feather = hole.filter(ImageFilter.GaussianBlur(12))
        shade.putalpha(ImageOps.invert(feather).point(lambda value: round(value * 0.57)))
        canvas.alpha_composite(shade)
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((x1 - 7, y1 - 7, x2 + 7, y2 + 7), radius=18, outline=color, width=6)
    elif annotation.style == "underline":
        # The underline is drawn as a thin left-to-right animation in render_v2.
        pass
    elif annotation.style == "arrow":
        target_x = round((x1 + x2) / 2)
        target_y = round((y1 + y2) / 2)
        direction = -1 if target_x > (image_box[0] + image_box[2]) / 2 else 1
        tail_x = max(image_box[0] + 40, min(image_box[2] - 40, target_x - direction * 115))
        tail_y = max(image_box[1] + 45, target_y - 78)
        glow_draw.line((tail_x, tail_y, target_x, target_y), fill=color, width=15)
        canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(12)))
        draw = ImageDraw.Draw(canvas)
        draw.line((tail_x, tail_y, target_x, target_y), fill=color, width=6)
        angle = math.atan2(target_y - tail_y, target_x - tail_x)
        head = 18
        wing = 0.58
        points = [
            (target_x, target_y),
            (target_x - head * math.cos(angle - wing), target_y - head * math.sin(angle - wing)),
            (target_x - head * math.cos(angle + wing), target_y - head * math.sin(angle + wing)),
        ]
        draw.polygon(points, fill=color)
    else:
        pad = 9
        glow_draw.rounded_rectangle(
            (x1 - pad, y1 - pad, x2 + pad, y2 + pad), radius=20, outline=color, width=18,
        )
        canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(16)))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            (x1 - pad, y1 - pad, x2 + pad, y2 + pad), radius=20, outline=color, width=6,
        )
        if annotation.style == "callout":
            dot_x = min(image_box[2] - 20, x2 + 28)
            dot_y = max(image_box[1] + 20, y1 - 20)
            draw.line((x2 + 8, y1, dot_x, dot_y), fill=color, width=5)
            draw.ellipse((dot_x - 9, dot_y - 9, dot_x + 9, dot_y + 9), fill=color)

    if annotation.label:
        label = annotation.label.upper()
        font = _font(25)
        bounds = draw.textbbox((0, 0), label, font=font)
        width = bounds[2] - bounds[0]
        label_x = max(image_box[0] + 14, min(x1, image_box[2] - width - 46))
        label_y = max(image_box[1] + 14, y1 - 54)
        draw.rounded_rectangle(
            (label_x, label_y, label_x + width + 30, label_y + 42), radius=18,
            fill=(5, 12, 23, 230), outline=color, width=2,
        )
        draw.text((label_x + 15, label_y + 7), label, font=font, fill="white")


def prepare_editorial_screenshot(
    source: Path,
    shot: Shot,
    destination: Path,
    *,
    source_label: str = "",
) -> Path:
    """Place a captured source in a clean 16:9 evidence card and apply semantic emphasis."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas = _background()
    card_box = (145, 55, 1775, 1025)
    content_box = (160, 125, 1760, 1025)

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (card_box[0] + 10, card_box[1] + 18, card_box[2] + 10, card_box[3] + 18),
        radius=34, fill=(0, 0, 0, 185),
    )
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(28)))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(card_box, radius=34, fill=CARD, outline=(95, 117, 153, 130), width=2)
    draw.rounded_rectangle((145, 55, 1775, 146), radius=34, fill=CARD_BAR)
    draw.rectangle((145, 112, 1775, 146), fill=CARD_BAR)
    for index, fill in enumerate(("#FF6B73", "#FFC861", "#63D69B")):
        x = 184 + index * 34
        draw.ellipse((x, 86, x + 16, 102), fill=fill)
    draw.text((300, 78), _short_source(source_label or "Editorial source"), font=_font(25), fill=MUTED)
    chip = "SOURCE EVIDENCE"
    chip_font = _font(21)
    chip_bounds = draw.textbbox((0, 0), chip, font=chip_font)
    chip_width = chip_bounds[2] - chip_bounds[0]
    draw.rounded_rectangle((1535 - chip_width, 76, 1569, 113), radius=16, fill="#25334A")
    draw.text((1552 - chip_width, 83), chip, font=chip_font, fill="#D8E4F6")

    with Image.open(source) as opened:
        original = ImageOps.exif_transpose(opened).convert("RGB")
    contained = ImageOps.contain(
        original,
        (content_box[2] - content_box[0], content_box[3] - content_box[1]),
        Image.Resampling.LANCZOS,
    )
    paste_x = content_box[0] + (content_box[2] - content_box[0] - contained.width) // 2
    paste_y = content_box[1] + (content_box[3] - content_box[1] - contained.height) // 2
    image_box = (paste_x, paste_y, paste_x + contained.width, paste_y + contained.height)
    canvas.paste(contained.convert("RGBA"), (paste_x, paste_y))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle(content_box, outline=(52, 67, 91, 180), width=2)
    for annotation in shot.annotations[:2]:
        _draw_annotation(canvas, annotation, image_box)

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((145, 55, 159, 1025), radius=7, fill="#65D6FF")
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(destination, quality=94)
    return destination
