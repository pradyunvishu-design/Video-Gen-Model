"""High-fidelity, single-speaker narration through Gemini TTS.

The client keeps credentials out of payload logs, writes the returned raw PCM
as a standards-compliant WAV file, and uses short independently cached chunks
to limit long-form voice drift.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
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

Director's notes: Natural American English at roughly 155 to 165 spoken words per minute. Underplay the delivery. Keep a normal conversational volume with small, meaningful changes in pitch. Speak in connected thought groups: give a new technical term or important contrast a little space, then continue naturally. Do not announce headlines or perform jokes. Pause where the meaning changes, not mechanically at every comma. Keep contractions casual and finish every sentence completely, including its last word. Keep the same speaker, accent, vocal distance, and energy throughout. The energy comes from the information, not a sales performance. Avoid radio voice, sing-song cadence, dramatic pauses, exaggerated punchlines, whispering, inserted filler words, and added sound effects. Return clean speech only: no music, background voices, or ambient noise. Read the transcript verbatim; do not add an introduction or conclusion.

SPOKEN TRANSCRIPT — read only the text after this marker:
"""


def split_text(text: str, limit: int = 850) -> list[str]:
    """Split on paragraphs and sentence boundaries without losing exact words."""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("Gemini TTS chunk limit must be a positive integer")
    if not text.strip():
        return []
    if len(text) <= limit:
        return [text.strip()]
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > limit:
            pieces = re.split(r"(?<=[,;:])\s+", sentence)
            bounded = []
            for piece in pieces:
                if len(piece) <= limit:
                    bounded.append(piece)
                    continue
                words = piece.split()
                if any(len(word) > limit for word in words):
                    raise ValueError("Gemini TTS contains a word longer than the chunk limit")
                fragment = ""
                for word in words:
                    if fragment and len(fragment) + 1 + len(word) > limit:
                        bounded.append(fragment)
                        fragment = ""
                    fragment = f"{fragment} {word}".strip()
                if fragment:
                    bounded.append(fragment)
            pieces = bounded
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


def _decode_pcm(audio: dict) -> tuple[bytes, int]:
    """Fail closed rather than wrapping compressed/invalid bytes in a WAV header."""
    mime = audio.get("mimeType", "").lower()
    if mime.split(";", 1)[0].strip() not in {"audio/l16", "audio/pcm"}:
        raise ValueError("Gemini TTS returned an unsupported audio format; expected mono PCM")
    channels = re.search(r"channels\s*=\s*(\d+)", mime)
    if channels and int(channels.group(1)) != 1:
        raise ValueError("Gemini TTS returned multiple audio channels")
    pcm = base64.b64decode(audio["data"], validate=True)
    rate = _sample_rate(mime)
    if not pcm or len(pcm) % 2 or not 8000 <= rate <= 96000:
        raise ValueError("Gemini TTS returned invalid PCM samples or sample rate")
    if pcm.startswith((b"RIFF", b"ID3", b"OggS", b"fLaC")):
        raise ValueError("Gemini TTS returned a container instead of raw PCM")
    return pcm, rate


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _cached_audio_valid(destination: Path, metadata: Path, prompt_hash: str) -> bool:
    try:
        record = json.loads(metadata.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            return False
        if record.get("prompt_hash") != prompt_hash:
            return False
        if record.get("audio_sha256") != hashlib.sha256(destination.read_bytes()).hexdigest():
            return False
        with wave.open(str(destination), "rb") as handle:
            return (handle.getnchannels() == 1 and handle.getsampwidth() == 2
                    and handle.getnframes() > 0 and handle.getcomptype() == "NONE")
    except (OSError, ValueError, EOFError, wave.Error):
        return False


def write_pcm_wav(path: Path, pcm: bytes, *, sample_rate: int = DEFAULT_SAMPLE_RATE) -> Path:
    if not pcm or len(pcm) % 2 or not 8000 <= sample_rate <= 96000:
        raise ValueError("WAV requires nonempty 16-bit PCM and a supported sample rate")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(fd)
    try:
        with wave.open(temporary, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(pcm)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
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
        if not isinstance(retries, int) or isinstance(retries, bool) or retries < 1:
            raise ValueError("Gemini TTS retries must be a positive integer")
        destination = Path(destination)
        prompt = director_prompt.rstrip() + "\n\n" + spoken
        prompt_hash = hashlib.sha256(
            json.dumps(
                {"model": self.model, "voice": self.voice, "prompt": prompt},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        metadata_path = destination.with_suffix(destination.suffix + ".tts.json")
        if _cached_audio_valid(destination, metadata_path, prompt_hash):
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
                    candidate = (data.get("candidates") or [{}])[0]
                    if candidate.get("finishReason") not in {None, "STOP"}:
                        raise RuntimeError("Gemini TTS generation did not finish normally")
                    parts = candidate.get("content", {}).get("parts", [])
                    audio_parts = [part["inlineData"] for part in parts if part.get("inlineData")]
                    audio = audio_parts[0] if audio_parts else None
                if not audio or not audio.get("data"):
                    raise RuntimeError("Gemini TTS response did not contain audio")
                decoded = [_decode_pcm(part) for part in ([audio] if uses_interactions else audio_parts)]
                sample_rate = decoded[0][1]
                if any(rate != sample_rate for _, rate in decoded):
                    raise ValueError("Gemini TTS returned inconsistent audio sample rates")
                pcm = b"".join(samples for samples, _ in decoded)
                write_pcm_wav(destination, pcm, sample_rate=sample_rate)
                _atomic_write(metadata_path, json.dumps({
                    "schema_version": 1, "prompt_hash": prompt_hash,
                    "model": self.model, "voice": self.voice,
                    "audio_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                }, sort_keys=True).encode("utf-8"))
                return GeminiTTSResult(
                    destination,
                    self.model,
                    self.voice,
                    prompt_hash,
                    data.get("usageMetadata") or data.get("usage") or {},
                )
            except (requests.RequestException, ValueError, KeyError, RuntimeError) as exc:
                if isinstance(exc, requests.HTTPError):
                    status = getattr(exc.response, "status_code", None)
                    if status not in {429, 500, 502, 503, 504}:
                        raise RuntimeError(f"Gemini TTS request rejected (HTTP {status}); check configuration") from None
                last_error = exc
                # Invalid successful responses are not transient network failures.
                if not isinstance(exc, requests.RequestException):
                    break
                if attempt < retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Gemini TTS failed after {attempt} attempts ({type(last_error).__name__}); no valid audio saved") from None
