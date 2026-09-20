"""Create identity-first, source-backed 1280x720 AI-news thumbnails.

Every represented company is composited from an exact, provenance-tracked local
logo or documented official mascot.  Missing identity assets stop generation;
the renderer never invents a mark, mascot, product UI, or glossy AI-art stand-in.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, ImageStat

from .brand_assets import DEFAULT_BRAND_ROOT, detect_brand_keys, resolve_brand_assets
from .creative_profile import ThumbnailConcept, build_thumbnail_concepts, classify_story
from .editorial_style import safe_editorial_accent
from .thumbnail_automation import build_automation_plan, generate_magic_hour_backplates


INK = "#0B0C0C"
CARD = "#181A1A"
PAPER = "#F4F3EE"
MUTED = "#A7AAA5"
SLATE = "#83938C"
MOSS = "#607457"
CLAY = "#D77A57"
BLUE = "#5576C9"
INDIGO = "#7768C9"
GENERIC_HYPE = {
    "THIS CHANGES EVERYTHING", "GAME CHANGER", "INSANE AI", "YOU WON'T BELIEVE",
    "THE FUTURE IS HERE", "BIG AI NEWS",
}


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ("C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _serif_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ("C:/Windows/Fonts/georgiaz.ttf", "C:/Windows/Fonts/timesbi.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return _font(size)


def _context_labels(text: str) -> list[str]:
    """Return neutral editorial labels, never synthetic product identities."""
    value = text.lower()
    labels = ["SOURCE", "WORKFLOW", "RESULT"]
    if any(term in value for term in ("open source", "github", "local")):
        labels[1] = "OPEN SOURCE"
    elif any(term in value for term in ("model", "agent", "coding")):
        labels[1] = "MODEL TEST"
    return labels[:2]


def _draw_context_label(draw: ImageDraw.ImageDraw, label: str, center: tuple[int, int], size: int) -> None:
    """Draw a channel-owned context tile, not a company logo or mascot."""
    color = MOSS
    cx, cy = center
    box = (cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2)
    draw.rounded_rectangle(box, radius=size // 5, fill=CARD, outline=color, width=max(4, size // 24))
    label_font = _font(max(12, size // (8 if len(label) > 9 else 6)))
    label_box = draw.textbbox((0, 0), label, font=label_font)
    draw.text(
        (cx - (label_box[2] - label_box[0]) // 2, cy - (label_box[3] - label_box[1]) // 2),
        label,
        font=label_font,
        fill=PAPER,
    )


def _trim_transparency(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    bounds = alpha.getbbox()
    return rgba.crop(bounds) if bounds else rgba


def _load_brand_image(record: dict[str, str], cache_dir: Path) -> Image.Image:
    """Load an exact raster mark or rasterize SVG through the installed Chromium."""
    source = Path(record["asset_path"])
    if source.suffix.casefold() != ".svg":
        return _trim_transparency(Image.open(source))
    cache_dir.mkdir(parents=True, exist_ok=True)
    raster = cache_dir / f"{record['key']}_{record['asset_sha256'][:12]}.png"
    if not raster.is_file():
        svg = source.read_text(encoding="utf-8").replace("<?xml version=\"1.0\" encoding=\"UTF-8\"?>", "")
        html = (
            "<html><head><style>html,body{margin:0;background:transparent;}"
            "#logo{width:512px;height:512px;display:flex;align-items:center;justify-content:center;}"
            "#logo svg{width:88%;height:88%;display:block;}</style></head>"
            f"<body><div id='logo'>{svg}</div></body></html>"
        )
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            chrome_candidates = (
                Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
                Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
            )
            chrome = next((path for path in chrome_candidates if path.is_file()), None)
            if chrome is None:
                raise RuntimeError("Playwright or a local Chromium browser is required to rasterize verified SVG assets")
            html_path = raster.with_suffix(".html")
            html_path.write_text(html, encoding="utf-8")
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                [
                    str(chrome), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--window-size=512,512", "--force-device-scale-factor=2",
                    "--default-background-color=00000000", f"--screenshot={raster}",
                    html_path.resolve().as_uri(),
                ],
                check=False, capture_output=True, text=True, timeout=30,
                creationflags=creation_flags,
            )
            html_path.unlink(missing_ok=True)
            if result.returncode or not raster.is_file():
                raise RuntimeError(f"Chromium SVG rasterization failed: {result.stderr.strip()}")
        else:
            with sync_playwright() as playwright:
                try:
                    browser = playwright.chromium.launch(headless=True)
                except Exception:
                    chrome_candidates = (
                        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
                        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
                    )
                    chrome = next((path for path in chrome_candidates if path.is_file()), None)
                    if chrome is None:
                        raise RuntimeError(
                            "Playwright's bundled Chromium is unavailable and no installed Chrome/Edge browser was found"
                        )
                    browser = playwright.chromium.launch(headless=True, executable_path=str(chrome))
                page = browser.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=2)
                page.set_content(html, wait_until="load")
                page.locator("#logo").screenshot(path=str(raster), omit_background=True)
                browser.close()
    return _trim_transparency(Image.open(raster))


def _logo_background(image: Image.Image) -> str:
    rgba = image.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
    mask = rgba.getchannel("A").point(lambda value: 255 if value > 32 else 0)
    if not mask.getbbox():
        return PAPER
    mean = sum(ImageStat.Stat(rgba.convert("RGB"), mask=mask).mean) / 3
    return CARD if mean > 170 else PAPER


def _draw_brand_identity(
    base: Image.Image, brand_images: list[tuple[dict[str, str], Image.Image]], archetype: str,
) -> list[dict[str, object]]:
    """Place required identities as readable story subjects, never footer decoration."""
    if not brand_images:
        return []
    comparison = archetype in {"agent_showdown", "proof_split", "criterion_card", "claim_vs_receipt"}
    if archetype == "broken_assumption":
        slots = [(54, 390, 226), (312, 470, 142), (474, 492, 118), (610, 502, 104)][:len(brand_images)]
    elif archetype == "proof_closeup":
        slots = [(1030, 470, 184), (878, 530, 126), (748, 548, 108), (634, 558, 96)][:len(brand_images)]
    elif archetype in {"mechanism_map", "workflow_relay"}:
        slots = [(54 + index * 192, 450, 138) for index in range(len(brand_images))]
    elif archetype == "consequence_frame":
        slots = [(1022, 470, 180), (864, 530, 124), (732, 548, 106), (618, 558, 94)][:len(brand_images)]
    elif archetype == "product_plus_proof":
        slots = [(342, 408, 226), (1080, 500, 120), (936, 530, 104), (814, 546, 92)][:len(brand_images)]
    elif comparison and len(brand_images) >= 2:
        slots = [(38, 200, 154), (1088, 200, 154), (555, 370, 132), (705, 370, 132)][:len(brand_images)]
    elif archetype in {"ranked_stack", "evidence_grid", "hero_story"} and len(brand_images) >= 2:
        slots = [(560 + index * 148, 34, 126) for index in range(min(3, len(brand_images)))]
        if len(brand_images) == 4:
            slots.append((1004, 34, 126))
    elif len(brand_images) >= 2:
        slots = [(1040 - index * 150, 42, 132) for index in range(len(brand_images))]
    else:
        slots = [(1032, 42, 182)]
    placements: list[dict[str, object]] = []
    for (record, logo), (x, y, size) in zip(brand_images, slots):
        shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle((x + 10, y + 14, x + size + 10, y + size + 14), radius=34, fill=(0, 0, 0, 145))
        base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
        tile = Image.new("RGBA", (size, size), _logo_background(logo))
        tile_draw = ImageDraw.Draw(tile)
        tile_draw.rounded_rectangle((1, 1, size - 2, size - 2), radius=30, outline=safe_editorial_accent(record["accent"]), width=5)
        fitted = logo.copy()
        fitted.thumbnail((int(size * .7), int(size * .7)), Image.Resampling.LANCZOS)
        tile.alpha_composite(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
        base.alpha_composite(tile, (x, y))
        placements.append({"key": record["key"], "x": x, "y": y, "width": size, "height": size})
    if comparison and len(placements) >= 2:
        draw = ImageDraw.Draw(base)
        draw.ellipse((596, 240, 684, 328), fill=INK, outline=SLATE, width=3)
        vs_font = _font(34)
        box = draw.textbbox((0, 0), "VS", font=vs_font)
        draw.text((640 - (box[2] - box[0]) / 2, 284 - (box[3] - box[1]) / 2), "VS", font=vs_font, fill=PAPER)
    return placements


def _headline_tokens(text: str) -> list[str]:
    tokens = text.upper().split()[:5]
    return tokens or ["THE", "WEEK", "IN", "AI"]


def _highlight_index(tokens: list[str]) -> int:
    candidates = [(len(word.strip("/:-")), index) for index, word in enumerate(tokens) if word not in {"THE", "A", "AN", "IN", "TO", "OF"}]
    return max(candidates, default=(len(tokens[-1]), len(tokens) - 1))[1]


def _draw_headline(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int]) -> None:
    tokens = _headline_tokens(text)
    highlight = _highlight_index(tokens)
    left, top, right, bottom = box
    max_width = right - left
    for size in range(96, 51, -4):
        font = _font(size)
        rows: list[list[tuple[str, int]]] = [[]]
        row_width = 0
        for index, token in enumerate(tokens):
            width = draw.textbbox((0, 0), token, font=font)[2]
            gap = size // 5 if rows[-1] else 0
            if row_width + gap + width > max_width and rows[-1]:
                rows.append([])
                row_width = 0
                gap = 0
            rows[-1].append((token, index))
            row_width += gap + width
        line_height = int(size * 1.08)
        if len(rows) <= 3 and top + len(rows) * line_height <= bottom:
            break
    y = top
    for row in rows:
        x = left
        for token, index in row:
            token_box = draw.textbbox((x, y), token, font=font)
            if index == highlight:
                draw.rounded_rectangle((token_box[0] - 8, token_box[1] - 5, token_box[2] + 9, token_box[3] + 7), radius=3, fill=SLATE)
                fill = INK
            else:
                fill = PAPER
            draw.text((x, y), token, font=font, fill=fill)
            x = token_box[2] + size // 5
        y += line_height


def _proof_panel(source: Image.Image, size: tuple[int, int], angle: float) -> Image.Image:
    width, height = size
    panel = Image.new("RGBA", size, CARD)
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle((2, 2, width - 3, height - 3), radius=24, fill=CARD, outline=(244, 243, 238, 55), width=3)
    capture = ImageOps.fit(source, (width - 28, height - 58), method=Image.Resampling.LANCZOS)
    capture = ImageEnhance.Sharpness(capture).enhance(1.2)
    mask = Image.new("L", capture.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, capture.width, capture.height), radius=15, fill=255)
    panel.paste(capture, (14, 44), mask)
    for index, color in enumerate(("#FF6B73", "#FFC861", "#63D69B")):
        draw.ellipse((18 + index * 22, 16, 30 + index * 22, 28), fill=color)
    return panel.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)


def source_suitability(path: Path) -> dict:
    """Reject blank and network-block captures before they become click packaging."""
    try:
        image = Image.open(path).convert("RGB").resize((320, 180), Image.Resampling.LANCZOS)
    except (OSError, ValueError) as exc:
        return {"passed": False, "reason": f"unreadable source: {exc}"}
    red, green, blue = image.split()
    white_mask = ImageChops.multiply(
        ImageChops.multiply(red.point(lambda value: 255 if value > 235 else 0), green.point(lambda value: 255 if value > 235 else 0)),
        blue.point(lambda value: 255 if value > 235 else 0),
    )
    white_ratio = ImageStat.Stat(white_mask).mean[0] / 255
    grayscale = image.convert("L")
    entropy = grayscale.entropy()
    standard_deviation = ImageStat.Stat(grayscale).stddev[0]
    failures: list[str] = []
    if white_ratio > .95 and entropy < 1.2:
        failures.append("capture is almost entirely blank or a browser block page")
    if standard_deviation < 8:
        failures.append("capture has no usable visual structure")
    return {
        "passed": not failures,
        "failures": failures,
        "white_ratio": round(white_ratio, 4),
        "entropy": round(entropy, 4),
        "standard_deviation": round(standard_deviation, 3),
    }


def _base_canvas(index: int) -> Image.Image:
    base = Image.new("RGBA", (1280, 720), INK)
    ambient = Image.new("RGBA", base.size, (0, 0, 0, 0))
    tone = MOSS if index % 2 == 0 else "#4D372D"
    rgb = tuple(int(tone[position:position + 2], 16) for position in (1, 3, 5))
    ImageDraw.Draw(ambient).ellipse((760, -160, 1420, 620), fill=(*rgb, 44))
    return Image.alpha_composite(base, ambient.filter(ImageFilter.GaussianBlur(92)))


def _paste_proof(base: Image.Image, source: Image.Image, position: tuple[int, int], size: tuple[int, int], angle: float = 0) -> None:
    base.alpha_composite(_proof_panel(source, size, angle), position)


def _hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _paste_mark(
    base: Image.Image,
    record: dict[str, str],
    logo: Image.Image,
    center: tuple[int, int],
    size: int,
    *,
    halo: str | None = None,
) -> dict[str, object]:
    """Composite an exact transparent mark with a crisp contrast edge, never rembg."""
    fitted = _trim_transparency(logo).copy()
    fitted.thumbnail((size, size), Image.Resampling.LANCZOS)
    x = int(center[0] - fitted.width / 2)
    y = int(center[1] - fitted.height / 2)
    alpha = fitted.getchannel("A")
    shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(max(5, size // 28)))
    shadow = Image.new("RGBA", fitted.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha.point(lambda value: int(value * .48)))
    base.alpha_composite(shadow, (x + 8, y + 11))
    sample_left = max(0, x)
    sample_top = max(0, y)
    sample_right = min(base.width, x + fitted.width)
    sample_bottom = min(base.height, y + fitted.height)
    sample = base.crop((sample_left, sample_top, sample_right, sample_bottom)).convert("RGB")
    mean_luma = ImageStat.Stat(sample.convert("L")).mean[0] if sample.width and sample.height else 128
    edge_rgb = (248, 246, 239) if mean_luma < 128 else (14, 15, 16)
    filter_size = 9 if min(fitted.size) >= 120 else 5
    expanded = alpha.filter(ImageFilter.MaxFilter(filter_size))
    ring = ImageChops.subtract(expanded, alpha).point(lambda value: int(value * .82))
    outline = Image.new("RGBA", fitted.size, (*edge_rgb, 0))
    outline.putalpha(ring)
    base.alpha_composite(outline, (x, y))
    base.alpha_composite(fitted, (x, y))
    return {"key": record["key"], "x": x, "y": y, "width": fitted.width, "height": fitted.height}


def _gradient(size: tuple[int, int], left: str, right: str) -> Image.Image:
    left_rgb = _hex_rgb(left)
    right_rgb = _hex_rgb(right)
    strip = Image.new("RGB", (size[0], 1))
    pixels = strip.load()
    for x in range(size[0]):
        ratio = x / max(1, size[0] - 1)
        pixels[x, 0] = tuple(round(a + (b - a) * ratio) for a, b in zip(left_rgb, right_rgb))
    return strip.resize(size).convert("RGBA")


def _headline_outline(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    *,
    fill: str,
    stroke: str,
    accent: str,
) -> None:
    tokens = _headline_tokens(text)
    left, top, right, bottom = box
    max_width = right - left
    rows: list[str] = []
    for size in range(114, 50, -4):
        font = _font(size)
        rows = []
        current = ""
        for token in tokens:
            candidate = f"{current} {token}".strip()
            if current and draw.textbbox((0, 0), candidate, font=font, stroke_width=4)[2] > max_width:
                rows.append(current)
                current = token
            else:
                current = candidate
        if current:
            rows.append(current)
        if len(rows) <= 3 and top + len(rows) * int(size * 1.02) <= bottom:
            break
    y = top
    highlight = max((word for word in tokens if word not in {"THE", "A", "AN", "TO", "OF"}), key=len, default=tokens[-1])
    for row in rows:
        color = accent if highlight in row.split() and len(rows) > 1 else fill
        draw.text((left, y), row, font=font, fill=color, stroke_width=max(2, size // 24), stroke_fill=stroke)
        y += int(size * 1.02)


def _render_cinematic_duel(
    sources: list[Image.Image], text: str, brand_images: list[tuple[dict[str, str], Image.Image]],
    backplate: Image.Image | None = None,
) -> tuple[Image.Image, list[dict[str, object]]]:
    gradient = _gradient((1280, 720), "#09183B", "#35140A")
    base = Image.blend(ImageOps.fit(backplate, (1280, 720)).convert("RGBA"), gradient, .74) if backplate else gradient
    left = ImageOps.fit(sources[0], (640, 720), method=Image.Resampling.LANCZOS).convert("RGBA")
    right = ImageOps.fit(sources[1 % len(sources)], (640, 720), method=Image.Resampling.LANCZOS).convert("RGBA")
    left = Image.blend(left, Image.new("RGBA", left.size, "#102D78"), .38)
    right = Image.blend(right, Image.new("RGBA", right.size, "#8A2D0F"), .42)
    base.alpha_composite(left, (0, 0))
    base.alpha_composite(right, (640, 0))
    veil = Image.new("RGBA", base.size, (0, 0, 0, 0))
    vd = ImageDraw.Draw(veil)
    vd.rectangle((0, 0, 1280, 185), fill=(0, 0, 0, 205))
    vd.rectangle((0, 520, 1280, 720), fill=(0, 0, 0, 135))
    base = Image.alpha_composite(base, veil.filter(ImageFilter.GaussianBlur(12)))
    draw = ImageDraw.Draw(base)
    _headline_outline(draw, text, (54, 35, 1226, 180), fill=PAPER, stroke=INK, accent=PAPER)
    placements: list[dict[str, object]] = []
    single_product = len(brand_images) == 1
    if single_product:
        record, logo = brand_images[0]
        placements.append(_paste_mark(base, record, logo, (640, 390), 230, halo=record["accent"]))
    elif brand_images:
        centers = ((330, 390), (950, 390), (520, 520), (760, 520))
        for index, (record, logo) in enumerate(brand_images):
            placements.append(_paste_mark(base, record, logo, centers[index], 230 if index < 2 else 130, halo=record["accent"]))
    draw = ImageDraw.Draw(base)
    if single_product:
        draw.rounded_rectangle((62, 420, 282, 468), radius=10, fill=(10, 10, 12, 225), outline="#739BFF", width=3)
        draw.rounded_rectangle((998, 420, 1218, 468), radius=10, fill=(10, 10, 12, 225), outline="#F5A14A", width=3)
        draw.text((88, 431), "OPEN SOURCE", font=_font(20), fill=PAPER)
        draw.text((1027, 431), "LATEST BUILD", font=_font(20), fill=PAPER)
    else:
        draw.text((594, 326), "VS", font=_font(72), fill="#FFFFFF", stroke_width=5, stroke_fill="#131313")
    draw.rounded_rectangle((477, 610, 803, 663), radius=14, fill=(10, 10, 12, 220), outline="#F5A14A", width=3)
    label = "CODE · CHAT · AGENTS" if single_product else "SAME STORY · SAME EVIDENCE"
    label_box = draw.textbbox((0, 0), label, font=_font(21))
    draw.text((640 - (label_box[2] - label_box[0]) / 2, 625), label, font=_font(21), fill=PAPER)
    return base, placements


def _render_bold_conflict(
    sources: list[Image.Image], text: str, brand_images: list[tuple[dict[str, str], Image.Image]],
    backplate: Image.Image | None = None,
) -> tuple[Image.Image, list[dict[str, object]]]:
    gradient = _gradient((1280, 720), "#F6E89A", "#F3D9B1")
    base = Image.blend(ImageOps.fit(backplate, (1280, 720)).convert("RGBA"), gradient, .72) if backplate else gradient
    draw = ImageDraw.Draw(base)
    _headline_outline(draw, text, (48, 22, 1232, 260), fill="#FFFFFF", stroke="#111111", accent="#FF3D21")
    evidence = _proof_panel(sources[0], (410, 268), -3.5)
    base.alpha_composite(evidence, (804, 376))
    draw = ImageDraw.Draw(base)
    draw.polygon(((722, 432), (824, 478), (722, 520), (744, 482)), fill="#FF3D21")
    placements: list[dict[str, object]] = []
    if brand_images:
        record, logo = brand_images[0]
        placements.append(_paste_mark(base, record, logo, (330, 475), 330, halo="#315CFF"))
    if len(brand_images) > 1:
        record, logo = brand_images[1]
        placements.append(_paste_mark(base, record, logo, (925, 470), 178, halo="#FF6A24"))
    for record, logo in brand_images[2:]:
        placements.append(_paste_mark(base, record, logo, (1090, 560), 92, halo=record["accent"]))
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((52, 626, 420, 680), radius=12, fill="#111111")
    draw.text((74, 641), "ONE CLAIM. ONE REAL RECEIPT.", font=_font(20), fill="#FFFFFF")
    return base, placements


def _render_editorial_symbol(
    sources: list[Image.Image], text: str, brand_images: list[tuple[dict[str, str], Image.Image]],
    backplate: Image.Image | None = None,
) -> tuple[Image.Image, list[dict[str, object]]]:
    dark = Image.new("RGBA", (1280, 720), "#1B1C20")
    base = Image.blend(ImageOps.fit(backplate, (1280, 720)).convert("RGBA"), dark, .88) if backplate else dark
    draw = ImageDraw.Draw(base)
    tokens = _headline_tokens(text)
    first = " ".join(tokens[:max(1, len(tokens) // 2)])
    second = " ".join(tokens[max(1, len(tokens) // 2):]) or tokens[-1]
    font_a = _font(86)
    font_b = _font(102)
    box_a = draw.textbbox((0, 0), first, font=font_a)
    box_b = draw.textbbox((0, 0), second, font=font_b)
    draw.rectangle((60, 42, 88 + box_a[2], 64 + box_a[3]), fill="#F7F4EA")
    draw.text((74, 45), first, font=font_a, fill="#111111")
    draw.rectangle((92, 143, 128 + box_b[2], 170 + box_b[3]), fill="#ECEA16")
    draw.text((108, 150), second, font=font_b, fill="#111111")
    placements: list[dict[str, object]] = []
    if brand_images:
        if len(brand_images) == 1:
            record, logo = brand_images[0]
            placements.append(_paste_mark(base, record, logo, (455, 492), 292, halo=record["accent"]))
        else:
            for index, (record, logo) in enumerate(brand_images[:2]):
                placements.append(_paste_mark(base, record, logo, ((340, 940)[index], 485), 232, halo=record["accent"]))
            draw = ImageDraw.Draw(base)
            draw.line((640, 348, 640, 630), fill="#ECEA16", width=8)
            draw.polygon(((622, 438), (659, 470), (623, 504)), fill="#1B1C20", outline="#ECEA16")
    proof = _proof_panel(sources[-1], (380, 236), 1.7)
    base.alpha_composite(proof, (820, 420))
    draw = ImageDraw.Draw(base)
    draw.text((68, 657), "THE RECEIPT IS THE STORY", font=_font(20), fill="#A9AAA8")
    return base, placements


def _render_commercial_collage(
    sources: list[Image.Image], text: str, brand_images: list[tuple[dict[str, str], Image.Image]],
    backplate: Image.Image | None = None,
) -> tuple[Image.Image, list[dict[str, object]]]:
    gradient = _gradient((1280, 720), "#F9F6EE", "#ECE8E2")
    base = Image.blend(ImageOps.fit(backplate, (1280, 720)).convert("RGBA"), gradient, .28) if backplate else gradient
    placements: list[dict[str, object]] = []
    collage = (
        (-72, 34, 330, 205, -5.0), (940, 28, 360, 214, 4.0),
        (-38, 472, 350, 220, 3.3), (925, 470, 390, 228, -3.0),
    )
    # Never pad a collage by repeating the same receipt. Fewer, larger authentic
    # sources read as deliberate; duplicated proof reads as template filler.
    for index, (x, y, width, height, angle) in enumerate(collage[:min(4, len(sources))]):
        source = sources[index]
        if index >= 2:
            source_width, source_height = source.size
            source = source.crop((
                int(source_width * .08), int(source_height * .18),
                int(source_width * .92), int(source_height * .86),
            ))
        base.alpha_composite(_proof_panel(source, (width, height), angle), (x, y))
    if brand_images:
        record, logo = brand_images[0]
        placements.append(_paste_mark(base, record, logo, (560, 126), 142, halo=record["accent"]))
        label = record["display_name"].split("/")[0].strip().upper()
        draw = ImageDraw.Draw(base)
        label_font = _font(38)
        label_box = draw.textbbox((0, 0), label, font=label_font)
        label_width = label_box[2] - label_box[0]
        draw.rounded_rectangle((628, 93, 662 + label_width, 149), radius=14, fill=(249, 246, 238, 228), outline="#171717", width=3)
        draw.text((645, 101), label, font=label_font, fill="#171717")
        for index, (record, logo) in enumerate(brand_images[1:]):
            placements.append(_paste_mark(base, record, logo, (570 + index * 140, 614), 104, halo=record["accent"]))
    draw = ImageDraw.Draw(base)
    tokens = _headline_tokens(text)
    split = max(1, len(tokens) // 2)
    first, second = " ".join(tokens[:split]), " ".join(tokens[split:])
    first_font, second_font = _font(86), _serif_font(116)
    first_box = draw.textbbox((0, 0), first, font=first_font)
    second_box = draw.textbbox((0, 0), second, font=second_font)
    draw.text((640 - (first_box[2] - first_box[0]) / 2, 228), first, font=first_font, fill="#171717")
    if second:
        draw.text((640 - (second_box[2] - second_box[0]) / 2, 314), second, font=second_font, fill="#E65322")
    return base, placements


def _render_hypothesis(
    sources: list[Image.Image], text: str, archetype: str, index: int, context_labels: list[str],
    brand_images: list[tuple[dict[str, str], Image.Image]], style_mode: str = "",
    backplate: Image.Image | None = None,
) -> tuple[Image.Image, list[dict[str, object]]]:
    if style_mode == "cinematic_duel":
        return _render_cinematic_duel(sources, text, brand_images, backplate)
    if style_mode == "bold_conflict":
        return _render_bold_conflict(sources, text, brand_images, backplate)
    if style_mode == "editorial_symbol":
        return _render_editorial_symbol(sources, text, brand_images, backplate)
    if style_mode == "commercial_collage":
        return _render_commercial_collage(sources, text, brand_images, backplate)
    base = _base_canvas(index)
    draw = ImageDraw.Draw(base)
    source_a = sources[index % len(sources)]
    source_b = sources[(index + 1) % len(sources)]
    if archetype == "mechanism_map":
        source_a = sources[0]
    if archetype == "claim_vs_receipt":
        source_a = sources[0]
        width, height = source_a.size
        source_b = source_a.crop((int(width * .58), 0, width, height))
    if archetype in {"agent_showdown", "proof_split", "before_after", "evidence_grid", "claim_vs_receipt"}:
        _draw_headline(draw, text, (58, 42, 1222, 190))
        _paste_proof(base, source_a, (56, 224), (558, 398), -0.6)
        _paste_proof(base, source_b, (666, 224), (558, 398), 0.6)
        left_label, right_label = (
            ("BEFORE", "AFTER") if archetype == "before_after" else
            ("SAME TASK", "SAME TEST") if archetype in {"agent_showdown", "proof_split"} else
            ("PROJECT PAGE", "CLAIM DETAIL") if archetype == "claim_vs_receipt" else
            ("SOURCE 01", "SOURCE 02")
        )
        draw.rounded_rectangle((76, 568, 230, 608), radius=8, fill=INK)
        draw.rounded_rectangle((686, 568, 840, 608), radius=8, fill=INK)
        draw.text((92, 577), left_label, font=_font(19), fill=PAPER)
        draw.text((702, 577), right_label, font=_font(19), fill=PAPER)
    elif archetype == "product_plus_proof":
        _draw_headline(draw, text, (58, 82, 572, 392))
        _paste_proof(base, source_a, (630, 104), (594, 470), .7)
        draw.rounded_rectangle((58, 486, 520, 618), radius=22, fill=CARD, outline=MOSS, width=4)
        _draw_context_label(draw, context_labels[0], (132, 552), 102)
        draw.text((206, 512), "PRODUCT CLAIM", font=_font(23), fill=MUTED)
        draw.text((206, 548), "PLUS SOURCE PROOF", font=_font(31), fill=PAPER)
    elif archetype in {"proof_closeup", "hero_story"}:
        capture = ImageOps.fit(source_a, base.size, method=Image.Resampling.LANCZOS)
        capture = ImageEnhance.Sharpness(capture).enhance(1.15).convert("RGBA")
        base = Image.blend(base, capture, .72)
        shade = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(shade).rectangle((0, 0, 690, 720), fill=(7, 8, 8, 210))
        base = Image.alpha_composite(base, shade.filter(ImageFilter.GaussianBlur(18)))
        draw = ImageDraw.Draw(base)
        _draw_headline(draw, text, (58, 110, 610, 430))
        draw.rounded_rectangle((58, 500, 278, 548), radius=6, fill=CARD, outline=SLATE, width=2)
        draw.text((78, 511), "SOURCE PROOF", font=_font(20), fill=PAPER)
    elif archetype in {"ranked_stack"}:
        _draw_headline(draw, text, (58, 76, 565, 380))
        for card_index, (x, y, angle) in enumerate(((610, 70, -2.2), (680, 185, .5), (750, 300, 2.2))):
            _paste_proof(base, sources[card_index % len(sources)], (x, y), (500, 320), angle)
    elif archetype in {"mechanism_map", "workflow_relay"}:
        _draw_headline(draw, text, (58, 72, 590, 350))
        _paste_proof(base, source_a, (690, 108), (540, 440), .5)
        points = [(120, 535), (338, 535), (556, 535)]
        for left, right in zip(points, points[1:]):
            draw.line((left[0] + 56, left[1], right[0] - 56, right[1]), fill=MOSS, width=4)
            draw.polygon(((right[0] - 62, right[1] - 8), (right[0] - 62, right[1] + 8), (right[0] - 48, right[1])), fill=MOSS)
        mechanism_labels = ["IDENTITY", "SOURCE", "REAL COST"] if brand_images else ["SOURCE CLAIM", "ONE LAYER", "GPU MEMORY"]
        if archetype == "workflow_relay" and not brand_images:
            mechanism_labels = (context_labels + ["RESULT"])[:3]
        start = min(len(brand_images), len(points))
        for label, point in zip(mechanism_labels[start:], points[start:]):
            _draw_context_label(draw, label, point, 112)
    elif archetype == "broken_assumption":
        draw.polygon(((0, 0), (748, 0), (610, 720), (0, 720)), fill="#101313")
        draw.line((668, 30, 548, 690), fill=SLATE, width=6)
        _draw_headline(draw, text, (54, 54, 610, 340))
        _paste_proof(base, source_a, (650, 116), (560, 474), 1.2)
        draw.rounded_rectangle((704, 554, 918, 602), radius=6, fill=INK, outline=SLATE, width=2)
        draw.text((725, 565), "THE SOURCE RECEIPT", font=_font(20), fill=PAPER)
    elif archetype == "consequence_frame":
        capture = ImageOps.fit(source_a, (820, 720), method=Image.Resampling.LANCZOS).convert("RGBA")
        base.alpha_composite(capture, (0, 0))
        veil = Image.new("RGBA", base.size, (0, 0, 0, 0))
        veil_draw = ImageDraw.Draw(veil)
        veil_draw.rectangle((0, 0, 840, 720), fill=(5, 6, 6, 62))
        veil_draw.polygon(((680, 0), (1280, 0), (1280, 720), (790, 720)), fill=(9, 10, 10, 244))
        base = Image.alpha_composite(base, veil)
        draw = ImageDraw.Draw(base)
        draw.line((792, 42, 706, 678), fill=SLATE, width=5)
        _draw_headline(draw, text, (840, 74, 1222, 405))
        draw.text((842, 420), "THE PRACTICAL CONSEQUENCE", font=_font(19), fill=MUTED)
    else:
        proof_x = 650 if index % 2 == 0 else -30
        headline_box = (58, 84, 600, 410) if proof_x > 0 else (700, 84, 1222, 410)
        _draw_headline(draw, text, headline_box)
        _paste_proof(base, source_a, (proof_x, 116), (690, 500), -1 if proof_x > 0 else 1)
        label_x = 120 if proof_x > 0 else 800
        if not brand_images:
            for label_index, label in enumerate(context_labels):
                _draw_context_label(draw, label, (label_x + label_index * 150, 560), 116)
    draw = ImageDraw.Draw(base)
    draw.text((58, 664), "AI NEWS / SOURCE FIRST", font=_font(20), fill=MUTED)
    draw.rectangle((316, 670, 446, 674), fill=SLATE)
    placements = _draw_brand_identity(base, brand_images, archetype)
    return base, placements


def validate_concepts(concepts: list[ThumbnailConcept]) -> dict:
    failures: list[str] = []
    if len(concepts) != 4:
        failures.append(f"expected four concept contracts, received {len(concepts)}")
    if len({concept.archetype for concept in concepts}) != len(concepts):
        failures.append("concept archetypes must be materially distinct")
    if len({concept.visual_sentence.casefold() for concept in concepts}) != len(concepts):
        failures.append("concept visual sentences must be materially distinct")
    if len({concept.style_mode for concept in concepts}) != len(concepts):
        failures.append("concept style modes must be materially distinct")
    for index, concept in enumerate(concepts, start=1):
        if not 2 <= len(concept.headline.split()) <= 5:
            failures.append(f"concept {index} headline must contain 2-5 words")
        if not concept.focal_subject.strip():
            failures.append(f"concept {index} has no dominant focal subject")
        if not concept.evidence_ids:
            failures.append(f"concept {index} has no evidence IDs")
        if not concept.asset_ids:
            failures.append(f"concept {index} has no accepted source/frame asset IDs")
        if len(concept.highlighted_keyword.split()) != 1:
            failures.append(f"concept {index} may highlight only one keyword")
        if len(set(concept.required_logos)) != len(concept.required_logos):
            failures.append(f"concept {index} repeats a required brand identity")
        if concept.headline.upper() in GENERIC_HYPE:
            failures.append(f"concept {index} uses an empty generic-hype hook")
        if any(term.casefold() in concept.visual_sentence.casefold() for term in concept.must_not_imply):
            failures.append(f"concept {index} repeats a forbidden implication")
        if concept.style_mode not in {"cinematic_duel", "bold_conflict", "editorial_symbol", "commercial_collage"}:
            failures.append(f"concept {index} uses an unsupported style mode: {concept.style_mode}")
    return {"passed": not failures, "failures": failures, "candidate_count": len(concepts)}


def generate_variants(
    backgrounds: list[Path], text: str, output_dir: Path, *, topic_context: str = "", episode_format: str = "",
    topic_class: str = "", evidence_ids: list[str] | None = None, asset_ids: list[str] | None = None,
    focal_subject: str = "PRIMARY SOURCE", supporting_subjects: list[str] | None = None,
    required_logos: list[str] | None = None, must_not_imply: list[str] | None = None,
    represented_companies: list[str] | None = None, brand_root: Path | None = None,
    brand_asset_overrides: dict[str, Path] | None = None,
    generate_backplates: bool = False, backplate_model: str = "nano-banana-2",
    backplate_fallback_model: str = "nano-banana", backplate_resolution: str = "2k",
    require_brand_identity: bool = False,
) -> list[Path]:
    if not backgrounds:
        raise ValueError("at least one thumbnail background is required")
    output_dir.mkdir(parents=True, exist_ok=True)
    source_reviews = [{"path": str(path), **source_suitability(path)} for path in backgrounds]
    accepted_paths = [Path(review["path"]) for review in source_reviews if review["passed"]]
    if not accepted_paths:
        raise ValueError("all thumbnail sources were rejected as blank, blocked, or unreadable")
    sources = [Image.open(path).convert("RGB") for path in accepted_paths]
    context = " ".join(filter(None, [text, topic_context, episode_format]))
    context_labels = _context_labels(context)
    detected_brands = detect_brand_keys(
        [focal_subject, *(supporting_subjects or [])], context=context,
    )
    requested_brands = list(dict.fromkeys(required_logos or represented_companies or detected_brands))
    if require_brand_identity and not requested_brands:
        raise ValueError("thumbnail identity gate requires at least one represented company logo or official mascot")
    brand_records = resolve_brand_assets(
        requested_brands, brand_root=brand_root or DEFAULT_BRAND_ROOT, overrides=brand_asset_overrides,
    ) if requested_brands else []
    cache_dir = output_dir / ".brand-cache"
    brand_images = [(record, _load_brand_image(record, cache_dir)) for record in brand_records]
    resolved_brand_keys = [record["key"] for record in brand_records]
    resolved_topic = topic_class or classify_story(context, source_count=len(sources))
    resolved_assets = asset_ids or [path.stem for path in accepted_paths]
    resolved_evidence = evidence_ids or [f"source:{asset_id}" for asset_id in resolved_assets]
    concepts = build_thumbnail_concepts(
        topic_class=resolved_topic, headline=text, focal_subject=focal_subject,
        evidence_ids=resolved_evidence, asset_ids=resolved_assets,
        supporting_subjects=supporting_subjects or [], required_logos=resolved_brand_keys,
        must_not_imply=must_not_imply or [],
    )
    concept_review = validate_concepts(concepts)
    if not concept_review["passed"]:
        raise ValueError("thumbnail concept contracts failed: " + "; ".join(concept_review["failures"]))
    backplate_paths: list[Path] = []
    backplate_record: dict[str, object] = {"enabled": False, "paths": []}
    if generate_backplates:
        backplate_paths, backplate_record = generate_magic_hour_backplates(
            concepts,
            output_dir,
            model=backplate_model,
            fallback_model=backplate_fallback_model,
            resolution=backplate_resolution,
        )
        backplate_record["enabled"] = True
    backplate_images: list[Image.Image | None] = [
        Image.open(path).convert("RGB") for path in backplate_paths[:4]
    ]
    backplate_images.extend([None] * (4 - len(backplate_images)))
    outputs: list[Path] = []
    candidates: list[dict] = []
    all_placements: list[list[dict[str, object]]] = []
    preview_dir = output_dir / "mobile-previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for index, concept in enumerate(concepts):
        base, placements = _render_hypothesis(
            sources, text, concept.archetype, index, context_labels, brand_images, concept.style_mode,
            backplate_images[index],
        )
        destination = output_dir / f"thumbnail_{index + 1}.jpg"
        preview = preview_dir / f"thumbnail_{index + 1}_320x180.jpg"
        base.convert("RGB").save(destination, quality=95, optimize=True)
        base.convert("RGB").resize((320, 180), Image.Resampling.LANCZOS).save(preview, quality=92)
        outputs.append(destination)
        all_placements.append(placements)
        candidates.append({
            "path": str(destination), "mobile_preview": str(preview),
            "brand_assets": brand_records, "brand_placements": placements,
            "generated_backplate": str(backplate_paths[index]) if index < len(backplate_paths) else "",
            "hook_strategy": {"angle": concept.angle, "visual_sentence": concept.visual_sentence},
            **concept.as_dict(),
        })
    inspection = validate_variants(
        outputs, text, concepts=concepts, brand_records=brand_records, brand_placements=all_placements,
    )
    for candidate, score in zip(candidates, inspection["scores"]):
        candidate["score"] = score
    preferred_archetypes = {
        "release": ("product_plus_proof", "proof_closeup"),
        "comparison": ("proof_split", "criterion_card", "agent_showdown"),
        "workflow": ("before_after", "mechanism_map", "proof_closeup"),
        "failure": ("broken_assumption", "proof_closeup", "consequence_frame"),
        "research": ("claim_vs_receipt", "proof_closeup", "mechanism_map"),
        "business-policy": ("consequence_frame", "claim_vs_receipt", "proof_split"),
        "weekly-roundup": ("hero_story", "ranked_stack", "evidence_grid"),
    }[concepts[0].topic_class]
    idea_fit_scores: list[int] = []
    for concept in concepts:
        try:
            idea_fit_scores.append(max(0, 8 - preferred_archetypes.index(concept.archetype) * 2))
        except ValueError:
            idea_fit_scores.append(1)
    winner_index = max(
        range(len(candidates)),
        key=lambda index: inspection["scores"][index]["score"] + idea_fit_scores[index],
    )
    for candidate, idea_fit in zip(candidates, idea_fit_scores):
        candidate["idea_fit_score"] = idea_fit
    for index, candidate in enumerate(candidates):
        candidate["recommended"] = index == winner_index
    automation_plan = build_automation_plan(
        concepts,
        brand_labels=[record["display_name"] for record in brand_records],
    )
    manifest = {
        "algorithm_version": 10, "story_type": concepts[0].topic_class,
        "topic_class": concepts[0].topic_class, "headline": text,
        "represented_companies": resolved_brand_keys, "requested_company_labels": requested_brands,
        "resolved_brand_assets": brand_records,
        "source_count": len(sources), "source_reviews": source_reviews,
        "quality_floor": 88, "identity_policy": "official-assets-only",
        "generated_backplate_policy": "scene-only-no-text-no-logos-no-product-ui",
        "generated_backplates": backplate_record,
        "automation_plan": automation_plan, "recommended_candidate": winner_index + 1,
        "selection_policy": "story-hook-fit-plus-mobile-quality-after-evidence-gate",
        "human_review_required": True, "candidates": candidates,
    }
    (output_dir / "thumbnail_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "thumbnail_qc.json").write_text(json.dumps(inspection, indent=2), encoding="utf-8")
    if not inspection["passed"]:
        raise ValueError("thumbnail candidates failed automated readability QC: " + "; ".join(inspection["failures"]))
    return outputs


def validate_variants(
    paths: list[Path], text: str, *, concepts: list[ThumbnailConcept] | None = None,
    brand_records: list[dict[str, str]] | None = None,
    brand_placements: list[list[dict[str, object]]] | None = None,
) -> dict:
    failures: list[str] = []
    scores: list[dict] = []
    if not 3 <= len(text.split()) <= 5:
        failures.append("overlay copy must contain 3-5 words")
    if len(paths) != 4:
        failures.append(f"expected four candidates, received {len(paths)}")
    if text.upper() in GENERIC_HYPE:
        failures.append("headline is empty generic hype rather than a specific supported hook")
    if concepts is not None:
        failures.extend(validate_concepts(concepts)["failures"])
    for index, path in enumerate(paths):
        try:
            image = Image.open(path).convert("RGB")
            grayscale = image.convert("L")
            extrema = ImageStat.Stat(grayscale).extrema[0]
            if image.size != (1280, 720):
                failures.append(f"{path.name} is not 1280x720")
            if extrema[1] - extrema[0] < 80 or grayscale.entropy() < 2.0:
                failures.append(f"{path.name} lacks readable tonal separation")
            contrast = min(10, round((extrema[1] - extrema[0]) / 255 * 10))
            concept = concepts[index] if concepts and index < len(concepts) else None
            evidence = 20 if concept is None or (concept.evidence_ids and concept.asset_ids) else 0
            mobile_gray = image.resize((320, 180), Image.Resampling.LANCZOS).convert("L")
            mobile_entropy = mobile_gray.entropy()
            mobile_stddev = ImageStat.Stat(mobile_gray).stddev[0]
            mobile = min(18, round(7 + min(7, mobile_entropy * 1.5) + min(4, mobile_stddev / 22)))
            hierarchy = min(12, round(4 + min(8, mobile_stddev / 12)))
            legibility = 15 if 3 <= len(text.split()) <= 5 and contrast >= 7 else 5
            required = set(concept.required_logos) if concept else set()
            resolved = {record["key"] for record in (brand_records or [])}
            placed = {
                str(item.get("key")) for item in (
                    brand_placements[index] if brand_placements and index < len(brand_placements) else []
                )
            }
            missing_brands = sorted(required - resolved)
            missing_placements = sorted(required - placed)
            if missing_brands:
                failures.append(f"{path.name} is missing approved brand assets: {', '.join(missing_brands)}")
            if missing_placements:
                failures.append(f"{path.name} does not visibly place required brands: {', '.join(missing_placements)}")
            brand = 15 if not required or (not missing_brands and not missing_placements) else 0
            hook = 10 if text.upper() not in GENERIC_HYPE and concept and concept.angle else 5
            topic_fit = 5 if concept is None or concept.topic_class else 0
            score = evidence + mobile + hierarchy + legibility + brand + hook + 5 + topic_fit
            scores.append({
                "path": str(path), "score": score, "promise_evidence": evidence,
                "mobile_comprehension": mobile, "focal_hierarchy": hierarchy,
                "text_legibility": legibility, "brand_accuracy": brand,
                "curiosity_tension": hook, "originality": 5, "topic_fit": topic_fit,
                "mobile_entropy": round(mobile_entropy, 3),
                "mobile_luma_stddev": round(mobile_stddev, 3),
            })
        except (OSError, ValueError) as exc:
            failures.append(f"{path.name} is unreadable: {exc}")
    if len(paths) >= 2:
        hashes = [Image.open(path).convert("L").resize((16, 9), Image.Resampling.LANCZOS) for path in paths]
        for left in range(len(hashes)):
            for right in range(left + 1, len(hashes)):
                if ImageStat.Stat(ImageChops.difference(hashes[left], hashes[right])).mean[0] < 2.5:
                    failures.append(f"thumbnail_{left + 1} and thumbnail_{right + 1} are near-duplicates")
                    scores[left]["originality"] = 0
                    scores[right]["originality"] = 0
                    scores[left]["score"] -= 5
                    scores[right]["score"] -= 5
    low_scores = [Path(item["path"]).name for item in scores if item["score"] < 88]
    if low_scores:
        failures.append("thumbnail candidates below the 88/100 quality floor: " + ", ".join(low_scores))
    return {"passed": not failures, "failures": failures, "candidate_count": len(paths), "text_words": len(text.split()), "scores": scores}
