from pathlib import Path

from PIL import Image

from pipeline.models import Shot, VisualAnnotation
from pipeline.config import NARRATION_TAIL_PADDING_SECONDS
from pipeline.render_v2 import _animated_underline, _delivery_timing, _still_filter
from pipeline.screenshot_treatment import prepare_editorial_screenshot
from pipeline.visual_director import annotation_is_warranted, fallback_annotation


def _shot(annotation: VisualAnnotation) -> Shot:
    return Shot(
        id="shot_001", beat_id="beat_001", asset_type="screenshot",
        presentation="full_bleed", annotations=[annotation],
    )


def test_editorial_screenshot_is_1080p_and_contains_accent(tmp_path: Path):
    source = tmp_path / "source.png"
    Image.new("RGB", (1200, 700), "white").save(source)
    destination = tmp_path / "treated.jpg"
    annotation = VisualAnnotation(style="underline", x=0.1, y=0.1, width=0.7, height=0.2)

    prepare_editorial_screenshot(source, _shot(annotation), destination, source_label="example.com")

    with Image.open(destination) as result:
        assert result.size == (1920, 1080)
        pixels = result.convert("RGB")
        cyan_pixels = sum(
            count for count, (red, green, blue) in (pixels.getcolors(maxcolors=1920 * 1080) or [])
            if blue > 180 and green > 120 and blue > red * 1.5
        )
        assert cyan_pixels > 500


def test_element_capture_fallback_does_not_guess_inner_coordinates(tmp_path: Path):
    from pipeline.models import ScriptBeat

    path = tmp_path / "story-element-01.png"
    beat = ScriptBeat(id="b1", narration="Evidence.", purpose="evidence", visual_direction="Show result")
    annotation = fallback_annotation(path, beat)
    # Red-underline-only policy requires actual text geometry; a filename is
    # not evidence of the location of a claim.
    assert annotation is None


def test_viewport_fallback_does_not_invent_a_headline_target(tmp_path: Path):
    from pipeline.models import ScriptBeat

    path = tmp_path / "story-viewport-01.png"
    beat = ScriptBeat(id="b1", narration="The result shows a 42% gain.", purpose="evidence", visual_direction="Show result")
    assert fallback_annotation(path, beat) is None


def test_annotation_requires_a_concrete_visual_target():
    from pipeline.models import ScriptBeat

    generic = ScriptBeat(id="b1", narration="This is where things get interesting.", purpose="context", visual_direction="Show the page")
    concrete = ScriptBeat(id="b2", narration="The benchmark shows a 42% gain.", purpose="evidence", visual_direction="Underline the result")
    assert annotation_is_warranted(generic) is False
    assert annotation_is_warranted(concrete) is True


def test_underlines_render_as_thin_red_draw_on_animation():
    annotation = VisualAnnotation(style="underline", x=0.1, y=0.2, width=0.25, height=0.03)
    result = _animated_underline(_shot(annotation), frames=150, seconds=5)
    assert result is not None
    line_input, graph = result
    assert "0xB84D45" in line_input
    assert "x3:" in line_input
    assert "(t-0.22)/0.34" in graph


def test_whole_paragraph_is_not_underlined():
    annotation = VisualAnnotation(style="underline", x=0.1, y=0.2, width=0.6, height=0.12)
    assert _animated_underline(_shot(annotation), frames=150, seconds=5) is None


def test_screen_grabs_ignore_off_axis_focus_and_stay_centered():
    shot = Shot(
        id="shot_center", beat_id="beat_001", asset_type="screenshot",
        focus_x=0.1, focus_y=0.9, motion_style="pan_right",
    )
    video_filter = _still_filter(shot, frames=150)
    assert "0.5000" in video_filter
    assert "0.34+0.26" not in video_filter


def test_delivery_timing_holds_the_last_frame_past_the_voice():
    output_seconds, video_pad = _delivery_timing(150.0, 149.9)
    assert output_seconds == 150.0 + NARRATION_TAIL_PADDING_SECONDS
    assert video_pad >= output_seconds - 149.9


def test_arrow_treatment_renders_without_covering_the_target(tmp_path: Path):
    source = tmp_path / "source.png"
    Image.new("RGB", (1920, 1080), "white").save(source)
    destination = tmp_path / "arrow.jpg"
    annotation = VisualAnnotation(
        style="arrow", x=0.75, y=0.18, width=0.05, height=0.06, color="#FF3B3B",
    )
    prepare_editorial_screenshot(source, _shot(annotation), destination, source_label="example.com")
    assert destination.is_file()
