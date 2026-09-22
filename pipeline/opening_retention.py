"""Evidence-led, topic-adaptive opening contracts and measured timeline gates.

The 5/12/30-second targets below are this channel's editorial hypotheses, not
universal retention thresholds or a trained prediction model. Role annotations
must be checked against the actual narration and frames by an independent review.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any


VERSION = "opening-retention-v1"
SOURCES = [
    "https://support.google.com/youtube/answer/9314415",
    "https://blog.youtube/creator-and-artist-stories/youtube-creator-playbook-tips-first-15/",
]
VISUAL_KINDS = {"official_output", "official_demo", "captured_test", "source_capture", "chart", "comparison"}


def _records(items: Any) -> dict[str, dict]:
    if isinstance(items, dict):
        return {str(key): value for key, value in items.items() if isinstance(value, dict)}
    return {str(item["id"]): item for item in (items or []) if isinstance(item, dict) and item.get("id")}


def build_opening_contract(
    episode_format: str, *, evidence: Any = None, product: str = "",
    product_spoken_aliases: list[str] | None = None,
    recent_openings: list[dict] | None = None,
) -> dict[str, Any]:
    """Route mechanisms by format and actual evidence; never invent a test."""
    assets = _records(evidence)
    visual_ids = [key for key, item in assets.items()
                  if item.get("available") is True and item.get("kind") in VISUAL_KINDS]
    if episode_format in {"weekly_roundup", "roundup"}:
        modes = ["roundup_burst", "relatable_friction", "context_reversal", "demonstration_first"]
        focus = "One prioritized consequence; preview only the strongest developments, then enter the top story."
    elif visual_ids:
        modes = ["demonstration_first", "relatable_friction", "context_reversal", "verdict_first"]
        focus = "Show the useful output or concrete difference before explaining the mechanism. Attribute official examples."
    else:
        modes = ["relatable_friction", "context_reversal", "verdict_first", "demonstration_first"]
        focus = "Start from one documented viewer problem. Acquire real visual proof before approving the opening."
    format_focus = {
        "tool_test": "Lead with one real captured task result, then identify what was tested and the practical limit. Official demos alone cannot substantiate our own test.",
        "product_test": "Lead with one real captured task result, then identify what was tested and the practical limit. Official demos alone cannot substantiate our own test.",
        "comparison": "Show the same task or clearly qualified source examples side by side; define the decision criterion and disclose unequal conditions.",
        "deep_dive": "Open with a concrete example that needs explaining, then promise the mechanism and one useful decision rather than a feature list.",
        "trend_explainer": "Anchor the trend in one visible consequence, explain the changed assumption, and distinguish demonstrated effects from predictions.",
        "news": "Name the concrete change and who it affects; establish what is confirmed before interpreting its significance.",
        "release_news": "Show the release's strongest documented change, translate the viewer benefit, and distinguish launch examples from independently verified performance.",
        "open_source_spotlight": "Show a useful official output or available workflow, then connect capability to actual access, practical constraints, and licensing limits.",
    }
    focus = format_focus.get(episode_format, focus)
    return {
        "version": VERSION, "episode_format": episode_format, "product": product,
        "product_spoken_aliases": list(product_spoken_aliases or []),
        "captured_test_required": episode_format in {"tool_test", "product_test"},
        "candidate_count": 4, "minimum_distinct_modes": 3,
        "preferred_modes": modes, "format_focus": focus, "available_visual_ids": visual_ids,
        "timing_basis": "Local production targets, to calibrate against real audience retention; not universal research findings.",
        "targets": {"first_proof_seconds": 5, "identity_benefit_seconds": 12,
                    "promise_limit_bridge_seconds": 30, "opening_min_seconds": 25,
                    "opening_max_seconds": 35, "timeline_tolerance_seconds": 0.08},
        "research_sources": SOURCES,
        "research_principles": ["Fulfill the title and thumbnail expectation immediately.",
                                "Put compelling material before branding and move strong moments earlier."],
        "generation_rules": [
            "Explore four genuinely different candidates across at least three mechanisms; do not fill a fixed sentence shell.",
            "Name the exact product or event and a concrete viewer benefit; make only one answerable promise.",
            "Give the edit a visible evidence ID, not a decoration or a future acquisition disguised as proof.",
            "Attribute official demos; never claim first-person testing without a captured test ledger.",
            "By 30 seconds include a relevant honest limitation and a causal bridge into the first example.",
            "No greeting, subscription request, standalone logo sequence, manufactured suspense, or unsupported superlative.",
            "Map the promise to a later payoff and supporting evidence. Review the final audio timing, not just word counts.",
            "Use title/thumbnail, viewer task, and available proof to choose the mechanism anew for each episode.",
        ],
        "recent_openings": list(recent_openings or [])[-8:],
        "measurement_status": "requires_actual_audio_and_visual_timeline",
    }


def _seconds(value: Any) -> float | None:
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if not isinstance(value, bool) and math.isfinite(number) and number >= 0 else None


def _name_tokens(value: str) -> list[str]:
    # Separate letters/digits so Qwen-Image2.1 and Qwen Image 2.1 match. Do not
    # infer spoken version numbers or fuzzy-match products; aliases are explicit.
    return re.findall(r"[^\W\d_]+|\d+", value.casefold())


def _mentions_product(text: str, names: list[str]) -> bool:
    spoken = _name_tokens(text)
    for name in names:
        tokens = _name_tokens(name)
        for offset in range(len(spoken) - len(tokens) + 1):
            end = offset + len(tokens)
            if tokens and spoken[offset:end] == tokens:
                # A shorter numeric version must not pass as a longer one.
                if tokens[-1].isdigit() and end < len(spoken) and spoken[end].isdigit():
                    continue
                return True
    return False


def evaluate_opening(
    beats: list[dict], *, contract: dict | None = None, evidence: Any = None,
    claims: Any = None, payoffs: list[dict] | None = None,
    asset_root: str | Path | None = None, require_local_assets: bool = False,
) -> dict[str, Any]:
    """Validate *actual* opening timing/provenance, without predicting engagement.

    Beats: id/start/end/text/roles, optional evidence_ids/claim_ids/promise_id.
    Role timing defaults to beat end (proof: start); role_times can give precise
    audio-aligned moments inside the beat. speech_end must not outlast the cut.
    Evidence: keyed records with available=True, source_url, kind, path and
    optional claim_ids. A captured_test additionally needs test_ledger_id.
    Payoffs: later id/promise_id/start/end/evidence_ids. Call with local-assets
    required at delivery; file existence verifies availability, NOT the depicted
    claim, visual quality, source ownership, or licensing.
    """
    contract = contract or build_opening_contract("deep_dive")
    targets = {**build_opening_contract("deep_dive")["targets"], **contract.get("targets", {})}
    assets, claim_map = _records(evidence), _records(claims)
    failures: list[str] = []
    warnings: list[str] = []
    times: dict[str, list[float]] = {}
    promises: set[str] = set()
    end_previous = 0.0
    seen: set[str] = set()
    text_parts: list[str] = []
    tolerance = float(targets["timeline_tolerance_seconds"])

    def usable(evidence_id: str) -> bool:
        item = assets.get(evidence_id, {})
        if item.get("available") is not True or not str(item.get("source_url", "")).startswith(("https://", "http://")):
            return False
        if require_local_assets:
            path = Path(item.get("path") or "")
            if not path.is_absolute():
                path = Path(asset_root or ".") / path
            if not item.get("path") or not path.is_file() or path.stat().st_size == 0:
                return False
        return True

    if not beats:
        failures.append("opening has no timed beats")
    for index, beat in enumerate(beats):
        key = str(beat.get("id", ""))
        start, end = _seconds(beat.get("start")), _seconds(beat.get("end"))
        if not key or key in seen:
            failures.append(f"beat {index}: missing or duplicate ID")
        seen.add(key)
        if start is None or end is None or end <= start:
            failures.append(f"{key}: invalid timing")
            continue
        if abs(start - end_previous) > tolerance:
            failures.append(f"{key}: gap or overlap at {start:g}s")
        end_previous = end
        speech_end = _seconds(beat.get("speech_end", end))
        if speech_end is None or speech_end > end + tolerance or speech_end < start:
            failures.append(f"{key}: speech is cut off or timing is invalid")
        text = str(beat.get("text", ""))
        text_parts.append(text)
        roles = beat.get("roles", [])
        if isinstance(roles, str):
            roles = [roles]
        if set(roles) & {"greeting", "cta", "logo_sequence"}:
            failures.append(f"{key}: greeting, CTA, or standalone branding delays the story")
        for evidence_id in beat.get("evidence_ids", []):
            if not usable(evidence_id):
                failures.append(f"{key}: evidence {evidence_id} is missing, unavailable, or lacks source provenance")
        refs = beat.get("evidence_ids", [])
        for claim_id in beat.get("claim_ids", []):
            if claim_id not in claim_map:
                failures.append(f"{key}: unknown claim {claim_id}")
            if refs and not any(claim_id in assets.get(ref, {}).get("claim_ids", []) for ref in refs):
                failures.append(f"{key}: claim {claim_id} has no linked visual evidence")
        if "proof" in roles and not any(usable(ref) and assets[ref].get("kind") in VISUAL_KINDS for ref in refs):
            failures.append(f"{key}: proof beat requires a usable source visual")
        if "proof" in roles and not beat.get("claim_ids"):
            failures.append(f"{key}: proof beat needs an evidence-backed claim ID")
        if "proof" in roles and contract.get("captured_test_required") and not any(
            usable(ref) and assets[ref].get("kind") == "captured_test"
            and assets[ref].get("test_ledger_id") for ref in refs
        ):
            failures.append(f"{key}: product-test opening requires a real captured test ledger, not only launch examples")
        first_person_test = beat.get("first_person_test") or re.search(
            r"\b(?:I|we)\s+(?:tested|tried|ran|generated|measured)\b", text, re.I)
        if first_person_test and not any(usable(ref) and assets[ref].get("kind") == "captured_test"
                                         and assets[ref].get("test_ledger_id") for ref in refs):
            failures.append(f"{key}: first-person test claim has no captured test ledger")
        for role in roles:
            at = _seconds(beat.get("role_times", {}).get(role, start if role == "proof" else end))
            if at is None or not start <= at <= end:
                failures.append(f"{key}: invalid {role} timing")
            else:
                times.setdefault(role, []).append(at)
        if "promise" in roles:
            if beat.get("promise_id"):
                promises.add(str(beat["promise_id"]))
            else:
                failures.append(f"{key}: promise is missing its payoff-mapping ID")

    for role, deadline in [("proof", targets["first_proof_seconds"]),
                           ("product", targets["identity_benefit_seconds"]),
                           ("benefit", targets["identity_benefit_seconds"]),
                           *[(r, targets["promise_limit_bridge_seconds"]) for r in ("promise", "limitation", "bridge")]]:
        if role not in times or min(times[role]) > deadline:
            failures.append(f"{role} must be established by {deadline:g}s")
    if not targets["opening_min_seconds"] <= end_previous <= targets["opening_max_seconds"]:
        failures.append("opening duration is outside its configured production band")
    if len(promises) != 1:
        failures.append("opening must make exactly one answerable promise")
    for promise in promises:
        candidates = [item for item in (payoffs or []) if item.get("promise_id") == promise]
        valid = False
        for item in candidates:
            start, end = _seconds(item.get("start")), _seconds(item.get("end"))
            valid |= bool(item.get("id") and start is not None and end is not None
                          and start >= end_previous and end > start
                          and item.get("evidence_ids") and all(usable(ref) for ref in item["evidence_ids"]))
        if not valid:
            failures.append(f"promise {promise} has no later evidence-linked payoff")
    spoken = " ".join(text_parts).lower()
    product = str(contract.get("product", "")).strip()
    names = [product, *contract.get("product_spoken_aliases", [])]
    if product and not _mentions_product(spoken, names):
        failures.append("the specified product is not named in the opening narration")
    tokens = re.findall(r"\w+", spoken)
    phrases = {tuple(tokens[i:i + 7]) for i in range(len(tokens) - 6)}
    for recent in contract.get("recent_openings", []):
        previous = re.findall(r"\w+", str(recent.get("opening", "")).lower())
        if phrases & {tuple(previous[i:i + 7]) for i in range(len(previous) - 6)}:
            warnings.append("A seven-word phrase repeats a recent opening; review novelty in context, not product names alone.")
            break
    return {
        "version": VERSION, "passed": not failures, "failures": list(dict.fromkeys(failures)),
        "warnings": warnings, "metrics": {
            "duration_seconds": round(end_previous, 3), "beat_count": len(beats),
            "first_proof_seconds": min(times.get("proof", []), default=None),
            "role_times": {key: min(value) for key, value in times.items()},
            "promise_count": len(promises), "local_assets_checked": require_local_assets,
        },
        "scope": "Timing and evidence-link validation only; independent semantic/frame/audio review and real retention analytics remain required.",
    }
