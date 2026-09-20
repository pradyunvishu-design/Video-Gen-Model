"""Render short original Gemini 3.1 TTS auditions without logging credentials."""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import dotenv_values

from pipeline.gemini_tts import GeminiTTSClient
from pipeline.render_v2 import duration


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = Path(
    r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker"
)
MODEL = "gemini-3.1-flash-tts-preview"
VOICES = ("Achird", "Sulafat", "Zubenelgenubi")
TEXT = (
    "Here is the useful part. Omni puts five different video tasks inside one ComfyUI node. "
    "That sounds convenient, but the menu is not the test. We still need to see whether a face, "
    "the lighting, and the motion survive when the model edits the clip."
)
DIRECTOR = """Read only the transcript below. Do not read these notes aloud.

You are an original male technology host speaking to one friend across a desk. Sound relaxed, curious, and specific. Use natural American English and a close, clean microphone. Let the first sentence feel like you are picking up a real conversation. Vary the pace gently: move through setup language, slow down on the caveat, and land the last sentence without an announcer cadence. Keep tiny natural breath spaces between ideas, but do not insert long silences. No sales voice, radio voice, imitation, exaggerated excitement, sing-song rhythm, or synthetic perfection.

TRANSCRIPT:
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    key = str(dotenv_values(args.env_file).get("GEMINI_API_KEY") or "")
    out = ROOT / "output" / "voice_canary" / "gemini_3_1_human_presenter"
    out.mkdir(parents=True, exist_ok=True)

    def render(voice: str) -> dict:
        destination = out / f"{voice.casefold()}.wav"
        if args.force:
            destination.unlink(missing_ok=True)
        result = GeminiTTSClient(key, model=MODEL, voice=voice).synthesize(
            TEXT, destination, director_prompt=DIRECTOR
        )
        return {
            "voice": voice,
            "path": str(destination),
            "duration_seconds": round(duration(destination), 3),
            "usage": result.usage,
        }

    with ThreadPoolExecutor(max_workers=len(VOICES)) as executor:
        records = list(executor.map(render, VOICES))
    receipt = out / "audition.json"
    receipt.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
