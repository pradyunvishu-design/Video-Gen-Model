"""Deterministic sentence-to-visual alignment and repetition QC."""
from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path
import re

from .models import EpisodeProject, Shot


STOPWORDS = {
    "all", "and", "are", "but", "can", "for", "had", "has", "how", "its",
    "not", "now", "one", "our", "out", "the", "too", "use", "was", "will",
    "you",
    "about", "after", "again", "against", "also", "among", "because", "been",
    "before", "being", "between", "both", "could", "does", "doing", "from",
    "have", "into", "just", "more", "most", "other", "over", "same", "should",
    "some", "than", "that", "their", "them", "then", "there", "these", "they",
    "this", "those", "through", "under", "very", "what", "when", "where", "which",
    "while", "with", "would", "your", "show", "visual", "footage", "video", "clip",
}

CONCEPTS = {
    "chip": {"chip", "semiconductor", "silicon", "wafer", "fab", "fabrication", "die"},
    "validation": {"validation", "validate", "testing", "test", "regression", "measurement", "signal"},
    "hardware": {"hardware", "equipment", "lab", "bench", "oscilloscope", "board", "sensor"},
    "code": {"code", "coding", "terminal", "developer", "repository", "software", "script"},
    "model": {"model", "claude", "anthropic", "llm", "agent", "reasoning"},
    "proof": {"proof", "evidence", "source", "report", "paper", "benchmark", "result"},
    "security": {
        "security", "cybersecurity", "cyber", "threat", "vulnerability",
        "vulnerabilities", "defense", "monitoring", "sandbox",
    },
    "people": {"human", "engineer", "review", "approval", "team", "interview", "keynote"},
    "workflow": {"workflow", "pipeline", "process", "loop", "sequence", "step", "rerun"},
}


def _tokens(value: str) -> set[str]:
    tokens = {
        token.strip(".+-")
        for token in re.findall(r"[a-z0-9][a-z0-9.+-]{2,}", value.casefold())
    }
    return {token for token in tokens if len(token) >= 3 and token not in STOPWORDS}


def alignment_terms(*values: str, limit: int = 24) -> list[str]:
    tokens = _tokens(" ".join(value for value in values if value))
    expanded = set(tokens)
    for family in CONCEPTS.values():
        if tokens.intersection(family):
            expanded.update(family)
    return sorted(expanded, key=lambda term: (-len(term), term))[:limit]


def score_alignment(target: str, candidate: str, *, source_hints: list[str] | None = None) -> dict:
    target_tokens = _tokens(target)
    candidate_tokens = _tokens(candidate)
    hints = _tokens(" ".join(source_hints or []))
    direct = target_tokens.intersection(candidate_tokens)
    concept_hits: set[str] = set()
    concept_total = 0
    for name, family in CONCEPTS.items():
        if target_tokens.intersection(family):
            concept_total += 1
            if candidate_tokens.intersection(family):
                concept_hits.add(name)
    direct_ratio = len(direct) / max(1, min(8, len(target_tokens)))
    concept_ratio = len(concept_hits) / max(1, concept_total)
    hint_ratio = len(hints.intersection(candidate_tokens)) / max(1, min(4, len(hints)))
    score = min(100.0, 55 * direct_ratio + 35 * concept_ratio + 10 * hint_ratio)
    return {
        "score": round(score, 2),
        "matched_terms": sorted(direct)[:16],
        "matched_concepts": sorted(concept_hits),
        "reason": f"matched {len(direct)} target terms and {len(concept_hits)}/{concept_total} visual concepts",
    }


def fingerprint_shot(shot: Shot) -> str:
    if shot.asset_fingerprint:
        return shot.asset_fingerprint
    if not shot.asset_path:
        return ""
    path = Path(shot.asset_path)
    identity = str(path.resolve()).casefold() if path.exists() else shot.asset_path.casefold()
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


def fingerprint_broll_source(shot: Shot, source_url: str = "") -> str:
    """Identify the source master, not the rendered six-second excerpt.

    Different files or timestamps from one YouTube/source video must share the
    same repetition budget.  `reuse_group` is preferred when ingestion records
    a canonical video ID; the evidence URL is the next strongest identity.
    """
    if shot.visual_category != "youtube_broll":
        return ""
    identity = (shot.reuse_group or source_url or shot.source_id or shot.asset_path).strip().casefold()
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20] if identity else ""


def review_project_clip_alignment(
    project: EpisodeProject, *, max_asset_uses: int = 2, cooldown_shots: int = 3,
) -> dict:
    """Review actual assignments after captures/licensed clips are attached."""
    if not project.script:
        return {"passed": False, "failures": ["script is missing"], "shots": []}
    beats = {beat.id: beat for beat in project.script.beats}
    sources = {source.id: source for source in project.sources}
    fingerprints = [fingerprint_shot(shot) for shot in project.shots]
    counts = Counter(value for value in fingerprints if value)
    source_fingerprints = [
        fingerprint_broll_source(shot, str(sources[shot.source_id].url) if shot.source_id in sources else "")
        for shot in project.shots
    ]
    source_counts = Counter(value for value in source_fingerprints if value)
    failures: list[str] = []
    records: list[dict] = []
    for index, shot in enumerate(project.shots):
        beat = beats.get(shot.beat_id)
        if not beat:
            failures.append(f"{shot.id} references missing beat {shot.beat_id}")
            continue
        if (
            shot.source_id and beat.source_ids and shot.source_id not in beat.source_ids
            and shot.visual_category not in {"youtube_broll", "miscellaneous"}
        ):
            failures.append(f"{shot.id} uses {shot.source_id}, which is not cited by {beat.id}")
        source = sources.get(shot.source_id or "")
        target = shot.semantic_target or f"{beat.narration} {beat.visual_direction}"
        candidate = " ".join(filter(None, [
            shot.prompt,
            source.title if source else "",
            source.publisher if source else "",
            shot.rights_note,
            shot.reuse_group,
        ]))
        result = score_alignment(target, candidate)
        shot.alignment_terms = alignment_terms(target)
        shot.alignment_score = result["score"]
        fingerprint = fingerprints[index]
        source_fingerprint = source_fingerprints[index]
        shot.asset_fingerprint = fingerprint
        if fingerprint and counts[fingerprint] > max_asset_uses:
            failures.append(f"asset {fingerprint} is used {counts[fingerprint]} times (limit {max_asset_uses})")
        if fingerprint and fingerprint in fingerprints[max(0, index - cooldown_shots):index]:
            failures.append(f"{shot.id} repeats an asset inside the {cooldown_shots}-shot cooldown")
        if source_fingerprint and source_counts[source_fingerprint] > max_asset_uses:
            failures.append(
                f"B-roll source {source_fingerprint} is used {source_counts[source_fingerprint]} times "
                f"(limit {max_asset_uses})"
            )
        if shot.asset_path and shot.source_id and result["score"] < 35:
            failures.append(f"{shot.id} visual alignment is only {result['score']:.0f}/100")
        records.append({
            "shot_id": shot.id, "beat_id": shot.beat_id, "source_id": shot.source_id,
            "asset_path": shot.asset_path, "fingerprint": fingerprint,
            "source_fingerprint": source_fingerprint, **result,
        })
    failures = list(dict.fromkeys(failures))
    scored = [item["score"] for item in records if item["asset_path"]]
    return {
        "passed": not failures,
        "minimum_score": min(scored) if scored else None,
        "median_score": sorted(scored)[len(scored) // 2] if scored else None,
        "max_asset_uses": max_asset_uses,
        "max_broll_source_uses": max_asset_uses,
        "cooldown_shots": cooldown_shots,
        "failures": failures,
        "shots": records,
    }
