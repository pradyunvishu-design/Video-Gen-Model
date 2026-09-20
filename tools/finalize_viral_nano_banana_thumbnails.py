"""Composite exact identity assets and headlines over selected Nano Banana plates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from pipeline.brand_assets import DEFAULT_BRAND_ROOT, resolve_brand_assets
from pipeline.thumbnail import _load_brand_image


ROOT = Path("output/thumbnails/viral_topics_aug_2026/nano_banana_remake")
FINAL = ROOT / "final"
CACHE = FINAL / ".brand-cache"
FONT_IMPACT = Path("C:/Windows/Fonts/impact.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/arialbd.ttf")


def font(size: int, *, impact: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_IMPACT if impact else FONT_BOLD), size)


def fit_text(draw: ImageDraw.ImageDraw, text: str, width: int, start: int, minimum: int = 44) -> ImageFont.FreeTypeFont:
    for size in range(start, minimum - 1, -2):
        candidate = font(size)
        if draw.textbbox((0, 0), text, font=candidate, stroke_width=2)[2] <= width:
            return candidate
    return font(minimum)


def plate(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image = ImageOps.fit(image, (1280, 720), method=Image.Resampling.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.06)
    image = ImageEnhance.Color(image).enhance(1.04)
    return image.convert("RGBA")


def exact_logo(label: str, color: str, maximum: tuple[int, int]) -> tuple[Image.Image, dict]:
    record = resolve_brand_assets([label], brand_root=DEFAULT_BRAND_ROOT)[0]
    mark = _load_brand_image(record, CACHE).convert("RGBA")
    mark.thumbnail(maximum, Image.Resampling.LANCZOS)
    alpha = mark.getchannel("A")
    result = Image.new("RGBA", mark.size, color)
    result.putalpha(alpha)
    identity = {
        "key": record["key"],
        "display_name": record["display_name"],
        "asset_path": str(Path(record["asset_path"]).resolve()),
        "asset_sha256": record["asset_sha256"],
        "official_source_url": record["official_source_url"],
        "generated": False,
    }
    return result, identity


def logo_badge(canvas: Image.Image, label: str, center: tuple[int, int], diameter: int, *,
               fill: str, logo_color: str, outline: str, logo_scale: float = 0.66) -> dict:
    x, y = center
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    shadow_box = (x - diameter // 2 + 7, y - diameter // 2 + 10, x + diameter // 2 + 7, y + diameter // 2 + 10)
    draw.ellipse(shadow_box, fill=(0, 0, 0, 150))
    layer = layer.filter(ImageFilter.GaussianBlur(8))
    canvas.alpha_composite(layer)
    draw = ImageDraw.Draw(canvas, "RGBA")
    box = (x - diameter // 2, y - diameter // 2, x + diameter // 2, y + diameter // 2)
    draw.ellipse(box, fill=fill, outline=outline, width=max(3, diameter // 28))
    mark, identity = exact_logo(label, logo_color, (round(diameter * logo_scale), round(diameter * logo_scale)))
    canvas.alpha_composite(mark, (x - mark.width // 2, y - mark.height // 2))
    return identity


def gpt_thumbnail() -> tuple[Image.Image, dict]:
    canvas = plate(ROOT / "gpt56_speed" / "plate_0.png")
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.text((48, 47), "GPT-5.6", font=fit_text(draw, "GPT-5.6", 445, 100), fill="#F7F4EA", stroke_width=3, stroke_fill="#0C0F12")
    draw.rounded_rectangle((45, 151, 397, 330), radius=12, fill="#E8F51B")
    draw.text((65, 140), "14X", font=fit_text(draw, "14X", 315, 188), fill="#0C0F12")
    draw.text((49, 340), "FASTER?", font=fit_text(draw, "FASTER?", 430, 112), fill="#FFFFFF", stroke_width=4, stroke_fill="#0C0F12")
    draw.rounded_rectangle((51, 484, 316, 531), radius=16, fill=(12, 15, 18, 205), outline="#E8F51B", width=2)
    draw.text((72, 494), "ULTRAFAST MODE", font=font(24, impact=False), fill="#F7F4EA")
    identity = logo_badge(canvas, "OpenAI", (1017, 480), 132, fill="#F4F1E9", logo_color="#111318", outline="#E8F51B")
    return canvas, identity


def github_thumbnail() -> tuple[Image.Image, dict]:
    canvas = plate(ROOT / "github_models_retired" / "plate_1.png")
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.text((46, 48), "GITHUB", font=fit_text(draw, "GITHUB", 390, 90), fill="#FFFFFF", stroke_width=3, stroke_fill="#111318")
    draw.text((43, 140), "MODELS", font=fit_text(draw, "MODELS", 425, 118), fill="#FFFFFF", stroke_width=3, stroke_fill="#111318")
    draw.rounded_rectangle((43, 275, 428, 397), radius=10, fill="#F04444")
    draw.text((61, 274), "ARE GONE", font=fit_text(draw, "ARE GONE", 348, 92), fill="#111318")
    draw.line((64, 450, 340, 450), fill="#F04444", width=7)
    draw.polygon(((340, 450), (313, 434), (313, 466)), fill="#F04444")
    identity = logo_badge(canvas, "GitHub", (1051, 521), 132, fill="#111318", logo_color="#FFFFFF", outline="#FFFFFF")
    return canvas, identity


def claude_thumbnail() -> tuple[Image.Image, dict]:
    canvas = plate(ROOT / "claude_tests_chips" / "plate_1.png")
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.text((47, 46), "CLAUDE", font=fit_text(draw, "CLAUDE", 390, 91), fill="#F6F0E7", stroke_width=3, stroke_fill="#171A1F")
    draw.rounded_rectangle((45, 151, 384, 279), radius=11, fill="#D97757")
    draw.text((64, 145), "TESTS", font=fit_text(draw, "TESTS", 303, 113), fill="#111318")
    draw.text((46, 291), "CHIPS", font=fit_text(draw, "CHIPS", 398, 134), fill="#FFFFFF", stroke_width=4, stroke_fill="#171A1F")
    draw.rounded_rectangle((49, 453, 357, 503), radius=16, fill=(17, 19, 23, 220), outline="#D97757", width=2)
    draw.text((72, 463), "FROM CODE TO SILICON", font=font(23, impact=False), fill="#F6F0E7")
    identity = logo_badge(canvas, "Claude", (963, 180), 142, fill="#F6F0E7", logo_color="#171A1F", outline="#D97757", logo_scale=0.72)
    return canvas, identity


def save_package() -> None:
    FINAL.mkdir(parents=True, exist_ok=True)
    items = [
        ("gpt56_14x_speed", gpt_thumbnail, "GPT-5.6 14X FASTER?", "gpt56_speed/plate_0.png"),
        ("github_models_gone", github_thumbnail, "GITHUB MODELS ARE GONE", "github_models_retired/plate_1.png"),
        ("claude_tests_chips", claude_thumbnail, "CLAUDE TESTS CHIPS", "claude_tests_chips/plate_1.png"),
    ]
    manifest = {
        "schema_version": "viral-thumbnail-nano-banana.v2",
        "provider": "Magic Hour",
        "model": "nano-banana-2",
        "resolution": "2k backplate / 1280x720 delivery",
        "reference_channels": ["AI LABS", "Dubibubi", "Jack Roberts", "Fireship", "Matt Wolfe", "AI Explained"],
        "reference_rule": "Reusable hierarchy and hook mechanisms only; no thumbnail composition or artwork copied.",
        "thumbnails": [],
    }
    for stem, builder, headline, source_plate in items:
        image, identity = builder()
        path = FINAL / f"{stem}.jpg"
        preview = FINAL / f"{stem}_320x180.jpg"
        image.convert("RGB").save(path, quality=96, optimize=True, subsampling=0)
        image.convert("RGB").resize((320, 180), Image.Resampling.LANCZOS).save(preview, quality=92, subsampling=0)
        manifest["thumbnails"].append({
            "headline": headline,
            "path": str(path.resolve()),
            "mobile_preview": str(preview.resolve()),
            "source_plate": str((ROOT / source_plate).resolve()),
            "identity": identity,
            "master_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "human_review_required": True,
        })
    (FINAL / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    save_package()
