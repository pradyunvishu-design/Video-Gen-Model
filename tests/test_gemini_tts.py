from pathlib import Path

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
