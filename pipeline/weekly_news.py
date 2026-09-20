"""Significance ranking and evidence-backed planning for the News Weekly format."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .config import OPENROUTER_MODEL
from .editorial import call_openrouter
from .models import Brief, Source
from .research import STOPWORDS


BIG_NEWS_TERMS = {
    "launch", "release", "released", "open source", "open-source", "weights", "acquisition",
    "lawsuit", "ruling", "regulation", "ban", "security", "breach", "funding", "acquires",
    "benchmark", "agent", "model", "video", "image", "robot", "chip", "gpu", "partnership",
}
DEMO_TERMS = {"model", "generator", "demo", "playground", "studio", "app", "workflow", "comfyui", "api"}
CATEGORY_LIMITS = {"model_release": 2, "product": 3, "business": 2, "policy": 2}
HOT_WINDOW_DAYS = 3.0


WEEKLY_DIGEST_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "NewsWeeklyPlan",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["show_title", "episode_title", "thumbnail_text", "cold_open", "throughline", "stories"],
            "properties": {
                "show_title": {"type": "string"},
                "episode_title": {"type": "string"},
                "thumbnail_text": {"type": "string"},
                "cold_open": {"type": "string"},
                "throughline": {"type": "string"},
                "stories": {
                    "type": "array",
                    "items": {
                        "type": "object", "additionalProperties": False,
                        "required": [
                            "story_id", "headline", "source_ids", "why_it_matters", "category",
                            "segment_seconds", "model_test_candidate", "demo_goal", "humor_angle",
                        ],
                        "properties": {
                            "story_id": {"type": "string"},
                            "headline": {"type": "string"},
                            "source_ids": {"type": "array", "items": {"type": "string"}},
                            "why_it_matters": {"type": "string"},
                            "category": {"type": "string", "enum": [
                                "model_release", "open_source", "product", "business", "research",
                                "policy", "security", "hardware",
                            ]},
                            "segment_seconds": {"type": "integer"},
                            "model_test_candidate": {"type": "boolean"},
                            "demo_goal": {"type": "string"},
                            "humor_angle": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
}


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]{2,}", value.casefold())
        if token not in STOPWORDS and not token.isdigit()
    }


def _similar(left: Source, right: Source) -> bool:
    a, b = _tokens(left.title), _tokens(right.title)
    title_overlap = len(a & b) / max(1, len(a | b))
    entities_a = {item.casefold() for item in left.entities if len(item) > 2}
    entities_b = {item.casefold() for item in right.entities if len(item) > 2}
    entity_overlap = entities_a & entities_b
    return title_overlap >= 0.38 or (title_overlap >= 0.16 and len(entity_overlap) >= 2)


def cluster_sources(sources: list[Source]) -> list[list[Source]]:
    """Cluster independent coverage of the same event without merging every story about one company."""
    groups: list[list[Source]] = []
    for source in sorted(sources, key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        destination = next((group for group in groups if any(_similar(source, member) for member in group)), None)
        if destination is None:
            destination = []
            groups.append(destination)
        destination.append(source)
    for group in groups:
        signature = " ".join(sorted(set.intersection(*[_tokens(item.title) or {item.id} for item in group])))
        if not signature:
            signature = sorted(item.id for item in group)[0]
        cluster = "weekly_" + hashlib.sha256(signature.encode()).hexdigest()[:10]
        for source in group:
            source.cluster_id = cluster
    return groups


def _age_days(source: Source, now: datetime) -> float:
    if not source.published_at:
        return 7.0
    stamp = source.published_at
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return max(0.0, (now - stamp.astimezone(timezone.utc)).total_seconds() / 86400)


def score_cluster(group: list[Source], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    publishers = {source.publisher.casefold() or str(source.url) for source in group}
    roles = {source.signal_role for source in group}
    source_types = {source.source_type for source in group}
    combined = " ".join(source.title for source in group).casefold()
    freshest_age_days = min(_age_days(source, now) for source in group)
    recency = max(0.0, 30 * math.exp(-freshest_age_days / 3.2))
    # The reference n8n workflow uses a hard three-day freshness filter. Keep
    # the broader 30-day research window for context, but make the newest 72
    # hours an explicit momentum signal rather than silently treating old and
    # breaking coverage alike.
    hot_window_bonus = 8.0 if freshest_age_days <= HOT_WINDOW_DAYS else 0.0
    breadth = min(22.0, 8 * math.log1p(len(publishers)))
    evidence = (18 if "primary" in source_types else 0) + (10 if "secondary" in source_types else 0)
    signals = (7 if "newsletter_lead" in roles else 0) + (6 if "community_signal" in roles else 0)
    engagement = min(12.0, max((source.trend_score for source in group), default=0) * 0.18)
    impact = min(12.0, sum(2.4 for term in BIG_NEWS_TERMS if term in combined))
    demonstrability = min(10.0, sum(2.5 for term in DEMO_TERMS if term in combined))
    score = min(100.0, recency + hot_window_bonus + breadth + evidence + signals + engagement + impact + demonstrability)
    if not ({"primary_evidence", "independent_reporting"} & roles) and "primary" not in source_types:
        score = min(score, 48.0)
    for source in group:
        source.importance_score = round(score, 2)
    entities = Counter(entity for source in group for entity in source.entities)
    return {
        "cluster_id": group[0].cluster_id,
        "score": round(score, 2),
        "source_ids": [source.id for source in group],
        "titles": [source.title for source in group],
        "publishers": sorted({source.publisher for source in group if source.publisher}),
        "roles": sorted(roles),
        "categories": sorted({source.category for source in group if source.category}),
        "entities": [name for name, _ in entities.most_common(8)],
        "has_primary": "primary" in source_types or "primary_evidence" in roles,
        "has_reporting": "secondary" in source_types or "independent_reporting" in roles,
        "demo_score": round(demonstrability, 2),
        "freshest_age_days": round(freshest_age_days, 3),
        "inside_72h_hot_window": freshest_age_days <= HOT_WINDOW_DAYS,
    }


def rank_clusters(sources: list[Source], now: datetime | None = None) -> list[dict[str, Any]]:
    ranked = [score_cluster(group, now) for group in cluster_sources(sources)]
    return sorted(ranked, key=lambda item: (item["score"], len(item["source_ids"])), reverse=True)


def _validate_plan(plan: dict, sources: list[Source]) -> dict:
    source_by_id = {source.id: source for source in sources}
    thumbnail_words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", plan.get("thumbnail_text", ""))
    if not 3 <= len(thumbnail_words) <= 5:
        title_words = [
            word for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", plan.get("episode_title", ""))
            if word.casefold() not in {"news", "weekly", "the", "and", "with"}
        ]
        fallback = title_words[:5]
        if len(fallback) < 3:
            fallback = ["AI", "NEWS", "CHANGED", "AGAIN"]
        plan["thumbnail_text"] = " ".join(fallback).upper()
    if not 5 <= len(plan["stories"]) <= 7:
        raise ValueError("News Weekly requires 5-7 stories")
    categories: Counter[str] = Counter()
    used_clusters: set[str] = set()
    tests = 0
    for story in plan["stories"]:
        ids = story["source_ids"]
        if not 2 <= len(ids) <= 6:
            raise ValueError(f"weekly story {story['story_id']} requires 2-6 sources")
        if not set(ids).issubset(source_by_id):
            raise ValueError(f"weekly story {story['story_id']} references an unknown source")
        evidence = [source_by_id[source_id] for source_id in ids]
        if not any(source.signal_role in {"primary_evidence", "independent_reporting"} or source.source_type in {"primary", "secondary"} for source in evidence):
            raise ValueError(f"weekly story {story['story_id']} is based only on community/newsletter signals")
        clusters = {source.cluster_id for source in evidence}
        if len(clusters) != 1:
            raise ValueError(f"weekly story {story['story_id']} mixes unrelated source clusters")
        if used_clusters & clusters:
            raise ValueError(f"weekly story {story['story_id']} repeats an earlier cluster")
        used_clusters.update(clusters)
        categories[story["category"]] += 1
        if categories[story["category"]] > CATEGORY_LIMITS.get(story["category"], 3):
            raise ValueError(f"weekly plan overuses {story['category']} stories")
        if not 45 <= int(story["segment_seconds"]) <= 110:
            raise ValueError(f"weekly story {story['story_id']} has an invalid segment length")
        if story["model_test_candidate"]:
            tests += 1
            if not story["demo_goal"].strip():
                raise ValueError(f"weekly story {story['story_id']} needs a concrete demo goal")
        elif story["demo_goal"].strip():
            raise ValueError(f"weekly story {story['story_id']} has a demo goal but is not a test candidate")
    if tests > 2:
        raise ValueError("News Weekly can contain at most two hands-on model tests")
    planned = sum(int(item["segment_seconds"]) for item in plan["stories"])
    if not 390 <= planned <= 570:
        raise ValueError(f"weekly story segments total {planned}s; expected 390-570s before intro/outro")
    return plan


def _repair_story_clusters(plan: dict, sources: list[Source]) -> dict:
    """Expand partial cluster picks and remove duplicate story clusters before validation."""
    source_by_id = {source.id: source for source in sources}
    members_by_cluster: dict[str, list[str]] = {}
    for source in sources:
        members_by_cluster.setdefault(source.cluster_id, []).append(source.id)
    repaired: list[dict] = []
    seen: set[str] = set()
    for story in plan.get("stories", []):
        chosen = [source_by_id[source_id] for source_id in story.get("source_ids", []) if source_id in source_by_id]
        clusters = {source.cluster_id for source in chosen if source.cluster_id}
        if len(clusters) != 1:
            repaired.append(story)
            continue
        cluster = next(iter(clusters))
        if cluster in seen:
            continue
        seen.add(cluster)
        story["source_ids"] = members_by_cluster.get(cluster, story["source_ids"])[:6]
        repaired.append(story)
    if len(repaired) < 5:
        groups: dict[str, list[Source]] = {}
        for source in sources:
            groups.setdefault(source.cluster_id, []).append(source)
        ranked_groups = sorted(
            (group for group in groups.values() if len(group) >= 2),
            key=lambda group: max(source.importance_score for source in group),
            reverse=True,
        )
        categories = Counter(story.get("category", "research") for story in repaired)
        category_map = {
            "models": "model_release", "products": "product", "technology": "business",
            "community": "open_source", "papers": "research",
        }
        for group in ranked_groups:
            cluster = group[0].cluster_id
            if cluster in seen:
                continue
            raw_category = next((source.category for source in group if source.category), "research")
            category = category_map.get(raw_category, raw_category)
            if category not in {"model_release", "open_source", "product", "business", "research", "policy", "security", "hardware"}:
                category = "research"
            if categories[category] >= CATEGORY_LIMITS.get(category, 3):
                continue
            headline = max(group, key=lambda source: source.importance_score).title
            repaired.append({
                "story_id": f"story_{len(repaired) + 1:03d}",
                "headline": headline,
                "source_ids": [source.id for source in group[:6]],
                "why_it_matters": "Explain what materially changed and the practical consequence using the attached evidence.",
                "category": category,
                "segment_seconds": 80,
                "model_test_candidate": False,
                "demo_goal": "",
                "humor_angle": "",
            })
            seen.add(cluster)
            categories[category] += 1
            if len(repaired) >= 5:
                break
    plan["stories"] = repaired
    if repaired:
        planned = sum(int(story.get("segment_seconds", 0)) for story in repaired)
        if not 390 <= planned <= 570:
            segment_seconds = max(45, min(110, round(480 / len(repaired))))
            for story in repaired:
                story["segment_seconds"] = segment_seconds
    return plan


def plan_weekly_digest(sources: list[Source], recent_topics: list[str] | None = None) -> tuple[Brief, dict[str, Any]]:
    ranked = [item for item in rank_clusters(sources) if len(item["source_ids"]) >= 2][:18]
    if len(ranked) < 5:
        raise ValueError(f"only {len(ranked)} multi-source story clusters are ready; at least five are required")
    valid_source_ids = {source_id for cluster in ranked for source_id in cluster["source_ids"]}
    candidates = [source for source in sources if source.id in valid_source_ids]
    correction = ""
    last_error: Exception | None = None
    for _attempt in range(3):
        plan = call_openrouter(
            OPENROUTER_MODEL,
            "You are the executive producer of The Week in AI, an original sub-ten-minute technology and AI news show. "
            "Select consequential stories, not merely loud ones. Community and newsletters are attention signals; factual narration must rest on primary evidence or independent reporting.",
            "Build one entertaining weekly rundown with 5-7 non-overlapping stories. Lead with the highest-consequence visible story, "
            "balance commercial AI, open source, research, business/policy, and creator tools, and choose at most two products for a real captured test. "
            "Humor angles must come from a documented contradiction, awkward limitation, or recognizable user behavior; use an empty string when nothing honest is funny. "
            "The cold open is a rapid promise, not a summary. The show title is THE WEEK IN AI. Do not fabricate a test, URL, result, number, or source. "
            "Use source IDs only within one ranked cluster per story. Avoid recent topics unless a material new event occurred."
            f"\n{correction}\n\nRECENT TOPICS:\n{json.dumps(recent_topics or [])}\n\nRANKED CLUSTERS:\n{json.dumps(ranked)}\n\n"
            f"SOURCES:\n{json.dumps([source.model_dump(mode='json') for source in candidates], default=str)}",
            WEEKLY_DIGEST_SCHEMA,
            temperature=0.45,
        )
        try:
            plan = _repair_story_clusters(plan, candidates)
            _validate_plan(plan, candidates)
            selected_ids = list(dict.fromkeys(source_id for story in plan["stories"] for source_id in story["source_ids"]))
            brief = Brief(
                title=plan["episode_title"], thesis=plan["throughline"], episode_format="weekly_roundup",
                source_ids=selected_ids, claim_ids=[], why_now=plan["cold_open"],
                visual_opportunities=[
                    f"{story['headline']}: {'hands-on model test' if story['model_test_candidate'] else 'source-led explainer'}"
                    for story in plan["stories"]
                ],
            )
            return brief, plan
        except ValueError as exc:
            last_error = exc
            correction = f"The previous plan failed validation: {exc}. Replace it and correct that exact defect."
    raise RuntimeError(f"weekly digest planning failed after three attempts: {last_error}")
