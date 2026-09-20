"""FFmpeg-based perceptual checks for final delivery and browser recordings."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


_NUMBER = r"(-?\d+(?:\.\d+)?)"


def _values(pattern: str, text: str) -> list[float]:
    return [float(value) for value in re.findall(pattern, text)]


def analyze_media(
    path: Path,
    *,
    duration_seconds: float,
    has_audio: bool = True,
    ffmpeg: Path | str = "ffmpeg",
) -> dict:
    """Detect black frames, frozen visuals, silence, and perceptual scene changes.

    The analysis branch is downscaled to keep a ten-minute review inexpensive.
    It never modifies the source file.
    """
    video_graph = (
        "[0:v]scale=320:-2:flags=fast_bilinear,split=2[vq][vs];"
        "[vq]blackdetect=d=0.75:pix_th=0.02,"
        "freezedetect=noise=-50dB:d=2[outv];"
        # Dark editorial cuts can replace structure without a large luminance
        # swing. A 0.003 threshold detects authored UI/source state changes;
        # nearby transition
        # frames are clustered below so a fade is counted once.
        "[vs]select='gt(scene,0.003)',showinfo,nullsink"
    )
    graph = video_graph
    command = [str(ffmpeg), "-hide_banner", "-nostats", "-i", str(path)]
    if has_audio:
        graph += ";[0:a]silencedetect=n=-50dB:d=2[outa]"
    command.extend(["-filter_complex", graph, "-map", "[outv]"])
    if has_audio:
        command.extend(["-map", "[outa]"])
    command.extend(["-f", "null", os.devnull])
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    log = (process.stderr or "") + "\n" + (process.stdout or "")
    if process.returncode:
        return {
            "passed": False,
            "analysis_error": log[-1200:],
            "black_durations": [],
            "freeze_durations": [],
            "silence_durations": [],
            "scene_change_seconds": [],
        }

    black_durations = _values(r"black_duration:" + _NUMBER, log)
    freeze_durations = _values(r"freeze_duration:\s*" + _NUMBER, log)
    silence_durations = _values(r"silence_duration:\s*" + _NUMBER, log) if has_audio else []
    raw_scene_times = sorted(set(_values(r"showinfo[^\n]*pts_time:" + _NUMBER, log)))
    scene_times: list[float] = []
    for timestamp in raw_scene_times:
        if not scene_times or timestamp - scene_times[-1] > 0.5:
            scene_times.append(timestamp)
    severe = []
    if black_durations and max(black_durations) > 2.0:
        severe.append(f"black frame lasts {max(black_durations):.2f}s")
    if freeze_durations and max(freeze_durations) > 12.0:
        severe.append(f"frozen visual lasts {max(freeze_durations):.2f}s")
    if silence_durations and max(silence_durations) > 4.0:
        severe.append(f"audio silence lasts {max(silence_durations):.2f}s")

    minimum_changes = max(1, int(duration_seconds / 15))
    warnings = []
    if len(scene_times) < minimum_changes:
        warnings.append(
            f"only {len(scene_times)} perceptual scene changes detected; expected at least {minimum_changes}"
        )
    return {
        "passed": not severe,
        "failures": severe,
        "warnings": warnings,
        "black_durations": [round(value, 3) for value in black_durations],
        "freeze_durations": [round(value, 3) for value in freeze_durations],
        "silence_durations": [round(value, 3) for value in silence_durations],
        "scene_change_seconds": [round(value, 3) for value in scene_times],
        "scene_change_count": len(scene_times),
    }
