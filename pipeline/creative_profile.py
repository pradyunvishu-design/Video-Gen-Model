"""Measurable creative profiles for narrated editorial video and thumbnails.

The preferred profile is derived from the strongest local 30-second Hermes
proof: one concrete claim, real source evidence, restrained motion, and a
narrow verdict. It encodes transferable rules rather than copying a frame.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any


HERMES_PROOF_FIRST = "hermes-proof-first-v1"


@dataclass(frozen=True)
class ThumbnailHypothesis:
    archetype: str
    angle: str
    visual_sentence: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ThumbnailConcept:
    """Evidence-bound contract for one materially distinct thumbnail idea."""

    topic_class: str
    archetype: str
    headline: str
    visual_sentence: str
    focal_subject: str
    supporting_subjects: tuple[str, ...]
    required_logos: tuple[str, ...]
    asset_ids: tuple[str, ...]
    highlighted_keyword: str
    must_not_imply: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    angle: str
    style_mode: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("supporting_subjects", "required_logos", "asset_ids", "must_not_imply", "evidence_ids"):
            data[key] = list(data[key])
        return data


TOPIC_ARCHETYPE_ROUTES: dict[str, tuple[str, ...]] = {
    "release": ("product_plus_proof", "proof_closeup", "mechanism_map", "broken_assumption"),
    "comparison": ("agent_showdown", "proof_split", "criterion_card", "workflow_relay"),
    "workflow": ("mechanism_map", "product_plus_proof", "proof_closeup", "consequence_frame"),
    "failure": ("broken_assumption", "proof_closeup", "mechanism_map", "consequence_frame"),
    "research": ("product_plus_proof", "mechanism_map", "claim_vs_receipt", "proof_closeup"),
    "business-policy": ("consequence_frame", "claim_vs_receipt", "proof_split", "broken_assumption"),
    "weekly-roundup": ("hero_story", "ranked_stack", "evidence_grid", "consequence_frame"),
}


# Four packaging systems derived from the user's references.  They describe
# reusable visual grammar, not a creator-specific composition or character.
TOPIC_STYLE_ROUTES: dict[str, tuple[str, ...]] = {
    "release": ("commercial_collage", "editorial_symbol", "cinematic_duel", "bold_conflict"),
    "comparison": ("commercial_collage", "cinematic_duel", "bold_conflict", "editorial_symbol"),
    "workflow": ("commercial_collage", "cinematic_duel", "editorial_symbol", "bold_conflict"),
    "failure": ("commercial_collage", "bold_conflict", "editorial_symbol", "cinematic_duel"),
    "research": ("commercial_collage", "editorial_symbol", "cinematic_duel", "bold_conflict"),
    "business-policy": ("commercial_collage", "bold_conflict", "editorial_symbol", "cinematic_duel"),
    "weekly-roundup": ("commercial_collage", "cinematic_duel", "bold_conflict", "editorial_symbol"),
}


def normalize_topic_class(topic_class: str) -> str:
    value = re.sub(r"[_\s]+", "-", topic_class.strip().casefold())
    aliases = {
        "launch": "release", "transformation": "workflow", "explainer": "workflow",
        "limitation": "failure", "roundup": "weekly-roundup", "business": "business-policy",
        "policy": "business-policy", "model": "research", "research-model": "research",
        "workflow-tool": "workflow", "failure-security": "failure",
    }
    value = aliases.get(value, value)
    if value not in TOPIC_ARCHETYPE_ROUTES:
        raise ValueError(f"unsupported thumbnail topic class: {topic_class}")
    return value


def classify_story(context: str, *, source_count: int = 1) -> str:
    """Route a story to an honest thumbnail family using episode language."""
    value = re.sub(r"\s+", " ", context).casefold()
    direct = re.sub(r"[_\s]+", "-", value.strip())
    if direct in TOPIC_ARCHETYPE_ROUTES:
        return direct
    if any(term in value for term in (" versus ", " vs ", "compare", "comparison", "head-to-head", "battle")):
        return "comparison"
    if any(term in value for term in ("before and after", "before/after", "transformation", "redesign", "rewrote", "fixed")) and source_count >= 2:
        return "workflow"
    if any(term in value for term in ("weekly", "roundup", "recap", "top stories", "what happened this week")):
        return "weekly-roundup"
    if any(term in value for term in ("limit", "catch", "cost", "problem", "warning", "not quite", "reality", "fails")):
        return "failure"
    if any(term in value for term in ("how it works", "explainer", "mechanism", "architecture", "workflow")):
        return "workflow"
    if any(term in value for term in ("paper", "research", "study", "benchmark", "model", "parameter")):
        return "research"
    if any(term in value for term in ("policy", "regulation", "law", "pricing", "acquisition", "business")):
        return "business-policy"
    return "release"


def thumbnail_hypotheses(context: str, *, source_count: int = 1) -> list[ThumbnailHypothesis]:
    """Return four structurally different, topic-compatible A/B hypotheses."""
    story_type = classify_story(context, source_count=source_count)
    primary: dict[str, list[ThumbnailHypothesis]] = {
        "comparison": [
            ThumbnailHypothesis("agent_showdown", "conflict", "Two verified products face the same criterion."),
            ThumbnailHypothesis("proof_split", "evidence", "Equal proof panels resolve the comparison."),
            ThumbnailHypothesis("criterion_card", "outcome", "One measured criterion becomes the focal result."),
            ThumbnailHypothesis("workflow_relay", "mechanism", "The handoff between products is the visual story."),
        ],
        "workflow": [
            ThumbnailHypothesis("before_after", "outcome", "Two authentic states show the demonstrated change."),
            ThumbnailHypothesis("proof_closeup", "evidence", "The changed region fills the frame."),
            ThumbnailHypothesis("mechanism_map", "mechanism", "A simple path explains how the result happened."),
            ThumbnailHypothesis("consequence_frame", "consequence", "The useful consequence sits beside the proof."),
        ],
        "weekly-roundup": [
            ThumbnailHypothesis("ranked_stack", "scope", "Three real story receipts form one weekly stack."),
            ThumbnailHypothesis("hero_story", "impact", "The biggest story dominates while two remain secondary."),
            ThumbnailHypothesis("evidence_grid", "breadth", "A clean evidence grid communicates a true roundup."),
            ThumbnailHypothesis("consequence_frame", "takeaway", "One shared consequence unifies the week."),
        ],
        "failure": [
            ThumbnailHypothesis("broken_assumption", "tension", "A familiar promise collides with one real limitation."),
            ThumbnailHypothesis("proof_closeup", "evidence", "The documented limit is the unmistakable focal point."),
            ThumbnailHypothesis("mechanism_map", "cause", "A simple mechanism shows why the limitation exists."),
            ThumbnailHypothesis("consequence_frame", "impact", "The practical cost sits beside the source proof."),
        ],
        "research": [
            ThumbnailHypothesis("product_plus_proof", "change", "The source-backed capability and authentic proof share one visual sentence."),
            ThumbnailHypothesis("mechanism_map", "mechanism", "One clear relationship explains how the reported capability works."),
            ThumbnailHypothesis("claim_vs_receipt", "limit", "The reported result faces its unresolved verification limit."),
            ThumbnailHypothesis("proof_closeup", "evidence", "The strongest readable source detail becomes the focal point."),
        ],
        "business-policy": [
            ThumbnailHypothesis("consequence_frame", "impact", "The affected audience and documented change form one consequence."),
            ThumbnailHypothesis("claim_vs_receipt", "decision", "The stated policy faces the source-backed practical effect."),
            ThumbnailHypothesis("proof_split", "contrast", "Two authentic source states show what changes."),
            ThumbnailHypothesis("broken_assumption", "tension", "A familiar expectation meets the documented constraint."),
        ],
        "release": [
            ThumbnailHypothesis("product_plus_proof", "launch", "One product and one authentic result communicate the release."),
            ThumbnailHypothesis("proof_closeup", "evidence", "The official result or interface fills the frame."),
            ThumbnailHypothesis("mechanism_map", "capability", "A restrained relationship map explains the new capability."),
            ThumbnailHypothesis("broken_assumption", "tension", "The useful launch promise meets its most important caveat."),
        ],
    }
    return primary[story_type]


def build_thumbnail_concepts(
    *, topic_class: str, headline: str, focal_subject: str,
    evidence_ids: list[str] | tuple[str, ...], asset_ids: list[str] | tuple[str, ...],
    supporting_subjects: list[str] | tuple[str, ...] = (),
    required_logos: list[str] | tuple[str, ...] = (),
    must_not_imply: list[str] | tuple[str, ...] = (),
) -> list[ThumbnailConcept]:
    """Create four truth-constrained concepts before any pixels are rendered."""
    topic = normalize_topic_class(topic_class)
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", headline.upper())
    if not 2 <= len(words) <= 5:
        raise ValueError("thumbnail headline must contain 2-5 words")
    evidence = tuple(dict.fromkeys(item.strip() for item in evidence_ids if item.strip()))
    assets = tuple(dict.fromkeys(item.strip() for item in asset_ids if item.strip()))
    if not evidence:
        raise ValueError("thumbnail concepts require at least one evidence ID")
    if not assets:
        raise ValueError("thumbnail concepts require at least one accepted source/frame asset ID")
    hypotheses = thumbnail_hypotheses(topic.replace("-", " "), source_count=len(assets))
    routes = TOPIC_ARCHETYPE_ROUTES[topic]
    style_routes = TOPIC_STYLE_ROUTES[topic]
    by_archetype = {item.archetype: item for item in hypotheses}
    concepts: list[ThumbnailConcept] = []
    highlight = max((word for word in words if word not in {"THE", "A", "AN", "IN", "TO", "OF"}), key=len, default=words[-1])
    for index, archetype in enumerate(routes):
        hypothesis = by_archetype.get(archetype) or ThumbnailHypothesis(
            archetype, ("change", "evidence", "mechanism", "decision")[index],
            f"Concept {index + 1} frames the supported promise through {archetype.replace('_', ' ')}.",
        )
        concepts.append(ThumbnailConcept(
            topic_class=topic, archetype=archetype, headline=" ".join(words),
            visual_sentence=hypothesis.visual_sentence, focal_subject=focal_subject.strip(),
            supporting_subjects=tuple(supporting_subjects), required_logos=tuple(required_logos),
            asset_ids=assets, highlighted_keyword=highlight, must_not_imply=tuple(must_not_imply),
            evidence_ids=evidence, angle=hypothesis.angle,
            style_mode=style_routes[index],
        ))
    return concepts


def review_proof_first_spec(spec: dict[str, Any], public_dir: Path | None = None) -> dict[str, Any]:
    """Score the narrated proof-first grammar and fail silent or decorative drafts."""
    if spec.get("creativeProfile") != HERMES_PROOF_FIRST:
        return {"passed": True, "score": 100, "failures": [], "warnings": [], "profile": "default"}
    scenes = spec.get("scenes") or []
    duration = sum(float(scene.get("durationSeconds", 0)) for scene in scenes) - max(0, len(scenes) - 1) * .2
    failures: list[str] = []
    warnings: list[str] = []
    audio_src = str(spec.get("audioSrc") or "").strip()
    if not audio_src:
        failures.append("proof-first videos require one narration track")
    elif public_dir and not audio_src.startswith(("http://", "https://")) and not (public_dir / audio_src).is_file():
        failures.append(f"narration asset is missing: {audio_src}")
    if not spec.get("captions"):
        failures.append("proof-first videos require word-timed captions")
    spoken_words = sum(
        len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", str(caption.get("text") or "")))
        for caption in spec.get("captions") or []
    )
    speech_wpm = spoken_words / duration * 60 if duration > 0 else 0
    if duration >= 20 and spoken_words and not 110 <= speech_wpm <= 185:
        failures.append(f"narration pace {speech_wpm:.1f} WPM is outside the human-listenable 110-185 range")
    if 20 <= duration <= 45 and not 5 <= len(scenes) <= 7:
        failures.append("20-45 second proof-first videos require 5-7 information states")
    if scenes and max(float(scene.get("durationSeconds", 0)) for scene in scenes) > 6.5:
        failures.append("proof-first scenes may not hold longer than 6.5 seconds")
    kinds = [str(scene.get("kind")) for scene in scenes]
    if "source" not in kinds:
        failures.append("proof-first videos require authentic source evidence")
    if not any(kind in {"compare", "activity"} for kind in kinds):
        failures.append("proof-first videos require a verification or verdict state")
    longest = current = 0
    previous = None
    for kind in kinds:
        current = current + 1 if kind == previous else 1
        longest = max(longest, current)
        previous = kind
    if longest > 2:
        warnings.append("more than two consecutive scenes use the same information family")
    source_ratio = sum(kind == "source" for kind in kinds) / max(1, len(kinds))
    if len(scenes) >= 6 and source_ratio < .25:
        warnings.append("less than one quarter of the sequence is authentic source media")
    penalty = len(failures) * 18 + len(warnings) * 7
    return {
        "passed": not failures,
        "score": max(0, 100 - penalty),
        "failures": failures,
        "warnings": warnings,
        "profile": HERMES_PROOF_FIRST,
        "duration_seconds": round(duration, 3),
        "scene_count": len(scenes),
        "source_ratio": round(source_ratio, 3),
        "spoken_word_count": spoken_words,
        "speech_wpm": round(speech_wpm, 2),
    }
