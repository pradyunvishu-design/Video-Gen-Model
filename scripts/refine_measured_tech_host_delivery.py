"""Second-pass original narrator canary with connected, non-performed phrasing."""
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
from scripts.audition_measured_tech_host_delivery import metric_distance, percentile, transcription_metrics
from scripts.rebuild_clear_voice_aligned_intro import master


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker")
OUTPUT = ROOT / "output" / "voice_canary" / "measured_original_tech_host_v4_round2"
MODEL = "gemini-3.1-flash-tts-preview"
VOICE = "Zubenelgenubi"

TEXT = (
    "ComfyUI just put five Gemini video tasks inside one node, which is genuinely useful if your "
    "current workflow involves three tabs and one folder called final, final, actually final. "
    "The catch is that convenience is not reliability, so the useful test is pretty boring: make "
    "one short clip, change one detail, then watch the face, lighting, and camera movement. If those "
    "survive twice, increase the resolution; if they do not, four K gives you a sharper view of the "
    "same problem. In this video, we will check the controls and official examples, then end with the "
    "cheapest workflow I would actually use."
)

DIRECTOR = """Read only the transcript below. Never read these notes aloud.

Use an original male American technology explainer voice. Do not imitate or evoke any identifiable real creator. Speak as if you are explaining a useful technical finding to one colleague after testing it yourself.

Underplay the delivery. Keep the voice plain, lightly dry, and matter-of-fact. Aim near 142 words per minute. Connect clauses into complete thoughts: do not pause after every comma, list item, contrast, or sentence. Use roughly one brief thinking pause every four seconds, usually 0.20 to 0.35 seconds. Continue through the rest with clean, efficient articulation. End statements neutrally or slightly downward. Emphasize only the one word that changes the meaning of a thought.

Do not sound warm for effect. Do not stretch vowels, smile through the copy, make the joke cute, announce the next point, or reset at sentence boundaries. Avoid radio voice, sales energy, podcast swagger, theatrical sincerity, trailer pacing, dramatic silence, sing-song rhythm, breathy intimacy, vocal fry, fake laughter, and synthetic perfection. Keep one consistent speaker and finish every word.

TRANSCRIPT:
"""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    key = str(dotenv_values(ENV_FILE).get("GEMINI_API_KEY") or "")
    raw = OUTPUT / "zubenelgenubi_connected_raw.wav"
    mastered = OUTPUT / "zubenelgenubi_connected_master.wav"
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
    review = audio_qc.review_narration(
        mastered, TEXT, ROOT / "data" / "episodes" / "episode_20260901_03",
        recognized_text=recognized, enforce_pacing=False, max_unmatched_words=16,
        min_intelligibility=0.90,
    )
    report = {
        "voice": VOICE,
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
    (OUTPUT / "refinement_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
