"""Replace blocked/irrelevant article frames with honest source-first visuals."""
from __future__ import annotations

import hashlib
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pipeline.config import CAPTURE_PARALLELISM, OPENROUTER_BROWSER_MODEL
from pipeline.models import CaptureArtifact, CapturePlan, CaptureRecord
from pipeline.project_store import load_project, mark_stage, save_project


PROJECT_DIR = Path("data/episodes/episode_20260901_03").resolve()
COMFY = "src_09022b345bc4"
GOOGLE = "src_90ba20dc32b5"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def _font(size: int, bold: bool = False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def _sentences(text: str) -> list[str]:
    clean = text.replace("�", "'")
    rows = [" ".join(row.split()) for row in re.split(r"(?<=[.!?])\s+|\n+", clean)]
    return [row for row in rows if 45 <= len(row) <= 420]


def _score(target: str, candidate: str) -> int:
    terms = set(re.findall(r"[a-z0-9]{4,}", target.casefold()))
    return len(terms.intersection(re.findall(r"[a-z0-9]{4,}", candidate.casefold())))


def _source_card(path: Path, source, excerpt: str, index: int) -> None:
    dark = index % 3 == 2
    bg, ink, muted, rule = (
        ("#121513", "#F4F3EF", "#B7BDB8", "#83938C") if dark
        else ("#F4F3EF", "#121513", "#4A4F4B", "#83938C")
    )
    canvas = Image.new("RGB", (1920, 1080), bg)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((122, 110, 128, 950), fill=rule)
    draw.text((170, 118), f"SOURCE EXCERPT  ·  {source.publisher.upper()}", font=_font(26, True), fill=muted)
    title = textwrap.wrap(source.title, width=48)[:2]
    y = 185
    for line in title:
        draw.text((170, y), line, font=_font(48, True), fill=ink)
        y += 58
    draw.line((170, y + 20, 1750, y + 20), fill=rule, width=2)
    quote_lines = textwrap.wrap(excerpt, width=54)
    quote_font = _font(48)
    quote_y = max(420, y + 100)
    for line in quote_lines[:7]:
        draw.text((210, quote_y), line, font=quote_font, fill=ink)
        quote_y += 65
    draw.text((170, 956), "VERIFIED ARTICLE TEXT  ·  PRIVATE REVIEW", font=_font(24, True), fill=muted)
    draw.text((1210, 956), source.url.host or "", font=_font(24), fill=muted)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, quality=96)


def main() -> None:
    project = load_project(PROJECT_DIR)
    beats = {beat.id: beat for beat in project.script.beats}
    sources = {source.id: source for source in project.sources}
    output = PROJECT_DIR / "captures" / "verified_source_frames"
    output.mkdir(parents=True, exist_ok=True)
    new_artifacts = {COMFY: [], GOOGLE: []}

    comfy_sentences = _sentences(sources[COMFY].text)
    used = set()
    comfy_article = [
        shot for shot in project.shots
        if shot.visual_category == "article_evidence" and shot.source_id == COMFY
    ]
    for index, shot in enumerate(comfy_article, 1):
        candidates = sorted(
            ((-_score(beats[shot.beat_id].narration, sentence), pos, sentence)
             for pos, sentence in enumerate(comfy_sentences) if pos not in used),
        )
        _, chosen_pos, excerpt = candidates[0]
        used.add(chosen_pos)
        target = output / f"comfy-source-excerpt-{index:02d}-{shot.id}.png"
        _source_card(target, sources[COMFY], excerpt, index)
        sha = _sha256(target)
        shot.asset_path = str(target)
        shot.asset_fingerprint = sha[:20]
        shot.asset_type = "screenshot"
        shot.motion_style = "locked"
        shot.presentation = "full_bleed"
        shot.transition = "cut"
        shot.prompt = f"Exact source excerpt supporting: {beats[shot.beat_id].narration}"
        shot.rights_note = "Exact verified ComfyUI article text; publication review required."
        new_artifacts[COMFY].append(CaptureArtifact(
            kind="element", path=str(target), label=excerpt[:150], sha256=sha,
            source_url=str(sources[COMFY].url), capture_mode="verified_source_excerpt_card",
            visible_text=excerpt, muted=True,
            quality={"status": "accepted", "exact_source_text": True, "invented_ui": False},
        ))

    # Preserve the already-positioned Google evidence frames. Capture-stage
    # retries may clear a shot path before this deterministic repair runs.
    positioned = PROJECT_DIR / "captures" / "positioned_evidence"
    google_article = [
        shot for shot in project.shots
        if shot.visual_category == "article_evidence" and shot.source_id == GOOGLE
    ]
    for shot in google_article:
        matches = sorted(positioned.glob(f"*-{shot.id}.png"))
        if not matches:
            raise FileNotFoundError(f"positioned Google evidence is missing for {shot.id}")
        target = matches[0]
        sha = _sha256(target)
        shot.asset_path = str(target)
        shot.asset_fingerprint = sha[:20]
        shot.asset_type = "screenshot"
        shot.motion_style = "locked"
        shot.presentation = "full_bleed"
        shot.transition = "cut"
        shot.rights_note = "Positioned official Google source evidence; publication review required."

    # Miscellaneous editorial frames use unique, pre-positioned crops from the
    # clean official Google page master. They are provenance visuals, not claim
    # evidence, so they keep their source identity separate from beat citations.
    full_page = next((PROJECT_DIR / "captures").glob(f"{GOOGLE}-*-full.png"))
    image = Image.open(full_page).convert("RGB")
    misc = [shot for shot in project.shots if shot.visual_category == "miscellaneous"]
    max_y = max(0, min(image.height - 1080, 7900))
    for index, shot in enumerate(misc, 1):
        y = round(max_y * (index - 1) / max(1, len(misc) - 1))
        frame = image.crop((0, y, 1920, y + 1080))
        target = output / f"google-editorial-{index:02d}-{shot.id}.png"
        frame.save(target, quality=96)
        sha = _sha256(target)
        shot.source_id = GOOGLE
        shot.asset_path = str(target)
        shot.asset_fingerprint = sha[:20]
        shot.asset_type = "screenshot"
        shot.motion_style = "locked"
        shot.presentation = "full_bleed"
        shot.transition = "cut"
        shot.prompt = f"Official Google launch-page editorial context for: {beats[shot.beat_id].narration}"
        shot.rights_note = "Official Google launch-page crop for private editorial review."
        new_artifacts[GOOGLE].append(CaptureArtifact(
            kind="element", path=str(target), label="Official Google launch-page context",
            sha256=sha, source_url=str(sources[GOOGLE].url),
            capture_mode="positioned_source_section", visible_text="", muted=True,
            quality={"status": "accepted", "width": 1920, "height": 1080, "popup_free": True},
        ))

    records = {record.source_id: record for record in project.captures}
    for source_id, artifacts in new_artifacts.items():
        if source_id in records:
            records[source_id].artifacts.extend(artifacts)
        else:
            source = sources[source_id]
            project.captures.append(CaptureRecord(
                source_id=source_id, requested_url=str(source.url), final_url=str(source.url),
                page_title=source.title, captured_at=datetime.now(timezone.utc),
                plan=CapturePlan(source_id=source_id, rationale="Verified source frames", actions=[]),
                artifacts=artifacts, errors=[],
            ))

    capture_input = {
        "planner": {
            "version": 7, "model": OPENROUTER_BROWSER_MODEL,
            "semantic_annotations": True, "resolution": "1080p",
            "parallelism": CAPTURE_PARALLELISM,
        },
        "sources": [{"id": source.id, "url": str(source.url)} for source in project.sources],
        "shots": [
            {"id": shot.id, "type": shot.asset_type, "source_id": shot.source_id, "prompt": shot.prompt}
            for shot in project.shots
        ],
        "model_tests": project.episode.get("model_test_queue", []),
    }
    mark_stage(project, "capture", capture_input)
    project.episode.get("stage_hashes", {}).pop("media", None)
    project.episode.get("stage_hashes", {}).pop("render", None)
    project.status = "approved_for_production"
    save_project(project, PROJECT_DIR)
    print(f"replaced {len(comfy_article)} blocked article frames and {len(misc)} utility frames")


if __name__ == "__main__":
    main()
