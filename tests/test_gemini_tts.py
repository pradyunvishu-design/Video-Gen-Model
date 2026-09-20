from pathlib import Path

import base64
import wave

import pytest
import requests

from pipeline import gemini_tts


def test_split_text_preserves_words_and_stays_bounded():
    text = "One short sentence. " * 80
    chunks = gemini_tts.split_text(text, limit=140)
    assert len(chunks) > 1
    assert all(len(chunk) <= 140 for chunk in chunks)
    assert " ".join(chunks).split() == text.split()


def test_synthesize_writes_pcm_response(monkeypatch, tmp_path: Path):
    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            import base64

            return {
                "candidates": [{
                    "content": {"parts": [{
                        "inlineData": {
                            "mimeType": "audio/L16;codec=pcm;rate=24000",
                            "data": base64.b64encode(b"\x00\x00" * 240).decode(),
                        }
                    }]}
                }],
                "usageMetadata": {"promptTokenCount": 10},
            }

    monkeypatch.setattr(gemini_tts.requests, "post", lambda *args, **kwargs: Response())
    output = tmp_path / "voice.wav"
    result = gemini_tts.GeminiTTSClient("valid-key-value-for-test").synthesize("Hello there.", output)
    assert result.path == output
    assert output.read_bytes().startswith(b"RIFF")


def audio_response(*, pcm=b"\x01\x00" * 240, mime="audio/L16;codec=pcm;rate=24000", finish="STOP"):
    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"finishReason": finish, "content": {"parts": [
                {"inlineData": {"mimeType": mime, "data": base64.b64encode(pcm).decode()}}
            ]}}]}
    return Response()


def test_cache_reuses_only_matching_script_voice_and_valid_audio(monkeypatch, tmp_path):
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs["json"])
        return audio_response()
    monkeypatch.setattr(gemini_tts.requests, "post", post)
    output = tmp_path / "voice.wav"
    client = gemini_tts.GeminiTTSClient("test-api-key", voice="Zubenelgenubi")
    first = client.synthesize("One complete thought.", output)
    assert client.synthesize("One complete thought.", output).usage == {"cached": True}
    second = client.synthesize("A revised complete thought.", output)
    assert second.prompt_hash != first.prompt_hash
    changed = gemini_tts.GeminiTTSClient("test-api-key", voice="Achird")
    changed.synthesize("A revised complete thought.", output)
    output.write_bytes(b"corrupted audio")
    changed.synthesize("A revised complete thought.", output)
    assert len(calls) == 4
    assert calls[0]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Zubenelgenubi"
    assert "test-api-key" not in output.with_suffix(".wav.tts.json").read_text()


def test_legacy_wav_without_cache_record_is_not_reused(monkeypatch, tmp_path):
    output = tmp_path / "old.wav"
    gemini_tts.write_pcm_wav(output, b"\x00\x00" * 240)
    calls = []
    monkeypatch.setattr(gemini_tts.requests, "post", lambda *a, **k: calls.append(1) or audio_response())
    gemini_tts.GeminiTTSClient("test-api-key").synthesize("New words.", output)
    assert calls == [1]


@pytest.mark.parametrize("mime,pcm", [
    ("audio/mpeg", b"\x00\x00" * 240),
    ("audio/pcm;rate=24000", b"odd"),
    ("audio/pcm;rate=0", b"\x00\x00"),
    ("audio/pcm;rate=24000;channels=2", b"\x00\x00"),
    ("audio/pcm;rate=24000", b""),
    ("audio/pcm;rate=24000", b"RIFF" + b"\x00\x00" * 240),
], ids=["compressed", "odd-samples", "bad-rate", "stereo", "empty", "container"])
def test_rejects_invalid_audio_without_retrying_or_overwriting(monkeypatch, tmp_path, mime, pcm):
    output = tmp_path / "voice.wav"
    output.write_bytes(b"previous approved file")
    calls = []
    monkeypatch.setattr(gemini_tts.requests, "post", lambda *a, **k: calls.append(1) or audio_response(mime=mime, pcm=pcm))
    with pytest.raises(RuntimeError, match="no valid audio saved"):
        gemini_tts.GeminiTTSClient("test-api-key").synthesize("New words.", output)
    assert calls == [1]
    assert output.read_bytes() == b"previous approved file"


def test_rejects_truncated_generation(monkeypatch, tmp_path):
    monkeypatch.setattr(gemini_tts.requests, "post", lambda *a, **k: audio_response(finish="MAX_TOKENS"))
    output = tmp_path / "voice.wav"
    with pytest.raises(RuntimeError):
        gemini_tts.GeminiTTSClient("test-api-key").synthesize("Do not cut off my sentence.", output)
    assert not output.exists()


def test_permanent_http_error_is_not_retried(monkeypatch, tmp_path):
    calls = []
    class Response:
        status_code = 401
        def raise_for_status(self):
            raise requests.HTTPError("secret-response-body", response=self)
    monkeypatch.setattr(gemini_tts.requests, "post", lambda *a, **k: calls.append(1) or Response())
    with pytest.raises(RuntimeError, match="HTTP 401") as error:
        gemini_tts.GeminiTTSClient("test-api-key").synthesize("Hello.", tmp_path / "voice.wav")
    assert "secret-response-body" not in str(error.value)
    assert calls == [1]


def test_transient_error_retries_and_preserves_voice(monkeypatch, tmp_path):
    class Response:
        status_code = 503
    responses = iter([Response(), audio_response()])
    waits = []
    monkeypatch.setattr(gemini_tts.time, "sleep", waits.append)
    monkeypatch.setattr(gemini_tts.requests, "post", lambda *a, **k: next(responses))
    result = gemini_tts.GeminiTTSClient("test-api-key", voice="Zubenelgenubi").synthesize("Hello.", tmp_path / "voice.wav")
    assert waits == [2]
    assert result.voice == "Zubenelgenubi"


def test_multiple_audio_parts_are_preserved(monkeypatch, tmp_path):
    response = audio_response()
    data = response.json()
    parts = data["candidates"][0]["content"]["parts"]
    parts.append(parts[0].copy())
    monkeypatch.setattr(response, "json", lambda: data)
    monkeypatch.setattr(gemini_tts.requests, "post", lambda *a, **k: response)
    output = tmp_path / "voice.wav"
    gemini_tts.GeminiTTSClient("test-api-key").synthesize("Hello.", output)
    with wave.open(str(output)) as handle:
        assert handle.getnframes() == 480


def test_long_clause_splits_on_words_and_empty_input_is_empty():
    text = "a natural explanation without punctuation " * 20
    chunks = gemini_tts.split_text(text, limit=80)
    assert " ".join(chunks).split() == text.split()
    assert all(len(chunk) <= 80 for chunk in chunks)
    assert gemini_tts.split_text("  ") == []
    with pytest.raises(ValueError):
        gemini_tts.split_text(text, limit=0)


def test_bad_retry_count_fails_before_network(tmp_path):
    with pytest.raises(ValueError, match="positive integer"):
        gemini_tts.GeminiTTSClient("test-api-key").synthesize("Hello.", tmp_path / "voice.wav", retries=0)


def test_interactions_response_retains_configured_voice(monkeypatch, tmp_path):
    response = audio_response()
    monkeypatch.setattr(response, "json", lambda: {"output_audio": {
        "data": base64.b64encode(b"\x01\x00" * 240).decode(),
        "mime_type": "audio/pcm;rate=24000",
    }, "usage": {"total_tokens": 20}})
    payloads = []
    def post(url, **kwargs):
        payloads.append((url, kwargs["json"]))
        return response
    monkeypatch.setattr(gemini_tts.requests, "post", post)
    result = gemini_tts.GeminiTTSClient("test-api-key", model="gemini-3.1-flash-tts-preview", voice="Zubenelgenubi").synthesize("Hello.", tmp_path / "voice.wav")
    assert result.voice == "Zubenelgenubi"
    assert result.usage == {"total_tokens": 20}
    assert payloads[0][0] == gemini_tts.INTERACTIONS_URL
    assert payloads[0][1]["generation_config"]["speech_config"] == [{"voice": "Zubenelgenubi"}]


def test_invalid_base64_fails_closed(monkeypatch, tmp_path):
    response = audio_response()
    data = response.json()
    data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"] = "!!!bad!!!"
    monkeypatch.setattr(response, "json", lambda: data)
    monkeypatch.setattr(gemini_tts.requests, "post", lambda *a, **k: response)
    output = tmp_path / "voice.wav"
    with pytest.raises(RuntimeError):
        gemini_tts.GeminiTTSClient("test-api-key").synthesize("Hello.", output)
    assert not output.exists()
