from pipeline.visual_style_profile import (
    DEFAULT_VISUAL_STYLE_PROFILE,
    TRAINING_VISUAL_STYLE_PROFILE,
    composition_family,
    load_visual_style_profile,
    route_pattern,
    semantic_intent,
    visual_style_profile_sha256,
)


def test_versioned_profile_loads_with_training_thresholds() -> None:
    profile = load_visual_style_profile()
    assert profile["version"] == DEFAULT_VISUAL_STYLE_PROFILE
    assert profile["timing"]["meaningfulStateChangeMaxSeconds"] == 3.0
    assert profile["typography"]["minimumBodyPx"] == 28


def test_semantic_routing_avoids_adjacent_pattern_repetition() -> None:
    profile = load_visual_style_profile()
    pattern = route_pattern(
        "proof",
        available_kinds={"source"},
        prior_patterns=["source-browser-proof"],
        prior_compositions=["evidence-ledger"],
        profile=profile,
    )
    assert pattern == "source-repo-metrics"
    assert composition_family(pattern) == "full-frame-proof"
    assert semantic_intent("limitation") == "caveat"


def test_training_profile_declares_final_raster_and_delivery_contract() -> None:
    profile = load_visual_style_profile(TRAINING_VISUAL_STYLE_PROFILE)
    assert profile["canvas"]["renderScale"] == 0.5
    assert profile["delivery"] == {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "videoCodec": "h264",
        "audioCodec": "aac",
        "audioChannels": 2,
        "audioSampleRate": 48000,
    }
    assert len(visual_style_profile_sha256(profile)) == 64
