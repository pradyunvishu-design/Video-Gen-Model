"""Create a local-only browser capture canary; no accounts or provider calls.

python -m scripts.preview_screen_framing --output output/screen_framing_preview
Requires installed Google Chrome and FFmpeg. Output is a synthetic test UI, not
footage of a real product or a replacement for human episode review.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from pipeline.capture import _recording_quality
from pipeline.product_demo import DemoAction, DemoSpec, _install_overlays, _perform, _render_cinematic_demo


HTML = """<!doctype html><html><head><style>
*{box-sizing:border-box}body{margin:0;background:#eceeea;color:#182722;font:26px Arial,sans-serif}
main{margin:100px auto;width:1420px}h1{font-size:64px;letter-spacing:-2px;margin-bottom:20px}
p{max-width:1000px;line-height:1.5;color:#42514b}button{font:28px Arial;padding:22px 36px;
background:#204b40;color:white;border:0;border-radius:8px;cursor:pointer;margin:24px 0}
section{background:white;border:1px solid #cbd5ce;border-radius:10px;padding:40px;margin-top:28px}
#result{font-size:38px;min-height:150px}small{font-size:20px;color:#526359}
</style></head><body><main><small>LOCAL RECORDING TEST / NOT PRODUCT FOOTAGE</small>
<h1>Show the action. Let the result land.</h1>
<p>A deliberate click, one gentle focus move, and enough time to read the outcome.
No account, AI generation, source download, or cloud upload.</p>
<button data-demo-id="d001" onclick="document.querySelector('#result').innerText='Export ready: 1920 × 1080 · 30 fps';this.innerText='Preview complete'">Preview result</button>
<section id="result">Waiting for the demonstration click.</section>
</main></body></html>"""


def preview(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    final = output / "screen_framing_preview_1080p.mp4"
    if final.exists():
        raise FileExistsError("Choose a new output directory; the existing preview is preserved")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            context = browser.new_context(viewport={"width": 1920, "height": 1080},
                                          record_video_dir=str(output / "raw"),
                                          record_video_size={"width": 1920, "height": 1080})
            page = context.new_page()
            page.set_content(HTML)
            page.evaluate("document.fonts.ready")
            _install_overlays(page)
            page.wait_for_timeout(400)
            started = time.perf_counter()
            page.wait_for_timeout(800)
            event = _perform(page, DemoAction(kind="click", candidate_id="d001", duration_seconds=2.5),
                             DemoSpec(website="https://example.com", goal="Local fixture only"),
                             time.perf_counter() - started)
            page.wait_for_timeout(1200)
            recorded_seconds = time.perf_counter() - started
            video = page.video
            context.close()
            raw = Path(video.path())
        finally:
            browser.close()
    events = [event] if event else []
    _render_cinematic_demo(raw, final, events, recorded_seconds=recorded_seconds)
    subprocess.run(["ffmpeg", "-v", "error", "-ss", "3", "-i", str(final), "-frames:v", "1",
                    str(output / "poster.png")], check=True, capture_output=True)
    report = _recording_quality(final, expected_seconds=recorded_seconds)
    report.update(synthetic_test_ui=True, focus_events=events, source_audio=False,
                  human_visual_review="required", paid_calls=0)
    (output / "quality.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/screen_framing_preview"))
    args = parser.parse_args()
    print(preview(args.output))
