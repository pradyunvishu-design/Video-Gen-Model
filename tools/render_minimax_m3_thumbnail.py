#!/usr/bin/env python3
"""Render the source-backed MiniMax M3 YouTube thumbnail and manifest."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(r"C:\Youtube Automation for Magic hour")
OUT = ROOT / "output" / "thumbnails" / "minimax_m3"
LOGO = OUT / "minimax-logo-transparent.png"
CHART = OUT / "minimax-m3-official-hero.png"
MASTER = OUT / "minimax_m3_1m-context_v01.png"
PREVIEW = OUT / "minimax_m3_1m-context_v01_320x180.jpg"
GRAY = OUT / "minimax_m3_1m-context_v01_grayscale.jpg"
MANIFEST = OUT / "minimax_m3_manifest.json"

SCALE = 2
W, H = 1280 * SCALE, 720 * SCALE


def s(value: int | float) -> int:
    return round(value * SCALE)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf") if bold else Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\bahnschrift.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), s(size))
    return ImageFont.load_default(s(size))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def linear_gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (W, H), top)
    draw = ImageDraw.Draw(image)
    for y in range(H):
        t = y / max(H - 1, 1)
        color = tuple(round(top[index] * (1 - t) + bottom[index] * t) for index in range(3))
        draw.line((0, y, W, y), fill=color)
    return image.convert("RGBA")


def add_ambient_light(canvas: Image.Image) -> None:
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    draw.ellipse((s(720), s(-150), s(1430), s(560)), fill=(255, 55, 105, 92))
    draw.ellipse((s(-260), s(430), s(450), s(1040)), fill=(255, 116, 64, 38))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s(105))))


def add_grid(canvas: Image.Image) -> None:
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for x in range(s(0), W, s(64)):
        draw.line((x, 0, x, H), fill=(255, 255, 255, 10), width=s(1))
    for y in range(s(0), H, s(64)):
        draw.line((0, y, W, y), fill=(255, 255, 255, 8), width=s(1))
    canvas.alpha_composite(overlay)


def paste_with_shadow(canvas: Image.Image, subject: Image.Image, xy: tuple[int, int], blur: int = 20) -> None:
    x, y = map(s, xy)
    alpha = subject.getchannel("A")
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    colored = Image.new("RGBA", subject.size, (255, 55, 103, 0))
    colored.putalpha(alpha.filter(ImageFilter.GaussianBlur(s(blur))))
    shadow.alpha_composite(colored, (x, y + s(10)))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(subject, (x, y))


def fit_logo(max_width: int, max_height: int) -> Image.Image:
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((s(max_width), s(max_height)), Image.Resampling.LANCZOS)
    return logo


def make_receipt() -> Image.Image:
    source = Image.open(CHART).convert("RGB")
    crop = source.crop((35, 35, 855, 445))
    crop = ImageOps.fit(crop, (s(448), s(206)), method=Image.Resampling.LANCZOS)
    card = Image.new("RGBA", (s(484), s(260)), (247, 246, 242, 255))
    card.paste(crop, (s(18), s(34)))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=s(20), outline=(255, 255, 255, 150), width=s(2))
    draw.text((s(20), s(7)), "OFFICIAL M3 RESULTS", font=font(16, True), fill=(26, 24, 28, 255))
    draw.text((s(462), s(8)), "01", anchor="ra", font=font(14, True), fill=(255, 63, 103, 255))
    return card.rotate(-2.2, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(0, 0, 0, 0))


def draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int]) -> None:
    x1, y1 = map(s, start)
    x2, y2 = map(s, end)
    color = (255, 255, 255, 210)
    draw.line((x1, y1, x2, y2), fill=color, width=s(4))
    angle = math.atan2(y2 - y1, x2 - x1)
    length = s(13)
    for offset in (2.55, -2.55):
        draw.line(
            (x2, y2, x2 + length * math.cos(angle + offset), y2 + length * math.sin(angle + offset)),
            fill=color,
            width=s(4),
        )


def render() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not LOGO.is_file() or not CHART.is_file():
        raise FileNotFoundError("Official MiniMax source assets are missing")

    canvas = linear_gradient((14, 14, 18), (28, 15, 21))
    add_ambient_light(canvas)
    add_grid(canvas)
    draw = ImageDraw.Draw(canvas)

    # Top identifiers.
    draw.rounded_rectangle((s(64), s(48), s(260), s(90)), radius=s(21), fill=(246, 245, 240, 255))
    draw.ellipse((s(79), s(62), s(91), s(74)), fill=(255, 59, 104, 255))
    draw.text((s(103), s(58)), "MINIMAX M3", font=font(18, True), fill=(19, 18, 21, 255))
    draw.rounded_rectangle((s(998), s(48), s(1216), s(90)), radius=s(21), outline=(255, 255, 255, 70), width=s(2))
    draw.text((s(1107), s(59)), "OPEN-WEIGHT", anchor="ma", font=font(16, True), fill=(255, 255, 255, 235))

    # Headline: cut-paper typography, one visual sentence.
    draw.text((s(58), s(126)), "1M", font=font(218, True), fill=(248, 247, 244, 255), stroke_width=s(2), stroke_fill=(248, 247, 244, 255))
    context_box = (s(60), s(365), s(612), s(492))
    draw.rounded_rectangle(context_box, radius=s(8), fill=(255, 65, 103, 255))
    draw.text((s(82), s(373)), "CONTEXT", font=font(96, True), fill=(15, 14, 18, 255))
    draw.text((s(66), s(520)), "NATIVE IMAGE + VIDEO  /  COMPUTER USE", font=font(20, True), fill=(224, 220, 222, 230))
    draw.line((s(66), s(560), s(600), s(560)), fill=(255, 255, 255, 42), width=s(2))
    draw.text((s(66), s(577)), "ONE MODEL. THREE FRONTIER CAPABILITIES.", font=font(22, True), fill=(255, 117, 71, 255))

    # Right focal cluster: exact logo inside a restrained context-window motif.
    arc_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    arc = ImageDraw.Draw(arc_layer)
    center = (s(940), s(285))
    for index, radius in enumerate((105, 145, 185, 225)):
        alpha = 80 - index * 13
        arc.arc(
            (center[0] - s(radius), center[1] - s(radius), center[0] + s(radius), center[1] + s(radius)),
            start=205,
            end=515,
            fill=(255, 255, 255, alpha),
            width=s(2),
        )
    canvas.alpha_composite(arc_layer)

    logo = fit_logo(320, 275)
    logo_x = 940 - round(logo.width / SCALE / 2)
    logo_y = 285 - round(logo.height / SCALE / 2)
    paste_with_shadow(canvas, logo, (logo_x, logo_y), blur=22)

    # Source-backed benchmark receipt.
    receipt = make_receipt()
    receipt_x, receipt_y = s(744), s(426)
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_card = Image.new("RGBA", receipt.size, (0, 0, 0, 170))
    shadow.alpha_composite(shadow_card.filter(ImageFilter.GaussianBlur(s(18))), (receipt_x + s(12), receipt_y + s(16)))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(receipt, (receipt_x, receipt_y))

    draw = ImageDraw.Draw(canvas)
    draw.text((s(1088), s(411)), "REAL BENCHMARKS", anchor="ma", font=font(15, True), fill=(255, 255, 255, 205))
    draw_arrow(draw, (1088, 430), (1092, 447))

    final = canvas.convert("RGB").resize((1280, 720), Image.Resampling.LANCZOS)
    final.save(MASTER, "PNG", optimize=True)
    final.resize((320, 180), Image.Resampling.LANCZOS).save(PREVIEW, "JPEG", quality=94, optimize=True)
    ImageOps.grayscale(final).save(GRAY, "JPEG", quality=92, optimize=True)

    manifest = {
        "topic": "MiniMax M3 launch",
        "language_policy": "English-language sources only",
        "headline": "1M CONTEXT",
        "hook_strategy": "specific supported scale + open-weight consequence",
        "style_mode": "cut-paper typographic reveal + editorial evidence receipt",
        "represented_companies": ["minimax"],
        "resolved_brand_assets": [
            {
                "key": "minimax",
                "asset_path": str(LOGO.resolve()),
                "official_source_url": "https://huggingface.co/spaces/MiniMaxAI/MiniMax-M1/tree/main/assets",
                "generated": "false",
                "cutout_method": "existing-alpha",
                "sha256": sha256(LOGO),
            }
        ],
        "evidence": [
            {
                "id": "E1",
                "claim": "MiniMax M3 supports a context window of up to 1 million tokens.",
                "source_language": "English",
                "source_url": "https://www.minimax.io/blog/minimax-m3",
            },
            {
                "id": "E2",
                "claim": "MiniMax describes M3 as an open-weight model with native image/video input and computer use.",
                "source_language": "English",
                "source_url": "https://www.minimax.io/blog/minimax-m3",
            },
        ],
        "source_assets": [
            {
                "path": str(CHART.resolve()),
                "source_language": "English",
                "official_source_url": "https://filecdn.minimax.chat/public/20260619-222405-1781879125997.png",
                "sha256": sha256(CHART),
            }
        ],
        "candidates": [
            {
                "path": str(MASTER.resolve()),
                "preview": str(PREVIEW.resolve()),
                "brand_placements": [{"key": "minimax", "bounds": [778, 124, 1102, 446]}],
                "proof_asset_ids": ["E1", "E2"],
                "scores": {
                    "instant_comprehension": 5,
                    "curiosity_tension": 4,
                    "identity_accuracy": 5,
                    "script_fidelity": 5,
                    "mobile_legibility": 5,
                    "source_authenticity": 5,
                    "originality": 4,
                },
            }
        ],
        "recommended_candidate": MASTER.name,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(MASTER)


if __name__ == "__main__":
    render()
