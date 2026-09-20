from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import build_news_weekly_20260822_video as episode

OUT = ROOT / "output" / "news_weekly_20260822"
DEST = OUT / "custom_motion_v3"
FFMPEG = episode.FFMPEG
W, H, FPS, SECONDS = 1920, 1080, 30, 6

BLACK = "#090A0A"
PAPER = "#F2F1ED"
PANEL = "#171818"
PANEL_2 = "#202121"
LINE = "#343636"
MUTED = "#929795"
SLATE = "#83938C"
RED = "#D96558"
GREEN = "#54A878"
BLUE = "#6D8DFF"

SECTION_ACCENT = {
    "intro": SLATE,
    "cyber": "#10A37F",
    "computer_use": "#D97757",
    "runway": PAPER,
    "chatgpt": "#10A37F",
    "ports": "#76B900",
    "open_models": SLATE,
    "outro": SLATE,
}

LOGOS = {
    "cyber": OUT / "render_cache_engaging_mix_v2" / "brand" / "openai.png",
    "computer_use": OUT / "render_cache_engaging_mix_v2" / "brand" / "anthropic.png",
    "chatgpt": OUT / "render_cache_engaging_mix_v2" / "brand" / "openai.png",
    "ports": OUT / "render_cache_engaging_mix_v2" / "brand" / "nvidia.png",
    "open_models": OUT / "render_cache_engaging_mix_v2" / "brand" / "huggingface.png",
}

# One-use editorial layouts for the balanced cut.  No layout below appears
# twice in the final episode.
FORCED_PATTERNS = {
    0: "recap", 12: "gate", 17: "network", 32: "pipeline", 36: "chart",
    44: "stat", 56: "timeline", 62: "compare", 74: "stack", 82: "funnel",
}


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        path = Path(r"C:\Windows\Fonts\consolab.ttf")
    elif bold:
        path = Path(r"C:\Windows\Fonts\segoeuib.ttf")
    else:
        path = Path(r"C:\Windows\Fonts\segoeui.ttf")
    return ImageFont.truetype(str(path), size=size)


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1 - (1 - value) ** 4


def smooth(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def ass_seconds(value: str) -> float:
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def narration_by_slot() -> dict[int, str]:
    lines: list[tuple[float, float, str]] = []
    for raw in episode.CAPTIONS.read_text(encoding="utf-8-sig").splitlines():
        if not raw.startswith("Dialogue:"):
            continue
        parts = raw.split(",", 9)
        if len(parts) < 10:
            continue
        lines.append((ass_seconds(parts[1]), ass_seconds(parts[2]), parts[9].replace("\\N", " ")))
    result: dict[int, str] = {}
    for slot in range(100):
        start, end = slot * 6, slot * 6 + 6
        words = [text for left, right, text in lines if right > start and left < end]
        result[slot] = " ".join(words).strip()
    return result


def headline(section: str, text: str, slot: int) -> str:
    low = text.lower()
    rules = [
        (("capable enough", "process around training"), "CAPABILITY CHANGES THE PROCESS"),
        (("two weeks", "paused", "on hold"), "THE SAFETY BRAKE"),
        (("monitor", "overhead"), "CONTROL HAS A COST"),
        (("mythos", "defender"), "DEFENSE HAS TO SCALE"),
        (("multi-action", "sequence of clicks", "operate web"), "ONE REQUEST, MANY ACTIONS"),
        (("recover", "differently", "fails"), "THE RECOVERY TEST"),
        (("32", "13 minutes", "thirty-two minutes"), "TIME SAVED—WITH A CAVEAT"),
        (("files", "skills", "persistent"), "THE AGENT KEEPS CONTEXT"),
        (("17", "usage"), "ADOPTION, NOT A DEMO"),
        (("generate", "review", "revise"), "THE PRODUCTION LOOP"),
        (("company-reported", "runway says"), "CLAIM VS. EVIDENCE"),
        (("paid", "ad-free"), "ONE PRODUCT, TWO ECONOMIES"),
        (("under eighteen", "younger users", "users who say they are thirteen"), "SAFETY BY DEFAULT"),
        (("31", "markets"), "DISTRIBUTION BECOMES THE PRODUCT"),
        (("8 gigawatts", "8 gw"), "COMPUTE GETS PHYSICAL"),
        (("jobs", "grants", "credits"), "THE INFRASTRUCTURE LEDGER"),
        (("2.96", "public models"), "MILLIONS OF MODELS"),
        (("85.6", "eighty-five-point-six", "fewer than two hundred"), "A VERY LONG TAIL"),
        (("1.5", "99.2", "one-point-five", "ninety-nine-point-two"), "ATTENTION IS CONCENTRATED"),
        (("151,448", "qwen"), "ONE FAMILY, MANY DERIVATIVES"),
        (("83%", "sub-1b", "small models"), "SMALL MODELS, BIG USE"),
        (("agents", "automation"), "THE USERS AREN'T ALL HUMAN"),
    ]
    for needles, title in rules:
        if any(needle in low for needle in needles):
            return title
    if section == "intro":
        return ["THIS WEEK, AI LEFT THE CHAT BOX", "SIX STORIES, ONE DIRECTION", "THE WEEK IN AI"][slot % 3]
    if section == "outro":
        return ["THE WEEK'S SIGNAL", "CAPABILITY MEETS CONSEQUENCE", "WHAT CHANGES NEXT?"][slot % 3]
    return episode.COPY[section][slot % len(episode.COPY[section])][0].replace("≠", "IS NOT")


def metrics(text: str) -> list[str]:
    found = re.findall(r"(?:\$\s?)?\d+(?:\.\d+)?(?:,\d{3})*(?:%|×|x|\s?(?:million|billion|gigawatts|GW|markets|days|hours|weeks|jobs))?", text, re.I)
    clean = []
    for value in found:
        value = re.sub(r"\s+", " ", value).strip()
        if value and value not in clean:
            clean.append(value.upper())
    word_metrics = [
        ("thirty-two minutes", "32 MIN"), ("thirteen", "13 MIN"),
        ("more than doubled", ">2×"), ("three hundred percent", ">300%"),
        ("seventeen times", ">17×"), ("eighty-five-point-six percent", "85.6%"),
        ("fewer than two hundred", "<200"), ("one-point-five percent", "1.5%"),
        ("ninety-nine-point-two", "99.2%"), ("eighty-three percent", "83%"),
        ("two-point-nine-six million", "2.96M"), ("eight gigawatts", "8 GW"),
        ("thirty-five thousand", "35,000"), ("two thousand five hundred", "2,500"),
        ("forty million", "$40M"), ("eighty-four million", "$84M"),
        ("thirty-one", "31"), ("two weeks", "2 WEEKS"), ("twenty percent", "20%"),
    ]
    low = text.lower()
    for phrase, value in word_metrics:
        if phrase in low and value not in clean:
            clean.append(value)
    return clean[:4]


def choose_pattern(section: str, text: str, slot: int) -> tuple[str, list[str], str]:
    low, nums = text.lower(), metrics(text)
    candidates = ["proof-dominant", "relationship-dominant", "sequential-ledger"]
    if section in {"intro", "outro"}:
        return ("recap", candidates, "A multi-story summary needs one connected field, not a logo card.")
    if any(word in low for word in ("paused", "hold", "approval", "review before")):
        return ("gate", candidates, "The narrated idea is a process stopping at a control boundary.")
    if (len(nums) >= 2 or any(word in low for word in ("doubled", "retention", "seventeen times", "thirty-two minutes", "eighty-five-point-six", "ninety-nine-point-two"))) and any(word in low for word in ("from", "to", "range", "share", "downloads", "usage", "retention", "doubled", "percent")):
        return ("chart", candidates, "The proof is numerical change or concentration, so the numbers become the structure.")
    if any(word in low for word in ("sequence", "workflow", "generate", "steps", "process", "operate")):
        return ("pipeline", candidates, "The narration explains ordered work; a moving process lane makes the mechanism visible.")
    if any(word in low for word in ("versus", "paid", "free", "caveat", "claim", "independently")):
        return ("compare", candidates, "The beat depends on a distinction between claim, audience, or evidence tiers.")
    if any(word in low for word in ("files", "skills", "context", "layers", "infrastructure", "permissions", "checkpoints", "logs")):
        return ("stack", candidates, "The explanation is about multiple layers accumulating into one working system.")
    if any(word in low for word in ("agents", "ecosystem", "derivative", "partners", "markets", "distribution")):
        return ("network", candidates, "A one-to-many relationship is the key information, so connectors carry the meaning.")
    if nums:
        return ("stat", candidates, "One reported value is the proof object and should dominate the frame.")
    return (["timeline", "network", "compare", "pipeline"][slot % 4], candidates, "Pattern chosen to vary information structure while matching the spoken relationship.")


def semantic_section(slot: int) -> str:
    # Boundaries come from the approved narration, not the old visual-card schedule.
    if slot <= 7: return "intro"
    if slot <= 26: return "cyber"
    if slot <= 41: return "computer_use"
    if slot <= 55: return "runway"
    if slot <= 67: return "chatgpt"
    if slot <= 78: return "ports"
    if slot <= 93: return "open_models"
    return "outro"


def wrap(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, width: int, max_lines: int = 2) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=face)[2] <= width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:max_lines]


def base(section: str, title: str, p: float, slot: int) -> Image.Image:
    image = Image.new("RGB", (W, H), BLACK)
    accent = SECTION_ACCENT[section]
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for x in range(110, W, 120):
        od.line((x, 300, x, H - 95), fill="#FFFFFF08", width=1)
    for y in range(320, H - 80, 95):
        od.line((90, y, W - 90, y), fill="#FFFFFF08", width=1)
    od.ellipse((1420, -280, 2120, 420), fill=accent + "13")
    image = Image.alpha_composite(image.convert("RGBA"), overlay.filter(ImageFilter.GaussianBlur(1))).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.ellipse((112, 80, 128, 96), fill=accent)
    draw.text((144, 69), section.replace("_", " ").upper(), font=font(21, True), fill=MUTED)
    title_face = font(62 if len(title) < 30 else 52, True)
    yy = 126 + int((1 - p) * 12)
    for line in wrap(draw, title, title_face, 1100, 2):
        draw.text((112, yy), line, font=title_face, fill=PAPER)
        yy += 68
    draw.line((112, 272, 112 + int(560 * p), 272), fill=accent, width=5)
    logo_path = LOGOS.get(section)
    if logo_path and logo_path.exists():
        with Image.open(logo_path).convert("RGBA") as logo:
            logo.thumbnail((94, 94), Image.Resampling.LANCZOS)
            tile = Image.new("RGBA", (118, 118), (242, 241, 237, 255))
            tile.alpha_composite(logo, ((118 - logo.width) // 2, (118 - logo.height) // 2))
            image.paste(tile.convert("RGB"), (1680, 82))
    elif section == "runway":
        draw.text((1650, 112), "RUNWAY", font=font(30, True), fill=PAPER)
    draw.text((112, 1015), "PRIVATE REVIEW CUT · SOURCE-BASED EXPLANATION", font=font(18, True), fill="#747977")
    draw.text((1780, 1012), f"{slot + 1:02d}", font=font(22, True), fill=accent)
    return image


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, accent: str, active: bool = False, size: int = 29) -> None:
    draw.rounded_rectangle(box, radius=24, fill=PANEL_2, outline=accent if active else LINE, width=4 if active else 2)
    face = font(size, True)
    bounds = draw.textbbox((0, 0), label, font=face)
    x = (box[0] + box[2] - (bounds[2] - bounds[0])) / 2
    y = (box[1] + box[3] - (bounds[3] - bounds[1])) / 2 - 4
    draw.text((x, y), label, font=face, fill=PAPER)


def short_labels(text: str, pattern: str) -> list[str]:
    low = text.lower()
    if pattern == "pipeline":
        if "training" in low or "cyber work" in low: return ["MODEL", "TRAINING", "CONTROLS", "CONTINUE"]
        if "browser" in low or "web" in low: return ["REQUEST", "CLICK", "CHECK", "FILE"]
        if "video" in low: return ["GENERATE", "REVIEW", "REVISE", "PUBLISH"]
        return ["SOURCE", "ACTION", "CHECK", "RESULT"]
    if pattern == "compare":
        if "paid" in low or "free" in low: return ["FREE / GO", "PAID"]
        if "claim" in low or "reported" in low: return ["COMPANY CLAIM", "VERIFIED FACT"]
        return ["CAPABILITY", "CONTROL"]
    if pattern == "stack":
        if "files" in low or "skills" in low: return ["SKILLS", "FILES", "TOOL STATE", "GOAL"]
        return ["POWER", "COOLING", "COMPUTE", "WORKLOAD"]
    if pattern == "network":
        if "monitor" in low or "security alerts" in low: return ["TRAINING", "MONITORING", "SECURITY TEAM", "PAUSE"]
        if "model" in low: return ["BASE MODEL", "FINE-TUNES", "APPS", "AGENTS"]
        if "markets" in low: return ["CHATGPT", "31 MARKETS", "USERS", "ADVERTISERS"]
        return ["MODEL", "TOOLS", "PEOPLE", "RESULTS"]
    return []


def draw_scene(slot: int, section: str, text: str, pattern: str, frame_index: int) -> Image.Image:
    t = frame_index / FPS
    enter = ease((t - 0.08) / 0.55)
    phase = ease((t - 0.65) / 1.0)
    finish = ease((t - 2.0) / 0.8)
    accent = SECTION_ACCENT[section]
    title = headline(section, text, slot)
    image = base(section, title, enter, slot)
    draw = ImageDraw.Draw(image)
    nums = metrics(text)
    labels = short_labels(text, pattern)

    if pattern == "pipeline":
        labels = labels or ["SOURCE", "ACTION", "CHECK", "RESULT"]
        for i, label in enumerate(labels):
            local = ease((t - 0.55 - i * 0.18) / 0.55)
            x, y = 112 + i * 430, 450 + int((1 - local) * 18)
            active = i == min(3, max(0, int((t - 1.15) / 0.68)))
            card(draw, (x, y, x + 330, y + 205), label, accent, active, 30)
            if i < 3:
                end = x + 330 + int(100 * phase)
                draw.line((x + 330, 552, end, 552), fill=MUTED, width=5)
        dot_x = 277 + min(3, max(0.0, (t - 1.15) / 0.68)) * 430
        draw.line((277, 742, dot_x, 742), fill=accent, width=5)
        draw.ellipse((dot_x - 11, 731, dot_x + 11, 753), fill=accent)

    elif pattern == "gate":
        draw.line((150, 570, 1760, 570), fill=LINE, width=10)
        dot_x = 150 + int(min(1.0, phase * 1.15) * 930)
        draw.ellipse((dot_x - 22, 548, dot_x + 22, 592), fill=RED)
        gx = 1130
        draw.line((gx, 385, gx, 535 - int(110 * finish)), fill=accent, width=12)
        draw.line((gx, 605 + int(110 * finish), gx, 785), fill=accent, width=12)
        draw.text((860, 820), "MONITOR → REVIEW → RESUME", font=font(31, True), fill=accent)
        if nums:
            draw.text((1450, 450), nums[0], font=font(96, True), fill=PAPER)

    elif pattern == "chart":
        values = nums or ["1.5%", "99.2%"]
        left, right = values[0], values[1] if len(values) > 1 else values[0]
        draw.text((140, 390), left, font=font(138, True), fill=PAPER)
        draw.text((820, 450), "→", font=font(72, True), fill=MUTED)
        draw.text((1080, 390), right, font=font(138, True), fill=PAPER)
        draw.rounded_rectangle((160, 690, 1760, 742), radius=26, fill=LINE)
        draw.rounded_rectangle((160, 690, 160 + int(1600 * (0.16 + 0.84 * finish)), 742), radius=26, fill=accent)
        draw.text((160, 805), "THE RELATIONSHIP IS THE STORY", font=font(28, True), fill=MUTED)

    elif pattern == "stat":
        value = nums[0] if nums else "ONE"
        draw.text((118, 388), value, font=font(210 if len(value) < 7 else 150, True), fill=PAPER)
        draw.line((120, 680, 120 + int(1120 * phase), 680), fill=accent, width=10)
        detail = " ".join(text.split()[:18])
        for i, line in enumerate(wrap(draw, detail, font(34), 980, 3)):
            draw.text((122, 744 + i * 46), line, font=font(34), fill=MUTED)

    elif pattern == "compare":
        labels = labels or ["CLAIM", "EVIDENCE"]
        for i, label in enumerate(labels[:2]):
            local = ease((t - 0.45 - i * 0.25) / 0.6)
            x = 120 + i * 850
            y = 410 + int((1 - local) * 20)
            draw.line((x, y, x + int(720 * local), y), fill=accent if i else MUTED, width=7)
            draw.text((x, y + 55), label, font=font(48, True), fill=PAPER)
            verdict = "AVAILABLE TO MORE PEOPLE" if i == 0 else "BOUNDARIES STILL MATTER"
            draw.text((x, y + 145), verdict, font=font(29), fill=MUTED)
        draw.text((120, 805), "THE DIFFERENCE CHANGES THE CONCLUSION", font=font(30, True), fill=accent)

    elif pattern == "stack":
        labels = labels or ["INPUT", "CONTEXT", "TOOLS", "RESULT"]
        for i, label in enumerate(labels):
            local = ease((t - 0.42 - i * 0.16) / 0.6)
            x, y = 130 + i * 315, 400 + i * 78
            dx = int((1 - local) * -70)
            draw.rounded_rectangle((x + dx, y, x + 430 + dx, y + 235), radius=23, fill=PANEL_2, outline=accent if i == 3 else LINE, width=3)
            draw.text((x + 28 + dx, y + 34), label, font=font(28, True), fill=PAPER)
            for row in range(3):
                draw.line((x + 28 + dx, y + 105 + row * 34, x + 305 + dx, y + 105 + row * 34), fill=LINE, width=7)

    elif pattern == "network":
        labels = labels or ["MODEL", "TOOLS", "USERS", "RESULTS"]
        center = (960, 600)
        radius = 118
        draw.ellipse((center[0]-radius, center[1]-radius, center[0]+radius, center[1]+radius), fill=PANEL_2, outline=accent, width=5)
        draw.text((center[0]-80, center[1]-18), labels[0], font=font(27, True), fill=PAPER)
        nodes = [(280, 430), (1540, 410), (330, 790), (1510, 790)]
        for i, point in enumerate(nodes):
            local = ease((t - 0.55 - i * 0.16) / 0.6)
            ex = center[0] + int((point[0] - center[0]) * phase)
            ey = center[1] + int((point[1] - center[1]) * phase)
            draw.line((center[0], center[1], ex, ey), fill=LINE, width=5)
            if local > 0.05:
                box = (point[0]-145, point[1]-58, point[0]+145, point[1]+58)
                card(draw, box, labels[min(i + 1, len(labels)-1)], accent, i == 3, 24)

    elif pattern == "timeline":
        draw.line((160, 615, 160 + int(1600 * phase), 615), fill=LINE, width=7)
        milestones = ["ANNOUNCE", "TEST", "LIMIT", "SHIP"]
        for i, label in enumerate(milestones):
            x = 190 + i * 500
            local = ease((t - 0.55 - i * 0.2) / 0.55)
            if local > 0.03:
                draw.ellipse((x-18, 597, x+18, 633), fill=accent if i == 3 else PAPER)
                draw.text((x-70, 675), label, font=font(25, True), fill=PAPER)

    elif pattern == "funnel":
        bands = [(170, 1750, "ALL MODELS"), (410, 1510, "DOWNLOADED"), (690, 1230, "REUSED"), (865, 1055, "ATTENTION")]
        for i, (left, right, label) in enumerate(bands):
            local = ease((t - 0.38 - i * 0.2) / 0.58)
            y = 365 + i * 135
            center = (left + right) // 2
            half = int((right - left) * 0.5 * local)
            draw.rounded_rectangle((center-half, y, center+half, y+88), radius=20, fill=PANEL_2,
                                   outline=accent if i == 3 else LINE, width=4 if i == 3 else 2)
            if local > 0.72:
                face = font(25, True)
                bounds = draw.textbbox((0, 0), label, font=face)
                draw.text((center-(bounds[2]-bounds[0])/2, y+26), label, font=face, fill=PAPER)

    else:  # recap
        items = ["SECURITY", "AGENTS", "VIDEO", "PLATFORMS", "COMPUTE", "OPEN MODELS"]
        for i, label in enumerate(items):
            local = ease((t - 0.35 - i * 0.13) / 0.55)
            angle = -math.pi * 0.84 + i * (math.pi * 1.68 / 5)
            cx, cy = 960, 650
            px = cx + math.cos(angle) * 620
            py = cy + math.sin(angle) * 250
            ex = cx + (px - cx) * phase
            ey = cy + (py - cy) * phase
            draw.line((cx, cy, ex, ey), fill=LINE, width=4)
            if local > 0.05:
                card(draw, (int(px-130), int(py-52), int(px+130), int(py+52)), label, accent, i == slot % 6, 22)
        draw.ellipse((850, 540, 1070, 760), fill=PANEL_2, outline=accent, width=5)
        draw.text((890, 615), "ONE\nDIRECTION", font=font(31, True), fill=PAPER, spacing=4)

    return image


def render_one(slot: int, section: str, text: str, pattern: str) -> Path:
    fix_suffix = "_oneuse" if slot in FORCED_PATTERNS else ("_fix1" if slot in {17, 36, 44, 45, 82} else "")
    destination = DEST / "segments_v2" / f"{slot:03d}_{section}_{pattern}{fix_suffix}.mp4"
    if destination.exists() and destination.stat().st_size > 60_000:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "17", "-pix_fmt", "yuv420p", "-g", "60", "-movflags", "+faststart", str(destination)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    for frame_index in range(FPS * SECONDS):
        process.stdin.write(draw_scene(slot, section, text, pattern, frame_index).tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"motion render failed for slot {slot}")
    return destination


def main() -> None:
    texts = narration_by_slot()
    slots = sorted(episode.ENGAGING_MOTION_SLOTS | episode.ENGAGING_MISC_SLOTS)
    art_direction = []
    jobs = []
    for slot in slots:
        section = semantic_section(slot)
        pattern, candidates, rationale = choose_pattern(section, texts[slot], slot)
        if slot in FORCED_PATTERNS:
            pattern = FORCED_PATTERNS[slot]
            rationale = "Reserved one-use layout: this information relationship appears once in the balanced cut."
        art_direction.append({
            "slot": slot, "section": section, "narration": texts[slot],
            "concept_candidates": candidates, "selected_pattern": pattern,
            "proof_object": metrics(texts[slot]) or ["spoken mechanism"], "selection_rationale": rationale,
        })
        jobs.append((slot, section, texts[slot], pattern))
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "art_direction.json").write_text(json.dumps(art_direction, indent=2), encoding="utf-8")
    rendered = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(render_one, *job): job[0] for job in jobs}
        for future in as_completed(futures):
            rendered[futures[future]] = str(future.result())
    (DEST / "motion_manifest.json").write_text(json.dumps({"slots": rendered}, indent=2), encoding="utf-8")
    print(json.dumps({"rendered": len(rendered), "patterns": sorted({item["selected_pattern"] for item in art_direction})}, indent=2))


if __name__ == "__main__":
    main()
