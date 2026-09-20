"""Audition original young-adult AI-news narrator voices with natural delivery."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from dotenv import dotenv_values
from faster_whisper import WhisperModel

from pipeline import audio_qc
from pipeline.gemini_tts import GeminiTTSClient
from pipeline.render_v2 import duration
from scripts.analyze_reference_delivery_sampled import estimate_pitch, frame_rms, full_mix_loudness, read_pcm
from scripts.audition_measured_tech_host_delivery import percentile, transcription_metrics
from scripts.rebuild_clear_voice_aligned_intro import master


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker")
OUTPUT = ROOT / "output" / "voice_canary" / "young_ai_native_host_v5"
MODEL = "gemini-3.1-flash-tts-preview"
# Official voice labels: casual, clear, even, and youthful. The prompt keeps
# every result adult and avoids influencer-style performance.
VOICES = ("Zubenelgenubi", "Iapetus", "Schedar", "Leda")

TEXT = (
    "Okay, ComfyUI just put five Gemini video tools in one node. And yeah, that is useful if your "
    "current setup is three tabs and a folder called final, final, actually final. But the menu is "
    "not the test. The real question is whether the face, lighting, and camera movement survive when "
    "you change one detail. So I would start with a cheap ten-second render, watch it twice, and only "
    "then increase the resolution. If the motion already looks wrong, four K is not fixing it. It is "
    "just giving you a much clearer view of the mistake."
)

DIRECTOR = """Read only the transcript below. Never read or paraphrase these production notes.

Use one original North American technology-presenter voice. The speaker is a credible young adult, roughly 20 to 28: old enough to sound informed and responsible, young enough that AI tools feel native rather than novel. Do not imitate or evoke any identifiable creator.

Talk to one technically curious friend after testing the product yourself. Keep the tone relaxed, slightly nerdy, and matter-of-fact. Sound conversational, not casual on purpose. The opening word "Okay" is a natural lead-in, not an announcement. Treat "And yeah" as a quick acknowledgment, not a catchphrase. Underplay the folder joke completely.

Stay around 148 to 155 words per minute. Move efficiently through setup clauses, then take brief 0.20 to 0.40 second thought breaks. Connect lists and contrasts instead of pausing on every comma. Keep a stable adult register, light vocal energy, restrained pitch movement, and mostly neutral or downward endings. A little rhythm variation is good; polished radio symmetry is not. Keep pronunciation clean and the speaker identity consistent.

Do not add slang, filler words, stutters, fake breaths, laughter, smiling delivery, vocal fry, exaggerated Gen-Z cadence, TikTok cadence, influencer energy, podcast swagger, announcer polish, sales excitement, theatrical warmth, sing-song rhythm, or dramatic silence. Do not stretch vowels or punch every important word.

TRANSCRIPT:
"""


def natural_delivery_distance(timing: dict, pitch: dict, dynamic_span: float, loudness: dict) -> float:
    targets = {
        "gross_wpm": (151.5, 10.0),
        "pauses_per_minute": (15.0, 6.0),
        "pause_median_s": (0.31, 0.14),
        "pause_p90_s": (0.50, 0.22),
        "sentence_end_pause_median_s": (0.32, 0.18),
    }
    values = [abs(timing[key] - center) / scale for key, (center, scale) in targets.items()]
    if pitch.get("median_hz"):
        values.append(0.15 * abs(pitch["median_hz"] - 150.0) / 40.0)
    values.append(0.20 * abs(dynamic_span - 19.0) / 8.0)
    if loudness.get("integrated_lufs") is not None:
        values.append(0.15 * abs(loudness["integrated_lufs"] + 17.0) / 2.0)
    return round(float(np.mean(values)), 4)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    key = str(dotenv_values(ENV_FILE).get("GEMINI_API_KEY") or "")
    if not key:
        raise RuntimeError(f"GEMINI_API_KEY is missing from {ENV_FILE}")
    asr = WhisperModel("small.en", device="cpu", compute_type="int8")
    records: list[dict] = []
    for voice in VOICES:
        raw = OUTPUT / f"{voice.casefold()}_raw.wav"
        mastered = OUTPUT / f"{voice.casefold()}_master.wav"
        result = GeminiTTSClient(key, model=MODEL, voice=voice, timeout_seconds=240).synthesize(
            TEXT, raw, director_prompt=DIRECTOR, retries=2
        )
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
        dynamic_span = round(
            (percentile(rms_values, 90) or 0) - (percentile(rms_values, 10) or 0), 2
        )
        loudness = full_mix_loudness(mastered)
        review = audio_qc.review_narration(
            mastered, TEXT, ROOT / "data" / "episodes" / "episode_20260901_03",
            recognized_text=recognized, enforce_pacing=False, max_unmatched_words=16,
            min_intelligibility=0.90,
        )
        records.append({
            "voice": voice,
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
        })
    records.sort(key=lambda item: (not item["audio_qc"]["passed"], item["natural_delivery_distance"]))
    report = {
        "scope": "Original young-adult AI-news narrator audition; no voice cloning or real-person impersonation.",
        "human_approval_required": True,
        "candidates": records,
    }
    (OUTPUT / "audition_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
