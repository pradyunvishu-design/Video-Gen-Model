from pipeline.models import ScriptBeat
from pathlib import Path

from pipeline.visual_director import _cue_is_semantically_safe, plan_annotation


def _beat(direction: str) -> ScriptBeat:
    return ScriptBeat(
        id="beat-1",
        narration="The official workflow file shows the control.",
        purpose="evidence",
        visual_direction=direction,
    )


def test_underline_requires_trusted_visible_phrase() -> None:
    beat = _beat("Underline the exact launch headline.")
    assert _cue_is_semantically_safe(
        style="underline", x=0.2, y=0.2, width=0.4, height=0.05,
        label="MiniMax H3", beat=beat,
        source_title="MiniMax H3 open source", artifact_label="launch headline",
        artifact_text="MiniMax H3 open source",
    )
    assert not _cue_is_semantically_safe(
        style="underline", x=0.2, y=0.2, width=0.4, height=0.05,
        label="random phrase", beat=beat,
        source_title="MiniMax H3 open source", artifact_label="launch headline",
        artifact_text="MiniMax H3 open source",
    )


def test_arrow_requires_named_small_target() -> None:
    assert _cue_is_semantically_safe(
        style="arrow", x=0.45, y=0.3, width=0.1, height=0.1,
        label="Official workflow", beat=_beat("Point to the workflow button."),
        source_title="Official workflow", artifact_label="workflow button",
        artifact_text="Official workflow button",
    )
    assert not _cue_is_semantically_safe(
        style="arrow", x=0.2, y=0.2, width=0.5, height=0.4,
        label="Official workflow", beat=_beat("Show the article headline."),
        source_title="Official workflow", artifact_label="article headline",
        artifact_text="Official workflow article headline",
    )


def test_spotlight_rejects_nearly_full_frame_guess() -> None:
    assert not _cue_is_semantically_safe(
        style="spotlight", x=0.01, y=0.01, width=0.95, height=0.9,
        label="", beat=_beat("Show the result panel."),
        source_title="Result", artifact_label="result panel",
        artifact_text="Result panel",
    )


def test_dom_range_bypasses_guessing_and_underlines_exact_line() -> None:
    annotation = plan_annotation(
        Path("not-opened-because-dom-range-is-authoritative.png"),
        _beat("Underline the exact launch headline."),
        source_title="Editorial title is not visual proof",
        artifact_label="MiniMax H3 open source",
        artifact_text="Today MiniMax H3 open source is available for testing.",
        exact_text_region={"x": 0.12, "y": 0.3, "width": 0.30, "height": 0.04},
    )
    assert annotation is not None
    assert annotation.style == "underline"
    assert annotation.target_text == "MiniMax H3 open source"
    assert annotation.verification_method == "dom-range"


def test_source_title_alone_cannot_authorize_an_underline() -> None:
    assert not _cue_is_semantically_safe(
        style="underline", x=0.2, y=0.2, width=0.4, height=0.05,
        label="MiniMax H3", beat=_beat("Underline the exact launch headline."),
        source_title="MiniMax H3", artifact_label="launch headline", artifact_text="",
    )
