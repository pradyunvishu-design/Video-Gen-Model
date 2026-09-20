"""Fail-closed lint and render metrics for the editorial visual training loop."""
from __future__ import annotations

import json
import hashlib
import re
import statistics
import subprocess
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from . import media_qc, visual_qc
from .visual_style_profile import (
    TRAINING_VISUAL_STYLE_PROFILE,
    composition_family,
    load_visual_style_profile,
    visual_style_profile_sha256,
)
from .art_direction import review_art_direction_plan


FACTUAL_INTENTS = {"consequence", "proof", "mechanism", "practical-consequence", "caveat", "decision"}


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _run_length(values: list[str]) -> int:
    longest = current = 0
    previous: str | None = None
    for value in values:
        current = current + 1 if value == previous else 1
        longest = max(longest, current)
        previous = value
    return longest


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _caption_metrics(
    captions: list[dict[str, Any]],
    *,
    approved_script: str,
    expected_duration: float,
    profile: dict[str, Any],
) -> dict[str, Any]:
    rules = profile.get("captions") or {}
    intervals = [(int(item.get("startMs", -1)), int(item.get("endMs", -1))) for item in captions]
    positive = bool(intervals) and all(start >= 0 and end > start for start, end in intervals)
    nonoverlapping = all(left[1] <= right[0] for left, right in zip(intervals, intervals[1:]))
    gaps = [max(0, right[0] - left[1]) for left, right in zip(intervals, intervals[1:])]
    reconstructed = _normalize_text("".join(str(item.get("text") or "") for item in captions))
    normalized_script = _normalize_text(approved_script)
    exact_script = bool(normalized_script) and reconstructed == normalized_script
    maximum_gap = int(rules.get("maximumGapMs", 1600))
    first_limit = int(rules.get("maximumFirstStartMs", 1600))
    trailing_limit = int(rules.get("maximumTrailingSilenceMs", 3000))
    first_start = intervals[0][0] if intervals else None
    last_end = intervals[-1][1] if intervals else None
    first_coverage = first_start is not None and first_start <= first_limit
    last_coverage = last_end is not None and last_end >= round(expected_duration * 1000) - trailing_limit
    largest_gap = max(gaps or [0])
    checks = {
        "present": bool(captions),
        "positive_intervals": positive,
        "nonoverlapping": nonoverlapping,
        "maximum_gap": largest_gap <= maximum_gap,
        "first_coverage": first_coverage,
        "last_coverage": last_coverage,
        "exact_script": exact_script,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "token_count": len(captions),
        "largest_gap_ms": largest_gap,
        "first_start_ms": first_start,
        "last_end_ms": last_end,
        "reconstructed_script": reconstructed,
    }


def _delivery_metrics(
    video: dict[str, Any],
    audio: dict[str, Any] | None,
    *,
    duration: float,
    expected_duration: float,
    profile: dict[str, Any],
) -> dict[str, Any]:
    delivery = profile.get("delivery") or {}
    expected_fps = float(delivery.get("fps", 30))
    raw_fps = str(video.get("r_frame_rate") or "0/1")
    try:
        actual_fps = float(Fraction(raw_fps))
    except (ValueError, ZeroDivisionError):
        actual_fps = 0.0
    decoded_frames = int(video.get("nb_read_frames") or 0)
    expected_frames = round(expected_duration * expected_fps)
    checks = {
        "duration": abs(duration - expected_duration) <= 0.001,
        "resolution": [video.get("width"), video.get("height")] == [delivery.get("width"), delivery.get("height")],
        "fps": abs(actual_fps - expected_fps) <= 0.001,
        "frame_count": decoded_frames == expected_frames,
        "video_codec": video.get("codec_name") == delivery.get("videoCodec"),
        "audio_present": audio is not None,
        "audio_codec": bool(audio) and audio.get("codec_name") == delivery.get("audioCodec"),
        "audio_channels": bool(audio) and int(audio.get("channels") or 0) == int(delivery.get("audioChannels", 2)),
        "audio_sample_rate": bool(audio) and int(audio.get("sample_rate") or 0) == int(delivery.get("audioSampleRate", 48000)),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "duration_seconds": duration,
        "expected_duration_seconds": expected_duration,
        "decoded_frames": decoded_frames,
        "expected_frames": expected_frames,
        "resolution": [video.get("width"), video.get("height")],
        "fps": raw_fps,
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_channels": audio.get("channels") if audio else None,
        "audio_sample_rate": audio.get("sample_rate") if audio else None,
    }


def lint_visual_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Check the learned profile before any expensive render begins."""
    version = str(spec.get("visualStyleProfileVersion") or "")
    if not version:
        return {"passed": True, "profile_version": None, "failures": [], "warnings": []}
    profile = load_visual_style_profile(version)
    embedded = spec.get("visualStyleProfile") or {}
    failures: list[str] = []
    warnings: list[str] = []
    integrity_required = version == TRAINING_VISUAL_STYLE_PROFILE or bool(
        (profile.get("integrity") or {}).get("failClosed")
    )
    if embedded != profile:
        failures.append("embedded visual style profile does not exactly match the canonical version")
    expected_profile_hash = visual_style_profile_sha256(profile)
    if integrity_required and spec.get("visualStyleProfileSha256") != expected_profile_hash:
        failures.append("embedded visual style profile hash is missing or invalid")
    locked_evidence = {str(item) for item in spec.get("lockedEvidenceIds") or [] if str(item)}
    if integrity_required and not locked_evidence:
        failures.append("locked evidence ledger IDs are missing")
    if bool((profile.get("integrity") or {}).get("evidenceLedgerRequired")):
        ledger = spec.get("lockedEvidenceLedger")
        ledger_hash = spec.get("lockedEvidenceLedgerSha256")
        if not isinstance(ledger, dict) or not ledger:
            failures.append("locked evidence ledger is missing")
        else:
            if set(map(str, ledger)) != locked_evidence:
                failures.append("locked evidence ledger entries do not exactly match lockedEvidenceIds")
            if ledger_hash != _canonical_sha256(ledger):
                failures.append("locked evidence ledger hash is missing or invalid")
            for evidence_id, record in ledger.items():
                if not isinstance(record, dict):
                    failures.append(f"{evidence_id}: evidence ledger record is malformed")
                    continue
                path = Path(str(record.get("assetPath") or ""))
                expected_hash = str(record.get("assetSha256") or "")
                if not str(record.get("sourceUrl") or "").startswith(("http://", "https://", "local://")):
                    failures.append(f"{evidence_id}: evidence ledger source URL is missing")
                if not path.is_file():
                    failures.append(f"{evidence_id}: locked evidence asset is missing")
                elif re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
                    failures.append(f"{evidence_id}: locked evidence asset hash is malformed")
                elif hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                    failures.append(f"{evidence_id}: locked evidence asset hash does not match")
    scenes = list(spec.get("scenes") or [])
    typography = profile["typography"]
    dominance = profile["dominance"]
    forbidden_furniture = set(profile.get("forbiddenFurniture") or [])
    furniture_counts: Counter[str] = Counter()
    rendered_body_sizes: list[float] = []
    rendered_label_sizes: list[float] = []
    render_scale = float(profile["canvas"].get("renderScale", 1.0))
    for index, scene in enumerate(scenes):
        label = str(scene.get("id") or f"scene[{index}]")
        intent = str(scene.get("semanticIntent") or "")
        kind = str(scene.get("kind") or "")
        evidence_ids = [str(item).strip() for item in scene.get("evidenceIds") or [] if str(item).strip()]
        if intent not in set(profile["routing"]):
            failures.append(f"{label}: semanticIntent is missing or unsupported")
        elif str(scene.get("motionPattern") or "") not in set(profile["routing"][intent]):
            failures.append(f"{label}: motion pattern is not routed from semanticIntent {intent}")
        if intent in FACTUAL_INTENTS and not evidence_ids:
            failures.append(f"{label}: factual beat has no locked evidence ID")
        unknown_evidence = sorted(set(evidence_ids) - locked_evidence) if locked_evidence else []
        if integrity_required and unknown_evidence:
            failures.append(f"{label}: evidence IDs are not in the locked ledger: {', '.join(unknown_evidence)}")
        expected_composition = composition_family(str(scene.get("motionPattern") or kind))
        if scene.get("compositionFamily") != expected_composition:
            failures.append(f"{label}: compositionFamily does not match its motion pattern")
        if float(scene.get("proofDominance", 0)) < float(dominance.get(kind, 0.8)):
            failures.append(f"{label}: dominant proof object is below the {kind} hierarchy floor")
        body_px = float(scene.get("bodyTextPx", 0))
        label_px = float(scene.get("labelTextPx", 0))
        rendered_body_px = (body_px / render_scale) * render_scale if render_scale > 0 else 0
        rendered_label_px = (label_px / render_scale) * render_scale if render_scale > 0 else 0
        rendered_body_sizes.append(rendered_body_px)
        rendered_label_sizes.append(rendered_label_px)
        if rendered_body_px < float(typography["minimumBodyPx"]):
            failures.append(f"{label}: body text is below the 1080p minimum")
        if rendered_label_px < float(typography["minimumLabelPx"]):
            failures.append(f"{label}: label text is below the 1080p minimum")
        duration = float(scene.get("durationSeconds", 0))
        states = list(scene.get("visualStates") or [])
        if duration >= 4 and len(states) < 2:
            failures.append(f"{label}: four-to-six-second scene requires at least two meaningful states")
        state_seconds = float(scene.get("meaningfulStateChangeSeconds", 0))
        if duration >= 4 and not (
            float(profile["timing"]["meaningfulStateChangeMinSeconds"])
            <= state_seconds
            <= float(profile["timing"]["meaningfulStateChangeMaxSeconds"])
        ):
            failures.append(f"{label}: planned state-change cadence is outside the two-to-three-second target")
        focus = scene.get("sourceFocus")
        purpose = str(scene.get("annotationPurpose") or "").strip()
        if bool(focus) != bool(purpose):
            failures.append(f"{label}: annotation geometry and semantic purpose must appear together")
        transition = str(scene.get("transitionAfter") or "hard-cut")
        reason = str(scene.get("transitionReason") or "").strip()
        if index < len(scenes) - 1 and not reason:
            failures.append(f"{label}: transition has no semantic reason")
        if transition == "handoff" and "handoff" not in reason.lower():
            failures.append(f"{label}: directional transition is not tied to a real handoff")
        for furniture in scene.get("furnitureIds") or []:
            furniture_counts[str(furniture)] += 1
            if furniture in forbidden_furniture:
                failures.append(f"{label}: forbidden repeated furniture {furniture}")
    patterns = [str(scene.get("motionPattern") or "") for scene in scenes]
    compositions = [str(scene.get("compositionFamily") or "") for scene in scenes]
    anchors = [str(scene.get("anchor") or "") for scene in scenes]
    transitions = [str(scene.get("transitionAfter") or "hard-cut") for scene in scenes[:-1]]
    repetition = profile["repetition"]
    if _run_length(patterns) > int(repetition["maxAdjacentSamePattern"]):
        failures.append("adjacent scenes repeat the same motion pattern")
    if _run_length(compositions) > int(repetition["maxAdjacentSameComposition"]):
        failures.append("composition family repeats too long without a proof/mechanism reset")
    if _run_length(anchors) > int(repetition["maxAnchorRun"]):
        failures.append("anchor repeats too long")
    if _run_length(transitions) > int(repetition["maxTransitionRun"]):
        warnings.append("transition type repeats across more than three boundaries")
    if patterns:
        max_share = max(Counter(patterns).values()) / len(patterns)
        if max_share > float(repetition["maxPatternTimelineShare"]):
            failures.append("one motion pattern occupies too much of the full timeline")
    repeated_furniture = [name for name, count in furniture_counts.items() if count > max(1, len(scenes) // 2)]
    if repeated_furniture and not profile["canvas"]["allowRepeatedFrameFurniture"]:
        failures.append("repeated frame furniture dominates the timeline: " + ", ".join(sorted(repeated_furniture)))
    source_count = sum(1 for scene in scenes if scene.get("kind") == "source")
    if scenes and source_count / len(scenes) < 0.25:
        warnings.append("fewer than one quarter of scenes use primary source proof")
    art_review = review_art_direction_plan(scenes, profile)
    failures.extend(art_review["failures"])
    warnings.extend(art_review["warnings"])
    return {
        "passed": not failures,
        "profile_version": version,
        "failures": failures,
        "warnings": warnings,
        "art_direction": art_review,
        "metrics": {
            "scene_count": len(scenes),
            "source_scene_count": source_count,
            "pattern_diversity": len(set(patterns)),
            "composition_diversity": len(set(compositions)),
            "transition_diversity": len(set(transitions)),
            "profile_sha256": expected_profile_hash,
            "render_scale": render_scale,
            "minimum_rendered_body_px": min(rendered_body_sizes, default=None),
            "minimum_rendered_label_px": min(rendered_label_sizes, default=None),
        },
    }


def _probe(path: Path, ffprobe: Path | str) -> dict[str, Any]:
    process = subprocess.run(
        [str(ffprobe), "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(process.stdout)


def _loudness(path: Path, ffmpeg: Path | str) -> dict[str, Any]:
    process = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-i", str(path), "-filter_complex", "ebur128=peak=true", "-f", "null", "NUL"],
        capture_output=True, text=True,
    )
    output = process.stdout + "\n" + process.stderr
    integrated = [float(value) for value in re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", output)]
    peaks = [float(value) for value in re.findall(r"Peak:\s+(-?\d+(?:\.\d+)?) dBFS", output)]
    value = integrated[-1] if integrated else None
    peak = peaks[-1] if peaks else None
    return {
        "passed": value is not None and peak is not None and -16.8 <= value <= -15.2 and peak <= -1.5,
        "integrated_lufs": value,
        "true_peak_dbfs": peak,
    }


def post_render_metrics(
    path: Path,
    spec: dict[str, Any],
    *,
    ffmpeg: Path | str = "ffmpeg",
    ffprobe: Path | str = "ffprobe",
    expected_duration: float | None = None,
) -> dict[str, Any]:
    """Measure the rendered artifact in the same dimensions used to train the profile."""
    probe = _probe(path, ffprobe)
    video = next(stream for stream in probe["streams"] if stream.get("codec_type") == "video")
    audio = next((stream for stream in probe["streams"] if stream.get("codec_type") == "audio"), None)
    duration = float(probe["format"]["duration"])
    expected = expected_duration if expected_duration is not None else duration
    decode = subprocess.run(
        [str(ffmpeg), "-v", "error", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "NUL"],
        capture_output=True, text=True,
    )
    perceptual = media_qc.analyze_media(
        path, duration_seconds=duration, has_audio=audio is not None, ffmpeg=ffmpeg,
    )
    occupancy = visual_qc.inspect_black_space_occupancy(path, ffmpeg=ffmpeg)
    structure = visual_qc.inspect_dark_editorial_structure(path, ffmpeg=ffmpeg)
    changes = [0.0, *perceptual.get("scene_change_seconds", []), duration]
    gaps = [right - left for left, right in zip(changes, changes[1:]) if right > left]
    state_change = {
        "passed": bool(gaps) and max(gaps) <= 3.5,
        "count": int(perceptual.get("scene_change_count", 0)),
        "mean_gap_seconds": round(statistics.fmean(gaps), 3) if gaps else None,
        "largest_gap_seconds": round(max(gaps), 3) if gaps else None,
        "target_seconds": [2.0, 3.0],
    }
    patterns = [str(scene.get("motionPattern") or scene.get("kind")) for scene in spec.get("scenes") or []]
    kinds = [str(scene.get("kind")) for scene in spec.get("scenes") or []]
    diversity = {
        "passed": len(set(patterns)) >= min(5, len(patterns)) and len(set(kinds)) >= min(4, len(kinds)),
        "shot_count": len(patterns),
        "pattern_count": len(set(patterns)),
        "scene_family_count": len(set(kinds)),
        "patterns": patterns,
    }
    profile = load_visual_style_profile(str(spec.get("visualStyleProfileVersion") or TRAINING_VISUAL_STYLE_PROFILE))
    captions = _caption_metrics(
        list(spec.get("captions") or []),
        approved_script=str(spec.get("approvedScript") or ""),
        expected_duration=expected,
        profile=profile,
    )
    exact = _delivery_metrics(video, audio, duration=duration, expected_duration=expected, profile=profile)
    loudness = _loudness(path, ffmpeg)
    checks = {
        "exact_delivery": exact["passed"],
        "full_decode": decode.returncode == 0,
        "loudness": loudness["passed"],
        "captions": captions["passed"],
        "state_change_cadence": state_change["passed"],
        "perceptual_qc": perceptual["passed"],
        "near_black_coverage": occupancy["passed"],
        "dark_structure": structure["passed"],
        "shot_pattern_diversity": diversity["passed"],
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "exact_delivery": exact,
        "full_decode": {"passed": decode.returncode == 0, "stderr": decode.stderr[-1200:]},
        "loudness": loudness,
        "captions": captions,
        "state_change_cadence": state_change,
        "perceptual_qc": perceptual,
        "near_black_coverage": occupancy,
        "dark_structure": structure,
        "shot_pattern_diversity": diversity,
    }
