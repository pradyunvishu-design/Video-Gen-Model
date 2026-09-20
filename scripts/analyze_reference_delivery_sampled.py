"""Fast, non-identifying delivery analysis for long reference narration.

This samples evenly across each source episode, preserving enough continuous
speech to measure cadence, pauses, pitch span, and dynamics without building a
voiceprint or transcribing an entire copyrighted episode.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "reference_voice_analysis" / "ai_search_delivery_20260901"
FILES = [
    Path(r"C:\Users\kanag\Downloads\1a3a-2d64-4b5c-8cfc-8085f42c23de.mp3"),
    Path(r"C:\Users\kanag\Downloads\28e4-8210-4f9d-8788-ca1f22d5e6ae.mp3"),
]
SAMPLE_RATE = 16_000
WINDOW_SECONDS = 45.0
WINDOW_FRACTIONS = (0.03, 0.18, 0.36, 0.55, 0.73, 0.90)


def command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=True)


def media_duration(path: Path) -> float:
    result = command([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ])
    return float(result.stdout.strip())


def full_mix_loudness(path: Path) -> dict[str, float | None]:
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-filter_complex", "ebur128=peak=true", "-f", "null", "NUL",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    summary = result.stderr.rsplit("Summary:", 1)[-1]

    def value(pattern: str) -> float | None:
        match = re.search(pattern, summary)
        return float(match.group(1)) if match else None

    return {
        "integrated_lufs": value(r"I:\s+(-?\d+(?:\.\d+)?)\s+LUFS"),
        "loudness_range_lu": value(r"LRA:\s+(\d+(?:\.\d+)?)\s+LU"),
        "true_peak_dbfs": value(r"Peak:\s+(-?\d+(?:\.\d+)?)\s+dBFS"),
    }


def extract_windows(path: Path, duration: float) -> list[Path]:
    sample_dir = OUTPUT / "samples" / path.stem
    sample_dir.mkdir(parents=True, exist_ok=True)
    windows: list[Path] = []
    for index, fraction in enumerate(WINDOW_FRACTIONS):
        start = min(max(0.0, duration * fraction), max(0.0, duration - WINDOW_SECONDS))
        target = sample_dir / f"sample_{index + 1:02d}_{start:.1f}.wav"
        if not target.is_file():
            command([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{start:.3f}", "-i", str(path), "-t", str(WINDOW_SECONDS),
                "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le",
                str(target),
            ])
        windows.append(target)
    return windows


def read_pcm(path: Path) -> np.ndarray:
    # The extracted samples are mono 16 kHz PCM WAV files. Read the RIFF data
    # chunk directly so no optional audio dependency is required.
    with path.open("rb") as handle:
        data = handle.read()
    marker = data.find(b"data")
    if marker < 0:
        raise ValueError(f"No WAV data chunk in {path}")
    size = int.from_bytes(data[marker + 4:marker + 8], "little")
    pcm = np.frombuffer(data[marker + 8:marker + 8 + size], dtype="<i2")
    return pcm.astype(np.float32) / 32768.0


def percentile(values: list[float], q: float) -> float | None:
    return round(float(np.percentile(values, q)), 3) if values else None


def estimate_pitch(samples: np.ndarray) -> list[float]:
    pitches: list[float] = []
    frame = int(0.04 * SAMPLE_RATE)
    hop = int(0.02 * SAMPLE_RATE)
    min_lag = int(SAMPLE_RATE / 260)
    max_lag = int(SAMPLE_RATE / 75)
    for offset in range(0, max(0, len(samples) - frame), hop):
        chunk = samples[offset:offset + frame]
        rms = float(np.sqrt(np.mean(chunk * chunk) + 1e-12))
        if rms < 0.012:
            continue
        chunk = chunk - np.mean(chunk)
        corr = np.correlate(chunk, chunk, mode="full")[frame - 1:]
        if corr[0] <= 0:
            continue
        search = corr[min_lag:max_lag]
        lag = min_lag + int(np.argmax(search))
        confidence = float(corr[lag] / corr[0])
        if confidence >= 0.34:
            pitches.append(SAMPLE_RATE / lag)
    return pitches


def frame_rms(samples: np.ndarray) -> list[float]:
    frame = int(0.05 * SAMPLE_RATE)
    values: list[float] = []
    for offset in range(0, max(0, len(samples) - frame), frame):
        rms = float(np.sqrt(np.mean(samples[offset:offset + frame] ** 2) + 1e-12))
        if rms >= 0.008:
            values.append(20 * math.log10(rms))
    return values


def transcribe_samples(model: WhisperModel, windows: list[Path]) -> tuple[list[dict], list[dict]]:
    words: list[dict] = []
    segments_out: list[dict] = []
    offset = 0.0
    for sample_index, window in enumerate(windows):
        segments, _ = model.transcribe(
            str(window),
            language="en",
            beam_size=3,
            vad_filter=True,
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        for segment in segments:
            segments_out.append({
                "sample": sample_index + 1,
                "start": round(offset + segment.start, 3),
                "end": round(offset + segment.end, 3),
                "text": segment.text.strip(),
            })
            for word in segment.words or []:
                token = word.word.strip()
                if token:
                    words.append({
                        "sample": sample_index + 1,
                        "start": offset + word.start,
                        "end": offset + word.end,
                        "text": token,
                    })
        offset += WINDOW_SECONDS + 5.0
    return words, segments_out


def timing_metrics(words: list[dict], sample_seconds: float) -> dict:
    gaps: list[float] = []
    sentence_gaps: list[float] = []
    sentence_lengths: list[int] = []
    current_sentence = 0
    active_seconds = 0.0
    for index, word in enumerate(words):
        active_seconds += max(0.0, word["end"] - word["start"])
        current_sentence += 1
        if index + 1 < len(words) and words[index + 1]["sample"] == word["sample"]:
            gap = max(0.0, words[index + 1]["start"] - word["end"])
            if gap >= 0.12:
                gaps.append(gap)
            if re.search(r"[.!?][\"']?$", word["text"]):
                sentence_gaps.append(gap)
                sentence_lengths.append(current_sentence)
                current_sentence = 0
        elif current_sentence:
            sentence_lengths.append(current_sentence)
            current_sentence = 0
    return {
        "recognized_words": len(words),
        "sampled_minutes": round(sample_seconds / 60, 3),
        "gross_wpm": round(len(words) / (sample_seconds / 60), 2),
        "articulation_wpm": round(len(words) / max(active_seconds / 60, 0.01), 2),
        "pause_count_ge_120ms": len(gaps),
        "pauses_per_minute": round(len(gaps) / (sample_seconds / 60), 2),
        "pause_median_s": percentile(gaps, 50),
        "pause_p75_s": percentile(gaps, 75),
        "pause_p90_s": percentile(gaps, 90),
        "pause_p95_s": percentile(gaps, 95),
        "sentence_end_pause_median_s": percentile(sentence_gaps, 50),
        "sentence_end_pause_p75_s": percentile(sentence_gaps, 75),
        "sentence_words_median": percentile([float(x) for x in sentence_lengths], 50),
        "sentence_words_p75": percentile([float(x) for x in sentence_lengths], 75),
        "sentence_words_p90": percentile([float(x) for x in sentence_lengths], 90),
    }


def analyze(path: Path, model: WhisperModel) -> dict:
    duration = media_duration(path)
    windows = extract_windows(path, duration)
    transcript_cache = OUTPUT / f"{path.stem}_sampled_transcript.json"
    if transcript_cache.is_file():
        cached = json.loads(transcript_cache.read_text(encoding="utf-8"))
        words, segments = cached["words"], cached["segments"]
    else:
        words, segments = transcribe_samples(model, windows)
        transcript_cache.write_text(
            json.dumps({"words": words, "segments": segments}, indent=2),
            encoding="utf-8",
        )

    all_pitch: list[float] = []
    all_rms: list[float] = []
    for window in windows:
        pcm = read_pcm(window)
        all_pitch.extend(estimate_pitch(pcm))
        all_rms.extend(frame_rms(pcm))

    pitch_p10 = percentile(all_pitch, 10)
    pitch_p90 = percentile(all_pitch, 90)
    pitch_span = None
    if pitch_p10 and pitch_p90:
        pitch_span = round(12 * math.log2(pitch_p90 / pitch_p10), 2)
    result = {
        "file": str(path),
        "source_duration_s": round(duration, 3),
        "sample_windows": [str(item) for item in windows],
        "full_mix_loudness": full_mix_loudness(path),
        "timing": timing_metrics(words, len(windows) * WINDOW_SECONDS),
        "delivery_pitch": {
            "p10_hz": pitch_p10,
            "median_hz": percentile(all_pitch, 50),
            "p90_hz": pitch_p90,
            "p10_p90_span_semitones": pitch_span,
            "note": "Non-identifying delivery statistic from voiced frames; not a voiceprint.",
        },
        "speech_level_samples": {
            "rms_p10_dbfs": percentile(all_rms, 10),
            "rms_median_dbfs": percentile(all_rms, 50),
            "rms_p90_dbfs": percentile(all_rms, 90),
            "dynamic_span_db": round((percentile(all_rms, 90) or 0) - (percentile(all_rms, 10) or 0), 2),
        },
        "transcript_segments": segments,
    }
    (OUTPUT / f"{path.stem}_sampled_profile.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def combined_profile(results: list[dict]) -> dict:
    timing_keys = [
        "gross_wpm", "articulation_wpm", "pauses_per_minute", "pause_median_s",
        "pause_p75_s", "pause_p90_s", "pause_p95_s", "sentence_end_pause_median_s",
        "sentence_end_pause_p75_s", "sentence_words_median", "sentence_words_p75",
        "sentence_words_p90",
    ]
    combined_timing = {
        key: round(float(np.mean([r["timing"][key] for r in results if r["timing"][key] is not None])), 3)
        for key in timing_keys
    }
    combined = {
        "scope": "Non-identifying narration delivery profile; excludes speaker identity and voice cloning.",
        "method": "Six 45-second windows distributed across each episode plus full-mix EBU R128 loudness.",
        "combined_timing": combined_timing,
        "episode_full_mix_loudness": [r["full_mix_loudness"] for r in results],
        "delivery_pitch_medians_hz": [r["delivery_pitch"]["median_hz"] for r in results],
        "delivery_pitch_spans_semitones": [r["delivery_pitch"]["p10_p90_span_semitones"] for r in results],
        "speech_dynamic_spans_db": [r["speech_level_samples"]["dynamic_span_db"] for r in results],
        "limitations": [
            "Full-mix loudness includes mastering, music, and effects; it is not dry-voice loudness.",
            "Pitch is a broad delivery measurement and must not be used to recreate speaker identity.",
            "Sampling estimates episode-wide cadence while avoiding retention of full transcripts.",
        ],
    }
    (OUTPUT / "combined_sampled_delivery_profile.json").write_text(
        json.dumps(combined, indent=2), encoding="utf-8"
    )
    return combined


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = WhisperModel("small.en", device="cpu", compute_type="int8")
    results = [analyze(path, model) for path in FILES]
    print(json.dumps(combined_profile(results), indent=2))


if __name__ == "__main__":
    main()
