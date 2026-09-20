"""Shared premium editorial color and source-credit primitives."""
from __future__ import annotations

import re
from typing import Any


CANVAS = "#111311"
PAPER = "#F1F2EE"
MUTED = "#A8AFAB"
LINE = "#3E4541"
SURFACE = "#181B19"
SLATE = "#83938C"
CLAY = "#B56F55"
MOSS = "#667C6D"

# These colors may remain inside an unmodified official logo asset. They may
# not be reused as editorial accents, source dots, captions, cards, or glow.
FORBIDDEN_EDITORIAL_HEX = {
    "#E8E32D", "#EAF21D", "#FFD21E", "#FFD24A", "#FFD51F", "#FFD84D", "#F5D547",
    "#A855F7", "#8B5CF6", "#7C3AED", "#9333EA", "#FF3B9D",
}


def is_forbidden_editorial_color(value: Any) -> bool:
    return str(value or "").strip().upper() in FORBIDDEN_EDITORIAL_HEX


def safe_editorial_accent(value: str | None, *, fallback: str = SLATE) -> str:
    return fallback if is_forbidden_editorial_color(value) else str(value or fallback)


def draw_source_credit(
    draw: Any,
    publisher: str,
    *,
    label_font: Any,
    publisher_font: Any,
    x: int = 42,
    y: int = 996,
) -> tuple[int, int, int, int]:
    """Draw a restrained newsroom credit: no dot, pill, glow, or brand tint."""
    clean = re.sub(r"\s+", " ", str(publisher or "Primary source")).strip()
    prefix = "SOURCE"
    prefix_box = draw.textbbox((0, 0), prefix, font=label_font)
    publisher_box = draw.textbbox((0, 0), clean, font=publisher_font)
    prefix_width = prefix_box[2] - prefix_box[0]
    publisher_width = publisher_box[2] - publisher_box[0]
    width = 18 + prefix_width + 18 + 1 + 18 + publisher_width + 20
    height = 48
    box = (x, y, x + width, y + height)
    draw.rectangle(box, fill=(14, 17, 15, 224))
    draw.line((x, y, x + width, y), fill=(124, 137, 130, 160), width=1)
    draw.rectangle((x, y, x + 3, y + height), fill=(131, 147, 140, 255))
    baseline = y + 14
    draw.text((x + 18, baseline), prefix, font=label_font, fill=(168, 175, 171, 255))
    separator_x = x + 18 + prefix_width + 18
    draw.line((separator_x, y + 11, separator_x, y + height - 11), fill=(92, 101, 96, 210), width=1)
    draw.text((separator_x + 18, baseline - 1), clean, font=publisher_font, fill=(241, 242, 238, 255))
    return box
