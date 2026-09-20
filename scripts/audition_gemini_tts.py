"""Generate and objectively screen original Gemini narrator candidates."""
from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import dotenv_values

from pipeline import audio_qc
from pipeline.gemini_tts import GeminiTTSClient


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "voice_canary" / "gemini_original_presenter"
DEFAULT_ENV = Path(
    r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker"
)
VOICES = ("Achird", "Zubenelgenubi", "Charon")
CANARY_TEXT = (
    "Before we get into the results, here's the plan. Google's new video node can handle five "
    "different jobs, which sounds convenient, but convenience is not the same thing as reliability. "
    "So we'll look at what actually launched, where the workflow saves time, and which claims still "
    "need a proper test. Then I'll show you the order I'd use, because spending on the final render "
    "before the idea works is basically lighting money on fire with extra steps."
)


def candidate_score(review: dict) -> float:
    metrics = review["metrics"]
    if not review["passed"]:
        return -100.0
    pace = max(0.0, 1.0 - abs(float(metrics["words_per_minute"]) - 170.0) / 45.0)
    intelligibility = float(metrics["intelligibility"])
    noise = max(0.0, 1.0 - float(metrics["spectral_flatness"]) / 0.08)
    pauses = 1.0 if float(metrics["longest_silence_seconds"]) <= 2.5 else 0.5
    return round(4 * intelligibility + 2.5 * pace + 2 * noise + pauses, 4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    key = str(values.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or "")
    if not key:
        raise SystemExit("GEMINI_API_KEY is missing from the selected environment file")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    def generate(voice: str) -> tuple[str, Path, dict]:
        path = OUTPUT / f"{voice.casefold()}_canary.wav"
        if args.force:
            path.unlink(missing_ok=True)
        result = GeminiTTSClient(key, voice=voice).synthesize(CANARY_TEXT, path)
        review = audio_qc.review_narration(
            path,
            CANARY_TEXT,
            reference_path=None,
            enforce_pacing=True,
            max_unmatched_words=6,
            min_intelligibility=0.9,
        )
        review["selection_score"] = candidate_score(review)
        review["provider"] = "gemini"
        review["model"] = result.model
        review["voice"] = voice
        review["usage"] = result.usage
        return voice, path, review

    records = []
    with ThreadPoolExecutor(max_workers=len(VOICES)) as executor:
        futures = [executor.submit(generate, voice) for voice in VOICES]
        for future in as_completed(futures):
            voice, path, review = future.result()
            records.append({"voice": voice, "path": str(path), "review": review})
    records.sort(key=lambda item: (-item["review"]["selection_score"], VOICES.index(item["voice"])))
    receipt = {
        "selected_voice": records[0]["voice"],
        "selected_path": records[0]["path"],
        "model": "gemini-2.5-pro-preview-tts",
        "selection_policy": "passed ASR/noise/pacing gates, then closest natural explainer cadence",
        "candidates": records,
    }
    (OUTPUT / "audition_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({
        "selected_voice": receipt["selected_voice"],
        "selected_path": receipt["selected_path"],
        "candidates": [
            {
                "voice": item["voice"],
                "passed": item["review"]["passed"],
                "score": item["review"]["selection_score"],
                "wpm": item["review"]["metrics"]["words_per_minute"],
                "intelligibility": item["review"]["metrics"]["intelligibility"],
            }
            for item in records
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
