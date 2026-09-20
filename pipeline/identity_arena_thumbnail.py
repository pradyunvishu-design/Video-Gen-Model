"""High-stakes, face-free identity thumbnails for agent and model stories."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .brand_assets import DEFAULT_BRAND_ROOT, resolve_brand_assets
from .thumbnail import _font, _load_brand_image, validate_variants
from .thumbnail_automation import generate_magic_hour_backplates


CANVAS = (1280, 720)
INK = "#0A0B0E"
PAPER = "#F7F4EA"
SLATE = "#83938C"
ORANGE = "#FF6A24"
BLUE = "#4E7CFF"
CYAN = "#63D7FF"
RED = "#FF3B30"


def _arena_prompt(name: str, composition: str, materials: str, lighting: str, zones: str) -> dict[str, str]:
    prompt = (
        "Generate exactly one premium 16:9 BACKGROUND PLATE at 2K for a high-stakes technology-news thumbnail. "
        "This is a photographed physical miniature set, not a finished YouTube thumbnail and not an AI illustration. "
        "The story is a new headquarters where several software agents meet, compete, and coordinate. "
        f"Composition: {composition}. Materials: {materials}. Lighting: {lighting}. "
        f"Required negative space and overlay zones: {zones}. "
        "Use a straight-on 40mm commercial product-photography camera, level horizon, deep but readable blacks, "
        "precise construction, physically grounded shadows, sharp material edges, and deliberate asymmetry. "
        "The later compositor will add exact official logos, app icons, typography, arrows, and evidence. "
        "Keep every icon mount completely empty and unmarked. Preserve large clean silhouette separation at phone size. "
        "Do not invent literal software products, agent characters, mascots, screens, interfaces, labels, or claims. "
        "STRICTLY EXCLUDE: words, letters, numbers, pseudo-writing, exact official logos, brand marks, mascots, UI, "
        "browser windows, people, faces, heads, hands, bodies, robots, androids, armor, boxing gloves, gears, circuit boards, "
        "microchips, sci-fi tunnels, portals, holograms, neon fog, floating orbs, liquid chrome, random glyphs, watermarks, "
        "confetti, warped geometry, duplicated props, impossible reflections, and excessive depth of field."
    )
    return {"style_mode": name, "archetype": "identity_arena", "generation_mode": "nano-banana-2", "prompt": prompt}


def build_identity_arena_prompts() -> list[dict[str, str]]:
    return [
        _arena_prompt(
            "agent_hq",
            "a monumental central hexagonal dais on the right, two lower square app-icon plinths on the left, and a broad headline field across the upper-left",
            "matte black lacquer, smoked acrylic, brushed aluminum, one amber glass slab, restrained cobalt edge accents",
            "premium sports-broadcast key light, warm rim on the central dais, cool side fill, no haze or bloom",
            "45 percent clean upper-left headline space; one 340-pixel central identity mount; two 190-pixel side identity mounts",
        ),
        _arena_prompt(
            "agent_showdown",
            "two opposing low platforms at the bottom corners aimed toward one elevated central command pedestal, with a clean tension gap",
            "charcoal architectural plaster, black glass, thin orange and cobalt acrylic rails, subtle brushed steel",
            "cinematic arena lighting with controlled orange left rim, cobalt right rim, neutral central key, no fog",
            "clean upper-third headline band; one central identity mount; equal left and right identity mounts",
        ),
        _arena_prompt(
            "agent_orbit",
            "one large central square pedestal surrounded by two smaller empty satellite mounts and a restrained circular floor track",
            "black painted wood, warm amber translucent acrylic, off-white enamel, thin metallic inlays",
            "high-end product launch lighting, crisp central key, narrow amber rim, soft shadow falloff",
            "uninterrupted upper-left headline field; large center identity zone; two satellite identity zones",
        ),
        _arena_prompt(
            "agent_home",
            "a high-key editorial studio with one large black architectural portal on the left and two small arrival platforms on the right",
            "warm ivory paper cyclorama, matte black acrylic, amber glass blocks, one cobalt registration line",
            "large softbox from upper left, restrained warm bounce, short plausible shadows, no atmospheric effects",
            "clean upper half for headline; large left identity zone; two right-side identity zones",
        ),
    ]


def _fit_mark(logo: Image.Image, box: tuple[int, int]) -> Image.Image:
    mark = logo.convert("RGBA").copy()
    mark.thumbnail(box, Image.Resampling.LANCZOS)
    return mark


def _hex(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5)) + (alpha,)


def _editorial_canvas(index: int) -> Image.Image:
    """Build a crisp, art-directed background without generative imagery."""
    width, height = CANVAS
    top = (7, 8, 12) if index != 3 else (242, 239, 225)
    bottom = (21, 25, 37) if index != 3 else (217, 225, 240)
    image = Image.new("RGBA", CANVAS)
    pixels = image.load()
    for y in range(height):
        mix = y / max(1, height - 1)
        color = tuple(int(top[c] * (1 - mix) + bottom[c] * mix) for c in range(3)) + (255,)
        for x in range(width):
            pixels[x, y] = color
    texture = Image.effect_noise(CANVAS, 18).convert("L").point(lambda value: int(255 * .88 + value * .12))
    texture_rgba = Image.merge("RGBA", (texture, texture, texture, Image.new("L", CANVAS, 24)))
    image = Image.alpha_composite(image, texture_rgba)
    draw = ImageDraw.Draw(image, "RGBA")
    if index == 0:
        draw.polygon(((665, 0), (1280, 0), (1280, 720), (835, 720)), fill=(255, 106, 36, 32))
        draw.line((780, 0, 1010, 720), fill=(255, 255, 255, 34), width=3)
        draw.ellipse((820, 150, 1330, 660), outline=(243, 234, 18, 80), width=5)
    elif index == 1:
        draw.polygon(((0, 240), (640, 90), (640, 720), (0, 720)), fill=(36, 90, 255, 52))
        draw.polygon(((640, 90), (1280, 240), (1280, 720), (640, 720)), fill=(255, 106, 36, 52))
        draw.line((640, 115, 640, 720), fill=(255, 255, 255, 58), width=4)
        draw.text((598, 335), "VS", font=_font(60), fill=(255, 255, 255, 70))
    elif index == 2:
        for radius, alpha in ((430, 28), (330, 38), (230, 48)):
            draw.ellipse((800 - radius, 430 - radius, 800 + radius, 430 + radius), outline=(99, 215, 255, alpha), width=4)
        draw.arc((230, 165, 1165, 760), 180, 348, fill=(243, 234, 18, 120), width=8)
    else:
        draw.rounded_rectangle((48, 46, 1232, 674), radius=36, fill=(255, 255, 255, 150), outline=(255, 255, 255, 220), width=3)
        draw.polygon(((0, 590), (1280, 480), (1280, 720), (0, 720)), fill=(78, 124, 255, 35))
        for x in range(0, width, 48):
            draw.line((x, 670, x + 320, 490), fill=(20, 24, 33, 13), width=2)
    return image


def _agent_body(
    base: Image.Image,
    record: dict[str, str],
    logo: Image.Image,
    center: tuple[int, int],
    size: int,
    *,
    body_color: str,
    lean: int = 0,
    dominant: bool = False,
) -> dict[str, object]:
    """Draw a clean mascot body and use the exact official mark as its head."""
    layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    x, y = center
    head = int(size * .52)
    torso_w = int(size * .64)
    torso_h = int(size * .52)
    shadow = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.ellipse((x - size * .48, y + size * .40, x + size * .48, y + size * .58), fill=(0, 0, 0, 155))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(10, size // 20)))
    base.alpha_composite(shadow)
    outline = max(8, size // 28)
    body_top = y + int(head * .28)
    body_box = (x - torso_w // 2, body_top, x + torso_w // 2, body_top + torso_h)
    draw.rounded_rectangle(body_box, radius=int(size * .16), fill=_hex(body_color), outline=(5, 6, 9, 255), width=outline)
    draw.pieslice((x - torso_w // 2, body_top - size * .06, x + torso_w // 2, body_top + size * .28), 190, 350, fill=(255, 255, 255, 28))
    shoulder_y = body_top + int(size * .15)
    arm_w = max(18, int(size * .16))
    left_hand = (x - int(size * .48) + lean, y + int(size * .42))
    right_hand = (x + int(size * .48) + lean, y + int(size * .32))
    draw.line((x - torso_w * .36, shoulder_y, *left_hand), fill=(5, 6, 9, 255), width=arm_w + outline)
    draw.line((x - torso_w * .36, shoulder_y, *left_hand), fill=_hex(body_color), width=arm_w)
    draw.line((x + torso_w * .36, shoulder_y, *right_hand), fill=(5, 6, 9, 255), width=arm_w + outline)
    draw.line((x + torso_w * .36, shoulder_y, *right_hand), fill=_hex(body_color), width=arm_w)
    for hx, hy in (left_hand, right_hand):
        r = int(size * .105)
        draw.ellipse((hx - r, hy - r, hx + r, hy + r), fill=_hex(body_color), outline=(5, 6, 9, 255), width=outline)
    leg_y = body_top + torso_h - 8
    for direction in (-1, 1):
        lx = x + direction * int(size * .16)
        draw.line((lx, leg_y, lx + direction * size * .06, leg_y + size * .22), fill=(5, 6, 9, 255), width=arm_w + outline)
        draw.line((lx, leg_y, lx + direction * size * .06, leg_y + size * .22), fill=_hex(body_color), width=arm_w)
    head_box = (x - head // 2, y - head // 2, x + head // 2, y + head // 2)
    draw.rounded_rectangle(head_box, radius=int(head * .20), fill=(248, 247, 242, 255), outline=(5, 6, 9, 255), width=outline)
    accent = record["accent"]
    draw.rounded_rectangle((head_box[0] + 8, head_box[1] + 8, head_box[2] - 8, head_box[3] - 8), radius=int(head * .16), outline=_hex(accent), width=max(4, outline // 2))
    mark = _fit_mark(logo, (int(head * .68), int(head * .68)))
    layer.alpha_composite(mark, (x - mark.width // 2, y - mark.height // 2))
    if dominant:
        glow = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((x - size * .62, y - size * .62, x + size * .62, y + size * .72), fill=_hex(accent, 65))
        base.alpha_composite(glow.filter(ImageFilter.GaussianBlur(int(size * .18))))
    base.alpha_composite(layer)
    return {
        "key": record["key"], "display_name": record["display_name"],
        "bbox": [int(x - size * .55), int(y - size * .55), int(x + size * .55), int(y + size * .78)],
        "asset_sha256": record["asset_sha256"],
    }


def _glow(base: Image.Image, center: tuple[int, int], radius: int, color: str, opacity: int = 115) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    rgb = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*rgb, opacity))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(12, radius // 2))))


def _icon_tile(
    base: Image.Image, record: dict[str, str], logo: Image.Image, center: tuple[int, int], size: int,
    *, angle: float = 0, dominant: bool = False,
) -> dict[str, object]:
    accent = record["accent"]
    _glow(base, center, int(size * .72), accent, 130 if dominant else 90)
    tile = Image.new("RGBA", (size + 44, size + 54), (0, 0, 0, 0))
    shadow = Image.new("RGBA", tile.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((25, 29, size + 25, size + 29), radius=max(22, size // 8), fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    tile.alpha_composite(shadow)
    td = ImageDraw.Draw(tile)
    panel_fill = "#F8F6EF" if record["key"] in {"openai", "claude"} else "#0B0B0B"
    td.rounded_rectangle((16, 10, size + 16, size + 10), radius=max(22, size // 8), fill=panel_fill, outline=accent, width=max(3, size // 70))
    mark = _fit_mark(logo, (int(size * .72), int(size * .72)))
    tile.alpha_composite(mark, (16 + (size - mark.width) // 2, 10 + (size - mark.height) // 2))
    if angle:
        tile = tile.rotate(angle, Image.Resampling.BICUBIC, expand=True)
    position = (int(center[0] - tile.width / 2), int(center[1] - tile.height / 2))
    base.alpha_composite(tile, position)
    return {
        "key": record["key"], "display_name": record["display_name"],
        "bbox": [position[0], position[1], position[0] + tile.width, position[1] + tile.height],
        "asset_sha256": record["asset_sha256"],
    }


def _logo_on_blank_panel(
    base: Image.Image,
    record: dict[str, str],
    logo: Image.Image,
    center: tuple[int, int],
    size: int,
) -> dict[str, object]:
    """Overlay an exact official mark onto a generated blank mascot panel."""
    mark = _fit_mark(logo, (int(size * .78), int(size * .78)))
    x = int(center[0] - mark.width / 2)
    y = int(center[1] - mark.height / 2)
    base.alpha_composite(mark, (x, y))
    return {
        "key": record["key"], "display_name": record["display_name"],
        "bbox": [x, y, x + mark.width, y + mark.height],
        "panel_center": list(center), "panel_size": size,
        "asset_sha256": record["asset_sha256"],
    }


def _neutral_components(image: Image.Image, tone: str) -> list[dict[str, int | float]]:
    """Find compact near-white or near-black components at a cheap analysis resolution."""
    analysis_width = 320
    scale = image.width / analysis_width
    analysis_height = max(1, round(image.height / scale))
    pixels = np.asarray(image.convert("RGB").resize((analysis_width, analysis_height), Image.Resampling.BILINEAR))
    high = pixels.max(axis=2)
    low = pixels.min(axis=2)
    spread = high.astype(np.int16) - low.astype(np.int16)
    mean = pixels.mean(axis=2)
    mask = ((mean >= 172) & (spread <= 58)) if tone == "white" else ((mean <= 58) & (spread <= 46))
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[dict[str, int | float]] = []
    for start_y in range(height):
        for start_x in range(width):
            if not mask[start_y, start_x] or visited[start_y, start_x]:
                continue
            stack = [(start_x, start_y)]
            visited[start_y, start_x] = True
            min_x = max_x = start_x
            min_y = max_y = start_y
            area = 0
            while stack:
                x, y = stack.pop()
                area += 1
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((nx, ny))
            box_width = max_x - min_x + 1
            box_height = max_y - min_y + 1
            touches_edge = min_x <= 1 or min_y <= 1 or max_x >= width - 2 or max_y >= height - 2
            aspect = box_width / max(1, box_height)
            fill = area / max(1, box_width * box_height)
            if touches_edge or min(box_width, box_height) < 18 or max(box_width, box_height) > 115:
                continue
            if not 0.55 <= aspect <= 1.65 or fill < 0.42:
                continue
            components.append({
                "x": round(((min_x + max_x + 1) / 2) * scale),
                "y": round(((min_y + max_y + 1) / 2) * scale),
                "width": round(box_width * scale), "height": round(box_height * scale),
                "fill": float(fill), "aspect": float(aspect),
            })
    return components


def snap_panel_anchors(image: Image.Image, panel_spec: dict[str, object]) -> dict[str, object]:
    """Snap planned logo anchors to the generated blank display panels."""
    adjusted = {key: dict(value) if isinstance(value, dict) else value for key, value in panel_spec.items()}
    used: set[tuple[str, int]] = set()
    candidates = {tone: _neutral_components(image, tone) for tone in ("black", "white")}
    targets = [
        (key, value) for key, value in adjusted.items()
        if isinstance(value, dict) and not value.get("badge") and "size" in value
    ]
    for _key, target in targets:
        tone = str(target.get("panel_tone") or "white")
        expected_x, expected_y, expected_size = int(target["x"]), int(target["y"]), int(target["size"])
        ranked: list[tuple[float, int, dict[str, int | float]]] = []
        for index, component in enumerate(candidates.get(tone, [])):
            if (tone, index) in used:
                continue
            distance = math.hypot(float(component["x"]) - expected_x, float(component["y"]) - expected_y) / 420
            side = min(float(component["width"]), float(component["height"]))
            desired_panel_side = max(90.0, expected_size / .68)
            size_penalty = abs(math.log(max(1.0, side) / desired_panel_side)) * .35
            aspect_penalty = abs(math.log(float(component["aspect"]))) * .22
            ranked.append((distance + size_penalty + aspect_penalty, index, component))
        if not ranked:
            target["anchor_detection"] = "planned-fallback"
            continue
        score, selected_index, selected = min(ranked, key=lambda item: item[0])
        if score > 1.25:
            target["anchor_detection"] = "planned-fallback"
            continue
        used.add((tone, selected_index))
        target["planned_x"], target["planned_y"], target["planned_size"] = expected_x, expected_y, expected_size
        target["x"], target["y"] = int(selected["x"]), int(selected["y"])
        target["size"] = max(64, min(230, round(min(float(selected["width"]), float(selected["height"])) * .68)))
        target["detected_panel_box"] = [
            round(float(selected["x"]) - float(selected["width"]) / 2),
            round(float(selected["y"]) - float(selected["height"]) / 2),
            round(float(selected["x"]) + float(selected["width"]) / 2),
            round(float(selected["y"]) + float(selected["height"]) / 2),
        ]
        target["anchor_detection"] = "visual-snap"
    return adjusted


def _identity_badge(
    base: Image.Image,
    record: dict[str, str],
    logo: Image.Image,
    center: tuple[int, int],
    width: int,
    height: int,
) -> dict[str, object]:
    """Place a deliberate high-contrast supporting-identity badge."""
    x, y = center
    shadow = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.rounded_rectangle((x - width // 2 + 5, y - height // 2 + 7, x + width // 2 + 5, y + height // 2 + 7), radius=height // 3, fill=(0, 0, 0, 150))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)))
    draw = ImageDraw.Draw(base, "RGBA")
    draw.rounded_rectangle((x - width // 2, y - height // 2, x + width // 2, y + height // 2), radius=height // 3, fill=(250, 249, 244, 245), outline=(12, 13, 17, 255), width=3)
    mark = _fit_mark(logo, (int(width * .72), int(height * .62)))
    px, py = x - mark.width // 2, y - mark.height // 2
    base.alpha_composite(mark, (px, py))
    return {
        "key": record["key"], "display_name": record["display_name"],
        "bbox": [x - width // 2, y - height // 2, x + width // 2, y + height // 2],
        "asset_sha256": record["asset_sha256"], "placement_kind": "supporting_identity_badge",
    }


def _headline(base: Image.Image, lines: tuple[str, str], *, left: int, top: int, width: int, dark: bool = True) -> None:
    draw = ImageDraw.Draw(base)
    first_size = 82
    second_size = 102
    first_font = _font(first_size)
    second_font = _font(second_size)
    while draw.textbbox((0, 0), lines[0], font=first_font)[2] > width and first_size > 48:
        first_size -= 2
        first_font = _font(first_size)
    while draw.textbbox((0, 0), lines[1], font=second_font)[2] > width and second_size > 54:
        second_size -= 2
        second_font = _font(second_size)
    ink = "#FFFFFF" if dark else "#111318"
    draw.text((left, top), lines[0], font=first_font, fill=ink, stroke_width=3 if dark else 0, stroke_fill="#050608")
    box = draw.textbbox((left, top + first_size + 5), lines[1], font=second_font)
    draw.rounded_rectangle((box[0] - 10, box[1] - 4, box[2] + 12, box[3] + 5), radius=4, fill=SLATE)
    draw.text((left, top + first_size + 5), lines[1], font=second_font, fill="#111318")


def _connector(base: Image.Image, start: tuple[int, int], end: tuple[int, int], color: str, width: int = 7) -> None:
    draw = ImageDraw.Draw(base)
    draw.line((*start, *end), fill="#07080A", width=width + 7)
    draw.line((*start, *end), fill=color, width=width)
    ex, ey = end
    sx, sy = start
    dx, dy = ex - sx, ey - sy
    length = max(1.0, (dx * dx + dy * dy) ** .5)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    tip = (ex, ey)
    back = (ex - ux * 27, ey - uy * 27)
    draw.polygon((tip, (back[0] + px * 14, back[1] + py * 14), (back[0] - px * 14, back[1] - py * 14)), fill=color)


def _vignette(image: Image.Image, strength: int = 115) -> Image.Image:
    overlay = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((70, 55, image.width - 70, image.height - 55), fill=255)
    overlay = overlay.filter(ImageFilter.GaussianBlur(110))
    dark = Image.new("RGBA", image.size, (0, 0, 0, strength))
    dark.putalpha(ImageOps.invert(overlay).point(lambda value: int(value * strength / 255)))
    return Image.alpha_composite(image, dark)


def _render_candidate(
    index: int, backplate: Image.Image | None, identities: dict[str, tuple[dict[str, str], Image.Image]],
    panel_spec: dict[str, object] | None = None, headline_text: str = "SLACK FOR AI AGENTS?",
) -> tuple[Image.Image, list[dict[str, object]], str]:
    base = (
        ImageOps.fit(backplate, CANVAS, method=Image.Resampling.LANCZOS).convert("RGBA")
        if backplate is not None else _editorial_canvas(index)
    )
    if backplate is not None:
        base = _vignette(base, 135 if index < 3 else 70)
    placements: list[dict[str, object]] = []
    if panel_spec is not None:
        panel_spec = snap_panel_anchors(base, panel_spec) if backplate is not None else panel_spec
        headline_cfg = panel_spec.get("headline") or {}
        configured_lines = headline_cfg.get("lines") or []
        if len(configured_lines) == 2:
            line_one, line_two = str(configured_lines[0]), str(configured_lines[1])
        else:
            from .thumbnail_formula import split_headline
            line_one, line_two = split_headline(headline_text)
        headline = headline_text.upper()
        _headline(
            base, (line_one, line_two), left=int(headline_cfg.get("left", 48)),
            top=int(headline_cfg.get("top", 40)), width=int(headline_cfg.get("width", 700)), dark=bool(headline_cfg.get("dark", index != 3)),
        )
        for key, record in identities.items():
            panel = panel_spec.get(key)
            if not isinstance(panel, dict):
                continue
            if panel.get("badge"):
                placements.append(_identity_badge(
                    base, *record, (int(panel["x"]), int(panel["y"])),
                    int(panel.get("width") or panel.get("size") or 100),
                    int(panel.get("height") or 58),
                ))
            else:
                placements.append(_logo_on_blank_panel(
                    base, *record, (int(panel["x"]), int(panel["y"])), int(panel["size"]),
                ))
        return base, placements, headline
    buzz = identities["buzz"]
    openai = identities["openai"]
    claude = identities["claude"]
    if index == 0:
        headline = "SLACK FOR AI AGENTS?"
        _headline(base, ("SLACK FOR", "AI AGENTS?"), left=54, top=45, width=690)
        placements.append(_agent_body(base, *buzz, (940, 345), 360, body_color="#B56F55", dominant=True))
        placements.append(_agent_body(base, *openai, (245, 470), 205, body_color="#275EFF", lean=-14))
        placements.append(_agent_body(base, *claude, (505, 490), 205, body_color="#F0672A", lean=12))
        _connector(base, (330, 420), (725, 335), CYAN)
        _connector(base, (585, 440), (755, 370), ORANGE)
        draw = ImageDraw.Draw(base)
        draw.rounded_rectangle((838, 603, 1042, 653), radius=8, fill=(8, 9, 11, 235), outline=SLATE, width=2)
        draw.text((881, 614), "BUZZ", font=_font(27), fill="#FFFFFF")
    elif index == 1:
        headline = "WHO RUNS THE AGENTS?"
        _headline(base, ("WHO RUNS", "THE AGENTS?"), left=54, top=40, width=760)
        placements.append(_agent_body(base, *buzz, (640, 370), 275, body_color="#B56F55", dominant=True))
        placements.append(_agent_body(base, *openai, (260, 470), 275, body_color="#275EFF", lean=16))
        placements.append(_agent_body(base, *claude, (1020, 470), 275, body_color="#F0672A", lean=-16))
        _connector(base, (400, 420), (500, 390), CYAN, 8)
        _connector(base, (880, 420), (780, 390), ORANGE, 8)
    elif index == 2:
        headline = "THE NEW AGENT HQ"
        _headline(base, ("THE NEW", "AGENT HQ"), left=54, top=42, width=630)
        placements.append(_agent_body(base, *buzz, (850, 365), 350, body_color="#B56F55", dominant=True))
        placements.append(_agent_body(base, *openai, (320, 455), 190, body_color="#275EFF", lean=-8))
        placements.append(_agent_body(base, *claude, (540, 515), 190, body_color="#F0672A", lean=8))
        draw = ImageDraw.Draw(base)
        draw.arc((195, 250, 1020, 720), 150, 345, fill=SLATE, width=5)
        draw.arc((215, 272, 995, 700), 155, 340, fill=(255, 255, 255, 120), width=2)
    else:
        headline = "YOUR AI TEAM HAS A HOME"
        _headline(base, ("YOUR AI TEAM", "HAS A HOME"), left=52, top=42, width=720, dark=False)
        placements.append(_agent_body(base, *buzz, (440, 430), 300, body_color="#B56F55", dominant=True))
        placements.append(_agent_body(base, *openai, (900, 405), 185, body_color="#275EFF", lean=-8))
        placements.append(_agent_body(base, *claude, (1080, 500), 185, body_color="#F0672A", lean=8))
        _connector(base, (815, 405), (620, 410), BLUE)
        _connector(base, (995, 490), (625, 465), ORANGE)
    return base, placements, headline


def generate_identity_arena_package(brief: dict[str, object], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_set = build_identity_arena_prompts()
    identity_plates = brief.get("identity_plates")
    background_mode = str(brief.get("background_mode") or ("curated_identity_plates" if identity_plates else "deterministic_editorial"))
    panel_specs: list[dict[str, object] | None]
    if background_mode == "curated_identity_plates" and isinstance(identity_plates, list) and len(identity_plates) == 4:
        backplates = [Path(str(item["path"])).resolve() for item in identity_plates]
        missing = [str(path) for path in backplates if not path.exists()]
        if missing:
            raise FileNotFoundError("Missing identity plates: " + ", ".join(missing))
        panel_specs = [dict(item) for item in identity_plates]
        backplate_record = {
            "mode": "curated_identity_plates", "credits_used": 0,
            "source_paths": [str(path) for path in backplates],
            "logo_policy": "exact official marks composited after generation",
            "background_removal": "not used",
        }
    elif background_mode == "generated_identity_plates":
        plan = brief.get("identity_arena_plan")
        if not isinstance(plan, dict) or not isinstance(plan.get("candidates"), list) or len(plan["candidates"]) != 4:
            raise ValueError("generated identity plates require a four-candidate identity_arena_plan")
        planned_candidates = [dict(item) for item in plan["candidates"]]
        prompt_set = [
            {key: value for key, value in item.items() if key in {"style_mode", "archetype", "generation_mode", "prompt"}}
            for item in planned_candidates
        ]
        panel_specs = [dict(item["panel_spec"]) for item in planned_candidates]
        backplates, backplate_record = generate_magic_hour_backplates(
            [], output_dir, model=str(brief.get("backplate_model") or "nano-banana-2"),
            fallback_model=str(brief.get("backplate_fallback_model") or "nano-banana"),
            resolution=str(brief.get("backplate_resolution") or "2k"), prompt_set_override=prompt_set,
        )
    elif background_mode == "generated_backplate":
        backplates, backplate_record = generate_magic_hour_backplates(
            [], output_dir, model=str(brief.get("backplate_model") or "nano-banana-2"),
            fallback_model=str(brief.get("backplate_fallback_model") or "nano-banana"),
            resolution=str(brief.get("backplate_resolution") or "2k"), prompt_set_override=prompt_set,
        )
        panel_specs = [None] * 4
    else:
        backplates = [None] * 4
        panel_specs = [None] * 4
        backplate_record = {
            "mode": "deterministic_editorial",
            "credits_used": 0,
            "reason": "Exact art direction and clean brand edges outperform synthetic stage imagery for identity stories.",
        }
    keys = [str(key) for key in (brief.get("identity_keys") or ["buzz", "openai", "claude"])]
    records = resolve_brand_assets(keys, brand_root=DEFAULT_BRAND_ROOT)
    cache_dir = output_dir / ".brand-cache"
    identities = {record["key"]: (record, _load_brand_image(record, cache_dir)) for record in records}
    outputs: list[Path] = []
    candidates: list[dict[str, object]] = []
    hook_class = str((brief.get("route_decision") or {}).get("hook_class") or "")
    preferred_style = {
        "showdown": "equal_showdown",
        "control": "equal_showdown",
        "category_analogy": "coordinator_lineup",
        "coordination": "coordinator_lineup",
        "identity_consequence": "shared_home",
    }.get(hook_class, "coordinator_lineup")
    recommended_index = next(
        (index for index, item in enumerate(prompt_set) if item.get("style_mode") == preferred_style), 0,
    )
    preview_dir = output_dir / "mobile-previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for index, path in enumerate(backplates):
        plate = Image.open(path).convert("RGB") if path is not None else None
        image, placements, headline = _render_candidate(
            index, plate, identities, panel_specs[index], str(brief.get("headline") or "SLACK FOR AI AGENTS?"),
        )
        destination = output_dir / f"thumbnail_{index + 1}.jpg"
        preview = preview_dir / f"thumbnail_{index + 1}_320x180.jpg"
        image.convert("RGB").save(destination, quality=96, optimize=True)
        image.convert("RGB").resize((320, 180), Image.Resampling.LANCZOS).save(preview, quality=92)
        outputs.append(destination)
        candidates.append({
            "path": str(destination.resolve()), "mobile_preview": str(preview.resolve()),
            "headline": headline, "style_mode": prompt_set[index]["style_mode"],
            "hook_strategy": (
                str(panel_specs[index].get("hook_strategy"))
                if panel_specs[index] is not None and panel_specs[index].get("hook_strategy")
                else ("category analogy", "control question", "new category", "human consequence")[index]
            ),
            "brand_placements": placements, "required_logos": keys, "recommended": index == recommended_index,
        })
    requested_headline = str(brief.get("headline") or "SLACK FOR AI AGENTS?").upper()
    qc = validate_variants(outputs, requested_headline)
    manifest = {
        "schema_version": "thumbnail-identity-arena.v4", "algorithm_version": 14,
        "headline": requested_headline, "topic_context": brief.get("topic_context"),
        "represented_companies": keys, "resolved_brand_assets": records,
        "evidence_ids": brief.get("evidence_ids") or [], "asset_ids": brief.get("asset_ids") or [],
        "evidence_display_policy": "evidence-selects-hook-not-required-in-artwork",
        "generated_backplates": backplate_record, "recommended_candidate": recommended_index + 1,
        "recommended_style": preferred_style,
        "selection_policy": "hook-routed-mobile-readable-identity-hierarchy",
        "route_decision": brief.get("route_decision") or {},
        "identity_arena_plan": brief.get("identity_arena_plan") or {},
        "must_not_imply": brief.get("must_not_imply") or [], "human_review_required": True,
        "candidates": candidates,
    }
    (output_dir / "thumbnail_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "thumbnail_qc.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")
    if not qc["passed"]:
        raise ValueError("identity-arena thumbnails failed QC: " + "; ".join(qc["failures"]))
    return outputs
