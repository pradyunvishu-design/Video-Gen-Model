from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.editorial_style import draw_source_credit
from pipeline.youtube_broll_bundle import load_approved_youtube_broll_bundle


OUT = ROOT / "output" / "news_weekly_20260822"
VARIANT = os.environ.get("NEWS_WEEKLY_VARIANT", "earthy_v2").strip() or "earthy_v2"
CACHE = OUT / f"render_cache_{VARIANT}"
CARDS = CACHE / "cards"
SEGMENTS = CACHE / "segments"
SOURCES = OUT / "sources"
NARRATION = OUT / "audio" / "narration_master.m4a"
CAPTIONS = OUT / "captions_monochrome.ass"
FINAL = Path(os.environ.get("NEWS_WEEKLY_FINAL") or (OUT / "the_week_in_ai_2026-08-22_10min_review.mp4"))
FFROOT = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\tools\ffmpeg\bin")
FFMPEG = FFROOT / "ffmpeg.exe"
FFPROBE = FFROOT / "ffprobe.exe"

W, H = 1920, 1080
FPS = 30
SHOT_SECONDS = 6
EPISODE_ID = "episode_20260822_news_weekly"
YOUTUBE_BROLL_MANIFEST = OUT / "youtube_broll_bundle" / "approved_youtube_broll_manifest.json"
OPEN_BROLL_MANIFEST = OUT / "open_broll" / "approved_open_broll_manifest.json"

# One hundred six-second shots make the requested percentages exact.  The
# categories are a hard partition, so a missing YouTube clip cannot silently
# turn back into another generic graphic.
YOUTUBE_BROLL_SLOTS = {
    3, 4, 6, 7, 9, 10, 12, 13, 15, 16, 19,
    22, 23, 25, 26, 28, 29, 32, 33, 36, 37,
    39, 40, 42, 43, 46, 47, 50, 51,
    53, 54, 57, 58, 61, 62,
    64, 65, 67, 68, 70, 71, 73, 74, 76,
    78, 79, 81, 82, 84, 85, 87, 88, 90, 91, 93,
}
ARTICLE_SOURCE_SLOTS = {
    5, 8, 11, 14, 18, 21,
    24, 27, 30, 34, 38,
    66, 69, 72, 75, 77,
    80, 83, 86, 89,
}
MISC_EDITORIAL_SLOTS = {0, 1, 2, 17, 20, 31, 55, 95, 98, 99}
MOTION_GRAPHICS_SLOTS = set(range(100)) - YOUTUBE_BROLL_SLOTS - ARTICLE_SOURCE_SLOTS - MISC_EDITORIAL_SLOTS
assert len(YOUTUBE_BROLL_SLOTS) == 55
assert len(ARTICLE_SOURCE_SLOTS) == 20
assert len(MOTION_GRAPHICS_SLOTS) == 15
assert len(MISC_EDITORIAL_SLOTS) == 10
assert not (
    YOUTUBE_BROLL_SLOTS & ARTICLE_SOURCE_SLOTS
    or YOUTUBE_BROLL_SLOTS & MOTION_GRAPHICS_SLOTS
    or YOUTUBE_BROLL_SLOTS & MISC_EDITORIAL_SLOTS
    or ARTICLE_SOURCE_SLOTS & MOTION_GRAPHICS_SLOTS
    or ARTICLE_SOURCE_SLOTS & MISC_EDITORIAL_SLOTS
    or MOTION_GRAPHICS_SLOTS & MISC_EDITORIAL_SLOTS
)
YOUTUBE_BROLL_BY_SLOT: dict[int, dict] = {}
OPEN_BROLL_BY_SLOT: dict[int, dict] = {}

# Engagement revision: keep the real-evidence share at 55%, but stop pretending
# that a later timestamp from the same master is a fresh visual.  No open B-roll
# master is used more than three times.  The removed repeats become source-page
# proof sequences or animated editorial explanations.
ENGAGING_BROLL_SLOTS = {
    3, 4, 9, 13, 19,
    22, 23, 26, 33,
    39, 40, 42, 46, 51,
    53, 54, 57, 58,
    64, 65, 67, 68, 70, 73, 76,
    78, 79, 81, 84, 85, 87,
}
ENGAGING_ARTICLE_SLOTS = ARTICLE_SOURCE_SLOTS | {6, 25, 71, 88}
ENGAGING_MISC_SLOTS = MISC_EDITORIAL_SLOTS
ENGAGING_MOTION_SLOTS = set(range(100)) - ENGAGING_BROLL_SLOTS - ENGAGING_ARTICLE_SLOTS - ENGAGING_MISC_SLOTS
assert len(ENGAGING_BROLL_SLOTS) == 31
assert len(ENGAGING_ARTICLE_SLOTS) == 24
assert len(ENGAGING_MOTION_SLOTS) == 35
assert len(ENGAGING_MISC_SLOTS) == 10

PALETTES = {
    # Warm paper is the channel canvas. Brand hues are muted into an earthy
    # editorial system and appear only on identity/active explanatory marks.
    "intro": ("#EEE9DF", "#202824", "#B8674F", "#667A70"),
    "cyber": ("#E8EEE8", "#18251F", "#4D8B72", "#789D8C"),
    "computer_use": ("#F1E3D9", "#2B211C", "#C86E50", "#A98272"),
    "runway": ("#E5E9E8", "#202624", "#687F89", "#8A9996"),
    "chatgpt": ("#E6EEE9", "#18251F", "#3E846F", "#71998B"),
    "ports": ("#E7ECE7", "#20271F", "#6D8A61", "#879788"),
    "open_models": ("#EEE9E1", "#252724", "#6E8275", "#9B8B7C"),
    "outro": ("#EEE9DF", "#202824", "#B8674F", "#667A70"),
}

BRAND_SVGS = {
    "openai": ROOT / "remotion" / "public" / "brands" / "openai.svg",
    "anthropic": OUT / "brand" / "anthropic.svg",
    "nvidia": OUT / "brand" / "nvidia.svg",
    "huggingface": OUT / "brand" / "huggingface.svg",
}
BRAND_PNGS = {name: CACHE / "brand" / f"{name}.png" for name in BRAND_SVGS}

COPY = {
    "intro": [
        ("THE WEEK IN AI", "Six stories. Ten minutes. No filler.", "AUG 17—22"),
        ("AI CROSSED A LINE", "Models got more capable—and the guardrails got more serious.", "THIS WEEK"),
        ("THE BIG PICTURE", "Security, agents, video, platforms, infrastructure, open models.", "6 STORIES"),
    ],
    "cyber": [
        ("OPENAI HIT PAUSE", "Astra may meet OpenAI's Critical cyber threshold.", "2 WEEKS"),
        ("CAPABILITY ≠ DEPLOYMENT", "The powerful part is not the chatbot. It is the training loop behind it.", "ASTRA"),
        ("THE NEW BOTTLENECK", "Monitoring overhead is now part of frontier model development.", "~20%"),
        ("A REAL SAFETY BRAKE", "Deployment-focused reinforcement learning was paused—not just announced.", "ON HOLD"),
        ("ANTHROPIC PUSHES DEFENSE", "Mythos 5 reaches more defenders through Claude Security.", "$35M"),
        ("HUMANS STILL SIGN OFF", "Security patches require review before they land.", "REVIEW"),
        ("THE CYBER GAP", "Attack capability is rising. Defensive access has to keep up.", "RACE"),
        ("WHY THIS MATTERS", "Frontier labs are now pacing capability against operational control.", "CONTROL"),
    ],
    "computer_use": [
        ("CLAUDE GETS HANDS", "Computer use and browser use are now generally available.", "GA"),
        ("MULTI-ACTION TURNS", "One request can trigger a sequence of clicks, checks, and file operations.", "AGENTS"),
        ("SKILLS + FILES", "Reusable instructions and persistent files make workflows less brittle.", "API"),
        ("THE REAL TEST", "Can the agent recover when the webpage behaves differently than expected?", "RECOVERY"),
        ("FROM CHAT TO WORK", "The product is moving from answers toward completed tasks.", "DO"),
        ("32 → 13 MINUTES", "A customer example—not a universal benchmark.", "CASE STUDY"),
        ("LESS DEMO MAGIC", "Production agents need logs, retries, and clear boundaries.", "OPS"),
        ("THE NEW INTERFACE", "The browser is becoming an execution environment for AI.", "BROWSER"),
    ],
    "runway": [
        ("VIDEO ENTERS WORKFLOW", "Runway is selling repeatable production—not a one-off prompt box.", "ENTERPRISE"),
        ("USAGE, NOT NOVELTY", "The key signal is whether teams keep using the system after the demo.", "NRR >300%"),
        ("17× MORE USAGE", "A company-reported example from one Fortune 20 customer.", "CASE STUDY"),
        ("CONTROL WINS", "Brands care about consistency, approvals, and integration.", "WORKFLOW"),
        ("THE VIDEO STACK", "Generate → review → revise → publish.", "4 STEPS"),
        ("AI VIDEO GROWS UP", "The product battle is shifting from quality alone to production reliability.", "RELIABILITY"),
        ("THE HONEST CAVEAT", "These are Runway's own business figures.", "COMPANY DATA"),
    ],
    "chatgpt": [
        ("CHATGPT ADDS ADS", "Free and Go users in 31 European markets enter the test.", "31 MARKETS"),
        ("PAID STAYS AD-FREE", "The platform is separating subscription value from advertiser reach.", "FREE / GO"),
        ("TEEN DEFAULTS", "OpenAI also introduced a dedicated experience for younger users.", "SAFETY"),
        ("A PLATFORM MOMENT", "ChatGPT is starting to look like distribution, not just software.", "PLATFORM"),
        ("TRUST IS THE PRODUCT", "Ads and youth features raise the stakes for clear boundaries.", "TRUST"),
        ("THE BUSINESS SHIFT", "Monetization is moving closer to the conversation itself.", "ATTENTION"),
    ],
    "ports": [
        ("8 GIGAWATTS OF AI", "PORTS-Pike is infrastructure at power-plant scale.", "~8 GW-IT"),
        ("COMPUTE GETS PHYSICAL", "Data centers mean power, land, cooling, jobs, and community impact.", "OHIO"),
        ("35,000 CONSTRUCTION JOBS", "The project also projects 2,500 long-term roles.", "JOBS"),
        ("$40M IN GRANTS", "Community investment is part of the pitch.", "LOCAL"),
        ("$84M IN CODEX CREDITS", "Training access is being packaged alongside infrastructure.", "EDUCATION"),
        ("THE NEXT CONSTRAINT", "Models scale only if the physical system around them can scale too.", "POWER"),
        ("AI'S REAL FOOTPRINT", "The cloud is not weightless. It has an address.", "INFRA"),
    ],
    "open_models": [
        ("2.96M PUBLIC MODELS", "The open model ecosystem is enormous—and extremely concentrated.", "HUGGING FACE"),
        ("85.6% UNDER 200", "Most public repositories have fewer than 200 lifetime downloads.", "LONG TAIL"),
        ("1.5% → 99.2%", "A tiny share of repositories accounts for nearly all downloads.", "POWER LAW"),
        ("QWEN: 151,448", "One family generated a huge derivative ecosystem.", "DERIVATIVES"),
        ("SMALL MODELS, BIG USE", "Sub-1B models captured 83% of downloads among repos declaring parameters.", "<1B"),
        ("AGENTS ARE ARRIVING", "Traffic patterns show automation becoming a bigger part of model use.", "AGENTS"),
        ("OPEN DOESN'T MEAN EVEN", "Availability is broad. Attention is not.", "DISTRIBUTION"),
        ("THE WEEK'S SIGNAL", "AI is becoming more capable, operational, commercial, physical, and concentrated.", "ZOOM OUT"),
    ],
    "outro": [
        ("ONE WEEK. SIX SHIFTS.", "Capability, defense, agents, video, platforms, infrastructure.", "RECAP"),
        ("THE QUESTION", "Which change will matter most six months from now?", "YOUR TAKE"),
        ("THE WEEK IN AI", "Useful context. Clear evidence. No hype required.", "NEXT WEEK"),
    ],
}

SLOT_SECTIONS = (
    ["intro"] * 3 + ["cyber"] * 19 + ["computer_use"] * 17 + ["runway"] * 14
    + ["chatgpt"] * 11 + ["ports"] * 14 + ["open_models"] * 17 + ["outro"] * 5
)
assert len(SLOT_SECTIONS) == 100


def font(size: int, bold: bool = False, display: bool = False) -> ImageFont.FreeTypeFont:
    if display:
        path = Path(r"C:\Windows\Fonts\georgiab.ttf" if bold else r"C:\Windows\Fonts\georgia.ttf")
    else:
        path = Path(r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf")
    return ImageFont.truetype(str(path), size=size)


def hexrgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def wrap(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=face)[2] <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def noise_layer(seed: int, bg: tuple[int, int, int]) -> Image.Image:
    # Deterministic subtle paper/grain; no generative imagery.
    import random
    rng = random.Random(seed)
    image = Image.new("RGB", (W, H), bg)
    pixels = image.load()
    for _ in range(25000):
        x, y = rng.randrange(W), rng.randrange(H)
        shift = rng.choice((-5, -3, 3, 5))
        pixels[x, y] = tuple(max(0, min(255, c + shift)) for c in bg)
    return image


def ensure_brand_pngs() -> None:
    (CACHE / "brand").mkdir(parents=True, exist_ok=True)
    # Reuse already rasterized official marks across variants.  Rasterization
    # is deterministic and should not make a fresh render depend on Playwright.
    for name, destination in BRAND_PNGS.items():
        if destination.exists():
            continue
        prior = next(iter(sorted(OUT.glob(f"render_cache_*/brand/{name}.png"))), None)
        if prior and prior.exists():
            shutil.copy2(prior, destination)
    pending = [(name, source, BRAND_PNGS[name]) for name, source in BRAND_SVGS.items() if source.exists() and not BRAND_PNGS[name].exists()]
    if not pending:
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 420, "height": 420}, device_scale_factor=2)
        for _, source, destination in pending:
            svg_markup = source.read_text(encoding="utf-8")
            page.set_content(
                f"<style>html,body{{margin:0;width:100%;height:100%;background:transparent;display:grid;place-items:center}}"
                f"svg{{width:340px;height:340px}}</style>{svg_markup}"
            )
            page.screenshot(path=str(destination), omit_background=True)
        browser.close()


def paste_brand(image: Image.Image, name: str, center: tuple[int, int], size: int = 126) -> None:
    source = BRAND_PNGS.get(name)
    if not source or not source.exists():
        return
    with Image.open(source).convert("RGBA") as logo:
        logo.thumbnail((size, size), Image.Resampling.LANCZOS)
        image.alpha_composite(logo, (center[0] - logo.width // 2, center[1] - logo.height // 2))


def draw_browser(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], accent: tuple[int, int, int], ink: tuple[int, int, int], slot: int) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=34, fill=(255, 253, 248, 238), outline=(*ink, 50), width=3)
    draw.rounded_rectangle((x1, y1, x2, y1 + 72), radius=34, fill=(238, 233, 223, 255))
    draw.rectangle((x1, y1 + 36, x2, y1 + 72), fill=(238, 233, 223, 255))
    for index, color in enumerate(((190, 104, 82), (204, 165, 88), (101, 145, 116))):
        draw.ellipse((x1 + 28 + index * 32, y1 + 25, x1 + 44 + index * 32, y1 + 41), fill=color)
    draw.rounded_rectangle((x1 + 150, y1 + 20, x2 - 30, y1 + 50), radius=15, fill=(217, 214, 204))
    draw.rounded_rectangle((x1 + 42, y1 + 112, x1 + 310, y2 - 40), radius=24, fill=(*accent, 34))
    for row in range(4):
        yy = y1 + 130 + row * 92
        draw.rounded_rectangle((x1 + 360, yy, x2 - 55, yy + 48), radius=18, fill=(*ink, 20 + row * 5))
    cx = x2 - 160 - (slot % 3) * 55
    cy = y2 - 130 - (slot % 2) * 45
    draw.polygon([(cx, cy), (cx + 32, cy + 76), (cx + 49, cy + 51), (cx + 84, cy + 83), (cx + 104, cy + 62), (cx + 69, cy + 31)], fill=accent)


def draw_story_illustration(image: Image.Image, draw: ImageDraw.ImageDraw, section: str, slot: int,
                            accent: tuple[int, int, int], soft: tuple[int, int, int], ink: tuple[int, int, int]) -> None:
    if section in {"intro", "outro"}:
        for (cx, cy), brand in zip(((1230, 405), (1510, 520), (1240, 690)), ("openai", "anthropic", "huggingface")):
            draw.ellipse((cx - 105, cy - 105, cx + 105, cy + 105), fill=(255, 253, 248, 225), outline=(*ink, 42), width=3)
            paste_brand(image, brand, (cx, cy), 116)
        draw.line((1335, 440, 1405, 478), fill=accent, width=6)
        draw.line((1405, 592, 1345, 652), fill=accent, width=6)
    elif section == "cyber":
        cx, cy = 1450, 530
        shield = [(cx, cy - 235), (cx + 210, cy - 145), (cx + 170, cy + 135), (cx, cy + 250), (cx - 170, cy + 135), (cx - 210, cy - 145)]
        draw.polygon(shield, fill=(*accent, 55), outline=accent)
        draw.line((cx, cy - 130, cx, cy + 110), fill=ink, width=18)
        draw.line((cx - 110, cy - 10, cx + 110, cy - 10), fill=ink, width=18)
        paste_brand(image, "openai" if slot % 2 == 0 else "anthropic", (cx, cy), 118)
    elif section == "computer_use":
        draw_browser(draw, (1050, 270, 1805, 795), accent, ink, slot)
        draw.ellipse((925, 650, 1125, 850), fill=(255, 253, 248, 235), outline=(*ink, 42), width=3)
        paste_brand(image, "anthropic", (1025, 750), 98)
    elif section == "runway":
        x1, y1, x2, y2 = 1030, 300, 1810, 780
        draw.rounded_rectangle((x1, y1, x2, y2), radius=44, fill=(255, 253, 248, 232), outline=(*ink, 45), width=3)
        for x in range(x1 + 32, x2 - 20, 82):
            draw.rounded_rectangle((x, y1 + 25, x + 42, y1 + 58), radius=8, fill=(*accent, 120))
            draw.rounded_rectangle((x, y2 - 58, x + 42, y2 - 25), radius=8, fill=(*accent, 120))
        draw.polygon([(1365, 410), (1365, 680), (1590, 545)], fill=accent)
        draw.text((1240, 810), "RUNWAY", font=font(44, True), fill=ink)
    elif section == "chatgpt":
        draw.rounded_rectangle((1070, 300, 1785, 735), radius=68, fill=(255, 253, 248, 235), outline=(*ink, 45), width=3)
        draw.polygon([(1220, 735), (1160, 845), (1340, 735)], fill=(255, 253, 248, 235))
        paste_brand(image, "openai", (1428, 500), 170)
        draw.rounded_rectangle((1555, 650, 1800, 810), radius=28, fill=accent)
        draw.ellipse((1625, 680, 1730, 785), outline=(255, 253, 248), width=8)
        draw.line((1677, 706, 1677, 758), fill=(255, 253, 248), width=8)
    elif section == "ports":
        for index in range(3):
            x = 1080 + index * 230
            draw.rounded_rectangle((x, 345, x + 175, 760), radius=24, fill=(255, 253, 248, 228), outline=(*ink, 50), width=3)
            for row in range(5):
                draw.rounded_rectangle((x + 28, 395 + row * 63, x + 147, 425 + row * 63), radius=10, fill=(*accent, 70 + row * 20))
        draw.line((1080, 820, 1715, 820), fill=accent, width=8)
        draw.polygon([(1730, 820), (1696, 799), (1696, 841)], fill=accent)
        draw.ellipse((1640, 160, 1810, 330), fill=(255, 253, 248, 235), outline=(*ink, 40), width=3)
        paste_brand(image, "nvidia", (1725, 245), 100)
    elif section == "open_models":
        nodes = [(1110, 380), (1380, 260), (1660, 405), (1200, 690), (1500, 720), (1780, 650)]
        for a, b in zip(nodes, nodes[1:]):
            draw.line((*a, *b), fill=soft, width=5)
        for index, (cx, cy) in enumerate(nodes):
            radius = 74 if index else 118
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(255, 253, 248, 235), outline=accent, width=4)
        paste_brand(image, "huggingface", nodes[0], 130)
        for index, height in enumerate((48, 74, 112, 175, 280)):
            x = 1290 + index * 95
            draw.rounded_rectangle((x, 900 - height, x + 54, 900), radius=12, fill=(*accent, 90 + index * 30))


def draw_card(section: str, slot: int, destination: Path) -> None:
    bg_hex, fg_hex, accent_hex, soft_hex = PALETTES[section]
    bg, fg, accent, soft = map(hexrgb, (bg_hex, fg_hex, accent_hex, soft_hex))
    image = noise_layer(slot + 71, bg).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    title, body, metric = COPY[section][slot % len(COPY[section])]

    # Quiet editorial canvas: warm paper, subtle organic fields, one active hue.
    draw.ellipse((1180, -250, 2130, 650), fill=(*accent, 24))
    draw.ellipse((930, 625, 1530, 1225), fill=(*soft, 16))
    draw.line((74, 76, 1846, 76), fill=(*fg, 38), width=2)
    draw.text((76, 100), "THE WEEK IN AI", font=font(22, True), fill=fg)
    draw.text((1620, 100), "AUG 17—22 · 2026", font=font(20), fill=soft)
    section_name = {
        "intro": "WEEKLY BRIEFING", "cyber": "OPENAI + ANTHROPIC", "computer_use": "ANTHROPIC",
        "runway": "RUNWAY", "chatgpt": "OPENAI", "ports": "OPENAI + NVIDIA",
        "open_models": "HUGGING FACE", "outro": "WEEKLY BRIEFING",
    }[section]
    draw.text((76, 184), section_name, font=font(20, True), fill=accent)
    draw.line((76, 225, 300, 225), fill=accent, width=4)

    y = 300
    title_face = font(78 if len(title) < 23 else 65, True, display=True)
    for line in wrap(draw, title, title_face, 790)[:3]:
        draw.text((76, y), line, font=title_face, fill=fg)
        y += 88 if len(title) < 23 else 76
    draw.text((78, min(625, y + 22)), metric, font=font(30, True), fill=accent)
    body_y = min(700, y + 94)
    for line in wrap(draw, body, font(34), 790)[:3]:
        draw.text((78, body_y), line, font=font(34), fill=soft)
        body_y += 47

    draw_story_illustration(image, draw, section, slot, accent, soft, fg)
    draw.line((76, 975, 1844, 975), fill=(*fg, 38), width=2)
    draw.text((76, 1000), "SOURCE-BACKED WEEKLY BRIEFING", font=font(18, True), fill=soft)
    draw.text((1775, 997), f"{slot + 1:02d}", font=font(22, True), fill=accent)
    image.convert("RGB").save(destination, quality=96)


def draw_motion_base(section: str, slot: int, destination: Path) -> None:
    """Quiet canvas used underneath staged card-region reveals."""
    bg_hex, fg_hex, accent_hex, soft_hex = PALETTES[section]
    bg, fg, accent, soft = map(hexrgb, (bg_hex, fg_hex, accent_hex, soft_hex))
    image = noise_layer(slot + 71, bg).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse((1180, -250, 2130, 650), fill=(*accent, 24))
    draw.ellipse((930, 625, 1530, 1225), fill=(*soft, 16))
    draw.line((74, 76, 1846, 76), fill=(*fg, 38), width=2)
    draw.text((76, 100), "THE WEEK IN AI", font=font(22, True), fill=fg)
    draw.text((1620, 100), "AUG 17—22 · 2026", font=font(20), fill=soft)
    draw.line((76, 975, 1844, 975), fill=(*fg, 38), width=2)
    draw.text((76, 1000), "SOURCE-BACKED WEEKLY BRIEFING", font=font(18, True), fill=soft)
    draw.text((1775, 997), f"{slot + 1:02d}", font=font(22, True), fill=accent)
    image.convert("RGB").save(destination, quality=96)


def draw_editorial_overlay(section: str, slot: int, source_name: str, destination: Path, *, headline: bool) -> None:
    """Create one restrained editorial overlay—never a generic 'B-roll' label."""
    _, fg_hex, accent_hex, _ = PALETTES[section]
    fg, accent = hexrgb(fg_hex), hexrgb(accent_hex)
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    if headline:
        title = COPY[section][slot % len(COPY[section])][0]
        face = font(38 if len(title) < 25 else 34, True, display=True)
        lines = wrap(draw, title, face, 560)[:2]
        height = 46 * len(lines) + 32
        draw.rounded_rectangle((42, 48, 650, 48 + height), radius=16, fill=(12, 15, 14, 202))
        draw.rectangle((42, 48, 48, 48 + height), fill=accent)
        yy = 62
        for line in lines:
            draw.text((76, yy), line, font=face, fill=(248, 247, 242, 255))
            yy += 46
    draw_source_credit(
        draw, source_name, label_font=font(13, True),
        publisher_font=font(18, True), x=42, y=996,
    )
    image.save(destination)


def source_candidates(section: str) -> list[Path]:
    patterns = {
        "cyber": ["anthropic_mythos_defense*viewport.png", "anthropic_mythos_defense*recording-01.mp4"],
        "computer_use": ["anthropic_computer_use*viewport.png", "anthropic_computer_use*recording-01.mp4"],
        "ports": ["nvidia_ports_pike*viewport.png", "nvidia_ports_pike*full.png"],
        "open_models": ["hf_open_models_report*viewport.png", "hf_open_models_report*full.png"],
    }
    found: list[Path] = []
    for pattern in patterns.get(section, []):
        found.extend(SOURCES.glob(pattern))
    return found


# Curated source beats for the final B-roll revision. Video clips are never
# repeated; long first-party source records may appear twice only at distinct
# evidence depths. Slots without a clean, relevant source remain deterministic
# editorial motion rather than falling back to generic stock or blocked pages.
CURATED_SOURCE_PLAN = {
    6: "anthropic_mythos_defense*full.png",
    5: "anthropic_mythos_defense*recording-01.mp4",
    8: "anthropic_mythos_defense*viewport.png",
    11: "anthropic_mythos_defense*full.png",
    14: "anthropic_mythos_defense*full.png",
    18: "anthropic_mythos_defense*viewport.png",
    21: "anthropic_mythos_defense*recording-01.mp4",
    24: "anthropic_computer_use*recording-01.mp4",
    25: "anthropic_computer_use*full.png",
    27: "anthropic_computer_use*viewport.png",
    30: "anthropic_computer_use*full.png",
    34: "anthropic_computer_use*full.png",
    38: "anthropic_computer_use*viewport.png",
    66: "nvidia_ports_pike*viewport.png",
    69: "nvidia_ports_pike*full.png",
    71: "nvidia_ports_pike*full.png",
    72: "nvidia_ports_pike*full.png",
    75: "nvidia_ports_pike*viewport.png",
    77: "nvidia_ports_pike*full.png",
    80: "hf_open_models_report*viewport.png",
    83: "hf_open_models_report*full.png",
    86: "hf_open_models_report*full.png",
    88: "hf_open_models_report*full.png",
    89: "hf_open_models_report*viewport.png",
}


def curated_source(slot: int) -> Path | None:
    pattern = CURATED_SOURCE_PLAN.get(slot)
    if not pattern:
        return None
    return next(iter(sorted(SOURCES.glob(pattern))), None)


def load_open_broll_bundle(path: Path) -> dict[int, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("episode_id") != EPISODE_ID:
        raise ValueError("open B-roll manifest belongs to a different episode")
    records = {int(item["slot"]): item for item in payload.get("clips", [])}
    if set(records) != YOUTUBE_BROLL_SLOTS:
        raise ValueError("open B-roll manifest does not cover the 55 real-footage slots")
    for slot, item in records.items():
        media = Path(item["media_file"])
        if not media.exists() or media.stat().st_size < 100_000:
            raise FileNotFoundError(f"missing B-roll media for slot {slot}: {media}")
        if item.get("qc_status") not in {"passed_manual_thumbnail_review", "passed_in_prior_episode_review"}:
            raise ValueError(f"B-roll slot {slot} has not passed visual review")
        if item.get("rights_status") != "reviewed_for_private_preview":
            raise ValueError(f"B-roll slot {slot} has no usable rights record")
    return records


def is_engaging_variant() -> bool:
    return VARIANT.startswith("engaging_mix")


def render_animated_card(section: str, slot: int, card: Path, destination: Path) -> None:
    """Staged semantic reveal: premise, evidence illustration, then emphasis."""
    base = CARDS / f"{slot:03d}_{section}_base.png"
    if not base.exists():
        draw_motion_base(section, slot, base)
    accent = PALETTES[section][2]
    filter_graph = (
        "[0:v]scale=1920:1080,format=rgba[base];"
        "[1:v]crop=880:720:55:165,format=rgba,fade=t=in:st=0.08:d=0.42:alpha=1[left];"
        "[2:v]crop=970:790:940:145,format=rgba,fade=t=in:st=0.58:d=0.48:alpha=1[right];"
        "[base][left]overlay=x='35+20*min(t/0.5,1)':y=165:shortest=1[one];"
        "[one][right]overlay=x='960-20*(1-min(max((t-0.55)/0.55,0),1))':y=145:shortest=1[two];"
        f"[two]drawbox=x=76:y=225:w='224*min(max((t-1.05)/0.45,0),1)':h=4:color={accent}:t=fill,"
        "fade=t=out:st=5.76:d=0.24,format=yuv420p[v]"
    )
    args = [
        FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-i", base, "-loop", "1", "-i", card, "-loop", "1", "-i", card,
        "-filter_complex", filter_graph, "-map", "[v]", "-t", str(SHOT_SECONDS), "-an",
        "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-g", "60", "-sc_threshold", "0", destination,
    ]
    subprocess.run([str(value) for value in args], check=True)


def render_source_sequence(section: str, slot: int, source: Path, destination: Path) -> None:
    source_name = {
        "cyber": "Anthropic", "computer_use": "Anthropic", "ports": "NVIDIA", "open_models": "Hugging Face",
    }.get(section, "Official source")
    overlay = CARDS / f"{slot:03d}_{section}_source_overlay_neutral_v3.png"
    if not overlay.exists():
        draw_editorial_overlay(section, slot, source_name, overlay, headline=True)
    video_exts = {".mp4", ".mov", ".mkv", ".webm", ".ogv", ".avi"}
    if source.suffix.lower() in video_exts:
        input_args = ["-stream_loop", "-1", "-i", source]
        base_filter = "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=rgba[base]"
    else:
        with Image.open(source) as im:
            sw, sh = im.size
        scaled_h = max(1080, round(sh * 1920 / sw))
        max_y = max(0, scaled_h - 1080)
        start_y = int(max_y * ((slot % 4) / 7))
        end_y = min(max_y, start_y + min(520, max_y // 3))
        input_args = ["-loop", "1", "-i", source]
        if max_y:
            # Land on the evidence before the shot begins. Article shots are
            # proof frames, not recordings of the editor looking for the line.
            base_filter = (
                f"[0:v]scale=1920:{scaled_h},crop=1920:1080:0:{end_y},"
                "fps=30,format=rgba[base]"
            )
        else:
            base_filter = "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=rgba[base]"
    filter_graph = (
        base_filter + ";"
        "[1:v]format=rgba,fade=t=in:st=0.45:d=0.35:alpha=1[ol];"
        "[base][ol]overlay=0:0:shortest=1,fade=t=out:st=5.78:d=0.22,format=yuv420p[v]"
    )
    args = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *input_args,
            "-loop", "1", "-i", overlay, "-filter_complex", filter_graph, "-map", "[v]",
            "-t", str(SHOT_SECONDS), "-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "18", "-g", "60", "-sc_threshold", "0", destination]
    subprocess.run([str(value) for value in args], check=True)


def render_broll_with_context(section: str, slot: int, record: dict, destination: Path) -> None:
    source = Path(record["media_file"])
    publisher = record.get("publisher", record.get("channel", "Source"))
    overlay = CARDS / f"{slot:03d}_{section}_broll_overlay_neutral_v3.png"
    if not overlay.exists():
        draw_editorial_overlay(section, slot, publisher, overlay, headline=(slot % 2 == 0))
    filter_graph = (
        "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,unsharp=3:3:0.35,fps=30,format=rgba[base];"
        "[1:v]format=rgba,fade=t=in:st=0.35:d=0.28:alpha=1,fade=t=out:st=5.55:d=0.3:alpha=1[ol];"
        "[base][ol]overlay=0:0:shortest=1,format=yuv420p[v]"
    )
    args = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(record["source_start_seconds"]),
            "-stream_loop", "-1", "-i", source, "-loop", "1", "-i", overlay,
            "-filter_complex", filter_graph, "-map", "[v]", "-t", str(SHOT_SECONDS), "-an",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-g", "60", "-sc_threshold", "0", destination]
    subprocess.run([str(value) for value in args], check=True)


def render_segment(slot: int, section: str, card: Path, destination: Path) -> dict:
    broll_record = None
    if VARIANT.startswith("youtube_mix"):
        broll_record = YOUTUBE_BROLL_BY_SLOT.get(slot)
    elif VARIANT.startswith("licensed_mix") or is_engaging_variant():
        broll_record = OPEN_BROLL_BY_SLOT.get(slot)
        if is_engaging_variant() and slot not in ENGAGING_BROLL_SLOTS:
            broll_record = None
    if broll_record:
        source = Path(broll_record["media_file"])
        use_source = True
        kind = "reviewed_broll" if is_engaging_variant() else ("licensed_broll" if VARIANT.startswith("licensed_mix") else "youtube_broll")
    elif (VARIANT.startswith("youtube_mix") or VARIANT.startswith("licensed_mix") or is_engaging_variant()) and slot in (ENGAGING_ARTICLE_SLOTS if is_engaging_variant() else ARTICLE_SOURCE_SLOTS):
        source = curated_source(slot)
        if source is None:
            raise FileNotFoundError(f"article source is missing for slot {slot}")
        use_source = True
        kind = "article_source"
    elif VARIANT.startswith("youtube_mix") or VARIANT.startswith("licensed_mix") or is_engaging_variant():
        source = card
        use_source = False
        kind = "misc_editorial" if slot in (ENGAGING_MISC_SLOTS if is_engaging_variant() else MISC_EDITORIAL_SLOTS) else "motion_graphics"
    elif VARIANT.startswith("earthy_broll"):
        source = curated_source(slot) or card
        use_source = source != card
        kind = "official_broll" if use_source else "motion"
    else:
        sources = source_candidates(section)
        # Insert real first-party pages/recordings at a restrained cadence.
        use_source = bool(sources) and slot % 4 == 2
        source = sources[(slot // 4) % len(sources)] if use_source else card
        kind = "official_broll" if use_source else "motion"
    if destination.exists() and destination.stat().st_size > 200_000:
        record = {"slot": slot, "section": section, "kind": kind, "source": str(source), "file": str(destination), "cached": True}
        if broll_record:
            record.update({
                "source_url": broll_record["source_url"],
                "source_start_seconds": broll_record["source_start_seconds"],
                "source_end_seconds": broll_record["source_end_seconds"],
                "title": broll_record["title"],
                "publisher": broll_record.get("publisher", broll_record.get("channel", "Source")),
                "creator": broll_record.get("creator", ""),
                "license": broll_record.get("license", ""),
                "semantic_target": broll_record.get("semantic_target", ""),
                "rights_basis": broll_record["rights_basis"],
                "rights_status": broll_record["rights_status"],
            })
        return record
    destination.parent.mkdir(parents=True, exist_ok=True)
    if is_engaging_variant() and broll_record:
        render_broll_with_context(section, slot, broll_record, destination)
        args = None
    elif is_engaging_variant() and kind == "article_source":
        render_source_sequence(section, slot, source, destination)
        args = None
    elif is_engaging_variant() and kind in {"motion_graphics", "misc_editorial"}:
        render_animated_card(section, slot, card, destination)
        args = None
    elif broll_record:
        args = [
            FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", str(broll_record["source_start_seconds"]), "-stream_loop", "-1", "-i", source,
            "-t", str(SHOT_SECONDS), "-an", "-vf",
            "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p",
        ]
    elif source.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".ogv", ".avi"}:
        args = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-stream_loop", "-1", "-i", source,
                "-t", str(SHOT_SECONDS), "-an", "-vf",
                "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p"]
    else:
        # Tall full-page captures are cropped at a deterministic vertical depth.
        with Image.open(source) as im:
            sw, sh = im.size
        if sh > H * 1.6:
            max_y = max(0, sh - H)
            y = int(max_y * ((slot % 5) / 4))
            crop = f"crop=1920:1080:0:{y},"
        else:
            crop = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
        args = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", source,
                "-t", str(SHOT_SECONDS), "-an", "-vf", f"{crop}fps=30,format=yuv420p"]
    if args is not None:
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-g", "60", "-sc_threshold", "0", destination]
        subprocess.run([str(value) for value in args], check=True)
    record = {"slot": slot, "section": section, "kind": kind, "source": str(source), "file": str(destination)}
    if broll_record:
        record.update({
            "source_url": broll_record["source_url"],
            "source_start_seconds": broll_record["source_start_seconds"],
            "source_end_seconds": broll_record["source_end_seconds"],
            "title": broll_record["title"],
            "publisher": broll_record.get("publisher", broll_record.get("channel", "Source")),
            "creator": broll_record.get("creator", ""),
            "license": broll_record.get("license", ""),
            "semantic_target": broll_record.get("semantic_target", ""),
            "rights_basis": broll_record["rights_basis"],
            "rights_status": broll_record["rights_status"],
        })
    return record


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    global YOUTUBE_BROLL_BY_SLOT, OPEN_BROLL_BY_SLOT
    for required in (FFMPEG, FFPROBE):
        if not required.exists():
            raise FileNotFoundError(required)
    if VARIANT.startswith("youtube_mix"):
        YOUTUBE_BROLL_BY_SLOT = load_approved_youtube_broll_bundle(
            YOUTUBE_BROLL_MANIFEST,
            expected_slots=YOUTUBE_BROLL_SLOTS,
            episode_id=EPISODE_ID,
        )
    elif VARIANT.startswith("licensed_mix") or is_engaging_variant():
        OPEN_BROLL_BY_SLOT = load_open_broll_bundle(OPEN_BROLL_MANIFEST)
    CARDS.mkdir(parents=True, exist_ok=True)
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    ensure_brand_pngs()
    for slot, section in enumerate(SLOT_SECTIONS):
        card = CARDS / f"{slot:03d}_{section}.png"
        if not card.exists():
            draw_card(section, slot, card)

    ledger: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, os.cpu_count() or 4))) as pool:
        futures = []
        for slot, section in enumerate(SLOT_SECTIONS):
            card = CARDS / f"{slot:03d}_{section}.png"
            destination = SEGMENTS / f"{slot:03d}_{section}.mp4"
            futures.append(pool.submit(render_segment, slot, section, card, destination))
        for future in as_completed(futures):
            ledger.append(future.result())
    ledger.sort(key=lambda item: item["slot"])
    (OUT / "shot_ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    if "--prebuild" in sys.argv:
        print(json.dumps({"prebuilt_shots": len(ledger), "source_shots": sum(item["kind"] == "official_broll" for item in ledger)}, indent=2))
        return

    for required in (NARRATION, CAPTIONS):
        if not required.exists():
            raise FileNotFoundError(required)

    concat = CACHE / "timeline.concat.txt"
    concat.write_text("".join(f"file '{Path(item['file']).resolve().as_posix()}'\n" for item in ledger), encoding="utf-8")
    visuals = CACHE / "visuals_600s.mp4"
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-c", "copy", "-t", "600", str(visuals)], check=True)
    # Captions are intentionally monochrome: white text, black outline/shadow.
    ass_path = str(CAPTIONS.resolve()).replace("\\", "/").replace(":", "\\:")
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-i", str(visuals), "-i", str(NARRATION),
                    "-vf", f"ass='{ass_path}'", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "medium",
                    "-b:v", "2000k", "-minrate", "2000k", "-maxrate", "2000k", "-bufsize", "4000k",
                    "-x264-params", "nal-hrd=cbr:force-cfr=1:filler=1",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-t", "600", "-movflags", "+faststart", str(FINAL)], check=True)
    manifest = {
        "title": "AI Crossed a Line This Week", "show": "THE WEEK IN AI",
        "duration_seconds": 600, "resolution": "1920x1080", "fps": 30,
        "publishing_enabled": False, "final": str(FINAL), "sha256": sha256(FINAL),
        "visual_policy": (
            "55% script-matched rights-cleared YouTube B-roll, 20% article/source evidence, "
            "15% motion graphics, 10% miscellaneous editorial visuals"
            if VARIANT.startswith("youtube_mix") else
            "55% reviewed official/open B-roll, 20% article/source evidence, "
            "15% motion graphics, 10% miscellaneous editorial visuals"
            if VARIANT.startswith("licensed_mix") else
            "31% distinct reviewed open B-roll, 24% moving source evidence, "
            "35% animated editorial explanation, 10% chapter/editorial visuals"
            if is_engaging_variant() else
            "real first-party pages plus deterministic editorial graphics; no AI-generated stills"
        ),
        "subtitle_policy": "white bold text with black outline and shadow",
        "transition_policy": "clean editorial hard cuts; no dip-to-black, spin, orbit, or camera shake",
        "company_accents": {name: values[2] for name, values in PALETTES.items()},
        "shot_count": len(ledger),
        "source_shots": sum(item["kind"] in {"official_broll", "article_source"} for item in ledger),
        "motion_shots": sum(item["kind"] in {"motion", "motion_graphics"} for item in ledger),
        "visual_mix": {
            kind: sum(item["kind"] == kind for item in ledger)
            for kind in (("reviewed_broll", "article_source", "motion_graphics", "misc_editorial")
                         if is_engaging_variant() else
                         ("licensed_broll", "article_source", "motion_graphics", "misc_editorial")
                         if VARIANT.startswith("licensed_mix") else
                         ("youtube_broll", "article_source", "motion_graphics", "misc_editorial"))
        } if (VARIANT.startswith("youtube_mix") or VARIANT.startswith("licensed_mix") or is_engaging_variant()) else {},
        "shot_ledger": ledger,
    }
    (OUT / "render_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "shot_ledger"}, indent=2))


if __name__ == "__main__":
    main()
