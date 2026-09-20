"""Automated technical, editorial, pacing, and rights quality gates."""
from __future__ import annotations

import json
import statistics
import subprocess
from pathlib import Path

from .config import (
    MAX_EPISODE_SECONDS, MIN_EPISODE_SECONDS, NARRATION_TAIL_PADDING_SECONDS,
    RUNTIME_BOUNDARY_TOLERANCE_SECONDS,
    VIDEO_H, VIDEO_W,
)
from .models import EpisodeProject
from .media_qc import analyze_media
from .storyboard import shot_limit
from .visual_mix import review_visual_mix


def probe(path: Path) -> dict:
    process = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(process.stdout)


def run_qc(project: EpisodeProject, video_path: Path) -> dict:
    failures, warnings = [], []
    details = probe(video_path)
    duration = float(details["format"].get("duration", 0))
    video_stream = next((stream for stream in details["streams"] if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in details["streams"] if stream.get("codec_type") == "audio"), None)
    target_minutes = float(project.episode.get("target_minutes", 10))
    private_canary = bool(project.episode.get("private_canary"))
    short_news_special = bool(project.episode.get("short_news_special"))
    runtime_tolerance = 0.05 if private_canary or short_news_special else RUNTIME_BOUNDARY_TOLERANCE_SECONDS
    if private_canary:
        minimum_seconds = maximum_seconds = target_minutes * 60
        minimum_words = int(project.episode.get("script_word_min", 65))
        maximum_words = int(project.episode.get("script_word_max", 80))
        minimum_shots, maximum_shots = 5, 7
    elif short_news_special:
        minimum_seconds = maximum_seconds = target_minutes * 60
        minimum_words = int(project.episode.get("script_word_min", 285))
        maximum_words = int(project.episode.get("script_word_max", 325))
        minimum_shots = int(project.episode.get("shot_min", 20))
        maximum_shots = int(project.episode.get("shot_max", 30))
    elif target_minutes <= 6:
        minimum_seconds, maximum_seconds = (target_minutes - 0.5) * 60, (target_minutes + 0.5) * 60
        minimum_words = int(project.episode.get("script_word_min", 600))
        maximum_words = int(project.episode.get("script_word_max", 840))
        minimum_shots, maximum_shots = 45, 70
    else:
        minimum_seconds, maximum_seconds = MIN_EPISODE_SECONDS, MAX_EPISODE_SECONDS
        minimum_words, maximum_words = 1250, 1800
        minimum_shots, maximum_shots = 70, 110
    spoken_runtime = max(0.0, duration - NARRATION_TAIL_PADDING_SECONDS)
    if not (
        minimum_seconds - runtime_tolerance
        <= spoken_runtime
        <= maximum_seconds + runtime_tolerance
    ):
        failures.append(f"spoken runtime {spoken_runtime:.2f}s is outside {minimum_seconds:.0f}-{maximum_seconds:.0f}s")
    if not video_stream or video_stream.get("width") != VIDEO_W or video_stream.get("height") != VIDEO_H:
        failures.append("video is not 1920x1080")
    if video_stream and video_stream.get("codec_name") != "h264":
        failures.append(f"video codec is {video_stream.get('codec_name')}, expected h264")
    if video_stream:
        raw_rate = str(video_stream.get("avg_frame_rate", "0/1"))
        try:
            numerator, denominator = raw_rate.split("/", 1)
            fps = float(numerator) / max(1.0, float(denominator))
        except (ValueError, ZeroDivisionError):
            fps = 0.0
        if not 29.5 <= fps <= 30.5:
            failures.append(f"video frame rate {fps:.2f} is not 30 fps")
        if int(video_stream.get("bit_rate") or details["format"].get("bit_rate") or 0) < 650_000:
            failures.append("video bitrate is too low for a 1080p review master")
    if not audio_stream:
        failures.append("video has no audio stream")
    narration_seconds = float(project.narration.get("duration_seconds") or 0)
    audio_duration = float(audio_stream.get("duration") or duration) if audio_stream else 0.0
    if narration_seconds and audio_duration + 0.05 < narration_seconds:
        failures.append(
            f"final audio ends at {audio_duration:.2f}s before narration completes at {narration_seconds:.2f}s"
        )
    if narration_seconds and duration + 0.05 < narration_seconds + NARRATION_TAIL_PADDING_SECONDS:
        failures.append("final delivery has no protected hold after the last spoken word")
    perceptual = analyze_media(video_path, duration_seconds=duration, has_audio=bool(audio_stream))
    if not perceptual.get("passed"):
        failures.extend(f"perceptual QC: {failure}" for failure in perceptual.get("failures", []))
        if perceptual.get("analysis_error"):
            failures.append("perceptual media analysis failed")
    warnings.extend(f"perceptual QC: {warning}" for warning in perceptual.get("warnings", []))
    if not project.script:
        failures.append("approved script is missing")
    elif not minimum_words <= project.script.word_count <= maximum_words:
        failures.append(f"script word count is {project.script.word_count}")
    durations = [shot.duration_seconds for shot in project.shots]
    if not minimum_shots <= len(durations) <= maximum_shots:
        failures.append(f"shot count is {len(durations)}")
    if durations and statistics.median(durations) > 6:
        failures.append("median visual duration exceeds six seconds")
    if any(shot.duration_seconds > shot_limit(shot.asset_type) for shot in project.shots):
        failures.append("one or more visual durations exceed their limit")
    missing_rights = [shot.id for shot in project.shots if shot.source_id and not shot.rights_note]
    if missing_rights:
        failures.append(f"shots missing rights notes: {missing_rights[:10]}")
    used_paths = {shot.asset_path for shot in project.shots if shot.asset_path}
    failed_media = [
        asset.id for asset in project.media
        if asset.qc_status == "failed" and asset.path in used_paths
    ]
    if failed_media:
        failures.append(f"media QC failed: {failed_media}")
    forbidden_stills = [
        shot.id for shot in project.shots if shot.asset_type == "generated_image"
    ] + [
        asset.id for asset in project.media
        if asset.kind in {"generated_image", "thumbnail_background"} and asset.path in used_paths
    ]
    if forbidden_stills:
        failures.append(f"standalone AI-generated stills are present: {forbidden_stills[:10]}")
    motion_without_pass = []
    for shot in project.shots:
        if shot.asset_type not in {"generated_video", "concept_animation"} or not shot.asset_path:
            continue
        asset = next((item for item in project.media if item.path == shot.asset_path), None)
        if not asset or asset.kind != "generated_motion_graphic" or asset.qc_status != "passed":
            motion_without_pass.append(shot.id)
    if motion_without_pass:
        failures.append(f"Magic Hour motion clips lack motion-specific QC approval: {motion_without_pass[:10]}")
    captions_required = bool(project.episode.get("captions_enabled", True))
    if captions_required and not project.artifacts.get("captions"):
        failures.append("caption artifact is missing")
    if not project.artifacts.get("thumbnails"):
        failures.append("thumbnail artifacts are missing")
    if not project.qc.get("thumbnails", {}).get("passed"):
        failures.append("thumbnail readability QC did not pass")
    if not project.rights:
        warnings.append("rights ledger is empty")
    capture_issues = []
    accepted_capture_count = 0
    for record in project.captures:
        for artifact in record.artifacts:
            if artifact.kind != "screen_recording":
                continue
            status = artifact.quality.get("status")
            if status in {"accepted", "cached"}:
                accepted_capture_count += 1
            else:
                capture_issues.append(artifact.path)
    if capture_issues:
        failures.append(f"screen recordings lack accepted capture QC: {capture_issues[:6]}")
    visual_mix = None
    if project.episode.get("visual_mix_policy"):
        visual_mix = review_visual_mix(project, require_assets=True)
        if not visual_mix["passed"]:
            failures.extend(f"visual mix: {failure}" for failure in visual_mix["failures"])
    return {
        "passed": not failures, "failures": failures, "warnings": warnings,
        "duration_seconds": duration, "video_codec": video_stream.get("codec_name") if video_stream else None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "audio_duration_seconds": round(audio_duration, 3),
        "narration_duration_seconds": round(narration_seconds, 3),
        "protected_voice_tail_seconds": NARRATION_TAIL_PADDING_SECONDS,
        "resolution": [video_stream.get("width"), video_stream.get("height")] if video_stream else None,
        "shot_count": len(durations), "median_shot_seconds": statistics.median(durations) if durations else 0,
        "capture_review": {
            "accepted_recordings": accepted_capture_count,
            "unreviewed_recordings": capture_issues,
        },
        "perceptual_media": perceptual,
        "visual_mix": visual_mix,
    }


def review_readiness(project: EpisodeProject) -> dict:
    """One auditable approval summary instead of scattered QC booleans."""
    fact_check = project.qc.get("fact_check", {})
    checks = {
        "facts": bool(fact_check.get("passed")),
        "script_voice": bool(fact_check.get("quality_review", {}).get("passed") or fact_check.get("manual_approval")),
        "narration": bool(project.qc.get("audio_listenability", {}).get("passed")),
        "captions": (
            not bool(project.episode.get("captions_enabled", True))
            or bool(project.artifacts.get("captions"))
        ),
        "thumbnails": bool(project.qc.get("thumbnails", {}).get("passed")),
        "source_rights_ledger": bool(project.rights),
        "final_delivery": bool(project.qc.get("final", {}).get("passed")),
        "visual_mix": bool(
            not project.episode.get("visual_mix_policy")
            or project.qc.get("visual_mix", {}).get("passed")
            or project.qc.get("final", {}).get("visual_mix", {}).get("passed")
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    warnings: list[str] = []
    voice_rights = project.episode.get("voice_rights", {})
    if voice_rights.get("documentation_pending"):
        warnings.append("voice documentation is still pending; public publishing must remain disabled")
    if project.qc.get("final", {}).get("capture_review", {}).get("accepted_recordings", 0) == 0:
        warnings.append("no reviewed screen recordings were used; confirm source visuals are sufficient")
    return {
        "passed": not failed,
        "checks": checks,
        "failed_checks": failed,
        "warnings": warnings,
        "reviewer_action": "approve draft" if not failed else "revise only the failed stages",
    }
