"""Create four source-first MiniMax H3 thumbnail candidates."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from playwright.sync_api import sync_playwright

from pipeline.config import LOCAL_FFMPEG_BIN, PROJECT_ROOT


RUN_DIR = PROJECT_ROOT / "output" / "minimax_h3_10m"
MEDIA_DIR = RUN_DIR / "official_media"
OUT_DIR = RUN_DIR / "thumbnails"
FFMPEG = str(LOCAL_FFMPEG_BIN / "ffmpeg.exe") if (LOCAL_FFMPEG_BIN / "ffmpeg.exe").is_file() else "ffmpeg"
FONT_BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
FONT_REGULAR = Path("C:/Windows/Fonts/arial.ttf")
BG = "#080808"
WHITE = "#f8f5ee"
SLATE = "#83938C"
RED = "#ee4d55"
CORAL = "#ff6b5f"


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frame(video: str, second: float = 3.0) -> Path:
    source = MEDIA_DIR / f"{video}.mp4"
    destination = OUT_DIR / "frames" / f"{video}.jpg"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file():
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-ss", str(second), "-i", str(source), "-frames:v", "1", "-q:v", "2", str(destination)], check=True)
    return destination


def _logo() -> Path:
    destination = OUT_DIR / "minimax-logo.png"
    if destination.is_file():
        return destination
    svg = (PROJECT_ROOT / "remotion" / "public" / "brands" / "minimax.svg").read_text(encoding="utf-8")
    html = f"<html><style>html,body{{margin:0;width:240px;height:240px;background:transparent}}svg{{position:absolute;inset:20px;width:200px;height:200px;fill:#fff}}</style><body>{svg}</body></html>"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 240, "height": 240})
        page.set_content(html)
        page.screenshot(path=str(destination), omit_background=True)
        browser.close()
    return destination


def _rounded(image: Image.Image, size: tuple[int, int], radius: int = 30) -> Image.Image:
    fitted = ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    fitted.putalpha(mask)
    return fitted


def _paste_shadow(canvas: Image.Image, card: Image.Image, xy: tuple[int, int]) -> None:
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    alpha = card.getchannel("A").filter(ImageFilter.GaussianBlur(22))
    shadow.paste((0, 0, 0, 185), (xy[0] + 12, xy[1] + 18), alpha)
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(card, xy)


def _brand_lockup(canvas: Image.Image, logo: Image.Image, xy: tuple[int, int], dark: bool = True) -> None:
    draw = ImageDraw.Draw(canvas)
    x, y = xy
    fill = (18, 18, 18, 235) if dark else (249, 247, 240, 245)
    draw.rounded_rectangle((x, y, x + 245, y + 76), radius=18, fill=fill, outline=(255, 255, 255, 45), width=2)
    mark = logo.resize((52, 52), Image.Resampling.LANCZOS)
    if not dark:
        alpha = mark.getchannel("A")
        black = Image.new("RGBA", mark.size, (10, 10, 10, 255))
        black.putalpha(alpha)
        mark = black
    canvas.alpha_composite(mark, (x + 14, y + 12))
    draw.text((x + 78, y + 14), "MiniMax", font=_font(25), fill=WHITE if dark else "#0b0b0b")
    draw.text((x + 80, y + 44), "H3", font=_font(17), fill=SLATE if dark else "#d13d42")


def _save(canvas: Image.Image, name: str) -> tuple[str, str]:
    master = OUT_DIR / f"{name}.png"
    preview = OUT_DIR / f"{name}_320x180.png"
    canvas.convert("RGB").save(master, quality=96)
    canvas.convert("RGB").resize((320, 180), Image.Resampling.LANCZOS).save(preview, quality=94)
    return str(master), str(preview)


def _candidate_collage(frames: list[Image.Image], logo: Image.Image) -> tuple[str, str]:
    canvas = Image.new("RGBA", (1280, 720), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((58, 52), "AI VIDEO", font=_font(78), fill=WHITE)
    draw.rectangle((52, 145, 520, 250), fill=SLATE)
    draw.text((65, 150), "WENT LOCAL", font=_font(70), fill="#080808")
    draw.text((60, 282), "The cloud just lost its monopoly.", font=_font(28, False), fill="#c8c5be")
    for index, image in enumerate(frames[:3]):
        card = _rounded(image, (260, 480), 28)
        _paste_shadow(canvas, card, (540 + index * 220, 130 + (index % 2) * 38))
    _brand_lockup(canvas, logo, (58, 566))
    return _save(canvas, "h3_editorial_collage_v01")


def _candidate_resolution(frames: list[Image.Image], logo: Image.Image) -> tuple[str, str]:
    canvas = Image.new("RGBA", (1280, 720), "#efe9dc")
    draw = ImageDraw.Draw(canvas)
    left = _rounded(frames[3], (560, 420), 28)
    right = _rounded(frames[4], (560, 420), 28)
    _paste_shadow(canvas, left, (52, 220))
    _paste_shadow(canvas, right, (668, 220))
    draw.rounded_rectangle((490, 180, 790, 258), radius=16, fill="#0a0a0a")
    draw.text((525, 190), "768P  →  2K", font=_font(43), fill=WHITE)
    draw.text((50, 35), "LOCAL VIDEO", font=_font(73), fill="#101010")
    draw.rectangle((530, 45, 1040, 137), fill=RED)
    draw.text((549, 49), "GOT SERIOUS", font=_font(65), fill=WHITE)
    _brand_lockup(canvas, logo, (1020, 32), dark=True)
    return _save(canvas, "h3_resolution_receipt_v01")


def _candidate_escape(frames: list[Image.Image], logo: Image.Image) -> tuple[str, str]:
    canvas = Image.new("RGBA", (1280, 720), "#0b0b0c")
    draw = ImageDraw.Draw(canvas)
    card = _rounded(frames[1], (650, 650), 40)
    _paste_shadow(canvas, card, (600, 36))
    draw.text((55, 55), "AI VIDEO", font=_font(76), fill=WHITE)
    draw.text((55, 142), "ESCAPED", font=_font(94), fill=SLATE)
    draw.text((55, 240), "THE CLOUD", font=_font(76), fill=WHITE)
    draw.line((80, 360, 500, 360), fill=RED, width=7)
    draw.polygon([(500, 360), (468, 340), (468, 380)], fill=RED)
    draw.rounded_rectangle((65, 395, 480, 585), radius=22, fill="#171717", outline="#555", width=3)
    draw.rectangle((105, 432, 440, 533), fill="#242424")
    draw.text((157, 457), "YOUR PC", font=_font(52), fill=WHITE)
    _brand_lockup(canvas, logo, (55, 612))
    return _save(canvas, "h3_cloud_escape_v01")


def _candidate_hardware(frames: list[Image.Image], logo: Image.Image) -> tuple[str, str]:
    canvas = Image.new("RGBA", (1280, 720), "#111111")
    draw = ImageDraw.Draw(canvas)
    card = _rounded(frames[2], (610, 610), 36)
    _paste_shadow(canvas, card, (635, 70))
    draw.text((55, 48), "RUNS ON", font=_font(77), fill=WHITE)
    draw.rectangle((50, 143, 578, 254), fill=SLATE)
    draw.text((66, 150), "A 3060?", font=_font(78), fill="#080808")
    draw.text((58, 294), "42.5 GB", font=_font(74), fill=CORAL)
    draw.text((60, 372), "optimized footprint", font=_font(28, False), fill="#c8c5be")
    draw.text((58, 435), "Possible. Not painless.", font=_font(34), fill=WHITE)
    _brand_lockup(canvas, logo, (55, 570))
    return _save(canvas, "h3_hardware_question_v01")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logo_path = _logo()
    logo = Image.open(logo_path).convert("RGBA")
    frame_paths = [_frame(name) for name in ("direct_2k", "t2va_2k", "r2va_2k", "direct_768", "i2va_direct_2k")]
    frames = [Image.open(path).convert("RGB") for path in frame_paths]
    outputs = [
        _candidate_collage(frames, logo),
        _candidate_resolution(frames, logo),
        _candidate_escape(frames, logo),
        _candidate_hardware(frames, logo),
    ]
    manifest = {
        "schema_version": 1,
        "episode_id": "episode_20260818_minimax_h3_deep_dive",
        "headline_options": ["AI VIDEO WENT LOCAL", "LOCAL VIDEO GOT SERIOUS", "AI VIDEO ESCAPED THE CLOUD", "RUNS ON A 3060?"],
        "recommended": "h3_editorial_collage_v01.png",
        "reason": "The official-output collage delivers the episode promise without overclaiming performance or inventing imagery.",
        "identity": {
            "company": "MiniMax",
            "asset": str(PROJECT_ROOT / "remotion" / "public" / "brands" / "minimax.svg"),
            "source_url": "https://simpleicons.org/?q=minimax",
            "sha256": _sha(PROJECT_ROOT / "remotion" / "public" / "brands" / "minimax.svg"),
        },
        "evidence": [{"asset": str(path), "source_url": "https://huggingface.co/MiniMaxAI/MiniMax-H3/tree/main/assets", "owner": "MiniMaxAI"} for path in frame_paths],
        "candidates": [{"master": master, "preview": preview} for master, preview in outputs],
        "human_review_required": True,
    }
    (OUT_DIR / "thumbnail_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
