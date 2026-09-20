"""Deterministic art direction for premium editorial motion graphics.

This module sits before a renderer. It converts a semantic scene intent into a
small visual contract and rejects the common patterns that make generated
motion graphics feel generic. It deliberately does not generate pixels.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any


ALLOWED_MOTION_INTENTS = {"micro", "enter", "connect", "emphasize"}
CONCEPT_ROUTES: dict[str, tuple[str, ...]] = {
    "consequence": ("receipt-first", "single-consequence", "scale-contrast"),
    "proof": ("proof-window", "proof-plus-annotation", "measured-result"),
    "mechanism": ("cause-chain", "system-map", "progressive-disclosure"),
    "practical-consequence": ("before-after", "decision-split", "impact-ledger"),
    "caveat": ("promise-versus-limit", "failure-path", "constraint-closeup"),
    "decision": ("evidence-verdict", "criterion-score", "next-action"),
    "orientation": ("editorial-reset", "chapter-object", "single-question"),
}

COMPOSITION_BY_KIND = {
    "source": "proof-dominant",
    "terminal": "proof-dominant",
    "graph": "relationship-dominant",
    "timeline": "relationship-dominant",
    "stack": "relationship-dominant",
    "compare": "split-evidence",
    "activity": "sequential-ledger",
    "chat": "sequential-ledger",
    "title": "open-editorial",
}

PROOF_OBJECT_BY_KIND = {
    "source": "real source crop with one verified line",
    "terminal": "real command and result",
    "graph": "verified relationship diagram",
    "timeline": "dated evidence sequence",
    "stack": "named workflow stages",
    "compare": "two evidence-backed states",
    "activity": "recorded action and outcome",
    "chat": "attributed exchange",
    "title": "one sourced editorial object",
}

CONCEPT_MECHANISMS = {
    "receipt-first": "begin on the source receipt, then reveal its consequence",
    "single-consequence": "make one consequence dominate and attach its proof",
    "scale-contrast": "compare the claimed scale with the measured scale",
    "proof-window": "crop directly into the source region that proves the line",
    "proof-plus-annotation": "pair one proof object with one exact annotation",
    "measured-result": "let one measured result organize the frame",
    "cause-chain": "reveal causal stages in reading order",
    "system-map": "connect named actors through verified relationships",
    "progressive-disclosure": "reveal only the next required layer",
    "before-after": "contrast the prior and changed state",
    "decision-split": "separate the choice from its consequence",
    "impact-ledger": "list concrete gains and limits as evidence",
    "promise-versus-limit": "place the claim beside its documented boundary",
    "failure-path": "trace the shortest verified failure route",
    "constraint-closeup": "magnify the one constraint that changes the story",
    "evidence-verdict": "build the conclusion directly from its proof",
    "criterion-score": "evaluate the claim against explicit criteria",
    "next-action": "end on the practical action supported by evidence",
    "editorial-reset": "reset attention around one sourced question",
    "chapter-object": "use one real object to introduce the chapter",
    "single-question": "organize the frame around one answerable question",
}


def _stable_pick(values: tuple[str, ...], seed: str) -> str:
    digest = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)
    return values[digest % len(values)]


def _short_focal_idea(context: str) -> str:
    clean = re.sub(r"\s+", " ", context).strip(" .")
    if not clean:
        return "Verified editorial point"
    first = re.split(r"(?<=[.!?])\s+", clean, maxsplit=1)[0]
    words = first.split()
    return " ".join(words[:12]).strip(" ,:;-")


def direct_scene(
    *,
    scene_id: str,
    kind: str,
    intent: str,
    context: str,
    accent: str,
    prior_concepts: list[str] | None = None,
) -> dict[str, Any]:
    """Return a renderer-neutral scene direction with one dominant idea."""
    candidates = list(CONCEPT_ROUTES.get(intent, CONCEPT_ROUTES["mechanism"]))
    prior_concepts = prior_concepts or []
    if prior_concepts:
        candidates = [item for item in candidates if item != prior_concepts[-1]] or candidates
    ordered = sorted(
        candidates,
        key=lambda item: hashlib.sha256(
            f"{scene_id}|{kind}|{intent}|{context}|{item}".encode("utf-8")
        ).hexdigest(),
    )
    concept_candidates = []
    for rank, item in enumerate(ordered[:3]):
        score = 92 - rank * 3 - (7 if prior_concepts and item == prior_concepts[-1] else 0)
        concept_candidates.append({
            "conceptFamily": item,
            "mechanism": CONCEPT_MECHANISMS[item],
            "proofObject": PROOF_OBJECT_BY_KIND.get(kind, "verified source object"),
            "score": score,
        })
    concept = max(concept_candidates, key=lambda item: item["score"])["conceptFamily"]
    if kind in {"graph", "timeline", "stack"}:
        motion_intents = ["enter", "connect", "emphasize"]
    elif kind in {"source", "terminal"}:
        motion_intents = ["enter", "emphasize"]
    else:
        motion_intents = ["enter", "micro", "emphasize"]
    return {
        "conceptFamily": concept,
        "conceptCandidates": concept_candidates,
        "selectionRationale": (
            f"Selected {concept} because it communicates the evidence relationship directly, "
            "stays distinct from the previous scene, and requires no invented documentary object."
        ),
        "composition": COMPOSITION_BY_KIND.get(kind, "open-editorial"),
        "compositionStrategy": "intentional-asymmetry",
        "focalIdea": _short_focal_idea(context),
        "specificityAnchor": PROOF_OBJECT_BY_KIND.get(kind, "verified source object"),
        "focalGroups": ["primary-proof", "editorial-annotation", "takeaway"],
        "readingOrder": ["context", "proof", "relationship", "takeaway"],
        "motionIntents": motion_intents,
        "paletteRoles": {
            "canvas": "canvas-neutral",
            "surface": "surface-raised",
            "text": "text-primary",
            "accent": accent,
        },
        "decorationPolicy": "semantic-only",
        "visualSourcePolicy": "real-source-or-official-brand-assets",
        "inventedMascotAllowed": False,
        "cameraPolicy": "locked",
        "density": "editorial-medium",
        "designCritique": {
            "philosophy": 4,
            "hierarchy": 4,
            "detailExecution": 4,
            "functionSpecificity": 4,
            "innovationRestraint": 4,
        },
    }


def review_art_direction_plan(
    scenes: list[dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed on generic, unreadable, or repetitive art direction."""
    rules = profile.get("artDirection") or {}
    if not rules:
        return {"passed": True, "score": 100, "failures": [], "warnings": []}
    failures: list[str] = []
    warnings: list[str] = []
    concepts: list[str] = []
    compositions: list[str] = []
    for index, scene in enumerate(scenes):
        label = str(scene.get("id") or f"scene[{index}]")
        direction = scene.get("artDirection")
        if not isinstance(direction, dict):
            failures.append(f"{label}: artDirection contract is missing")
            continue
        concept = str(direction.get("conceptFamily") or "")
        composition = str(direction.get("composition") or "")
        concepts.append(concept)
        compositions.append(composition)
        if not concept:
            failures.append(f"{label}: concept family is missing")
        candidates = list(direction.get("conceptCandidates") or [])
        if len(candidates) != 3 or len({item.get("conceptFamily") for item in candidates}) != 3:
            failures.append(f"{label}: director must compare three structurally distinct concepts")
        if not direction.get("selectionRationale"):
            failures.append(f"{label}: concept selection rationale is missing")
        if composition != COMPOSITION_BY_KIND.get(str(scene.get("kind")), "open-editorial"):
            failures.append(f"{label}: composition does not match the evidence relationship")
        if direction.get("compositionStrategy") != "intentional-asymmetry":
            failures.append(f"{label}: composition must use intentional asymmetry, not template symmetry")
        if not direction.get("specificityAnchor"):
            failures.append(f"{label}: product- or source-specific proof object is missing")
        groups = list(direction.get("focalGroups") or [])
        if not 1 <= len(groups) <= int(rules.get("maximumFocalGroups", 3)):
            failures.append(f"{label}: focal group count breaks the hierarchy limit")
        intents = set(direction.get("motionIntents") or [])
        if not intents or not intents <= ALLOWED_MOTION_INTENTS:
            failures.append(f"{label}: motion lacks a supported semantic intent")
        if direction.get("decorationPolicy") != "semantic-only":
            failures.append(f"{label}: decorative motion is not evidence-led")
        if direction.get("visualSourcePolicy") != "real-source-or-official-brand-assets":
            failures.append(f"{label}: visual source policy permits synthetic documentary evidence")
        if direction.get("inventedMascotAllowed") is not False:
            failures.append(f"{label}: invented mascots are forbidden")
        if direction.get("cameraPolicy") != "locked":
            failures.append(f"{label}: default camera must remain locked")
        focal = str(direction.get("focalIdea") or "")
        if len(focal.split()) > int(rules.get("maximumFocalIdeaWords", 12)):
            failures.append(f"{label}: focal idea is too long to read as one visual sentence")
        critique = direction.get("designCritique") or {}
        minimum_dimension = int(rules.get("minimumCritiqueDimension", 3))
        if critique.get("philosophy", 0) < int(rules.get("minimumPhilosophyScore", 4)):
            failures.append(f"{label}: design philosophy score requires another iteration")
        if any(int(value) < minimum_dimension for value in critique.values()) or len(critique) != 5:
            failures.append(f"{label}: five-dimension design critique did not pass")
        combined = " ".join(str(value) for value in direction.values()).casefold()
        for banned in rules.get("forbiddenAestheticDefaults") or []:
            if str(banned).casefold() in combined:
                failures.append(f"{label}: forbidden aesthetic default '{banned}'")
    if len(scenes) >= 4:
        max_concept_share = max(Counter(concepts).values(), default=0) / len(scenes)
        if max_concept_share > float(rules.get("maximumConceptTimelineShare", 0.4)):
            failures.append("one art-direction concept dominates too much of the episode")
    if scenes:
        for left, middle, right in zip(compositions, compositions[1:], compositions[2:]):
            if left == middle == right:
                failures.append("three consecutive scenes repeat the same composition family")
                break
    score = max(0, 100 - 12 * len(failures) - 3 * len(warnings))
    return {"passed": not failures, "score": score, "failures": failures, "warnings": warnings}
