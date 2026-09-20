"""Build the selected source-first Gemini/ComfyUI thumbnail composition."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from pipeline.brand_assets import resolve_brand_assets
from pipeline.thumbnail import _load_brand_image


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "data" / "episodes" / "episode_20260901_03"
OUT = EPISODE / "thumbnails_clean_v2"
SOURCE = EPISODE / "captures" / "verified_source_frames" / "google-editorial-03-shot_010.png"


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/Arial.ttf"),
    ):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    raise FileNotFoundError("Arial is required for the thumbnail master")


def fit_logo(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    logo = image.convert("RGBA")
    logo.thumbnail(box, Image.Resampling.LANCZOS)
    return logo


def paste_center(base: Image.Image, logo: Image.Image, center: tuple[int, int]) -> tuple[int, int, int, int]:
    x = center[0] - logo.width // 2
    y = center[1] - logo.height // 2
    base.alpha_composite(logo, (x, y))
    return (x, y, x + logo.width, y + logo.height)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cache = (OUT / ".brand-cache").resolve()
    records = resolve_brand_assets(["gemini", "comfyui"])
    logos = {record["key"]: _load_brand_image(record, cache) for record in records}

    width, height = 1280, 720
    base = Image.new("RGBA", (width, height), "#111413")
    draw = ImageDraw.Draw(base)

    # Quiet studio-paper depth, with no synthetic glow or decorative UI cards.
    draw.rectangle((0, 0, 690, height), fill="#141716")
    draw.rectangle((690, 0, width, height), fill="#E8E5DD")
    draw.rectangle((686, 0, 692, height), fill="#7D8984")
    draw.ellipse((850, -220, 1420, 350), fill="#D7DBD8")
    draw.ellipse((900, 440, 1460, 950), fill="#D9CFC4")

    # Headline: one supported promise, two clean lines, one clay highlight.
    top_headline = font(94)
    lower_headline = font(102)
    draw.text((72, 108), "FIVE TOOLS.", font=top_headline, fill="#F4F3EE", stroke_width=1, stroke_fill="#F4F3EE")
    highlight = (68, 226, 634, 358)
    draw.rounded_rectangle(highlight, radius=18, fill="#C96F50")
    draw.text((92, 236), "ONE NODE.", font=lower_headline, fill="#111413")
    draw.text((76, 615), "GEMINI VIDEO OMNI", font=font(28), fill="#9EA7A3")

    # A single physically grounded node object. Five input ports converge on
    # one real ComfyUI identity and one authentic Gemini output crop.
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((748, 116, 1198, 628), radius=42, fill=(0, 0, 0, 125))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    base.alpha_composite(shadow)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((730, 92, 1180, 604), radius=40, fill="#171A19", outline="#3F4744", width=4)
    draw.rounded_rectangle((752, 116, 1158, 180), radius=20, fill="#222725")

    draw.rounded_rectangle((762, 123, 990, 173), radius=16, fill="#F4F3EE")
    gemini = fit_logo(logos["gemini"], (202, 42))
    gemini_bounds = paste_center(base, gemini, (876, 148))
    comfy = fit_logo(logos["comfyui"], (98, 98))
    comfy_bounds = paste_center(base, comfy, (1092, 148))
    draw = ImageDraw.Draw(base)

    port_y = [246, 308, 370, 432, 494]
    port_colors = ["#6D8ED8", "#7EA39B", "#C96F50", "#A59D86", "#8B7F9C"]
    join_x, join_y = 878, 370
    for y, color in zip(port_y, port_colors):
        draw.ellipse((766, y - 9, 784, y + 9), fill=color)
        draw.line((784, y, 846, y, join_x, join_y), fill="#7D8984", width=4, joint="curve")
    draw.ellipse((join_x - 12, join_y - 12, join_x + 12, join_y + 12), fill="#F4F3EE")
    draw.line((join_x + 12, join_y, 936, join_y), fill="#F4F3EE", width=5)
    draw.polygon([(936, 358), (954, 370), (936, 382)], fill="#F4F3EE")

    source = Image.open(SOURCE).convert("RGB")
    crop = ImageOps.fit(source, (180, 250), method=Image.Resampling.LANCZOS, centering=(0.48, 0.30))
    crop = ImageEnhance.Contrast(crop).enhance(1.05)
    crop = ImageEnhance.Color(crop).enhance(0.82)
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, crop.width, crop.height), radius=24, fill=255)
    base.paste(crop, (970, 222), mask)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((968, 220, 1152, 474), radius=26, outline="#F4F3EE", width=4)
    draw.rounded_rectangle((956, 502, 1162, 558), radius=18, fill="#F4F3EE")
    draw.text((982, 513), "5 → 1", font=font(30), fill="#111413")

    master = OUT / "gemini_comfyui_five_tools_one_node_v01.png"
    preview = OUT / "mobile-previews" / "gemini_comfyui_five_tools_one_node_v01_320x180.jpg"
    preview.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(master, quality=96)
    base.convert("RGB").resize((320, 180), Image.Resampling.LANCZOS).save(preview, quality=94)

    manifest = {
        "schema_version": "thumbnail-selected.v1",
        "headline": "FIVE TOOLS. ONE NODE.",
        "visual_sentence": "Five documented Gemini video tasks converge into one ComfyUI node.",
        "style_mode": "mechanism_handoff",
        "master": str(master),
        "mobile_preview": str(preview),
        "source_asset": str(SOURCE),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "evidence_ids": ["src_90ba20dc32b5", "src_09022b345bc4"],
        "brand_assets": records,
        "represented_companies": ["gemini", "comfyui"],
        "resolved_brand_assets": records,
        "brand_placements": {
            "gemini": gemini_bounds,
            "comfyui": comfy_bounds,
        },
        "candidates": [{
            "path": str(master),
            "brand_placements": [
                {"key": "gemini", "bounds": gemini_bounds},
                {"key": "comfyui", "bounds": comfy_bounds},
            ],
        }],
        "generated_pixels": False,
        "publishing_enabled": False,
        "human_review_required": True,
    }
    (OUT / "selected_thumbnail_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
