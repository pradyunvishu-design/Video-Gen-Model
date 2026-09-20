"""High-fidelity, single-speaker narration through Gemini TTS.

The client keeps credentials out of payload logs, writes the returned raw PCM
as a standards-compliant WAV file, and uses short independently cached chunks
to limit long-form voice drift.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import requests


BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_MODEL = "gemini-2.5-pro-preview-tts"
DEFAULT_VOICE = "Achird"
DEFAULT_SAMPLE_RATE = 24000

DIRECTOR_PROMPT = """Synthesize the spoken transcript below. Do not read these production notes aloud.

Audio profile: An original male technology journalist in his late twenties or thirties. Clear, intelligent, grounded, slightly dry, and naturally conversational. This is not an announcer, character voice, celebrity impression, or imitation of any real creator.

Scene: One technically curious person explaining something he actually researched to one colleague in a quiet room.

Director's notes: Natural American English at roughly 155 to 165 spoken words per minute. Underplay the delivery. Keep a normal conversational volume, mostly neutral downward sentence endings, and only small changes in pitch. Do not perform commas, headlines, lists, jokes, or caveats. Pause briefly when a real speaker would think, not automatically after every sentence. Keep contractions casual and finish every sentence completely. The energy must come from the specificity of the information, not vocal emphasis. Avoid radio voice, sales energy, trailer pacing, sing-song cadence, dramatic pauses, exaggerated punchlines, vocal fry, whispering, and synthetic perfection.

SPOKEN TRANSCRIPT — read only the text after this marker:
"""


def split_text(text: str, limit: int = 850) -> list[str]:
    """Split on paragraphs and sentence boundaries without losing exact words."""
    if len(text) <= limit:
        return [text.strip()]
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > limit:
            pieces = re.split(r"(?<=[,;:])\s+", sentence)
        else:
            pieces = [sentence]
        for piece in pieces:
            candidate = piece if not current else current + " " + piece
            if current and len(candidate) > limit:
                chunks.append(current.strip())
                current = piece
            else:
                current = candidate
    if current.strip():
        chunks.append(current.strip())
    if any(len(chunk) > limit for chunk in chunks):
        raise ValueError("Gemini TTS chunk could not be split below the configured limit")
    return chunks


def _sample_rate(mime_type: str) -> int:
    match = re.search(r"rate=(\d+)", mime_type or "", flags=re.I)
    return int(match.group(1)) if match else DEFAULT_SAMPLE_RATE


def write_pcm_wav(path: Path, pcm: bytes, *, sample_rate: int = DEFAULT_SAMPLE_RATE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return path


@dataclass(frozen=True)
class GeminiTTSResult:
    path: Path
    model: str
    voice: str
    prompt_hash: str
    usage: dict


class GeminiTTSClient:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_MODEL,
        voice: str = DEFAULT_VOICE,
        timeout_seconds: int = 180,
    ) -> None:
        if not api_key or api_key.startswith(("replace-", "PASTE_")):
            raise ValueError("a non-placeholder Gemini API key is required")
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.timeout_seconds = timeout_seconds

    def synthesize(
        self,
        transcript: str,
        destination: Path,
        *,
        director_prompt: str = DIRECTOR_PROMPT,
        retries: int = 3,
    ) -> GeminiTTSResult:
        spoken = transcript.strip()
        if not spoken:
            raise ValueError("Gemini TTS transcript is empty")
        prompt = director_prompt.rstrip() + "\n\n" + spoken
        prompt_hash = hashlib.sha256(
            json.dumps(
                {"model": self.model, "voice": self.voice, "prompt": prompt},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        if destination.is_file() and destination.stat().st_size > 44:
            return GeminiTTSResult(destination, self.model, self.voice, prompt_hash, {"cached": True})

        uses_interactions = self.model.startswith("gemini-3.1-")
        if uses_interactions:
            payload = {
                "model": self.model,
                "input": prompt,
                "response_format": {"type": "audio"},
                "generation_config": {
                    "speech_config": [{"voice": self.voice}],
                },
            }
            url = INTERACTIONS_URL
        else:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": self.voice},
                        },
                        "languageCode": "en-US",
                    },
                },
            }
            url = f"{BASE_URL}/{self.model}:generateContent"
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                response = requests.post(
                    url,
                    headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                if response.status_code in {429, 500, 502, 503, 504} and attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                data = response.json()
                if uses_interactions:
                    output_audio = data.get("output_audio") or {}
                    if not output_audio:
                        for step in reversed(data.get("steps") or []):
                            output_audio = next(
                                (
                                    item for item in reversed(step.get("content") or [])
                                    if item.get("type") == "audio" and item.get("data")
                                ),
                                {},
                            )
                            if output_audio:
                                break
                    audio = {
                        "data": output_audio.get("data"),
                        "mimeType": output_audio.get("mime_type") or output_audio.get("mimeType") or "audio/pcm;rate=24000",
                    }
                else:
                    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    audio = next((part.get("inlineData") for part in parts if part.get("inlineData")), None)
                if not audio or not audio.get("data"):
                    raise RuntimeError("Gemini TTS response did not contain audio")
                pcm = base64.b64decode(audio["data"])
                write_pcm_wav(destination, pcm, sample_rate=_sample_rate(audio.get("mimeType", "")))
                return GeminiTTSResult(
                    destination,
                    self.model,
                    self.voice,
                    prompt_hash,
                    data.get("usageMetadata") or data.get("usage") or {},
                )
            except (requests.RequestException, ValueError, KeyError, RuntimeError) as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Gemini TTS failed after {retries} attempts: {last_error}")
