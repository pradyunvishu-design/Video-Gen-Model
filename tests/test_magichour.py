from pipeline import magichour
import pytest


def test_nano_banana_2_image_generation_payload(monkeypatch):
    captured = {}

    def fake_post(path, payload):
        captured.update({"path": path, "payload": payload})
        return {"id": "image-project-1"}

    monkeypatch.setattr(magichour, "_post", fake_post)
    result = magichour.image_generate(
        "clean prompt", "hero", model="nano-banana-2", resolution="2k", image_count=4,
    )
    assert result["id"] == "image-project-1"
    assert captured["path"] == "/v1/ai-image-generator"
    assert captured["payload"] == {
        "name": "hero",
        "image_count": 4,
        "model": "nano-banana-2",
        "aspect_ratio": "16:9",
        "resolution": "2k",
        "style": {"prompt": "clean prompt"},
    }


def test_nano_banana_2_rejects_unsupported_batch_size():
    with pytest.raises(ValueError, match="one of 1, 4, 9, or 16"):
        magichour.image_generate("clean prompt", "hero", model="nano-banana-2", image_count=3)


def test_image_to_video_disables_audio(monkeypatch):
    captured = {}

    def fake_post(path, payload):
        captured.update({"path": path, "payload": payload})
        return {"id": "video_job", "credits_charged": 100}

    monkeypatch.setattr(magichour, "_post", fake_post)
    magichour.image_to_video("api-assets/id/image.png", "subtle motion", "hero", model="veo3.1")
    assert captured["path"] == "/v1/image-to-video"
    assert captured["payload"]["audio"] is False
    assert captured["payload"]["resolution"] == "1080p"
    assert captured["payload"]["style"]["prompt"] == "subtle motion"


def test_voice_client_rejects_text_over_verified_limit():
    with pytest.raises(ValueError, match="1000-character"):
        magichour.voice_clone("x" * 1001, "sample", "too-long")
