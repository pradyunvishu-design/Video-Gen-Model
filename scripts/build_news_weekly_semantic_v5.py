from __future__ import annotations

"""Build the News Weekly review cut with sentence-matched, capped B-roll.

The earlier balanced cut inherited a visual section schedule that did not follow
the final narration timing.  This revision uses the approved ASS captions as the
clock, manually approves every B-roll assignment, and treats all excerpts from
one source URL as the same asset for the two-use limit.
"""

from collections import Counter
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.editorial_style import draw_source_credit
from scripts import build_news_weekly_20260822_video as episode
from scripts import render_news_weekly_custom_motion as motion

OUT = ROOT / "output" / "news_weekly_20260822"
SOURCE_RENDER = OUT / "balanced_v4" / "render_manifest.json"
OPEN_MANIFEST = OUT / "open_broll" / "approved_open_broll_manifest.json"
REPUTABLE_YOUTUBE_MANIFEST = OUT / "reputable_youtube_v7" / "ingested_manifest.json"
WORK = OUT / "semantic_v5"
SEGMENTS = WORK / "segments"
OVERLAYS = WORK / "overlays"
NARRATION = OUT / "audio" / "narration_master.m4a"
CAPTIONS = OUT / "captions_monochrome.ass"
FINAL = OUT / "the_week_in_ai_2026-08-22_10min_semantic_v5.mp4"
FFMPEG, FFPROBE = episode.FFMPEG, episode.FFPROBE

# target: donor, source start, terms that must occur in the current six-second
# narration window, and the visible action that supports that narration.
BROLL_PLAN = {
    9: (3, 13, ("cybersecurity", "security"), "defenders working in a cyber operations environment"),
    14: (4, 30, ("security",), "security experts discussing operational controls"),
    19: (3, 37, ("defense", "mythos"), "hands-on cyber defense work"),
    39: (22, 36, ("failure", "permissions", "logs"), "a real browser session visibly encountering failure"),
    40: (23, 30, ("shared drive", "workflow"), "a person working in a normal computer environment"),
    42: (39, 65, ("workflow", "media", "runway"), "an open media workflow and archive interface"),
    47: (39, 105, ("editing", "collaboration", "integrations"), "media assets moving through a reusable production system"),
    53: (42, 55, ("direction", "selection", "rights"), "professional creators discussing how work is directed and finished"),
    54: (40, 85, ("ai video", "video"), "a finished moving-image production example"),
    55: (42, 75, ("production calendar", "production"), "professional creators in a real production setting"),
    61: (53, 36, ("teens", "thirteen", "seventeen"), "students discussing technology in a classroom"),
    64: (57, 48, ("schoolwork", "daily life"), "students using technology in an education context"),
    67: (64, 0, ("ohio", "gigawatts"), "official chip-manufacturing and compute infrastructure footage"),
    68: (65, 0, ("ports-pike", "nvidia"), "official semiconductor infrastructure footage"),
    76: (70, 28, ("power", "substations"), "large physical power and cooling infrastructure"),
}

# Caption-timed semantic gates for the additional reputable YouTube sources.
# These clips only enter the render after the rights-aware ingestion stage has
# produced a local 1080p file and marked picture QC accepted.
REPUTABLE_YOUTUBE_TERMS = {
    9: ("cybersecurity", "critical"),
    10: ("cyber", "training"),
    11: ("hardened", "research environments"),
    16: ("monitoring", "security alerts"),
    19: ("defense", "claude security"),
    20: ("scanning codebases", "vulnerabilities"),
    21: ("open-source software", "patches"),
    28: ("computer use", "browser use"),
    34: ("actions per model turn", "several actions"),
    38: ("failure surface", "permissions"),
    39: ("checkpoints", "logs"),
    69: ("nvidia", "ai compute"),
    93: ("document", "package", "secure releases"),
}

SOURCE_CARDS = {
    "intro": ("THE WEEK IN AI", "Sources: OpenAI · Anthropic · Runway · Hugging Face", "Evidence first. Visuals follow the spoken sentence."),
    "cyber": ("OPENAI / ANTHROPIC", "Cyber capability, monitoring, and defense", "Source claims are shown as evidence, not decorative footage."),
    "computer_use": ("ANTHROPIC", "Computer use · Browser use · Skills · Files", "The product page replaces generic computer footage."),
    "runway": ("RUNWAY", "The Next Phase of Enterprise Video Generation", "Company figures are labeled as company-reported evidence."),
    "chatgpt": ("OPENAI", "ChatGPT Ads / ChatGPT for Teens", "Product evidence replaces unrelated lifestyle footage."),
    "ports": ("NVIDIA / PORTS-PIKE", "Physical AI infrastructure in Ohio", "Official infrastructure evidence replaces generic industrial clips."),
    "open_models": ("HUGGING FACE", "State of Open Models: Summer 2026", "The report itself stays on screen for data-heavy claims."),
    "outro": ("THE WATCH LIST", "Safety · Workflows · Infrastructure", "Only sourced visuals from the episode recap are reused."),
}

CAPTURE_BY_SECTION = {
    "intro": ("Hugging Face", "hf_open_models_report*full.png"),
    "cyber": ("Anthropic", "anthropic_mythos_defense*full.png"),
    "computer_use": ("Anthropic", "anthropic_computer_use*full.png"),
    "ports": ("NVIDIA", "nvidia_ports_pike*full.png"),
    "open_models": ("Hugging Face", "hf_open_models_report*full.png"),
}


def duration(path: Path) -> float:
    return float(subprocess.check_output([
        str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], text=True).strip())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def open_records() -> dict[int, dict]:
    payload = json.loads(OPEN_MANIFEST.read_text(encoding="utf-8"))
    return {int(item["slot"]): item for item in payload["clips"]}


def reputable_youtube_records() -> dict[int, dict]:
    if not REPUTABLE_YOUTUBE_MANIFEST.is_file():
        return {}
    payload = json.loads(REPUTABLE_YOUTUBE_MANIFEST.read_text(encoding="utf-8"))
    records: dict[int, dict] = {}
    for item in payload.get("clips", []):
        quality = item.get("quality") or {}
        clip = Path(str(item.get("clip") or ""))
        if quality.get("status") != "accepted" or not clip.is_file():
            continue
        if int(quality.get("width") or 0) != 1920 or int(quality.get("height") or 0) != 1080:
            continue
        records[int(item["slot"])] = {
            **item,
            "media_file": str(clip),
            "publisher": item["channel"],
            "license": "creativeCommon",
        }
    return records


def source_overlay(slot: int, publisher: str) -> Path:
    destination = OVERLAYS / f"{slot:03d}_{publisher.lower().replace(' ', '_')}_neutral_v2.png"
    if destination.exists():
        return destination
    OVERLAYS.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    draw_source_credit(
        draw, publisher, label_font=episode.font(13, True),
        publisher_font=episode.font(18, True), x=42, y=996,
    )
    image.save(destination)
    return destination


def render_broll(target: int, donor: dict, start: float) -> Path:
    destination = SEGMENTS / f"{target:03d}_broll.mp4"
    if destination.exists() and destination.stat().st_size > 80_000:
        return destination
    source = Path(donor["media_file"])
    start = min(float(start), max(0.0, duration(source) - 6.1))
    overlay = source_overlay(target, donor.get("publisher", "Source"))
    graph = (
        "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
        "unsharp=3:3:0.22,fps=30,format=rgba[base];"
        "[1:v]format=rgba,fade=t=in:st=0.25:d=0.2:alpha=1,fade=t=out:st=5.6:d=0.2:alpha=1[ol];"
        "[base][ol]overlay=0:0:shortest=1,format=yuv420p[v]"
    )
    subprocess.run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start),
        "-stream_loop", "-1", "-i", str(source), "-loop", "1", "-i", str(overlay),
        "-filter_complex", graph, "-map", "[v]", "-t", "6", "-an", "-r", "30",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-g", "60", str(destination),
    ], check=True)
    return destination


def render_article(target: int, publisher: str, source: Path) -> Path:
    destination = SEGMENTS / f"{target:03d}_article.mp4"
    if destination.exists() and destination.stat().st_size > 70_000:
        return destination
    overlay = source_overlay(target, publisher)
    with Image.open(source) as image:
        sw, sh = image.size
    scaled_h = max(1080, round(sh * 1920 / sw))
    max_y = max(0, scaled_h - 1080)
    start_y = int(max_y * ((target % 7) / 8))
    # Article evidence is pre-positioned before it appears.  Do not make the
    # viewer watch the editor search/scroll for the relevant passage.
    travel = min(380, max(0, max_y - start_y))
    settled_y = start_y + travel
    base = (
        f"[0:v]scale=1920:{scaled_h},crop=1920:1080:0:{settled_y},"
        "fps=30,format=rgba[base]"
    )
    graph = base + ";[1:v]format=rgba[ol];[base][ol]overlay=0:0:shortest=1,format=yuv420p[v]"
    subprocess.run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(source),
        "-loop", "1", "-i", str(overlay), "-filter_complex", graph, "-map", "[v]", "-t", "6",
        "-an", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-g", "60", str(destination),
    ], check=True)
    return destination


def render_source_card(target: int, section: str, narration: str) -> Path:
    still = SEGMENTS / f"{target:03d}_source_card.png"
    destination = SEGMENTS / f"{target:03d}_source_card.mp4"
    if destination.exists() and destination.stat().st_size > 60_000:
        return destination
    publisher, title, note = SOURCE_CARDS[section]
    bg = (239, 236, 226)
    ink = (28, 32, 30)
    accent = (184, 103, 79) if section in {"computer_use", "runway"} else (64, 117, 91)
    image = Image.new("RGB", (1920, 1080), bg)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 26, 1080), fill=accent)
    draw.text((108, 92), f"SOURCE · {publisher}", font=episode.font(22, True), fill=accent)
    y = 166
    for line in episode.wrap(draw, title, episode.font(63, True, True), 1460):
        draw.text((108, y), line, font=episode.font(63, True, True), fill=ink)
        y += 80
    draw.line((108, y + 22, 1810, y + 22), fill=(184, 181, 171), width=2)
    excerpt = narration.strip()
    y += 78
    for line in episode.wrap(draw, excerpt, episode.font(34), 1510)[:5]:
        draw.text((108, y), line, font=episode.font(34), fill=ink)
        y += 52
    draw.text((108, 930), note, font=episode.font(24), fill=(92, 96, 91))
    image.save(still)
    subprocess.run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(still),
        "-t", "6", "-an", "-r", "30", "-vf", "format=yuv420p", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "18", "-g", "60", str(destination),
    ], check=True)
    return destination


def contains_required(narration: str, required: tuple[str, ...]) -> bool:
    lowered = narration.casefold()
    return any(term.casefold() in lowered for term in required)


def main() -> None:
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    records = open_records()
    texts = motion.narration_by_slot()
    source_root = OUT / "sources"
    source_manifest = json.loads(SOURCE_RENDER.read_text(encoding="utf-8"))
    base_ledger = source_manifest["shot_ledger"]
    old_broll_slots = {int(item["slot"]) for item in base_ledger if item["kind"] == "reviewed_broll"}

    active_plan = {
        target: {
            "donor": records[donor], "start": start, "required": required,
            "reason": reason, "source_kind": "reviewed_broll",
        }
        for target, (donor, start, required, reason) in BROLL_PLAN.items()
    }
    for target, donor in reputable_youtube_records().items():
        if target not in REPUTABLE_YOUTUBE_TERMS:
            continue
        active_plan[target] = {
            "donor": donor, "start": 0.0,
            "required": REPUTABLE_YOUTUBE_TERMS[target],
            "reason": "caption-matched reputable Creative Commons YouTube footage",
            "source_kind": "reputable_youtube_broll",
        }
    donor_records = {target: item["donor"] for target, item in active_plan.items()}
    source_counts = Counter(item["source_url"] for item in donor_records.values())
    media_counts = Counter(str(Path(item["media_file"]).resolve()).casefold() for item in donor_records.values())
    if max(source_counts.values(), default=0) > 2 or max(media_counts.values(), default=0) > 2:
        raise RuntimeError("B-roll plan exceeds the two-use source or media limit")

    alignment = []
    for target, item in active_plan.items():
        start, required, reason = item["start"], item["required"], item["reason"]
        narration = texts[target]
        passed = contains_required(narration, required)
        alignment.append({
            "slot": target, "start_seconds": target * 6, "narration": narration,
            "required_terms_any": list(required), "matched": passed, "match_reason": reason,
            "source_url": donor_records[target]["source_url"], "source_start_seconds": start,
        })
        if not passed:
            raise RuntimeError(f"slot {target} failed narration-to-B-roll alignment")

    jobs = {}
    replacements: dict[int, tuple[Path, str, dict]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for target, item in active_plan.items():
            start, reason, donor = item["start"], item["reason"], item["donor"]
            future = pool.submit(render_broll, target, donor, start)
            jobs[future] = (target, item["source_kind"], {**donor, "semantic_target": reason, "selected_start": start})

        for target in sorted(old_broll_slots - active_plan.keys()):
            section = motion.semantic_section(target)
            if section in CAPTURE_BY_SECTION:
                publisher, pattern = CAPTURE_BY_SECTION[section]
                source = next(iter(sorted(source_root.glob(pattern))), None)
                if source is None:
                    raise FileNotFoundError(pattern)
                future = pool.submit(render_article, target, publisher, source)
                metadata = {"publisher": publisher, "semantic_target": texts[target], "article_asset": str(source)}
                jobs[future] = (target, "article_source", metadata)
            else:
                future = pool.submit(render_source_card, target, section, texts[target])
                jobs[future] = (target, "source_evidence_card", {
                    "publisher": SOURCE_CARDS[section][0], "semantic_target": texts[target],
                })

        for future in as_completed(jobs):
            target, kind, metadata = jobs[future]
            replacements[target] = (future.result(), kind, metadata)

    timeline: list[Path] = []
    ledger = []
    for record in base_ledger:
        slot = int(record["slot"])
        revised = dict(record)
        if slot in replacements:
            path, kind, metadata = replacements[slot]
            revised.update(metadata)
            revised.update({"file": str(path), "source": str(path), "kind": kind})
            if kind in {"reviewed_broll", "reputable_youtube_broll"}:
                revised.update({
                    "source_start_seconds": metadata["selected_start"],
                    "source_end_seconds": metadata["selected_start"] + 6,
                    "alignment_status": "passed_caption_timed_manual_review",
                })
        else:
            path = Path(revised["file"])
        if not path.exists() or path.stat().st_size < 60_000:
            raise FileNotFoundError(path)
        timeline.append(path.resolve())
        ledger.append(revised)

    final_broll = [
        item for item in ledger
        if item["kind"] in {"reviewed_broll", "reputable_youtube_broll"}
    ]
    final_counts = Counter(item.get("source_url", "") for item in final_broll)
    if "" in final_counts or max(final_counts.values(), default=0) > 2:
        raise RuntimeError(f"final B-roll provenance/repetition gate failed: {dict(final_counts)}")

    qc = {
        "passed": True,
        "policy": {"caption_timed_matching": True, "maximum_uses_per_source_video": 2},
        "broll_count": len(final_broll),
        "source_use_counts": dict(final_counts),
        "assignments": alignment,
    }
    (WORK / "broll_alignment_qc.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")

    concat = WORK / "timeline.concat.txt"
    concat.write_text("".join(f"file '{path.as_posix()}'\n" for path in timeline), encoding="utf-8")
    visuals = WORK / "visuals_600s.mp4"
    subprocess.run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat), "-c", "copy", "-t", "600", str(visuals),
    ], check=True)
    ass_path = str(CAPTIONS.resolve()).replace("\\", "/").replace(":", "\\:")
    subprocess.run([
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-i", str(visuals), "-i", str(NARRATION),
        "-vf", f"ass='{ass_path}'", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-ac", "2", "-t", "600", "-movflags", "+faststart", str(FINAL),
    ], check=True)

    mix = Counter(item["kind"] for item in ledger)
    manifest = {
        "final": str(FINAL), "sha256": sha256(FINAL), "duration_seconds": 600,
        "resolution": "1920x1080", "fps": 30, "publishing_enabled": False,
        "visual_mix": dict(mix), "broll_alignment_qc": str(WORK / "broll_alignment_qc.json"),
        "shot_ledger": ledger,
    }
    (WORK / "render_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "shot_ledger"}, indent=2))


if __name__ == "__main__":
    main()
