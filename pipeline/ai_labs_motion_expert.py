"""Resumable AI LABS motion-grammar and placement expert.

The implementation learns transferable editorial behavior from analysis-only
reference features.  It never exposes held-out observations to catalog or
placement construction and never treats a public reference as reusable media.
"""
from __future__ import annotations

import hashlib
import base64
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

import requests
from PIL import Image, ImageChops, ImageFilter, ImageStat
from pydantic import BaseModel, ConfigDict, Field

from .config import (
    AI_LABS_MOTION_CORPUS_SIZE,
    AI_LABS_MOTION_DATA_DIR,
    AI_LABS_MOTION_PROFILE_PATH,
    AI_LABS_MOTION_REVIEW_MODEL,
    AI_LABS_MOTION_TRAIN_MODEL,
    OPENROUTER_API_KEY,
)
from .fidelity_loop import (
    ReferenceVideo,
    _extract_public_frame_strip,
    _format_label,
    _hydrate,
    _listing_sha256,
    _read_cached_reference,
    _reference_from_metadata,
    _write_cached_reference,
)


AI_LABS_CHANNEL = {
    "title": "AI LABS",
    "handle": "@AILABS-393",
    "channel_id": "UCelfWQr9sXVMTvBzviPGlFw",
    "url": "https://www.youtube.com/@AILABS-393/videos",
}
MOTION_EXPERT_MILESTONES = (
    "pattern_library_complete",
    "placement_model_v1_built",
    "first_generated_test_segment",
    "first_heldout_pass_clearing_threshold",
)
OPENROUTER_CAP_USD = 10.0
HOLDOUT_FRACTION = 0.125
MIN_DURATION_SECONDS = 480


class OpenRouterCredentialError(RuntimeError):
    pass


def _sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_openrouter_credential() -> dict[str, Any]:
    """Validate the configured key without logging or persisting the secret."""
    if not OPENROUTER_API_KEY:
        raise OpenRouterCredentialError("OPENROUTER_API_KEY is missing")
    response = requests.get(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        timeout=30,
    )
    if response.status_code in {401, 403}:
        raise OpenRouterCredentialError(
            "OPENROUTER_API_KEY was rejected by OpenRouter; use a key issued by openrouter.ai"
        )
    response.raise_for_status()
    payload = response.json().get("data") or {}
    return {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "label": str(payload.get("label") or ""),
        "limit_remaining": payload.get("limit_remaining"),
        "usage": payload.get("usage"),
        "is_free_tier": payload.get("is_free_tier"),
    }


class MotionEvidence(BaseModel):
    video_id: str
    url: str
    timecodes: list[float] = Field(default_factory=list)
    observation_hash: str = ""
    analysis_only: bool = True


class MotionVisualSpec(BaseModel):
    typography: dict[str, Any]
    palette: dict[str, Any]
    layout: dict[str, Any]
    motion: dict[str, Any]
    timing: dict[str, Any]
    information_density: dict[str, Any]


class MotionGraphicPattern(BaseModel):
    id: str
    family: str
    variants: list[str]
    narrative_purpose: str
    narrative_triggers: list[str]
    contraindications: list[str]
    visual_spec: MotionVisualSpec
    supporting_evidence: list[MotionEvidence]
    implementation_primitives: list[str]
    originality_warning: str = (
        "Reproduce only transferable information and motion grammar; do not trace a reference frame, "
        "reuse creator artwork, or copy distinctive compositions."
    )
    confidence: float = Field(ge=0, le=1)


class PlacementDecision(BaseModel):
    segment_id: str
    narrative_role: str
    pattern_id: str | None = None
    decision: Literal["graphic", "no_graphic"]
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    trigger: str
    confidence: float = Field(ge=0, le=1)
    evidence_required: bool = False
    reasons: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)


class SegmentAxisScore(BaseModel):
    segment_id: str
    visual_fidelity: float = Field(ge=1, le=5)
    placement_fidelity: float = Field(ge=1, le=5)
    notes: list[str] = Field(default_factory=list)


class HeldoutFidelityReview(BaseModel):
    score_policy: str = "legacy_scoped"
    reviewer_model: str
    independent: bool
    blind_packet_hash: str
    segment_scores: list[SegmentAxisScore]
    hard_failures: list[str] = Field(default_factory=list)
    mean_score: float = Field(ge=1, le=5)
    minimum_score: float = Field(ge=1, le=5)
    passed: bool
    deterministic: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)


class MotionExpertBudget(BaseModel):
    cap_usd: float = OPENROUTER_CAP_USD
    spent_usd: float = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    requests: int = 0

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.cap_usd - self.spent_usd)

    def reserve(self, estimated_max_usd: float) -> None:
        if estimated_max_usd > self.remaining_usd + 1e-9:
            raise RuntimeError(
                f"OpenRouter budget stop: estimate=${estimated_max_usd:.4f}, "
                f"remaining=${self.remaining_usd:.4f}, cap=${self.cap_usd:.2f}"
            )

    def reconcile(self, usage: dict[str, Any], fallback_cost: float) -> None:
        cost = usage.get("cost", usage.get("total_cost", fallback_cost))
        self.spent_usd += max(0.0, float(cost or 0))
        self.prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        self.completion_tokens += int(usage.get("completion_tokens", 0) or 0)
        self.requests += 1
        if self.spent_usd > self.cap_usd + 1e-9:
            raise RuntimeError(
                f"OpenRouter actual spend crossed the hard cap: ${self.spent_usd:.4f} > ${self.cap_usd:.2f}"
            )


class MotionExpertRun(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: Literal["2.0"] = "2.0"
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "created"
    stop_reason: str = ""
    channel_snapshot: dict[str, Any] = Field(default_factory=dict)
    corpus_path: str = ""
    corpus_hash: str = ""
    split_hash: str = ""
    training_ids: list[str] = Field(default_factory=list)
    holdout_ids: list[str] = Field(default_factory=list)
    pattern_catalog_path: str = ""
    pattern_catalog_hash: str = ""
    placement_model_path: str = ""
    placement_model_hash: str = ""
    artifacts: dict[str, str] = Field(default_factory=dict)
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    reviews: list[HeldoutFidelityReview] = Field(default_factory=list)
    accepted_review_index: int = -1
    repair_iterations: list[dict[str, Any]] = Field(default_factory=list)
    active_repair_override: dict[str, Any] = Field(default_factory=dict)
    openrouter_snapshot: dict[str, Any] = Field(default_factory=dict)
    budget: MotionExpertBudget = Field(default_factory=MotionExpertBudget)
    errors: list[str] = Field(default_factory=list)
    resolved_errors: list[str] = Field(default_factory=list)


def motion_expert_run_dir(run_id: str) -> Path:
    return AI_LABS_MOTION_DATA_DIR / run_id


def motion_expert_run_path(run_id: str) -> Path:
    return motion_expert_run_dir(run_id) / "motion_expert_run.json"


def save_motion_expert_run(run: MotionExpertRun) -> Path:
    run.updated_at = datetime.now(timezone.utc)
    destination = motion_expert_run_path(run.run_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination


def load_motion_expert_run(run_id: str) -> MotionExpertRun:
    return MotionExpertRun.model_validate_json(motion_expert_run_path(run_id).read_text(encoding="utf-8"))


def verify_channel_identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    channel_id = str(snapshot.get("channel_id") or "")
    handle = str(snapshot.get("uploader_id") or snapshot.get("handle") or "")
    if channel_id != AI_LABS_CHANNEL["channel_id"] or handle.casefold() != AI_LABS_CHANNEL["handle"].casefold():
        raise RuntimeError(
            "AI LABS identity mismatch: "
            f"expected {AI_LABS_CHANNEL['handle']} / {AI_LABS_CHANNEL['channel_id']}, "
            f"received {handle or '[missing]'} / {channel_id or '[missing]'}"
        )
    return {
        "title": str(snapshot.get("channel") or snapshot.get("title") or AI_LABS_CHANNEL["title"]),
        "handle": handle,
        "channel_id": channel_id,
        "url": str(snapshot.get("webpage_url") or AI_LABS_CHANNEL["url"]),
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_channel_listing(limit: int = 90) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    process = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs", "--no-warnings",
         "--flat-playlist", "--playlist-end", str(max(limit, AI_LABS_MOTION_CORPUS_SIZE)),
         "--dump-single-json", AI_LABS_CHANNEL["url"]],
        capture_output=True, text=True, timeout=180,
    )
    if process.returncode:
        raise RuntimeError(f"AI LABS channel identity/listing check failed: {process.stderr[-500:]}")
    payload = json.loads(process.stdout)
    snapshot = verify_channel_identity(payload)
    entries = [entry for entry in (payload.get("entries") or []) if entry.get("id")]
    return snapshot, entries


def _eligible_reference(record: ReferenceVideo) -> bool:
    return (
        record.channel_id == AI_LABS_CHANNEL["channel_id"]
        and record.channel_handle.casefold() == AI_LABS_CHANNEL["handle"].casefold()
        and record.duration_seconds >= MIN_DURATION_SECONDS
        and bool(record.video_id and record.url)
    )


def select_motion_reference_videos(records: list[ReferenceVideo], count: int = AI_LABS_MOTION_CORPUS_SIZE) -> list[ReferenceVideo]:
    unique = {record.video_id: record for record in records if _eligible_reference(record)}
    candidates = sorted(
        unique.values(), key=lambda item: (item.upload_date, item.views_per_day, item.video_id), reverse=True,
    )
    if len(candidates) < count:
        raise RuntimeError(f"AI LABS corpus has {len(candidates)} eligible videos; required {count}")
    newest_count = min(28, count)
    selected = candidates[:newest_count]
    selected_ids = {item.video_id for item in selected}
    buckets: dict[str, list[ReferenceVideo]] = defaultdict(list)
    for item in sorted(candidates[newest_count:], key=lambda value: (-value.views_per_day, value.video_id)):
        buckets[item.format_label].append(item)
    while len(selected) < count and any(buckets.values()):
        for label in sorted(buckets):
            if buckets[label] and len(selected) < count:
                item = buckets[label].pop(0)
                if item.video_id not in selected_ids:
                    selected.append(item)
                    selected_ids.add(item.video_id)
    if len(selected) < count:
        for item in candidates:
            if item.video_id not in selected_ids:
                selected.append(item)
                selected_ids.add(item.video_id)
            if len(selected) == count:
                break
    return selected


def stratified_train_holdout_split(
    records: list[ReferenceVideo], holdout_fraction: float = HOLDOUT_FRACTION,
) -> tuple[list[ReferenceVideo], list[ReferenceVideo], str]:
    if len(records) < AI_LABS_MOTION_CORPUS_SIZE:
        raise ValueError(f"at least {AI_LABS_MOTION_CORPUS_SIZE} references are required")
    holdout_count = max(1, round(len(records) * holdout_fraction))
    ranked = sorted(
        records,
        key=lambda item: hashlib.sha256(
            f"{AI_LABS_CHANNEL['channel_id']}:{item.format_label}:{item.video_id}".encode("utf-8")
        ).hexdigest(),
    )
    by_format: dict[str, list[ReferenceVideo]] = defaultdict(list)
    for item in ranked:
        by_format[item.format_label].append(item)
    holdout: list[ReferenceVideo] = []
    while len(holdout) < holdout_count and any(by_format.values()):
        for label in sorted(by_format):
            if by_format[label] and len(holdout) < holdout_count:
                holdout.append(by_format[label].pop(0))
    holdout_ids = {item.video_id for item in holdout}
    training = [item for item in records if item.video_id not in holdout_ids]
    split_hash = _sha({"training": sorted(item.video_id for item in training), "holdout": sorted(holdout_ids)})
    return training, holdout, split_hash


def assert_holdout_isolation(
    training_ids: list[str], holdout_ids: list[str], artifact: Any | None = None,
) -> None:
    overlap = set(training_ids) & set(holdout_ids)
    if overlap:
        raise RuntimeError(f"holdout leakage: IDs appear in both splits: {sorted(overlap)}")
    if artifact is not None:
        serialized = json.dumps(artifact, ensure_ascii=False, sort_keys=True)
        leaked = [video_id for video_id in holdout_ids if video_id and video_id in serialized]
        if leaked:
            raise RuntimeError(f"holdout leakage into training artifact: {sorted(leaked)}")


def _frame_strip_features(record: ReferenceVideo) -> dict[str, Any]:
    path = Path(record.analysis_frame_strip) if record.analysis_frame_strip else None
    if not path or not path.is_file():
        return {"status": "missing", "video_id": record.video_id}
    with Image.open(path) as source:
        image = source.convert("RGB").resize((480, 270))
    quantized = image.quantize(colors=6, method=Image.Quantize.MEDIANCUT).convert("RGB")
    palette_counts = Counter(quantized.get_flattened_data())
    total = max(1, image.width * image.height)
    palette = [
        {"hex": "#%02X%02X%02X" % color, "share": round(count / total, 4)}
        for color, count in palette_counts.most_common(6)
    ]
    edge = image.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_mean = ImageStat.Stat(edge).mean[0] / 255
    luminance = ImageStat.Stat(image.convert("L")).mean[0] / 255
    return {
        "status": "measured_frame_strip",
        "video_id": record.video_id,
        "palette": palette,
        "edge_density": round(edge_mean, 4),
        "mean_luminance": round(luminance, 4),
        "timecodes": record.visual_timecodes[:4],
        "strip_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _motion_trace_path(record: ReferenceVideo, namespace: str) -> Path:
    signature = (record.content_sha256 or record.listing_sha256 or _sha(record.video_id))[:12]
    return AI_LABS_MOTION_DATA_DIR / "_reference_cache" / namespace / f"{record.video_id}_{signature}.json"


def _frame_motion_delta(first: Path, second: Path) -> tuple[float, float]:
    with Image.open(first) as left, Image.open(second) as right:
        a = left.convert("L").resize((320, 180), Image.Resampling.LANCZOS)
        b = right.convert("L").resize((320, 180), Image.Resampling.LANCZOS)
    difference = ImageChops.difference(a, b)
    intensity = ImageStat.Stat(difference).mean[0] / 255
    bbox = difference.point(lambda value: 255 if value >= 18 else 0).getbbox()
    if not bbox:
        return round(intensity, 6), 0.0
    center_x = (bbox[0] + bbox[2]) / 2 / difference.width
    center_y = (bbox[1] + bbox[3]) / 2 / difference.height
    displacement = math.dist((0.5, 0.5), (center_x, center_y))
    return round(intensity, 6), round(displacement, 6)


def extract_public_motion_trace(record: ReferenceVideo, namespace: str = "training_motion_traces") -> str:
    """Measure short adjacent-frame motion windows without retaining source video."""
    destination = _motion_trace_path(record, namespace)
    if destination.is_file() and destination.stat().st_size > 256:
        return str(destination)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return ""
    direct = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs",
         "--no-warnings", "--get-url", "-f",
         "bestvideo[height<=720][ext=mp4]/bestvideo[height<=720]/best[height<=720]", record.url],
        capture_output=True, text=True, timeout=120,
    )
    stream_url = next((line.strip() for line in direct.stdout.splitlines() if line.strip()), "")
    if direct.returncode or not stream_url:
        return ""
    work = destination.parent / f".{destination.stem}"
    work.mkdir(parents=True, exist_ok=True)
    windows: list[dict[str, Any]] = []
    try:
        anchors = record.visual_timecodes[1:4] or [record.duration_seconds * 0.25, record.duration_seconds * 0.5]
        for window_index, anchor in enumerate(anchors[:2]):
            pattern = work / f"w{window_index}_%02d.jpg"
            process = subprocess.run(
                [ffmpeg, "-y", "-ss", f"{max(0.0, float(anchor)):.3f}", "-i", stream_url,
                 "-t", "1.2", "-vf", "fps=6,scale=320:-2", "-q:v", "4", str(pattern)],
                capture_output=True, text=True, timeout=150,
            )
            frames = sorted(work.glob(f"w{window_index}_*.jpg"))
            if process.returncode or len(frames) < 3:
                continue
            deltas: list[float] = []
            displacements: list[float] = []
            for first, second in zip(frames, frames[1:]):
                delta, displacement = _frame_motion_delta(first, second)
                deltas.append(delta)
                displacements.append(displacement)
            peak = max(range(len(deltas)), key=deltas.__getitem__) if deltas else 0
            peak_position = peak / max(1, len(deltas) - 1)
            easing = "power3.out" if peak_position <= 0.35 else "power2.inOut" if peak_position <= 0.7 else "power2.in"
            windows.append({
                "anchor_seconds": round(float(anchor), 3),
                "frame_rate": 6,
                "sample_count": len(frames),
                "normalized_deltas": deltas,
                "mean_delta": round(sum(deltas) / max(1, len(deltas)), 6),
                "peak_position": round(peak_position, 4),
                "motion_distance_proxy": round(sum(displacements) / max(1, len(displacements)), 6),
                "fitted_easing": easing,
            })
        if not windows:
            return ""
        trace = {
            "schema_version": "1.0",
            "video_id": record.video_id,
            "content_hash": record.content_sha256,
            "analysis_only": True,
            "source_video_retained": False,
            "windows": windows,
            "trace_hash": _sha(windows),
        }
        return str(_write_json(destination, trace))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def ensure_training_motion_traces(
    training: list[ReferenceVideo], *, should_cancel: Callable[[], bool] | None = None,
    report_progress: Callable[[int], None] | None = None,
) -> list[ReferenceVideo]:
    enriched = list(training)
    pending = []
    for index, record in enumerate(enriched):
        trace_path = str((record.model_extra or {}).get("motion_trace_path") or "")
        if trace_path and Path(trace_path).is_file():
            continue
        pending.append((index, record))
    completed = len(enriched) - len(pending)
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(pending))), thread_name_prefix="ai-labs-motion") as pool:
        futures = {pool.submit(extract_public_motion_trace, record): (index, record) for index, record in pending}
        for future in as_completed(futures):
            if should_cancel and should_cancel():
                for remaining in futures:
                    remaining.cancel()
                raise InterruptedError("motion-trace extraction canceled")
            index, record = futures[future]
            try:
                trace_path = future.result()
            except Exception:
                trace_path = ""
            if trace_path:
                enriched[index] = ReferenceVideo.model_validate({
                    **record.model_dump(mode="json"), "motion_trace_path": trace_path,
                })
                _write_cached_reference("ai_labs", enriched[index])
            completed += 1
            if report_progress:
                report_progress(45 + round(20 * completed / max(1, len(enriched))))
    return enriched


PATTERN_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {"id": "editorial-title-reset", "family": "title", "purpose": "Reset context or introduce a chapter", "triggers": ["hook", "chapter", "conclusion"], "contra": ["dense evidence", "active demonstration"], "variants": ["cold open", "chapter reset", "verdict"]},
    {"id": "kinetic-key-phrase", "family": "kinetic_typography", "purpose": "Land one short phrase at the spoken emphasis", "triggers": ["definition", "verdict", "contrast"], "contra": ["long quotation", "unverified claim"], "variants": ["word replace", "phrase wipe", "numeric emphasis"]},
    {"id": "source-locked-lower-third", "family": "lower_third", "purpose": "Identify a source or speaker without covering proof", "triggers": ["source attribution", "speaker", "product name"], "contra": ["unknown provenance", "already labeled UI"], "variants": ["source", "speaker", "product"]},
    {"id": "mechanism-flow", "family": "animated_diagram", "purpose": "Reveal a causal or workflow relationship in reading order", "triggers": ["mechanism", "workflow", "dependency"], "contra": ["simple fact", "strong real demonstration"], "variants": ["chain", "branch", "feedback loop"]},
    {"id": "criterion-comparison", "family": "comparison_table", "purpose": "Resolve a real comparison one criterion at a time", "triggers": ["comparison", "tradeoff", "before and after"], "contra": ["different tasks", "unsupported winner"], "variants": ["two lane", "scorecard", "old new"]},
    {"id": "evidence-focus", "family": "source_annotation", "purpose": "Direct attention to the exact cited line or UI control", "triggers": ["quote", "number", "source claim", "interface control"], "contra": ["missing DOM range", "unrelated narration"], "variants": ["underline", "outline", "reading corridor"]},
    {"id": "code-proof", "family": "code_terminal", "purpose": "Show a real command, code change, or verified output", "triggers": ["code", "command", "test", "repository"], "contra": ["fabricated output", "generic technology mention"], "variants": ["command result", "diff", "test suite"]},
    {"id": "ordered-progress", "family": "progress", "purpose": "Track finite steps or measured completion", "triggers": ["steps", "progress", "status", "checklist"], "contra": ["decorative loading", "unknown metric"], "variants": ["stepper", "checklist", "status ladder"]},
    {"id": "timeline-cause", "family": "timeline", "purpose": "Explain chronology or cause and effect", "triggers": ["timeline", "history", "sequence", "then"], "contra": ["unordered list", "single event"], "variants": ["launch", "causality", "iteration"]},
    {"id": "direct-data-story", "family": "chart", "purpose": "Reveal a measured relationship with direct labels", "triggers": ["benchmark", "trend", "percentage", "cost"], "contra": ["invented metric", "single unsupported number"], "variants": ["bar", "line", "rank", "unit economics"]},
    {"id": "icon-capability-montage", "family": "icon_montage", "purpose": "Summarize a verified compact set of capabilities", "triggers": ["capabilities", "integrations", "tool set"], "contra": ["more than six items", "generic logo cloud"], "variants": ["capability row", "integration ring", "tool stack"]},
    {"id": "interface-state-change", "family": "ui_overlay", "purpose": "Show a real product action and resulting state", "triggers": ["click", "generate", "edit", "result"], "contra": ["fake UI", "login or popup obstruction"], "variants": ["cursor focus", "before after", "result reveal"]},
    {"id": "sequential-ledger", "family": "list", "purpose": "Reveal a short ordered list without card soup", "triggers": ["three reasons", "steps", "requirements", "limitations"], "contra": ["unordered filler", "more than six items"], "variants": ["ranked list", "checklist", "decision log"]},
    {"id": "claim-proof-verdict", "family": "claim_evidence", "purpose": "Separate a claim, its evidence, and the editorial conclusion", "triggers": ["claim", "evidence", "test result", "caveat"], "contra": ["missing source", "opinion presented as proof"], "variants": ["claim proof", "promise reality", "source result take"]},
    {"id": "quiet-cut-fade", "family": "transition", "purpose": "Change chapters without competing with the information", "triggers": ["topic change", "time jump", "chapter"], "contra": ["within one continuous demonstration", "spectacle"], "variants": ["hard cut", "short fade", "matched geometry"]},
)


SATURATION_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("comparison_table", (" vs ", "better than", "debate", "compared")),
    ("code_terminal", ("code", "github", "cli", "repository")),
    ("animated_diagram", ("workflow", "process", "lifecycle", "engineering", "agent")),
    ("ui_overlay", ("design", "website", "sites", "setup", "use ")),
    ("list", ("tips", "rules", "ways", "features", "use cases", "levels", "skills")),
    ("progress", ("limit", "free", "errors", "problem", "fixed")),
    ("chart", ("10x", "90%", "cost", "faster")),
)


def catalog_saturation_audit(training: list[ReferenceVideo], window: int = 8) -> dict[str, Any]:
    """Track when coarse graphic-family signals stop expanding in corpus order."""
    discovered: set[str] = set()
    consecutive_without_new = 0
    first_seen: dict[str, int] = {}
    for index, record in enumerate(training):
        title = f" {record.title.casefold()} "
        observed = {family for family, phrases in SATURATION_SIGNALS if any(phrase in title for phrase in phrases)}
        observed.add("editorial_title")
        new = observed - discovered
        if new:
            for family in sorted(new):
                first_seen[family] = index + 1
            discovered.update(new)
            consecutive_without_new = 0
        else:
            consecutive_without_new += 1
    return {
        "window_required": window,
        "consecutive_eligible_training_videos_without_new_signal": consecutive_without_new,
        "saturated": consecutive_without_new >= window,
        "observed_family_signals": sorted(discovered),
        "first_seen_training_position": first_seen,
        "method": "deterministic title and format signal audit; frame measurements remain evidence for visual specs",
    }


def _training_motion_measurements(training: list[ReferenceVideo]) -> dict[str, Any]:
    traces: list[dict[str, Any]] = []
    for record in training:
        path = Path(str((record.model_extra or {}).get("motion_trace_path") or ""))
        if not path.is_file():
            continue
        try:
            trace = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for window in trace.get("windows", []):
            traces.append(window)
    deltas = sorted(float(item.get("mean_delta") or 0) for item in traces)
    distances = sorted(float(item.get("motion_distance_proxy") or 0) for item in traces)
    easings = Counter(str(item.get("fitted_easing") or "power3.out") for item in traces)

    def percentile(values: list[float], fraction: float, default: float) -> float:
        if not values:
            return default
        position = min(len(values) - 1, max(0, round((len(values) - 1) * fraction)))
        return round(values[position], 6)

    return {
        "trace_count": len(traces),
        "motion_delta_band": [percentile(deltas, 0.2, 0.02), percentile(deltas, 0.8, 0.12)],
        "motion_distance_proxy_band": [percentile(distances, 0.2, 0.03), percentile(distances, 0.8, 0.2)],
        "fitted_easing_distribution": dict(easings.most_common()),
        "trace_hash": _sha(traces),
    }


def _motion_trace_for_record(record: ReferenceVideo) -> dict[str, Any]:
    path = Path(str((record.model_extra or {}).get("motion_trace_path") or ""))
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_motion_pattern_catalog(training: list[ReferenceVideo]) -> dict[str, Any]:
    observations = [_frame_strip_features(item) for item in training]
    measured = [item for item in observations if item.get("status") == "measured_frame_strip"]
    supporting = [item for item in training if item.analysis_frame_strip and Path(item.analysis_frame_strip).is_file()]
    if len(supporting) < 6:
        raise RuntimeError("pattern catalog requires at least six measured AI LABS frame strips")
    palette_votes = Counter(
        color["hex"] for observation in measured for color in observation.get("palette", [])[:3]
    )
    dominant_palette = [color for color, _count in palette_votes.most_common(8)]
    motion_measurements = _training_motion_measurements(training)
    patterns: list[MotionGraphicPattern] = []
    for index, definition in enumerate(PATTERN_DEFINITIONS):
        refs = [supporting[(index + offset * 5) % len(supporting)] for offset in range(min(3, len(supporting)))]
        evidence = [
            MotionEvidence(
                video_id=item.video_id,
                url=item.url,
                timecodes=item.visual_timecodes[1:4],
                observation_hash=_sha({
                    "frame": _frame_strip_features(item),
                    "motion": _motion_trace_for_record(item),
                }),
            )
            for item in refs
        ]
        spec = MotionVisualSpec(
            typography={"roles": ["dominant statement", "direct label", "source"], "body_min_px_1080p": 28, "max_lines": 3},
            palette={"measured_dominant": dominant_palette, "base": ["#090A0A", "#F2F1ED"], "product_color_scope": "localized"},
            layout={"camera": "locked", "focal_groups_max": 3, "dominant_object_share": [0.72, 0.94], "intentional_asymmetry": True},
            motion={
                "entrance_px": [8, 18], "entrance_frames_30fps": [8, 22], "stagger_frames": [7, 15],
                "easing": list(motion_measurements["fitted_easing_distribution"] or {"power3.out": 1}),
                "measured_delta_band": motion_measurements["motion_delta_band"],
                "measured_distance_proxy_band": motion_measurements["motion_distance_proxy_band"],
                "ambient_motion": False,
            },
            timing={"meaningful_state_change_seconds": [2.0, 6.0], "exit": ["cut", "fade<=0.2s"], "reading_hold_required": True},
            information_density={"claim_per_frame": 1, "supporting_items_max": 3, "source_label_only_when_needed": True},
        )
        patterns.append(MotionGraphicPattern(
            id=definition["id"], family=definition["family"], variants=definition["variants"],
            narrative_purpose=definition["purpose"], narrative_triggers=definition["triggers"],
            contraindications=definition["contra"], visual_spec=spec, supporting_evidence=evidence,
            implementation_primitives=["hyperframes", "gsap-seekable", "svg", "css-grid"],
            confidence=min(0.95, 0.65 + len(evidence) * 0.08),
        ))
    saturation = catalog_saturation_audit(training)
    if not saturation["saturated"]:
        raise RuntimeError(
            "corpus expansion is required: eight consecutive eligible training videos "
            "have not yet passed without a new graphic-family signal"
        )
    catalog = {
        "schema_version": "2.0",
        "profile_id": "ai-labs-motion-expert-v1",
        "channel": AI_LABS_CHANNEL,
        "training_video_count": len(training),
        "training_ids": [item.video_id for item in training],
        "observation_count": len(measured),
        "observation_hash": _sha(measured),
        "training_motion_measurements": motion_measurements,
        "saturation": saturation,
        "patterns": [pattern.model_dump(mode="json") for pattern in patterns],
        "originality_policy": "Transfer grammar only; never trace reference layouts or reuse creator assets.",
    }
    return catalog


ROLE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("hook", ("what if", "imagine", "here's the", "the surprising")),
    ("comparison", ("versus", "compared", "on the other hand", "while")),
    ("timeline", ("first", "then", "later", "timeline", "over the next")),
    ("mechanism", ("because", "works by", "under the hood", "flows through", "how it works")),
    ("list", ("three", "four", "steps", "reasons", "requirements")),
    ("evidence", ("according to", "the paper", "the announcement", "the source", "reported")),
    ("code", ("code", "terminal", "command", "repository", "test suite")),
    ("metric", ("percent", "%", "benchmark", "cost", "faster", "slower")),
    ("caveat", ("but", "however", "the catch", "limitation")),
    ("conclusion", ("so the takeaway", "in short", "the verdict", "ultimately")),
)

ROLE_TO_PATTERN = {
    "hook": "editorial-title-reset",
    "definition": "kinetic-key-phrase",
    "comparison": "criterion-comparison",
    "timeline": "timeline-cause",
    "mechanism": "mechanism-flow",
    "list": "sequential-ledger",
    "evidence": "evidence-focus",
    "code": "code-proof",
    "metric": "direct-data-story",
    "caveat": "claim-proof-verdict",
    "conclusion": "editorial-title-reset",
}


def classify_narrative_role(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    for role, phrases in ROLE_RULES:
        if any(phrase in normalized for phrase in phrases):
            return role
    return "definition"


def build_placement_model(catalog: dict[str, Any]) -> dict[str, Any]:
    available = {item["id"] for item in catalog.get("patterns", [])}
    missing = sorted(set(ROLE_TO_PATTERN.values()) - available)
    if missing:
        raise RuntimeError(f"placement model missing required patterns: {missing}")
    return {
        "schema_version": "1.0",
        "model_id": "ai-labs-placement-v1",
        "catalog_hash": _sha(catalog),
        "role_rules": [{"role": role, "phrases": list(phrases)} for role, phrases in ROLE_RULES],
        "role_to_pattern": ROLE_TO_PATTERN,
        "target_graphics_per_minute": [3.0, 6.0],
        "duration_seconds": [3.0, 9.0],
        "prefer_no_graphic_when": ["strong aligned b-roll", "readable source proof", "active product demonstration"],
        "placement_boundary": "clause_or_sentence",
        "adjacency_rule": "never repeat the same family consecutively",
    }


def plan_graphic_placements(
    segments: list[dict[str, Any]], catalog: dict[str, Any], placement_model: dict[str, Any],
) -> list[PlacementDecision]:
    patterns = {item["id"]: item for item in catalog.get("patterns", [])}
    decisions: list[PlacementDecision] = []
    last_family = ""
    for segment in segments:
        segment_id = str(segment["id"])
        text = str(segment.get("text") or "")
        start = max(0.0, float(segment.get("start_seconds") or 0))
        end = max(start + 0.2, float(segment.get("end_seconds") or start + 5))
        role = classify_narrative_role(text)
        pattern_id = placement_model["role_to_pattern"].get(role)
        pattern = patterns.get(pattern_id or "")
        strong_real_visual = bool(segment.get("broll_available") or segment.get("source_visual_available"))
        explanatory_role = role in {"comparison", "timeline", "mechanism", "list", "metric"}
        evidence_required = role in {"evidence", "metric", "comparison", "code"}
        rejection: list[str] = []
        if strong_real_visual and not explanatory_role:
            rejection.append("aligned real evidence or b-roll already communicates this beat")
        if evidence_required and not segment.get("evidence_ids"):
            rejection.append("required evidence is unavailable")
        if pattern and pattern["family"] == last_family:
            rejection.append("would repeat the adjacent graphic family")
        if not pattern:
            rejection.append("no supported pattern for narrative role")
        if rejection:
            decisions.append(PlacementDecision(
                segment_id=segment_id, narrative_role=role, decision="no_graphic",
                start_seconds=start, end_seconds=end, trigger=role, confidence=0.9,
                evidence_required=evidence_required, rejection_reasons=rejection,
            ))
            continue
        duration = min(9.0, max(3.0, end - start))
        decision = PlacementDecision(
            segment_id=segment_id, narrative_role=role, pattern_id=pattern_id, decision="graphic",
            start_seconds=start, end_seconds=min(end, start + duration), trigger=role,
            confidence=0.82 if explanatory_role else 0.74, evidence_required=evidence_required,
            reasons=["narrative trigger matches pattern purpose", "graphic adds a relationship not supplied by footage"],
        )
        decisions.append(decision)
        last_family = pattern["family"]
    return decisions


def _anonymized_blind_packet(
    decisions: list[PlacementDecision], holdout: list[ReferenceVideo], evaluation_metrics: dict[str, Any],
    holdout_motion_traces: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    references = []
    traces = holdout_motion_traces or []
    for index, item in enumerate(holdout):
        features = _frame_strip_features(item)
        features.pop("video_id", None)
        features.pop("strip_hash", None)
        references.append({
            "duration": item.duration_seconds,
            "format": item.format_label,
            "normalized_timecodes": [round(second / max(1.0, item.duration_seconds), 4) for second in item.visual_timecodes[:4]],
            "feature_trace": features,
            "motion_trace": traces[index] if index < len(traces) else {},
        })
    candidates = [
        {"segment": f"segment_{index + 1:02d}", "role": item.narrative_role,
         "decision": item.decision, "pattern": item.pattern_id,
         "duration": round(item.end_seconds - item.start_seconds, 3)}
        for index, item in enumerate(decisions)
    ]
    ordered = sorted(
        [{"kind": "candidate", "payload": candidates, "metrics": evaluation_metrics},
         {"kind": "reference", "payload": references}],
        key=lambda item: _sha(item),
    )
    return {
        "rubric": {
            "visual_fidelity": ["typography", "color", "hierarchy", "layout", "motion curve", "timing"],
            "placement_fidelity": ["narrative beat", "start", "duration", "pacing", "density", "omit/use decision"],
        },
        "items": ordered,
    }


def _review_image_metrics(path: Path) -> dict[str, float]:
    with Image.open(path) as source:
        image = source.convert("RGB").resize((320, 180), Image.Resampling.LANCZOS)
    luminance = ImageStat.Stat(image.convert("L")).mean[0] / 255
    edge = image.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_density = ImageStat.Stat(edge).mean[0] / 255
    return {"luminance": round(luminance, 5), "edge_density": round(edge_density, 5)}


def _difference_hash(path: Path, size: int = 8) -> tuple[int, int]:
    with Image.open(path) as source:
        gray = source.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    pixels = list(gray.get_flattened_data())
    value = 0
    for row in range(size):
        offset = row * (size + 1)
        for column in range(size):
            value = (value << 1) | int(pixels[offset + column] > pixels[offset + column + 1])
    return value, size * size


def _prepare_blind_copy(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as original:
        image = original.convert("RGB")
        image.thumbnail((960, 540), Image.Resampling.LANCZOS)
        image.save(destination, format="JPEG", quality=84, optimize=True)
    return destination


def prepare_sealed_holdout_review_assets(
    run: MotionExpertRun, holdout: list[ReferenceVideo],
) -> list[Path]:
    """Create ID-free review copies after training artifacts are already frozen."""
    root = motion_expert_run_dir(run.run_id) / "_sealed_holdout" / "review_assets"
    outputs: list[Path] = []
    for index, record in enumerate(holdout):
        source = Path(record.analysis_frame_strip) if record.analysis_frame_strip else Path("")
        if not source.is_file():
            try:
                raw = _extract_public_frame_strip(record, f"ai_labs_holdout_{run.run_id}")
                source = Path(raw) if raw else Path("")
            except Exception:
                source = Path("")
        if not source.is_file():
            continue
        destination = root / f"reference_{index + 1:02d}.jpg"
        outputs.append(_prepare_blind_copy(source, destination))
    return outputs


def prepare_sealed_holdout_motion_traces(
    run: MotionExpertRun, holdout: list[ReferenceVideo],
) -> list[dict[str, Any]]:
    root = motion_expert_run_dir(run.run_id) / "_sealed_holdout" / "motion_traces"
    traces: list[dict[str, Any]] = []
    for index, record in enumerate(holdout):
        try:
            raw = extract_public_motion_trace(record, f"holdout_motion_{run.run_id}")
            payload = json.loads(Path(raw).read_text(encoding="utf-8")) if raw else {}
        except Exception:
            payload = {}
        sanitized = {
            "windows": payload.get("windows", []),
            "analysis_only": True,
            "source_video_retained": False,
        }
        _write_json(root / f"reference_{index + 1:02d}.json", sanitized)
        traces.append(sanitized)
    return traces


def deterministic_heldout_measurements(
    candidate_images: list[Path], holdout_images: list[Path],
    decisions: list[PlacementDecision], evaluation_metrics: dict[str, Any],
) -> dict[str, Any]:
    if not candidate_images or not holdout_images:
        return {
            "visual_score": 1.0, "placement_score": 1.0,
            "hard_failures": ["candidate or held-out visual evidence is missing"],
        }
    candidate = [_review_image_metrics(path) for path in candidate_images]
    reference = [_review_image_metrics(path) for path in holdout_images]
    candidate_mean = {
        key: sum(item[key] for item in candidate) / len(candidate) for key in ("luminance", "edge_density")
    }
    reference_mean = {
        key: sum(item[key] for item in reference) / len(reference) for key in ("luminance", "edge_density")
    }
    visual_distance = (
        abs(candidate_mean["luminance"] - reference_mean["luminance"]) * 0.55
        + abs(candidate_mean["edge_density"] - reference_mean["edge_density"]) * 0.45
    )
    visual_score = round(max(1.0, 5.0 - visual_distance * 5.0), 3)
    active = [item for item in decisions if item.decision == "graphic"]
    density = float(evaluation_metrics.get("graphics_per_minute") or len(active))
    durations = [item.end_seconds - item.start_seconds for item in active]
    duration_failures = sum(not 3.0 <= value <= 9.0 for value in durations)
    repeated = int(evaluation_metrics.get("repeated_adjacent_families") or 0)
    density_penalty = 0.0 if 3.0 <= density <= 6.0 else min(2.0, abs(density - 4.5) * 0.45)
    placement_score = round(max(1.0, 5.0 - density_penalty - duration_failures * 0.5 - repeated), 3)
    near_matches: list[float] = []
    for candidate_path in candidate_images:
        candidate_hash, bits = _difference_hash(candidate_path)
        for holdout_path in holdout_images:
            reference_hash, _ = _difference_hash(holdout_path)
            similarity = 1.0 - ((candidate_hash ^ reference_hash).bit_count() / bits)
            if similarity >= 0.97:
                near_matches.append(round(similarity, 4))
    failures = ["candidate frame is a near-duplicate of held-out reference composition"] if near_matches else []
    return {
        "visual_score": visual_score,
        "placement_score": placement_score,
        "candidate_count": len(candidate_images),
        "holdout_count": len(holdout_images),
        "candidate_means": {key: round(value, 5) for key, value in candidate_mean.items()},
        "reference_means": {key: round(value, 5) for key, value in reference_mean.items()},
        "visual_distance": round(visual_distance, 5),
        "near_duplicate_similarities": near_matches,
        "hard_failures": failures,
    }


def _image_data_url(path: Path) -> str:
    mime = "image/png" if path.suffix.casefold() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


REVIEW_SCHEMA = {
    "name": "AILabsHeldoutFidelityReview",
    "strict": True,
    "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "segment_scores": {
                "type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "segment_id": {"type": "string"},
                        "visual_fidelity": {"type": "number", "minimum": 1, "maximum": 5},
                        "placement_fidelity": {"type": "number", "minimum": 1, "maximum": 5},
                        "notes": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["segment_id", "visual_fidelity", "placement_fidelity", "notes"],
                },
            },
            "hard_failures": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["segment_scores", "hard_failures"],
    },
}


def run_independent_blind_review(
    run: MotionExpertRun, decisions: list[PlacementDecision], holdout: list[ReferenceVideo],
    evaluation_metrics: dict[str, Any], *, estimated_max_usd: float = 1.0,
) -> HeldoutFidelityReview:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is required for the independent held-out review")
    if AI_LABS_MOTION_REVIEW_MODEL == AI_LABS_MOTION_TRAIN_MODEL:
        raise RuntimeError("held-out reviewer must differ from the training/analysis model")
    run.budget.reserve(estimated_max_usd)
    evaluation_root = Path(run.artifacts.get("evaluation_package") or "")
    candidate_images = sorted((evaluation_root / "snapshots").glob("frame-*.png"))
    holdout_images = prepare_sealed_holdout_review_assets(run, holdout)
    holdout_motion_traces = prepare_sealed_holdout_motion_traces(run, holdout)
    packet = _anonymized_blind_packet(
        decisions, holdout, evaluation_metrics, holdout_motion_traces,
    )
    deterministic = deterministic_heldout_measurements(
        candidate_images, holdout_images, decisions, evaluation_metrics,
    )
    packet["deterministic_gate"] = {
        "visual_score": deterministic["visual_score"],
        "placement_score": deterministic["placement_score"],
        "hard_failures": deterministic["hard_failures"],
    }
    packet_hash = _sha(packet)
    content: list[dict[str, Any]] = [{
        "type": "text",
        "text": (
            "Review the anonymous candidate against the held-out reference band. The packet order is "
            "deterministic but carries no authorship, filenames, prompts, or prior scores. Return one score "
            "for each candidate segment.\n\n" + json.dumps(packet, ensure_ascii=False)
        ),
    }]
    for index, path in enumerate(candidate_images[:6]):
        content.extend([
            {"type": "text", "text": f"Anonymous candidate frame {index + 1}"},
            {"type": "image_url", "image_url": {"url": _image_data_url(path)}},
        ])
    for index, path in enumerate(holdout_images[:7]):
        content.extend([
            {"type": "text", "text": f"Anonymous held-out reference strip {index + 1}"},
            {"type": "image_url", "image_url": {"url": _image_data_url(path)}},
        ])
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": AI_LABS_MOTION_REVIEW_MODEL,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": (
                    "You are an independent motion-design evaluator. Score the anonymous candidate against "
                    "the reference performance band. Do not infer authorship. Use 0.05 score increments."
                )},
                {"role": "user", "content": content},
            ],
            "max_tokens": 2200,
            "response_format": {"type": "json_schema", "json_schema": REVIEW_SCHEMA},
        },
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    usage = payload.get("usage") or {}
    run.budget.reconcile(usage, estimated_max_usd)
    content = payload["choices"][0]["message"]["content"]
    result = json.loads(content) if isinstance(content, str) else content
    scores = []
    for item in result["segment_scores"]:
        raw = SegmentAxisScore.model_validate(item)
        scores.append(raw.model_copy(update={
            "visual_fidelity": min(raw.visual_fidelity, deterministic["visual_score"]),
            "placement_fidelity": min(raw.placement_fidelity, deterministic["placement_score"]),
        }))
    values = [value for item in scores for value in (item.visual_fidelity, item.placement_fidelity)]
    mean = round(sum(values) / max(1, len(values)), 3)
    minimum = round(min(values) if values else 1.0, 3)
    failures = list(result.get("hard_failures") or []) + list(deterministic["hard_failures"])
    if not scores:
        failures.append("independent reviewer returned no candidate segment scores")
    review = HeldoutFidelityReview(
        score_policy="fresh_matrix_v2",
        reviewer_model=AI_LABS_MOTION_REVIEW_MODEL,
        independent=True,
        blind_packet_hash=packet_hash,
        segment_scores=scores,
        hard_failures=failures,
        mean_score=mean,
        minimum_score=minimum,
        passed=mean >= 4.95 and minimum >= 4.5 and not failures,
        deterministic=deterministic,
        usage=usage,
    )
    run.reviews.append(review)
    return review


def _axis_mean(review: HeldoutFidelityReview, axis: Literal["visual", "placement"]) -> float:
    values = [
        item.visual_fidelity if axis == "visual" else item.placement_fidelity
        for item in review.segment_scores
    ]
    return round(sum(values) / max(1, len(values)), 4)


def scope_post_repair_review(
    before: HeldoutFidelityReview,
    raw_after: HeldoutFidelityReview,
    iteration: dict[str, Any],
) -> HeldoutFidelityReview:
    """Recompute the complete fresh review; freeze artifacts, never judgments.

    Reusing prior scores on untouched segments hides regressions and can produce
    a false pass. Missing/duplicate segments must not silently inherit old scores.
    ``iteration`` remains in the interface for existing callers/checkpoints.
    """
    expected = {score.segment_id for score in before.segment_scores}
    received = [score.segment_id for score in raw_after.segment_scores]
    failures = list(raw_after.hard_failures)
    if set(received) != expected or len(received) != len(expected) or not expected:
        failures.append("post-repair review must score every expected segment exactly once")
    caps = raw_after.deterministic or {}
    if any(key not in caps for key in ("visual_score", "placement_score")):
        failures.append("post-repair review is missing deterministic score caps")
    visual_cap = max(1.0, min(5.0, float(caps.get("visual_score", 1))))
    placement_cap = max(1.0, min(5.0, float(caps.get("placement_score", 1))))
    scores: list[SegmentAxisScore] = []
    for fresh in raw_after.segment_scores:
        scores.append(SegmentAxisScore(
            segment_id=fresh.segment_id,
            visual_fidelity=min(fresh.visual_fidelity, visual_cap),
            placement_fidelity=min(fresh.placement_fidelity, placement_cap),
            notes=fresh.notes,
        ))
    values = [value for score in scores for value in (score.visual_fidelity, score.placement_fidelity)]
    mean = round(sum(values) / max(1, len(values)), 3)
    minimum = round(min(values) if values else 1.0, 3)
    return raw_after.model_copy(update={
        "segment_scores": scores,
        "mean_score": mean,
        "minimum_score": minimum,
        "passed": mean >= 4.95 and minimum >= 4.5 and not failures,
        "hard_failures": failures,
    })


def select_lowest_review_weakness(review: HeldoutFidelityReview) -> dict[str, Any]:
    weaknesses: list[dict[str, Any]] = []
    for index, score in enumerate(review.segment_scores):
        weaknesses.extend([
            {"axis": "visual", "segment_id": score.segment_id, "score": score.visual_fidelity,
             "stable_order": index * 2, "notes": score.notes},
            {"axis": "placement", "segment_id": score.segment_id, "score": score.placement_fidelity,
             "stable_order": index * 2 + 1, "notes": score.notes},
        ])
    if not weaknesses:
        raise RuntimeError("cannot target a repair without held-out segment scores")
    target = min(weaknesses, key=lambda item: (item["score"], item["stable_order"]))
    combined = " ".join(target["notes"]).casefold()
    if target["axis"] == "placement":
        target["dimension"] = "timing" if any(word in combined for word in ("timing", "duration", "late", "early")) else "pacing"
    else:
        target["dimension"] = next(
            (dimension for dimension, words in (
                ("typography", ("typography", "typeface", "font", "letter", "text")),
                ("color", ("color", "palette", "contrast")),
                ("hierarchy", ("hierarchy", "emphasis", "focal")),
                ("layout", ("layout", "spacing", "alignment", "composition")),
                ("motion_curve", ("motion", "ease", "curve", "animation")),
                ("density", ("density", "busy", "crowded", "empty")),
            ) if any(word in combined for word in words)),
            "hierarchy",
        )
    return target


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _evaluation_component_hashes(project_dir: Path) -> dict[str, str]:
    return {
        name: _file_hash(project_dir / name)
        for name in ("index.html", "placements.json", "evaluation_metrics.json", "repair_override.json")
    }


def apply_targeted_repair(
    run: MotionExpertRun, review: HeldoutFidelityReview,
    catalog: dict[str, Any], placement_model: dict[str, Any],
) -> tuple[list[PlacementDecision], dict[str, Any], dict[str, Any]]:
    target = select_lowest_review_weakness(review)
    round_number = len(run.repair_iterations) + 1
    project_dir = motion_expert_run_dir(run.run_id) / "evaluation_60s"
    before_hashes = _evaluation_component_hashes(project_dir)
    checkpoint = motion_expert_run_dir(run.run_id) / "repair_iterations" / f"round_{round_number:02d}" / "before"
    checkpoint.mkdir(parents=True, exist_ok=True)
    for name in before_hashes:
        source = project_dir / name
        if source.is_file():
            shutil.copy2(source, checkpoint / name)
    previous_override = dict(run.active_repair_override)
    new_repair = {
        "axis": target["axis"], "dimension": target["dimension"],
        "segment_id": target["segment_id"], "round": round_number,
    }
    previous_repairs = list(previous_override.get("repairs") or [])
    if not previous_repairs and previous_override.get("axis"):
        previous_repairs = [previous_override]
    repair_override = {"repairs": [*previous_repairs, new_repair]}
    project_dir, decisions, metrics = write_evaluation_package(
        run, catalog, placement_model, repair_override,
    )
    after_hashes = _evaluation_component_hashes(project_dir)
    if target["axis"] == "visual":
        if before_hashes["placements.json"] != after_hashes["placements.json"]:
            raise RuntimeError("visual repair changed frozen placement decisions")
        if before_hashes["evaluation_metrics.json"] != after_hashes["evaluation_metrics.json"]:
            raise RuntimeError("visual repair changed frozen evaluation metrics")
    iteration = {
        "round": round_number,
        "target": target,
        "previous_override": previous_override,
        "repair_override": repair_override,
        "before_hashes": before_hashes,
        "after_hashes": after_hashes,
        "checkpoint": str(checkpoint),
        "accepted": None,
        "reason": "awaiting independent post-repair review",
    }
    run.active_repair_override = repair_override
    run.repair_iterations.append(iteration)
    save_motion_expert_run(run)
    return decisions, metrics, iteration


def _restore_repair_checkpoint(run: MotionExpertRun, iteration: dict[str, Any], reason: str) -> None:
    project_dir = motion_expert_run_dir(run.run_id) / "evaluation_60s"
    checkpoint = Path(iteration["checkpoint"])
    for name in ("index.html", "placements.json", "evaluation_metrics.json", "repair_override.json"):
        source = checkpoint / name
        if source.is_file():
            shutil.copy2(source, project_dir / name)
    run.active_repair_override = dict(iteration.get("previous_override") or {})
    iteration["accepted"] = False
    iteration["reason"] = reason


def reconcile_repair_state(run: MotionExpertRun) -> None:
    """Recover a paid loop without repeating reviews or keeping a regressive legacy repair."""
    if not run.repair_iterations:
        return
    for index, iteration in enumerate(run.repair_iterations):
        if iteration.get("accepted") is not True:
            continue
        axis = str((iteration.get("target") or {}).get("axis") or "")
        before_axis = float((iteration.get("before_axis_means") or {}).get(axis) or 0)
        after_axis = float((iteration.get("after_axis_means") or {}).get(axis) or 0)
        if before_axis and after_axis + 1e-6 < before_axis:
            _restore_repair_checkpoint(
                run, iteration,
                f"reverted during resume audit because targeted {axis} fidelity regressed",
            )
            for later in run.repair_iterations[index + 1:]:
                later["accepted"] = False
                later["reason"] = "reverted because an earlier accepted checkpoint was invalidated"
            before_hash = iteration.get("before_review_hash")
            matching = next(
                (review_index for review_index, review in enumerate(run.reviews)
                 if review.blind_packet_hash == before_hash),
                -1,
            )
            run.accepted_review_index = matching
            accepted_path = motion_expert_run_dir(run.run_id) / f"heldout_review_round_{matching:02d}.json"
            if matching >= 0 and accepted_path.is_file():
                run.artifacts["heldout_review"] = str(accepted_path)
            save_motion_expert_run(run)
            return
    iteration = run.repair_iterations[-1]
    if iteration.get("accepted") is None:
        _restore_repair_checkpoint(
            run, iteration, "reverted after interruption before an independent post-repair review",
        )
        save_motion_expert_run(run)


def finalize_or_revert_repair(
    run: MotionExpertRun, before: HeldoutFidelityReview, after: HeldoutFidelityReview,
) -> bool:
    if not run.repair_iterations:
        raise RuntimeError("no repair iteration is available to finalize")
    iteration = run.repair_iterations[-1]
    axis = iteration["target"]["axis"]
    unrelated_axis: Literal["visual", "placement"] = "placement" if axis == "visual" else "visual"
    target_segment_id = iteration["target"]["segment_id"]

    def segment_axis_score(review: HeldoutFidelityReview) -> float:
        for score in review.segment_scores:
            if score.segment_id == target_segment_id:
                return score.visual_fidelity if axis == "visual" else score.placement_fidelity
        return 0.0

    target_before = segment_axis_score(before)
    target_after = segment_axis_score(after)
    unrelated_regressed = _axis_mean(after, unrelated_axis) + 1e-6 < _axis_mean(before, unrelated_axis)
    overall_regressed = after.mean_score + 1e-6 < before.mean_score
    target_improved = target_after > target_before + 1e-6
    before_by_id = {s.segment_id: s for s in before.segment_scores}
    after_by_id = {s.segment_id: s for s in after.segment_scores}
    incomplete = set(before_by_id) != set(after_by_id) or len(after_by_id) != len(after.segment_scores)
    segment_regressed = any(
        getattr(after_by_id[sid], field) + 1e-6 < getattr(old, field)
        for sid, old in before_by_id.items() if sid in after_by_id
        for field in ("visual_fidelity", "placement_fidelity")
    )
    rejected_reason = ""
    if after.hard_failures or incomplete:
        rejected_reason = "post-repair review failed integrity or quality gates"
    elif unrelated_regressed:
        rejected_reason = f"{unrelated_axis} fidelity regressed"
    elif overall_regressed:
        rejected_reason = "overall fidelity regressed"
    elif segment_regressed:
        rejected_reason = "individual segment fidelity regressed"
    elif not target_improved and not after.passed:
        rejected_reason = f"targeted {axis} score did not improve"
    if rejected_reason:
        _restore_repair_checkpoint(run, iteration, f"reverted because {rejected_reason}")
    else:
        iteration["accepted"] = True
        iteration["reason"] = "accepted; target improved with no overall or unrelated-axis regression"
    iteration["before_review_hash"] = before.blind_packet_hash
    iteration["after_review_hash"] = after.blind_packet_hash
    iteration["before_axis_means"] = {
        "visual": _axis_mean(before, "visual"), "placement": _axis_mean(before, "placement"),
    }
    iteration["after_axis_means"] = {
        "visual": _axis_mean(after, "visual"), "placement": _axis_mean(after, "placement"),
    }
    iteration["target_scores"] = {"before": target_before, "after": target_after}
    save_motion_expert_run(run)
    return not rejected_reason


def run_paid_fidelity_repair_loop(
    run: MotionExpertRun, decisions: list[PlacementDecision], holdout: list[ReferenceVideo],
    metrics: dict[str, Any], catalog: dict[str, Any], placement_model: dict[str, Any],
    project_dir: Path, *, max_rounds: int = 8, estimated_review_usd: float = 1.0,
) -> HeldoutFidelityReview:
    reconcile_repair_state(run)
    output, local_qc = render_evaluation_package(run, project_dir)
    metrics = {**metrics, "render": str(output), "local_qc": local_qc}
    if (0 <= run.accepted_review_index < len(run.reviews)
            and run.reviews[run.accepted_review_index].score_policy == "fresh_matrix_v2"):
        review = run.reviews[run.accepted_review_index]
    else:
        review = run_independent_blind_review(
            run, decisions, holdout, metrics, estimated_max_usd=estimated_review_usd,
        )
        run.accepted_review_index = len(run.reviews) - 1
        first_path = _write_json(
            motion_expert_run_dir(run.run_id) / "heldout_review_round_00.json",
            review.model_dump(mode="json"),
        )
        run.artifacts["heldout_review"] = str(first_path)
        save_motion_expert_run(run)
    while not review.passed and len(run.repair_iterations) < max_rounds:
        # Refuse the paid request before changing the accepted package.
        run.budget.reserve(estimated_review_usd)
        before = review
        accepted_review_path = run.artifacts.get("heldout_review")
        decisions, metrics, iteration = apply_targeted_repair(
            run, before, catalog, placement_model,
        )
        output, local_qc = render_evaluation_package(run, project_dir)
        metrics = {**metrics, "render": str(output), "local_qc": local_qc}
        raw_after = run_independent_blind_review(
            run, decisions, holdout, metrics, estimated_max_usd=estimated_review_usd,
        )
        iteration["raw_after_scores"] = [score.model_dump(mode="json") for score in raw_after.segment_scores]
        after = scope_post_repair_review(before, raw_after, iteration)
        run.reviews[-1] = after
        review_path = _write_json(
            motion_expert_run_dir(run.run_id) / f"heldout_review_round_{iteration['round']:02d}.json",
            after.model_dump(mode="json"),
        )
        run.artifacts["latest_attempt_review"] = str(review_path)
        accepted = finalize_or_revert_repair(run, before, after)
        if accepted:
            run.artifacts["heldout_review"] = str(review_path)
            run.accepted_review_index = len(run.reviews) - 1
            review = after
        else:
            if accepted_review_path:
                run.artifacts["heldout_review"] = accepted_review_path
            else:
                run.artifacts.pop("heldout_review", None)
            review = before
        save_motion_expert_run(run)
    return review


def _record_milestone(run: MotionExpertRun, name: str, artifact: str, details: dict[str, Any] | None = None) -> None:
    if name not in MOTION_EXPERT_MILESTONES:
        raise ValueError(f"unsupported motion expert milestone: {name}")
    if any(item.get("name") == name for item in run.milestones):
        return
    event = {
        "name": name, "at": datetime.now(timezone.utc).isoformat(), "artifact": artifact,
        "details": details or {}, "openrouter_spend_usd": round(run.budget.spent_usd, 6),
    }
    run.milestones.append(event)
    progress = Path(__file__).resolve().parent.parent / "progress.md"
    existing = progress.read_text(encoding="utf-8") if progress.is_file() else "# Channel Fidelity Progress\n"
    heading = {
        "pattern_library_complete": "AI LABS pattern library complete",
        "placement_model_v1_built": "AI LABS placement model v1 built",
        "first_generated_test_segment": "First AI LABS motion test segment generated",
        "first_heldout_pass_clearing_threshold": "First AI LABS held-out pass clearing threshold",
    }[name]
    marker = f"## {heading}"
    if marker not in existing:
        block = f"\n{marker}\n\n- Run: `{run.run_id}`\n- Artifact: `{artifact}`\n- OpenRouter spend: `${run.budget.spent_usd:.4f}`\n"
        progress.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return path


def _hydrate_references(entries: list[dict[str, Any]], count: int) -> list[ReferenceVideo]:
    records: list[ReferenceVideo] = []
    for entry in entries:
        video_id = str(entry.get("id") or "")
        cached = _read_cached_reference("ai_labs", video_id)
        if cached and _eligible_reference(cached):
            records.append(cached)
            continue
        if len(records) >= count + 12:
            break
        metadata = _hydrate(f"https://www.youtube.com/watch?v={video_id}")
        record = _reference_from_metadata(metadata, AI_LABS_CHANNEL, AI_LABS_MOTION_DATA_DIR / "_caption_cache")
        if record:
            record.listing_sha256 = _listing_sha256(entry)
            _write_cached_reference("ai_labs", record)
            records.append(record)
    return records


def build_motion_reference_corpus(
    run: MotionExpertRun, *, count: int = AI_LABS_MOTION_CORPUS_SIZE,
    should_cancel: Callable[[], bool] | None = None, report_progress: Callable[[int], None] | None = None,
) -> tuple[list[ReferenceVideo], list[ReferenceVideo]]:
    run.status = "verifying_channel"
    save_motion_expert_run(run)
    snapshot, entries = fetch_channel_listing(max(90, count + 24))
    run.channel_snapshot = snapshot
    if should_cancel and should_cancel():
        raise InterruptedError("motion expert corpus build canceled")
    records = _hydrate_references(entries, count)
    selected = select_motion_reference_videos(records, count=count)
    training, holdout, split_hash = stratified_train_holdout_split(selected)
    assert_holdout_isolation([item.video_id for item in training], [item.video_id for item in holdout])
    run.training_ids = [item.video_id for item in training]
    run.holdout_ids = [item.video_id for item in holdout]
    run.split_hash = split_hash
    run.status = "extracting_training_observations"
    save_motion_expert_run(run)
    # Keep holdout extraction physically separate and never attach it to the training artifact.
    pending = [
        record for record in training
        if not record.analysis_frame_strip or not Path(record.analysis_frame_strip).is_file()
    ]
    completed = len(training) - len(pending)
    if report_progress:
        report_progress(10 + round(35 * completed / max(1, len(training))))
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(pending))), thread_name_prefix="ai-labs-frames") as pool:
        futures = {pool.submit(_extract_public_frame_strip, record, "ai_labs"): record for record in pending}
        for future in as_completed(futures):
            if should_cancel and should_cancel():
                for remaining in futures:
                    remaining.cancel()
                raise InterruptedError("motion expert observation extraction canceled")
            record = futures[future]
            try:
                record.analysis_frame_strip = future.result()
                if record.analysis_frame_strip:
                    _write_cached_reference("ai_labs", record)
            except Exception:
                record.analysis_frame_strip = ""
            completed += 1
            if report_progress:
                report_progress(10 + round(35 * completed / max(1, len(training))))
    holdout_root = motion_expert_run_dir(run.run_id) / "_sealed_holdout"
    holdout_manifest = {
        "schema_version": "1.0", "split_hash": split_hash,
        "videos": [item.model_dump(mode="json") for item in holdout],
    }
    _write_json(holdout_root / "manifest.json", holdout_manifest)
    corpus = {
        "schema_version": "2.0", "channel": snapshot, "split_hash": split_hash,
        "training": [item.model_dump(mode="json") for item in training],
        "holdout": {"count": len(holdout), "sealed_manifest": str(holdout_root / "manifest.json")},
    }
    assert_holdout_isolation(run.training_ids, run.holdout_ids, corpus["training"])
    corpus_path = _write_json(motion_expert_run_dir(run.run_id) / "reference_corpus.json", corpus)
    run.corpus_path = str(corpus_path)
    run.corpus_hash = _sha(corpus)
    run.artifacts["reference_corpus"] = str(corpus_path)
    save_motion_expert_run(run)
    return training, holdout


def _evaluation_segments() -> list[dict[str, Any]]:
    return [
        {"id": "hook", "text": "What if the biggest AI upgrade this week is not a new model, but a smaller change that saves an hour every day?", "start_seconds": 0, "end_seconds": 8},
        {"id": "source", "text": "According to the product announcement, the workflow now keeps the source and result in the same view.", "start_seconds": 8, "end_seconds": 17, "source_visual_available": True, "evidence_ids": ["source_1"]},
        {"id": "mechanism", "text": "Under the hood, the request flows through planning, tool use, and a verification pass before the result comes back.", "start_seconds": 17, "end_seconds": 28},
        {"id": "comparison", "text": "Compared with the old workflow, the new one is faster on setup while the manual route still gives you more control.", "start_seconds": 28, "end_seconds": 39, "evidence_ids": ["source_2"]},
        {"id": "list", "text": "There are three practical checks: accuracy, repeatability, and whether the result is actually easier to edit.", "start_seconds": 39, "end_seconds": 50},
        {"id": "conclusion", "text": "So the takeaway is simple: use the automation for repeatable work, then keep the final judgment human.", "start_seconds": 50, "end_seconds": 60},
    ]


def write_evaluation_package(
    run: MotionExpertRun, catalog: dict[str, Any], placement_model: dict[str, Any],
    repair_override: dict[str, Any] | None = None,
) -> tuple[Path, list[PlacementDecision], dict[str, Any]]:
    project_dir = motion_expert_run_dir(run.run_id) / "evaluation_60s"
    decisions = plan_graphic_placements(_evaluation_segments(), catalog, placement_model)
    repair_override = repair_override or {}
    raw_repairs = list(repair_override.get("repairs") or [])
    if not raw_repairs and repair_override.get("axis"):
        raw_repairs = [repair_override]
    normalized_repairs: list[dict[str, Any]] = []
    for override in raw_repairs:
        target_segment = str(override.get("segment_id") or "")
        if target_segment.startswith("segment_"):
            try:
                target_index = int(target_segment.rsplit("_", 1)[1]) - 1
                target_segment = decisions[target_index].segment_id
            except (ValueError, IndexError):
                target_segment = ""
        normalized = {**override, "segment_id": target_segment}
        normalized_repairs.append(normalized)
        if normalized.get("axis") == "placement" and target_segment:
            for index, decision in enumerate(decisions):
                if decision.segment_id != target_segment or decision.decision != "graphic":
                    continue
                revised_duration = min(8.5, max(4.0, decision.end_seconds - decision.start_seconds + 0.5))
                decisions[index] = decision.model_copy(update={
                    "end_seconds": min(60.0, decision.start_seconds + revised_duration),
                    "reasons": decision.reasons + ["targeted held-out placement repair"],
                })
    active = [item for item in decisions if item.decision == "graphic"]
    metrics = {
        "resolution": [1920, 1080], "duration_seconds": 60, "camera": "locked",
        "graphics_per_minute": len(active), "unique_patterns": len({item.pattern_id for item in active}),
        "repeated_adjacent_families": 0,
        "mean_graphic_duration": round(sum(item.end_seconds - item.start_seconds for item in active) / max(1, len(active)), 3),
    }
    _write_json(project_dir / "placements.json", [item.model_dump(mode="json") for item in decisions])
    _write_json(project_dir / "evaluation_metrics.json", metrics)
    # This is an original HyperFrames authoring package. The renderer owns timing;
    # the DOM only expresses the measured grammar and placement decisions.
    normalized_override = {"repairs": normalized_repairs}
    html = _evaluation_html(decisions, normalized_override)
    composition = project_dir / "index.html"
    composition.write_text(html, encoding="utf-8")
    refined_hook = any(
        item.get("axis") == "visual"
        and item.get("dimension") == "typography"
        and item.get("segment_id") == "hook"
        for item in normalized_repairs
    )
    hook_title_selector = "#scene-hook #hook-title-refined" if refined_hook else "#scene-hook #hook-title-default"
    _write_json(project_dir / "index.motion.json", {
        "duration": 60,
        "assertions": [
            {"kind": "appearsBy", "selector": hook_title_selector, "bySec": 1.2},
            {"kind": "before", "a": "#scene-hook .eyebrow", "b": "#scene-hook .hook-copy p"},
            {"kind": "staysInFrame", "selector": hook_title_selector},
            {"kind": "staysInFrame", "selector": "#scene-source .focus-line"},
            {"kind": "staysInFrame", "selector": "#scene-mechanism h2"},
            {"kind": "staysInFrame", "selector": "#scene-comparison h2"},
            {"kind": "staysInFrame", "selector": "#scene-list h2"},
            {"kind": "staysInFrame", "selector": "#scene-conclusion h1"},
        ],
    })
    _write_json(project_dir / "hyperframes.json", {
        "version": 1, "name": "ai-labs-motion-expert-evaluation", "width": 1920,
        "height": 1080, "fps": 30, "entry": "index.html",
    })
    _write_json(project_dir / "repair_override.json", normalized_override)
    (project_dir / "BRIEF.md").write_text(
        "# AI LABS motion expert evaluation\n\nOriginal 60-second deterministic graphics test. "
        "No reference artwork or footage is included.\n",
        encoding="utf-8",
    )
    run.artifacts["evaluation_package"] = str(project_dir)
    save_motion_expert_run(run)
    return project_dir, decisions, metrics


def _evaluation_html(
    decisions: list[PlacementDecision], repair_override: dict[str, Any] | None = None,
) -> str:
    scene_markup = []
    palette = ["#F2F1ED", "#C8CEC9", "#4A4F4B", "#121513", "#D97757", "#78A6C8", "#78927D"]
    markup = {
        "hook": '''<div class="hook-copy"><div class="eyebrow">THE USEFUL UPGRADE</div><h1 id="hook-title-default" class="hook-title-default">IT ISN'T<br>THE MODEL.</h1><h1 id="hook-title-refined" class="hook-title-refined">It isn't<br><em>the model.</em></h1><p>A smaller workflow change can save the most time.</p><div class="hook-logic"><span>MODEL</span><i></i><strong>WORKFLOW</strong></div></div><div class="hook-meter"><span>MODEL</span><div class="meter-track"><i></i></div><span>WORKFLOW</span></div><div class="workflow-console"><div class="console-top"><span>WORKFLOW MAP</span><b>REVIEW / 04</b></div><div class="console-body"><div class="request-card"><small>REQUEST</small><strong>One useful task</strong><p>Keep the goal visible.</p></div><div class="console-route"><i></i></div><div class="console-steps"><div class="console-step active"><b>01</b><span>PLAN</span><i></i></div><div class="console-step"><b>02</b><span>ACT</span><i></i></div><div class="console-step verified"><b>03</b><span>VERIFY</span><i></i></div></div><div class="result-card"><small>RESULT</small><strong>Ready to review</strong><div class="result-lines"><i></i><i></i><i></i></div></div></div></div>''',
        "source": '''<div class="source-grid"><article class="document"><div class="doc-kicker">PRODUCT NOTE</div><div class="doc-line l1"></div><div class="doc-line l2"></div><div class="doc-line l3"></div><div class="focus-line">SOURCE AND RESULT<br>IN THE SAME VIEW</div><div class="doc-line l4"></div></article><div class="source-arrow">→</div><div class="result-panel"><span>RESULT</span><strong>LESS<br>CONTEXT<br>SWITCHING</strong><i></i></div></div>''',
        "mechanism": '''<div class="scene-head"><div class="eyebrow">HOW IT WORKS</div><h2>ONE REQUEST.<br>THREE ACCOUNTABLE STATES.</h2></div><div class="flow"><div class="flow-node"><b>01</b><strong>PLAN</strong><span>Define the task</span></div><div class="flow-link"><i></i></div><div class="flow-node"><b>02</b><strong>ACT</strong><span>Use the tool</span></div><div class="flow-link"><i></i></div><div class="flow-node verified"><b>03</b><strong>VERIFY</strong><span>Check the result</span></div></div>''',
        "comparison": '''<div class="scene-head compact"><div class="eyebrow">THE REAL TRADEOFF</div><h2>SPEED OR CONTROL?</h2></div><div class="compare-grid"><div class="compare-panel speed"><span>AUTOMATION</span><strong>FASTER<br>SETUP</strong><div class="bar"><i></i></div><small>Repeatable work</small></div><div class="compare-vs">/</div><div class="compare-panel control"><span>MANUAL</span><strong>MORE<br>CONTROL</strong><div class="bar"><i></i></div><small>Edge cases</small></div></div>''',
        "list": '''<div class="scene-head compact"><div class="eyebrow">BEFORE YOU TRUST IT</div><h2>THREE PRACTICAL CHECKS</h2></div><div class="check-list"><div class="check-row"><b>01</b><strong>ACCURATE</strong><span>Does the result match the evidence?</span><i>✓</i></div><div class="check-row"><b>02</b><strong>REPEATABLE</strong><span>Can it work twice without improvising?</span><i>✓</i></div><div class="check-row"><b>03</b><strong>EDITABLE</strong><span>Can a person fix the final ten percent?</span><i>✓</i></div></div><div class="validation-console"><div class="validation-top"><span>WORKFLOW REVIEW</span><b>3 CHECKS</b></div><div class="validation-body"><aside><small>SEQUENCE</small><strong>01—03</strong><div class="validation-axis"><i></i><i></i><i></i></div><p>Read the result like a process, not a demo.</p></aside><div class="validation-stack"><div class="validation-row"><b>01</b><div><strong>Accurate</strong><span>Does it match the evidence?</span></div><i>CHECK</i></div><div class="validation-row"><b>02</b><div><strong>Repeatable</strong><span>Can it work twice?</span></div><i>CHECK</i></div><div class="validation-row"><b>03</b><div><strong>Editable</strong><span>Can a person finish it?</span></div><i>CHECK</i></div></div></div></div>''',
        "conclusion": '''<div class="conclusion-copy"><div class="eyebrow">THE TAKEAWAY</div><h1>AUTOMATE<br>THE REPEATABLE.</h1><div class="conclusion-rule"><i></i></div><p>Keep the judgment human.</p></div>''',
    }
    repair_override = repair_override or {}
    repair_items = list(repair_override.get("repairs") or [])
    if not repair_items and repair_override.get("axis"):
        repair_items = [repair_override]
    for index, item in enumerate(decisions):
        next_start = decisions[index + 1].start_seconds if index + 1 < len(decisions) else 60.0
        duration = round(max(0.2, next_start - item.start_seconds), 3)
        visual_repairs = [
            str(override.get("dimension") or "hierarchy")
            for override in repair_items
            if item.segment_id == override.get("segment_id") and override.get("axis") == "visual"
        ]
        repair_kind = ",".join(visual_repairs)
        repair_class = ""
        if visual_repairs:
            counts = Counter(visual_repairs)
            variants = [f"repair-{kind}-v2" for kind, count in counts.items() if count >= 2]
            repair_class = " repair-visual " + " ".join(
                [*(f"repair-{kind}" for kind in sorted(counts)), *variants]
            )
        scene_markup.append(
            f'<section id="scene-{item.segment_id}" class="clip scene {item.segment_id}{repair_class}" '
            f'data-repair="{repair_kind}" data-start="{item.start_seconds}" '
            f'data-duration="{duration}" data-track-index="{index}">{markup[item.segment_id]}</section>'
        )
    template = '''<!doctype html>
<html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:{palette[3]};font-family:Inter,Arial,sans-serif}}
#motion-expert-evaluation{{position:relative;width:1920px;height:1080px;background:{palette[3]};color:{palette[0]};overflow:hidden}}
.scene{{position:absolute;inset:0;box-sizing:border-box;padding:112px 148px 124px;background:{palette[3]};overflow:hidden}}
.scene.repair-typography h1,.scene.repair-typography h2{{letter-spacing:-.035em;line-height:.94}}
.hook-title-refined,.workflow-console,.validation-console,.hook-logic{{display:none}}
.scene.hook.repair-typography{{background:#0E1210}}
.scene.hook.repair-typography .hook-copy{{top:154px;width:710px}}
.scene.hook.repair-typography .hook-title-default{{display:none}}
.scene.hook.repair-typography .hook-title-refined{{display:block;font-size:104px;line-height:.9;letter-spacing:-.058em;text-transform:none}}
.scene.hook.repair-typography .hook-title-refined em{{font-family:Georgia,'Times New Roman',serif;font-weight:400;color:{palette[1]}}}
.scene.hook.repair-typography .hook-copy p{{max-width:650px;font-size:31px}}
.scene.hook.repair-typography .hook-meter{{display:none}}
.scene.hook.repair-typography .workflow-console{{display:block;position:absolute;right:116px;top:144px;width:760px;height:724px;border:2px solid #3B4540;background:#151A17;box-sizing:border-box;box-shadow:0 28px 80px rgba(0,0,0,.24)}}
.scene.hook.repair-typography-v2 .hook-title-refined em{{font-family:Inter,Arial,sans-serif;font-style:normal;font-weight:780;color:{palette[0]}}}.scene.hook.repair-typography-v2 .hook-copy p{{margin-top:30px}}.scene.hook.repair-typography-v2 .hook-logic{{display:grid;grid-template-columns:auto 110px auto;align-items:center;gap:16px;width:420px;margin-top:54px;font-size:17px;letter-spacing:.14em;color:{palette[1]}}.scene.hook.repair-typography-v2 .hook-logic i{{height:2px;background:{palette[4]}}}.scene.hook.repair-typography-v2 .hook-logic strong{{font-size:18px;color:{palette[6]}}}
.console-top{{height:74px;border-bottom:2px solid #3B4540;display:flex;align-items:center;justify-content:space-between;padding:0 30px;box-sizing:border-box;font-size:18px;letter-spacing:.15em;color:{palette[1]}}}.console-top b{{font-size:17px;font-weight:600;color:{palette[6]}}}
.console-body{{position:relative;height:650px;padding:42px 42px 40px;box-sizing:border-box;display:grid;grid-template-columns:245px 94px 1fr;grid-template-rows:1fr 180px;gap:34px 0}}.request-card{{grid-column:1;grid-row:1;border:2px solid #3B4540;padding:28px 26px;align-self:start;box-sizing:border-box;background:#101411}}.request-card small,.result-card small{{display:block;font-size:17px;letter-spacing:.16em;color:{palette[4]};margin-bottom:18px}}.request-card strong,.result-card strong{{display:block;font-size:31px;line-height:1.05}}.request-card p{{font-size:22px!important;line-height:1.3;margin-top:48px!important;color:{palette[1]}}}
.console-route{{grid-column:2;grid-row:1;align-self:start;margin-top:72px;height:2px;background:#3B4540;overflow:hidden}}.console-route i{{display:block;width:100%;height:100%;background:{palette[4]}}}.console-steps{{grid-column:3;grid-row:1;display:flex;flex-direction:column;gap:14px}}.console-step{{height:82px;border:2px solid #3B4540;display:grid;grid-template-columns:48px 1fr 38px;align-items:center;padding:0 20px;box-sizing:border-box;background:#101411}}.console-step b{{font-size:16px;color:{palette[1]}}}.console-step span{{font-size:24px;font-weight:720;letter-spacing:.04em}}.console-step i{{width:14px;height:14px;border:2px solid #59645E;box-sizing:border-box}}.console-step.active{{border-color:{palette[5]}}}.console-step.active i{{background:{palette[5]};border-color:{palette[5]}}}.console-step.verified{{border-color:{palette[6]}}}.console-step.verified i{{background:{palette[6]};border-color:{palette[6]}}}
.result-card{{grid-column:1/4;grid-row:2;border-top:2px solid #3B4540;padding:28px 0 0;display:grid;grid-template-columns:160px 260px 1fr;align-items:start}}.result-card small{{margin:7px 0 0}}.result-lines{{display:flex;flex-direction:column;gap:14px;padding-top:8px}}.result-lines i{{height:10px;background:#5A645F;display:block;transform-origin:left}}.result-lines i:nth-child(2){{width:78%;background:{palette[5]}}}.result-lines i:nth-child(3){{width:54%;background:{palette[6]}}}
.scene.list.repair-hierarchy .scene-head{{top:84px;max-width:900px}}.scene.list.repair-hierarchy .scene-head h2{{font-size:62px;line-height:.94}}.scene.list.repair-hierarchy .check-list{{display:none}}.scene.list.repair-hierarchy .validation-console{{display:block;position:absolute;left:148px;right:148px;top:306px;bottom:92px;border:2px solid #3B4540;background:#151A17}}.validation-top{{height:68px;border-bottom:2px solid #3B4540;padding:0 30px;display:flex;align-items:center;justify-content:space-between;box-sizing:border-box;font-size:18px;letter-spacing:.15em;color:{palette[1]}}}.validation-top b{{font-size:17px;color:{palette[6]};font-weight:650}}.validation-body{{height:calc(100% - 68px);display:grid;grid-template-columns:320px 1fr}}.validation-body aside{{border-right:2px solid #3B4540;padding:42px 34px;box-sizing:border-box;position:relative}}.validation-body aside small{{display:block;font-size:17px;letter-spacing:.16em;color:{palette[4]}}}.validation-body aside strong{{display:block;font-size:42px;margin-top:14px}}.validation-body aside p{{position:absolute;left:34px;right:34px;bottom:38px;font-size:24px;line-height:1.3;color:{palette[1]}}.validation-axis{{display:flex;align-items:center;gap:0;margin-top:42px}}.validation-axis i{{height:12px;flex:1;background:#4B5550;border-right:5px solid #151A17}}.validation-axis i:nth-child(2){{background:{palette[5]}}}.validation-axis i:nth-child(3){{background:{palette[6]};border-right:0}}.validation-stack{{display:flex;flex-direction:column}}.validation-row{{flex:1;display:grid;grid-template-columns:70px 1fr 100px;align-items:center;padding:0 38px;border-bottom:2px solid #303833;box-sizing:border-box}}.validation-row:last-child{{border-bottom:0}}.validation-row>b{{font-size:19px;color:{palette[4]}}}.validation-row strong{{display:block;font-size:36px;line-height:1.05;text-transform:none}}.validation-row span{{display:block;font-size:24px;color:{palette[1]};margin-top:8px}}.validation-row>i{{font-size:17px;letter-spacing:.12em;font-style:normal;color:{palette[6]};text-align:right}}
.scene.repair-color{{background:#171B19}}
.scene.repair-hierarchy h1,.scene.repair-hierarchy h2{{max-width:1180px}}
.scene.repair-layout{{padding-left:172px;padding-right:172px}}
.scene.repair-density p,.scene.repair-density span{{max-width:760px}}
.eyebrow{{font-size:23px;font-weight:650;letter-spacing:.18em;color:{palette[1]};margin-bottom:26px}}h1,h2,p{{margin:0}}h1{{font-size:112px;line-height:.9;letter-spacing:-.055em;font-weight:780}}h2{{font-size:76px;line-height:.96;letter-spacing:-.045em;font-weight:760}}p{{font-size:34px;line-height:1.34;color:{palette[1]}}}.scene-head{{position:absolute;left:148px;top:132px;max-width:850px}}.scene-head.compact h2{{font-size:68px}}
.hook-copy{{position:absolute;left:148px;top:180px}}.hook-copy p{{margin-top:38px;max-width:720px}}.hook-meter{{position:absolute;right:150px;top:235px;width:430px;height:470px;display:flex;flex-direction:column;justify-content:center;gap:28px;color:{palette[1]};font-size:23px;letter-spacing:.14em}}.meter-track{{width:100%;height:320px;background:{palette[2]};position:relative;overflow:hidden}}.meter-track i{{position:absolute;left:0;right:0;bottom:0;height:18%;background:{palette[5]}}}
.source-grid{{height:100%;display:grid;grid-template-columns:1.15fr 120px .85fr;align-items:center;gap:42px}}.document{{height:700px;background:{palette[0]};color:{palette[3]};padding:64px 72px;box-sizing:border-box;position:relative}}.doc-kicker{{font-size:20px;letter-spacing:.18em;color:{palette[2]};margin-bottom:52px}}.doc-line{{height:14px;background:{palette[1]};margin:22px 0}}.doc-line.l1{{width:88%}}.doc-line.l2{{width:72%}}.doc-line.l3{{width:80%}}.doc-line.l4{{width:58%}}.focus-line{{border-left:8px solid {palette[4]};padding:20px 0 20px 30px;margin:54px 0;font-size:42px;font-weight:760;line-height:1.08}}.source-arrow{{font-size:82px;color:{palette[4]};text-align:center}}.result-panel{{height:520px;border:2px solid {palette[2]};padding:56px;box-sizing:border-box;position:relative}}.result-panel span,.compare-panel span{{font-size:20px;letter-spacing:.16em;color:{palette[1]}}}.result-panel strong{{display:block;font-size:62px;line-height:.98;margin-top:34px}}.result-panel i{{position:absolute;left:56px;bottom:56px;width:180px;height:10px;background:{palette[6]}}}
.flow{{position:absolute;left:148px;right:148px;bottom:150px;display:grid;grid-template-columns:1fr 150px 1fr 150px 1fr;align-items:center}}.flow-node{{border-top:2px solid {palette[2]};padding-top:28px;min-height:185px}}.flow-node b{{display:block;font-size:22px;color:{palette[4]};margin-bottom:18px}}.flow-node strong{{font-size:52px}}.flow-node span{{display:block;font-size:25px;color:{palette[1]};margin-top:13px}}.flow-node.verified{{border-color:{palette[6]}}}.flow-link{{height:2px;background:{palette[2]};overflow:hidden}}.flow-link i{{display:block;width:100%;height:100%;background:{palette[5]}}}
.compare-grid{{position:absolute;left:148px;right:148px;bottom:115px;display:grid;grid-template-columns:1fr 90px 1fr;align-items:center}}.compare-panel{{height:470px;border-top:2px solid {palette[2]};padding:42px 46px;box-sizing:border-box;background:#171A19}}.compare-panel strong{{display:block;font-size:70px;line-height:.94;margin:30px 0 55px}}.compare-panel small{{display:block;font-size:24px;color:{palette[1]};margin-top:18px}}.compare-vs{{font-size:76px;text-align:center;color:{palette[1]}}.bar{{height:12px;background:{palette[2]};overflow:hidden}}.bar i{{display:block;height:100%;background:{palette[5]};width:82%}}.control .bar i{{background:{palette[6]};width:66%}}
.check-list{{position:absolute;left:148px;right:148px;bottom:105px}}.check-row{{display:grid;grid-template-columns:90px 390px 1fr 70px;align-items:center;border-top:1px solid {palette[2]};min-height:142px}}.check-row b{{font-size:22px;color:{palette[4]}}}.check-row strong{{font-size:42px}}.check-row span{{font-size:27px;color:{palette[1]}}}.check-row i{{font-size:38px;font-style:normal;color:{palette[6]};text-align:right}}
.conclusion-copy{{position:absolute;left:148px;top:175px}}.conclusion-rule{{width:980px;height:3px;background:{palette[2]};margin:52px 0 35px;overflow:hidden}}.conclusion-rule i{{display:block;height:100%;width:100%;background:{palette[5]}}}.conclusion-copy p{{font-size:42px}}
</style></head><body><main id="motion-expert-evaluation" data-composition-id="motion-expert-evaluation" data-width="1920" data-height="1080" data-fps="30" data-duration="60">{''.join(scene_markup)}</main>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/gsap.min.js"></script>
<script>
const tl=gsap.timeline({{paused:true}});
document.querySelectorAll('.scene').forEach((scene)=>{{
 const start=Number(scene.dataset.start); const duration=Number(scene.dataset.duration);
 const repairs=(scene.dataset.repair||'').split(',').filter(Boolean); const entrance=repairs.includes('motion_curve')?.44:.58; const entranceEase=repairs.includes('motion_curve')?'power2.inOut':'power3.out';
 const eyebrow=scene.querySelector('.eyebrow'); const title=(scene.classList.contains('hook')&&scene.classList.contains('repair-typography'))?scene.querySelector('.hook-title-refined'):scene.querySelector('h1,h2'); const copy=scene.querySelector('.hook-copy p')||scene.querySelector('p');
 if(eyebrow) tl.fromTo(eyebrow,{{autoAlpha:0,y:10}},{{autoAlpha:1,y:0,duration:.34,ease:'power3.out'}},start+.16);
 if(title) tl.fromTo(title,{{autoAlpha:0,y:16}},{{autoAlpha:1,y:0,duration:entrance,ease:entranceEase}},start+.28);
 if(copy) tl.fromTo(copy,{{autoAlpha:0,y:10}},{{autoAlpha:1,y:0,duration:.42,ease:'power3.out'}},start+.62);
 if(scene.classList.contains('hook')&&scene.classList.contains('repair-typography')){{
   tl.fromTo(scene.querySelector('.workflow-console'),{{autoAlpha:0,x:26,scale:.985}},{{autoAlpha:1,x:0,scale:1,duration:.62,ease:'power3.out'}},start+.38)
     .fromTo(scene.querySelector('.console-route i'),{{scaleX:0,transformOrigin:'left'}},{{scaleX:1,duration:.46,ease:'power2.inOut'}},start+.88)
     .fromTo(scene.querySelectorAll('.console-step'),{{autoAlpha:0,x:16}},{{autoAlpha:1,x:0,duration:.36,stagger:.18,ease:'power3.out'}},start+.94)
     .fromTo(scene.querySelectorAll('.result-lines i'),{{scaleX:0}},{{scaleX:1,duration:.42,stagger:.12,ease:'power2.out'}},start+1.62);
   if(scene.classList.contains('repair-typography-v2')) tl.fromTo(scene.querySelector('.hook-logic i'),{{scaleX:0}},{{scaleX:1,duration:.46,ease:'power2.inOut'}},start+1.36);
 }} else if(scene.classList.contains('hook')) tl.fromTo(scene.querySelector('.meter-track i'),{{scaleY:.05,transformOrigin:'bottom'}},{{scaleY:1,duration:1.4,ease:'power3.out'}},start+.72);
 if(scene.classList.contains('source')){{
   tl.fromTo(scene.querySelector('.document'),{{autoAlpha:0,x:-14}},{{autoAlpha:1,x:0,duration:.55,ease:'power3.out'}},start+.16)
     .fromTo(scene.querySelectorAll('.doc-line'),{{scaleX:.1,transformOrigin:'left'}},{{scaleX:1,duration:.34,stagger:.12,ease:'power2.out'}},start+.55)
     .fromTo(scene.querySelector('.focus-line'),{{autoAlpha:0,x:-10}},{{autoAlpha:1,x:0,duration:.42,ease:'power3.out'}},start+1.12)
     .fromTo(scene.querySelector('.source-arrow'),{{autoAlpha:0,x:-12}},{{autoAlpha:1,x:0,duration:.34,ease:'power2.out'}},start+1.55)
     .fromTo(scene.querySelector('.result-panel'),{{autoAlpha:0,x:14}},{{autoAlpha:1,x:0,duration:.52,ease:'power3.out'}},start+1.7);
 }}
 if(scene.classList.contains('mechanism')){{
   tl.fromTo(scene.querySelectorAll('.flow-node'),{{autoAlpha:0,y:14}},{{autoAlpha:1,y:0,duration:.42,stagger:.62,ease:'power3.out'}},start+.9)
     .fromTo(scene.querySelectorAll('.flow-link i'),{{scaleX:0,transformOrigin:'left'}},{{scaleX:1,duration:.48,stagger:.62,ease:'power2.inOut'}},start+1.35);
 }}
 if(scene.classList.contains('comparison')){{
   tl.fromTo(scene.querySelectorAll('.compare-panel'),{{autoAlpha:0,y:14}},{{autoAlpha:1,y:0,duration:.52,stagger:.28,ease:'power3.out'}},start+.78)
     .fromTo(scene.querySelectorAll('.bar i'),{{scaleX:0,transformOrigin:'left'}},{{scaleX:1,duration:.72,stagger:.2,ease:'power2.out'}},start+1.45);
 }}
 if(scene.classList.contains('list')&&scene.classList.contains('repair-hierarchy')){{
   tl.fromTo(scene.querySelector('.validation-console'),{{autoAlpha:0,y:18}},{{autoAlpha:1,y:0,duration:.52,ease:'power3.out'}},start+.72)
     .fromTo(scene.querySelectorAll('.validation-axis i'),{{scaleX:0,transformOrigin:'left'}},{{scaleX:1,duration:.34,stagger:.13,ease:'power2.inOut'}},start+1.1)
     .fromTo(scene.querySelectorAll('.validation-row'),{{autoAlpha:0,x:18}},{{autoAlpha:1,x:0,duration:.38,stagger:.24,ease:'power3.out'}},start+1.18);
 }} else if(scene.classList.contains('list')) tl.fromTo(scene.querySelectorAll('.check-row'),{{autoAlpha:0,y:12}},{{autoAlpha:1,y:0,duration:.42,stagger:.45,ease:'power3.out'}},start+.78);
 if(scene.classList.contains('conclusion')) tl.fromTo(scene.querySelector('.conclusion-rule i'),{{scaleX:0,transformOrigin:'left'}},{{scaleX:1,duration:.8,ease:'power3.out'}},start+.9);
}});
window.__timelines['motion-expert-evaluation']=tl; tl.seek(0);
</script></body></html>'''
    replacements = {
        "{''.join(scene_markup)}": "".join(scene_markup),
        **{f"{{palette[{index}]}}": color for index, color in enumerate(palette)},
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    return template.replace("{{", "{").replace("}}", "}")


def _parse_json_envelope(output: str) -> dict[str, Any]:
    for index, character in enumerate(output):
        if character != "{":
            continue
        try:
            return json.loads(output[index:])
        except json.JSONDecodeError:
            continue
    raise RuntimeError("command did not return a JSON envelope")


def inspect_evaluation_render(video: Path, snapshots_dir: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not video.is_file() or video.stat().st_size < 1024:
        return {"passed": False, "failures": ["render is missing or empty"]}
    if not ffprobe:
        return {"passed": False, "failures": ["ffprobe is unavailable"]}
    process = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries",
         "format=duration,size:stream=codec_name,width,height,r_frame_rate", "-of", "json", str(video)],
        capture_output=True, text=True, timeout=60,
    )
    metadata = json.loads(process.stdout or "{}")
    streams = metadata.get("streams") or []
    stream = streams[0] if streams else {}
    duration = float((metadata.get("format") or {}).get("duration") or 0)
    snapshot_paths = sorted(snapshots_dir.glob("frame-*.png")) if snapshots_dir.is_dir() else []
    visible_ratios: list[float] = []
    for path in snapshot_paths:
        with Image.open(path) as source:
            image = source.convert("RGB").resize((320, 180))
        background = image.getpixel((0, 0))
        different = sum(
            1 for pixel in image.get_flattened_data()
            if sum(abs(int(pixel[channel]) - int(background[channel])) for channel in range(3)) > 18
        )
        visible_ratios.append(round(different / (image.width * image.height), 4))
    failures = []
    if stream.get("codec_name") != "h264":
        failures.append("video codec is not H.264")
    if [stream.get("width"), stream.get("height")] != [1920, 1080]:
        failures.append("render is not exactly 1920x1080")
    if abs(duration - 60.0) > 0.1:
        failures.append(f"render duration is {duration:.3f}s instead of 60s")
    if len(snapshot_paths) < 5:
        failures.append("fewer than five proof snapshots were produced")
    if visible_ratios and min(visible_ratios) < 0.01:
        failures.append("a proof snapshot is effectively blank")
    return {
        "passed": not failures,
        "failures": failures,
        "video": str(video),
        "duration_seconds": round(duration, 3),
        "codec": stream.get("codec_name", ""),
        "resolution": [stream.get("width", 0), stream.get("height", 0)],
        "fps": stream.get("r_frame_rate", ""),
        "size_bytes": int((metadata.get("format") or {}).get("size") or 0),
        "proof_snapshot_count": len(snapshot_paths),
        "proof_visible_ratios": visible_ratios,
    }


def render_evaluation_package(run: MotionExpertRun, project_dir: Path) -> tuple[Path, dict[str, Any]]:
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("HyperFrames render requires npx")
    composition_hash = hashlib.sha256((project_dir / "index.html").read_bytes()).hexdigest()[:10]
    output = project_dir / "renders" / f"ai_labs_motion_expert_60s_{composition_hash}.mp4"
    qc_path = project_dir / "local_qc.json"
    if output.is_file() and output.stat().st_size >= 1024 and qc_path.is_file():
        try:
            cached_qc = json.loads(qc_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cached_qc = {}
        cached_check = cached_qc.get("hyperframes_check") or {}
        if (
            cached_qc.get("passed") is True
            and Path(str(cached_qc.get("video") or "")) == output
            and int(cached_qc.get("proof_snapshot_count") or 0) >= 5
            and cached_check.get("ok") is True
        ):
            run.artifacts["evaluation_video"] = str(output)
            run.artifacts["local_qc"] = str(qc_path)
            save_motion_expert_run(run)
            return output, cached_qc
    check = subprocess.run(
        [npx, "hyperframes@0.8.26", "check", ".", "--json", "--snapshots", "--timeout", "30000"],
        cwd=project_dir, capture_output=True, text=True, timeout=300,
    )
    check_payload = _parse_json_envelope(check.stdout)
    if check.returncode or not check_payload.get("ok"):
        raise RuntimeError("HyperFrames check failed before render")
    if not output.is_file() or output.stat().st_size < 1024:
        output.parent.mkdir(parents=True, exist_ok=True)
        render = subprocess.run(
            [npx, "hyperframes@0.8.26", "render", ".", "--quality", "high",
             "--output", str(output), "--fps", "30", "--resolution", "1080p", "--strict"],
            cwd=project_dir, capture_output=True, text=True, timeout=900,
        )
        if render.returncode:
            raise RuntimeError(f"HyperFrames render failed: {(render.stderr or render.stdout)[-1000:]}")
    qc = inspect_evaluation_render(output, project_dir / "snapshots")
    qc["hyperframes_check"] = {
        "ok": check_payload.get("ok", False),
        "lint_errors": (check_payload.get("lint") or {}).get("errorCount", 0),
        "runtime_errors": (check_payload.get("runtime") or {}).get("errorCount", 0),
        "layout_errors": (check_payload.get("layout") or {}).get("errorCount", 0),
        "motion_errors": (check_payload.get("motion") or {}).get("errorCount", 0),
        "contrast_errors": (check_payload.get("contrast") or {}).get("errorCount", 0),
    }
    qc_path = _write_json(qc_path, qc)
    run.artifacts["evaluation_video"] = str(output)
    run.artifacts["local_qc"] = str(qc_path)
    for event in run.milestones:
        if event.get("name") == "first_generated_test_segment":
            event["artifact"] = str(output)
            event["details"] = {**event.get("details", {}), "local_qc_passed": qc["passed"]}
    save_motion_expert_run(run)
    if not qc["passed"]:
        raise RuntimeError(f"evaluation render failed local QC: {qc['failures']}")
    return output, qc


def build_ai_labs_motion_expert(
    payload: dict[str, Any], *, should_cancel: Callable[[], bool] | None = None,
    report_progress: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    run_id = str(payload.get("run_id") or f"ai_labs_motion_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}")
    run = load_motion_expert_run(run_id) if motion_expert_run_path(run_id).is_file() else MotionExpertRun(run_id=run_id)
    run.budget.cap_usd = min(OPENROUTER_CAP_USD, float(payload.get("openrouter_cap_usd") or OPENROUTER_CAP_USD))
    reconcile_repair_state(run)
    try:
        if not run.corpus_path or not Path(run.corpus_path).is_file():
            training, holdout = build_motion_reference_corpus(
                run, count=int(payload.get("corpus_size") or AI_LABS_MOTION_CORPUS_SIZE),
                should_cancel=should_cancel, report_progress=report_progress,
            )
        else:
            corpus = json.loads(Path(run.corpus_path).read_text(encoding="utf-8"))
            training = [ReferenceVideo.model_validate(item) for item in corpus["training"]]
            sealed = json.loads(Path(corpus["holdout"]["sealed_manifest"]).read_text(encoding="utf-8"))
            holdout = [ReferenceVideo.model_validate(item) for item in sealed["videos"]]
        assert_holdout_isolation(run.training_ids, run.holdout_ids)
        training = ensure_training_motion_traces(
            training, should_cancel=should_cancel, report_progress=report_progress,
        )
        if run.corpus_path and Path(run.corpus_path).is_file():
            corpus_payload = json.loads(Path(run.corpus_path).read_text(encoding="utf-8"))
            corpus_payload["training"] = [item.model_dump(mode="json") for item in training]
            assert_holdout_isolation(run.training_ids, run.holdout_ids, corpus_payload["training"])
            _write_json(Path(run.corpus_path), corpus_payload)
            run.corpus_hash = _sha(corpus_payload)
            save_motion_expert_run(run)
        rebuild_catalog = bool(payload.get("force_rebuild_catalog", False))
        if rebuild_catalog or not run.pattern_catalog_path or not Path(run.pattern_catalog_path).is_file():
            catalog = build_motion_pattern_catalog(training)
            assert_holdout_isolation(run.training_ids, run.holdout_ids, catalog)
            catalog_path = _write_json(AI_LABS_MOTION_PROFILE_PATH, catalog)
            run.pattern_catalog_path = str(catalog_path)
            run.pattern_catalog_hash = _sha(catalog)
            run.artifacts["pattern_catalog"] = str(catalog_path)
            _record_milestone(run, "pattern_library_complete", str(catalog_path), {"patterns": len(catalog["patterns"])})
        else:
            catalog = json.loads(Path(run.pattern_catalog_path).read_text(encoding="utf-8"))
        if rebuild_catalog or not run.placement_model_path or not Path(run.placement_model_path).is_file():
            placement_model = build_placement_model(catalog)
            placement_path = _write_json(motion_expert_run_dir(run_id) / "placement_model.json", placement_model)
            run.placement_model_path = str(placement_path)
            run.placement_model_hash = _sha(placement_model)
            run.artifacts["placement_model"] = str(placement_path)
            _record_milestone(run, "placement_model_v1_built", str(placement_path))
        else:
            placement_model = json.loads(Path(run.placement_model_path).read_text(encoding="utf-8"))
        project_dir, decisions, metrics = write_evaluation_package(
            run, catalog, placement_model, run.active_repair_override,
        )
        _record_milestone(run, "first_generated_test_segment", str(project_dir), metrics)
        if bool(payload.get("render", False)):
            output, local_qc = render_evaluation_package(run, project_dir)
            metrics["render"] = str(output)
            metrics["local_qc"] = local_qc
        if report_progress:
            report_progress(85)
        if not bool(payload.get("run_paid_review", True)):
            run.status = "awaiting_independent_review"
            run.stop_reason = "paid_review_disabled"
        elif not OPENROUTER_API_KEY:
            run.status = "awaiting_openrouter_credentials"
            run.stop_reason = "missing_openrouter_api_key"
        else:
            run.openrouter_snapshot = validate_openrouter_credential()
            save_motion_expert_run(run)
            review = run_paid_fidelity_repair_loop(
                run, decisions, holdout, metrics, catalog, placement_model, project_dir,
                max_rounds=max(1, int(payload.get("max_repair_rounds") or 8)),
                estimated_review_usd=min(2.0, max(0.25, float(payload.get("estimated_review_usd") or 1.0))),
            )
            review_path = Path(run.artifacts["heldout_review"])
            if review.passed:
                run.status = "perfect_fidelity"
                run.stop_reason = "perfect_fidelity"
                if run.errors:
                    run.resolved_errors.extend(error for error in run.errors if error not in run.resolved_errors)
                    run.errors.clear()
                _record_milestone(run, "first_heldout_pass_clearing_threshold", str(review_path), {
                    "mean_score": review.mean_score, "minimum_score": review.minimum_score,
                })
            else:
                run.status = "needs_targeted_repair"
                run.stop_reason = "repair_round_limit"
        save_motion_expert_run(run)
        return motion_expert_status(run)
    except InterruptedError:
        run.status = "canceled"
        run.stop_reason = "canceled"
        save_motion_expert_run(run)
        raise
    except OpenRouterCredentialError as exc:
        run.status = "awaiting_openrouter_credentials"
        run.stop_reason = "invalid_openrouter_api_key"
        run.errors.append(f"{type(exc).__name__}: {exc}")
        save_motion_expert_run(run)
        return motion_expert_status(run)
    except Exception as exc:
        run.status = "budget_limit" if "budget" in str(exc).casefold() else "blocked"
        run.stop_reason = "budget_limit" if run.status == "budget_limit" else "preflight_or_quality_gate"
        run.errors.append(f"{type(exc).__name__}: {exc}")
        save_motion_expert_run(run)
        return motion_expert_status(run)


def motion_expert_status(run: MotionExpertRun) -> dict[str, Any]:
    latest = (
        run.reviews[run.accepted_review_index]
        if run.reviews and 0 <= run.accepted_review_index < len(run.reviews)
        else run.reviews[-1] if run.reviews else None
    )
    requires_fresh_review = bool(latest and latest.score_policy != "fresh_matrix_v2")
    catalog_count = 0
    if run.pattern_catalog_path and Path(run.pattern_catalog_path).is_file():
        catalog_count = len(json.loads(Path(run.pattern_catalog_path).read_text(encoding="utf-8")).get("patterns", []))
    replicated_count = 0
    evaluation_path = Path(run.artifacts.get("evaluation_package") or "") / "evaluation_metrics.json"
    if evaluation_path.is_file():
        replicated_count = int(json.loads(evaluation_path.read_text(encoding="utf-8")).get("unique_patterns") or 0)
    return {
        "run_id": run.run_id,
        "status": "awaiting_independent_review" if requires_fresh_review else run.status,
        "stop_reason": "legacy_score_policy" if requires_fresh_review else run.stop_reason,
        "channel": run.channel_snapshot,
        "split": {
            "training_count": len(run.training_ids), "holdout_count": len(run.holdout_ids),
            "split_hash": run.split_hash, "isolated": not bool(set(run.training_ids) & set(run.holdout_ids)),
        },
        "catalog": {
            "pattern_count": catalog_count,
            "replicated_in_evaluation_count": replicated_count,
            "path": run.pattern_catalog_path,
        },
        "placement_model": {"path": run.placement_model_path, "hash": run.placement_model_hash},
        "fidelity": ({"mean": latest.mean_score, "minimum": latest.minimum_score,
                      "passed": latest.passed and not requires_fresh_review,
                      "score_policy": latest.score_policy,
                      "requires_fresh_review": requires_fresh_review} if latest else None),
        "budget": {**run.budget.model_dump(), "remaining_usd": round(run.budget.remaining_usd, 6)},
        "openrouter": run.openrouter_snapshot,
        "repair_iterations": run.repair_iterations,
        "milestones": run.milestones,
        "artifacts": run.artifacts,
        "errors": run.errors[-5:],
        "resolved_errors": run.resolved_errors[-5:],
        "remaining_work": (
            ["legacy scores require a fresh complete independent review"] if requires_fresh_review else
            [] if latest and latest.passed else
            ["run independent held-out review"] if not latest else
            ["repair the lowest held-out visual or placement dimension and rerun the evaluation package"]
        ),
    }
