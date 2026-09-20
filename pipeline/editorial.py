"""Evidence-constrained slate planning, script writing, and independent verification."""
from __future__ import annotations

import json
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from collections import Counter
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests

from .config import (
    MAX_SCRIPT_WORDS, MIN_SCRIPT_WORDS, OPENROUTER_API_KEY, OPENROUTER_MODEL,
    OPENROUTER_VERIFY_MODEL, PROJECT_ROOT, require,
)
from .models import Brief, Claim, DeliveryDirection, EpisodeProject, Script, Source
from .tooling_catalog import method_provenance_for

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
FORMATS = ["roundup", "weekly_roundup", "deep_dive", "tool_test", "open_source_spotlight", "trend_explainer"]
EDITORIAL_VOICE_PROFILE_PATH = PROJECT_ROOT / "configs" / "editorial_voice_profile.json"
CONVERSATIONAL_SCRIPT_PROFILE_PATH = PROJECT_ROOT / "configs" / "conversational_script_profile.json"


@lru_cache(maxsize=1)
def load_editorial_voice_profile() -> dict[str, Any]:
    """Load the channel's durable spoken-voice contract."""
    payload = json.loads(EDITORIAL_VOICE_PROFILE_PATH.read_text(encoding="utf-8"))
    required = {"profile_id", "audience_relationship", "cadence", "language", "humor", "avoid"}
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"editorial voice profile is missing required fields: {', '.join(missing)}")
    return payload


@lru_cache(maxsize=1)
def load_conversational_script_profile() -> dict[str, Any]:
    """Load the channel's opening, conversation, and retention-writing contract."""
    payload = json.loads(CONVERSATIONAL_SCRIPT_PROFILE_PATH.read_text(encoding="utf-8"))
    required = {
        "profile_id", "opening_modes", "selection_rubric", "conversation_loop",
        "rhythm", "retention", "anti_imitation",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(
            "conversational script profile is missing required fields: " + ", ".join(missing)
        )
    return payload


def _schema(model: type) -> dict:
    return {"type": "json_schema", "json_schema": {"name": model.__name__, "strict": True, "schema": model.model_json_schema()}}


_OPENROUTER_USAGE_HOOK: ContextVar[Any | None] = ContextVar("openrouter_usage_hook", default=None)


@contextmanager
def capture_openrouter_usage(hook):
    """Attach a per-run budget/usage hook without changing existing call sites."""
    token = _OPENROUTER_USAGE_HOOK.set(hook)
    try:
        yield
    finally:
        _OPENROUTER_USAGE_HOOK.reset(token)


def _openrouter_input_metrics(system: str, user: Any) -> dict[str, int]:
    """Count billable text separately from image payload bytes for budget bounds."""
    text_parts = [system]
    image_count = 0

    def visit(value: Any) -> None:
        nonlocal image_count
        if isinstance(value, str):
            text_parts.append(value)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            if value.get("type") == "image_url":
                image_count += 1
            else:
                for key, item in value.items():
                    if key not in {"image_url", "url"}:
                        visit(item)
        else:
            text_parts.append(json.dumps(value, ensure_ascii=False, default=str))

    visit(user)
    text = "\n".join(text_parts)
    return {
        "input_characters": len(text),
        "input_bytes": len(text.encode("utf-8")),
        "input_images": image_count,
    }


def call_openrouter(
    model: str, system: str, user: Any, response_schema: dict, *, temperature: float = 0.4,
) -> dict:
    key = require(OPENROUTER_API_KEY, "OPENROUTER_API_KEY")
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": 16000,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": response_schema,
    }
    hook = _OPENROUTER_USAGE_HOOK.get()
    if hook:
        adjustment = hook({
            "phase": "before", "model": model, "max_tokens": payload["max_tokens"],
            **_openrouter_input_metrics(system, user),
        })
        if isinstance(adjustment, dict):
            if adjustment.get("max_tokens"):
                payload["max_tokens"] = min(payload["max_tokens"], int(adjustment["max_tokens"]))
            if adjustment.get("provider"):
                payload["provider"] = adjustment["provider"]
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "Magic Hour Editorial"},
                json=payload,
                timeout=600,
            )
            if not response.ok:
                detail = response.text.strip().replace(OPENROUTER_API_KEY, "[redacted]")[:4000]
                error = RuntimeError(f"OpenRouter returned HTTP {response.status_code}: {detail}")
                if response.status_code not in {408, 409, 429} and response.status_code < 500:
                    raise error
                raise error
            envelope = response.json()
            if hook:
                hook({
                    "phase": "after", "model": model,
                    "usage": envelope.get("usage") or {},
                    "generation_id": envelope.get("id") or "",
                })
            content = envelope["choices"][0]["message"]["content"]
            return json.loads(content)
        except (requests.RequestException, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            last_error = exc
        except RuntimeError as exc:
            last_error = exc
            if "HTTP 4" in str(exc) and not any(code in str(exc) for code in ("408", "409", "429")):
                raise
        if attempt < 2:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OpenRouter response remained unavailable or malformed after 3 attempts: {last_error}")


SLATE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "WeeklySlate", "strict": True,
        "schema": {
            "type": "object", "additionalProperties": False, "required": ["briefs"],
            "properties": {
                "briefs": {
                    "type": "array",
                    "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["title", "thesis", "episode_format", "source_ids", "why_now", "visual_opportunities"],
                        "properties": {
                            "title": {"type": "string"}, "thesis": {"type": "string"},
                            "episode_format": {"type": "string", "enum": FORMATS},
                            "source_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                            "why_now": {"type": "string"},
                            "visual_opportunities": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                }
            },
        },
    },
}

CLAIMS_SCHEMA = {
    "type": "json_schema", "json_schema": {"name": "EvidenceClaims", "strict": True, "schema": {
        "type": "object", "additionalProperties": False, "required": ["claims"], "properties": {"claims": {
            "type": "array", "items": {"type": "object", "additionalProperties": False,
                "required": ["id", "text", "source_ids", "disputed", "kind"], "properties": {
                    "id": {"type": "string"}, "text": {"type": "string"},
                    "source_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                    "disputed": {"type": "boolean"},
                    "kind": {"type": "string", "enum": ["fact", "number", "quote", "commentary"]},
                }}
        }}}
    }
}

SCRIPT_SCHEMA = {"type": "json_schema", "json_schema": {"name": "EpisodeScript", "strict": True, "schema": {
    "type": "object", "additionalProperties": False,
    "required": ["title", "description", "tags", "thumbnail_text", "beats", "disclosure"],
    "properties": {
        "title": {"type": "string"}, "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}}, "thumbnail_text": {"type": "string"},
        "disclosure": {"type": "string"},
        "beats": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": [
                "id", "narration", "claim_ids", "purpose", "visual_direction", "source_ids",
                "delivery", "pronunciations"
            ],
            "properties": {
                "id": {"type": "string"}, "narration": {"type": "string", "maxLength": 900},
                "claim_ids": {"type": "array", "items": {"type": "string"}},
                "purpose": {"type": "string", "enum": [
                    "hook", "show_intro", "headlines", "story_intro", "orientation", "context", "test_setup", "model_test", "observation", "evidence",
                    "analysis", "limitation", "comparison", "transition", "implication", "verdict",
                    "weekly_recap", "disclosure", "outro"
                ]},
                "visual_direction": {"type": "string"},
                "source_ids": {"type": "array", "items": {"type": "string"}},
                "delivery": {
                    "type": "object", "additionalProperties": False,
                    "required": ["pace", "energy", "pause_before_ms", "pause_after_ms", "emphasis_words"],
                    "properties": {
                        "pace": {"type": "string", "enum": ["slow", "normal", "quick"]},
                        "energy": {"type": "string", "enum": ["restrained", "normal", "emphatic"]},
                        "pause_before_ms": {"type": "integer"},
                        "pause_after_ms": {"type": "integer"},
                        "emphasis_words": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "pronunciations": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["term", "spoken_as"],
                    "properties": {"term": {"type": "string"}, "spoken_as": {"type": "string"}},
                }},
            },
        }},
    },
}}}

OPENING_LAB_SCHEMA = {"type": "json_schema", "json_schema": {"name": "OpeningLab", "strict": True, "schema": {
    "type": "object", "additionalProperties": False,
    "required": ["candidates", "selected_id", "selection_reason"],
    "properties": {
        "candidates": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "mode", "opening", "claim_ids", "proof_target", "promise", "risk"],
            "properties": {
                "id": {"type": "string"},
                "mode": {"type": "string", "enum": [
                    "verdict_first", "demonstration_first", "relatable_friction",
                    "context_reversal", "roundup_burst"
                ]},
                "opening": {"type": "string"},
                "claim_ids": {"type": "array", "items": {"type": "string"}},
                "proof_target": {"type": "string"},
                "promise": {"type": "string"},
                "risk": {"type": "string"}
            }
        }},
        "selected_id": {"type": "string"},
        "selection_reason": {"type": "string"}
    }
}}}

AUDIENCE_SCHEMA = {"type": "json_schema", "json_schema": {"name": "AudienceTranslation", "strict": True, "schema": {
    "type": "object", "additionalProperties": False,
    "required": ["thesis", "viewer_promise", "why_care", "terms", "examples", "limitations", "unknowns"],
    "properties": {
        "thesis": {"type": "string"}, "viewer_promise": {"type": "string"}, "why_care": {"type": "string"},
        "terms": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["term", "plain_definition"], "properties": {
                "term": {"type": "string"}, "plain_definition": {"type": "string"}
            }}},
        "examples": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["claim_ids", "plain_example"], "properties": {
                "claim_ids": {"type": "array", "items": {"type": "string"}},
                "plain_example": {"type": "string"}
            }}},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "unknowns": {"type": "array", "items": {"type": "string"}},
    },
}}}

OUTLINE_SCHEMA = {"type": "json_schema", "json_schema": {"name": "SpeechOutline", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["chapters"],
    "properties": {"chapters": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "title", "function", "listener_question", "payoff", "claim_ids", "target_words", "visual_mode"],
        "properties": {
            "id": {"type": "string"}, "title": {"type": "string"},
            "function": {"type": "string", "enum": [
                "hook", "show_intro", "headlines", "story", "orientation", "test_setup", "model_test", "result", "limitation", "comparison",
                "implication", "verdict", "weekly_recap", "outro"
            ]},
            "listener_question": {"type": "string"}, "payoff": {"type": "string"},
            "claim_ids": {"type": "array", "items": {"type": "string"}},
            "target_words": {"type": "integer"},
            "visual_mode": {"type": "string", "enum": [
                "source_demo", "source_ui", "comparison", "motion_graphic", "generated_hero", "chapter_card"
            ]},
        },
    }}},
}}}

SECTION_DRAFT_SCHEMA = {"type": "json_schema", "json_schema": {"name": "ResearchedSectionDrafts", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["chapters"],
    "properties": {"chapters": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "spoken_draft", "bridge_to_next", "used_claim_ids", "humor_opportunity"],
        "properties": {
            "id": {"type": "string"}, "spoken_draft": {"type": "string"},
            "bridge_to_next": {"type": "string"},
            "used_claim_ids": {"type": "array", "items": {"type": "string"}},
            "humor_opportunity": {"type": "string"},
        },
    }}},
}}}

QUALITY_SCHEMA = {"type": "json_schema", "json_schema": {"name": "SpokenScriptQuality", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["passed", "scores", "issues"],
    "properties": {
        "passed": {"type": "boolean"},
        "scores": {"type": "object", "additionalProperties": False,
            "required": [
                "clarity", "natural_speech", "useful_density", "continuity", "originality",
                "visual_proof", "teaching_value", "promise_delivery", "voice_consistency",
            ],
            "properties": {name: {"type": "integer"} for name in [
                "clarity", "natural_speech", "useful_density", "continuity", "originality",
                "visual_proof", "teaching_value", "promise_delivery", "voice_consistency",
            ]}},
        "issues": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["beat_id", "category", "severity", "explanation", "rewrite_instruction"],
            "properties": {
                "beat_id": {"type": "string"},
                "category": {"type": "string", "enum": [
                    "jargon", "confusing_reference", "repetition", "hype", "weak_transition",
                    "unsupported", "visual_gap", "imitative", "written_not_spoken", "teaching_gap",
                    "promise_gap", "voice_drift"
                ]},
                "severity": {"type": "string", "enum": ["minor", "major", "blocking"]},
                "explanation": {"type": "string"}, "rewrite_instruction": {"type": "string"},
            }}},
    },
}}}

HUMANIZE_SCHEMA = {"type": "json_schema", "json_schema": {"name": "HumanSpokenRewrite", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["beats"],
    "properties": {"beats": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "narration", "delivery"],
        "properties": {
            "id": {"type": "string"},
            # Length is validated locally because strict-output provider support
            # for maxLength/maxItems is inconsistent across routes.
            "narration": {"type": "string"},
            "delivery": {
                "type": "object", "additionalProperties": False,
                "required": ["pace", "energy", "pause_before_ms", "pause_after_ms", "emphasis_words"],
                "properties": {
                    "pace": {"type": "string", "enum": ["slow", "normal", "quick"]},
                    "energy": {"type": "string", "enum": ["restrained", "normal", "emphatic"]},
                    # Some OpenRouter providers reject numeric bounds in strict
                    # structured-output schemas. Pydantic enforces 0-2500 after
                    # receipt, preserving the same contract portably.
                    "pause_before_ms": {"type": "integer"},
                    "pause_after_ms": {"type": "integer"},
                    "emphasis_words": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    }}},
}}}

VERIFY_SCHEMA = {"type": "json_schema", "json_schema": {"name": "ScriptVerification", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["passed", "unsupported", "corrections", "visual_gaps"],
    "properties": {
        "passed": {"type": "boolean"},
        "unsupported": {"type": "array", "items": {"type": "string"}},
        "corrections": {"type": "array", "items": {"type": "string"}},
        "visual_gaps": {"type": "array", "items": {"type": "string"}},
    },
}}}


def _source_payload(sources: list[Source], include_text: bool = False) -> list[dict]:
    fields = [
        "id", "title", "url", "publisher", "published_at", "source_type", "signal_role", "category",
        "summary", "cluster_id", "entities", "trend_score", "importance_score",
    ]
    if include_text:
        fields.append("text")
    return [{key: source.model_dump(mode="json").get(key) for key in fields} for source in sources]


def _validate_slate(data: dict, sources: list[Source]) -> list[Brief]:
    valid_ids = {source.id for source in sources}
    source_by_id = {source.id: source for source in sources}
    result = []
    used_clusters: set[str] = set()
    fingerprints: set[tuple[str, ...]] = set()
    for item in data["briefs"]:
        if len(item["source_ids"]) < 2:
            raise ValueError(f"slate brief needs at least two sources: {item['title']}")
        if not set(item["source_ids"]).issubset(valid_ids):
            raise ValueError(f"slate returned unknown source ids for {item['title']}")
        clusters = {source_by_id[source_id].cluster_id for source_id in item["source_ids"] if source_by_id[source_id].cluster_id}
        overlap = clusters & used_clusters
        if overlap:
            raise ValueError(f"weekly slate reuses story clusters for {item['title']}: {sorted(overlap)}")
        entities = sorted({
            entity.casefold() for source_id in item["source_ids"]
            for entity in source_by_id[source_id].entities if entity.casefold() not in {"ai", "api"}
        })[:8]
        fingerprint = tuple(entities)
        if fingerprint and fingerprint in fingerprints:
            raise ValueError(f"weekly slate repeats an entity fingerprint for {item['title']}")
        used_clusters.update(clusters)
        fingerprints.add(fingerprint)
        result.append(Brief(**item, claim_ids=[]))
    if len(result) != 7:
        raise ValueError(f"weekly slate returned {len(result)} briefs instead of exactly 7")
    if len({brief.title.lower() for brief in result}) != 7:
        raise ValueError("weekly slate contains duplicate titles")
    return result


def plan_weekly_slate(sources: list[Source], recent_topics: list[str] | None = None) -> list[Brief]:
    correction = ""
    last_error: ValueError | None = None
    for _attempt in range(3):
        data = call_openrouter(
            OPENROUTER_MODEL,
            "You are the evidence-first executive editor for a transparent Magic Hour-affiliated AI media channel. "
            "Choose materially distinct episodes, favor primary sources and visually demonstrable developments, and never invent facts.",
            "Create exactly seven 8-12 minute episode briefs for the coming week. Use a curated mix of formats. "
            "Every brief must cite at least two source IDs that exist in SOURCES. Avoid the RECENT TOPICS, never reuse a story cluster "
            "across two briefs, and make all seven titles distinct.\n"
            f"{correction}\n\nRECENT TOPICS:\n{json.dumps(recent_topics or [])}\n\n"
            f"SOURCES:\n{json.dumps(_source_payload(sources))}",
            SLATE_SCHEMA,
        )
        try:
            return _validate_slate(data, sources)
        except ValueError as exc:
            last_error = exc
            correction = f"The previous slate failed validation: {exc}. Correct that exact defect in the replacement slate."
    raise RuntimeError(f"weekly slate failed local quality validation after 3 attempts: {last_error}")


def extract_claims(brief: Brief, sources: list[Source]) -> list[Claim]:
    selected = [source for source in sources if source.id in brief.source_ids]
    data = call_openrouter(
        OPENROUTER_VERIFY_MODEL,
        "You are a meticulous fact editor. Extract only claims directly supported by the supplied source text. "
        "Do not use outside knowledge. Cover every supplied story cluster. Mark a claim disputed when sources conflict or when it relies "
        "only on community or newsletter reporting; those lead sources must not be presented as confirmation.",
        f"BRIEF:\n{brief.model_dump_json()}\n\nSOURCES:\n{json.dumps(_source_payload(selected, include_text=True))}",
        CLAIMS_SCHEMA,
        temperature=0.1,
    )
    valid_ids = {source.id for source in selected}
    claims = [Claim.model_validate(item) for item in data["claims"]]
    if len(claims) < 8:
        raise ValueError(f"claim extraction returned {len(claims)} claims; at least 8 are required")
    for claim in claims:
        if not set(claim.source_ids).issubset(valid_ids):
            raise ValueError(f"claim {claim.id} references an unknown source")
        evidence_sources = [source for source in selected if source.id in claim.source_ids]
        if evidence_sources and all(source.signal_role in {"newsletter_lead", "community_signal"} for source in evidence_sources):
            claim.disputed = True
        if claim.disputed and len(set(claim.source_ids)) < 2:
            claim.text = "Reported but not independently confirmed: " + claim.text
    selected_clusters = {source.cluster_id for source in selected if source.cluster_id}
    covered_clusters = {
        source.cluster_id for claim in claims for source in selected
        if source.id in claim.source_ids and source.cluster_id
    }
    missing_clusters = selected_clusters - covered_clusters
    if missing_clusters:
        raise ValueError(f"claim extraction omitted weekly story clusters: {sorted(missing_clusters)}")
    return claims


def duration_profile(project: EpisodeProject) -> dict[str, Any]:
    """Return editorial limits for standard episodes and explicitly requested short specials."""
    target_minutes = float(project.episode.get("target_minutes", 10))
    if target_minutes < 1:
        return {
            "target_minutes": target_minutes, "word_min": 65, "word_max": 80,
            "beat_min": 6, "beat_max": 7, "chapter_min": 5, "chapter_max": 7,
            "outline_target": 74,
            "voice_words_per_minute": float(project.episode.get("voice_words_per_minute", 0) or 0),
        }
    if target_minutes <= 6:
        calibrated_wpm = float(project.episode.get("voice_words_per_minute", 0) or 0)
        if calibrated_wpm:
            center = round(target_minutes * calibrated_wpm)
            # The real audio duration remains the hard gate. Keep enough latitude for
            # a concise verified rewrite, then measure the cloned voice again.
            word_min = max(360, round(center * 0.86))
            word_max = max(word_min + 30, round(center * 1.06))
            return {
                "target_minutes": target_minutes, "word_min": word_min, "word_max": word_max,
                "beat_min": 14, "beat_max": 18, "chapter_min": 5, "chapter_max": 7,
                "outline_target": center, "voice_words_per_minute": calibrated_wpm,
            }
        return {
            "target_minutes": target_minutes, "word_min": 600, "word_max": 840,
            "beat_min": 14, "beat_max": 18, "chapter_min": 5, "chapter_max": 7,
            "outline_target": 750,
        }
    return {
        "target_minutes": target_minutes, "word_min": MIN_SCRIPT_WORDS, "word_max": MAX_SCRIPT_WORDS,
        "beat_min": 24, "beat_max": 30, "chapter_min": 7, "chapter_max": 11,
        "outline_target": 1450,
    }


def _validate_opening_lab(data: dict[str, Any], project: EpisodeProject) -> dict[str, Any]:
    """Reject generic or unsupported opening candidates before full-script drafting."""
    candidates = data.get("candidates", [])
    if len(candidates) != 4:
        raise ValueError(f"opening lab returned {len(candidates)} candidates instead of exactly 4")
    ids = [str(candidate.get("id", "")) for candidate in candidates]
    if len(set(ids)) != len(ids) or any(not item for item in ids):
        raise ValueError("opening candidate IDs must be non-empty and unique")
    if data.get("selected_id") not in ids:
        raise ValueError("selected opening ID does not match a candidate")
    modes = [candidate.get("mode") for candidate in candidates]
    if len(set(modes)) < 3:
        raise ValueError("opening candidates do not explore at least three distinct modes")
    allowed_claims = {claim.id for claim in project.claims}
    short_canary = float(project.episode.get("target_minutes", 10)) < 1
    minimum, maximum = ((8, 24) if short_canary else (30, 68))
    for candidate in candidates:
        words = len(str(candidate.get("opening", "")).split())
        if not minimum <= words <= maximum:
            raise ValueError(
                f"opening candidate {candidate.get('id')} is {words} words; required {minimum}-{maximum}"
            )
        claim_ids = set(candidate.get("claim_ids", []))
        if not claim_ids:
            raise ValueError(f"opening candidate {candidate.get('id')} has no evidence claim")
        unknown = claim_ids - allowed_claims
        if unknown:
            raise ValueError(f"opening candidate {candidate.get('id')} uses unknown claims: {sorted(unknown)}")
    return data


def build_opening_lab(
    project: EpisodeProject, *, evidence: dict[str, Any], audience: dict[str, Any],
    promise_contract: dict[str, Any], format_playbook: dict[str, Any],
    voice_profile: dict[str, Any], conversational_profile: dict[str, Any],
) -> dict[str, Any]:
    """Generate and compare four truthful openings before committing to one script."""
    correction = ""
    last_error: ValueError | None = None
    for _attempt in range(3):
        data = call_openrouter(
            OPENROUTER_VERIFY_MODEL,
            "You are an opening editor for an original evidence-led technology channel. Explore different "
            "story mechanisms without imitating a creator's wording, catchphrases, jokes, or persona.",
            "Write exactly four materially different spoken opening candidates, using at least three supplied opening modes. "
            "Each candidate must be supported by one or more supplied claim IDs, state or imply one answerable promise, and point "
            "to proof the edit can show quickly. Prefer a named result, concrete friction, visible demonstration, or meaningful "
            "reversal over adjectives. A roundup may preview several developments, but it still needs a clear priority. "
            "Select the candidate that best balances specificity, early proof, freshness, clarity, and speakability. "
            "Do not use greetings, stock suspense, generic excitement, or copied creator language. Return only the schema."
            + correction
            + "\n\nCONVERSATIONAL PROFILE:\n" + json.dumps(conversational_profile)
            + "\n\nVOICE PROFILE:\n" + json.dumps(voice_profile)
            + "\n\nPROMISE CONTRACT:\n" + json.dumps(promise_contract)
            + "\n\nFORMAT PLAYBOOK:\n" + json.dumps(format_playbook)
            + "\n\nAUDIENCE TRANSLATION:\n" + json.dumps(audience)
            + "\n\nEVIDENCE:\n" + json.dumps(evidence),
            OPENING_LAB_SCHEMA,
            temperature=0.7,
        )
        try:
            return _validate_opening_lab(data, project)
        except ValueError as exc:
            last_error = exc
            correction = (
                "\nThe previous opening set failed validation: " + str(exc)
                + ". Replace the entire set and correct that exact defect."
            )
    raise RuntimeError(f"opening lab failed local validation after 3 attempts: {last_error}")


def build_editorial_plan(project: EpisodeProject) -> dict[str, Any]:
    """Translate research into a listener-first argument before prose is written."""
    if not project.brief or not project.claims:
        raise ValueError("approved brief and claims are required before editorial planning")
    evidence = {
        "brief": project.brief.model_dump(mode="json"),
        "claims": [claim.model_dump(mode="json") for claim in project.claims],
        "sources": _source_payload(project.sources),
        "weekly_digest": project.episode.get("digest_plan", {}),
    }
    audience = call_openrouter(
        OPENROUTER_MODEL,
        "You are a senior explainer editor. Translate technical AI-media news for a smart general audience. "
        "Use only supplied evidence, distinguish verified facts from uncertainty, and avoid marketing language.",
        "Create the audience translation that a writer must understand before drafting. Define only terms that "
        "are genuinely necessary, give concrete examples tied to claim IDs, and state real limitations and unknowns.\n\n"
        + json.dumps(evidence),
        AUDIENCE_SCHEMA,
        temperature=0.25,
    )
    voice_profile = load_editorial_voice_profile()
    conversational_profile = load_conversational_script_profile()
    promise_contract = {
        "viewer_question": audience["why_care"],
        "promised_payoff": audience["viewer_promise"],
        "opening_contract": (
            "the first beat states a concrete consequence or visible result and makes one answerable promise; "
            "it does not greet, advertise, or manufacture mystery"
        ),
        "proof_deadline": "show the first source-backed proof, result, or example within the first 45 seconds",
        "section_contract": (
            "each chapter opens a useful question, supplies evidence that changes the listener's understanding, "
            "and exits with a consequence or decision—not a mini-summary"
        ),
        "ending_contract": (
            "resolve the opening promise with a reusable judgment, decision rule, or bounded conclusion"
        ),
    }
    teaching_contract = {
        "audience": "smart generalist who follows AI but may not know the underlying technical term",
        "learning_goal": audience["viewer_promise"],
        "chapter_loop": [
            "pose one concrete viewer question",
            "explain the minimum concept needed",
            "show source evidence or a real example",
            "translate what the evidence changes",
            "state the boundary, tradeoff, or uncertainty",
            "land one memorable takeaway",
        ],
        "retention_rule": "earn attention with a new piece of proof, a useful example, or a changed conclusion every 45-75 seconds",
        "language_rule": "example before abstraction; define a term in one plain sentence at first use",
        "ending_rule": "finish with a reusable mental model or decision rule, not a generic recap or subscribe request",
        "hidden_story_logic": "state the change, explain only what is needed, show a concrete example, then land the implication; never announce these steps",
        "hook_selection": [
            "result first when a real output or failure is visible",
            "relatable friction when the evidence documents a familiar creator problem",
            "curiosity gap only when the promised answer is delivered in the episode",
        ],
        "humor_rule": (
            "humor must grow from a documented contradiction, inconvenience, limitation, or recognizable human behavior; "
            "one short line is enough and an empty humor opportunity is better than a forced joke"
        ),
        "voice_rule": "sound like one informed person thinking clearly, not a host reading headings or a model filling a template",
        "promise_contract": promise_contract,
        "writer_room_workflow": [
            "lock the viewer promise and evidence boundary",
            "build the researched chapter blueprint",
            "draft sections against only their assigned claims",
            "unify the sections into one speaker and one argument",
            "perform a fact-locked read-aloud line edit",
            "run independent promise, voice, clarity, evidence, and retention review",
        ],
        "show_rule": (
            "for The Week in AI, use a rapid consequence-first cold open, a two-to-four second branded welcome, distinct story chapters, "
            "and a brief closing watch-list; never read a stack of headlines without explaining why each one matters"
        ),
        "reference_style_findings": {
            "research_basis": [
                "AI Search public video transcripts and chapter structures",
                "AI LABS public video transcripts, descriptions, and chapter structures",
            ],
            "borrow_structure_not_voice": (
                "use the successful explanatory mechanics while keeping wording, jokes, transitions, catchphrases, "
                "persona, and branding original"
            ),
            "fast_news_loop": [
                "name the concrete change",
                "explain it in the simplest accurate sentence",
                "show a visible example or source detail",
                "translate the consequence for a normal user",
                "state the most important limitation",
                "leave on a useful verdict or open question",
            ],
            "deep_explainer_loop": [
                "open with a real consequence or surprising contrast",
                "delay jargon until after the viewer understands the problem",
                "use one specific human or workflow example",
                "explain the mechanism through that example",
                "give a practical framework or decision rule",
                "address the strongest reasonable objection",
            ],
            "spoken_cadence": (
                "favor 8-18 word sentences, use an occasional short landing line, keep referents explicit, "
                "and allow brief pauses after visible proof rather than filling every second"
            ),
            "anti_template_rule": (
                "do not copy recurring creator lines such as AI never sleeps, this week was insane, the awesome thing is, "
                "or repeated also-this-week and link-in-the-description transitions"
            ),
        },
    }
    format_playbooks = {
        "tool_test": {
            "opening": "show the most useful result or surprising failure before explaining the setup",
            "proof_order": ["identical input", "visible output", "failure case", "best use case", "verdict"],
            "required_test_ledger": [
                "exact input or prompt", "model and settings", "captured output", "evaluation rule", "limitations",
            ],
            "decision_axes": [
                "prompt adherence", "temporal consistency", "camera control", "text integrity", "usable-output rate",
            ],
            "honesty_rule": "use first-person testing language only when all test-ledger fields exist in the evidence package",
        },
        "deep_dive": {
            "opening": "show the consequence first, then reveal the mechanism",
            "proof_order": ["observable change", "primary evidence", "plain-language mechanism", "limit", "decision rule"],
        },
        "roundup": {
            "opening": "lead with the one development that changes a viewer decision",
            "proof_order": ["impact ranking", "evidence per item", "connection between items", "what to ignore", "decision rule"],
        },
        "weekly_roundup": {
            "opening": "cold-open on the biggest consequence, flash the other two strongest stories, then say Welcome to The Week in AI once",
            "proof_order": [
                "three-headline cold open", "brief branded welcome", "ranked story chapters", "captured model tests where approved",
                "what was overhyped", "next-week watch list",
            ],
            "story_rule": "each story gets change, proof, human consequence, one honest limitation, and a clean handoff in roughly 55-100 seconds",
            "test_rule": "only call something a hands-on test when the digest plan marks it as a model-test candidate and captured output exists",
            "humor_rule": "use dry observations about real product friction or industry behavior; never joke over layoffs, safety incidents, or personal harm",
            "brand_line": "Welcome to News Weekly—the ten-minute recap of the tech and AI news actually worth knowing.",
        },
        "open_source_spotlight": {
            "opening": "show a working output before repository details",
            "proof_order": ["output", "real setup", "license and requirements", "failure boundary", "who should use it"],
        },
        "trend_explainer": {
            "opening": "start with a concrete example that makes the trend visible",
            "proof_order": ["example", "pattern", "counterexample", "mechanism", "what would change the conclusion"],
        },
    }
    format_playbook = format_playbooks[project.brief.episode_format]
    opening_lab = build_opening_lab(
        project,
        evidence=evidence,
        audience=audience,
        promise_contract=promise_contract,
        format_playbook=format_playbook,
        voice_profile=voice_profile,
        conversational_profile=conversational_profile,
    )
    profile = duration_profile(project)
    outline = call_openrouter(
        OPENROUTER_MODEL,
        "You are the story editor for an original evidence-led educational AI-media channel. Build a learning journey "
        "with proof, not a list of headlines. Never imitate another creator's wording or persona.",
        f"Build {profile['chapter_min']}-{profile['chapter_max']} chapters for a {profile['target_minutes']:g}-minute spoken episode. "
        "Reveal a real result, consequence, or failure in the opening, then move from a concrete puzzle to the minimum concept, "
        "evidence, implication, limitation, and a useful takeaway. For weekly_roundup, preserve the ranked story order from WEEKLY DIGEST, "
        "give every selected story its own chapter, and place the show intro immediately after the cold open. "
        "Each chapter must answer a listener question and "
        "earn its payoff with a cited test, source, comparison, limitation, or implication. Put a proof/example at "
        "least every 75 seconds. Introduce no more than one genuinely new technical idea per chapter. Use repository pages, source demos, UI captures, charts, and restrained local diagrams; do not plan generative visual filler. "
        f"Target about {profile['outline_target']} total words across chapters.\n\n"
        f"TEACHING CONTRACT:\n{json.dumps(teaching_contract)}\n\nVOICE PROFILE:\n{json.dumps(voice_profile)}\n\n"
        f"CONVERSATIONAL PROFILE:\n{json.dumps(conversational_profile)}\n\nOPENING LAB:\n{json.dumps(opening_lab)}\n\n"
        f"FORMAT PLAYBOOK:\n{json.dumps(format_playbook)}\n\n"
        f"AUDIENCE TRANSLATION:\n{json.dumps(audience)}\n\nEVIDENCE:\n{json.dumps(evidence)}",
        OUTLINE_SCHEMA,
        temperature=0.35,
    )
    if not profile["chapter_min"] <= len(outline["chapters"]) <= profile["chapter_max"]:
        raise ValueError(
            f"editorial outline returned {len(outline['chapters'])} chapters; required "
            f"{profile['chapter_min']}-{profile['chapter_max']}"
        )
    target_words = sum(item["target_words"] for item in outline["chapters"])
    if not profile["word_min"] <= target_words <= profile["word_max"]:
        scale = profile["outline_target"] / max(1, target_words)
        for item in outline["chapters"]:
            item["target_words"] = max(40, min(320, round(item["target_words"] * scale)))
    project.editorial_plan = {
        "audience": audience,
        "voice_profile": voice_profile,
        "conversational_profile": conversational_profile,
        "opening_lab": opening_lab,
        "promise_contract": promise_contract,
        "teaching_contract": teaching_contract,
        "format_playbook": format_playbook,
        "outline": outline,
        "method_provenance": method_provenance_for("script") + [
            {
                "source": "https://www.youtube.com/@theAIsearch",
                "adapted_pattern": (
                    "eighteen-video transcript-backed study of verdict-first, demonstration-first, friction-first, "
                    "roundup-burst, and context-reversal openings; no copied wording, catchphrases, or persona"
                ),
            },
            {
                "source": "https://www.youtube.com/@AILABS-393",
                "adapted_pattern": "consequence-first hooks, concrete workflow stories, mechanisms, and practical frameworks",
            },
        ],
    }
    return project.editorial_plan


def draft_researched_sections(project: EpisodeProject) -> dict[str, Any]:
    """Draft chapters independently from their evidence before the final voice pass."""
    if not project.editorial_plan:
        build_editorial_plan(project)
    chapters = project.editorial_plan["outline"]["chapters"]
    evidence = {
        "brief": project.brief.model_dump(mode="json") if project.brief else {},
        "audience": project.editorial_plan["audience"],
        "teaching_contract": project.editorial_plan["teaching_contract"],
        "voice_profile": project.editorial_plan.get("voice_profile", load_editorial_voice_profile()),
        "conversational_profile": project.editorial_plan.get(
            "conversational_profile", load_conversational_script_profile()
        ),
        "opening_lab": project.editorial_plan.get("opening_lab", {}),
        "promise_contract": project.editorial_plan.get("promise_contract", {}),
        "chapters": chapters,
        "claims": {claim.id: claim.model_dump(mode="json") for claim in project.claims},
        "sources": _source_payload(project.sources),
    }
    result = call_openrouter(
        OPENROUTER_MODEL,
        "You are a research-backed YouTube section writer. Work only from supplied evidence. Write for speech, not an article. "
        "Do not imitate any creator, invent testing, or add names, numbers, dates, benchmarks, or product behavior.",
        "Draft each chapter separately before the final script is stitched together. Match its target word count within about 20 percent. "
        "Treat the chapter as a compact spoken beat: a useful question or tension, its evidence-backed delivery, then a bridge caused by the "
        "meaning of that evidence. Open in the middle of a useful thought, not with a heading, reset, recap, or generic mini-hook. "
        "Use a concrete example before technical language. "
        "For fast news, draft the hidden sequence change, plain explanation, visible example, consequence, limitation, and verdict. "
        "For a deeper explainer, use consequence, specific human example, mechanism, practical rule, and strongest objection. "
        "These are reasoning sequences, never spoken labels. "
        "The bridge should create logical momentum without saying next, moving on, that brings us to, speaking of, or here's where it gets interesting. "
        "Follow the supplied voice profile, but do not force every listed trait into every paragraph. Variation is more human than compliance theater. "
        "Use the selected opening mode as the episode's entry point, then let the explanation feel like a real thought unfolding: "
        "specific thing, honest reaction, plain translation, proof, and what that proof changes. Do not turn those into labels. "
        "The humor_opportunity must be empty unless a supplied fact contains a real contradiction, inconvenience, limitation, or relatable "
        "behavior. When present, describe the comic observation in plain language; do not write a canned punchline. Do not conclude individual "
        "sections. Return only the schema.\n\n" + json.dumps(evidence),
        SECTION_DRAFT_SCHEMA,
        temperature=0.5,
    )
    expected_ids = [chapter["id"] for chapter in chapters]
    returned_ids = [chapter.get("id", "") for chapter in result.get("chapters", [])]
    if returned_ids != expected_ids:
        raise ValueError("section drafting changed, reordered, or omitted outline chapter IDs")
    outline_by_id = {chapter["id"]: chapter for chapter in chapters}
    for chapter in result["chapters"]:
        outline_chapter = outline_by_id[chapter["id"]]
        unknown = set(chapter["used_claim_ids"]) - set(outline_chapter["claim_ids"])
        if unknown:
            raise ValueError(f"section {chapter['id']} introduced claims outside its outline: {sorted(unknown)}")
        target = int(outline_chapter["target_words"])
        actual = len(chapter["spoken_draft"].split())
        minimum = 4
        maximum = max(80, round(target * 3.0))
        if not minimum <= actual <= maximum:
            raise ValueError(f"section {chapter['id']} is {actual} words for a {target}-word allocation")
    return result


def _spoken_quality_report(script: Script, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Measure whether a fact-locked script will still sound natural out loud."""
    failures: list[str] = []
    metrics: dict[str, Any] = {}
    profile = profile or {
        "beat_min": 24, "beat_max": 30, "word_min": MIN_SCRIPT_WORDS, "word_max": MAX_SCRIPT_WORDS,
    }
    short_canary = float(profile.get("target_minutes", 10)) < 1
    if not profile["beat_min"] <= len(script.beats) <= profile["beat_max"]:
        failures.append(
            f"beat count is {len(script.beats)}; required {profile['beat_min']}-{profile['beat_max']} spoken segments"
        )
    if not profile["word_min"] <= script.word_count <= profile["word_max"]:
        failures.append(f"word count is {script.word_count}; required {profile['word_min']}-{profile['word_max']}")
    narration_lower = script.narration.casefold()
    template_phrases = [
        "next question", "observation:", "analysis:", "what worked", "what failed",
        "the source adds", "the guidance splits", "first, the timing", "now the next question",
        "the practical question becomes simple", "here's the practical checklist",
    ]
    found_templates = [phrase for phrase in template_phrases if phrase in narration_lower]
    if found_templates:
        failures.append("template-like narration phrases: " + ", ".join(found_templates))
    ai_cliches = [
        "let's dive in", "here's where things get interesting", "but here's the thing",
        "in today's rapidly evolving", "rapidly evolving landscape", "game-changer",
        "it remains to be seen", "at its core", "the world of ai", "delve into",
        "this isn't just", "the key takeaway is", "only time will tell",
        "you might be wondering", "the answer might surprise you", "let that sink in",
        "in a world where", "imagine a world", "what does this mean for you",
        "revolutionary", "unlock the power", "seamlessly integrates", "welcome back",
        "in this video we're going to", "in this video we are going to",
        "ai never sleeps", "this week has been absolutely insane", "this week was absolutely insane",
        "the awesome thing is", "what a time to be alive", "you won't believe",
        "so buckle up", "without further ado", "everything you need to know",
        "this changes everything", "that brings us to", "speaking of which",
        "the bottom line is", "needless to say", "it's safe to say",
    ]
    found_cliches = [phrase for phrase in ai_cliches if phrase in narration_lower]
    if found_cliches:
        failures.append("AI-script cliches: " + ", ".join(found_cliches))
    mechanical_contrasts = re.findall(
        r"\b(?:isn't|is not|wasn't|was not)\b[^.!?]{0,90}\b(?:but|it's)\b",
        narration_lower,
    )
    if len(mechanical_contrasts) > max(2, round(script.word_count / 500)):
        failures.append(f"repeated mechanical 'not X but Y' construction appears {len(mechanical_contrasts)} times")
    source_signposts = sum(narration_lower.count(phrase) for phrase in ["the source", "the guidance", "the documents"])
    if source_signposts > max(2, len(script.beats) // 6):
        failures.append(
            f"source-centered signposting appears {source_signposts} times; explain the story directly instead"
        )
    repetitive_handoffs = sum(
        narration_lower.count(phrase)
        for phrase in ["also this week", "if you're interested", "link in the description", "description below"]
    )
    if repetitive_handoffs > max(2, round(script.word_count / 450)):
        failures.append(
            f"repetitive creator-style handoffs appear {repetitive_handoffs} times; use causal transitions and clean cuts"
        )
    discourse_starters = re.findall(
        r"(?:^|[.!?]\s+)(so|now|okay|look|honestly|basically)[,:]?\s+",
        narration_lower,
    )
    metrics["discourse_starters"] = len(discourse_starters)
    if len(discourse_starters) > max(3, round(script.word_count / 300)):
        failures.append(
            f"conversational filler starts {len(discourse_starters)} sentences; keep only the ones that carry meaning"
        )
    essay_connectors = re.findall(
        r"(?:^|[.!?]\s+)(?:moreover|furthermore|additionally|consequently|nevertheless|in conclusion)\b",
        narration_lower,
    )
    metrics["essay_connectors"] = len(essay_connectors)
    if len(essay_connectors) > max(1, round(script.word_count / 650)):
        failures.append(
            f"formal essay connectors appear {len(essay_connectors)} times; rewrite the logic as natural spoken causality"
        )
    if script.beats:
        hook_words = len(script.beats[0].narration.split())
        hook_min, hook_max = (8, 18) if short_canary else (35, 65)
        if not hook_min <= hook_words <= hook_max:
            failures.append(f"hook is {hook_words} words; required {hook_min}-{hook_max}")
    long_sentences: list[str] = []
    sentence_lengths: list[int] = []
    openers: Counter[str] = Counter()
    for beat in script.beats:
        words = beat.narration.split()
        minimum_words = 6 if short_canary else (12 if beat.purpose == "show_intro" else 20)
        maximum_words = 24 if short_canary else 80
        if not minimum_words <= len(words) <= maximum_words:
            failures.append(
                f"{beat.id} is {len(words)} words; spoken segments must be "
                f"{minimum_words}-{maximum_words} for {beat.purpose}"
            )
        opener = " ".join(word.casefold().strip(".,:;!?—–\"") for word in words[:3])
        if opener:
            openers[opener] += 1
        for sentence in re.split(r"(?<=[.!?])\s+", beat.narration.strip()):
            count = len(sentence.split())
            if count:
                sentence_lengths.append(count)
            # A hard 24-word ceiling was rejecting otherwise natural spoken
            # sentences by a single word. Twenty-eight keeps breath groups
            # readable while avoiding brittle rewrite loops.
            if count > 36:
                long_sentences.append(f"{beat.id}:{count}")
    if long_sentences:
        failures.append("sentences over 36 words: " + ", ".join(long_sentences[:8]))
    if sentence_lengths:
        average = sum(sentence_lengths) / len(sentence_lengths)
        metrics["average_sentence_words"] = round(average, 2)
        if not 8 <= average <= 19:
            failures.append(f"average sentence length is {average:.1f}; target 8-19 words")
        if len(sentence_lengths) >= 12:
            variance = sum((value - average) ** 2 for value in sentence_lengths) / len(sentence_lengths)
            metrics["sentence_length_spread"] = round(variance ** 0.5, 2)
            if variance ** 0.5 < 3.0:
                failures.append("sentence rhythm is too uniform; vary short landings and fuller explanations")
        short_landings = sum(value <= 7 for value in sentence_lengths)
        medium_explanations = sum(14 <= value <= 24 for value in sentence_lengths)
        metrics["short_landings"] = short_landings
        metrics["medium_explanations"] = medium_explanations
        if script.word_count >= 600 and short_landings == 0:
            failures.append("long-form narration has no brief landing sentences; the spoken rhythm feels written")
    repeated = [text for text, count in openers.items() if count >= 3]
    if repeated:
        failures.append("repeated beat openers: " + ", ".join(repeated[:5]))
    normalized_words = re.findall(r"[a-z0-9]+", narration_lower)
    repeated_five_grams = [
        " ".join(words) for words, count in Counter(
            tuple(normalized_words[index:index + 5])
            for index in range(max(0, len(normalized_words) - 4))
        ).items()
        if count >= 3 and len(set(words)) >= 3
    ]
    metrics["repeated_five_word_phrases"] = repeated_five_grams[:8]
    if repeated_five_grams:
        failures.append("repeated five-word script templates: " + ", ".join(repeated_five_grams[:4]))
    # Spoken drafts often use typographic apostrophes. Count both forms so a
    # perfectly natural "don’t" is not falsely rejected as formal prose.
    contractions = re.findall(
        r"\b[\w]+(?:n['’]t|['’]re|['’]ve|['’]ll|['’]d|['’]m)\b",
        script.narration,
        flags=re.IGNORECASE,
    )
    if script.word_count >= 600 and len(contractions) < 3:
        failures.append(
            f"only {len(contractions)} natural contractions in {script.word_count} words; spoken delivery is too formal"
        )
    questions = sum(beat.narration.count("?") for beat in script.beats)
    if questions > max(4, round(script.word_count / 160)):
        failures.append(f"rhetorical-question count is {questions}; use them more selectively")
    factual = {"hook", "headlines", "story_intro", "context", "test_setup", "model_test", "observation", "evidence", "comparison"}
    for beat in script.beats:
        if beat.purpose in factual and not beat.claim_ids:
            failures.append(f"{beat.id} is a factual {beat.purpose} beat without claim IDs")

    # A claimed hands-on experience is much more persuasive than a summary, so
    # it needs an actual test beat rather than wording that only sounds tested.
    first_person_test = re.findall(
        r"\b(?:i|we)\s+(?:tested|tried|ran|generated|compared|used)\b",
        narration_lower,
    )
    documented_tests = sum(beat.purpose == "model_test" for beat in script.beats)
    if first_person_test and not documented_tests:
        failures.append("first-person testing language appears without a documented model_test beat")

    # Avoid a script that is technically grammatical yet offers only hype and
    # pronouns. These phrases are intentionally narrow so honest commentary is
    # not penalized for sounding conversational.
    hype = re.findall(
        r"\b(?:insane|crazy|wild|massive|huge|mind[- ]blowing|unbelievable)\b",
        narration_lower,
    )
    metrics["hype_words"] = len(hype)
    if len(hype) > max(1, round(script.word_count / 700)):
        failures.append("hype language is doing too much of the explanatory work")
    vague_openers = re.findall(r"(?:^|[.!?]\s+)(?:this|it|they|that)\b", narration_lower)
    metrics["vague_sentence_openers"] = len(vague_openers)
    if len(vague_openers) > max(4, round(len(sentence_lengths) * 0.22)):
        failures.append("too many sentences open with vague pronouns; name the subject before explaining it")

    jargon_terms = (
        "quantization", "tokenizer", "latent", "inference", "checkpoint", "fine-tuning",
        "distillation", "parameter", "diffusion", "multimodal",
    )
    unexplained_jargon = []
    for sentence in re.split(r"(?<=[.!?])\s+", narration_lower):
        for term in jargon_terms:
            if term in sentence and not re.search(r"\b(?:means|meaning|basically|in plain|that is|which is)\b", sentence):
                unexplained_jargon.append(term)
    metrics["unexplained_jargon_terms"] = sorted(set(unexplained_jargon))
    if len(set(unexplained_jargon)) >= 3:
        failures.append("several technical terms arrive without plain-English definitions")
    metrics["spoken_segments"] = len(script.beats)
    return {"failures": failures, "metrics": metrics}


def _spoken_quality_failures(script: Script, profile: dict[str, Any] | None = None) -> list[str]:
    """Compatibility wrapper for deterministic oral-edit checks."""
    return _spoken_quality_report(script, profile)["failures"]


def review_script_quality(project: EpisodeProject) -> dict[str, Any]:
    if not project.script:
        raise ValueError("script is required")
    oral_report = _spoken_quality_report(project.script, duration_profile(project))
    deterministic = oral_report["failures"]
    voice_profile = project.editorial_plan.get("voice_profile", load_editorial_voice_profile())
    conversational_profile = project.editorial_plan.get(
        "conversational_profile", load_conversational_script_profile()
    )
    promise_contract = project.editorial_plan.get("promise_contract", {})
    data = call_openrouter(
        OPENROUTER_VERIFY_MODEL,
        "You are an independent spoken-language editor. Judge whether this sounds like an original, clear human "
        "explaining evidence to another human. Penalize jargon, vague references, hype, repetitive cadence, copied "
        "creator mannerisms, and visuals that merely decorate rather than prove the narration.",
        "Score the script as spoken audio, not as an article. A 9 in natural_speech means a listener could reasonably "
        "believe a thoughtful human YouTube writer composed and read it aloud. Clarity, natural_speech, promise_delivery, "
        "and voice_consistency must be at least 9; every other score must be at least 8. Any major or blocking issue fails "
        "the script. Reject policy-memo "
        "language, mechanical signposts, repetitive sentence shapes, generic AI-summary phrasing, and fact-dump cadence. "
        "Teaching value measures whether the viewer can explain the core idea afterward: concepts arrive before they are used, "
        "examples make abstractions concrete, evidence changes the conclusion, and limitations prevent overclaiming. "
        "Check that every story contains a visible example, a real consequence, and an honest limit. Deeper chapters must derive a "
        "practical rule from a specific workflow rather than merely summarizing a launch page. Run a listener-confusion audit: flag "
        "a pronoun with no clear subject, a term used before a plain definition, a conclusion that arrives before proof, and any "
        "first-person testing claim without a documented test. Penalize repeated transition filler. Promise delivery means the "
        "opening makes one answerable promise, proof arrives on time, and the ending resolves it. Voice consistency means the same "
        "audience relationship, vocabulary range, humor restraint, and cadence survive across chapters without becoming repetitive. "
        "Opening quality must be judged separately: it should choose an evidence-appropriate mechanism, name something concrete, "
        "translate why it matters quickly, and avoid sounding like a reusable viral-hook shell. A conversational script should feel "
        "like connected thought, not fake dialogue, constant direct address, or filler words painted over an essay. "
        "Give beat-specific rewrite instructions only for genuinely actionable problems. Do not invent an issue merely to "
        "offer an alternative phrasing, and return an empty issues list when the script already clears the standard. A 9 "
        "means believable, polished human narration; it does not mean no editor could imagine another wording. Treat a "
        "subjective wording preference as minor unless it causes real listener confusion, repetition, broken evidence "
        "logic, or a missed promise. Judge the script as a connected episode: an individual beat does not need to repeat "
        "proof or definitions that arrived clearly in the immediately preceding beat. The separate factual verifier owns "
        "claim support; only flag an unsupported statement here when it creates a clear spoken promise or teaching problem.\n\n"
        f"VOICE PROFILE:\n{json.dumps(voice_profile)}\n\nCONVERSATIONAL PROFILE:\n{json.dumps(conversational_profile)}\n\n"
        f"PROMISE CONTRACT:\n{json.dumps(promise_contract)}\n\n"
        f"EDITORIAL PLAN:\n{json.dumps(project.editorial_plan)}\n\nSCRIPT:\n{project.script.model_dump_json()}\n\n"
        f"LOCAL ORAL-EDIT FAILURES:\n{json.dumps(deterministic)}",
        QUALITY_SCHEMA,
        temperature=0.15,
    )
    scores = data["scores"]
    scores_are_valid = all(1 <= value <= 10 for value in scores.values())
    strict_scores = {"clarity", "natural_speech", "promise_delivery", "voice_consistency"}
    thresholds_pass = scores_are_valid and all(scores[key] >= 9 for key in strict_scores) and all(
        value >= 8 for key, value in scores.items() if key not in strict_scores
    )
    data["deterministic_failures"] = deterministic
    no_major_issues = not any(issue["severity"] in {"major", "blocking"} for issue in data["issues"])
    data["oral_metrics"] = oral_report["metrics"]
    data["passed"] = bool(thresholds_pass and no_major_issues and not deterministic)
    return data


def write_script(
    project: EpisodeProject, *, revision_feedback: dict | None = None,
    previous_script: Script | None = None,
) -> Script:
    if not project.brief or not project.claims:
        raise ValueError("approved brief and claims are required before script writing")
    if not project.editorial_plan:
        build_editorial_plan(project)
    if "section_drafts" not in project.editorial_plan:
        project.editorial_plan["section_drafts"] = draft_researched_sections(project)
    payload = {
        "brief": project.brief.model_dump(mode="json"),
        "claims": [claim.model_dump(mode="json") for claim in project.claims],
        "sources": _source_payload(project.sources),
        "editorial_plan": project.editorial_plan,
    }
    if previous_script:
        payload["previous_script"] = previous_script.model_dump(mode="json")
    if revision_feedback:
        payload["mandatory_verifier_feedback"] = revision_feedback
    profile = duration_profile(project)
    short_form = profile["target_minutes"] <= 6
    weekly = project.brief.episode_format == "weekly_roundup"
    voice_profile = project.editorial_plan.get("voice_profile", load_editorial_voice_profile())
    conversational_profile = project.editorial_plan.get(
        "conversational_profile", load_conversational_script_profile()
    )
    promise_contract = project.editorial_plan.get("promise_contract", {})
    opening_lab = project.editorial_plan.get("opening_lab", {})
    segment_rule = (
        f"Use 28-30 spoken segments. The first is a 35-55 word cold open, the show_intro beat is 20-24 words, "
        "and every other segment should usually be 45-60 words. Do not use tiny transition-only beats. "
        if weekly else
        f"Use {profile['beat_min']}-{profile['beat_max']} spoken segments. The first is a 35-55 word hook; other "
        "segments should usually be 20-45 words. Vary their length naturally while satisfying the total word range. "
        if short_form else
        f"Use {profile['beat_min']}-{profile['beat_max']} spoken segments. The first is a 35-55 word hook; other segments are 20-80 words. "
    )
    instruction = (
        f"Write a {profile['word_min']}-{profile['word_max']} word, {profile['target_minutes']:g}-minute speech-first "
        f"YouTube script. {segment_rule}"
        "Honor the supplied channel voice profile across the whole script. Treat it as a range, not a bag of catchphrases: "
        "the speaker should remain recognizable while sentence lengths, energy, and reactions vary naturally. Fulfill the supplied "
        "promise contract exactly: make one answerable promise, deliver early proof, and resolve the promise at the end. "
        "The hook must create truthful tension, make one concrete promise, and contain no greeting. Write for the ear, not the page. "
        "Use the opening lab's selected mechanism and evidence, but rewrite it naturally inside the finished script rather than treating "
        "the candidate as sacred copy. The first two sentences should identify a concrete change or result and translate why it matters. "
        "Open on the strongest visible result, consequence, or failure that the supplied evidence can actually support. Tell the viewer "
        "what they will understand or decide by the end, without teasing information you already have. "
        "The researched section drafts are fact-locked raw material, not final copy. Stitch them into one continuous speaker and remove "
        "duplicated setup, mini-conclusions, and changes in voice. It should sound like one informed person explaining something "
        "surprising to another person, with natural contractions, "
        "specific examples, and connective thought between beats. Mix short punchy sentences with fuller explanations. Prefer sentences "
        "under 24 words, but allow an occasional sentence up to 32 words when splitting it would make the thought less natural. "
        "Explain unavoidable jargon immediately. Never announce the structure with phrases like first, next "
        "question, observation, analysis, what worked, or what failed. Do not repeatedly say the source, the guidance, or the documents; "
        "state the supported point directly and use source labels in the visuals. Build momentum through cause, contrast, consequence, "
        "and payoff instead of a checklist cadence. Use the episode format playbook as story logic, not as headings. Separate observation from interpretation and never pretend the channel "
        "personally tested something unless the evidence package explicitly documents that test. "
        "Teach one useful idea at a time. Put a concrete example before a difficult abstraction, then show the evidence, explain why it "
        "changes the viewer's understanding, and name the important limitation. Every 45-75 seconds must earn attention with proof, a "
        "new example, or a changed conclusion; do not manufacture suspense. Use callbacks only when they genuinely simplify a later idea. "
        "Direct address is useful when it clarifies a viewer decision, not as filler. Brief reactions are allowed after proof, not before it. "
        "Do not begin several consecutive beats with So, Now, Okay, Look, Honestly, or Basically. Never reuse the same five-word phrase as a template. "
        "For each news item, silently follow this loop: concrete change, one-sentence plain explanation, visible example, user consequence, "
        "honest limitation, and verdict. For a deep explanation, use a real workflow story, then derive the mechanism and a practical rule. "
        "Never say those labels aloud. Do not repeat 'also this week', 'the awesome thing is', or description-link filler. "
        "Use humor sparingly: at most one short comic observation per 120-180 words, only when it grows from a documented contradiction, "
        "awkward workflow, limitation, or recognizable behavior. Never force slang, meme references, stand-up punchlines, or jokes that obscure a fact. "
        "End with a reusable mental model, practical decision rule, or precise open question—not a generic recap or subscription request. "
        "Every factual sentence must be supported by the claim_ids attached to that beat. Never add a proper noun, number, date, benchmark, "
        "quotation, or causal claim not present in the supplied evidence. Commentary beats may have no claim IDs but must sound like analysis, not fact. "
        "No beat may exceed 900 characters. Put timing only in the delivery object, never write bracketed pause tokens in narration. "
        "Use 250-400ms ordinary pauses, 450-650ms contrasts, 600-900ms before a visible result, 750-1100ms after a verdict, "
        "and 1300-2500ms only when a demo genuinely needs silence. Add pronunciation entries only where necessary. "
        "Prioritize current AI-media news: open-source releases, ComfyUI workflows, image/video models, creative tools, real demos, and the decisions those changes create. "
        "Treat Reddit and X posts as leads or community reaction, not proof. Do not make Magic Hour the topic unless the approved brief explicitly contains independently newsworthy Magic Hour evidence. "
        "Keep commercial and open-source coverage equally skeptical; no product receives promotional language because of channel affiliation. "
        "Thumbnail text must be one plain line containing 3-5 words. Do not imitate another creator's phrasing, catchphrases, "
        "persona, or branding. Before returning, silently read every line aloud and rewrite anything that sounds like a press release, "
        "policy memo, AI summary, or template. Return only the schema."
    )
    instruction += (
        "\n\nCHANNEL VOICE PROFILE:\n" + json.dumps(voice_profile)
        + "\n\nCONVERSATIONAL PROFILE:\n" + json.dumps(conversational_profile)
        + "\n\nOPENING LAB:\n" + json.dumps(opening_lab)
        + "\n\nPROMISE CONTRACT:\n" + json.dumps(promise_contract)
    )
    if weekly:
        instruction += (
            " This is THE WEEK IN AI, not a single-story essay. Start with a 35-55 word cold open that names or clearly previews the three "
            "highest-value developments. The next beat must be purpose show_intro and should say exactly one natural variation of: "
            "'Welcome to News Weekly—the ten-minute recap of the tech and AI news actually worth knowing.' Keep it under 24 words. "
            "Then cover the digest-plan stories in their supplied order. Give each story a clear change, source-backed proof, why a normal person "
            "should care, and the important limit. Use story_intro and transition beats so listeners always know what subject changed without "
            "hearing robotic labels such as story one or moving on. Hands-on language is forbidden unless that story is marked model_test_candidate; "
            "even then, describe a test as planned until captured results exist. End with a concise weekly_recap naming the two developments worth "
            "watching, followed by a one-line original sign-off. Do not add a subscribe request. The host is warm, lightly dry, and curious—not loud."
        )
    if revision_feedback:
        instruction += (
            " This is a mandatory full rewrite. Correct every item in mandatory_verifier_feedback. "
            "Delete unsupported facts and numbers; when retaining interpretation, label it unmistakably as analysis or an open question."
        )
    correction = ""
    last_problem = ""
    script_model = OPENROUTER_VERIFY_MODEL if (short_form or weekly) else OPENROUTER_MODEL
    for _attempt in range(3):
        data = call_openrouter(
            script_model,
            "You are the head writer for an independent, high-retention AI-media news and education channel. The pace may be brisk and visual, but the wording, analysis, and persona must be original.",
            instruction + correction + "\n\nEVIDENCE PACKAGE:\n" + json.dumps(payload),
            SCRIPT_SCHEMA,
            temperature=0.65,
        )
        allowed_purposes = {
            "hook", "show_intro", "headlines", "story_intro", "context", "test_setup",
            "model_test", "observation", "evidence", "analysis", "limitation", "comparison",
            "transition", "implication", "verdict", "weekly_recap", "disclosure", "outro",
        }
        for beat_data in data.get("beats", []):
            if beat_data.get("purpose") not in allowed_purposes:
                beat_data["purpose"] = "context" if beat_data.get("claim_ids") else "analysis"
            delivery = beat_data.get("delivery", {})
            delivery["emphasis_words"] = list(delivery.get("emphasis_words", []))[:5]
        try:
            script = Script.model_validate(data)
        except ValueError as exc:
            last_problem = f"schema validation failed: {exc}"
            correction = (
                "\nThe previous draft failed deterministic schema validation: " + last_problem + ". "
                "Rewrite the complete response and correct every reported field. Thumbnail text must be one 3-5 word line."
            )
            continue
        problems = _spoken_quality_failures(script, profile)
        # The next mandatory stage is a fact-locked spoken line edit. Let that
        # editor split a small number of overlong draft sentences while keeping
        # structural, evidence, beat-count, and total-length failures blocking.
        problems = [
            problem for problem in problems
            if not problem.startswith("sentences over 36 words:")
            and not (problem.startswith("only ") and "natural contractions" in problem)
        ]
        if not problems:
            return script
        last_problem = "; ".join(problems)
        rewrite_rule = (
            "Rewrite the complete script with 28-30 segments: a 35-55 word cold open, a 20-24 word show_intro, "
            "and 45-60 words in every other segment. Do not create short transition-only beats. "
            if weekly else
            f"Rewrite the complete script with {profile['beat_min']}-{profile['beat_max']} naturally varied spoken segments, "
            "a 35-55 word hook, and usually 20-45 words in every other segment. "
            if short_form else
            f"Rewrite the complete script with {profile['beat_min']}-{profile['beat_max']} segments, a 35-55 word hook, and 20-80 words in every other segment. "
        )
        correction = (
            "\nThe previous draft failed deterministic validation because " + last_problem + ". "
            + rewrite_rule
            + "Satisfy both limits without padding or repetition. Every context, test_setup, observation, "
            "evidence, and comparison beat must include at least one supplied claim ID. Use analysis or "
            "transition only when the line contains no factual assertion."
        )
    raise RuntimeError(f"script failed local length validation after 3 attempts: {last_problem}")


def humanize_script(project: EpisodeProject, script: Script) -> Script:
    """Run a fact-locked spoken line edit before independent verification and narration spend."""
    profile = duration_profile(project)
    expected_ids = [beat.id for beat in script.beats]
    correction = ""
    last_problem = ""
    voice_profile = project.editorial_plan.get("voice_profile", load_editorial_voice_profile())
    conversational_profile = project.editorial_plan.get(
        "conversational_profile", load_conversational_script_profile()
    )
    promise_contract = project.editorial_plan.get("promise_contract", {})
    short_canary = float(profile.get("target_minutes", project.episode.get("target_minutes", 10))) < 1
    # The long-form line editor tends to pad an already clean 65-80 word draft.
    # Preserve a fact-locked canary verbatim once every deterministic oral gate passes.
    if short_canary and not _spoken_quality_failures(script, profile):
        return script
    canary_rule = (
        f"\nSHORT CANARY RULES:\n- Keep the complete script between {profile['word_min']} and {profile['word_max']} words."
        f"\n- Keep all {len(expected_ids)} compact beats; each beat must be 6-24 words and the hook 8-18 words."
        "\n- Preserve the hidden order: change, proof, mechanism, consequence, caveat, watch item."
        "\n- Do not expand this into a long-form explanation.\n"
        if short_canary else ""
    )
    line_model = OPENROUTER_VERIFY_MODEL if short_canary or (project.brief and project.brief.episode_format == "weekly_roundup") else OPENROUTER_MODEL
    for _attempt in range(2):
        data = call_openrouter(
            line_model,
            "You are a meticulous spoken-word line editor, not a researcher. Rewrite delivery while keeping every fact, "
            "qualification, and evidence boundary locked. Your job is to make the script sound like one thoughtful human "
            "explaining a difficult topic clearly to another human.",
            "Rewrite only narration and delivery metadata for every supplied beat. Keep every beat ID exactly once and in the "
            "same order. Do not add, remove, strengthen, or weaken a factual claim. Do not add a name, number, date, comparison, "
            "test result, or first-person experience. Preserve the meaning and the existing evidence mapping.\n\n"
            "SPOKEN VOICE RULES:\n"
            "- Use ordinary words and natural contractions where they fit; don't force slang.\n"
            "- Preserve the channel voice profile as a consistent audience relationship and vocabulary range, not repeated verbal tics.\n"
            "- Let one thought lead to the next. Transitions should complete an idea, not announce a section.\n"
            "- Prefer a concrete example before an abstraction. Define unavoidable jargon in one plain sentence.\n"
            "- Let the audience see the result before you explain the mechanism. Describe only what the evidence bundle can show.\n"
            "- Make each story causally connected: change, visible proof, consequence, limitation, then a clean landing. Never announce that sequence.\n"
            "- Prefer one concrete person, task, or creator workflow over a pile of abstract benefits.\n"
            "- Keep referents obvious: replace vague words like it, this, and they when a listener could lose track.\n"
            "- Use a brief honest reaction only when it helps interpret evidence; never manufacture surprise or personal testing.\n"
            "- Make the listener feel included through clear consequences and occasional direct address, not repeated you-language.\n"
            "- Keep small self-corrections or asides only when they genuinely clarify a confusing name, comparison, or limitation.\n"
            "- Alternate a concise observation with a fuller explanation when the evidence supports it; don't make every line punchy.\n"
            "- Vary cadence: a short landing sentence after a denser explanation is useful. Avoid a metronomic rhythm.\n"
            "- Keep the speaker confident but intellectually honest. Say what is unknown without policy-memo language.\n"
            "- Delete AI-script cliches, throat-clearing, fake excitement, repeated rhetorical questions, and generic recaps.\n"
            "- Preserve humor only when it comes directly from a real limitation, contradiction, awkward workflow, or recognizable behavior. "
            "Cut jokes that sound inserted by a comedy prompt.\n"
            "- Never use 'let's dive in', 'here's where things get interesting', 'but here's the thing', 'game-changer', "
            "'rapidly evolving landscape', 'the key takeaway is', or 'it remains to be seen'.\n"
            "- Prefer sentences under 24 words. Allow an occasional sentence up to 32 words when splitting would hurt spoken clarity. "
            "No narration field may exceed 900 characters.\n"
            "- Use pauses to let proof and verdicts land, not after every sentence. Return only the schema."
            + canary_rule
            + correction
            + "\n\nCHANNEL VOICE PROFILE:\n" + json.dumps(voice_profile)
            + "\n\nCONVERSATIONAL PROFILE:\n" + json.dumps(conversational_profile)
            + "\n\nPROMISE CONTRACT:\n" + json.dumps(promise_contract)
            + "\n\nEDITORIAL PLAN:\n" + json.dumps(project.editorial_plan)
            + "\n\nFACT-LOCKED DRAFT:\n" + script.model_dump_json(),
            HUMANIZE_SCHEMA,
            temperature=0.45,
        )
        returned_ids = [item.get("id", "") for item in data.get("beats", [])]
        if returned_ids != expected_ids:
            last_problem = "the spoken rewrite changed, reordered, or omitted beat IDs"
            correction = "\nThe previous response failed because it changed the beat structure. Return the exact IDs in the exact supplied order."
            continue
        rewritten = script.model_copy(deep=True)
        by_id = {item["id"]: item for item in data["beats"]}
        for beat in rewritten.beats:
            beat.narration = by_id[beat.id]["narration"]
            beat.delivery = DeliveryDirection.model_validate(by_id[beat.id]["delivery"])
        contractions = [
            (r"\bit is\b", "it's"), (r"\bthat is\b", "that's"), (r"\bthere is\b", "there's"),
            (r"\bdo not\b", "don't"), (r"\bdoes not\b", "doesn't"), (r"\bcannot\b", "can't"),
            (r"\bwe are\b", "we're"), (r"\byou are\b", "you're"), (r"\bthey are\b", "they're"),
            (r"\bwill not\b", "won't"),
        ]
        for beat in rewritten.beats:
            for pattern, replacement in contractions:
                beat.narration = re.sub(pattern, replacement, beat.narration, flags=re.IGNORECASE)
        rewritten = Script.model_validate(rewritten.model_dump())
        problems = _spoken_quality_failures(rewritten, profile)
        if not problems:
            return rewritten
        last_problem = "; ".join(problems)
        correction = (
            "\nThe previous spoken rewrite failed deterministic oral editing: " + last_problem
            + ". Rewrite every beat again without changing its factual meaning or structure."
        )
    raise RuntimeError(f"spoken humanization failed after 2 attempts: {last_problem}")


def write_verified_script(project: EpisodeProject, max_revisions: int = 3) -> tuple[Script, dict[str, Any], int]:
    """Write, independently verify, and automatically revise before any narration spend."""
    script = humanize_script(project, write_script(project))
    verification: dict[str, Any] = {}
    for revision in range(max_revisions + 1):
        project.script = script
        fact_check = verify_script(project)
        quality_review = review_script_quality(project)
        verification = {
            **fact_check,
            "quality_review": quality_review,
            "passed": bool(fact_check["passed"] and quality_review["passed"]),
        }
        if verification["passed"]:
            return script, verification, revision
        if revision < max_revisions:
            script = humanize_script(
                project,
                write_script(
                    project,
                    revision_feedback={"fact_check": fact_check, "quality_review": quality_review},
                    previous_script=script,
                ),
            )
    return script, verification, max_revisions


def verify_script(project: EpisodeProject) -> dict[str, Any]:
    if not project.script:
        raise ValueError("script is required")
    data = call_openrouter(
        OPENROUTER_VERIFY_MODEL,
        "You are an independent fact checker. Use only the evidence package. Flag unsupported checkable factual statements, "
        "especially names, numbers, dates, rankings, causation, and sensational wording. Do not flag rhetorical framing, "
        "transitions, recommendations, or faithful plain-language paraphrases that introduce no new checkable fact. "
        "The supplied claim records are the approved evidence abstraction. When a beat faithfully paraphrases an attached "
        "claim, treat it as supported; do not relitigate harmless wording differences between that claim and its source text. "
        "For every unsupported item, identify the specific new factual assertion. Put missing or weak visual evidence only in "
        "visual_gaps, never in unsupported or corrections. Locally rendered explanatory diagrams, labels, maps, timelines, "
        "and interface reconstructions are allowed when they do not pretend to be documentary footage.",
        json.dumps({
            "script": project.script.model_dump(mode="json"),
            "claims": [claim.model_dump(mode="json") for claim in project.claims],
            "sources": _source_payload(project.sources, include_text=True),
        }),
        VERIFY_SCHEMA,
        temperature=0.1,
    )
    # Older/verifier model variants occasionally put storyboard coverage notes in
    # `unsupported` even though VERIFY_SCHEMA has a dedicated `visual_gaps` field.
    # Keep fact gating strict while routing those non-factual notes to the visual
    # director, where source/capture coverage is actually resolved.
    visual_markers = (
        "no usable visual source", "visual direction", "visual source", "illustrative graphic",
        "illustrative diagram", "illustrative split", "illustrative node", "interface graphic",
        "ending mental-model graphic", "timeline graphic", "rumor caution card",
    )
    factual_unsupported: list[str] = []
    routed_visual_gaps = list(data.get("visual_gaps", []))
    script_text = " ".join(beat.narration for beat in project.script.beats).casefold()
    beats_by_id = {beat.id: beat for beat in project.script.beats}
    claims_by_id = {claim.id: claim for claim in project.claims}
    for item in data.get("unsupported", []):
        lowered = item.lower()
        quoted = re.findall(r'"([^"\n]{4,})"', item)
        quoted_assertion_missing = bool(
            quoted and re.sub(r"\s+", " ", quoted[0].casefold()).strip()
            not in re.sub(r"\s+", " ", script_text)
        )
        beat_match = re.search(r"\bb\d{2}\b", lowered)
        quoted_claim_supported = False
        if beat_match and quoted:
            beat = beats_by_id.get(beat_match.group(0))
            claim_text = " ".join(
                claims_by_id[claim_id].text
                for claim_id in (beat.claim_ids if beat else [])
                if claim_id in claims_by_id
            )
            assertion_tokens = set(re.findall(r"[a-z0-9]+", quoted[0].casefold()))
            claim_tokens = set(re.findall(r"[a-z0-9]+", claim_text.casefold()))
            quoted_claim_supported = bool(
                assertion_tokens
                and len(assertion_tokens & claim_tokens) / len(assertion_tokens) >= 0.75
            )
        if any(marker in lowered for marker in visual_markers):
            routed_visual_gaps.append(item)
        elif any(marker in lowered for marker in (
            "no issue", "no unsupported item", "harmless paraphrase",
            "advice rather than a factual claim", "advice and not a factual claim",
            "not unsupported in", "this is supported by", "is supported by c",
        )):
            # Some structured-output reviewers explain why a candidate is
            # supported inside the `unsupported` array. Do not turn an
            # explicit non-finding into a blocking factual error.
            continue
        elif quoted_assertion_missing:
            # Reject stale reviewer findings that quote text not present in the
            # submitted script. This commonly happens after narrow factual
            # revisions and must not create an impossible repair loop.
            continue
        elif quoted_claim_supported:
            # The model occasionally relitigates a harmless phrasing change
            # even when the quoted assertion is already covered almost word
            # for word by a claim attached to that beat.
            continue
        else:
            factual_unsupported.append(item)
    data["unsupported"] = factual_unsupported
    data["visual_gaps"] = list(dict.fromkeys(routed_visual_gaps))
    if not factual_unsupported:
        # Corrections are remedies for factual findings, not optional copy
        # preferences. With no factual finding, optional precision notes must
        # not independently fail the gate.
        data["corrections"] = []
    data["passed"] = not data["unsupported"] and not data["corrections"]
    return data


def save_slate(briefs: list[Brief], output: Path, start_date: date | None = None) -> Path:
    first = start_date or date.today()
    payload = {"schema_version": "2.0", "created_at": date.today().isoformat(), "episodes": []}
    for index, brief in enumerate(briefs):
        payload["episodes"].append({"scheduled_date": (first + timedelta(days=index)).isoformat(), "brief": brief.model_dump(mode="json")})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return output
