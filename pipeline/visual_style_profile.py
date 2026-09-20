"""Versioned visual-style profiles for deterministic editorial video planning."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "configs" / "visual_style_profiles"
DEFAULT_VISUAL_STYLE_PROFILE = "ai-news-editorial-v6"
TRAINING_VISUAL_STYLE_PROFILE = "ai-news-editorial-v3"


@lru_cache(maxsize=8)
def load_visual_style_profile(version: str = DEFAULT_VISUAL_STYLE_PROFILE) -> dict[str, Any]:
    path = PROFILE_DIR / f"{version}.json"
    if not path.is_file():
        raise ValueError(f"unknown visual style profile: {version}")
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("version") != version:
        raise ValueError(f"visual style profile version mismatch: {path}")
    required = {"canvas", "timing", "typography", "dominance", "repetition", "routing"}
    missing = sorted(required - set(profile))
    if missing:
        raise ValueError(f"visual style profile is missing: {', '.join(missing)}")
    return profile


def visual_style_profile_sha256(profile: dict[str, Any]) -> str:
    """Return the canonical content identity embedded beside a style profile."""
    payload = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def semantic_intent(purpose: str, narration: str = "") -> str:
    """Normalize editorial beats before a scene family or pattern is selected."""
    purpose = purpose.lower().replace("_", "-")
    text = narration.lower()
    if purpose in {"hook", "change", "cold-open"} or any(term in text for term in ("failed", "failure", "cost", "consequence")):
        return "consequence"
    if purpose in {"evidence", "observation", "source", "proof", "model-test", "test-setup"}:
        return "proof"
    if purpose in {"analysis", "mechanism", "explanation"}:
        return "mechanism"
    if purpose in {"implication", "consequence", "benefit"}:
        return "practical-consequence"
    if purpose in {"limitation", "caveat", "risk", "unknown"}:
        return "caveat"
    if purpose in {"decision", "watch", "verdict", "takeaway", "conclusion"}:
        return "decision"
    if purpose in {"chapter", "orientation", "reset"}:
        return "orientation"
    return "mechanism"


def pattern_family(pattern: str) -> str:
    return pattern.split("-", 1)[0]


def composition_family(pattern: str) -> str:
    family = pattern_family(pattern)
    if family in {"source", "terminal"}:
        return "full-frame-proof"
    if family in {"graph", "timeline", "stack"}:
        return "mechanism-stage"
    if family in {"compare", "activity", "chat"}:
        return "evidence-ledger"
    return "open-reset"


def route_pattern(
    intent: str,
    *,
    available_kinds: set[str] | None = None,
    prior_patterns: list[str] | None = None,
    prior_compositions: list[str] | None = None,
    profile: dict[str, Any] | None = None,
) -> str:
    """Choose a semantic pattern while preventing adjacent visual repetition."""
    profile = profile or load_visual_style_profile()
    candidates = list(profile["routing"].get(intent) or profile["routing"]["mechanism"])
    if available_kinds:
        candidates = [item for item in candidates if pattern_family(item) in available_kinds] or candidates
    prior_patterns = prior_patterns or []
    prior_compositions = prior_compositions or []
    for pattern in candidates:
        if prior_patterns and pattern == prior_patterns[-1]:
            continue
        composition = composition_family(pattern)
        if len(prior_compositions) >= 2 and prior_compositions[-2:] == [composition, composition]:
            continue
        return pattern
    return candidates[0]
