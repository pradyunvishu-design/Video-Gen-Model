"""Budget-capped, resumable reference-fidelity loop for the AI-news channel.

The loop measures transferable editorial grammar. It deliberately rejects
verbatim imitation, full-video retention, and publication side effects.
"""
from __future__ import annotations

import hashlib
import base64
import json
import math
import re
import shutil
import statistics
import subprocess
import sys
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, ConfigDict, Field

from . import editorial, storyboard
from .config import (
    EPISODE_DATA_DIR,
    FIDELITY_BUDGET_FRACTION,
    FIDELITY_CORPUS_SIZE,
    FIDELITY_DATA_DIR,
    FIDELITY_PROFILE_PATH,
    FIDELITY_PROGRESS_PATH,
    MAGIC_HOUR_API_KEY,
    MAGIC_HOUR_STARTING_BALANCE_CREDITS,
    OPENROUTER_API_KEY,
    OPENROUTER_FIDELITY_MAX_REQUEST_USD,
    OPENROUTER_MODEL,
    OPENROUTER_STARTING_BALANCE_USD,
    OPENROUTER_VERIFY_MODEL,
    PROJECT_ROOT,
)
from .models import EpisodeProject, Script
from .project_store import canonical_hash, load_project, save_project
from .viral_clips import _canonical_url, _discover_entries, _hydrate, _public_caption_file, parse_vtt


SCRIPT_DIMENSIONS = (
    "hook_style", "sentence_rhythm", "question_use", "callbacks", "pacing", "structure",
)
VISUAL_DIMENSIONS = (
    "typography", "motion_style", "color_palette", "chart_data_viz",
    "information_density", "visual_reveal_pacing",
)
ALL_DIMENSIONS = SCRIPT_DIMENSIONS + VISUAL_DIMENSIONS
MILESTONES = (
    "pattern_library_finalized", "first_fully_scored_script",
    "first_fully_scored_storyboard", "first_episode_clearing_verification",
)

CHANNELS = {
    "ai_search": {
        "title": "AI Search", "handle": "@theAIsearch",
        "channel_id": "UCIgnGlGkVRhd4qNFcEwLL4A",
        "url": "https://www.youtube.com/@theAIsearch/videos",
    },
    "ai_labs": {
        "title": "AI LABS", "handle": "@AILABS-393",
        "channel_id": "UCelfWQr9sXVMTvBzviPGlFw",
        "url": "https://www.youtube.com/@AILABS-393/videos",
    },
}


class BudgetLimitExceeded(Exception):
    """Hard stop that must escape OpenRouter's transient-request retry loop."""

    pass


class ReferenceVideo(BaseModel):
    model_config = ConfigDict(extra="allow")
    video_id: str
    channel_id: str
    channel_handle: str
    title: str
    url: str
    upload_date: str = ""
    duration_seconds: float
    view_count: int = 0
    views_per_day: float = 0
    format_label: str = "explainer"
    chapters: list[dict[str, Any]] = Field(default_factory=list)
    transcript_available: bool = False
    transcript_sha256: str = ""
    opening_excerpt: str = ""
    transcript_metrics: dict[str, float | int] = Field(default_factory=dict)
    visual_timecodes: list[float] = Field(default_factory=list)
    thumbnail_url: str = ""
    content_sha256: str = ""
    listing_sha256: str = ""
    analysis_frame_strip: str = ""
    analysis_only: bool = True


class FidelityScorecard(BaseModel):
    stage: Literal["script", "storyboard", "integrated"]
    deterministic: dict[str, int]
    blind_review: dict[str, int]
    final: dict[str, int]
    distance_from_reference: dict[str, float] = Field(default_factory=dict)
    notes: dict[str, str] = Field(default_factory=dict)
    reference_ids: list[str] = Field(default_factory=list)
    artifact_sha256: str = ""

    @property
    def passed(self) -> bool:
        return bool(self.final) and all(value == 5 for value in self.final.values())


class FidelityIteration(BaseModel):
    index: int
    stage: Literal["script", "storyboard", "integrated"]
    target_dimension: str
    before_scores: dict[str, int]
    after_scores: dict[str, int]
    before_sha256: str
    after_sha256: str
    accepted: bool
    reason: str
    usage_after: dict[str, int | float]


class FidelityBudget(BaseModel):
    openrouter_starting_balance_usd: float = Field(default=0, ge=0)
    magic_hour_starting_balance_credits: int = Field(default=0, ge=0)
    openrouter_absolute_cap_usd: float = Field(default=0, ge=0)
    magic_hour_absolute_cap_credits: int = Field(default=0, ge=0)
    limit_fraction: float = Field(default=0.30, gt=0, le=1)
    openrouter_spend_usd: float = 0
    magic_hour_spend_credits: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    openrouter_requests: int = 0

    def caps(self) -> dict[str, float | int]:
        return {
            "openrouter_usd": (
                self.openrouter_absolute_cap_usd
                or self.openrouter_starting_balance_usd * self.limit_fraction
            ),
            "magic_hour_credits": (
                self.magic_hour_absolute_cap_credits
                or math.floor(self.magic_hour_starting_balance_credits * self.limit_fraction)
            ),
        }

    def fractions(self) -> dict[str, float]:
        caps = self.caps()
        return {
            "openrouter": (
                self.openrouter_spend_usd / max(self.openrouter_absolute_cap_usd, 1e-9)
                if self.openrouter_absolute_cap_usd
                else self.openrouter_spend_usd / max(self.openrouter_starting_balance_usd, 1e-9)
            ),
            "magic_hour": (
                self.magic_hour_spend_credits / max(self.magic_hour_absolute_cap_credits, 1)
                if self.magic_hour_absolute_cap_credits
                else self.magic_hour_spend_credits / max(self.magic_hour_starting_balance_credits, 1)
            ),
        }

    def consumed_fraction(self) -> float:
        return max(self.fractions().values())

    def remaining_openrouter_cap(self) -> float:
        return max(0.0, float(self.caps()["openrouter_usd"]) - self.openrouter_spend_usd)

    def remaining_magic_hour_cap(self) -> int:
        return max(0, int(self.caps()["magic_hour_credits"]) - self.magic_hour_spend_credits)

    def assert_openrouter_estimate(self, estimate: float) -> None:
        if estimate > self.remaining_openrouter_cap() + 1e-9:
            raise BudgetLimitExceeded(
                f"next OpenRouter request could cross the fidelity cap: "
                f"estimate=${estimate:.4f}, remaining=${self.remaining_openrouter_cap():.4f}"
            )

    def record_openrouter(self, usage: dict[str, Any], fallback_cost: float) -> None:
        cost = usage.get("cost", usage.get("total_cost", fallback_cost))
        try:
            self.openrouter_spend_usd += max(0.0, float(cost))
        except (TypeError, ValueError):
            self.openrouter_spend_usd += max(0.0, fallback_cost)
        self.prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        self.completion_tokens += int(usage.get("completion_tokens", 0) or 0)
        details = usage.get("completion_tokens_details") or {}
        self.reasoning_tokens += int(details.get("reasoning_tokens", usage.get("reasoning_tokens", 0)) or 0)
        self.openrouter_requests += 1

    def record_magic_hour(self, credits: int) -> None:
        credits = max(0, int(credits))
        self.magic_hour_spend_credits += credits
        if self.magic_hour_spend_credits >= int(self.caps()["magic_hour_credits"]):
            raise BudgetLimitExceeded(
                f"actual Magic Hour charge reached or crossed the fidelity cap: "
                f"charge={credits}, total={self.magic_hour_spend_credits}"
            )


class FidelityRun(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "created"
    channels: dict[str, dict[str, Any]] = Field(default_factory=dict)
    corpus_path: str = ""
    corpus_sha256: str = ""
    pattern_library_path: str = ""
    pattern_library_sha256: str = ""
    supported_formats: list[str] = Field(default_factory=lambda: ["tool_test", "weekly_roundup", "deep_dive"])
    pilot_format: str = "tool_test"
    pilot_episode_id: str = ""
    budget: FidelityBudget | None = None
    scorecards: dict[str, FidelityScorecard] = Field(default_factory=dict)
    iterations: list[FidelityIteration] = Field(default_factory=list)
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    stop_reason: str = ""
    errors: list[str] = Field(default_factory=list)


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fidelity_run_dir(run_id: str) -> Path:
    return FIDELITY_DATA_DIR / run_id


def fidelity_run_path(run_id: str) -> Path:
    return fidelity_run_dir(run_id) / "fidelity_run.json"


def save_fidelity_run(run: FidelityRun) -> Path:
    run.updated_at = datetime.now(timezone.utc)
    target = fidelity_run_path(run.run_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def load_fidelity_run(run_id: str) -> FidelityRun:
    return FidelityRun.model_validate_json(fidelity_run_path(run_id).read_text(encoding="utf-8"))


def _milestone_heading(name: str) -> str:
    return {
        "pattern_library_finalized": "Pattern library finalized",
        "first_fully_scored_script": "First fully-scored script",
        "first_fully_scored_storyboard": "First fully-scored storyboard",
        "first_episode_clearing_verification": "First episode clearing verification",
    }[name]


def record_milestone(run: FidelityRun, name: str, artifact: str, scores: dict[str, int] | None = None) -> None:
    if name not in MILESTONES:
        raise ValueError(f"unsupported fidelity milestone: {name}")
    if any(item.get("name") == name for item in run.milestones):
        return
    event = {
        "name": name, "at": datetime.now(timezone.utc).isoformat(), "artifact": artifact,
        "scores": scores or {}, "usage": run.budget.model_dump() if run.budget else {},
    }
    run.milestones.append(event)
    heading = _milestone_heading(name)
    existing = FIDELITY_PROGRESS_PATH.read_text(encoding="utf-8") if FIDELITY_PROGRESS_PATH.is_file() else "# Channel Fidelity Progress\n"
    if f"## {heading}" not in existing:
        block = (
            f"\n## {heading}\n\n"
            f"- Time: {event['at']}\n- Run: `{run.run_id}`\n- Artifact: `{artifact}`\n"
            f"- Scores: `{json.dumps(scores or {}, sort_keys=True)}`\n"
        )
        FIDELITY_PROGRESS_PATH.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")
    save_fidelity_run(run)


def _format_label(title: str) -> str:
    text = title.casefold()
    if "ai news" in text or any(term in text for term in ("this week", "weekly", "roundup")):
        return "weekly_roundup"
    if any(term in text for term in ("how to", "guide", "tutorial", "use this", "setup")):
        return "tool_test"
    if any(term in text for term in ("explained", "every level", "types of", "breakthrough")):
        return "deep_dive"
    return "explainer"


def _upload_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except (TypeError, ValueError):
        return date(1970, 1, 1)


def _deduplicated_caption_text(cues: list[Any]) -> str:
    """Collapse rolling-caption overlaps before deriving editorial metrics."""
    accumulated: list[tuple[str, str]] = []
    for cue in cues:
        current = [
            (token, re.sub(r"[^a-z0-9']+", "", token.casefold()))
            for token in str(cue.text).split()
        ]
        current = [item for item in current if item[1]]
        if not current:
            continue
        prior_norm = [item[1] for item in accumulated]
        current_norm = [item[1] for item in current]
        overlap = 0
        for width in range(min(80, len(prior_norm), len(current_norm)), 0, -1):
            if prior_norm[-width:] == current_norm[:width]:
                overlap = width
                break
        # Some auto-caption tracks repeat a complete short rolling window after
        # inserting a tiny timing-only cue. Do not append that window twice.
        if not overlap and len(current_norm) <= 24:
            recent = prior_norm[-120:]
            if any(
                recent[index:index + len(current_norm)] == current_norm
                for index in range(max(0, len(recent) - len(current_norm) + 1))
            ):
                continue
        accumulated.extend(current[overlap:])
    return " ".join(raw for raw, _normalized in accumulated).strip()


def _transcript_metrics(cues: list[Any]) -> tuple[dict[str, float | int], str, str]:
    text = _deduplicated_caption_text(cues)
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    lengths = [len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", item)) for item in sentences]
    word_count = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", text))
    excerpt = " ".join(text.split()[:25])
    metrics: dict[str, float | int] = {
        "word_count": word_count,
        "sentence_count": len(sentences),
        "mean_sentence_words": round(statistics.fmean(lengths), 3) if lengths else 0,
        "sentence_word_stdev": round(statistics.pstdev(lengths), 3) if len(lengths) > 1 else 0,
        "short_sentence_share": round(sum(length <= 9 for length in lengths) / max(1, len(lengths)), 4),
        "questions_per_1000_words": round(text.count("?") * 1000 / max(1, word_count), 3),
    }
    return metrics, excerpt, hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def _reference_from_metadata(
    metadata: dict[str, Any], channel: dict[str, str], cache_dir: Path,
) -> ReferenceVideo | None:
    video_id = str(metadata.get("id") or "").strip()
    duration = float(metadata.get("duration") or 0)
    if not video_id or duration < 480 or metadata.get("live_status") in {"is_live", "is_upcoming", "post_live"}:
        return None
    found_channel_id = str(metadata.get("channel_id") or metadata.get("uploader_id") or "")
    if found_channel_id and found_channel_id != channel["channel_id"]:
        return None
    url = _canonical_url(metadata)
    caption = _public_caption_file(url, video_id, cache_dir)
    cues = parse_vtt(caption) if caption else []
    metrics, excerpt, transcript_hash = _transcript_metrics(cues)
    if caption and caption.is_file():
        caption.unlink(missing_ok=True)
    upload = str(metadata.get("upload_date") or "")
    age = max(1, (date.today() - _upload_date(upload)).days)
    views = int(metadata.get("view_count") or 0)
    count = 8
    timecodes = sorted({round(max(0, min(duration - 2, duration * index / (count - 1))), 3) for index in range(count)})
    thumbnails = metadata.get("thumbnails") or []
    thumbnail = str((thumbnails[-1] if thumbnails else {}).get("url") or metadata.get("thumbnail") or "")
    record = ReferenceVideo(
        video_id=video_id, channel_id=channel["channel_id"], channel_handle=channel["handle"],
        title=str(metadata.get("title") or "Untitled"), url=url, upload_date=upload,
        duration_seconds=duration, view_count=views, views_per_day=round(views / age, 3),
        format_label=_format_label(str(metadata.get("title") or "")),
        chapters=list(metadata.get("chapters") or []), transcript_available=bool(cues),
        transcript_sha256=transcript_hash, opening_excerpt=excerpt,
        transcript_metrics=metrics, visual_timecodes=timecodes, thumbnail_url=thumbnail,
    )
    record.content_sha256 = _canonical_sha256({
        "video_id": record.video_id,
        "title": record.title,
        "upload_date": record.upload_date,
        "duration_seconds": record.duration_seconds,
        "view_count": record.view_count,
        "chapters": record.chapters,
        "transcript_sha256": record.transcript_sha256,
        "thumbnail_url": record.thumbnail_url,
    })
    return record


def _reference_cache_path(channel_key: str, video_id: str) -> Path:
    return FIDELITY_DATA_DIR / "_reference_cache" / channel_key / f"{video_id}.json"


def _listing_sha256(entry: dict[str, Any]) -> str:
    return _canonical_sha256({
        "id": entry.get("id"), "title": entry.get("title"),
        "duration": entry.get("duration"), "upload_date": entry.get("upload_date"),
        "timestamp": entry.get("timestamp"), "live_status": entry.get("live_status"),
    })


def _read_cached_reference(channel_key: str, video_id: str) -> ReferenceVideo | None:
    path = _reference_cache_path(channel_key, video_id)
    if not path.is_file():
        return None
    try:
        return ReferenceVideo.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cached_reference(channel_key: str, record: ReferenceVideo) -> None:
    path = _reference_cache_path(channel_key, record.video_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def _make_contact_sheet(
    frames: list[Path], destination: Path, labels: list[str] | None = None,
) -> Path:
    if not frames:
        raise ValueError("contact sheet requires at least one frame")
    cells: list[Image.Image] = []
    for index, frame in enumerate(frames[:4]):
        with Image.open(frame) as source:
            cell = ImageOps.fit(source.convert("RGB"), (480, 270), method=Image.Resampling.LANCZOS)
        if labels and index < len(labels):
            draw = ImageDraw.Draw(cell)
            font = ImageFont.load_default(size=18)
            label = labels[index]
            box = draw.textbbox((0, 0), label, font=font)
            width = box[2] - box[0]
            draw.rounded_rectangle((10, 10, 30 + width, 40), radius=6, fill=(8, 9, 9, 220))
            draw.text((20, 16), label, font=font, fill=(245, 244, 239))
        cells.append(cell)
    canvas = Image.new("RGB", (960, 540), (18, 19, 20))
    for index, cell in enumerate(cells):
        canvas.paste(cell, ((index % 2) * 480, (index // 2) * 270))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, quality=88, optimize=True)
    return destination


def _extract_public_frame_strip(record: ReferenceVideo, channel_key: str) -> str:
    """Cache analysis-only public playback frames without retaining the source video."""
    root = FIDELITY_DATA_DIR / "_reference_cache" / channel_key / "frame_strips"
    destination = root / f"{record.video_id}_{record.content_sha256[:12]}.jpg"
    if destination.is_file() and destination.stat().st_size > 1024:
        return str(destination)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return ""
    direct = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs",
         "--no-warnings", "--get-url", "-f",
         "bestvideo[height<=720][ext=mp4]/bestvideo[height<=720]/best[height<=720]",
         record.url],
        capture_output=True, text=True, timeout=120,
    )
    stream_url = next((line.strip() for line in direct.stdout.splitlines() if line.strip()), "")
    if direct.returncode or not stream_url:
        return ""
    frame_dir = root / f".{record.video_id}_{record.content_sha256[:12]}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    try:
        timecodes = record.visual_timecodes[1:7:2] or [record.duration_seconds * 0.2, record.duration_seconds * 0.5, record.duration_seconds * 0.8]
        for index, second in enumerate(timecodes[:4]):
            frame = frame_dir / f"frame_{index:02d}.jpg"
            process = subprocess.run(
                [ffmpeg, "-y", "-ss", f"{float(second):.3f}", "-i", stream_url,
                 "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "3", str(frame)],
                capture_output=True, text=True, timeout=120,
            )
            if process.returncode == 0 and frame.is_file() and frame.stat().st_size > 512:
                frames.append(frame)
        return str(_make_contact_sheet(frames, destination)) if frames else ""
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)


def refresh_reference_frame_strips(
    run: FidelityRun, corpus: dict[str, Any], *, per_channel: int = 6,
    should_cancel: Callable[[], bool] | None = None,
) -> int:
    """Enrich a cached corpus with analysis stills without refetching listings.

    Full reference videos are never retained. Only four-frame 960x540 contact
    sheets are persisted, and existing valid sheets are reused by content hash.
    """
    changed = 0
    for key in CHANNELS:
        videos = corpus.get("channels", {}).get(key, {}).get("videos", [])
        for index, item in enumerate(videos[: max(0, per_channel)]):
            if should_cancel and should_cancel():
                raise InterruptedError("reference frame-strip refresh canceled")
            record = ReferenceVideo.model_validate(item)
            current = Path(record.analysis_frame_strip) if record.analysis_frame_strip else None
            if current and current.is_file() and current.stat().st_size > 1024:
                continue
            try:
                frame_strip = _extract_public_frame_strip(record, key)
            except Exception:
                frame_strip = ""
            if not frame_strip:
                continue
            record.analysis_frame_strip = frame_strip
            videos[index] = record.model_dump(mode="json")
            _write_cached_reference(key, record)
            changed += 1
    if not changed:
        return 0
    target = Path(run.corpus_path) if run.corpus_path else fidelity_run_dir(run.run_id) / "reference_corpus.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(corpus, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
    run.corpus_path = str(target)
    run.corpus_sha256 = _canonical_sha256(corpus)
    run.artifacts["reference_corpus"] = str(target)
    save_fidelity_run(run)
    return changed


def _data_url(path: Path) -> str:
    suffix = path.suffix.casefold()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _video_contact_sheet(video: Path, cache_root: Path) -> str:
    if not video.is_file() or not shutil.which("ffmpeg"):
        return ""
    signature = hashlib.sha256(
        f"{video.resolve()}:{video.stat().st_size}:{video.stat().st_mtime_ns}".encode("utf-8")
    ).hexdigest()[:16]
    destination = cache_root / f"candidate_{signature}.jpg"
    if destination.is_file() and destination.stat().st_size > 1024:
        return str(destination)
    frame_dir = cache_root / f".{signature}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    pattern = frame_dir / "frame_%02d.jpg"
    try:
        process = subprocess.run(
            [shutil.which("ffmpeg") or "ffmpeg", "-y", "-i", str(video),
             "-vf", "fps=4/600,scale=640:-2", "-frames:v", "4", str(pattern)],
            capture_output=True, text=True, timeout=300,
        )
        frames = sorted(frame_dir.glob("frame_*.jpg"))
        if process.returncode or not frames:
            return ""
        return str(_make_contact_sheet(frames, destination))
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)


def _representative_video_contact_sheets(
    video: Path, shots: list[Any], cache_root: Path,
) -> list[str]:
    """Build three timecoded strips stratified across the required visual mix.

    Four uniform frames cannot fairly judge an eight-minute edit and can miss
    entire visual classes. This sampler contributes three shots from each
    policy category, covering source footage, article evidence, motion design,
    and miscellaneous editorial visuals without retaining the source video.
    """
    if not video.is_file() or not shutil.which("ffmpeg") or not shots:
        return []
    sample_contract = [
        {
            "id": str(getattr(shot, "id", "")),
            "category": str(getattr(shot, "visual_category", "") or "miscellaneous"),
            "start": round(float(getattr(shot, "start_seconds", 0)), 3),
            "duration": round(float(getattr(shot, "duration_seconds", 0)), 3),
        }
        for shot in shots
    ]
    signature = hashlib.sha256(
        (
            f"{video.resolve()}:{video.stat().st_size}:{video.stat().st_mtime_ns}:"
            + json.dumps(sample_contract, sort_keys=True)
        ).encode("utf-8")
    ).hexdigest()[:16]
    expected = [cache_root / f"representative_{signature}_{index:02d}.jpg" for index in range(3)]
    if all(path.is_file() and path.stat().st_size > 1024 for path in expected):
        return [str(path) for path in expected]

    by_category: dict[str, list[Any]] = {}
    for shot in shots:
        category = str(getattr(shot, "visual_category", "") or "miscellaneous")
        by_category.setdefault(category, []).append(shot)
    category_order = ["youtube_broll", "article_evidence", "motion_graphics", "miscellaneous"]
    selected: list[Any] = []
    for category in category_order:
        items = by_category.get(category, [])
        if not items:
            continue
        indices = sorted({0, len(items) // 2, len(items) - 1})
        selected.extend(items[index] for index in indices[:3])

    frame_dir = cache_root / f".{signature}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    labels: list[str] = []
    try:
        for index, shot in enumerate(selected[:12]):
            second = float(getattr(shot, "start_seconds", 0)) + min(
                max(0.15, float(getattr(shot, "duration_seconds", 0)) * 0.55),
                max(0.15, float(getattr(shot, "duration_seconds", 0)) - 0.15),
            )
            frame = frame_dir / f"frame_{index:02d}.jpg"
            process = subprocess.run(
                [shutil.which("ffmpeg") or "ffmpeg", "-y", "-ss", f"{second:.3f}", "-i", str(video),
                 "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "3", str(frame)],
                capture_output=True, text=True, timeout=120,
            )
            if process.returncode or not frame.is_file() or frame.stat().st_size <= 512:
                continue
            frames.append(frame)
            category = str(getattr(shot, "visual_category", "miscellaneous")).replace("_", " ").upper()
            labels.append(f"{category} · {int(second // 60):02d}:{int(second % 60):02d}")
        outputs: list[str] = []
        for index in range(0, len(frames), 4):
            destination = cache_root / f"representative_{signature}_{index // 4:02d}.jpg"
            outputs.append(str(_make_contact_sheet(
                frames[index:index + 4], destination, labels[index:index + 4],
            )))
        return outputs
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)


def _word_ngrams(text: str, size: int = 8) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.casefold())
    return {tuple(words[index:index + size]) for index in range(max(0, len(words) - size + 1))}


def _difference_hash(path: Path, hash_size: int = 8) -> tuple[int, int] | None:
    if not path.is_file():
        return None
    try:
        with Image.open(path) as source:
            gray = source.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            pixels = list(gray.getdata())
    except Exception:
        return None
    value = 0
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for column in range(hash_size):
            value = (value << 1) | int(pixels[offset + column] > pixels[offset + column + 1])
    return value, hash_size * hash_size


def originality_report(
    project: EpisodeProject, profile: dict[str, Any], run: FidelityRun,
) -> dict[str, Any]:
    """Reject verbatim reference phrasing and near-identical frame compositions."""
    narration = project.script.narration if project.script else ""
    candidate_ngrams = _word_ngrams(narration)
    matched_phrases: list[str] = []
    for reference in profile.get("reference_clips", {}).get("script", []):
        overlap = candidate_ngrams & _word_ngrams(str(reference.get("transcript_segment") or ""))
        for words in sorted(overlap):
            phrase = " ".join(words)
            if phrase not in matched_phrases:
                matched_phrases.append(phrase)
    video_path = Path(str(project.artifacts.get("video") or ""))
    candidate_path = Path("")
    if video_path.is_file():
        raw = _video_contact_sheet(video_path, fidelity_run_dir(run.run_id) / "candidate_frame_strips")
        candidate_path = Path(raw) if raw else Path("")
    candidate_hash = _difference_hash(candidate_path) if str(candidate_path) else None
    visual_matches: list[dict[str, Any]] = []
    if candidate_hash:
        candidate_value, bit_count = candidate_hash
        for reference in profile.get("reference_clips", {}).get("visual", []):
            path = Path(str(reference.get("frame_strip") or ""))
            reference_hash = _difference_hash(path)
            if not reference_hash:
                continue
            similarity = 1.0 - ((candidate_value ^ reference_hash[0]).bit_count() / bit_count)
            if similarity >= 0.97:
                visual_matches.append({
                    "video_id": reference.get("video_id", ""),
                    "similarity": round(similarity, 6),
                })
    return {
        "passed": not matched_phrases and not visual_matches,
        "script": {
            "passed": not matched_phrases,
            "ngram_size": 8,
            "matched_phrase_count": len(matched_phrases),
            "matched_phrases": matched_phrases[:10],
        },
        "visual": {
            "passed": not visual_matches,
            "near_duplicate_threshold": 0.97,
            "matches": visual_matches,
        },
    }


def integrated_verification_gates(
    project: EpisodeProject, profile: dict[str, Any], run: FidelityRun,
) -> dict[str, Any]:
    """Collect every non-fidelity acceptance gate in one auditable record."""
    final_qc = project.qc.get("final") or {}
    fact_check = project.qc.get("fact_check") or {}
    audio = project.qc.get("audio_listenability") or {}
    readiness = project.qc.get("review_readiness") or {}
    source_shots = [shot for shot in project.shots if shot.source_id]
    rights_passed = bool(project.rights) and all(shot.rights_note for shot in source_shots)
    voice_rights = project.episode.get("voice_rights") or project.narration.get("voice_rights") or {}
    originality = originality_report(project, profile, run)
    checks = {
        "facts": bool(fact_check.get("passed")),
        "originality": bool(originality.get("passed")),
        "rights_and_provenance": rights_passed,
        "render_qc": bool(final_qc.get("passed")),
        "exact_1920x1080": final_qc.get("resolution") == [1920, 1080],
        "narration_intelligible": bool(audio.get("passed")),
        "one_voice_profile": bool(project.narration.get("voice_profile_id") and voice_rights.get("status")),
        "review_readiness": bool(readiness.get("passed")),
        "publishing_disabled": not bool(project.episode.get("publishing_enabled", False)),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "originality": originality,
    }


def select_reference_videos(
    candidates: list[ReferenceVideo], *, count: int = 30, transcript_required: bool = False,
) -> list[ReferenceVideo]:
    eligible = [item for item in candidates if item.duration_seconds >= 480]
    if transcript_required:
        eligible = [item for item in eligible if item.transcript_available]
    eligible.sort(key=lambda item: (_upload_date(item.upload_date), item.views_per_day), reverse=True)
    newest = eligible[: min(20, count)]
    selected_ids = {item.video_id for item in newest}
    remaining = [item for item in eligible if item.video_id not in selected_ids]
    by_format: dict[str, list[ReferenceVideo]] = {}
    for item in sorted(remaining, key=lambda value: value.views_per_day, reverse=True):
        by_format.setdefault(item.format_label, []).append(item)
    diverse: list[ReferenceVideo] = []
    while len(newest) + len(diverse) < count and any(by_format.values()):
        for label in sorted(by_format):
            if by_format[label] and len(newest) + len(diverse) < count:
                diverse.append(by_format[label].pop(0))
    result = newest + diverse
    if len(result) < count:
        raise RuntimeError(f"reference corpus has {len(result)} eligible videos; required {count}")
    return result[:count]


def build_reference_corpus(
    run: FidelityRun, *, count: int = FIDELITY_CORPUS_SIZE,
    should_cancel: Callable[[], bool] | None = None, report_progress: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    run.status = "building_corpus"
    save_fidelity_run(run)
    payload = {"schema_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(), "channels": {}}
    for channel_index, (key, channel) in enumerate(CHANNELS.items()):
        if should_cancel and should_cancel():
            raise InterruptedError("fidelity corpus build canceled")
        entries = _discover_entries(channel["url"], min(60, count + 20))
        cache_dir = FIDELITY_DATA_DIR / "_caption_cache" / key
        candidates: list[ReferenceVideo] = []
        entry_ids = {
            str(entry.get("id") or "").strip(): entry for entry in entries
            if str(entry.get("id") or "").strip()
        }
        # Reuse immutable transcript and structural analysis from prior runs.
        # Popularity is refreshed below only for videos that still need hydration;
        # the channel index is always fetched so new uploads are discovered.
        cached_by_id = {}
        for video_id, entry in entry_ids.items():
            cached = _read_cached_reference(key, video_id)
            if cached is not None and cached.listing_sha256 == _listing_sha256(entry):
                cached_by_id[video_id] = cached
        candidates.extend(cached_by_id.values())
        workers = min(6, max(1, len(entries)))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"fidelity-{key}") as pool:
            futures = {
                pool.submit(_hydrate, _canonical_url(entry)): entry
                for entry in entries
                if _canonical_url(entry) and str(entry.get("id") or "") not in cached_by_id
            }
            for future in as_completed(futures):
                if should_cancel and should_cancel():
                    raise InterruptedError("fidelity corpus build canceled")
                try:
                    entry = futures[future]
                    item = _reference_from_metadata(future.result(), channel, cache_dir)
                    if item:
                        item.listing_sha256 = _listing_sha256(entry)
                        candidates.append(item)
                        _write_cached_reference(key, item)
                except Exception:
                    continue
        selected = select_reference_videos(candidates, count=count, transcript_required=(key == "ai_search"))
        # A small, diverse calibration subset gets real timecoded playback
        # frames. These are analysis-only stills, not retained source videos.
        for record in selected[: min(6, len(selected))]:
            if not record.analysis_frame_strip or not Path(record.analysis_frame_strip).is_file():
                try:
                    record.analysis_frame_strip = _extract_public_frame_strip(record, key)
                except Exception:
                    record.analysis_frame_strip = ""
            _write_cached_reference(key, record)
        payload["channels"][key] = {
            **channel, "selection": {"newest": 20, "representative": count - 20},
            "videos": [item.model_dump(mode="json") for item in selected],
        }
        run.channels[key] = {
            **channel, "video_count": len(selected),
            "transcript_count": sum(item.transcript_available for item in selected),
            "video_ids": [item.video_id for item in selected],
        }
        if report_progress:
            report_progress(10 + (channel_index + 1) * 15)
        save_fidelity_run(run)
    target = fidelity_run_dir(run.run_id) / "reference_corpus.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    run.corpus_path = str(target)
    run.corpus_sha256 = _canonical_sha256(payload)
    run.artifacts["reference_corpus"] = str(target)
    save_fidelity_run(run)
    return payload


def _range(values: list[float], fallback: tuple[float, float]) -> list[float]:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return list(fallback)
    return [round(clean[max(0, math.floor((len(clean) - 1) * 0.2))], 3), round(clean[math.ceil((len(clean) - 1) * 0.8)], 3)]


def build_pattern_library(run: FidelityRun, corpus: dict[str, Any]) -> dict[str, Any]:
    search = corpus["channels"]["ai_search"]["videos"]
    labs = corpus["channels"]["ai_labs"]["videos"]
    support_search = [item["video_id"] for item in search[:6]]
    support_labs = [item["video_id"] for item in labs[:6]]
    means = [float((item.get("transcript_metrics") or {}).get("mean_sentence_words", 0)) for item in search]
    stdevs = [float((item.get("transcript_metrics") or {}).get("sentence_word_stdev", 0)) for item in search]
    questions = [float((item.get("transcript_metrics") or {}).get("questions_per_1000_words", 0)) for item in search]
    short_shares = [float((item.get("transcript_metrics") or {}).get("short_sentence_share", 0)) for item in search]
    chapter_counts = [float(len(item.get("chapters") or [])) for item in search]
    prior_script_profile_path = PROJECT_ROOT / "configs" / "conversational_script_profile.json"
    prior_motion_study_path = PROJECT_ROOT / "research" / "ai_labs_motion_refresh_2026_08_18.md"
    prior_script_profile = (
        json.loads(prior_script_profile_path.read_text(encoding="utf-8"))
        if prior_script_profile_path.is_file() else {}
    )
    prior_motion_study_sha256 = (
        hashlib.sha256(prior_motion_study_path.read_bytes()).hexdigest()
        if prior_motion_study_path.is_file() else ""
    )
    library = {
        "schema_version": "1.0", "profile_id": "ai-search-x-ai-labs-fidelity-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_sha256": _canonical_sha256(corpus),
        "channels": {key: {**CHANNELS[key], "video_count": len(corpus["channels"][key]["videos"])} for key in CHANNELS},
        "reused_project_research": {
            "script_profile": str(prior_script_profile_path),
            "script_profile_id": prior_script_profile.get("profile_id", ""),
            "script_sample_size": (prior_script_profile.get("research_basis") or {}).get("sample_size", 0),
            "motion_study": str(prior_motion_study_path),
            "motion_study_sha256": prior_motion_study_sha256,
        },
        "reference_clips": {
            "script": [
                {"video_id": item["video_id"], "url": item["url"],
                 "timecodes": item["visual_timecodes"][:3],
                 "transcript_segment": item.get("opening_excerpt", "")}
                for item in search[:12]
            ],
            "visual": [
                {"video_id": item["video_id"], "url": item["url"],
                 "timecodes": item["visual_timecodes"][:3],
                 "frame_strip": item.get("analysis_frame_strip", "")}
                for item in labs[:12]
            ],
        },
        "script": {
            "hook_style": {"rule": "Open on a concrete result, contradiction, or consequence; translate why it matters within two sentences.", "references": support_search[:4], "confidence": 0.9},
            "sentence_rhythm": {"rule": "Alternate compact landings with fuller explanations; avoid metronomic sentence lengths.", "mean_sentence_words": _range(means, (12, 21)), "sentence_stdev": _range(stdevs, (6, 12)), "references": support_search[1:5], "confidence": 0.88},
            "question_use": {"rule": "Questions must open a real information gap and receive a nearby answer; never use them as filler.", "questions_per_1000_words": _range(questions, (1, 8)), "references": support_search[2:6], "confidence": 0.86},
            "callbacks": {"rule": "Reuse an early concrete example only when it simplifies a later mechanism or verdict.", "references": support_search[:4], "confidence": 0.82},
            "pacing": {"rule": "Earn attention every 45-75 seconds with proof, a visible example, or a changed conclusion.", "references": support_search[1:5], "confidence": 0.9},
            "structure": {"rule": "Consequence or result, proof, plain-language mechanism, practical implication, limitation, verdict.", "references": support_search[2:6], "confidence": 0.91},
        },
        "visual": {
            "typography": {"rule": "One dominant statement, large readable type, restrained labels, and functional negative space.", "references": support_labs[:4], "confidence": 0.86},
            "motion_style": {"rule": "Lock the camera and animate state changes inside the interface or diagram; use cuts or short fades.", "references": support_labs[1:5], "confidence": 0.9},
            "color_palette": {"rule": "Neutral editorial base with small product-native accents; no broad yellow or generic purple glow.", "references": support_labs[2:6], "confidence": 0.86},
            "chart_data_viz": {"rule": "Direct labels, visible source, narration-led reveal, and no decorative chart furniture.", "references": support_labs[:4], "confidence": 0.82},
            "information_density": {"rule": "One claim per frame and one dominant proof object occupying most of the usable stage.", "references": support_labs[1:5], "confidence": 0.9},
            "visual_reveal_pacing": {"rule": "Change a meaningful state every two to three seconds without ambient drift.", "references": support_labs[2:6], "confidence": 0.89},
        },
        "originality": {
            "required": True,
            "rule": "Use only transferable grammar; never copy wording, catchphrases, proprietary artwork, or recognizable frame compositions.",
        },
    }
    source_by_id = {
        item["video_id"]: item
        for item in [*search, *labs]
    }
    observed_ranges: dict[str, dict[str, Any]] = {
        "hook_style": {
            "opening_excerpt_words": _range(
                [float(len(item.get("opening_excerpt", "").split())) for item in search], (25, 65),
            ),
        },
        "sentence_rhythm": {
            "mean_sentence_words": _range(means, (12, 21)),
            "sentence_word_stdev": _range(stdevs, (6, 12)),
            "short_sentence_share": _range(short_shares, (0.12, 0.55)),
        },
        "question_use": {"questions_per_1000_words": _range(questions, (1, 8))},
        "callbacks": {"qualitative_band": "one purposeful return to an earlier concrete example per section"},
        "pacing": {"proof_or_conclusion_change_seconds": [45, 75]},
        "structure": {
            "chapter_count": _range(chapter_counts, (4, 12)),
            "observed_order": ["consequence", "proof", "mechanism", "implication", "limitation", "verdict"],
        },
        "typography": {"dominant_statements_per_frame": [1, 1], "supporting_labels_per_frame": [0, 3]},
        "motion_style": {"camera_behavior": ["locked", "short purposeful reframe"]},
        "color_palette": {"base": ["neutral light", "neutral dark"], "accent_scope": ["single product accent", "two coordinated accents"]},
        "chart_data_viz": {"simultaneous_series": [1, 3], "source_label_required": True},
        "information_density": {"dominant_proof_objects_per_frame": [1, 1], "supporting_items_per_frame": [0, 3]},
        "visual_reveal_pacing": {"meaningful_state_change_seconds": [2, 3]},
    }
    for section in ("script", "visual"):
        for dimension, pattern in library[section].items():
            pattern["applicable_episode_formats"] = ["tool_test", "weekly_roundup", "deep_dive"]
            pattern["originality_warning"] = (
                "Transfer the underlying editorial function only; do not copy wording, branded art, or composition."
            )
            pattern["observed_range"] = observed_ranges[dimension]
            pattern["supporting_evidence"] = [
                {
                    "video_id": video_id,
                    "url": source_by_id[video_id]["url"],
                    "timecodes": source_by_id[video_id].get("visual_timecodes", [])[:3],
                }
                for video_id in pattern["references"]
                if video_id in source_by_id
            ]
    FIDELITY_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIDELITY_PROFILE_PATH.write_text(json.dumps(library, indent=2, ensure_ascii=False), encoding="utf-8")
    run.pattern_library_path = str(FIDELITY_PROFILE_PATH)
    run.pattern_library_sha256 = _canonical_sha256(library)
    run.artifacts["pattern_library"] = str(FIDELITY_PROFILE_PATH)
    run.status = "pattern_library_finalized"
    save_fidelity_run(run)
    record_milestone(run, "pattern_library_finalized", str(FIDELITY_PROFILE_PATH))
    return library


def _clamp_score(value: float) -> int:
    return max(1, min(5, round(value)))


def score_script_dimensions(script: Script, profile: dict[str, Any] | None = None) -> dict[str, int]:
    text = script.narration.strip()
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    lengths = [len(item.split()) for item in sentences]
    first = script.beats[0] if script.beats else None
    hook_words = len(first.narration.split()) if first else 0
    concrete = bool(first and (first.claim_ids or re.search(r"\b\d[\d,.%]*\b", first.narration)))
    generic = bool(first and re.search(r"\b(?:welcome back|let'?s dive|in this video|game[- ]changer)\b", first.narration, re.I))
    hook = 5 if first and first.purpose == "hook" and 25 <= hook_words <= 65 and concrete and not generic else 4 if first and first.purpose == "hook" and not generic else 2
    mean = statistics.fmean(lengths) if lengths else 0
    stdev = statistics.pstdev(lengths) if len(lengths) > 1 else 0
    short_share = sum(value <= 9 for value in lengths) / max(1, len(lengths))
    rhythm = 5 if 10 <= mean <= 24 and stdev >= 6 and 0.12 <= short_share <= 0.55 else 4 if 8 <= mean <= 28 and stdev >= 4 else 2
    questions = text.count("?") * 1000 / max(1, script.word_count)
    question_score = 5 if 1 <= questions <= 8 else 4 if questions <= 12 else 2
    words = [word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text)]
    stop = {"this", "that", "with", "from", "have", "your", "they", "what", "when", "where", "about", "into", "there"}
    span = max(1, len(words) // 4)
    overlap = (set(words[:span]) & set(words[-span:])) - stop
    callbacks = 5 if len(overlap) >= 3 else 4 if len(overlap) >= 1 else 3
    beat_lengths = [len(beat.narration.split()) for beat in script.beats]
    pacing = 5 if 1250 <= script.word_count <= 1800 and beat_lengths and max(beat_lengths) <= 80 and statistics.median(beat_lengths) <= 60 else 4 if beat_lengths and max(beat_lengths) <= 100 else 2
    purposes = {beat.purpose for beat in script.beats}
    required = {"hook", "evidence", "analysis", "limitation", "verdict"}
    mapped = all(beat.claim_ids or beat.purpose in {"analysis", "transition", "outro", "show_intro", "weekly_recap"} for beat in script.beats)
    structure = 5 if required.issubset(purposes) and mapped else 4 if {"hook", "evidence", "analysis"}.issubset(purposes) else 2
    return dict(zip(SCRIPT_DIMENSIONS, (hook, rhythm, question_score, callbacks, pacing, structure)))


def _quantitative_beat_ids(script: Script | None) -> set[str]:
    """Return beats that contain an actual measurable fact, not a model version."""
    if not script:
        return set()
    numeric_unit = re.compile(
        r"(?:\b\d+(?:\.\d+)?\s*(?:%|p|k|seconds?|minutes?|hours?|frames?|times?)\b"
        r"|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|sixty)\s+"
        r"(?:seconds?|minutes?|hours?|frames?|percent|times?)\b"
        r"|\b(?:faster|slower|third of the cost|aspect ratios?|cumulative cap)\b)",
        re.I,
    )
    return {beat.id for beat in script.beats if numeric_unit.search(beat.narration)}


def script_dimension_distances(script: Script, profile: dict[str, Any]) -> dict[str, float]:
    text = script.narration.strip()
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    lengths = [len(item.split()) for item in sentences]
    mean = statistics.fmean(lengths) if lengths else 0.0
    stdev = statistics.pstdev(lengths) if len(lengths) > 1 else 0.0
    short_share = sum(value <= 9 for value in lengths) / max(1, len(lengths))
    rhythm_profile = profile.get("script", {}).get("sentence_rhythm", {})
    mean_band = rhythm_profile.get("mean_sentence_words", [10, 24])
    stdev_band = rhythm_profile.get("sentence_stdev", [6, 12])

    def outside(value: float, band: list[float], scale: float = 1.0) -> float:
        low, high = float(band[0]), float(band[-1])
        return round(max(low - value, value - high, 0.0) / max(scale, high - low, 1.0), 6)

    first = script.beats[0] if script.beats else None
    hook_words = len(first.narration.split()) if first else 0
    hook_distance = (
        (0 if first and first.purpose == "hook" else 1)
        + outside(float(hook_words), [25, 65], 40)
        + (1 if first and re.search(r"\b(?:welcome back|let'?s dive|in this video|game[- ]changer)\b", first.narration, re.I) else 0)
        + (0 if first and (first.claim_ids or re.search(r"\b\d[\d,.%]*\b", first.narration)) else 0.5)
    )
    question_rate = text.count("?") * 1000 / max(1, script.word_count)
    question_band = profile.get("script", {}).get("question_use", {}).get("questions_per_1000_words", [1, 8])
    words = [word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text)]
    stop = {"this", "that", "with", "from", "have", "your", "they", "what", "when", "where", "about", "into", "there"}
    span = max(1, len(words) // 4)
    callback_overlap = len((set(words[:span]) & set(words[-span:])) - stop)
    beat_lengths = [len(beat.narration.split()) for beat in script.beats]
    purposes = {beat.purpose for beat in script.beats}
    required = {"hook", "evidence", "analysis", "limitation", "verdict"}
    return {
        "hook_style": round(hook_distance, 6),
        "sentence_rhythm": round(
            outside(mean, list(mean_band)) + outside(stdev, list(stdev_band))
            + outside(short_share, [0.12, 0.55]), 6
        ),
        "question_use": outside(question_rate, list(question_band)),
        "callbacks": round(max(0, 3 - callback_overlap) / 3, 6),
        "pacing": round(
            outside(float(script.word_count), [1250, 1800], 550)
            + (max(0, max(beat_lengths, default=0) - 80) / 80), 6
        ),
        "structure": round(len(required - purposes) / len(required), 6),
    }


def score_storyboard_dimensions(project: EpisodeProject) -> dict[str, int]:
    shots = project.shots
    overrides = project.editorial_plan.get("fidelity_visual_overrides") or {}
    if not shots:
        return {dimension: 1 for dimension in VISUAL_DIMENSIONS}
    source_shots = [shot for shot in shots if shot.asset_type in {"screenshot", "screen_recording", "official_demo"}]
    locked_share = sum(shot.motion_style == "locked" for shot in source_shots) / max(1, len(source_shots))
    odd_transitions = sum(shot.transition not in {"cut", "dissolve"} for shot in shots)
    motion = 5 if locked_share >= 0.8 and not odd_transitions and all(shot.motion_style != "float" for shot in shots) else 4 if not odd_transitions else 2
    typography = 5 if overrides.get("typography_profile") == "large_editorial" else 4
    palette = 5 if overrides.get("palette_profile") == "neutral_product_accent" else 4
    numeric_beats = _quantitative_beat_ids(project.script)
    rights_source_by_shot = {
        str(entry.get("shot_id")): str(entry.get("source_id") or "")
        for entry in project.rights if entry.get("shot_id")
    }
    evidence_visualized = {
        shot.beat_id for shot in shots
        if shot.asset_type == "chart"
        or (
            shot.asset_type in {"screenshot", "screen_recording", "official_demo"}
            and bool(shot.source_id or rights_source_by_shot.get(shot.id))
        )
    }
    nonquant_charts = {
        shot.beat_id for shot in shots
        if shot.asset_type == "chart" and shot.beat_id not in numeric_beats
    }
    charts = 5 if (
        not numeric_beats
        or (numeric_beats.issubset(evidence_visualized) and not nonquant_charts)
    ) else 3
    durations = [shot.duration_seconds for shot in shots]
    density = 5 if len(shots) >= 70 and statistics.median(durations) <= 6 and overrides.get("max_information_items", 3) <= 3 else 4 if statistics.median(durations) <= 7 else 2
    reveal = 5 if max(durations) <= 12 and overrides.get("meaningful_state_change_seconds", 2.5) <= 3 else 4 if max(durations) <= 18 else 2
    return dict(zip(VISUAL_DIMENSIONS, (typography, motion, palette, charts, density, reveal)))


def storyboard_dimension_distances(project: EpisodeProject) -> dict[str, float]:
    shots = project.shots
    overrides = project.editorial_plan.get("fidelity_visual_overrides") or {}
    if not shots:
        return {dimension: 1.0 for dimension in VISUAL_DIMENSIONS}
    source_shots = [shot for shot in shots if shot.asset_type in {"screenshot", "screen_recording", "official_demo"}]
    locked_share = sum(shot.motion_style == "locked" for shot in source_shots) / max(1, len(source_shots))
    transition_error_share = sum(shot.transition not in {"cut", "dissolve"} for shot in shots) / len(shots)
    numeric_beats = _quantitative_beat_ids(project.script)
    rights_source_by_shot = {
        str(entry.get("shot_id")): str(entry.get("source_id") or "")
        for entry in project.rights if entry.get("shot_id")
    }
    evidence_visualized = {
        shot.beat_id for shot in shots
        if shot.asset_type == "chart"
        or (
            shot.asset_type in {"screenshot", "screen_recording", "official_demo"}
            and bool(shot.source_id or rights_source_by_shot.get(shot.id))
        )
    }
    durations = [shot.duration_seconds for shot in shots]
    missing_charts = len(numeric_beats - evidence_visualized) / max(1, len(numeric_beats))
    return {
        "typography": 0.0 if overrides.get("typography_profile") == "large_editorial" else 1.0,
        "motion_style": round((1 - locked_share) + transition_error_share, 6),
        "color_palette": 0.0 if overrides.get("palette_profile") == "neutral_product_accent" else 1.0,
        "chart_data_viz": round(missing_charts, 6),
        "information_density": round(
            max(0, 70 - len(shots)) / 70
            + max(0.0, statistics.median(durations) - 6) / 6
            + max(0, int(overrides.get("max_information_items", 4)) - 3) / 3,
            6,
        ),
        "visual_reveal_pacing": round(
            max(0.0, max(durations) - 12) / 12
            + max(0.0, float(overrides.get("meaningful_state_change_seconds", 9)) - 3) / 3,
            6,
        ),
    }


def choose_lowest_dimension(scores: dict[str, int], distance: dict[str, float] | None = None) -> str:
    if not scores:
        raise ValueError("cannot choose a fidelity dimension from an empty scorecard")
    order = {name: index for index, name in enumerate(ALL_DIMENSIONS)}
    distance = distance or {}
    return min(scores, key=lambda name: (scores[name], -float(distance.get(name, 0)), order.get(name, 999)))


def build_blind_packet(
    stage: Literal["script", "storyboard", "integrated"], candidate: dict[str, Any],
    profile: dict[str, Any], dimensions: tuple[str, ...],
) -> dict[str, Any]:
    """Create a stable, anonymized order without exposing iteration or authorship."""
    hidden = {"iteration", "iteration_number", "authorship", "author", "prior_scores", "target_dimension"}
    candidate_clean = {
        key: value for key, value in candidate.items()
        if not key.startswith("_") and key not in hidden
    }
    candidate_hash = _canonical_sha256(candidate_clean)
    candidate_id = f"packet_{candidate_hash[:10]}"
    entries = [{"packet_id": candidate_id, "material": candidate_clean}]
    reference_key = "script" if stage == "script" else "visual"
    for index, reference in enumerate(profile.get("reference_clips", {}).get(reference_key, [])[:4]):
        reference_material = {
            "video_id": reference.get("video_id", ""),
            "timecodes": reference.get("timecodes", []),
            "transcript_segment": reference.get("transcript_segment", ""),
            "observed_band": {
                name: (profile["script"] if name in SCRIPT_DIMENSIONS else profile["visual"])[name]
                for name in dimensions
            },
        }
        entries.append({
            "packet_id": f"packet_{_canonical_sha256(reference_material)[:10]}",
            "material": reference_material,
        })
    entries.sort(key=lambda item: hashlib.sha256(
        f"{candidate_hash}:{item['packet_id']}".encode("utf-8")
    ).hexdigest())
    return {
        "stage": stage,
        "candidate_packet_id": candidate_id,
        "packets": entries,
        "dimensions_to_score": list(dimensions),
        "anti_imitation_gate": profile["originality"],
    }


BLIND_REVIEW_SCHEMA = {
    "type": "json_schema", "json_schema": {"name": "FidelityBlindReview", "strict": True, "schema": {
        "type": "object", "additionalProperties": False, "required": ["scores", "notes"],
        "properties": {
            "scores": {"type": "object", "additionalProperties": False,
                "properties": {name: {"type": "integer", "minimum": 1, "maximum": 5} for name in ALL_DIMENSIONS},
                "required": list(ALL_DIMENSIONS)},
            "notes": {"type": "object", "additionalProperties": False,
                "properties": {name: {"type": "string"} for name in ALL_DIMENSIONS},
                "required": list(ALL_DIMENSIONS)},
        },
    }},
}


def _blind_review(
    stage: Literal["script", "storyboard", "integrated"], candidate: dict[str, Any],
    profile: dict[str, Any], dimensions: tuple[str, ...],
) -> tuple[dict[str, int], dict[str, str]]:
    packet = build_blind_packet(stage, candidate, profile, dimensions)
    content: list[dict[str, Any]] = [{
        "type": "text",
        "text": (
            "Score only candidate_packet_id. Packet order is hash-randomized and contains no authorship or iteration data. "
            "Every attached image is explicitly labeled as REFERENCE STRIP or CANDIDATE STRIP. "
            "If no CANDIDATE STRIP is attached, do not infer rendered colors, glow, compositing, or frame quality; "
            "score only the candidate storyboard evidence and contracts.\n\n"
            + json.dumps(packet, ensure_ascii=False)
        ),
    }]
    if stage in {"storyboard", "integrated"}:
        for item in profile.get("reference_clips", {}).get("visual", [])[:4]:
            frame_strip = Path(str(item.get("frame_strip") or ""))
            if frame_strip.is_file():
                content.append({
                    "type": "text",
                    "text": f"REFERENCE STRIP — video_id={item.get('video_id', '')}; timecodes={item.get('timecodes', [])}",
                })
                content.append({"type": "image_url", "image_url": {"url": _data_url(frame_strip)}})
        for raw in candidate.get("_frame_strip_paths", [])[:3]:
            frame_strip = Path(str(raw))
            if frame_strip.is_file():
                content.append({"type": "text", "text": "CANDIDATE STRIP — anonymous rendered output"})
                content.append({"type": "image_url", "image_url": {"url": _data_url(frame_strip)}})
    raw = editorial.call_openrouter(
        OPENROUTER_VERIFY_MODEL,
        "You are an isolated fidelity evaluator. You did not generate the candidate and cannot see prior drafts or scores. "
        "Judge only transferable editorial behavior. Do not reward copied wording, catchphrases, traced layouts, or proprietary art. "
        "Score the anonymous candidate against the supplied reference band. A 5 means it sits inside the strongest observed band "
        "while remaining original. Use 1 for a clear miss. Return every schema dimension; use 5 for dimensions outside the requested stage.\n\n"
        ,
        content,
        BLIND_REVIEW_SCHEMA,
        temperature=0.0,
    )
    scores = {name: int(raw["scores"][name]) for name in dimensions}
    notes = {name: str((raw.get("notes") or {}).get(name, "")) for name in dimensions}
    return scores, notes


def score_script(script: Script, profile: dict[str, Any]) -> FidelityScorecard:
    deterministic = score_script_dimensions(script, profile)
    distances = script_dimension_distances(script, profile)
    blind, notes = _blind_review("script", script.model_dump(mode="json"), profile, SCRIPT_DIMENSIONS)
    final = {name: min(deterministic[name], blind[name]) for name in SCRIPT_DIMENSIONS}
    refs = sorted({ref for item in profile["script"].values() for ref in item.get("references", [])})
    return FidelityScorecard(
        stage="script", deterministic=deterministic, blind_review=blind, final=final,
        distance_from_reference=distances, notes=notes, reference_ids=refs,
        artifact_sha256=canonical_hash(script.model_dump(mode="json")),
    )


def _storyboard_review_candidate(project: EpisodeProject) -> dict[str, Any]:
    """Build a compact, evenly sampled storyboard packet without fake frames."""
    shots_by_type: dict[str, list[Shot]] = {}
    for shot in project.shots:
        shots_by_type.setdefault(shot.asset_type, []).append(shot)

    def sample_evenly(items: list[Shot], maximum: int = 3) -> list[Shot]:
        if len(items) <= maximum:
            return items
        indices = sorted({0, len(items) // 2, len(items) - 1})
        return [items[index] for index in indices[:maximum]]

    sampled_shots = [
        shot.model_dump(mode="json")
        for asset_type in sorted(shots_by_type)
        for shot in sample_evenly(shots_by_type[asset_type])
    ]
    raw_overrides = project.editorial_plan.get("fidelity_visual_overrides") or {}
    compact_overrides: dict[str, Any] = {}
    for key, value in raw_overrides.items():
        if key == "intra_shot_keyframes" and isinstance(value, list):
            middle_values = [
                float(item.get("seconds", [0, 0])[1])
                for item in value
                if isinstance(item, dict) and len(item.get("seconds", [])) >= 2
            ]
            compact_overrides[key] = {
                "count": len(value),
                "middle_state_seconds_range": (
                    [round(min(middle_values), 3), round(max(middle_values), 3)]
                    if middle_values else []
                ),
                "editorial_reasons": sorted({
                    str(item.get("editorial_reason") or "") for item in value
                    if isinstance(item, dict) and item.get("editorial_reason")
                }),
            }
        elif isinstance(value, list) and len(value) > 24:
            compact_overrides[key] = {"count": len(value), "sample": value[:3]}
        else:
            compact_overrides[key] = value
    return {
        "storyboard_metrics": {
            "shot_count": len(project.shots),
            "asset_types": {key: len(value) for key, value in shots_by_type.items()},
            "median_duration_seconds": statistics.median(shot.duration_seconds for shot in project.shots),
            "maximum_duration_seconds": max(shot.duration_seconds for shot in project.shots),
            "motion_styles": dict(Counter(shot.motion_style for shot in project.shots)),
            "transitions": dict(Counter(shot.transition for shot in project.shots)),
            "motion_templates": dict(Counter(shot.motion_template for shot in project.shots)),
        },
        "stratified_shot_sample": sampled_shots,
        "visual_overrides": compact_overrides,
        "candidate_frame_status": "not rendered at storyboard stage",
    }


def score_storyboard(project: EpisodeProject, profile: dict[str, Any]) -> FidelityScorecard:
    deterministic = score_storyboard_dimensions(project)
    distances = storyboard_dimension_distances(project)
    candidate = _storyboard_review_candidate(project)
    blind, notes = _blind_review("storyboard", candidate, profile, VISUAL_DIMENSIONS)
    final = {name: min(deterministic[name], blind[name]) for name in VISUAL_DIMENSIONS}
    refs = sorted({ref for item in profile["visual"].values() for ref in item.get("references", [])})
    return FidelityScorecard(
        stage="storyboard", deterministic=deterministic, blind_review=blind, final=final,
        distance_from_reference=distances, notes=notes, reference_ids=refs,
        artifact_sha256=canonical_hash({
            "shots": [shot.model_dump(mode="json") for shot in project.shots],
            "visual_overrides": project.editorial_plan.get("fidelity_visual_overrides") or {},
        }),
    )


def score_storyboard_targeted(
    project: EpisodeProject, profile: dict[str, Any], before: FidelityScorecard, target: str,
) -> FidelityScorecard:
    """Review only the edited visual dimension and freeze unrelated blind scores."""
    deterministic = score_storyboard_dimensions(project)
    distances = storyboard_dimension_distances(project)
    candidate = _storyboard_review_candidate(project)
    candidate["target_dimension"] = target
    review_profile = json.loads(json.dumps(profile))
    reference_clips = review_profile.setdefault("reference_clips", {})
    reference_clips["visual"] = reference_clips.get("visual", [])[:2]
    target_scores, target_notes = _blind_review(
        "storyboard", candidate, review_profile, (target,),
    )
    blind = before.blind_review.copy()
    blind[target] = target_scores[target]
    notes = before.notes.copy()
    notes[target] = target_notes[target]
    final = {
        name: min(deterministic[name], blind[name])
        for name in VISUAL_DIMENSIONS
    }
    refs = sorted({ref for item in profile["visual"].values() for ref in item.get("references", [])})
    return FidelityScorecard(
        stage="storyboard", deterministic=deterministic, blind_review=blind, final=final,
        distance_from_reference=distances, notes=notes, reference_ids=refs,
        artifact_sha256=canonical_hash({
            "shots": [shot.model_dump(mode="json") for shot in project.shots],
            "visual_overrides": project.editorial_plan.get("fidelity_visual_overrides") or {},
        }),
    )


def score_integrated(project: EpisodeProject, profile: dict[str, Any], run: FidelityRun) -> FidelityScorecard:
    if not project.script:
        raise ValueError("integrated fidelity scoring requires a script")
    deterministic = {**score_script_dimensions(project.script, profile), **score_storyboard_dimensions(project)}
    distances = {**script_dimension_distances(project.script, profile), **storyboard_dimension_distances(project)}
    frame_paths: list[str] = []
    video_path = Path(str(project.artifacts.get("video") or ""))
    if video_path.is_file():
        frame_paths.extend(_representative_video_contact_sheets(
            video_path, project.shots, fidelity_run_dir(run.run_id) / "candidate_frame_strips",
        ))
    candidate = {
        "script": project.script.model_dump(mode="json"),
        "shots": [shot.model_dump(mode="json") for shot in project.shots],
        "visual_overrides": project.editorial_plan.get("fidelity_visual_overrides") or {},
        "final_qc": project.qc.get("final") or {},
        "_frame_strip_paths": frame_paths,
    }
    blind, notes = _blind_review("integrated", candidate, profile, ALL_DIMENSIONS)
    final = {name: min(deterministic[name], blind[name]) for name in ALL_DIMENSIONS}
    refs = sorted({
        ref for group in (profile["script"], profile["visual"])
        for item in group.values() for ref in item.get("references", [])
    })
    return FidelityScorecard(
        stage="integrated", deterministic=deterministic, blind_review=blind, final=final,
        distance_from_reference=distances, notes=notes, reference_ids=refs,
        artifact_sha256=_canonical_sha256({
            "candidate": {key: value for key, value in candidate.items() if not key.startswith("_")},
            "video_signature": (
                {"size": video_path.stat().st_size, "modified_ns": video_path.stat().st_mtime_ns}
                if video_path.is_file() else {}
            ),
        }),
    )


def _budget_snapshot(
    openrouter_override: float = 0, magic_hour_override: int = 0, *,
    openrouter_absolute_cap_usd: float = 0, magic_hour_absolute_cap_credits: int = 0,
) -> FidelityBudget:
    openrouter = float(openrouter_override or OPENROUTER_STARTING_BALANCE_USD)
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is required before the first paid fidelity call")
    if not MAGIC_HOUR_API_KEY:
        raise RuntimeError("MAGIC_HOUR_API_KEY is required before the first paid fidelity call")
    if openrouter <= 0 and openrouter_absolute_cap_usd <= 0:
        response = requests.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}, timeout=30,
        )
        response.raise_for_status()
        data = response.json().get("data") or {}
        openrouter = float(data.get("limit_remaining") or 0)
        if openrouter <= 0:
            credits = requests.get(
                "https://openrouter.ai/api/v1/credits",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}, timeout=30,
            )
            if credits.ok:
                credit_data = credits.json().get("data") or {}
                openrouter = float(credit_data.get("total_credits", 0)) - float(credit_data.get("total_usage", 0))
    magic_hour = int(magic_hour_override or MAGIC_HOUR_STARTING_BALANCE_CREDITS)
    if openrouter <= 0 and openrouter_absolute_cap_usd <= 0:
        raise RuntimeError("OpenRouter remaining balance could not be read; set OPENROUTER_STARTING_BALANCE_USD")
    if magic_hour <= 0 and magic_hour_absolute_cap_credits <= 0:
        raise RuntimeError("set MAGIC_HOUR_STARTING_BALANCE_CREDITS from the Magic Hour dashboard")
    return FidelityBudget(
        openrouter_starting_balance_usd=openrouter,
        magic_hour_starting_balance_credits=magic_hour,
        openrouter_absolute_cap_usd=max(0.0, float(openrouter_absolute_cap_usd)),
        magic_hour_absolute_cap_credits=max(0, int(magic_hour_absolute_cap_credits)),
        limit_fraction=FIDELITY_BUDGET_FRACTION,
    )


_OPENROUTER_PRICING_CACHE: dict[str, dict[str, float]] = {}


def _openrouter_pricing(model: str) -> dict[str, float]:
    cached = _OPENROUTER_PRICING_CACHE.get(model)
    if cached:
        return cached
    response = requests.get(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}, timeout=30,
    )
    response.raise_for_status()
    item = next((entry for entry in response.json().get("data", []) if entry.get("id") == model), None)
    if not item:
        raise RuntimeError(f"OpenRouter pricing is unavailable for {model}")
    raw = item.get("pricing") or {}
    prompt_rates = [float(raw.get("prompt") or 0)]
    completion_rates = [float(raw.get("completion") or 0)]
    for override in raw.get("overrides") or []:
        prompt_rates.append(float(override.get("prompt") or 0))
        completion_rates.append(float(override.get("completion") or 0))
    pricing = {
        "prompt": max(prompt_rates),
        "completion": max(completion_rates),
        "request": float(raw.get("request") or 0),
        "image": float(raw.get("image") or 0),
    }
    if pricing["prompt"] <= 0 or pricing["completion"] <= 0:
        raise RuntimeError(f"OpenRouter returned incomplete pricing for {model}")
    _OPENROUTER_PRICING_CACHE[model] = pricing
    return pricing


class OpenRouterBudgetGuard:
    def __init__(self, run: FidelityRun, *, adaptive: bool = False):
        if not run.budget:
            raise ValueError("fidelity run has no budget snapshot")
        self.run = run
        self.adaptive = adaptive
        self.pending_estimate = 0.0

    def __call__(self, event: dict[str, Any]) -> dict[str, Any] | None:
        assert self.run.budget is not None
        if event["phase"] == "before":
            # The response usage contains the exact charge. Until then use a
            # conservative configurable ceiling so the preflight fails closed.
            remaining = self.run.budget.remaining_openrouter_cap()
            static_estimate = max(0.01, OPENROUTER_FIDELITY_MAX_REQUEST_USD)
            if not self.adaptive or remaining >= static_estimate:
                self.pending_estimate = static_estimate
                self.run.budget.assert_openrouter_estimate(self.pending_estimate)
                return None
            pricing = _openrouter_pricing(str(event["model"]))
            # UTF-8 bytes are a safe upper bound for ordinary text token count.
            # Image inputs receive a separate deliberately conservative reserve.
            input_tokens_upper = int(event.get("input_bytes") or event.get("input_characters") or 0) + 2048
            image_count = int(event.get("input_images") or 0)
            image_reserve = image_count * max(20_000 * pricing["prompt"], pricing["image"])
            input_reserve = input_tokens_upper * pricing["prompt"] + pricing["request"]
            fixed_reserve = input_reserve + image_reserve + 0.02
            available_completion = remaining - fixed_reserve
            max_tokens = min(
                int(event.get("max_tokens") or 16000),
                math.floor(available_completion / pricing["completion"]),
            )
            if max_tokens < 512:
                raise BudgetLimitExceeded(
                    f"next OpenRouter request cannot fit safely inside the remaining cap: "
                    f"remaining=${remaining:.4f}, fixed_reserve=${fixed_reserve:.4f}"
                )
            self.pending_estimate = fixed_reserve + max_tokens * pricing["completion"]
            self.run.budget.assert_openrouter_estimate(self.pending_estimate)
            return {
                "max_tokens": max_tokens,
                "provider": {
                    "sort": "price",
                    "max_price": {
                        "prompt": pricing["prompt"] * 1_000_000,
                        "completion": pricing["completion"] * 1_000_000,
                    },
                },
            }
        self.run.budget.record_openrouter(event.get("usage") or {}, self.pending_estimate)
        self.pending_estimate = 0.0
        if self.run.budget.openrouter_spend_usd >= float(self.run.budget.caps()["openrouter_usd"]):
            self.run.status = "budget_limit"
            self.run.stop_reason = "budget_limit"
            save_fidelity_run(self.run)
            raise BudgetLimitExceeded(
                "actual OpenRouter charge reached or crossed the fidelity cap; stopping before another call"
            )
        save_fidelity_run(self.run)
        return None


def _repair_visual_dimension(
    project: EpisodeProject, dimension: str, *, attempt: int = 0,
) -> EpisodeProject:
    repaired = project.model_copy(deep=True)
    overrides = repaired.editorial_plan.setdefault("fidelity_visual_overrides", {})
    if dimension == "typography":
        overrides["typography_profile"] = "large_editorial"
        overrides["typography_contract"] = {
            "dominant_statement_max_words": 7,
            "minimum_primary_type_px": 64,
            "source_ui_treatment": "crop_to_one_readable_region",
            "supporting_labels_max": 1,
            "label_policy": "source citation only; never label b-roll, AI, or visual type",
            "disclaimer_policy": "one concise disclaimer at the first relevant claim only",
        }
        overrides["typography_scene_audit"] = [
            {"shot_id": shot.id, "role": "one dominant statement", "supporting_labels_max": 1}
            for shot in repaired.shots
            if shot.asset_type in {"motion_graphic", "chapter_card", "chart"}
        ]
        for shot in repaired.shots:
            shot.prompt = re.sub(
                r"(?i)\s*(?:clearly\s+)?labeled\s+['\"]?illustrative[^.]*\.?",
                "",
                shot.prompt or "",
            ).strip()
            shot.prompt = re.sub(
                r"(?i)\s*label(?:ed)?\s+as\s+['\"]?illustrative[^.]*\.?",
                "",
                shot.prompt or "",
            ).strip()
            if shot.asset_type in {"screenshot", "screen_recording", "official_demo"}:
                shot.prompt = (
                    shot.prompt.rstrip(" .")
                    + ". Full-screen centered evidence; one quiet source credit only."
                )
    elif dimension == "motion_style":
        for shot in repaired.shots:
            shot.motion_style = "locked"
            shot.transition = "cut"
            shot.easing = "ease_out"
        source_indices = [
            index for index, shot in enumerate(repaired.shots)
            if shot.asset_type in {"screenshot", "screen_recording", "official_demo"}
        ]
        for index in source_indices[::15]:
            repaired.shots[index].motion_style = "push_in"
        first_shot_by_beat: dict[str, Shot] = {}
        for shot in repaired.shots:
            first_shot_by_beat.setdefault(shot.beat_id, shot)
        chapter_beats = {
            beat.id for beat in (repaired.script.beats if repaired.script else [])
            if beat.purpose in {"hook", "model_test", "comparison", "limitation", "verdict"}
        }
        for beat_id in chapter_beats:
            if beat_id in first_shot_by_beat:
                first_shot_by_beat[beat_id].transition = "dissolve"
        overrides["camera_contract"] = "locked_camera_with_internal_object_state_changes"
        overrides["camera_variation_contract"] = (
            "one short purposeful reframe per chapter; dissolve only on chapter cards"
        )
        overrides["purposeful_reframe_shot_ids"] = [
            repaired.shots[index].id for index in source_indices[::15]
        ]
        overrides["chapter_dissolve_shot_ids"] = [
            first_shot_by_beat[beat_id].id for beat_id in sorted(chapter_beats)
            if beat_id in first_shot_by_beat
        ]
    elif dimension == "color_palette":
        overrides["palette_profile"] = "neutral_product_accent"
        overrides["palette_contract"] = {
            "base": ["#F0F2F0", "#C8CEC9", "#4A4F4B", "#121513"],
            "accent_rule": "one official product-native accent per scene",
            "forbidden": ["broad yellow", "generic purple glow", "rainbow gradient"],
        }
    elif dimension == "chart_data_viz":
        if repaired.script:
            numeric = _quantitative_beat_ids(repaired.script)
            for shot in repaired.shots:
                if shot.asset_type == "chart" and shot.beat_id not in numeric:
                    shot.asset_type = "motion_graphic"
                    shot.motion_template = "step_flow"
            for beat_id in numeric:
                candidates = [shot for shot in repaired.shots if shot.beat_id == beat_id]
                has_source_evidence = any(
                    shot.asset_type in {"screenshot", "screen_recording", "official_demo"}
                    and bool(shot.source_id)
                    for shot in candidates
                )
                if candidates and not has_source_evidence and not any(shot.asset_type == "chart" for shot in candidates):
                    candidates[-1].asset_type = "chart"
                    candidates[-1].motion_template = "stat_reveal"
                    candidates[-1].source_id = None
                    candidates[-1].asset_path = ""
        overrides["chart_contract"] = {
            "direct_labels": True,
            "visible_source": True,
            "simultaneous_series_max": 3,
            "reveal_order": ["claim", "measure", "comparison", "source"],
            "chart_only_when_quantitative": True,
            "non_numeric_explanations_use": "labeled diagram, never faux chart",
        }
        overrides["quantitative_chart_shot_ids"] = [
            shot.id for shot in repaired.shots if shot.asset_type == "chart"
        ]
    elif dimension == "information_density":
        overrides["max_information_items"] = 3
        overrides["density_contract"] = {
            "dominant_proof_objects": 1,
            "supporting_items_max": 2,
            "full_bleed_evidence_crop": True,
            "two_column_summary_cards": False,
            "layout": "single-column proof hierarchy",
        }
        overrides["single_proof_object_shot_ids"] = [shot.id for shot in repaired.shots]
        for shot in repaired.shots:
            shot.prompt = re.sub(
                r"(?i)two[- ]column(?:\s+card)?",
                "sequential single-proof frames",
                shot.prompt or "",
            )
    elif dimension == "visual_reveal_pacing":
        overrides["meaningful_state_change_seconds"] = 2.5
        overrides["reveal_contract"] = {
            "source_shot_states": ["clean_crop", "evidence_emphasis", "source_settle"],
            "motion_graphic_states": ["claim", "mechanism", "consequence"],
            "ambient_drift_forbidden": True,
        }
        cadence_ratios = (0.36, 0.43, 0.51, 0.39, 0.47, 0.54)
        overrides["intra_shot_keyframes"] = []
        for index, shot in enumerate(repaired.shots):
            middle = min(2.9, shot.duration_seconds * cadence_ratios[index % len(cadence_ratios)])
            overrides["intra_shot_keyframes"].append({
                "shot_id": shot.id,
                "seconds": [0, round(middle, 3), round(shot.duration_seconds, 3)],
                "editorial_reason": ("proof emphasis" if index % 3 == 0 else "mechanism reveal" if index % 3 == 1 else "consequence landing"),
            })
        for shot in repaired.shots:
            if shot.asset_type in {"screenshot", "screen_recording", "official_demo"}:
                shot.motion_template = "evidence_focus"
            elif shot.asset_type == "chart":
                shot.motion_template = "stat_reveal"
            elif shot.asset_type in {"motion_graphic", "concept_animation"}:
                shot.motion_template = "step_flow"
    else:
        raise ValueError(f"unsupported visual fidelity dimension: {dimension}")
    return repaired


def _punctuation_only_rhythm_repair(script: Script, attempt: int = 0) -> Script:
    """Vary sentence boundaries without changing the script's factual tokens."""
    repaired = script.model_copy(deep=True)
    max_splits = min(3, max(1, attempt + 1))
    for beat_index, beat in enumerate(repaired.beats):
        if beat_index == 0:
            continue  # Freeze the already-passing hook.
        sentences = [
            item.strip() for item in re.split(r"(?<=[.!?])\s+", beat.narration)
            if item.strip()
        ]
        output: list[str] = []
        split_count = 0
        for sentence in sentences:
            words = sentence.split()
            if len(words) < 18 or split_count >= max_splits:
                output.append(sentence)
                continue
            candidates: list[tuple[float, re.Match[str]]] = []
            for match in re.finditer(r"[,;]\s+(?=(?:and|but|so|yet|while|because|which|that)\b)|[,;]\s+", sentence, re.I):
                left_count = len(sentence[:match.start()].split())
                right_count = len(sentence[match.end():].split())
                if 5 <= left_count <= 14 and right_count >= 6:
                    candidates.append((abs(left_count - 8), match))
            if not candidates:
                output.append(sentence)
                continue
            match = min(candidates, key=lambda item: (item[0], item[1].start()))[1]
            left = sentence[:match.start()].rstrip(" ,;")
            right = sentence[match.end():].lstrip()
            if right:
                right = right[0].upper() + right[1:]
            output.extend([left + ".", right])
            split_count += 1
        beat.narration = " ".join(output)
    return Script.model_validate(repaired.model_dump())


def _fact_locked_script_equivalent(before: Script, after: Script) -> bool:
    """Prove a cadence edit retained every factual token and evidence mapping."""
    if len(before.beats) != len(after.beats):
        return False
    for left, right in zip(before.beats, after.beats):
        if (
            left.id != right.id
            or left.purpose != right.purpose
            or left.claim_ids != right.claim_ids
            or left.source_ids != right.source_ids
        ):
            return False
        left_tokens = re.findall(r"[a-z0-9]+", left.narration.casefold())
        right_tokens = re.findall(r"[a-z0-9]+", right.narration.casefold())
        if left_tokens != right_tokens:
            return False
    return True


def _punctuation_only_question_repair(script: Script) -> Script:
    """Move question frequency toward the observed band without adding claims."""
    repaired = script.model_copy(deep=True)
    question_count = sum(beat.narration.count("?") for beat in repaired.beats)
    if question_count > 2:
        # Remove meta/reminder questions first; they do not open information
        # gaps and are the exact kind of signposting the reference band avoids.
        transformations = (
            (r"\bRemember ([^.!?]+)\?", r"Remember \1."),
            (r"\b([^.!?]+?) answers,\s*what happens next\?", r"\1 answers what happens next."),
            (
                r"\bWhy does ([^.!?]+?) matter\?",
                lambda match: match.group(1)[:1].upper() + match.group(1)[1:] + " matters here.",
            ),
        )
        for pattern, replacement in transformations:
            for beat in repaired.beats:
                if question_count <= 2:
                    break
                updated, count = re.subn(pattern, replacement, beat.narration, count=1, flags=re.I)
                if count:
                    beat.narration = updated
                    question_count -= 1
        return Script.model_validate(repaired.model_dump())

    # If the script is below band, promote one already-explicit information
    # gap. This changes delivery punctuation only and never adds a new claim.
    patterns = (
        r"(The real question is[^.!?]+)\.",
        r"(The practical question is[^.!?]+)\.",
        r"(Which raises the question[^.!?]+)\.",
    )
    for beat in repaired.beats:
        for pattern in patterns:
            updated, count = re.subn(pattern, r"\1?", beat.narration, count=1, flags=re.I)
            if count:
                beat.narration = updated
                return Script.model_validate(repaired.model_dump())
    return Script.model_validate(repaired.model_dump())


def _evidence_copied_callback_repair(script: Script) -> Script:
    """Repeat one supported concrete example in a compatible late verdict beat."""
    repaired = script.model_copy(deep=True)
    targets = [
        beat for beat in reversed(repaired.beats)
        if beat.purpose in {"verdict", "outro", "analysis"} and beat.claim_ids
    ]
    sources = [
        beat for beat in repaired.beats
        if beat.purpose in {"model_test", "evidence", "observation"} and beat.claim_ids
    ]
    for target in targets:
        target_claims = set(target.claim_ids)
        for source in sources:
            if source.id == target.id or not set(source.claim_ids).issubset(target_claims):
                continue
            sentences = [
                item.strip() for item in re.split(r"(?<=[.!?])\s+", source.narration)
                if item.strip()
            ]
            compact: list[str] = []
            word_total = 0
            for sentence in sentences:
                count = len(sentence.split())
                if count <= 12 and word_total + count <= 22:
                    compact.append(sentence)
                    word_total += count
                if len(compact) == 2:
                    break
            if not compact:
                continue
            excerpt = " ".join(compact)
            target.narration = (
                target.narration.rstrip()
                + " Remember that earlier example: "
                + excerpt[0].lower() + excerpt[1:]
            )
            return Script.model_validate(repaired.model_dump())
    return Script.model_validate(repaired.model_dump())


def _evidence_copied_callback_safe(before: Script, after: Script) -> bool:
    changed = [
        (left, right) for left, right in zip(before.beats, after.beats)
        if left.narration != right.narration
    ]
    if len(before.beats) != len(after.beats) or len(changed) != 1:
        return False
    target_before, target_after = changed[0]
    for left, right in zip(before.beats, after.beats):
        if (
            left.id != right.id or left.purpose != right.purpose
            or left.claim_ids != right.claim_ids or left.source_ids != right.source_ids
        ):
            return False
    marker = " Remember that earlier example: "
    prefix = target_before.narration.rstrip() + marker
    if not target_after.narration.startswith(prefix):
        return False
    inserted_tokens = re.findall(r"[a-z0-9]+", target_after.narration[len(prefix):].casefold())
    if not inserted_tokens:
        return False
    target_claims = set(target_before.claim_ids)
    for source in before.beats:
        if not source.claim_ids or not set(source.claim_ids).issubset(target_claims):
            continue
        source_tokens = re.findall(r"[a-z0-9]+", source.narration.casefold())
        width = len(inserted_tokens)
        if any(source_tokens[index:index + width] == inserted_tokens for index in range(len(source_tokens) - width + 1)):
            return True
    return False


def _repair_script_dimension(
    project: EpisodeProject, dimension: str, feedback: str, *, attempt: int = 0,
) -> Script:
    if not project.script:
        raise ValueError("script is required for a fidelity repair")
    if dimension == "sentence_rhythm":
        return _punctuation_only_rhythm_repair(project.script, attempt)
    if dimension == "question_use":
        return _punctuation_only_question_repair(project.script)
    if dimension == "callbacks":
        return _evidence_copied_callback_repair(project.script)
    beat_schema = {
        "type": "object", "additionalProperties": False,
        "required": ["id", "narration", "delivery"],
        "properties": {
            "id": {"type": "string"}, "narration": {"type": "string"},
            "delivery": {
                "type": "object", "additionalProperties": False,
                "required": ["pace", "energy", "pause_before_ms", "pause_after_ms", "emphasis_words"],
                "properties": {
                    "pace": {"type": "string", "enum": ["slow", "normal", "quick"]},
                    "energy": {"type": "string", "enum": ["restrained", "normal", "emphatic"]},
                    "pause_before_ms": {"type": "integer", "minimum": 0, "maximum": 2500},
                    "pause_after_ms": {"type": "integer", "minimum": 0, "maximum": 2500},
                    "emphasis_words": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                },
            },
        },
    }
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "TargetedScriptRepair", "strict": True,
            "schema": {
                "type": "object", "additionalProperties": False, "required": ["beats"],
                "properties": {"beats": {"type": "array", "items": beat_schema}},
            },
        },
    }
    raw = editorial.call_openrouter(
        OPENROUTER_MODEL,
        "You are a fact-locked spoken-word editor. Change only the requested fidelity dimension. Never imitate wording or persona.",
        f"Repair only {dimension}. Preserve every beat ID, order, purpose, claim/source mapping, fact, qualification, and title field. "
        "Do not add a proper noun, number, capability, causal statement, personal test, or stronger claim. "
        "Return every beat, but leave narration unchanged where a change is not necessary for the requested dimension. "
        f"This is targeted attempt {attempt + 1}. Reviewer note: {feedback}\n\nSCRIPT:\n{project.script.model_dump_json()}",
        schema, temperature=0.35,
    )
    expected = [beat.id for beat in project.script.beats]
    if [item.get("id") for item in raw.get("beats", [])] != expected:
        raise RuntimeError("targeted script repair changed beat IDs or order")
    repaired = project.script.model_copy(deep=True)
    by_id = {item["id"]: item for item in raw["beats"]}
    for beat in repaired.beats:
        beat.narration = by_id[beat.id]["narration"]
        beat.delivery = type(beat.delivery).model_validate(by_id[beat.id]["delivery"])
    return Script.model_validate(repaired.model_dump())


def _accept_targeted_repair(
    before: FidelityScorecard, after: FidelityScorecard, target: str,
) -> tuple[bool, str]:
    if after.final.get(target, 0) <= before.final.get(target, 0):
        return False, "target dimension did not improve"
    regressions = [name for name, score in before.final.items() if name != target and after.final.get(name, 0) < score]
    if regressions:
        return False, "non-target dimensions regressed: " + ", ".join(regressions)
    return True, "target improved without non-target regression"


def _restore_rejected_project(before: EpisodeProject, attempted: EpisodeProject) -> EpisodeProject:
    """Restore creative state while retaining irreversible cost/provenance records."""
    restored = before.model_copy(deep=True)
    restored.costs = attempted.costs.copy()
    known_media = {item.id for item in restored.media}
    for item in attempted.media:
        if item.id not in known_media:
            retained = item.model_copy(deep=True)
            retained.qc_notes.append("Retained for spend provenance after rejected fidelity repair.")
            restored.media.append(retained)
    return restored


def _usage_snapshot(run: FidelityRun) -> dict[str, int | float]:
    return run.budget.model_dump() if run.budget else {}


def _create_or_select_pilot(run: FidelityRun) -> EpisodeProject:
    from .production import create_weekly_slate, refresh_sources
    refresh_sources()
    slate = create_weekly_slate()
    episode_ids = [item["episode_id"] for item in slate["episodes"]]
    projects = [load_project(EPISODE_DATA_DIR / episode_id) for episode_id in episode_ids]
    project = next((item for item in projects if item.brief and item.brief.episode_format == run.pilot_format), None)
    project = project or next((item for item in projects if item.brief and item.brief.episode_format == "deep_dive"), projects[0])
    assert project.brief is not None
    project.brief.approved = True
    project.review.slate_status = "approved"
    project.status = "approved_for_private_fidelity_draft"
    project.episode["publishing_enabled"] = False
    project.episode["approval_mode"] = "private_fidelity_loop"
    project.episode["fidelity_run_id"] = run.run_id
    save_project(project, EPISODE_DATA_DIR / project.episode_id)
    run.pilot_episode_id = project.episode_id
    save_fidelity_run(run)
    return project


def build_fidelity_reference_profile(
    payload: dict[str, Any], *, should_cancel: Callable[[], bool] | None = None,
    report_progress: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Build the real public reference corpus/profile without a paid provider call.

    This deliberately does not snapshot or invent provider balances. The paid
    fidelity loop still performs its own fail-closed budget preflight.
    """
    run_id = str(payload.get("run_id") or f"fidelity_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}")
    run = load_fidelity_run(run_id) if fidelity_run_path(run_id).is_file() else FidelityRun(run_id=run_id)
    run.status = "building_corpus"
    run.stop_reason = ""
    save_fidelity_run(run)
    try:
        corpus = (
            json.loads(Path(run.corpus_path).read_text(encoding="utf-8"))
            if run.corpus_path and Path(run.corpus_path).is_file()
            else build_reference_corpus(
                run, count=int(payload.get("corpus_size") or FIDELITY_CORPUS_SIZE),
                should_cancel=should_cancel, report_progress=report_progress,
            )
        )
        frame_strips_added = refresh_reference_frame_strips(
            run, corpus, per_channel=int(payload.get("frame_strips_per_channel") or 6),
            should_cancel=should_cancel,
        )
        profile = (
            json.loads(Path(run.pattern_library_path).read_text(encoding="utf-8"))
            if not frame_strips_added and run.pattern_library_path and Path(run.pattern_library_path).is_file()
            else build_pattern_library(run, corpus)
        )
        run.status = "pattern_library_finalized"
        run.stop_reason = "awaiting_paid_budget_preflight"
        run.artifacts["pattern_library"] = str(run.pattern_library_path)
        run.pattern_library_sha256 = run.pattern_library_sha256 or _canonical_sha256(profile)
        save_fidelity_run(run)
        if report_progress:
            report_progress(100)
        return fidelity_status(run)
    except InterruptedError:
        run.status = "canceled"
        run.stop_reason = "canceled"
        save_fidelity_run(run)
        raise
    except Exception as exc:
        run.status = "blocked"
        run.stop_reason = "reference_profile_gate"
        run.errors.append(f"{type(exc).__name__}: {exc}")
        save_fidelity_run(run)
        return fidelity_status(run)


def _produce_integrated_round(
    run: FidelityRun, project: EpisodeProject, guard: OpenRouterBudgetGuard, *,
    should_cancel: Callable[[], bool] | None = None,
    report_progress: Callable[[int], None] | None = None,
) -> EpisodeProject:
    from .production import produce_episode

    assert run.budget is not None
    # A private draft approval is a production-routing signal, not permission to
    # waive factual or spoken-quality review. Re-check the frozen script before
    # narration so a stale/failed verifier record can never be converted into a
    # pass merely by entering the render path.
    script_hash = canonical_hash(project.script.model_dump(mode="json"))
    cached_fact_check = project.qc.get("fact_check") or {}
    cached_quality = cached_fact_check.get("quality_review") or {}
    if not (
        cached_fact_check.get("passed") is True
        and cached_quality.get("passed") is True
        and cached_fact_check.get("script_hash") == script_hash
    ):
        with editorial.capture_openrouter_usage(guard):
            fact_check = editorial.verify_script(project)
            quality_review = editorial.review_script_quality(project)
        project.qc["fact_check"] = {
            **fact_check,
            "quality_review": quality_review,
            "passed": bool(fact_check.get("passed") and quality_review.get("passed")),
            "script_hash": script_hash,
        }
    if not project.qc["fact_check"]["passed"]:
        project.status = "script_revision_required"
        save_project(project, EPISODE_DATA_DIR / project.episode_id)
        raise RuntimeError("fidelity script failed factual or spoken-quality verification before render")
    project.qc["script_manual_approval"] = {
        "approved": True,
        "script_hash": script_hash,
        "scope": "private fidelity run; publishing remains disabled",
    }
    project.episode["publishing_enabled"] = False
    project.episode["credit_limit"] = (
        int(project.costs.get("magic_hour_credits", 0))
        + run.budget.remaining_magic_hour_cap()
    )
    starting_project_credits = int(project.costs.get("magic_hour_credits", 0))
    run.artifacts.setdefault("pilot_magic_hour_start_credits", str(starting_project_credits))
    save_project(project, EPISODE_DATA_DIR / project.episode_id)
    try:
        with editorial.capture_openrouter_usage(guard):
            produce_episode(
                project.episode_id,
                should_cancel=should_cancel,
                report_progress=(
                    (lambda value: report_progress(80 + round(float(value) * 0.19)))
                    if report_progress else None
                ),
            )
    finally:
        current = load_project(EPISODE_DATA_DIR / project.episode_id)
        total_since_run_start = max(
            0,
            int(current.costs.get("magic_hour_credits", 0))
            - int(run.artifacts.get("pilot_magic_hour_start_credits", "0") or 0),
        )
        already_recorded = int(run.artifacts.get("pilot_magic_hour_recorded_credits", "0") or 0)
        if total_since_run_start > already_recorded:
            run.budget.record_magic_hour(total_since_run_start - already_recorded)
            run.artifacts["pilot_magic_hour_recorded_credits"] = str(total_since_run_start)
            save_fidelity_run(run)
    return load_project(EPISODE_DATA_DIR / project.episode_id)


def run_fidelity_loop(
    payload: dict[str, Any], *, should_cancel: Callable[[], bool] | None = None,
    report_progress: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Run or resume the fidelity state machine until pass, budget stop, or a real gate blocks."""
    run_id = str(payload.get("run_id") or f"fidelity_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}")
    run = load_fidelity_run(run_id) if fidelity_run_path(run_id).is_file() else FidelityRun(run_id=run_id)
    run.pilot_format = str(payload.get("pilot_format") or run.pilot_format)
    adaptive_budget = bool(payload.get("adaptive_budget", False))
    requested_openrouter_cap = float(payload.get("openrouter_max_spend_usd") or 0)
    requested_magic_hour_cap = int(payload.get("magic_hour_max_credits") or 0)
    if run.budget:
        # A resumed run may receive an explicitly authorized higher absolute cap.
        # Caps are monotonic: a payload can raise them, never silently lower them.
        if requested_openrouter_cap > run.budget.openrouter_absolute_cap_usd:
            previous = run.budget.openrouter_absolute_cap_usd
            run.budget.openrouter_absolute_cap_usd = requested_openrouter_cap
            run.artifacts["openrouter_cap_authorization"] = (
                f"raised_from_usd_{previous:.6f}_to_usd_{requested_openrouter_cap:.6f}"
            )
        if requested_magic_hour_cap > run.budget.magic_hour_absolute_cap_credits:
            previous = run.budget.magic_hour_absolute_cap_credits
            run.budget.magic_hour_absolute_cap_credits = requested_magic_hour_cap
            run.artifacts["magic_hour_cap_authorization"] = (
                f"raised_from_credits_{previous}_to_credits_{requested_magic_hour_cap}"
            )
        save_fidelity_run(run)
    if run.status in {"budget_limit", "predictive_budget_hold"}:
        actual_cap_reached = bool(
            run.budget and run.budget.openrouter_spend_usd >= float(run.budget.caps()["openrouter_usd"])
        )
        if actual_cap_reached or not adaptive_budget:
            return fidelity_status(run)
        run.status = "resuming_from_predictive_budget_hold"
        run.stop_reason = ""
        save_fidelity_run(run)
    completed_video = Path(str(run.artifacts.get("episode_video") or ""))
    if (
        run.status == "perfect_fidelity" and run.stop_reason == "perfect_fidelity"
        and completed_video.is_file() and completed_video.stat().st_size > 0
    ):
        return fidelity_status(run)
    if run.status == "perfect_fidelity":
        run.status = "resume_missing_artifact"
        run.stop_reason = ""
    save_fidelity_run(run)
    try:
        # Fail before network-heavy corpus refresh or any paid generation. This
        # makes a missing credential/balance a clean, resumable preflight state.
        if not run.budget:
            run.status = "budget_preflight"
            save_fidelity_run(run)
            run.budget = _budget_snapshot(
                float(payload.get("openrouter_starting_balance_usd") or 0),
                int(payload.get("magic_hour_starting_balance_credits") or 0),
                openrouter_absolute_cap_usd=requested_openrouter_cap,
                magic_hour_absolute_cap_credits=requested_magic_hour_cap,
            )
            save_fidelity_run(run)
        corpus = (
            json.loads(Path(run.corpus_path).read_text(encoding="utf-8"))
            if run.corpus_path and Path(run.corpus_path).is_file()
            else build_reference_corpus(run, count=int(payload.get("corpus_size") or FIDELITY_CORPUS_SIZE), should_cancel=should_cancel, report_progress=report_progress)
        )
        profile = (
            json.loads(Path(run.pattern_library_path).read_text(encoding="utf-8"))
            if run.pattern_library_path and Path(run.pattern_library_path).is_file()
            else build_pattern_library(run, corpus)
        )
        if report_progress:
            report_progress(35)
        guard = OpenRouterBudgetGuard(run, adaptive=adaptive_budget)
        with editorial.capture_openrouter_usage(guard):
            project = (
                load_project(EPISODE_DATA_DIR / str(payload["episode_id"]))
                if payload.get("episode_id") else
                load_project(EPISODE_DATA_DIR / run.pilot_episode_id) if run.pilot_episode_id else
                _create_or_select_pilot(run)
            )
            run.pilot_episode_id = project.episode_id
            project.episode["publishing_enabled"] = False
            project.episode["fidelity_run_id"] = run.run_id
            save_project(project, EPISODE_DATA_DIR / project.episode_id)
            save_fidelity_run(run)
            if should_cancel and should_cancel():
                raise InterruptedError("fidelity loop canceled")
            if not project.claims:
                project.claims = editorial.extract_claims(project.brief, project.sources)
                project.brief.claim_ids = [claim.id for claim in project.claims]
            if not project.script:
                project.script, verification, revisions = editorial.write_verified_script(project)
                project.qc["fact_check"] = {**verification, "automatic_revisions": revisions}
                save_project(project, EPISODE_DATA_DIR / project.episode_id)
            no_progress = 0
            while True:
                cached_card = run.scorecards.get("script")
                cached_matches = bool(
                    cached_card and cached_card.artifact_sha256
                    == canonical_hash(project.script.model_dump(mode="json"))
                )
                card = cached_card if cached_matches else score_script(project.script, profile)
                run.scorecards["script"] = card
                save_fidelity_run(run)
                record_milestone(
                    run, "first_fully_scored_script",
                    str(EPISODE_DATA_DIR / project.episode_id / "episode_project.json"), card.final,
                )
                if card.passed:
                    break
                target = choose_lowest_dimension(card.final, card.distance_from_reference)
                before_script = project.script.model_copy(deep=True)
                repaired = _repair_script_dimension(
                    project, target, card.notes.get(target, ""), attempt=no_progress,
                )
                project.script = repaired
                fact_check = (
                    {"passed": True, "verification": "fact_locked_token_and_evidence_equivalence"}
                    if (
                        target in {"sentence_rhythm", "question_use"}
                        and _fact_locked_script_equivalent(before_script, project.script)
                    ) or (
                        target == "callbacks"
                        and _evidence_copied_callback_safe(before_script, project.script)
                    )
                    else editorial.verify_script(project)
                )
                if not fact_check["passed"]:
                    project.script = before_script
                    no_progress += 1
                    accepted, reason = False, "targeted repair failed factual verification"
                    after_card = card
                else:
                    after_card = score_script(project.script, profile)
                    accepted, reason = _accept_targeted_repair(card, after_card, target)
                    if not accepted:
                        project.script = before_script
                        no_progress += 1
                    else:
                        no_progress = 0
                        run.scorecards["script"] = after_card
                        save_project(project, EPISODE_DATA_DIR / project.episode_id)
                run.iterations.append(FidelityIteration(
                    index=len(run.iterations) + 1, stage="script", target_dimension=target,
                    before_scores=card.final, after_scores=after_card.final,
                    before_sha256=card.artifact_sha256, after_sha256=after_card.artifact_sha256,
                    accepted=accepted, reason=reason, usage_after=_usage_snapshot(run),
                ))
                save_fidelity_run(run)
            duration_seconds = max(480.0, min(720.0, project.script.word_count / 2.5))
            if not project.shots:
                project.shots = storyboard.build_shot_plan(project, duration_seconds)
            project.editorial_plan.setdefault("fidelity_visual_overrides", {
                "typography_profile": "large_editorial", "palette_profile": "neutral_product_accent",
                "max_information_items": 3, "meaningful_state_change_seconds": 2.5,
            })
            save_project(project, EPISODE_DATA_DIR / project.episode_id)
            no_progress = 0
            while True:
                storyboard_payload = {
                    "shots": [shot.model_dump(mode="json") for shot in project.shots],
                    "visual_overrides": project.editorial_plan.get("fidelity_visual_overrides") or {},
                }
                cached_card = run.scorecards.get("storyboard")
                cached_matches = bool(
                    cached_card and cached_card.artifact_sha256 == canonical_hash(storyboard_payload)
                )
                card = cached_card if cached_matches else score_storyboard(project, profile)
                run.scorecards["storyboard"] = card
                save_fidelity_run(run)
                record_milestone(
                    run, "first_fully_scored_storyboard",
                    str(EPISODE_DATA_DIR / project.episode_id / "episode_project.json"), card.final,
                )
                if card.passed:
                    break
                target = choose_lowest_dimension(card.final, card.distance_from_reference)
                before_project = project.model_copy(deep=True)
                repaired_project = _repair_visual_dimension(project, target, attempt=no_progress)
                after_card = score_storyboard_targeted(
                    repaired_project, profile, card, target,
                )
                accepted, reason = _accept_targeted_repair(card, after_card, target)
                if accepted:
                    project = repaired_project
                    run.scorecards["storyboard"] = after_card
                    save_project(project, EPISODE_DATA_DIR / project.episode_id)
                    no_progress = 0
                else:
                    project = before_project
                    # A rejected repair must be rolled back on disk as well as
                    # in memory; otherwise an interrupted process resumes from
                    # the failed candidate while its scorecard describes the
                    # accepted storyboard.
                    save_project(project, EPISODE_DATA_DIR / project.episode_id)
                    no_progress += 1
                run.iterations.append(FidelityIteration(
                    index=len(run.iterations) + 1, stage="storyboard", target_dimension=target,
                    before_scores=card.final, after_scores=after_card.final,
                    before_sha256=card.artifact_sha256, after_sha256=after_card.artifact_sha256,
                    accepted=accepted, reason=reason, usage_after=_usage_snapshot(run),
                ))
                save_fidelity_run(run)
        run.status = "storyboard_verified"
        run.stop_reason = "awaiting_integrated_episode_render"
        save_fidelity_run(run)
        if report_progress:
            report_progress(80)
        if not bool(payload.get("render_episode", True)):
            return fidelity_status(run)

        assert run.budget is not None
        project = load_project(EPISODE_DATA_DIR / run.pilot_episode_id)
        project = _produce_integrated_round(
            run, project, guard, should_cancel=should_cancel, report_progress=report_progress,
        )
        no_progress = 0
        with editorial.capture_openrouter_usage(guard):
            integrated = score_integrated(project, profile, run)
        while True:
            run.scorecards["integrated"] = integrated
            if project.artifacts.get("video"):
                run.artifacts["episode_video"] = project.artifacts["video"]
            final_qc = project.qc.get("final") or {}
            verification = integrated_verification_gates(project, profile, run)
            project.qc["fidelity_verification"] = verification
            save_project(project, EPISODE_DATA_DIR / project.episode_id)
            save_fidelity_run(run)
            if integrated.passed and bool(verification.get("passed")):
                run.status = "perfect_fidelity"
                run.stop_reason = "perfect_fidelity"
                record_milestone(
                    run, "first_episode_clearing_verification",
                    project.artifacts.get("video", str(EPISODE_DATA_DIR / project.episode_id)),
                    integrated.final,
                )
                return fidelity_status(run)
            if not final_qc.get("passed"):
                raise RuntimeError("integrated render failed final production QC")
            if integrated.passed and not verification.get("passed"):
                raise RuntimeError(
                    "integrated episode failed non-fidelity verification gates: "
                    + ", ".join(verification.get("failed_checks") or [])
                )
            target = choose_lowest_dimension(integrated.final, integrated.distance_from_reference)
            before_project = project.model_copy(deep=True)
            before_card = integrated
            if target in SCRIPT_DIMENSIONS:
                with editorial.capture_openrouter_usage(guard):
                    project.script = _repair_script_dimension(
                        project, target, integrated.notes.get(target, ""), attempt=no_progress,
                    )
                    factual = (
                        {"passed": True, "verification": "fact_locked_token_and_evidence_equivalence"}
                        if before_project.script and project.script and (
                            (
                                target in {"sentence_rhythm", "question_use"}
                                and _fact_locked_script_equivalent(before_project.script, project.script)
                            ) or (
                                target == "callbacks"
                                and _evidence_copied_callback_safe(before_project.script, project.script)
                            )
                        )
                        else editorial.verify_script(project)
                    )
                if not factual.get("passed"):
                    project = before_project
                    after_card = before_card
                    accepted, reason = False, "integrated script repair failed factual verification"
                else:
                    save_project(project, EPISODE_DATA_DIR / project.episode_id)
                    project = _produce_integrated_round(
                        run, project, guard, should_cancel=should_cancel,
                        report_progress=report_progress,
                    )
                    with editorial.capture_openrouter_usage(guard):
                        after_card = score_integrated(project, profile, run)
                    accepted, reason = _accept_targeted_repair(before_card, after_card, target)
            else:
                project = _repair_visual_dimension(project, target, attempt=no_progress)
                save_project(project, EPISODE_DATA_DIR / project.episode_id)
                project = _produce_integrated_round(
                    run, project, guard, should_cancel=should_cancel,
                    report_progress=report_progress,
                )
                with editorial.capture_openrouter_usage(guard):
                    after_card = score_integrated(project, profile, run)
                accepted, reason = _accept_targeted_repair(before_card, after_card, target)
            if accepted:
                no_progress = 0
                integrated = after_card
            else:
                no_progress += 1
                project = _restore_rejected_project(before_project, project)
                integrated = before_card
                save_project(project, EPISODE_DATA_DIR / project.episode_id)
            run.iterations.append(FidelityIteration(
                index=len(run.iterations) + 1, stage="integrated", target_dimension=target,
                before_scores=before_card.final, after_scores=after_card.final,
                before_sha256=before_card.artifact_sha256,
                after_sha256=after_card.artifact_sha256,
                accepted=accepted, reason=reason, usage_after=_usage_snapshot(run),
            ))
            save_fidelity_run(run)
    except BudgetLimitExceeded as exc:
        predictive = "next OpenRouter request" in str(exc)
        run.status = "predictive_budget_hold" if predictive else "budget_limit"
        run.stop_reason = run.status
        run.errors.append(str(exc))
        save_fidelity_run(run)
        return fidelity_status(run)
    except Exception as exc:
        run.status = "blocked"
        run.stop_reason = "preflight_or_quality_gate"
        run.errors.append(f"{type(exc).__name__}: {exc}")
        save_fidelity_run(run)
        return fidelity_status(run)


def fidelity_status(run: FidelityRun) -> dict[str, Any]:
    budget = run.budget
    scores = {name: card.final for name, card in run.scorecards.items()}
    latest = (
        run.scorecards.get("integrated") or run.scorecards.get("storyboard")
        or run.scorecards.get("script")
    )
    gaps = [
        {"dimension": name, "score": score, "points_to_5": 5 - score,
         "review_note": latest.notes.get(name, "") if latest else ""}
        for name, score in (latest.final.items() if latest else []) if score < 5
    ]
    return {
        "run_id": run.run_id, "status": run.status, "stop_reason": run.stop_reason,
        "pilot_episode_id": run.pilot_episode_id, "scores": scores,
        "budget": ({
            **budget.model_dump(),
            "caps": {
                "openrouter_usd": round(float(budget.caps()["openrouter_usd"]), 6),
                "magic_hour_credits": int(budget.caps()["magic_hour_credits"]),
            },
            "cap_mode": {
                "openrouter": "absolute" if budget.openrouter_absolute_cap_usd else "fraction_of_starting_balance",
                "magic_hour": "absolute" if budget.magic_hour_absolute_cap_credits else "fraction_of_starting_balance",
            },
            "fractions": budget.fractions(),
            "consumed_fraction": budget.consumed_fraction(),
        } if budget else None),
        "milestones": run.milestones, "iterations": len(run.iterations),
        "completed_rounds": {
            stage: sum(item.stage == stage for item in run.iterations)
            for stage in ("script", "storyboard", "integrated")
        },
        "artifacts": run.artifacts, "errors": run.errors[-5:],
        "remaining_gaps": gaps,
        "finishing_estimate": {
            "minimum_targeted_repairs": len(gaps),
            "minimum_additional_blind_reviews": len(gaps),
            "integrated_render_required": "first_episode_clearing_verification" not in {
                item.get("name") for item in run.milestones
            },
        },
    }
