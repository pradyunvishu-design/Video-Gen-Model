"""Measure non-identifying delivery characteristics from reference narration audio."""
from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import asdict
from pathlib import Path

import numpy as np

from pipeline.captions import TimedWord, transcribe_words


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "reference_voice_analysis" / "ai_search_delivery_20260901"
FILES = [
    Path(r"C:\Users\kanag\Downloads\1a3a-2d64-4b5c-8cfc-8085f42c23de.mp3"),
    Path(r"C:\Users\kanag\Downloads\28e4-8210-4f9d-8788-ca1f22d5e6ae.mp3"),
]
SAMPLE_RATE = 16000


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=True)


def duration(path: Path) -> float:
    result = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ])
    return float(result.stdout.strip())


def loudness(path: Path) -> dict:
    process = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-filter_complex", "ebur128=peak=true", "-f", "null", "NUL",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    summary = process.stderr.rsplit("Summary:", 1)[-1]
    def number(pattern: str) -> float | None:
        match = re.search(pattern, summary)
        return float(match.group(1)) if match else None
    return {
        "integrated_lufs": number(r"I:\s+(-?\d+(?:\.\d+)?)\s+LUFS"),
        "loudness_range_lu": number(r"LRA:\s+(\d+(?:\.\d+)?)\s+LU"),
        "true_peak_dbfs": number(r"Peak:\s+(-?\d+(?:\.\d+)?)\s+dBFS"),
    }


def transcript(path: Path) -> list[TimedWord]:
    cache = OUTPUT / f"{path.stem}_words.json"
    if cache.is_file():
        return [TimedWord(**item) for item in json.loads(cache.read_text(encoding="utf-8"))]
    words = transcribe_words(path, model_size="small.en")
    cache.write_text(json.dumps([asdict(word) for word in words]), encoding="utf-8")
    return words


def speech_runs(words: list[TimedWord]) -> list[tuple[float, float]]:
    runs: list[tuple[float, float]] = []
    start = words[0].start
    end = words[0].end
    for word in words[1:]:
        if word.start - end <= 0.45 and word.end - start <= 14:
            end = word.end
            continue
        if end - start >= 5:
            runs.append((max(0, start - 0.1), end + 0.1))
        start, end = word.start, word.end
    if end - start >= 5:
        runs.append((max(0, start - 0.1), end + 0.1))
    return runs


def choose_runs(runs: list[tuple[float, float]], count: int = 12) -> list[tuple[float, float]]:
    if len(runs) <= count:
        return runs
    indexes = np.linspace(0, len(runs) - 1, count).round().astype(int)
    return [runs[int(index)] for index in indexes]


def pcm(path: Path, start: float, end: float) -> np.ndarray:
    process = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{end-start:.3f}",
            "-i", str(path), "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
            "-f", "s16le", "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    return np.frombuffer(process.stdout, dtype="<i2").astype(np.float32) / 32768.0


def pitch_and_dynamics(path: Path, runs: list[tuple[float, float]]) -> dict:
    f0_values: list[float] = []
    rms_values: list[float] = []
    frame_size = int(0.04 * SAMPLE_RATE)
    hop = int(0.02 * SAMPLE_RATE)
    fft_size = 2048
    minimum_lag = int(SAMPLE_RATE / 260)
    maximum_lag = int(SAMPLE_RATE / 75)
    window = np.hanning(frame_size).astype(np.float32)
    for start, end in runs:
        samples = pcm(path, start, end)
        for offset in range(0, max(0, len(samples) - frame_size), hop):
            frame = samples[offset:offset + frame_size]
            rms = float(np.sqrt(np.mean(frame * frame) + 1e-12))
            rms_dbfs = 20 * math.log10(max(rms, 1e-8))
            if rms_dbfs < -42:
                continue
            rms_values.append(rms_dbfs)
            centered = (frame - frame.mean()) * window
            spectrum = np.fft.rfft(centered, n=fft_size)
            autocorrelation = np.fft.irfft(spectrum * np.conj(spectrum), n=fft_size)
            if autocorrelation[0] <= 1e-8:
                continue
            normalized = autocorrelation / autocorrelation[0]
            region = normalized[minimum_lag:maximum_lag + 1]
            lag = minimum_lag + int(np.argmax(region))
            confidence = float(normalized[lag])
            if confidence < 0.42:
                continue
            if 1 <= lag < len(normalized) - 1:
                left, center, right = normalized[lag - 1:lag + 2]
                denominator = left - 2 * center + right
                if abs(denominator) > 1e-8:
                    lag += float(0.5 * (left - right) / denominator)
            f0 = SAMPLE_RATE / lag
            if 75 <= f0 <= 260:
                f0_values.append(float(f0))
    if not f0_values:
        return {"voiced_frames": 0}
    f0 = np.asarray(f0_values)
    rms = np.asarray(rms_values)
    p10, median, p90 = np.percentile(f0, [10, 50, 90])
    return {
        "sampled_speech_seconds": round(sum(end - start for start, end in runs), 2),
        "voiced_frames": len(f0_values),
        "pitch_hz_p10": round(float(p10), 2),
        "pitch_hz_median": round(float(median), 2),
        "pitch_hz_p90": round(float(p90), 2),
        "pitch_span_semitones_p10_p90": round(12 * math.log2(p90 / p10), 2),
        "speech_rms_dbfs_p10": round(float(np.percentile(rms, 10)), 2),
        "speech_rms_dbfs_median": round(float(np.median(rms)), 2),
        "speech_rms_dbfs_p90": round(float(np.percentile(rms, 90)), 2),
        "speech_dynamic_span_db": round(float(np.percentile(rms, 90) - np.percentile(rms, 10)), 2),
    }


def pause_and_rhythm(words: list[TimedWord], total_seconds: float) -> dict:
    gaps = [max(0.0, current.start - previous.end) for previous, current in zip(words, words[1:])]
    pauses = [gap for gap in gaps if gap >= 0.12]
    sentence_pauses = [
        gap for previous, gap in zip(words, gaps)
        if previous.text.rstrip().endswith((".", "?", "!")) and gap >= 0
    ]
    active_seconds = sum(max(0.0, word.end - word.start) for word in words) + sum(min(gap, 0.12) for gap in gaps)
    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", " ".join(word.text for word in words)) if segment.strip()]
    sentence_lengths = [len(re.findall(r"\b[\w'-]+\b", sentence)) for sentence in sentences]
    def percentile(values: list[float], value: float) -> float | None:
        return round(float(np.percentile(values, value)), 3) if values else None
    return {
        "recognized_words": len(words),
        "overall_words_per_minute": round(len(words) / max(total_seconds, 1) * 60, 2),
        "active_speech_words_per_minute": round(len(words) / max(active_seconds, 1) * 60, 2),
        "pause_count_over_120ms": len(pauses),
        "pauses_per_minute": round(len(pauses) / max(total_seconds, 1) * 60, 2),
        "pause_seconds_median": percentile(pauses, 50),
        "pause_seconds_p75": percentile(pauses, 75),
        "pause_seconds_p90": percentile(pauses, 90),
        "pause_seconds_p95": percentile(pauses, 95),
        "sentence_end_pause_median": percentile(sentence_pauses, 50),
        "sentence_end_pause_p75": percentile(sentence_pauses, 75),
        "sentence_words_median": percentile(sentence_lengths, 50),
        "sentence_words_p75": percentile(sentence_lengths, 75),
        "sentence_words_p90": percentile(sentence_lengths, 90),
    }


def aggregate(reports: list[dict]) -> dict:
    keys = [
        ("loudness", "integrated_lufs"), ("loudness", "loudness_range_lu"),
        ("loudness", "true_peak_dbfs"), ("delivery", "active_speech_words_per_minute"),
        ("delivery", "pause_seconds_median"), ("delivery", "pause_seconds_p90"),
        ("delivery", "sentence_end_pause_median"), ("delivery", "sentence_words_median"),
        ("acoustics", "pitch_hz_median"), ("acoustics", "pitch_span_semitones_p10_p90"),
        ("acoustics", "speech_dynamic_span_db"),
    ]
    result = {}
    for section, key in keys:
        values = [report[section].get(key) for report in reports if report[section].get(key) is not None]
        result[key] = round(float(np.mean(values)), 3) if values else None
    return result


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reports = []
    for path in FILES:
        if not path.is_file():
            raise FileNotFoundError(path)
        seconds = duration(path)
        words = transcript(path)
        selected_runs = choose_runs(speech_runs(words))
        report = {
            "file": str(path),
            "duration_seconds": round(seconds, 3),
            "loudness": loudness(path),
            "delivery": pause_and_rhythm(words, seconds),
            "acoustics": pitch_and_dynamics(path, selected_runs),
            "sampled_runs": [{"start": round(start, 3), "end": round(end, 3)} for start, end in selected_runs],
        }
        reports.append(report)
        (OUTPUT / f"{path.stem}_analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)
    combined = {
        "scope": "Non-identifying delivery analysis only; not a voiceprint or cloning profile.",
        "files": reports,
        "combined_targets": aggregate(reports),
    }
    (OUTPUT / "combined_delivery_profile.json").write_text(json.dumps(combined, indent=2), encoding="utf-8")
    print(json.dumps({"combined_targets": combined["combined_targets"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
