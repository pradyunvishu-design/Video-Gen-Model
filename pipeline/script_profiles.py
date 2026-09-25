"""Opt-in nonfiction writing contracts, independent of the channel's news slate."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Literal, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .models import EpisodeProject

VERSION = "general-script-v1"


class ScriptProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    version: Literal["1.0"] = "1.0"
    niche: str = Field(min_length=1, max_length=160)
    subject: str = Field(min_length=1, max_length=240)
    audience: str = Field(min_length=1, max_length=400)
    viewer_payoff: str = Field(min_length=1, max_length=400)
    format: Literal["explainer", "tutorial", "comparison", "history", "science",
                    "case_study", "documentary", "news"] = "explainer"
    knowledge_level: Literal["beginner", "intermediate", "expert"] = "beginner"
    timeliness: Literal["evergreen", "current"] = "evergreen"
    voice: Literal["conversational", "calm_documentary", "precise_teacher", "warm_guide"] = "conversational"
    humor: Literal["none", "light"] = "light"
    words_per_minute: int = Field(default=145, ge=90, le=190)
    risk_domain: Literal["general", "health", "finance", "law", "safety"] = "general"


PLAYBOOKS = {
    "explainer": {
        "sequence": ["concrete puzzle", "necessary context", "mechanism", "worked example", "boundary", "mental model"],
        "guidance": "Distinguish literal mechanisms from analogies. Build understanding, not an artificial news peg.",
    },
    "tutorial": {
        "sequence": ["outcome", "prerequisites", "ordered steps", "checkpoints", "troubleshooting", "next action"],
        "guidance": "Natural First/Next instructions are welcome. State prerequisites, observable checkpoints and recovery. Never imply a documented procedure was personally tested.",
    },
    "comparison": {
        "sequence": ["viewer decision", "criteria", "comparable evidence", "tradeoffs", "conditional verdict"],
        "guidance": "Use the same criteria for all options. Disclose unequal test conditions. Never invent scores or a universal winner.",
    },
    "history": {
        "sequence": ["historical question", "context", "chronology", "turning point", "competing interpretations", "consequence"],
        "guidance": "Dates and chronology must be sourced. Do not invent dialogue, motives or thoughts. Separate documented events from historical interpretation.",
    },
    "science": {
        "sequence": ["observable phenomenon", "model", "evidence", "alternative explanation", "uncertainty", "implications"],
        "guidance": "Explain units and scale. Separate correlation, causation, models and observations. Do not turn preliminary findings into consensus.",
    },
    "case_study": {
        "sequence": ["decision", "context and incentives", "actions", "measured outcomes", "alternative causes", "transferable lesson"],
        "guidance": "Avoid hindsight certainty and success mythology. Financial metrics need dates, definitions and comparable bases. Attribution is not proof of causation.",
    },
    "documentary": {
        "sequence": ["documented stakes", "context", "sequence", "turning point", "resolution", "remaining question"],
        "guidance": "Use narrative tension from documented events. Label reconstructions; never invent witnessed scenes, quotations, emotions or motives.",
    },
    "news": {
        "sequence": ["verified change", "context", "evidence", "consequence", "limits", "what to watch"],
        "guidance": "Distinguish announcement date from event date. Attribute unverified reports. Rank changes by audience consequence, not hype.",
    },
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def resolve_contract(project: EpisodeProject) -> dict:
    profile = project.script_profile
    if profile is None:
        raise ValueError("script_profile is required for the general writer")
    minutes = float(project.episode.get("target_minutes", 10))
    if not math.isfinite(minutes) or not 1 <= minutes <= 20:
        raise ValueError("general scripts support 1-20 target minutes; split longer projects into episodes")
    wpm = float(project.episode.get("voice_words_per_minute") or profile.words_per_minute)
    if not math.isfinite(wpm) or not 70 <= wpm <= 220:
        raise ValueError("voice_words_per_minute must be between 70 and 220")
    words = round(minutes * wpm)
    return {
        "version": VERSION, "profile": profile.model_dump(), "playbook": PLAYBOOKS[profile.format],
        "duration": {"target_minutes": minutes, "voice_words_per_minute": wpm,
                     "outline_target": words, "word_min": round(words * .9), "word_max": round(words * 1.1),
                     "beat_min": max(3, math.ceil(words / 70)), "beat_max": max(4, math.ceil(words / 35)),
                     "chapter_min": 3 if minutes < 4 else 5, "chapter_max": 5 if minutes < 4 else 10},
        "timing_status": "awaiting_actual_timeline",
        "evidence_policy": "Nonfiction only. Every factual sentence needs attached claims supported by source text. "
                           "No invented experience, quotations, numbers or causal certainty. Label hypothetical examples. "
                           "Health, finance, legal and safety content needs qualified human review before production.",
        "opening_policy": "Choose among evidence-led mechanisms; no mandatory shock or joke. Name the subject, "
                          "make one achievable promise, supply a concrete example early, and resolve it at the end. "
                          "Evergreen episodes must not invent urgency. Timing is unverified until aligned audio exists.",
        "originality": "Use original language and examples. Do not copy creator wording, persona or catchphrases.",
    }


def script_input_hash(project: EpisodeProject) -> str:
    """Capture status/media changes must not invalidate an otherwise identical script."""
    return digest({
        "contract": resolve_contract(project),
        "brief": project.brief.model_dump(mode="json") if project.brief else None,
        "claims": [c.model_dump(mode="json") for c in project.claims],
        "sources": [{k: s.model_dump(mode="json")[k] for k in
                     ("id", "title", "url", "publisher", "published_at", "source_type", "signal_role", "text", "summary")}
                    for s in project.sources],
    })
