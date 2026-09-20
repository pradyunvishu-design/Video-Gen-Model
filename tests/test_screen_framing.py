import json
import shutil
import subprocess

import pytest

from pipeline.capture import _recording_quality, _visual_frame_metrics
from pipeline import capture, product_demo
from pipeline.product_demo import DemoAction, _render_cinematic_demo, recording_window
from pipeline.screen_framing import focus_events, framing_filter


def event(start=1, end=4, x=0.7, y=0.3, kind="click"):
    return dict(start_seconds=start, end_seconds=end, x=x, y=y, kind=kind)


def test_hover_and_brief_clicks_do_not_create_camera_bounces():
    assert focus_events([event(kind="hover"), event(end=1.5)]) == []
    assert "zoompan" not in framing_filter([])


def test_nearby_actions_merge_but_overlapping_far_targets_do_not_jump():
    result = focus_events([event(), event(4.2, 6, .72), event(5, 7, .1)])
    assert len(result) == 1
    assert result[0]["end_seconds"] == 6


@pytest.mark.parametrize("change", [dict(x=float("nan")), dict(end=float("inf")), dict(start=-1), dict(x=1.1), dict(end=0)])
def test_untrusted_focus_values_rejected(change):
    with pytest.raises(ValueError):
        focus_events([event(**change)])


def test_unknown_demo_action_rejected():
    with pytest.raises(ValueError):
        DemoAction(kind="execute_shell")


def test_action_window_excludes_navigation_without_cutting_completed_actions():
    assert recording_window(17, 12) == (5, 12)
    with pytest.raises(ValueError, match="missing"):
        recording_window(5, 12)
    with pytest.raises(ValueError):
        recording_window(float("nan"), 12)


def test_camera_returns_to_overview_after_click_not_after_reading_hold(monkeypatch):
    class Locator:
        def count(self): return 1
        def scroll_into_view_if_needed(self, **kw): pass
        def bounding_box(self): return dict(x=100, y=100, width=100, height=40)
        def click(self, **kw): pass

    class Page:
        def locator(self, selector): return Locator()
        def evaluate(self, *args): pass
        def wait_for_timeout(self, milliseconds): pass

    clock = iter([100, 100.1, 101, 105])
    monkeypatch.setattr(product_demo.time, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(product_demo, "_move_cursor", lambda *a: None)
    result = product_demo._perform(Page(), DemoAction(kind="click", candidate_id="d001", duration_seconds=4),
                                   product_demo.DemoSpec(website="https://example.com", goal="Test target focus"), 2)
    assert result["start_seconds"] == 2.1
    assert result["end_seconds"] == 3.5  # Not 7.0, the end of the reading hold.


def test_capture_cache_preserves_qc_and_rejects_changed_video(tmp_path):
    import hashlib

    target = tmp_path / "recording.mp4"
    target.write_bytes(b"fixture")
    entry = dict(name=target.name, sha256=hashlib.sha256(b"fixture").hexdigest(),
                 quality=dict(status="accepted", readability_review_required=True))
    assert capture.CAPTURE_CACHE_VERSION > 3
    assert capture._recording_cache_valid([entry], tmp_path)
    assert not capture._recording_cache_valid([{**entry, "quality": {}}], tmp_path)
    assert not capture._recording_cache_valid([{**entry, "name": "../recording.mp4"}], tmp_path)
    target.write_bytes(b"changed")
    assert not capture._recording_cache_valid([entry], tmp_path)


def test_quality_rejects_truncated_recording(monkeypatch, tmp_path):
    payload = {"streams": [{"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "30/1"}],
               "format": {"duration": "2", "bit_rate": "1000000"}}
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: type("Result", (), {"stdout": json.dumps(payload)})())
    with pytest.raises(RuntimeError, match="too short"):
        _recording_quality(tmp_path / "short.mp4", expected_seconds=10)


def test_low_bitrate_does_not_reject_legitimate_still_ui(monkeypatch, tmp_path):
    payload = {"streams": [{"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "30/1"}],
               "format": {"duration": "10", "bit_rate": "100000"}}
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: type("Result", (), {"stdout": json.dumps(payload)})())
    report = _recording_quality(tmp_path / "static.mp4", expected_seconds=10)
    assert report["status"] == "accepted"
    assert report["readability_review_required"]
    assert "sharp_encode" not in report["checks"]


def test_visual_frame_metrics_reject_black_or_frozen_capture():
    frame_size = 16 * 9
    frames = bytes([0]) * frame_size * 4
    report = _visual_frame_metrics(frames, width=16, height=9)

    assert report["black_frame_ratio"] == 1
    assert report["frozen_pair_ratio"] == 1
    assert "capture is black" in report["failures"]
    assert "capture has no visible movement" in report["failures"]


def test_visual_frame_metrics_accept_deliberate_moving_content():
    width, height = 16, 9
    frames = []
    for offset in range(4):
        pixels = bytearray([30] * (width * height))
        for row in range(2, 6):
            for column in range(2 + offset, 6 + offset):
                pixels[row * width + column] = 230
        frames.append(bytes(pixels))
    report = _visual_frame_metrics(b"".join(frames), width=width, height=height)

    assert report["failures"] == []
    assert report["frozen_pair_ratio"] == 0
    assert report["edge_energy"] > 1


def test_public_capture_moves_visible_editorial_cursor_before_interaction():
    calls = []

    class Locator:
        def count(self): return 1
        def scroll_into_view_if_needed(self, **kw): pass
        def bounding_box(self): return {"x": 400, "y": 240, "width": 200, "height": 80}
        def hover(self, **kw): pass

    class Page:
        def locator(self, selector): return Locator()
        def evaluate(self, script, args=None): calls.append((script, args))
        def wait_for_timeout(self, milliseconds): pass

    capture._perform_motion(
        Page(),
        capture.CaptureAction(kind="hover", candidate_id="c001", duration_seconds=2),
    )

    scripts = "\n".join(script for script, _ in calls)
    assert "__ai_capture_cursor" in scripts
    assert "requestAnimationFrame" in scripts


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_local_recording_to_framed_export_happy_path(tmp_path):
    """Real local encode/probe, no API, login, paid service, or source media."""
    raw = tmp_path / "raw.mp4"
    final = tmp_path / "framed.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=3",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", str(raw),
    ], check=True, capture_output=True)
    _render_cinematic_demo(raw, final, [event(.15, 1.9)], recorded_seconds=2.2)
    report = _recording_quality(final, expected_seconds=2.2)
    assert (report["width"], report["height"]) == (1920, 1080)
    assert abs(report["duration_seconds"] - 2.2) <= 1 / 30
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(final), "-f", "null", "-"],
                   check=True, capture_output=True)
