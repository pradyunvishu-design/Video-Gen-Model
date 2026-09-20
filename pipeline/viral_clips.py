"""Discover timely podcast/keynote moments without downloading unapproved footage.

Discovery stores public metadata, caption-derived moment suggestions, and a rights
queue. Video bytes only enter the project through ``LicensedClipRequest`` after
an editor supplies an accepted rights basis and any required proof record.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, HttpUrl, model_validator

from .licensed_clips import LicensedClipRequest


ClipKind = Literal["podcast", "keynote", "interview", "launch", "demo", "talk", "other"]
RightsStatus = Literal[
    "research_only", "permission_requested", "approved", "rejected",
]

_SIGNAL_TERMS = {
    "announce", "announced", "launch", "launched", "release", "released",
    "new", "first", "benchmark", "model", "agent", "open source", "paper",
    "research", "million", "billion", "faster", "cheaper", "problem",
    "surprising", "actually", "here's why", "this means",
}
_LOW_VALUE_TERMS = {
    "subscribe", "sponsor", "sponsored", "discount code", "link in the description",
    "smash the like", "thanks for watching", "patreon",
}
_KIND_TERMS: dict[ClipKind, tuple[str, ...]] = {
    "podcast": ("podcast", "episode", "full conversation"),
    "keynote": ("keynote", "conference", "opening address", "developer day"),
    "interview": ("interview", "in conversation", "q&a", "fireside chat"),
    "launch": ("launch", "introducing", "announcement", "unveiling"),
    "demo": ("demo", "walkthrough", "hands-on", "in action"),
    "talk": ("talk", "lecture", "presentation", "session"),
    "other": (),
}


class ClipDiscoveryRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    queries: list[str] = Field(default_factory=list, max_length=20)
    channel_urls: list[HttpUrl] = Field(default_factory=list, max_length=20)
    topic_terms: list[str] = Field(default_factory=list, max_length=60)
    published_within_days: int = Field(default=30, ge=1, le=365)
    max_results_per_source: int = Field(default=12, ge=1, le=50)
    max_candidates: int = Field(default=30, ge=1, le=100)
    caption_candidate_count: int = Field(default=12, ge=0, le=30)
    min_duration_seconds: float = Field(default=60, ge=0)
    max_duration_seconds: float = Field(default=14_400, gt=0)

    @model_validator(mode="after")
    def require_a_discovery_source(self) -> "ClipDiscoveryRequest":
        if not self.queries and not self.channel_urls:
            raise ValueError("at least one search query or channel URL is required")
        if self.min_duration_seconds >= self.max_duration_seconds:
            raise ValueError("min_duration_seconds must be below max_duration_seconds")
        return self


class CaptionCue(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=1000)


class ClipMoment(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    score: float = Field(ge=0, le=100)
    transcript_excerpt: str = Field(default="", max_length=500)
    reason: str = Field(default="", max_length=500)
    requires_manual_timestamp_review: bool = False


class ClipCandidate(BaseModel):
    candidate_id: str
    video_id: str
    source_url: HttpUrl
    title: str
    channel: str = ""
    channel_id: str = ""
    upload_date: str = ""
    duration_seconds: float = 0
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    age_days: float = 0
    views_per_day: float = 0
    clip_kind: ClipKind = "other"
    viral_score: float = Field(ge=0, le=100)
    relevance_score: float = Field(ge=0, le=100)
    combined_score: float = Field(ge=0, le=100)
    license_name: str = ""
    rights_status: RightsStatus = "research_only"
    suggested_rights_basis: str = ""
    moments: list[ClipMoment] = Field(default_factory=list)
    caption_file: str = ""
    permission_contact_url: str = ""
    discovery_notes: list[str] = Field(default_factory=list)


class ClipApproval(BaseModel):
    rights_status: Literal["approved"]
    rights_basis: Literal["owned", "written_permission", "creative_commons", "public_domain"]
    rights_proof_file: str = ""
    rights_proof_url: str = ""
    approved_by: str = Field(min_length=2, max_length=120)
    attribution: str = Field(min_length=2, max_length=500)
    moment_index: int = Field(default=0, ge=0)
    keep_audio: bool = False
    source_id: str = ""
    avoid_faces: bool = False


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9+#.-]*", value.casefold()))


def classify_clip_kind(title: str, description: str = "") -> ClipKind:
    haystack = f"{title} {description}".casefold()
    scores = {
        kind: sum(1 for term in terms if term in haystack)
        for kind, terms in _KIND_TERMS.items() if kind != "other"
    }
    if not scores or max(scores.values()) == 0:
        return "other"
    return max(scores, key=scores.get)  # type: ignore[arg-type]


def _upload_datetime(metadata: dict) -> datetime | None:
    timestamp = metadata.get("timestamp") or metadata.get("release_timestamp")
    if timestamp:
        try:
            return datetime.fromtimestamp(float(timestamp), timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
    raw = str(metadata.get("upload_date") or metadata.get("release_date") or "")
    for pattern in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def score_video_metadata(
    metadata: dict, topic_terms: list[str], now: datetime | None = None,
) -> dict[str, float]:
    """Return explainable 0-100 momentum and relevance scores."""
    now = now or datetime.now(timezone.utc)
    uploaded = _upload_datetime(metadata)
    age_days = max(0.25, (now - uploaded).total_seconds() / 86_400) if uploaded else 30.0
    views = max(0, int(metadata.get("view_count") or 0))
    likes = max(0, int(metadata.get("like_count") or 0))
    comments = max(0, int(metadata.get("comment_count") or 0))
    views_per_day = views / age_days
    velocity = min(50.0, max(0.0, (math.log10(views_per_day + 1) - 1.0) * 12.5))
    recency = max(0.0, 30.0 * (1.0 - min(age_days, 45.0) / 45.0))
    engagement_rate = (likes + comments * 2) / max(views, 1)
    engagement = min(20.0, engagement_rate * 500.0)
    viral = min(100.0, velocity + recency + engagement)

    text = " ".join([
        str(metadata.get("title") or ""), str(metadata.get("description") or ""),
        " ".join(str(item) for item in (metadata.get("tags") or [])),
    ]).casefold()
    wanted = [term.casefold().strip() for term in topic_terms if term.strip()]
    exact_hits = sum(1 for term in wanted if term in text)
    relevance = min(100.0, exact_hits * 22.0 + (15.0 if any(term in text for term in _SIGNAL_TERMS) else 0.0))
    if not wanted:
        relevance = 50.0
    return {
        "age_days": round(age_days, 3),
        "views_per_day": round(views_per_day, 3),
        "viral_score": round(viral, 2),
        "relevance_score": round(relevance, 2),
    }


def _clean_caption_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", html.unescape(value))
    value = re.sub(r"\[[^]]{1,60}]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_vtt(path: Path) -> list[CaptionCue]:
    """Parse public WebVTT captions and collapse YouTube rolling duplicates."""
    time_pattern = re.compile(
        r"(?P<sh>\d{2}):(?P<sm>\d{2}):(?P<ss>\d{2}(?:\.\d+)?)\s+-->\s+"
        r"(?P<eh>\d{2}):(?P<em>\d{2}):(?P<es>\d{2}(?:\.\d+)?)"
    )
    blocks = re.split(r"\r?\n\s*\r?\n", path.read_text(encoding="utf-8", errors="ignore"))
    cues: list[CaptionCue] = []
    previous = ""
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        match = time_pattern.search(lines[timing_index])
        if not match:
            continue
        start = int(match["sh"]) * 3600 + int(match["sm"]) * 60 + float(match["ss"])
        end = int(match["eh"]) * 3600 + int(match["em"]) * 60 + float(match["es"])
        text = _clean_caption_text(" ".join(lines[timing_index + 1:]))
        if not text or text == previous:
            continue
        if previous and text.startswith(previous):
            text = text[len(previous):].strip()
        if text:
            cues.append(CaptionCue(start_seconds=start, end_seconds=end, text=text[:1000]))
            previous = _clean_caption_text(" ".join(lines[timing_index + 1:]))
    return cues


def rank_caption_moments(
    cues: list[CaptionCue], topic_terms: list[str], *, max_moments: int = 3,
    target_seconds: float = 24.0,
) -> list[ClipMoment]:
    """Find concise, quotable, non-overlapping windows in a public transcript."""
    if not cues:
        return []
    wanted = {term.casefold().strip() for term in topic_terms if term.strip()}
    windows: list[tuple[float, int, int, str]] = []
    for start_index, first in enumerate(cues):
        end_index = start_index
        while end_index + 1 < len(cues) and cues[end_index].end_seconds - first.start_seconds < target_seconds:
            end_index += 1
        duration = cues[end_index].end_seconds - first.start_seconds
        if duration < 8 or duration > 45:
            continue
        transcript = _clean_caption_text(" ".join(cue.text for cue in cues[start_index:end_index + 1]))
        lower = transcript.casefold()
        topic_hits = sum(1 for term in wanted if term in lower)
        signal_hits = sum(1 for term in _SIGNAL_TERMS if term in lower)
        penalty = sum(1 for term in _LOW_VALUE_TERMS if term in lower)
        word_count = len(transcript.split())
        clarity = 8.0 if 24 <= word_count <= 110 else 2.0
        score = min(100.0, 24.0 + topic_hits * 16.0 + signal_hits * 4.0 + clarity - penalty * 24.0)
        windows.append((score, start_index, end_index, transcript))
    selected: list[ClipMoment] = []
    spans: list[tuple[float, float]] = []
    for score, start_index, end_index, transcript in sorted(windows, reverse=True):
        start = cues[start_index].start_seconds
        end = cues[end_index].end_seconds
        if any(not (end <= prior_start or start >= prior_end) for prior_start, prior_end in spans):
            continue
        terms_found = [term for term in sorted(wanted) if term in transcript.casefold()][:4]
        reason = "Strong topic match"
        if terms_found:
            reason += ": " + ", ".join(terms_found)
        selected.append(ClipMoment(
            start_seconds=round(start, 3), end_seconds=round(end, 3), score=round(score, 2),
            transcript_excerpt=transcript[:500], reason=reason,
        ))
        spans.append((start, end))
        if len(selected) >= max_moments:
            break
    return selected


def _run_json(command: list[str], timeout: int = 240) -> dict:
    process = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if process.returncode:
        raise RuntimeError("yt-dlp discovery failed: " + "\n".join(process.stderr.splitlines()[-8:]))
    return json.loads(process.stdout)


def _discover_entries(target: str, max_results: int) -> list[dict]:
    source = target
    if not urlsplit(target).scheme:
        # Current yt-dlp builds support ytsearchN consistently; recency ordering
        # is handled by our own upload-date and views-per-day score below.
        source = f"ytsearch{max_results}:{target}"
    data = _run_json([
        sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs",
        "--flat-playlist", "--playlist-end", str(max_results), "--dump-single-json", source,
    ])
    return [entry for entry in (data.get("entries") or []) if isinstance(entry, dict)]


def _hydrate(url: str) -> dict:
    return _run_json([
        sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs",
        "--no-playlist", "--dump-single-json", "--skip-download", url,
    ])


def _public_caption_file(url: str, candidate_id: str, directory: Path) -> Path | None:
    directory.mkdir(parents=True, exist_ok=True)
    template = str((directory / f"{candidate_id}.%(ext)s").resolve())
    process = subprocess.run([
        sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs",
        "--no-playlist", "--skip-download", "--write-subs", "--write-auto-subs",
        "--sub-langs", "en.*,en", "--sub-format", "vtt", "-o", template, url,
    ], capture_output=True, text=True, timeout=240)
    if process.returncode:
        return None
    candidates = sorted(directory.glob(f"{candidate_id}*.vtt"))
    return candidates[0] if candidates else None


def _canonical_url(entry: dict) -> str:
    video_id = str(entry.get("id") or "").strip()
    raw = str(entry.get("webpage_url") or entry.get("url") or "").strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return ""


def _candidate_from_metadata(metadata: dict, topic_terms: list[str], now: datetime) -> ClipCandidate:
    video_id = str(metadata.get("id") or "")
    url = _canonical_url(metadata)
    candidate_id = "clip_" + hashlib.sha256(f"youtube:{video_id or url}".encode()).hexdigest()[:12]
    scores = score_video_metadata(metadata, topic_terms, now)
    title = str(metadata.get("title") or "Untitled video")
    description = str(metadata.get("description") or "")
    clip_kind = classify_clip_kind(title, description)
    clipability = 75.0 if clip_kind in {"podcast", "keynote", "interview", "launch", "demo"} else 45.0
    combined = min(100.0, scores["viral_score"] * 0.58 + scores["relevance_score"] * 0.32 + clipability * 0.10)
    license_name = str(metadata.get("license") or "")
    return ClipCandidate(
        candidate_id=candidate_id, video_id=video_id, source_url=url, title=title,
        channel=str(metadata.get("channel") or metadata.get("uploader") or ""),
        channel_id=str(metadata.get("channel_id") or metadata.get("uploader_id") or ""),
        upload_date=str(metadata.get("upload_date") or metadata.get("release_date") or ""),
        duration_seconds=float(metadata.get("duration") or 0),
        view_count=max(0, int(metadata.get("view_count") or 0)),
        like_count=max(0, int(metadata.get("like_count") or 0)),
        comment_count=max(0, int(metadata.get("comment_count") or 0)),
        age_days=scores["age_days"], views_per_day=scores["views_per_day"],
        clip_kind=clip_kind, viral_score=scores["viral_score"],
        relevance_score=scores["relevance_score"], combined_score=round(combined, 2),
        license_name=license_name,
        suggested_rights_basis="creative_commons" if "creative commons" in license_name.casefold() else "",
        permission_contact_url=str(metadata.get("channel_url") or metadata.get("uploader_url") or ""),
        discovery_notes=["No video media downloaded during discovery."],
    )


def discover_viral_clips(request: ClipDiscoveryRequest, output_dir: Path) -> dict:
    """Discover, score, caption-rank, and persist a research-only clip queue."""
    output_dir.mkdir(parents=True, exist_ok=True)
    topic_terms = request.topic_terms or sorted(_tokens(request.topic))
    now = datetime.now(timezone.utc)
    discovered: dict[str, str] = {}
    targets = [*request.queries, *(str(url) for url in request.channel_urls)]
    errors: list[dict[str, str]] = []
    for target in targets:
        try:
            for entry in _discover_entries(target, request.max_results_per_source):
                url = _canonical_url(entry)
                video_id = str(entry.get("id") or "")
                if url and video_id:
                    discovered[video_id] = url
        except Exception as exc:
            errors.append({"source": target, "error": f"{type(exc).__name__}: {exc}"})

    candidates: list[ClipCandidate] = []
    for video_id, url in list(discovered.items()):
        try:
            metadata = _hydrate(url)
            duration = float(metadata.get("duration") or 0)
            scores = score_video_metadata(metadata, topic_terms, now)
            if duration and not (request.min_duration_seconds <= duration <= request.max_duration_seconds):
                continue
            if scores["age_days"] > request.published_within_days:
                continue
            candidates.append(_candidate_from_metadata(metadata, topic_terms, now))
        except Exception as exc:
            errors.append({"source": url, "error": f"{type(exc).__name__}: {exc}"})
    candidates.sort(key=lambda item: item.combined_score, reverse=True)
    candidates = candidates[:request.max_candidates]

    captions_dir = output_dir / "public_captions"
    for candidate in candidates[:request.caption_candidate_count]:
        caption = _public_caption_file(str(candidate.source_url), candidate.candidate_id, captions_dir)
        if not caption:
            candidate.discovery_notes.append("No English public captions were available; timestamp review is manual.")
            continue
        candidate.caption_file = str(caption)
        candidate.moments = rank_caption_moments(parse_vtt(caption), topic_terms)
        if not candidate.moments:
            candidate.discovery_notes.append("Captions were available but no strong automatic moment passed ranking.")

    manifest = {
        "schema_version": 1, "created_at": now.isoformat(), "request": request.model_dump(mode="json"),
        "policy": {
            "discovery_downloads_video": False,
            "default_rights_status": "research_only",
            "render_gate": "An approved rights basis is required before clip ingestion or rendering.",
            "publication_review_required": True,
        },
        "permission_request_template": (
            "Hi {creator}, we're producing an original commentary video about {topic}. "
            "May we use the {start}-{end} excerpt from {title}, with visible attribution and a source link? "
            "Please confirm whether you grant permission for YouTube and other company social channels."
        ),
        "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
        "errors": errors,
    }
    manifest_path = output_dir / "clip_candidates.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    queue_path = output_dir / "permission_queue.csv"
    with queue_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "candidate_id", "title", "channel", "source_url", "moment_start", "moment_end",
            "combined_score", "rights_status", "permission_contact_url", "permission_notes",
        ])
        writer.writeheader()
        for candidate in candidates:
            moment = candidate.moments[0] if candidate.moments else None
            writer.writerow({
                "candidate_id": candidate.candidate_id, "title": candidate.title,
                "channel": candidate.channel, "source_url": str(candidate.source_url),
                "moment_start": moment.start_seconds if moment else "",
                "moment_end": moment.end_seconds if moment else "",
                "combined_score": candidate.combined_score, "rights_status": candidate.rights_status,
                "permission_contact_url": candidate.permission_contact_url, "permission_notes": "",
            })
    return {
        "manifest": str(manifest_path), "permission_queue": str(queue_path),
        "candidate_count": len(candidates), "error_count": len(errors),
        "top_candidates": [candidate.model_dump(mode="json") for candidate in candidates[:5]],
    }


def load_candidate(manifest_path: Path, candidate_id: str) -> ClipCandidate:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for raw in data.get("candidates", []):
        if raw.get("candidate_id") == candidate_id:
            return ClipCandidate.model_validate(raw)
    raise KeyError(f"clip candidate not found: {candidate_id}")


def build_licensed_request(candidate: ClipCandidate, approval: ClipApproval) -> LicensedClipRequest:
    """Convert one approved timestamp into the existing rights-gated ingest contract."""
    if approval.moment_index >= len(candidate.moments):
        raise ValueError("approved moment_index does not exist; add or review timestamps first")
    moment = candidate.moments[approval.moment_index]
    if moment.requires_manual_timestamp_review:
        raise PermissionError("candidate timestamp still requires manual review")
    return LicensedClipRequest(
        clip_id=candidate.candidate_id, source_id=approval.source_id,
        url=candidate.source_url, start_seconds=moment.start_seconds, end_seconds=moment.end_seconds,
        rights_basis=approval.rights_basis, rights_proof_file=approval.rights_proof_file,
        rights_proof_url=approval.rights_proof_url, approved_by=approval.approved_by,
        attribution=approval.attribution, keep_audio=approval.keep_audio,
        avoid_faces=approval.avoid_faces or candidate.clip_kind in {"podcast", "interview", "talk", "keynote", "launch"},
    )
