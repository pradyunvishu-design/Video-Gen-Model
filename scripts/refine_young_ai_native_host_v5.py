"""Refine the selected original young-adult narrator without pitch shifting."""
from __future__ import annotations

import json
import math
from pathlib import Path

from dotenv import dotenv_values
from faster_whisper import WhisperModel

from pipeline import audio_qc
from pipeline.gemini_tts import GeminiTTSClient
from pipeline.render_v2 import duration
from scripts.analyze_reference_delivery_sampled import estimate_pitch, frame_rms, full_mix_loudness, read_pcm
from scripts.audition_measured_tech_host_delivery import percentile, transcription_metrics
from scripts.audition_young_ai_native_host_v5 import TEXT, natural_delivery_distance
from scripts.rebuild_clear_voice_aligned_intro import master


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker")
OUTPUT = ROOT / "output" / "voice_canary" / "young_ai_native_host_v5_refined"
MODEL = "gemini-3.1-flash-tts-preview"
VOICE = "Iapetus"

DIRECTOR = """Read only the transcript below. Never read or paraphrase these notes.

Use one original North American male technology-presenter voice. The speaker is a credible young adult, roughly 20 to 28: technically fluent, responsible, and accustomed to AI tools. Do not imitate or evoke any identifiable creator.

This is a low-key explanation to one friend, recorded on a clean microphone after actually testing the product. Stay relaxed and matter-of-fact. The speaker is not trying to sound young, cool, funny, polished, or impressive. Let the language do that work.

Use an easy pace near 142 to 148 words per minute. Do not rush the first two sentences. Move efficiently inside a thought, but connect sentence endings into the next idea without a performance reset. Use short, quiet thinking gaps only when the argument changes. Keep lists connected. Keep an adult middle register, restrained pitch movement, light energy, and neutral or slightly downward endings. Underplay the folder joke as if it is barely an aside.

Do not add words, slang, filler, stutters, fake breaths, laughter, vocal fry, smiling delivery, influencer cadence, TikTok cadence, podcast swagger, announcer polish, radio compression, sales energy, theatrical warmth, sing-song rhythm, or dramatic pauses. Keep one consistent speaker and finish every word clearly.

TRANSCRIPT:
"""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    key = str(dotenv_values(ENV_FILE).get("GEMINI_API_KEY") or "")
    raw = OUTPUT / "iapetus_young_adult_raw.wav"
    mastered = OUTPUT / "iapetus_young_adult_master.wav"
    result = GeminiTTSClient(key, model=MODEL, voice=VOICE, timeout_seconds=240).synthesize(
        TEXT, raw, director_prompt=DIRECTOR, retries=2
    )
    master(raw, mastered)
    asr = WhisperModel("small.en", device="cpu", compute_type="int8")
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
    dynamic_span = round(
        (percentile(rms_values, 90) or 0) - (percentile(rms_values, 10) or 0), 2
    )
    loudness = full_mix_loudness(mastered)
    review = audio_qc.review_narration(
        mastered, TEXT, ROOT / "data" / "episodes" / "episode_20260901_03",
        recognized_text=recognized, enforce_pacing=False, max_unmatched_words=16,
        min_intelligibility=0.90,
    )
    report = {
        "voice": VOICE,
        "profile": "original young-adult AI-native technology host",
        "identity_note": "Original Gemini prebuilt voice; not a clone or identifiable-person imitation.",
        "path": str(mastered),
        "duration_seconds": round(duration(mastered), 3),
        "timing": timing,
        "pitch": pitch,
        "speech_dynamic_span_db": dynamic_span,
        "master_loudness": loudness,
        "natural_delivery_distance": natural_delivery_distance(timing, pitch, dynamic_span, loudness),
        "audio_qc": review,
        "usage": result.usage,
    }
    (OUTPUT / "refinement_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
