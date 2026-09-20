"""Universal hook-to-thumbnail planning for technology and AI videos.

The planner decides whether a story should use the approved cinematic identity
arena or a source-first proof composition.  Image models receive only
brand-neutral scene instructions; exact identity marks are resolved and
composited later.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import re
from typing import Any

from .brand_assets import detect_brand_keys, normalize_brand_key
from .creative_profile import TOPIC_STYLE_ROUTES, classify_story, normalize_topic_class, thumbnail_hypotheses


ARENA_SIGNALS = (
    "agent", "team", "versus", " vs ", "fight", "battle", "war", "wins", "winner",
    "runs", "controls", "replaces", "for ai", "together", "handoff", "workspace",
    "headquarters", " hq", "home", "alliance", "ecosystem", "collaboration",
)
PROOF_SIGNALS = (
    "benchmark", "pricing", "price", "policy", "receipt", "test result", "failed",
    "failure", "catch", "limit", "lawsuit", "chart", "paper", "study", "cost",
)
ROUNDUP_SIGNALS = ("weekly", "roundup", "recap", "top stories", "this week")


@dataclass(frozen=True)
class HookRoute:
    hook_class: str
    hero_template: str
    reason: str
    evidence_display: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def split_headline(headline: str) -> tuple[str, str]:
    """Split a 2-6 word hook into two visually balanced lines."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*\??", headline.upper())
    if not 2 <= len(words) <= 5:
        raise ValueError("universal thumbnail headline must contain 2-5 words")
    best_index = 1
    best_delta = float("inf")
    for index in range(1, len(words)):
        left = " ".join(words[:index])
        right = " ".join(words[index:])
        delta = abs(len(left) - len(right) * 1.10)
        if delta < best_delta:
            best_index, best_delta = index, delta
    return " ".join(words[:best_index]), " ".join(words[best_index:])


def classify_thumbnail_route(
    headline: str,
    context: str,
    *,
    identity_count: int,
    source_count: int,
) -> HookRoute:
    """Choose a visual mechanism from the hook rather than a fixed template."""
    value = f" {headline} {context} ".casefold()
    if any(signal in value for signal in ROUNDUP_SIGNALS):
        return HookRoute("roundup", "source_package", "A roundup needs ranked story receipts.", "required")
    arena_hit = any(signal in value for signal in ARENA_SIGNALS)
    proof_hit = any(signal in value for signal in PROOF_SIGNALS)
    showdown = any(term in value for term in ("versus", " vs ", "fight", "battle", "war", "wins"))
    if identity_count >= 2 and showdown and source_count:
        return HookRoute(
            "comparison_proof", "source_package",
            "A verified comparison should visualize the shared test or result, not default to mascots.", "required",
        )
    if identity_count >= 2 and arena_hit:
        hook_class = (
            "showdown" if showdown
            else "control" if any(term in value for term in ("who runs", "controls", "owns"))
            else "category_analogy" if " for " in f" {headline.casefold()} " or headline.rstrip().endswith("?")
            else "coordination"
        )
        return HookRoute(hook_class, "identity_arena", "The click premise is an identity interaction.", "manifest_only")
    if proof_hit and source_count:
        return HookRoute("receipt", "source_package", "The source receipt creates the curiosity gap.", "required")
    if identity_count >= 2 and source_count == 0:
        return HookRoute("identity_consequence", "identity_arena", "No authentic proof asset is available; identities carry the hook.", "manifest_only")
    if identity_count >= 1 and arena_hit:
        return HookRoute("identity_consequence", "identity_arena", "The product identity is the visual subject.", "manifest_only")
    return HookRoute("product_proof", "source_package", "The story is clearer through authentic product evidence.", "required")


def build_creative_ideation(
    brief: dict[str, Any], keys: list[str], route: HookRoute,
) -> dict[str, Any]:
    """Create four story-specific visual sentences; the approved mascot look is only one option."""
    source_count = len(brief.get("source_images") or [])
    context = " ".join(filter(None, (
        str(brief.get("headline") or ""), str(brief.get("topic_context") or ""),
        str(brief.get("episode_format") or ""), str(brief.get("topic_class") or ""),
    )))
    requested_topic = str(brief.get("topic_class") or "").strip()
    story_type = (
        normalize_topic_class(requested_topic)
        if requested_topic else classify_story(context, source_count=source_count)
    )
    hypotheses = thumbnail_hypotheses(story_type.replace("-", " "), source_count=source_count)
    style_modes = TOPIC_STYLE_ROUTES[story_type]
    mechanism_by_archetype = {
        "agent_showdown": "identity_tableau",
        "product_plus_proof": "product_and_authentic_result",
        "proof_closeup": "source_receipt_closeup",
        "proof_split": "same_test_split_screen",
        "criterion_card": "single_result_scoreboard",
        "workflow_relay": "visual_handoff",
        "before_after": "authentic_before_after",
        "mechanism_map": "simple_process_map",
        "consequence_frame": "physical_consequence_metaphor",
        "broken_assumption": "promise_vs_limitation",
        "claim_vs_receipt": "claim_vs_source_receipt",
        "ranked_stack": "ranked_story_stack",
        "hero_story": "one_dominant_story",
        "evidence_grid": "source_evidence_grid",
    }
    source_required = {
        "product_plus_proof", "proof_closeup", "proof_split", "criterion_card", "before_after",
        "claim_vs_receipt", "ranked_stack", "hero_story", "evidence_grid",
    }
    visual_history = {
        str(value).casefold() for value in brief.get("recent_thumbnail_archetypes") or []
    }
    candidates: list[dict[str, Any]] = []
    for index, (hypothesis, style_mode) in enumerate(zip(hypotheses, style_modes), start=1):
        requires_source = hypothesis.archetype in source_required
        feasible = not requires_source or source_count > 0
        evidence_fit = 5 if requires_source and source_count else 4 if not requires_source else 1
        hook_fit = 5 if (
            (route.hook_class in {"showdown", "comparison_proof"} and hypothesis.archetype in {"agent_showdown", "proof_split", "criterion_card"})
            or (route.hook_class == "receipt" and hypothesis.archetype in {"proof_closeup", "claim_vs_receipt", "broken_assumption"})
            or (route.hook_class == "roundup" and hypothesis.archetype in {"hero_story", "ranked_stack", "evidence_grid"})
            or (route.hook_class in {"category_analogy", "coordination", "control"} and hypothesis.archetype in {"agent_showdown", "mechanism_map", "workflow_relay"})
        ) else 4
        identity_fit = 5 if hypothesis.archetype == "agent_showdown" and len(keys) >= 2 else 4
        repetition_penalty = 4 if hypothesis.archetype.casefold() in visual_history else 0
        cliche_penalty = 2 if hypothesis.archetype == "agent_showdown" else 0
        score = evidence_fit + hook_fit + identity_fit + 5 - repetition_penalty - cliche_penalty
        candidates.append({
            "candidate": index, "archetype": hypothesis.archetype,
            "visual_mechanism": mechanism_by_archetype.get(hypothesis.archetype, hypothesis.archetype),
            "angle": hypothesis.angle, "visual_sentence": hypothesis.visual_sentence,
            "style_mode": style_mode, "requires_authentic_source": requires_source,
            "feasible": feasible, "score": score,
            "score_breakdown": {
                "hook_fit": hook_fit, "evidence_fit": evidence_fit, "identity_fit": identity_fit,
                "mobile_clarity": 5, "repetition_penalty": repetition_penalty,
                "cliche_penalty": cliche_penalty,
            },
        })
    if route.hero_template == "identity_arena" and not any(
        item["archetype"] == "agent_showdown" for item in candidates
    ):
        candidates = [{
            "candidate": 1, "archetype": "agent_showdown",
            "visual_mechanism": "identity_tableau", "angle": route.hook_class,
            "visual_sentence": "The represented identities form one clear physical relationship that explains the hook.",
            "style_mode": "cinematic_duel", "requires_authentic_source": False,
            "feasible": len(keys) >= 1, "score": 18,
            "score_breakdown": {
                "hook_fit": 5, "evidence_fit": 4, "identity_fit": 5,
                "mobile_clarity": 5, "repetition_penalty": 0, "cliche_penalty": 1,
            },
        }, *candidates[:3]]
        for candidate_index, candidate in enumerate(candidates, start=1):
            candidate["candidate"] = candidate_index
    feasible_candidates = [item for item in candidates if item["feasible"]]
    recommended = max(feasible_candidates or candidates, key=lambda item: (item["score"], -item["candidate"]))
    return {
        "schema_version": "thumbnail-ideation.v1", "story_type": story_type,
        "reference_policy": "reuse the quality bar and reasoning process, never the same composition by default",
        "candidate_count": len(candidates), "candidates": candidates,
        "recommended_candidate": recommended["candidate"],
        "recommended_archetype": recommended["archetype"],
        "recommended_visual_mechanism": recommended["visual_mechanism"],
        "selection_reason": "highest hook/evidence/identity/mobile score after repetition and cliché penalties",
    }


def _identity_keys(brief: dict[str, Any]) -> list[str]:
    explicit = [str(value) for value in brief.get("identity_keys") or []]
    values = explicit or [str(value) for value in brief.get("represented_companies") or []]
    keys: list[str] = []
    for value in values:
        key = normalize_brand_key(value)
        if key and key not in keys:
            keys.append(key)
    if not keys:
        keys = detect_brand_keys(
            [str(value) for value in brief.get("represented_companies") or []],
            context=" ".join((str(brief.get("headline") or ""), str(brief.get("topic_context") or ""))),
            source_urls=[str(value) for value in brief.get("source_urls") or []],
        )
    if len(keys) > 5:
        raise ValueError("identity-arena thumbnails support at most five mobile-visible identities")
    return keys


def _choose_focal_key(brief: dict[str, Any], keys: list[str]) -> str:
    requested = normalize_brand_key(str(brief.get("focal_identity_key") or ""))
    if requested in keys:
        return requested
    focal_text = str(brief.get("focal_subject") or "")
    detected = detect_brand_keys(context=focal_text)
    return next((key for key in detected if key in keys), keys[0] if keys else "")


def _owner_keys(brief: dict[str, Any], keys: list[str], focal_key: str) -> list[str]:
    owners: list[str] = []
    for value in brief.get("owner_identity_keys") or []:
        key = normalize_brand_key(str(value))
        if key and key in keys and key != focal_key and key not in owners:
            owners.append(key)
    return owners[:1]


def _panel(x: int, y: int, size: int, *, tone: str) -> dict[str, int | str]:
    return {"x": x, "y": y, "size": size, "panel_tone": tone}


def _badge(x: int, y: int, width: int = 156) -> dict[str, int | bool]:
    return {"x": x, "y": y, "width": width, "height": 58, "badge": True}


def _candidate_layouts(
    keys: list[str], focal_key: str, owner_keys: list[str], headline: str,
) -> list[dict[str, Any]]:
    line_one, line_two = split_headline(headline)
    supporting = [key for key in keys if key != focal_key and key not in owner_keys]
    mascot_keys = [focal_key, *supporting[:3]] if focal_key else supporting[:4]
    badge_keys = [*owner_keys, *supporting[3:]]
    count = len(mascot_keys)
    anchor_sets = {
        "coordinator_lineup": {
            1: [(940, 330, 230)],
            2: [(960, 300, 215), (330, 480, 145)],
            3: [(940, 285, 210), (260, 470, 135), (520, 485, 130)],
            4: [(994, 248, 205), (228, 445, 132), (461, 451, 132), (690, 456, 116)],
        },
        "equal_showdown": {
            1: [(640, 420, 230)],
            2: [(350, 410, 175), (930, 410, 175)],
            3: [(640, 430, 105), (340, 405, 175), (940, 405, 175)],
            4: [(640, 420, 100), (270, 405, 165), (1010, 405, 165), (640, 615, 90)],
        },
        "agent_headquarters": {
            1: [(875, 255, 225)],
            2: [(900, 235, 215), (320, 505, 120)],
            3: [(900, 220, 210), (270, 500, 112), (520, 500, 108)],
            4: [(880, 190, 205), (250, 505, 105), (455, 500, 105), (650, 515, 100)],
        },
        "shared_home": {
            1: [(980, 405, 150)],
            2: [(980, 405, 140), (480, 520, 95)],
            3: [(980, 405, 130), (430, 520, 88), (610, 520, 84)],
            4: [(980, 405, 120), (430, 520, 82), (590, 520, 82), (745, 520, 78)],
        },
    }
    layouts = [
        {
            "style_mode": "coordinator_lineup", "hook_strategy": "category or coordination",
            "headline": {"left": 48, "top": 38, "width": 700, "dark": True, "lines": [line_one, line_two]},
            "mascot_anchors": anchor_sets["coordinator_lineup"][count],
            "badge_anchors": [(1138, 65), (760, 650)],
        },
        {
            "style_mode": "equal_showdown", "hook_strategy": "conflict or control",
            "headline": {"left": 48, "top": 35, "width": 760, "dark": True, "lines": [line_one, line_two]},
            "mascot_anchors": anchor_sets["equal_showdown"][count],
            "badge_anchors": [(1125, 650), (1010, 650)],
        },
        {
            "style_mode": "agent_headquarters", "hook_strategy": "new category or hierarchy",
            "headline": {"left": 48, "top": 38, "width": 650, "dark": True, "lines": [line_one, line_two]},
            "mascot_anchors": anchor_sets["agent_headquarters"][count],
            "badge_anchors": [(1125, 650), (1010, 650)],
        },
        {
            "style_mode": "shared_home", "hook_strategy": "consequence or handoff",
            "headline": {"left": 48, "top": 38, "width": 710, "dark": False, "lines": [line_one, line_two]},
            "mascot_anchors": anchor_sets["shared_home"][count],
            "badge_anchors": [(1190, 650), (1060, 650)],
        },
    ]
    for layout in layouts:
        for mascot_index, (key, (x, y, size)) in enumerate(zip(mascot_keys, layout.pop("mascot_anchors"))):
            layout[key] = _panel(x, y, size, tone="black" if mascot_index == 0 else "white")
        for key, (x, y) in zip(badge_keys, layout.pop("badge_anchors")):
            layout[key] = _badge(x, y)
    return layouts


def _plate_prompt(layout: dict[str, Any], mascot_count: int, *, light: bool) -> str:
    colors = ("muted-slate", "moss-green", "warm-clay", "charcoal-black")[:mascot_count]
    subject_lines = []
    for index, color in enumerate(colors):
        scale = (
            "large equal-weight" if layout["style_mode"] == "equal_showdown" and index < 2
            else "large dominant" if index == 0 else "smaller supporting"
        )
        panel = "blank black" if index == 0 else "blank white"
        subject_lines.append(f"one {scale} {color} soft-vinyl mascot with a large front-facing {panel} square display head")
    scene = "warm off-white handcrafted paper studio" if light else "matte-black physical photography studio"
    composition = {
        "coordinator_lineup": "Put the dominant first mascot on the right and arrange supporting mascots in a clean lower-left lineup facing it.",
        "equal_showdown": "Put the first two mascots on opposite lower sides facing each other with a clean central tension gap; any additional mascots stay smaller and secondary.",
        "agent_headquarters": "Put the dominant mascot high on the right-center and arrange supporting mascots approaching from the lower left in a clear hierarchy.",
        "shared_home": "Build a handcrafted architectural doorway on the right; place the dominant mascot at the doorway and supporting mascots approaching from the lower-left.",
    }[str(layout["style_mode"])]
    return (
        "Generate exactly one premium 16:9 BACKGROUND PLATE at 2K for an original technology-news thumbnail. "
        "This is a brand-neutral photographed miniature character plate, not a finished thumbnail. "
        f"Scene: {scene}, practical commercial lighting, believable floor contact shadows, controlled reflections. "
        f"Subjects: exactly {mascot_count} figures total: " + "; ".join(subject_lines) + ". "
        f"Composition family: {layout['style_mode'].replace('_', ' ')}. {composition} Arrange every figure with deliberate hierarchy and clear separation. "
        "Reserve at least 40 percent clean negative space across the upper-left for deterministic headline typography. "
        "Every blank display panel must be unobstructed, front-facing, flat, and large enough for exact official logos composited later. "
        "Use tactile painted resin and soft vinyl with tiny real-world imperfections, crisp material edges, a 40mm product-photography camera, and premium campaign art direction. "
        "Do not create exact official logos or any identity marks; the compositor adds verified assets afterward. "
        "STRICTLY EXCLUDE: text, letters, numbers, pseudo-writing, logos, brand marks, UI, browser windows, app screens, people, faces, eyes, mouths, skin, armor, weapons, boxing gloves, generic robots, sci-fi stages, podiums, holograms, neon fog, liquid chrome, random glyphs, watermarks, extra characters, duplicate limbs, malformed hands, and fake interface elements."
    )


def build_identity_arena_plan(brief: dict[str, Any], keys: list[str], focal_key: str) -> dict[str, Any]:
    owner_keys = _owner_keys(brief, keys, focal_key)
    layouts = _candidate_layouts(keys, focal_key, owner_keys, str(brief["headline"]))
    mascot_count = min(4, len(keys) - len(owner_keys))
    prompts = []
    for index, layout in enumerate(layouts):
        prompts.append({
            "style_mode": layout["style_mode"], "archetype": "identity_arena",
            "generation_mode": "nano-banana-2",
            "prompt": _plate_prompt(layout, mascot_count, light=index == 3),
            "panel_spec": layout,
        })
    return {
        "schema_version": "identity-arena-plan.v1", "focal_identity_key": focal_key,
        "owner_identity_keys": owner_keys, "mascot_count": mascot_count,
        "identity_keys": keys, "candidates": prompts,
        "logo_policy": "exact verified assets composited after blank-panel generation",
        "background_removal": "never used for flat logos or full-frame mascot plates",
    }


def build_universal_thumbnail_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Expand a minimal request into a production-ready routed thumbnail brief."""
    planned = deepcopy(brief)
    if not str(planned.get("headline") or "").strip():
        raise ValueError("universal thumbnail planning requires a headline")
    planned.setdefault("source_images", [])
    planned.setdefault("evidence_ids", [])
    keys = _identity_keys(planned)
    route = classify_thumbnail_route(
        str(planned["headline"]), str(planned.get("topic_context") or ""),
        identity_count=len(keys), source_count=len(planned["source_images"]),
    )
    recent_archetypes = {
        str(value).casefold() for value in planned.get("recent_thumbnail_archetypes") or []
    }
    if (
        route.hero_template == "identity_arena"
        and planned["source_images"]
        and {"identity_arena", "agent_showdown", "identity_tableau"} & recent_archetypes
    ):
        route = HookRoute(
            "diversity_rotation", "source_package",
            "Recent channel packaging already used the identity tableau; rotate to authentic evidence.", "required",
        )
    planned["schema_version"] = "thumbnail-automation.v3"
    planned["route_decision"] = route.as_dict()
    planned["creative_ideation"] = build_creative_ideation(planned, keys, route)
    planned["hero_template"] = route.hero_template
    planned["identity_keys"] = keys
    planned.setdefault("represented_companies", keys)
    if route.hero_template == "identity_arena":
        if not keys:
            raise ValueError("identity-arena route requires at least one resolvable company/product identity")
        focal_key = _choose_focal_key(planned, keys)
        planned["focal_identity_key"] = focal_key
        planned["background_mode"] = "generated_identity_plates"
        planned["identity_arena_plan"] = build_identity_arena_plan(planned, keys, focal_key)
        planned.setdefault("generate_backplates", True)
        planned.setdefault("backplate_model", "nano-banana-2")
        planned.setdefault("backplate_fallback_model", "nano-banana")
        planned.setdefault("backplate_resolution", "2k")
        planned["require_brand_identity"] = True
    elif not planned["source_images"]:
        raise ValueError("source-first thumbnail route requires at least one accepted source image")
    return planned
