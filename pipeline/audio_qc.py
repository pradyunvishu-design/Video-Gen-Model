"""Master narration and reject garble, static, clipping, drift, or poor intelligibility."""
from __future__ import annotations

import difflib
import math
import re
import subprocess
from pathlib import Path

import numpy as np

from . import captions
from .config import LOCAL_FFMPEG_BIN


FFMPEG = str(LOCAL_FFMPEG_BIN / "ffmpeg.exe") if (LOCAL_FFMPEG_BIN / "ffmpeg.exe").is_file() else "ffmpeg"
AUDIO_MASTERING_VERSION = 2


def master_narration(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-af", (
            "adeclip,highpass=f=80,lowpass=f=14500,"
            "afftdn=nr=10:nf=-45:tn=1:tr=1:ad=0.35:rf=-55,"
            "agate=threshold=0.0035:ratio=2.2:range=0.08:attack=8:release=180,"
            "loudnorm=I=-16:TP=-1.5:LRA=8"
        ),
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(destination),
    ], check=True)
    return destination


def retime_narration(source: Path, destination: Path, *, target_duration_seconds: float) -> Path:
    """Apply one small, pitch-preserving runtime correction to an approved master.

    This is intentionally limited to a ten-percent tempo change. Larger misses
    need a script or performance revision rather than an audibly stretched
    narrator.
    """
    source_duration = technical_metrics(source)["duration_seconds"]
    if source_duration <= 0 or target_duration_seconds <= 0:
        raise ValueError("source and target narration durations must be positive")
    tempo = source_duration / target_duration_seconds
    if not 0.9 <= tempo <= 1.1:
        raise ValueError(f"runtime correction tempo {tempo:.4f} exceeds the 10% quality boundary")
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-af", f"atempo={tempo:.8f}",
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(destination),
    ], check=True)
    return destination


def _decode(path: Path, sample_rate: int = 24000) -> np.ndarray:
    process = subprocess.run([
        FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "pipe:1",
    ], capture_output=True, check=True)
    return np.frombuffer(process.stdout, dtype=np.float32)


def _words(text: str) -> list[str]:
    normalized = text.casefold()
    for joined, spoken in {
        "comfyui": "comfy ui",
        "openai": "open ai",
        "huggingface": "hugging face",
    }.items():
        normalized = normalized.replace(joined, spoken)
    # TTS receives deliberately spoken display values ("three sixty P"),
    # while ASR commonly returns their compact written forms ("360p").
    # Normalize those equivalent readings before judging garble.
    normalized = normalized.replace("%", " percent ")
    for pattern, replacement in (
        (r"\bthree\s+sixty\s+p\b", "360p"),
        (r"\bseven\s+twenty\s+p\b", "720p"),
        (r"\bten\s+eighty\s+p\b", "1080p"),
        (r"\bfour\s+k\b", "4k"),
        (r"\bsixty\s+percent\b", "60 percent"),
        (r"\bone\s+point\s+one(?:'s)?\b", "1 1"),
        (r"\b1\s*\.\s*1(?:'s|s)?\b", "1 1"),
    ):
        normalized = re.sub(pattern, replacement, normalized)
    return re.findall(r"[a-z0-9]+", normalized)


def intelligibility_score(expected: str, recognized: str) -> float:
    return difflib.SequenceMatcher(a=_words(expected), b=_words(recognized), autojunk=False).ratio()


def _largest_unmatched_run(expected: str, recognized: str) -> tuple[int, int]:
    matcher = difflib.SequenceMatcher(a=_words(expected), b=_words(recognized), autojunk=False)
    expected_run = recognized_run = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        expected_run = max(expected_run, i2 - i1)
        recognized_run = max(recognized_run, j2 - j1)
    return expected_run, recognized_run


def _longest_silence(frame_db: np.ndarray, seconds_per_frame: float, threshold: float = -46) -> float:
    longest = current = 0
    for silent in frame_db < threshold:
        current = current + 1 if silent else 0
        longest = max(longest, current)
    return longest * seconds_per_frame


def _spectrum_features(samples: np.ndarray, sample_rate: int) -> tuple[float, float, np.ndarray]:
    frame_size = 4096
    usable = len(samples) // frame_size * frame_size
    if not usable:
        return 0.0, 0.0, np.zeros(12, dtype=np.float64)
    frames = samples[:usable].reshape(-1, frame_size)
    rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
    active = frames[20 * np.log10(rms + 1e-12) > -42]
    if not len(active):
        active = frames
    active = active[:: max(1, len(active) // 80)]
    window = np.hanning(frame_size)
    power = np.abs(np.fft.rfft(active * window, axis=1)) ** 2 + 1e-12
    freqs = np.fft.rfftfreq(frame_size, 1 / sample_rate)
    useful = (freqs >= 100) & (freqs <= 11000)
    high = (freqs >= 7500) & (freqs <= 11000)
    high_ratio = float(np.mean(power[:, high].sum(axis=1) / power[:, useful].sum(axis=1)))
    flatness = float(np.mean(np.exp(np.mean(np.log(power[:, useful]), axis=1)) / np.mean(power[:, useful], axis=1)))
    edges = np.geomspace(100, 11000, 13)
    bands = []
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (freqs >= left) & (freqs < right)
        bands.append(np.log(np.median(power[:, mask].sum(axis=1)) + 1e-12))
    signature = np.asarray(bands, dtype=np.float64)
    signature -= signature.mean()
    signature /= np.linalg.norm(signature) + 1e-9
    return high_ratio, flatness, signature


def _voice_similarity(reference: np.ndarray, narration: np.ndarray, sample_rate: int) -> float:
    _, _, ref = _spectrum_features(reference, sample_rate)
    _, _, voice = _spectrum_features(narration, sample_rate)
    return float(np.clip(np.dot(ref, voice), -1, 1))


def _window_voice_metrics(reference: np.ndarray, narration: np.ndarray, sample_rate: int) -> dict[str, float]:
    """Measure narrator timbre repeatedly so averaging cannot hide a voice switch."""
    window = sample_rate * 3
    hop = sample_rate * 2
    starts = list(range(0, max(1, len(narration) - window + 1), hop))
    # Sixty evenly distributed windows provide full-episode coverage without
    # recomputing hundreds of nearly overlapping FFTs on long narration.
    if len(starts) > 60:
        starts = [starts[index] for index in np.linspace(0, len(starts) - 1, 60, dtype=int)]
    _, _, reference_signature = _spectrum_features(reference, sample_rate)
    similarities: list[float] = []
    for start in starts:
        chunk = narration[start:start + window]
        if len(chunk) < sample_rate or np.sqrt(np.mean(chunk * chunk) + 1e-12) < 0.004:
            continue
        _, _, chunk_signature = _spectrum_features(chunk, sample_rate)
        similarities.append(float(np.clip(np.dot(reference_signature, chunk_signature), -1, 1)))
    if not similarities:
        return {}
    values = np.asarray(similarities, dtype=np.float64)
    return {
        "voice_similarity_p10": float(np.percentile(values, 10)),
        "voice_similarity_min": float(np.min(values)),
        "voice_similarity_spread": float(np.max(values) - np.min(values)),
        "voice_windows_checked": float(len(values)),
    }


def technical_metrics(path: Path, reference_path: Path | None = None) -> dict[str, float]:
    sample_rate = 24000
    samples = _decode(path, sample_rate)
    if not len(samples):
        raise RuntimeError("narration decode produced no samples")
    frame_size = sample_rate // 2
    usable = len(samples) // frame_size * frame_size
    frames = samples[:usable].reshape(-1, frame_size) if usable else samples.reshape(1, -1)
    frame_rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
    frame_db = 20 * np.log10(frame_rms + 1e-12)
    high_ratio, flatness, _ = _spectrum_features(samples, sample_rate)
    audible_db = frame_db[(frame_db > -80) & (frame_db < -18)]
    background_noise_dbfs = float(np.percentile(audible_db, 20)) if len(audible_db) else -120.0
    low_level_noise_ratio = float(np.mean((frame_db > -65) & (frame_db < -38)))
    metrics = {
        "duration_seconds": len(samples) / sample_rate,
        "peak_dbfs": 20 * math.log10(float(np.max(np.abs(samples))) + 1e-12),
        "rms_dbfs": 20 * math.log10(float(np.sqrt(np.mean(samples * samples))) + 1e-12),
        "clipping_ratio": float(np.mean(np.abs(samples) >= 0.995)),
        "dc_offset": float(abs(np.mean(samples))),
        "silent_frame_ratio": float(np.mean(frame_db < -46)),
        "longest_silence_seconds": _longest_silence(frame_db, 0.5),
        "high_frequency_noise_ratio": high_ratio,
        "spectral_flatness": flatness,
        "background_noise_dbfs": background_noise_dbfs,
        "low_level_noise_ratio": low_level_noise_ratio,
    }
    if reference_path and reference_path.is_file():
        reference = _decode(reference_path, sample_rate)
        metrics["voice_similarity"] = _voice_similarity(reference, samples, sample_rate)
        metrics.update(_window_voice_metrics(reference, samples, sample_rate))
    return {key: round(value, 6) for key, value in metrics.items()}


def review_narration(
    path: Path,
    approved_script: str,
    reference_path: Path | None = None,
    *,
    recognized_text: str | None = None,
    enforce_pacing: bool = True,
    max_unmatched_words: int = 12,
    min_intelligibility: float = 0.9,
) -> dict:
    metrics = technical_metrics(path, reference_path)
    if recognized_text is None:
        recognized = captions.transcribe_words(path)
        recognized_text = " ".join(word.text for word in recognized)
    score = intelligibility_score(approved_script, recognized_text)
    unmatched_expected, unmatched_recognized = _largest_unmatched_run(approved_script, recognized_text)
    expected_words = set(_words(approved_script))
    nonspeech_markers = sorted({
        word for word in _words(recognized_text)
        if word in {"music", "applause", "laughing", "laughter", "inaudible"} and word not in expected_words
    })
    metrics["intelligibility"] = round(score, 6)
    metrics["english_script_match"] = round(score, 6)
    metrics["max_unmatched_expected_words"] = float(unmatched_expected)
    metrics["max_unmatched_recognized_words"] = float(unmatched_recognized)
    script_words = len(_words(approved_script))
    metrics["words_per_minute"] = round(script_words / max(metrics["duration_seconds"] / 60, 0.01), 2)

    failures: list[str] = []
    if score < min_intelligibility:
        failures.append(f"English/script match {score:.3f} is below {min_intelligibility:.3f}")
    if max(unmatched_expected, unmatched_recognized) > max_unmatched_words:
        failures.append("a continuous narration passage does not match the approved English script")
    if nonspeech_markers:
        failures.append("unexpected non-speech audio detected: " + ", ".join(nonspeech_markers))
    if metrics["clipping_ratio"] > 0.0005 or metrics["peak_dbfs"] > -0.45:
        failures.append("audio clips or has insufficient peak headroom")
    if metrics["high_frequency_noise_ratio"] > 0.22 and metrics["spectral_flatness"] > 0.08:
        failures.append("static-like high-frequency noise detected")
    if metrics["low_level_noise_ratio"] > 0.24 and metrics["spectral_flatness"] > 0.045:
        failures.append("persistent low-level background noise detected")
    if metrics["dc_offset"] > 0.015:
        failures.append("excessive DC offset detected")
    if metrics["longest_silence_seconds"] > 4.0:
        failures.append("unintended pause longer than four seconds")
    if enforce_pacing and not 90 <= metrics["words_per_minute"] <= 190:
        failures.append(f"delivery rate {metrics['words_per_minute']:.1f} WPM is outside 90-190")
    if "voice_similarity" in metrics and metrics["voice_similarity"] < 0.45:
        failures.append("narrator timbre drifted too far from the approved reference")
    if metrics.get("voice_similarity_p10", 1.0) < 0.35:
        failures.append("one or more narration sections appear to use a different speaker")
    if metrics.get("voice_similarity_spread", 0.0) > 0.55:
        failures.append("narrator timbre changes too much between sections")
    return {"passed": not failures, "failures": failures, "metrics": metrics}
