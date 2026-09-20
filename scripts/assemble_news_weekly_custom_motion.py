from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "news_weekly_20260822"
CACHE = OUT / "render_cache_engaging_mix_v2"
MOTION = OUT / "custom_motion_v3"
FFMPEG = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\tools\ffmpeg\bin\ffmpeg.exe")
FINAL = OUT / "the_week_in_ai_2026-08-22_10min_custom_motion_v3.mp4"
NARRATION = OUT / "audio" / "narration_master.m4a"
CAPTIONS = OUT / "captions_monochrome.ass"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    base_ledger = json.loads((OUT / "shot_ledger.json").read_text(encoding="utf-8"))
    motion_payload = json.loads((MOTION / "motion_manifest.json").read_text(encoding="utf-8"))["slots"]
    motion_by_slot = {int(slot): Path(path) for slot, path in motion_payload.items()}
    timeline = []
    revised_ledger = []
    for record in base_ledger:
        slot = int(record["slot"])
        source = motion_by_slot.get(slot, Path(record["file"]))
        if not source.exists() or source.stat().st_size < 60_000:
            raise FileNotFoundError(source)
        timeline.append(source.resolve())
        revised = dict(record)
        if slot in motion_by_slot:
            revised.update({"kind": "custom_explainer_motion", "source": str(source), "file": str(source)})
        revised_ledger.append(revised)

    concat = MOTION / "timeline.concat.txt"
    concat.write_text("".join(f"file '{path.as_posix()}'\n" for path in timeline), encoding="utf-8")
    visuals = MOTION / "visuals_600s.mp4"
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat), "-c", "copy", "-t", "600", str(visuals)], check=True)
    ass_path = str(CAPTIONS.resolve()).replace("\\", "/").replace(":", "\\:")
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-i", str(visuals), "-i", str(NARRATION),
                    "-vf", f"ass='{ass_path}'", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-t", "600", "-movflags", "+faststart", str(FINAL)], check=True)
    manifest = {
        "final": str(FINAL), "sha256": sha256(FINAL), "duration_seconds": 600,
        "resolution": "1920x1080", "fps": 30, "publishing_enabled": False,
        "custom_motion_shots": len(motion_by_slot),
        "motion_policy": "Narration-routed custom mechanisms; no repeated slideshow cards or decorative camera motion.",
        "shot_ledger": revised_ledger,
    }
    (MOTION / "render_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "shot_ledger"}, indent=2))


if __name__ == "__main__":
    main()
