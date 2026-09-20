import wave

import numpy as np

from pipeline.audio_qc import _largest_unmatched_run, _window_voice_metrics, intelligibility_score, technical_metrics


def test_technical_metrics_report_background_noise(tmp_path):
    sample_rate = 24000
    rng = np.random.default_rng(7)
    time = np.arange(sample_rate * 2) / sample_rate
    samples = 0.12 * np.sin(2 * np.pi * 220 * time) + 0.004 * rng.standard_normal(len(time))
    pcm = np.clip(samples * 32767, -32768, 32767).astype("<i2")
    path = tmp_path / "narration-with-noise.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(pcm.tobytes())

    metrics = technical_metrics(path)
    assert "background_noise_dbfs" in metrics
    assert "low_level_noise_ratio" in metrics
    assert 0 <= metrics["low_level_noise_ratio"] <= 1


def test_intelligibility_is_case_and_punctuation_insensitive():
    expected = "ComfyUI shipped a new workflow feature. It is useful."
    recognized = "comfy ui shipped a new workflow feature it is useful"
    assert intelligibility_score(expected, recognized) > 0.85


def test_intelligibility_rejects_garbled_transcript():
    expected = "The model runs locally and the repository includes weights."
    recognized = "static water model purple broken"
    assert intelligibility_score(expected, recognized) < 0.5


def test_intelligibility_accepts_spoken_and_compact_resolution_values():
    expected = (
        "three sixty P, seven twenty P, ten eighty P, and four K. "
        "Up to sixty percent faster than Omni one point one's standard seven twenty P."
    )
    recognized = "360p, 720p, 1080p, and 4K. Up to 60% faster than Omni 1.1's standard 720p."

    assert intelligibility_score(expected, recognized) > 0.9


def test_window_voice_metrics_expose_mid_file_speaker_change():
    sample_rate = 24000
    time = np.arange(sample_rate * 6) / sample_rate
    approved = (0.2 * np.sin(2 * np.pi * 210 * time) + 0.1 * np.sin(2 * np.pi * 420 * time)).astype("float32")
    other = (0.2 * np.sin(2 * np.pi * 900 * time) + 0.1 * np.sin(2 * np.pi * 1800 * time)).astype("float32")

    consistent = _window_voice_metrics(approved, np.tile(approved, 2), sample_rate)
    switched = _window_voice_metrics(approved, np.concatenate([approved, other]), sample_rate)

    assert consistent["voice_similarity_p10"] > 0.9
    assert switched["voice_similarity_p10"] < 0.35
    assert switched["voice_similarity_spread"] > 0.55


def test_unmatched_run_catches_a_foreign_language_section():
    expected = "This release runs locally and includes the model weights for creators to test."
    recognized = "This release runs locally hola este segmento cambia completamente de idioma y voz model weights."

    expected_run, recognized_run = _largest_unmatched_run(expected, recognized)

    assert max(expected_run, recognized_run) > 6
