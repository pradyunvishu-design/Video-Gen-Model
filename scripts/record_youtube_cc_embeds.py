from __future__ import annotations

import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "news_weekly_20260822" / "broll_api_manual"
RAW = OUT / "embed_raw"
FINAL = OUT / "embed_recordings_chrome"
FFMPEG = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\tools\ffmpeg\bin\ffmpeg.exe")

selections = [
    {"video_id": "V8lD0q29wAk", "scene_id": "computer_use", "start": 245, "source_url": "https://www.youtube.com/watch?v=V8lD0q29wAk"},
    {"video_id": "TZ6bvYydog4", "scene_id": "chatgpt_platform", "start": 5, "source_url": "https://www.youtube.com/watch?v=TZ6bvYydog4"},
    {"video_id": "7rxt2aDnejI", "scene_id": "open_models", "start": 45, "source_url": "https://www.youtube.com/watch?v=7rxt2aDnejI"},
    {"video_id": "gsN_CJJDy_o", "scene_id": "ports_pike", "start": 60, "source_url": "https://www.youtube.com/watch?v=gsN_CJJDy_o"},
]

RAW.mkdir(parents=True, exist_ok=True)
FINAL.mkdir(parents=True, exist_ok=True)
records = []

with sync_playwright() as p:
    # Use the installed Chrome build rather than Playwright's codec-limited
    # Chromium.  The context is still temporary: no user profile, cookies, or
    # credentials are loaded into the capture worker.
    browser = p.chromium.launch(
        channel="chrome",
        headless=True,
        args=[
            "--autoplay-policy=no-user-gesture-required",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    for item in selections:
        destination = FINAL / f"ytcc_{item['video_id']}.mp4"
        if destination.exists() and destination.stat().st_size > 500_000:
            records.append({**item, "clip": str(destination), "cached": True})
            continue
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(RAW), record_video_size={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = context.new_page()
        start = int(item["start"])
        embed = (
            f"https://www.youtube.com/embed/{item['video_id']}?autoplay=1&mute=1&controls=0"
            f"&modestbranding=1&rel=0&playsinline=1&start={start}"
        )
        # Navigating to the embed directly gives YouTube a normal HTTPS origin;
        # loading it in a data/about:blank iframe produces configuration errors.
        page.goto(embed, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(15000)
        raw_video = page.video
        context.close()
        raw_path = Path(raw_video.path())
        # Keep the final eight seconds after the player has loaded and settled.
        subprocess.run([
            str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-sseof", "-8", "-i", str(raw_path),
            "-t", "8", "-an", "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(destination),
        ], check=True)
        records.append({**item, "clip": str(destination), "cached": False})
    browser.close()

manifest = {
    "schema_version": 1,
    "method": "clean muted public YouTube embed recording",
    "rights_basis": "creative_commons verified by YouTube Data API",
    "publication_review_required": True,
    "clips": records,
}
(OUT / "embed_recordings_chrome_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({"recorded": len(records), "manifest": str(OUT / 'embed_recordings_chrome_manifest.json')}, indent=2))
