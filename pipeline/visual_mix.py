"""Duration-based visual allocation and render-readiness gates.

The house edit is footage-led: 55% rights-cleared YouTube b-roll, 20% article
evidence, 15% motion graphics, and 10% miscellaneous editorial utility.  Shot
counts are never used as a proxy for screen time; every check is duration
weighted.
"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from .clip_alignment import fingerprint_shot
from .config import SEEDANCE_MOTION_ENABLED, SEEDANCE_MOTION_SHARE
from .models import EpisodeProject, Shot


POLICY_PATH = Path(__file__).resolve().parents[1] / "configs" / "video_visual_mix.json"
CATEGORIES = ("youtube_broll", "article_evidence", "motion_graphics", "miscellaneous")
MOTION_TYPES = {
    "generated_image", "generated_video", "concept_animation", "motion_graphic",
    "chapter_card", "chart",
}


def load_policy(path: Path = POLICY_PATH) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    shares = [float(policy["categories"][name]["target_share"]) for name in CATEGORIES]
    if abs(sum(shares) - 1.0) > 0.0001:
        raise ValueError("visual-mix target shares must sum to 1.0")
    return policy


def _is_youtube_url(value: str) -> bool:
    try:
        host = (urlparse(value).hostname or "").casefold()
    except Exception:
        return False
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def _rights_for_shot(project: EpisodeProject, shot: Shot) -> list[dict]:
    return [
        entry for entry in project.rights
        if entry.get("shot_id") == shot.id
        or (shot.asset_path and entry.get("asset_path") == shot.asset_path)
    ]


def classify_shot(project: EpisodeProject, shot: Shot) -> str:
    if shot.visual_category != "auto":
        return shot.visual_category
    rights = _rights_for_shot(project, shot)
    source = next((item for item in project.sources if item.id == shot.source_id), None)
    urls = [str(item.get("source_url") or "") for item in rights]
    if source:
        urls.append(str(source.url))
    if any(_is_youtube_url(value) for value in urls):
        return "youtube_broll"
    if shot.asset_type in MOTION_TYPES:
        return "motion_graphics"
    if shot.asset_type == "screenshot":
        return "article_evidence"
    return "miscellaneous"


def _category_counts(total_shots: int, total_duration: float, policy: dict) -> dict[str, int]:
    raw = {
        name: total_shots * float(policy["categories"][name]["target_share"])
        for name in CATEGORIES
    }
    counts = {name: max(1, int(value)) for name, value in raw.items()}
    while sum(counts.values()) < total_shots:
        name = max(CATEGORIES, key=lambda item: raw[item] - counts[item])
        counts[name] += 1
    while sum(counts.values()) > total_shots:
        name = max(
            (item for item in CATEGORIES if counts[item] > 1),
            key=lambda item: counts[item] - raw[item],
        )
        counts[name] -= 1
    minimums = {
        name: math.ceil(
            total_duration * float(policy["categories"][name]["target_share"])
            / float(policy["categories"][name]["max_shot_seconds"])
        )
        for name in CATEGORIES
    }
    for name in CATEGORIES:
        while counts[name] < minimums[name]:
            donor = max(
                (item for item in CATEGORIES if counts[item] > minimums[item]),
                key=lambda item: counts[item] - minimums[item],
                default=None,
            )
            if donor is None:
                raise ValueError("shot count is too low to satisfy visual-mix duration limits")
            counts[donor] -= 1
            counts[name] += 1
    return counts


def _distributed_categories(counts: dict[str, int]) -> list[str]:
    """Interleave categories instead of creating long blocks of one treatment."""
    total = sum(counts.values())
    used = Counter()
    result: list[str] = []
    for index in range(total):
        available = [name for name in CATEGORIES if used[name] < counts[name]]
        choice = max(
            available,
            key=lambda name: ((index + 1) * counts[name] / total) - used[name],
        )
        result.append(choice)
        used[choice] += 1
    return result


def _seedance_utility_score(shot: Shot) -> int:
    """Prefer generated motion for invisible mechanisms, not factual evidence."""
    text = f"{shot.prompt} {shot.semantic_target}".casefold()
    useful = {
        "flow": 4, "route": 4, "pipeline": 4, "workflow": 4, "process": 4,
        "transform": 4, "connect": 3, "mapping": 3, "mechanism": 3,
        "before": 2, "after": 2, "versus": 2, "compare": 2, "timeline": 2,
        "layer": 2, "scale": 2, "sequence": 2, "step": 2,
    }
    contraindicated = {
        "benchmark": 5, "exact": 4, "quote": 4, "source": 3, "article": 3,
        "screenshot": 3, "documentation": 3, "table": 3, "chart": 3,
        "terminal": 2, "code": 2,
    }
    return sum(weight for token, weight in useful.items() if token in text) - sum(
        weight for token, weight in contraindicated.items() if token in text
    )


def apply_seedance_motion_split(
    shots: list[Shot], *, share: float | None = None, enabled: bool | None = None,
) -> list[Shot]:
    """Route about half of motion time to silent, text-free Seedance inserts.

    The overall 55/20/15/10 editorial mix is unchanged.  Seedance is only a
    rendering method inside the motion-graphics category; exact typography,
    logos, charts, citations, and numeric evidence stay deterministic.
    """
    enabled = SEEDANCE_MOTION_ENABLED if enabled is None else enabled
    share = SEEDANCE_MOTION_SHARE if share is None else min(1.0, max(0.0, share))
    motion_indices = [
        index for index, shot in enumerate(shots)
        if shot.visual_category == "motion_graphics"
    ]
    if not enabled or not motion_indices or share <= 0:
        return shots

    target = min(len(motion_indices), max(1, int(len(motion_indices) * share + 0.5)))
    candidates = [
        index for index in motion_indices
        if shots[index].asset_type != "concept_animation"
    ]
    # Choose useful beats first, then favor an even spread across the edit.
    selected: list[int] = []
    while candidates and len(selected) < target:
        best = max(
            candidates,
            key=lambda index: (
                _seedance_utility_score(shots[index]),
                min((abs(index - used) for used in selected), default=len(shots)),
                -index,
            ),
        )
        selected.append(best)
        candidates.remove(best)

    for index in selected:
        shot = shots[index]
        shot.asset_type = "generated_video"
        shot.motion_template = "seedance_editorial"
        shot.motion_style = "locked"
        shot.transition = "cut"
        shot.presentation = "full_bleed"
        shot.source_id = None
        shot.asset_path = ""
        shot.fallback_reason = "no_relevant_rights_cleared_footage"
        shot.rights_note = (
            "Original silent text-free Seedance editorial insert; not source evidence. "
            "All exact words, marks, numbers, and citations are rendered locally."
        )
    return shots


def apply_house_mix(shots: list[Shot], total_duration: float, policy: dict | None = None) -> list[Shot]:
    """Assign the house mix to a storyboard and retime it to exact target shares."""
    if not shots:
        return shots
    policy = policy or load_policy()
    counts = _category_counts(len(shots), total_duration, policy)
    categories = _distributed_categories(counts)
    special_motion_indices = [
        index for index, shot in enumerate(shots)
        if shot.asset_type in {"generated_video", "concept_animation"}
    ]
    motion_indices = [index for index, name in enumerate(categories) if name == "motion_graphics"]
    for special in special_motion_indices[:len(motion_indices)]:
        if categories[special] == "motion_graphics":
            continue
        replacement = next(
            (index for index in motion_indices if index not in special_motion_indices), None
        )
        if replacement is None:
            break
        categories[special], categories[replacement] = categories[replacement], categories[special]
        motion_indices.remove(replacement)
    sourced = [index for index, shot in enumerate(shots) if shot.source_id]
    article_needed = counts["article_evidence"]
    if len(sourced) < article_needed:
        raise ValueError(
            f"visual mix needs {article_needed} article-evidence shots but only {len(sourced)} shots cite sources"
        )

    # Article evidence can only occupy cited beats. Swap category assignments
    # deterministically so the global allocation remains unchanged.
    article_indices = {index for index, name in enumerate(categories) if name == "article_evidence"}
    invalid = sorted(index for index in article_indices if not shots[index].source_id)
    replacements = [
        index for index in sourced
        if index not in article_indices and categories[index] != "motion_graphics"
    ]
    for old, new in zip(invalid, replacements):
        categories[old], categories[new] = categories[new], categories[old]

    target_seconds = {
        name: total_duration * float(policy["categories"][name]["target_share"])
        for name in CATEGORIES
    }
    durations_by_category: dict[str, list[float]] = {}
    for name in CATEGORIES:
        count = counts[name]
        average = target_seconds[name] / count
        if average <= 6:
            short_count = math.ceil(count / 2)
            short_seconds = max(1.2, average - 0.3)
            long_count = count - short_count
            long_seconds = (
                (target_seconds[name] - short_count * short_seconds) / long_count
                if long_count else short_seconds
            )
            raw_durations = [short_seconds] * short_count + [long_seconds] * long_count
        else:
            short_count = math.ceil(count * 0.55)
            long_count = count - short_count
            maximum = float(policy["categories"][name]["max_shot_seconds"])
            minimum_short = (
                (target_seconds[name] - long_count * maximum) / short_count
                if short_count else average
            )
            short_seconds = max(minimum_short, min(5.8, average))
            long_seconds = (
                (target_seconds[name] - short_count * short_seconds) / long_count
                if long_count else short_seconds
            )
            if long_seconds > maximum + 0.001:
                raise ValueError(f"{name} allocation exceeds its {maximum:.0f}s shot limit")
            raw_durations = [short_seconds] * short_count + [long_seconds] * long_count
        rounded = [round(value, 3) for value in raw_durations]
        rounded[-1] = round(rounded[-1] + target_seconds[name] - sum(rounded), 3)
        durations_by_category[name] = rounded
    duration_indices = {name: 0 for name in CATEGORIES}
    cursor = 0.0
    for shot, category in zip(shots, categories):
        shot.visual_category = category
        shot.fallback_reason = ""
        if category == "youtube_broll":
            shot.asset_type = "official_demo"
            shot.asset_path = ""
            shot.motion_style = "locked"
            shot.presentation = "full_bleed"
            shot.rights_note = "YouTube b-roll placeholder; approved rights record and timestamp required before render."
        elif category == "article_evidence":
            shot.asset_type = "screenshot"
            shot.motion_style = "push_in"
            shot.presentation = "full_bleed"
            shot.rights_note = "Cited source-page evidence; capture and publication rights review required."
        elif category == "motion_graphics":
            if shot.asset_type not in {"generated_video", "concept_animation"}:
                shot.asset_type = "motion_graphic"
            shot.source_id = None
            shot.asset_path = ""
            shot.fallback_reason = "no_relevant_rights_cleared_footage"
            shot.rights_note = (
                "Original explanatory visualization; not source evidence. "
                "Used only where relevant rights-cleared footage is unavailable."
            )
        else:
            beat_hint = f"{shot.prompt} {shot.semantic_target}".casefold()
            shot.asset_type = "chapter_card" if any(
                token in beat_hint for token in ("intro", "transition", "outro", "recap")
            ) else "screen_recording"
            shot.rights_note = "Editorial utility visual; provenance and rights review required before publication."
        shot.start_seconds = round(cursor, 3)
        assigned_seconds = durations_by_category[category][duration_indices[category]]
        duration_indices[category] += 1
        shot.duration_seconds = assigned_seconds
        cursor += shot.duration_seconds
    shots[-1].duration_seconds = round(shots[-1].duration_seconds + (total_duration - cursor), 3)
    return apply_seedance_motion_split(shots)


def review_youtube_readiness(project: EpisodeProject, policy: dict | None = None) -> dict:
    policy = policy or load_policy()
    minimum_alignment = float(policy["minimum_youtube_alignment_score"])
    max_uses = int(policy["maximum_youtube_asset_uses"])
    youtube_shots = [shot for shot in project.shots if classify_shot(project, shot) == "youtube_broll"]
    # Rendering may split one editorial shot into short, contiguous pacing
    # fragments (``__pace_01``, ``__pace_02``). Those fragments are one source
    # use, not repeated B-roll. Count unique logical shots per fingerprint so
    # the reuse gate still catches the same asset in separate timeline slots.
    logical_uses: dict[str, set[str]] = {}
    for shot in youtube_shots:
        fingerprint = fingerprint_shot(shot)
        if not fingerprint:
            continue
        logical_id = shot.id.split("__pace_", 1)[0]
        logical_uses.setdefault(fingerprint, set()).add(logical_id)
    fingerprints = Counter({key: len(value) for key, value in logical_uses.items()})
    failures: list[str] = []
    ready_seconds = 0.0
    for shot in youtube_shots:
        rights = _rights_for_shot(project, shot)
        source_footage_rights = [
            entry for entry in rights
            if _is_youtube_url(str(entry.get("source_url") or ""))
            or entry.get("capture_mode") == "official_source_timestamped_excerpt"
        ]
        approved = [
            entry for entry in source_footage_rights
            if entry.get("capture_mode") in {
                "licensed_timestamped_excerpt", "official_source_timestamped_excerpt",
            }
            and entry.get("rights_basis")
            and (
                entry.get("capture_mode") == "licensed_timestamped_excerpt"
                or entry.get("review_required_before_publication") is True
            )
        ]
        if not shot.asset_path or not approved:
            failures.append(f"{shot.id} lacks an ingested, provenance-recorded source excerpt")
            continue
        if shot.alignment_score is None or shot.alignment_score < minimum_alignment:
            failures.append(
                f"{shot.id} source-footage alignment is {shot.alignment_score if shot.alignment_score is not None else 'unscored'}; minimum {minimum_alignment:.0f}"
            )
            continue
        if policy.get("source_audio_must_be_muted") and not all(entry.get("muted", True) for entry in approved):
            failures.append(f"{shot.id} source audio is not recorded as muted")
            continue
        fingerprint = fingerprint_shot(shot)
        if fingerprint and fingerprints[fingerprint] > max_uses:
            failures.append(f"{shot.id} reuses source-footage asset {fingerprint}; limit {max_uses}")
            continue
        ready_seconds += shot.duration_seconds
    return {
        "passed": not failures,
        "planned_seconds": round(sum(shot.duration_seconds for shot in youtube_shots), 3),
        "ready_seconds": round(ready_seconds, 3),
        "shot_count": len(youtube_shots),
        "failures": list(dict.fromkeys(failures)),
    }


def review_visual_mix(
    project: EpisodeProject, *, require_assets: bool = True, policy: dict | None = None,
) -> dict:
    policy = policy or load_policy()
    total = sum(shot.duration_seconds for shot in project.shots)
    seconds = {name: 0.0 for name in CATEGORIES}
    failures: list[str] = []
    for shot in project.shots:
        category = classify_shot(project, shot)
        seconds[category] += shot.duration_seconds
        if category == "motion_graphics" and shot.fallback_reason not in policy["motion_allowed_reasons"]:
            failures.append(f"{shot.id} motion graphic has no allowed fallback/transition reason")
        if require_assets and category == "article_evidence" and not shot.asset_path:
            failures.append(f"{shot.id} article-evidence slot has no captured source asset")
    categories: dict[str, dict] = {}
    for name in CATEGORIES:
        actual = seconds[name] / total if total else 0.0
        target = float(policy["categories"][name]["target_share"])
        tolerance = float(policy["categories"][name]["tolerance"])
        categories[name] = {
            "seconds": round(seconds[name], 3), "share": round(actual, 4),
            "target_share": target, "tolerance": tolerance,
        }
        if abs(actual - target) > tolerance:
            failures.append(
                f"{name} is {actual:.1%} of runtime; target is {target:.0%} ± {tolerance:.0%}"
            )
    youtube = review_youtube_readiness(project, policy)
    if require_assets and not youtube["passed"]:
        failures.extend(youtube["failures"])
    return {
        "passed": not failures,
        "policy_id": policy["policy_id"],
        "duration_seconds": round(total, 3),
        "categories": categories,
        "youtube_readiness": youtube,
        "failures": list(dict.fromkeys(failures)),
    }


def review_timeline_ledger(records: list[dict], shot_seconds: float = 6.0) -> dict:
    """Audit legacy/custom render ledgers that predate EpisodeProject fields."""
    policy = load_policy()
    seconds = {name: 0.0 for name in CATEGORIES}
    for record in records:
        duration = float(record.get("duration_seconds") or shot_seconds)
        kind = str(record.get("kind") or "").casefold()
        source = str(record.get("source") or "")
        url = str(record.get("source_url") or "")
        if kind == "youtube_broll" or _is_youtube_url(url):
            category = "youtube_broll"
        elif kind in {"motion", "motion_graphics"}:
            category = "motion_graphics"
        elif Path(source).suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}:
            category = "article_evidence"
        else:
            category = "miscellaneous"
        seconds[category] += duration
    total = sum(seconds.values())
    categories = {}
    failures = []
    for name in CATEGORIES:
        share = seconds[name] / total if total else 0.0
        target = float(policy["categories"][name]["target_share"])
        tolerance = float(policy["categories"][name]["tolerance"])
        categories[name] = {"seconds": seconds[name], "share": round(share, 4), "target_share": target}
        if abs(share - target) > tolerance:
            failures.append(f"{name} is {share:.1%}; target is {target:.0%} ± {tolerance:.0%}")
    return {
        "passed": not failures, "policy_id": policy["policy_id"],
        "duration_seconds": total, "categories": categories, "failures": failures,
    }
