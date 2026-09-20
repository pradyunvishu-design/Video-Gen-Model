"""Build a dense, evidence-linked visual timeline independently from narration beats."""
from __future__ import annotations

from collections import defaultdict
import re

from .config import CONCEPT_ANIMATIONS_ENABLED, GENERATIVE_VISUALS_ENABLED
from .models import EpisodeProject, Shot
from .visual_mix import apply_house_mix


def shot_limit(asset_type: str) -> float:
    if asset_type in {"screen_recording", "official_demo"}:
        return 18.0
    if asset_type in {"generated_video", "concept_animation"}:
        return 10.0 if asset_type == "concept_animation" else 8.0
    if asset_type in {"motion_graphic", "chapter_card"}:
        return 8.0
    return 12.0


def motion_template_for(asset_type: str, purpose: str) -> str:
    if purpose == "show_intro":
        return "news_intro"
    if asset_type == "chapter_card":
        return "chapter_title"
    if asset_type == "chart":
        return "stat_reveal"
    if purpose == "comparison":
        return "comparison"
    if purpose in {"evidence", "observation", "test_setup", "model_test"}:
        return "evidence_focus"
    if purpose in {"analysis", "implication", "weekly_recap"}:
        return "orbit_map"
    return "step_flow"


def concept_animation_score(narration: str, visual_direction: str, purpose: str) -> int:
    """Rank beats where a brief visual metaphor explains an invisible mechanism."""
    if purpose not in {"context", "analysis", "implication", "evidence", "test_setup", "comparison"}:
        return 0
    text = f"{narration} {visual_direction}".casefold()
    score = 0
    mechanism_terms = {
        "because": 1, "inside": 1, "process": 3, "workflow": 3, "pipeline": 3,
        "turns": 2, "converts": 3, "transforms": 3, "moves": 1, "passes": 1,
        "from one": 2, "step": 1, "layer": 2, "route": 2, "flow": 2,
        "before": 1, "after": 1, "instead": 1, "how": 2,
    }
    for term, weight in mechanism_terms.items():
        if term in text:
            score += weight
    if re.search(r"\b(?:first|then|next|finally)\b", text):
        score += 2
    # Product specs, quotes, dates, and benchmarks should remain attached to
    # real sources or deterministic graphics rather than invented imagery.
    if re.search(r"(?:\$|\b\d[\d,.]*\s?(?:%|gb|mb|fps|k|m|b|ms|seconds?)\b)", text):
        score -= 3
    return max(0, score)


def build_shot_plan(
    project: EpisodeProject, target_duration: float | None = None, *, min_shots: int = 70, max_shots: int = 110,
) -> list[Shot]:
    if not project.script:
        raise ValueError("script is required before shot planning")
    beats = project.script.beats
    duration = target_duration or max(480.0, min(720.0, project.script.word_count / 2.45))
    total_shots = max(min_shots, min(max_shots, round(duration / 4.9)))
    allocations = [0] * len(beats)
    if total_shots >= len(beats):
        allocations = [1] * len(beats)
        while sum(allocations) < total_shots:
            index = max(
                range(len(beats)),
                key=lambda i: (len(beats[i].narration.split()) * (1.35 if beats[i].purpose == "hook" else 1))
                / (allocations[i] + 0.65),
            )
            allocations[index] += 1
    else:
        selected = {
            round(index * (len(beats) - 1) / max(1, total_shots - 1))
            for index in range(total_shots)
        }
        for index in selected:
            allocations[index] = 1
    concept_count = min(3, max(1, round(duration / 210))) if CONCEPT_ANIMATIONS_ENABLED else 0
    concept_candidates = sorted(
        (
            (concept_animation_score(beat.narration, beat.visual_direction, beat.purpose), index)
            for index, beat in enumerate(beats)
            if allocations[index] >= 2
        ),
        key=lambda item: (-item[0], item[1]),
    )
    concept_beat_indices = {
        index for score, index in concept_candidates[:concept_count] if score >= 4
    }
    hero_count = (1 if max_shots <= 15 else 5) if GENERATIVE_VISUALS_ENABLED else 0
    weekly = bool(project.brief and project.brief.episode_format == "weekly_roundup")
    hero_slots = (
        {round((index + 0.65) * (total_shots - 1) / hero_count) for index in range(hero_count)}
        if hero_count else set()
    )
    source_use: dict[str, int] = defaultdict(int)
    number_claim_ids = {claim.id for claim in project.claims if claim.kind == "number"}
    shots: list[Shot] = []
    for beat_index, beat in enumerate(beats):
        cuts_per_beat = allocations[beat_index]
        if not cuts_per_beat:
            continue
        candidates = beat.source_ids or ([project.brief.source_ids[0]] if project.brief and project.brief.source_ids else [])
        for cut_index in range(cuts_per_beat):
            global_index = len(shots)
            # Prefer the least-used cited source. This preserves evidence
            # coverage and avoids mechanically cycling the same launch page.
            source_id = min(
                candidates, key=lambda value: (source_use[value], candidates.index(value))
            ) if candidates else None
            if weekly and beat.purpose == "show_intro" and cut_index == 0:
                asset_type = "motion_graphic"
                source_id = None
            # A generated hero may fill a genuine visual gap, but must never
            # displace a cited launch page, paper, repository, demo, or article.
            elif global_index in hero_slots and not source_id:
                asset_type = "generated_video"
                source_id = None
            elif beat.purpose in {"story_intro", "transition", "weekly_recap", "outro"} and cut_index == 0:
                asset_type = "chapter_card"
                source_id = None
            elif number_claim_ids.intersection(beat.claim_ids) and cut_index == cuts_per_beat - 1:
                asset_type = "chart"
                source_id = None
            elif beat_index in concept_beat_indices and cut_index == cuts_per_beat - 1:
                asset_type = "concept_animation"
                source_id = None
            elif beat.purpose in {"comparison", "implication", "verdict"} and cut_index == cuts_per_beat - 1:
                asset_type = "motion_graphic"
                source_id = None
            elif source_id and cut_index == 0:
                asset_type = "screen_recording"
            elif source_id:
                asset_type = "screenshot"
            else:
                asset_type = "motion_graphic"
            if source_id:
                source_use[source_id] += 1
            motion_cycle = ["push_in", "pan_right", "locked", "pan_left", "pull_out"]
            focus_cycle = [(0.5, 0.48), (0.42, 0.5), (0.58, 0.5), (0.5, 0.42)]
            focus_x, focus_y = focus_cycle[global_index % len(focus_cycle)]
            if asset_type in {"screenshot", "screen_recording", "official_demo"}:
                # Source captures use a centered subject-safe crop. Semantic
                # emphasis belongs to an annotation, not an off-axis camera.
                focus_x = focus_y = 0.5
            shots.append(Shot(
                id=f"shot_{len(shots) + 1:03d}", beat_id=beat.id, asset_type=asset_type,
                source_id=source_id, prompt=beat.visual_direction,
                semantic_target=f"{beat.narration} {beat.visual_direction}", start_seconds=0,
                duration_seconds=4.0, focus_x=focus_x, focus_y=focus_y,
                motion_style=(
                    "locked" if asset_type in {"screen_recording", "official_demo", "concept_animation"}
                    else "push_in" if asset_type == "screenshot"
                    else motion_cycle[global_index % len(motion_cycle)]
                ),
                transition="dissolve" if asset_type == "chapter_card" else "cut",
                # Source evidence should feel like native editorial footage, not
                # a screenshot placed inside a decorative laptop/browser shell.
                presentation="full_bleed",
                motion_template=motion_template_for(asset_type, beat.purpose),
                rights_note=(
                    "Public source captured for editorial commentary; verify usage rights before publication."
                    if source_id else (
                        "Original explanatory visualization; not source evidence. Generated with Magic Hour from a text-free local concept plate."
                        if asset_type == "concept_animation" else (
                            "Original exact motion graphic rendered locally for this episode."
                            if asset_type != "generated_video"
                            else "Original Magic Hour motion-design clip generated from a local graphic plate."
                        )
                    )
                ),
            ))
    weight_by_type = {
        "screen_recording": 1.75, "official_demo": 1.9, "generated_video": 1.25,
        "concept_animation": 1.05,
        "screenshot": 0.72, "generated_image": 0.82, "motion_graphic": 0.78,
        "chart": 0.82, "chapter_card": 0.55,
    }
    weights = []
    for shot in shots:
        beat = next(item for item in beats if item.id == shot.beat_id)
        pace = 0.58 if beat.purpose == "hook" else 1.0
        weights.append(weight_by_type[shot.asset_type] * pace)
    remaining = duration
    active = set(range(len(shots)))
    assigned = [0.0] * len(shots)
    while active and remaining > 0.001:
        unit = remaining / sum(weights[index] for index in active)
        capped = []
        for index in active:
            proposed = weights[index] * unit
            maximum = shot_limit(shots[index].asset_type)
            if proposed > maximum:
                assigned[index] = maximum
                remaining -= maximum
                capped.append(index)
        if not capped:
            for index in active:
                assigned[index] = weights[index] * unit
            remaining = 0
            break
        active.difference_update(capped)
    if remaining > 0.1:
        raise ValueError(f"shot plan cannot cover the requested duration; {remaining:.2f}s remains")
    cursor = 0.0
    for index, shot in enumerate(shots):
        shot.start_seconds = round(cursor, 3)
        shot.duration_seconds = round(max(1.2, assigned[index]), 3)
        cursor += shot.duration_seconds
    correction = duration - cursor
    if shots and abs(correction) > 0.001:
        shots[-1].duration_seconds = round(shots[-1].duration_seconds + correction, 3)
    if max_shots > 15 and any(shot.source_id for shot in shots):
        apply_house_mix(shots, duration)
    return shots


def validate_shot_plan(
    shots: list[Shot], expected_duration: float, *, min_shots: int = 70, max_shots: int = 110,
) -> dict:
    durations = sorted(shot.duration_seconds for shot in shots)
    median = durations[len(durations) // 2] if durations else 0
    covered = sum(shot.duration_seconds for shot in shots)
    failures = []
    ai_stills = [shot.id for shot in shots if shot.asset_type == "generated_image"]
    if ai_stills:
        failures.append(f"standalone generated-image shots are forbidden: {ai_stills[:10]}")
    if len(shots) < min_shots or len(shots) > max_shots:
        failures.append(f"shot count {len(shots)} is outside {min_shots}-{max_shots}")
    if median > 6:
        failures.append(f"median shot duration {median:.2f}s exceeds 6s")
    concept_shots = [(index, shot) for index, shot in enumerate(shots) if shot.asset_type == "concept_animation"]
    concept_limit = min(3, max(1, round(expected_duration / 210)))
    if len(concept_shots) > concept_limit:
        failures.append(f"concept animation count {len(concept_shots)} exceeds restrained limit {concept_limit}")
    for index, shot in concept_shots:
        if shot.source_id:
            failures.append(f"{shot.id} concept animation must not masquerade as sourced footage")
        if "explanatory visualization" not in shot.rights_note.casefold():
            failures.append(f"{shot.id} concept animation lacks an explanatory-visualization disclosure")
        neighbors = shots[max(0, index - 2):index] + shots[index + 1:index + 3]
        if not any(item.source_id or item.asset_type == "official_demo" for item in neighbors):
            failures.append(f"{shot.id} concept animation is not anchored next to source evidence")
    for shot in shots:
        limit = shot_limit(shot.asset_type)
        if shot.duration_seconds > limit + 0.01:
            failures.append(f"{shot.id} exceeds {limit}s")
    if abs(covered - expected_duration) > max(5, expected_duration * 0.02):
        failures.append(f"timeline covers {covered:.1f}s, expected {expected_duration:.1f}s")
    return {"passed": not failures, "shot_count": len(shots), "median_seconds": median, "covered_seconds": covered, "failures": failures}
