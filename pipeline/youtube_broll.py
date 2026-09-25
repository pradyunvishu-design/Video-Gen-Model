"""Scene-specific YouTube b-roll discovery using official public APIs.

The discovery stage never downloads video. It creates a human-review manifest
with three candidates per narration scene, public source URLs, suggested
timestamps when captions are available, and a rights status. Existing
``licensed_clips`` code remains the only path that can download an approved
excerpt into an episode.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import requests
from pydantic import BaseModel, Field

from .config import OPENAI_API_KEY, OPENAI_BROLL_MODEL, YOUTUBE_API_KEY
from .clip_alignment import score_alignment
from .models import EpisodeProject
from .viral_clips import (
    ClipCandidate,
    ClipMoment,
    _public_caption_file,
    _tokens,
    classify_clip_kind,
    parse_vtt,
    rank_caption_moments,
    score_video_metadata,
)


YOUTUBE_API_ROOT = "https://www.googleapis.com/youtube/v3"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class BrollScene(BaseModel):
    search_context: Literal["ai_news", "general"] = "ai_news"
    scene_id: str = Field(min_length=1, max_length=120)
    beat_id: str = Field(min_length=1, max_length=120)
    shot_ids: list[str] = Field(default_factory=list, max_length=3)
    narration: str = Field(min_length=2, max_length=3000)
    visual_need: str = Field(min_length=2, max_length=600)
    source_hints: list[str] = Field(default_factory=list, max_length=12)
    publisher_hints: list[str] = Field(default_factory=list, max_length=8)


class BrollDiscoveryRequest(BaseModel):
    scenes: list[BrollScene] = Field(min_length=1, max_length=70)
    candidates_per_scene: int = Field(default=3, ge=1, le=3)
    search_results_per_scene: int = Field(default=12, ge=3, le=50)
    published_within_days: int | None = Field(default=180, ge=1, le=3650)
    caption_candidates_per_scene: int = Field(default=1, ge=0, le=3)
    region_code: str = Field(default="US", min_length=2, max_length=2)
    relevance_language: str = Field(default="en", min_length=2, max_length=12)
    creative_commons_only: bool = False
    require_reputable_or_viral: bool = True
    min_channel_subscribers: int = Field(default=250_000, ge=0)
    min_video_views: int = Field(default=250_000, ge=0)
    min_views_per_day: float = Field(default=5_000, ge=0)
    min_semantic_score: float = Field(default=45, ge=0, le=100)
    recognized_publishers_only: bool = False
    recognized_publishers: list[str] = Field(default_factory=list, max_length=100)


class BrollCandidate(ClipCandidate):
    scene_id: str
    beat_id: str
    shot_ids: list[str] = Field(default_factory=list)
    search_query: str
    visual_target: str
    thumbnail_url: str = ""
    definition: str = ""
    embeddable: bool = True
    rank_reason: str = ""
    semantic_score: float = 0
    matched_terms: list[str] = Field(default_factory=list)
    matched_concepts: list[str] = Field(default_factory=list)
    alignment_reason: str = ""
    subscriber_count: int = 0
    official_channel_match: bool = False
    recognized_publisher_match: bool = False
    reputable_channel: bool = False
    viral_video: bool = False
    source_tier: str = "rejected"
    quality_gate_passed: bool = False
    quality_gate_reasons: list[str] = Field(default_factory=list)
    render_eligible: bool = False


def _normalized_publisher(value: str) -> str:
    """Normalize a visible channel/publisher name for strict trust matching.

    Substring matching is intentionally avoided: a channel named ``Learn
    Claude Code`` must not be treated as Anthropic's official channel merely
    because its title contains a product name.
    """
    value = re.sub(r"\[[^\]]+\]", " ", value.casefold())
    value = re.sub(r"\b(official|channel|youtube)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _publisher_matches(channel: str, publishers: list[str]) -> bool:
    channel_name = _normalized_publisher(channel)
    if not channel_name:
        return False
    return any(
        channel_name == _normalized_publisher(publisher)
        for publisher in publishers
        if _normalized_publisher(publisher)
    )


def _redact(value: str, secret: str) -> str:
    return value.replace(secret, "<redacted>") if secret else value


def _youtube_get(resource: str, params: dict, api_key: str | None = None) -> dict:
    key = YOUTUBE_API_KEY if api_key is None else api_key
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY is not configured")
    request_params = {**params, "key": key}
    last_error = ""
    for attempt in range(3):
        try:
            response = requests.get(
                f"{YOUTUBE_API_ROOT}/{resource}", params=request_params, timeout=30,
            )
            if response.status_code == 200:
                return response.json()
            try:
                detail = response.json().get("error", {}).get("message", "")
            except Exception:
                detail = response.text[:300]
            last_error = f"YouTube API {resource} returned {response.status_code}: {detail}"
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
        except requests.RequestException as exc:
            last_error = _redact(f"YouTube API request failed: {exc}", key)
        time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(_redact(last_error or "YouTube API request failed", key))


def _response_text(payload: dict) -> str:
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return str(content["text"])
    raise RuntimeError("OpenAI response did not contain output text")


def _fallback_plan(scene: BrollScene) -> dict:
    hint = " ".join(scene.source_hints[:3])
    visual = re.sub(r"\s+", " ", scene.visual_need).strip()
    suffix = "official demo keynote" if scene.search_context == "ai_news" else "demonstration documentary footage"
    query = " ".join(part for part in (hint, visual, suffix) if part).strip()
    return {
        "scene_id": scene.scene_id,
        "query": query[:220],
        "visual_target": visual[:300],
        "avoid": "reaction videos, reuploads, slideshows, unrelated talking heads",
    }


def plan_scene_queries(
    scenes: list[BrollScene], api_key: str | None = None,
) -> tuple[list[dict], str]:
    """Use one structured OpenAI call for all scene searches, with a local fallback."""
    key = OPENAI_API_KEY if api_key is None else api_key
    fallback = [_fallback_plan(scene) for scene in scenes]
    if not key:
        return fallback, "deterministic_fallback"
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["plans"],
        "properties": {
            "plans": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["scene_id", "query", "visual_target", "avoid"],
                    "properties": {
                        "scene_id": {"type": "string"},
                        "query": {"type": "string"},
                        "visual_target": {"type": "string"},
                        "avoid": {"type": "string"},
                    },
                },
            }
        },
    }
    compact_scenes = [
        {
            "scene_id": scene.scene_id,
            "search_context": scene.search_context,
            "narration": scene.narration[:1200],
            "visual_need": scene.visual_need,
            "source_hints": scene.source_hints,
            "publisher_hints": scene.publisher_hints,
        }
        for scene in scenes
    ]
    body = {
        "model": OPENAI_BROLL_MODEL,
        "store": False,
        "instructions": (
            "Create one concise YouTube search query per scene for an original AI-media news video. "
            "Prefer the official company channel, launch demos, conference keynotes, engineering footage, "
            "product UI, and direct interviews. The query must describe visible footage, not repeat the "
            "narration. Avoid reaction channels, compilations, reuploads, generic AI slideshows, and footage "
            "that would misrepresent the sentence. Return every supplied scene_id exactly once."
        ),
        "input": json.dumps(compact_scenes, ensure_ascii=False),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "youtube_broll_search_plan",
                "strict": True,
                "schema": schema,
            }
        },
    }
    if any(scene.search_context == "general" for scene in scenes):
        body["instructions"] = (
            "Create one concise YouTube search query per scene for a nonfiction explanation. "
            "Adapt to the scene's actual subject: demonstrations, documentary footage, museum or research institution "
            "material, original reporting, and credible domain specialists. Do not force technology launches or "
            "keynotes onto unrelated topics. Describe visible evidence, not talking-head reactions. Avoid reuploads, "
            "misleading matches and unsupported historical reconstructions. Return every scene_id exactly once."
        )
    try:
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=body,
            timeout=90,
        )
        if response.status_code != 200:
            return fallback, f"deterministic_fallback_openai_{response.status_code}"
        parsed = json.loads(_response_text(response.json()))
        by_id = {str(item.get("scene_id")): item for item in parsed.get("plans", [])}
        plans = [by_id.get(scene.scene_id, _fallback_plan(scene)) for scene in scenes]
        return plans, "openai_structured"
    except Exception:
        return fallback, "deterministic_fallback_openai_error"


def _iso_duration_seconds(value: str) -> float:
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?",
        value or "",
    )
    if not match:
        return 0.0
    return float(
        int(match.group("days") or 0) * 86_400
        + int(match.group("hours") or 0) * 3_600
        + int(match.group("minutes") or 0) * 60
        + int(match.group("seconds") or 0)
    )


def _search_video_ids(
    query: str, request: BrollDiscoveryRequest, api_key: str | None = None,
) -> list[str]:
    params = {
        "part": "snippet",
        "type": "video",
        "q": query,
        "maxResults": request.search_results_per_scene,
        "order": "relevance",
        "regionCode": request.region_code.upper(),
        "relevanceLanguage": request.relevance_language,
        "safeSearch": "moderate",
        "videoEmbeddable": "true",
        "videoDefinition": "high",
    }
    if request.published_within_days is not None:
        published_after = datetime.now(timezone.utc) - timedelta(days=request.published_within_days)
        params["publishedAfter"] = published_after.isoformat().replace("+00:00", "Z")
    if request.creative_commons_only:
        params["videoLicense"] = "creativeCommon"
    data = _youtube_get("search", params, api_key)
    return list(dict.fromkeys(
        str(item.get("id", {}).get("videoId") or "")
        for item in data.get("items", [])
        if item.get("id", {}).get("videoId")
    ))


def _video_details(video_ids: list[str], api_key: str | None = None) -> list[dict]:
    if not video_ids:
        return []
    data = _youtube_get("videos", {
        "part": "snippet,contentDetails,statistics,status",
        "id": ",".join(video_ids[:50]),
        "maxResults": min(50, len(video_ids)),
    }, api_key)
    return [item for item in data.get("items", []) if isinstance(item, dict)]


def _channel_details(channel_ids: list[str], api_key: str | None = None) -> dict[str, dict]:
    """Fetch reputation signals without scraping channel pages.

    Subscriber counts are only a trust signal; an exact publisher/channel match
    can pass even when the channel hides its subscriber count.
    """
    ids = list(dict.fromkeys(channel_id for channel_id in channel_ids if channel_id))[:50]
    if not ids:
        return {}
    data = _youtube_get("channels", {
        "part": "snippet,statistics,status",
        "id": ",".join(ids),
        "maxResults": len(ids),
    }, api_key)
    result: dict[str, dict] = {}
    for item in data.get("items", []):
        if not isinstance(item, dict):
            continue
        channel_id = str(item.get("id") or "")
        statistics = item.get("statistics") or {}
        snippet = item.get("snippet") or {}
        result[channel_id] = {
            "subscriber_count": int(statistics.get("subscriberCount") or 0),
            "hidden_subscriber_count": bool(statistics.get("hiddenSubscriberCount", False)),
            "channel_view_count": int(statistics.get("viewCount") or 0),
            "channel_video_count": int(statistics.get("videoCount") or 0),
            "channel_title": str(snippet.get("title") or ""),
            "custom_url": str(snippet.get("customUrl") or ""),
        }
    return result


def _thumbnail(snippet: dict) -> str:
    thumbs = snippet.get("thumbnails") or {}
    for name in ("maxres", "standard", "high", "medium", "default"):
        if thumbs.get(name, {}).get("url"):
            return str(thumbs[name]["url"])
    return ""


def _metadata(item: dict) -> dict:
    snippet = item.get("snippet") or {}
    statistics = item.get("statistics") or {}
    content = item.get("contentDetails") or {}
    status = item.get("status") or {}
    published = str(snippet.get("publishedAt") or "")
    upload_date = published[:10].replace("-", "") if published else ""
    return {
        "id": str(item.get("id") or ""),
        "title": str(snippet.get("title") or "Untitled video"),
        "description": str(snippet.get("description") or ""),
        "channel": str(snippet.get("channelTitle") or ""),
        "channel_id": str(snippet.get("channelId") or ""),
        "upload_date": upload_date,
        "duration": _iso_duration_seconds(str(content.get("duration") or "")),
        "view_count": int(statistics.get("viewCount") or 0),
        "like_count": int(statistics.get("likeCount") or 0),
        "comment_count": int(statistics.get("commentCount") or 0),
        "license": str(status.get("license") or ""),
        "embeddable": bool(status.get("embeddable", True)),
        "definition": str(content.get("definition") or ""),
        "thumbnail_url": _thumbnail(snippet),
    }


def _candidate(
    scene: BrollScene, plan: dict, raw: dict, now: datetime,
    request: BrollDiscoveryRequest, channel_info: dict | None = None,
) -> BrollCandidate:
    metadata = _metadata(raw)
    query_terms = sorted(_tokens(f"{scene.visual_need} {' '.join(scene.source_hints)}"))
    scores = score_video_metadata(metadata, query_terms, now)
    kind = classify_clip_kind(metadata["title"], metadata["description"])
    # Only publishers may establish an official-channel match. Article titles
    # often contain a company/product name and previously caused tutorial
    # channels such as "Learn Claude Code" to be mislabeled as official.
    official_channel_match = _publisher_matches(metadata["channel"], scene.publisher_hints)
    recognized_publisher_match = _publisher_matches(
        metadata["channel"], request.recognized_publishers,
    )
    official_boost = 18.0 if official_channel_match else (10.0 if recognized_publisher_match else 0.0)
    subscriber_count = int((channel_info or {}).get("subscriber_count") or 0)
    reputable_channel = (
        official_channel_match
        or recognized_publisher_match
        or subscriber_count >= request.min_channel_subscribers
    )
    viral_video = (
        metadata["view_count"] >= request.min_video_views
        or scores["views_per_day"] >= request.min_views_per_day
    )
    blocked_title = bool(re.search(
        r"\b(reaction|reupload|compilation|top\s*\d+|shorts?)\b",
        f"{metadata['title']} {metadata['description'][:240]}",
        re.IGNORECASE,
    ))
    gate_reasons: list[str] = []
    if metadata["definition"].casefold() != "hd":
        gate_reasons.append("not_hd")
    if not metadata["embeddable"]:
        gate_reasons.append("not_embeddable")
    if not (reputable_channel or viral_video):
        gate_reasons.append("neither_reputable_nor_viral")
    if request.recognized_publishers_only and not (
        official_channel_match or recognized_publisher_match
    ):
        gate_reasons.append("not_recognized_publisher")
    if blocked_title and not official_channel_match:
        gate_reasons.append("low_value_or_reupload_pattern")
    quality_gate_passed = not gate_reasons or (
        not request.require_reputable_or_viral
        and set(gate_reasons) <= {"neither_reputable_nor_viral"}
    )
    if official_channel_match:
        source_tier = "official"
    elif recognized_publisher_match:
        source_tier = "recognized_organization"
    elif reputable_channel:
        source_tier = "established_channel"
    elif viral_video:
        source_tier = "viral_video"
    else:
        source_tier = "rejected"
    format_boost = 8.0 if kind in {"keynote", "launch", "demo", "interview", "podcast"} else 2.0
    relevance = min(100.0, scores["relevance_score"] + official_boost)
    # Rank the picture against the requested picture. Narration is deliberately
    # excluded here: long scripts contain enough generic terms to make an
    # unrelated tutorial look semantically relevant.
    alignment = score_alignment(
        f"{scene.visual_need} {plan.get('visual_target', '')}",
        f"{metadata['title']} {metadata['description']} {metadata['channel']} {kind}",
        source_hints=scene.publisher_hints or scene.source_hints,
    )
    # Sentence-to-picture fit is the largest component. A viral but unrelated
    # keynote is not useful b-roll.
    combined = min(
        100.0,
        alignment["score"] * 0.52 + relevance * 0.28
        + scores["viral_score"] * 0.12 + format_boost,
    )
    license_name = metadata["license"]
    creative_commons = license_name.casefold() in {"creativecommon", "creative commons"}
    video_id = metadata["id"]
    candidate_id = "broll_" + hashlib.sha256(
        f"{scene.scene_id}:youtube:{video_id}".encode("utf-8")
    ).hexdigest()[:14]
    return BrollCandidate(
        candidate_id=candidate_id,
        video_id=video_id,
        source_url=f"https://www.youtube.com/watch?v={video_id}",
        title=metadata["title"],
        channel=metadata["channel"],
        channel_id=metadata["channel_id"],
        upload_date=metadata["upload_date"],
        duration_seconds=metadata["duration"],
        view_count=metadata["view_count"],
        like_count=metadata["like_count"],
        comment_count=metadata["comment_count"],
        age_days=scores["age_days"],
        views_per_day=scores["views_per_day"],
        clip_kind=kind,
        viral_score=scores["viral_score"],
        relevance_score=round(relevance, 2),
        combined_score=round(combined, 2),
        license_name=license_name,
        suggested_rights_basis="creative_commons" if creative_commons else "",
        permission_contact_url=f"https://www.youtube.com/channel/{metadata['channel_id']}",
        discovery_notes=[
            "Metadata discovered through the YouTube Data API; no video media downloaded.",
            "Human clip and rights review required before ingestion.",
        ],
        scene_id=scene.scene_id,
        beat_id=scene.beat_id,
        shot_ids=scene.shot_ids,
        search_query=str(plan.get("query") or ""),
        visual_target=str(plan.get("visual_target") or scene.visual_need),
        thumbnail_url=metadata["thumbnail_url"],
        definition=metadata["definition"],
        embeddable=metadata["embeddable"],
        rank_reason=(
            f"semantic fit {alignment['score']:.0f}, relevance {relevance:.0f}, momentum {scores['viral_score']:.0f}, "
            f"format {kind}, official-channel boost {official_boost:.0f}"
        ),
        semantic_score=alignment["score"],
        matched_terms=alignment["matched_terms"],
        matched_concepts=alignment["matched_concepts"],
        alignment_reason=alignment["reason"],
        subscriber_count=subscriber_count,
        official_channel_match=official_channel_match,
        recognized_publisher_match=recognized_publisher_match,
        reputable_channel=reputable_channel,
        viral_video=viral_video,
        source_tier=source_tier,
        quality_gate_passed=quality_gate_passed,
        quality_gate_reasons=gate_reasons,
        render_eligible=False,
    )


def build_project_broll_request(project: EpisodeProject) -> BrollDiscoveryRequest:
    if not project.script or not project.shots:
        raise ValueError("episode requires an approved script and storyboard before b-roll discovery")
    shots_by_beat: dict[str, list] = {}
    for shot in project.shots:
        if shot.asset_type in {"chapter_card", "chart"}:
            continue
        shots_by_beat.setdefault(shot.beat_id, []).append(shot)
    source_by_id = {source.id: source for source in project.sources}
    preferred_purposes = {
        "hook", "story_intro", "test_setup", "model_test", "observation", "evidence",
        "analysis", "comparison", "implication", "verdict", "weekly_recap",
    }
    target_shots = [shot for shot in project.shots if shot.visual_category == "youtube_broll"]
    scenes: list[BrollScene] = []
    for beat in project.script.beats:
        shots = sorted(shots_by_beat.get(beat.id, []), key=lambda item: item.start_seconds)
        if not shots or beat.purpose not in preferred_purposes:
            continue
        hints = []
        publishers = []
        for source_id in beat.source_ids:
            source = source_by_id.get(source_id)
            if source:
                hints.extend([source.publisher, source.title])
                publishers.append(source.publisher)
        selected = [shot for shot in shots if not target_shots or shot.visual_category == "youtube_broll"]
        for shot in selected:
            scenes.append(BrollScene(
                scene_id=f"scene_{shot.id}",
                beat_id=beat.id,
                shot_ids=[shot.id],
                narration=beat.narration,
                visual_need=shot.prompt or beat.visual_direction,
                source_hints=list(dict.fromkeys(hint for hint in hints if hint))[:8],
                publisher_hints=list(dict.fromkeys(hint for hint in publishers if hint))[:8],
            ))
    if len(scenes) > 70:
        indices = [round(index * (len(scenes) - 1) / 69) for index in range(70)]
        scenes = [scenes[index] for index in dict.fromkeys(indices)]
    if not scenes:
        raise ValueError("storyboard has no narration scenes eligible for external b-roll")
    return BrollDiscoveryRequest(scenes=scenes)


def discover_project_broll(
    project: EpisodeProject,
    output_dir: Path,
    request: BrollDiscoveryRequest | None = None,
    *,
    youtube_api_key: str | None = None,
    openai_api_key: str | None = None,
    should_cancel=None,
) -> dict:
    request = request or build_project_broll_request(project)
    output_dir.mkdir(parents=True, exist_ok=True)
    plans, planner = plan_scene_queries(request.scenes, openai_api_key)
    plan_by_scene = {str(plan["scene_id"]): plan for plan in plans}
    now = datetime.now(timezone.utc)
    all_candidates: list[BrollCandidate] = []
    scene_records: list[dict] = []
    errors: list[dict[str, str]] = []
    globally_selected_video_ids: set[str] = set()
    captions_dir = output_dir / "public_captions"

    for scene in request.scenes:
        if should_cancel and should_cancel():
            raise InterruptedError("b-roll discovery canceled")
        plan = plan_by_scene.get(scene.scene_id, _fallback_plan(scene))
        try:
            video_ids = _search_video_ids(str(plan["query"]), request, youtube_api_key)
            details = _video_details(video_ids, youtube_api_key)
            channels = _channel_details(
                [str((item.get("snippet") or {}).get("channelId") or "") for item in details],
                youtube_api_key,
            )
            ranked = sorted(
                (
                    _candidate(
                        scene, plan, item, now, request,
                        channels.get(str((item.get("snippet") or {}).get("channelId") or ""), {}),
                    )
                    for item in details
                ),
                key=lambda item: item.combined_score,
                reverse=True,
            )
            unique = [
                item for item in ranked
                if item.video_id not in globally_selected_video_ids
                and item.semantic_score >= request.min_semantic_score
                and item.quality_gate_passed
            ]
            selected = unique[:request.candidates_per_scene]
            globally_selected_video_ids.update(item.video_id for item in selected)
            terms = sorted(_tokens(f"{scene.visual_need} {scene.narration}"))
            for candidate in selected[:request.caption_candidates_per_scene]:
                caption = _public_caption_file(
                    str(candidate.source_url), candidate.candidate_id, captions_dir,
                )
                if caption:
                    candidate.caption_file = str(caption)
                    candidate.moments = rank_caption_moments(
                        parse_vtt(caption), terms, max_moments=2, target_seconds=14.0,
                    )
                if not candidate.moments:
                    candidate.discovery_notes.append(
                        "No reliable timestamp was inferred; choose the range manually in review."
                    )
            all_candidates.extend(selected)
            scene_records.append({
                **scene.model_dump(mode="json"),
                "search_query": plan["query"],
                "visual_target": plan["visual_target"],
                "avoid": plan["avoid"],
                "candidate_ids": [item.candidate_id for item in selected],
            })
        except Exception as exc:
            errors.append({"scene_id": scene.scene_id, "error": f"{type(exc).__name__}: {exc}"})
            scene_records.append({
                **scene.model_dump(mode="json"),
                "search_query": plan["query"],
                "visual_target": plan["visual_target"],
                "avoid": plan["avoid"],
                "candidate_ids": [],
            })

    manifest = {
        "schema_version": 1,
        "created_at": now.isoformat(),
        "episode_id": project.episode_id,
        "planner": planner,
        "request": request.model_dump(mode="json"),
        "policy": {
            "discovery_downloads_video": False,
            "candidates_per_scene": request.candidates_per_scene,
            "render_gate": "approved owned, permissioned, Creative Commons, or public-domain rights",
            "source_audio_default": "muted",
            "publication_review_required": True,
            "minimum_semantic_score": request.min_semantic_score,
            "max_video_uses_per_episode": 1,
            "creative_commons_only": request.creative_commons_only,
            "require_reputable_or_viral": request.require_reputable_or_viral,
            "minimum_channel_subscribers": request.min_channel_subscribers,
            "minimum_video_views": request.min_video_views,
            "minimum_views_per_day": request.min_views_per_day,
            "recognized_publishers_only": request.recognized_publishers_only,
            "recognized_publishers": request.recognized_publishers,
            "blocked_media_is_never_rendered": True,
        },
        "scenes": scene_records,
        "candidates": [item.model_dump(mode="json") for item in all_candidates],
        "errors": errors,
    }
    manifest_path = output_dir / "broll_candidates.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    queue_path = output_dir / "broll_review.csv"
    with queue_path.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "scene_id", "beat_id", "shot_ids", "candidate_id", "title", "channel",
            "source_url", "thumbnail_url", "moment_start", "moment_end", "semantic_score", "combined_score",
            "source_tier", "subscriber_count", "view_count", "views_per_day",
            "license_name", "rights_status", "quality_gate_passed", "review_notes",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in all_candidates:
            moment = item.moments[0] if item.moments else None
            writer.writerow({
                "scene_id": item.scene_id,
                "beat_id": item.beat_id,
                "shot_ids": ",".join(item.shot_ids),
                "candidate_id": item.candidate_id,
                "title": item.title,
                "channel": item.channel,
                "source_url": str(item.source_url),
                "thumbnail_url": item.thumbnail_url,
                "moment_start": moment.start_seconds if moment else "",
                "moment_end": moment.end_seconds if moment else "",
                "combined_score": item.combined_score,
                "semantic_score": item.semantic_score,
                "source_tier": item.source_tier,
                "subscriber_count": item.subscriber_count,
                "view_count": item.view_count,
                "views_per_day": item.views_per_day,
                "license_name": item.license_name,
                "rights_status": item.rights_status,
                "quality_gate_passed": item.quality_gate_passed,
                "review_notes": "",
            })
    grouped = {
        scene.scene_id: [
            item.model_dump(mode="json") for item in all_candidates if item.scene_id == scene.scene_id
        ]
        for scene in request.scenes
    }
    return {
        "manifest": str(manifest_path),
        "review_queue": str(queue_path),
        "scene_count": len(request.scenes),
        "candidate_count": len(all_candidates),
        "error_count": len(errors),
        "candidates_by_scene": grouped,
        "planner": planner,
    }
