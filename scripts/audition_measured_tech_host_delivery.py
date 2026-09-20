"""Audition original narrator voices against measured delivery-only targets.

Reference files are used only to derive broad, non-identifying delivery
statistics. The generated voices remain Gemini prebuilt voices and must not be
presented as the reference speaker or as a clone.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np
from dotenv import dotenv_values
from faster_whisper import WhisperModel

from pipeline import audio_qc
from pipeline.gemini_tts import GeminiTTSClient
from pipeline.render_v2 import duration
from scripts.analyze_reference_delivery_sampled import estimate_pitch, frame_rms, full_mix_loudness, read_pcm
from scripts.rebuild_clear_voice_aligned_intro import master


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = Path(
    r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker"
)
OUTPUT = ROOT / "output" / "voice_canary" / "measured_original_tech_host_v4"
MODEL = "gemini-3.1-flash-tts-preview"
VOICES = ("Charon", "Sadaltager", "Zubenelgenubi")

TEXT = (
    "ComfyUI just put five Gemini video tasks inside one node. That is genuinely useful, "
    "especially if your current workflow involves three tabs and one folder called final, final, "
    "actually final. But convenience is not the same thing as reliability. So the useful test is "
    "pretty boring: make one short clip, change one detail, and watch what happens to the face, "
    "lighting, and camera movement. If those survive twice, increase the resolution. If they do not, "
    "four K only gives you a sharper view of the problem. In this video, we will check the controls, "
    "compare the official examples, and end with the cheapest workflow I would actually use."
)

DIRECTOR = """Read only the transcript below. Never read these production notes aloud.

Use an original male American technology explainer voice. Do not imitate, reproduce, or evoke any identifiable real creator. The delivery should feel like a technically curious person explaining a finding to one colleague, not performing for an audience.

Measured delivery targets: finish near 145 to 150 words per minute overall. Speak quickly and cleanly inside each thought, then use frequent short thinking gaps around 0.25 to 0.40 seconds. Avoid dramatic gaps over 0.55 seconds. Keep most sentences between 12 and 18 spoken words. Use a grounded middle-low register, a restrained pitch range, and neutral or slightly downward sentence endings. Emphasize at most one useful word in a thought; do not punch every contrast.

Underplay the joke. Keep lists connected. Do not stretch vowels, add warmth for effect, smile through the copy, or reset your performance at paragraph boundaries. Avoid announcer polish, podcast-host swagger, radio voice, sales energy, trailer pacing, theatrical sincerity, breathy intimacy, sing-song rhythm, vocal fry, fake chuckles, and synthetic perfection. Finish every word cleanly and keep one consistent speaker throughout.

TRANSCRIPT:
"""


def percentile(values: list[float], q: float) -> float | None:
    return round(float(np.percentile(values, q)), 3) if values else None


def transcription_metrics(model: WhisperModel, path: Path) -> tuple[str, dict]:
    segments, _ = model.transcribe(
        str(path), language="en", beam_size=4, vad_filter=True,
        word_timestamps=True, condition_on_previous_text=False,
    )
    words: list[dict] = []
    text_parts: list[str] = []
    for segment in segments:
        text_parts.append(segment.text.strip())
        for word in segment.words or []:
            token = word.word.strip()
            if token:
                words.append({"text": token, "start": word.start, "end": word.end})
    gaps: list[float] = []
    sentence_gaps: list[float] = []
    active = 0.0
    for index, word in enumerate(words):
        active += max(0.0, word["end"] - word["start"])
        if index + 1 >= len(words):
            continue
        gap = max(0.0, words[index + 1]["start"] - word["end"])
        if gap >= 0.12:
            gaps.append(gap)
        if re.search(r"[.!?][\"']?$", word["text"]):
            sentence_gaps.append(gap)
    seconds = duration(path)
    return " ".join(text_parts), {
        "recognized_words": len(words),
        "gross_wpm": round(len(words) / max(seconds / 60, 0.01), 2),
        "articulation_wpm": round(len(words) / max(active / 60, 0.01), 2),
        "pauses_per_minute": round(len(gaps) / max(seconds / 60, 0.01), 2),
        "pause_median_s": percentile(gaps, 50),
        "pause_p75_s": percentile(gaps, 75),
        "pause_p90_s": percentile(gaps, 90),
        "sentence_end_pause_median_s": percentile(sentence_gaps, 50),
    }


def metric_distance(metrics: dict, pitch: dict) -> float:
    """Distance from delivery band only; lower is closer, never an identity score."""
    targets = {
        "gross_wpm": (146.885, 12.0),
        "articulation_wpm": (218.305, 28.0),
        "pauses_per_minute": (14.555, 5.0),
        "pause_median_s": (0.285, 0.12),
        "pause_p90_s": (0.473, 0.20),
        "sentence_end_pause_median_s": (0.300, 0.15),
    }
    distances = [abs(metrics[key] - center) / scale for key, (center, scale) in targets.items()]
    # Pitch is deliberately low-weight and broad. It describes register only.
    if pitch.get("median_hz"):
        distances.append(0.25 * abs(pitch["median_hz"] - 138.0) / 35.0)
    return round(float(np.mean(distances)), 4)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    key = str(dotenv_values(DEFAULT_ENV).get("GEMINI_API_KEY") or "")
    if not key:
        raise RuntimeError(f"GEMINI_API_KEY is missing from {DEFAULT_ENV}")
    asr = WhisperModel("small.en", device="cpu", compute_type="int8")
    records: list[dict] = []
    for voice in VOICES:
        raw = OUTPUT / f"{voice.casefold()}_raw.wav"
        mastered = OUTPUT / f"{voice.casefold()}_master.wav"
        result = GeminiTTSClient(key, model=MODEL, voice=voice, timeout_seconds=240).synthesize(
            TEXT, raw, director_prompt=DIRECTOR, retries=2
        )
        if not mastered.is_file():
            master(raw, mastered)
        recognized, timing = transcription_metrics(asr, mastered)
        pcm = read_pcm(mastered)
        pitch_values = estimate_pitch(pcm)
        rms_values = frame_rms(pcm)
        pitch = {
            "p10_hz": percentile(pitch_values, 10),
            "median_hz": percentile(pitch_values, 50),
            "p90_hz": percentile(pitch_values, 90),
        }
        if pitch["p10_hz"] and pitch["p90_hz"]:
            pitch["p10_p90_span_semitones"] = round(
                12 * math.log2(pitch["p90_hz"] / pitch["p10_hz"]), 2
            )
        review = audio_qc.review_narration(
            mastered, TEXT, ROOT / "data" / "episodes" / "episode_20260901_03",
            recognized_text=recognized, enforce_pacing=False, max_unmatched_words=16,
            min_intelligibility=0.90,
        )
        record = {
            "voice": voice,
            "identity_note": "Original Gemini prebuilt voice; not the reference speaker and not a clone.",
            "path": str(mastered),
            "duration_seconds": round(duration(mastered), 3),
            "timing": timing,
            "pitch": pitch,
            "speech_dynamic_span_db": round(
                (percentile(rms_values, 90) or 0) - (percentile(rms_values, 10) or 0), 2
            ),
            "master_loudness": full_mix_loudness(mastered),
            "delivery_band_distance": metric_distance(timing, pitch),
            "audio_qc": review,
            "usage": result.usage,
        }
        records.append(record)
    records.sort(key=lambda item: item["delivery_band_distance"])
    receipt = {
        "reference_scope": "Broad, non-identifying delivery characteristics only.",
        "target": {
            "gross_wpm": 146.885,
            "articulation_wpm": 218.305,
            "pauses_per_minute": 14.555,
            "pause_median_s": 0.285,
            "pause_p90_s": 0.473,
            "sentence_end_pause_median_s": 0.300,
            "target_master_lufs": -17.0,
            "safe_true_peak_dbfs": -1.5,
        },
        "candidates": records,
    }
    (OUTPUT / "audition_report.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
