"""Render the reusable, locked-camera MiniMax H3 motion-graphics pack."""
from __future__ import annotations

import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline.config import LOCAL_FFMPEG_BIN, PROJECT_ROOT


RUN_DIR = PROJECT_ROOT / "output" / "minimax_h3_10m"
EPISODE_PATH = PROJECT_ROOT / "remotion" / "public" / "episode" / "h3-10m" / "episode.json"
REMOTION_DIR = PROJECT_ROOT / "remotion"
PACK_DIR = RUN_DIR / "motion_pack"
FFMPEG = str(LOCAL_FFMPEG_BIN / "ffmpeg.exe")
REMOTION = REMOTION_DIR / "node_modules" / ".bin" / "remotion.cmd"
SCENE_SECONDS = 5


KIND_BY_PURPOSE = {
    "hook": "title",
    "what_it_is": "ladder",
    "native_audio": "workflow",
    "open_release": "checklist",
    "comfyui": "workflow",
    "hardware": "metric",
    "quality": "checklist",
    "sample_limits": "checklist",
    "resolution": "boundary",
    "not_fully_local": "boundary",
    "community": "ladder",
    "workflow": "workflow",
    "creator_test": "workflow",
    "who_for": "ladder",
    "why_now": "workflow",
    "decision": "boundary",
    "verdict": "title",
}

ITEMS_BY_PURPOSE = {
    "hook": ["OPEN WEIGHTS · NATIVE AUDIO · COMFYUI DAY ZERO"],
    "what_it_is": ["4–15 SECOND CLIPS", "UP TO 12 REFERENCES", "24 FPS OUTPUT"],
    "native_audio": ["PROMPT", "VIDEO + AUDIO", "ONE GENERATION"],
    "open_release": ["DOWNLOAD", "FINE-TUNE", "BUILD AROUND IT"],
    "comfyui": ["TEXT", "KEYFRAMES", "REFERENCES"],
    "hardware": ["123.6 GB", "66% LESS", "42.5 GB"],
    "quality": ["SUBJECT DETAIL", "LIGHTING DIRECTION", "SCENE LAYOUT"],
    "sample_limits": ["VISIBLE RESULT", "PICKED DEMOS", "UNKNOWN FAILURE RATE"],
    "resolution": ["768P BASE", "HOSTED 2K REGEN", "PICK BY THE JOB"],
    "not_fully_local": ["LOCAL WEIGHTS", "HOSTED HELPERS", "HYBRID SYSTEM"],
    "community": ["KEYFRAMES", "PREVIEWS", "LoRAs"],
    "workflow": ["PREVIEW LOW", "LOCK REFERENCES", "FINISH HIGH"],
    "creator_test": ["ONE SUBJECT", "ONE MOVE", "ONE SOUND CUE"],
    "who_for": ["BUILDERS", "STUDIOS", "RESEARCHERS"],
    "why_now": ["MODEL", "TOOLS", "INFRASTRUCTURE"],
    "decision": ["LOCAL CONTROL", "HOSTED SPEED", "CHOOSE PER SHOT"],
    "verdict": ["POWERFUL OPEN BASE · HYBRID FINISHING SYSTEM"],
}


def run(command: list[str], *, cwd: Path | None = None) -> None:
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if process.returncode:
        tail = "\n".join((process.stdout + "\n" + process.stderr).splitlines()[-30:])
        raise RuntimeError(f"command failed: {' '.join(command[:12])}\n{tail}")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


def main() -> None:
    if not REMOTION.is_file():
        raise FileNotFoundError(f"Remotion executable not found: {REMOTION}")
    episode = json.loads(EPISODE_PATH.read_text(encoding="utf-8"))
    first_by_purpose: dict[str, dict] = {}
    for beat in episode["beats"]:
        first_by_purpose.setdefault(beat["purpose"], beat)

    scenes = []
    for purpose, beat in first_by_purpose.items():
        scenes.append({
            "id": purpose,
            "kind": KIND_BY_PURPOSE.get(purpose, "checklist"),
            "kicker": f"MINIMAX H3 · {purpose.replace('_', ' ').upper()}",
            "title": beat["overlay"],
            "footer": beat["accent"],
            "items": ITEMS_BY_PURPOSE.get(purpose, ["WHAT SHIPPED", "WHAT WORKS", "WHAT REMAINS"]),
        })

    source_files = [
        PROJECT_ROOT / "remotion" / "src" / "episode" / "H3MotionGraphic.tsx",
        PROJECT_ROOT / "remotion" / "src" / "Composition.tsx",
    ]
    payload = {
        "version": 2,
        "scenes": scenes,
        "source_mtimes": {str(path): path.stat().st_mtime_ns for path in source_files},
    }
    key = digest(payload)
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    props_path = PACK_DIR / f"props_{key}.json"
    pack_path = PACK_DIR / f"h3_motion_pack_{key}.mp4"
    props_path.write_text(json.dumps({"scenes": scenes}, indent=2), encoding="utf-8")

    if not pack_path.is_file() or pack_path.stat().st_size < 500_000:
        run([
            str(REMOTION), "render", "src/index.ts", "MiniMaxH3MotionPack1080", str(pack_path),
            f"--props={props_path}", "--codec=h264", "--crf=16", "--pixel-format=yuv420p",
            "--color-space=bt709", "--image-format=png", "--concurrency=6",
        ], cwd=REMOTION_DIR)

    def split(index_scene: tuple[int, dict]) -> tuple[str, str]:
        index, scene = index_scene
        destination = PACK_DIR / f"{index:02d}_{scene['id']}_{key}.mp4"
        if not destination.is_file() or destination.stat().st_size < 100_000:
            run([
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-ss", str(index * SCENE_SECONDS),
                "-i", str(pack_path), "-t", str(SCENE_SECONDS), "-an", "-c:v", "libx264",
                "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(destination),
            ])
        return scene["id"], str(destination.resolve())

    with ThreadPoolExecutor(max_workers=5) as executor:
        rendered = dict(executor.map(split, enumerate(scenes)))

    manifest = {
        "version": "h3-locked-camera-motion-v2",
        "pack": str(pack_path.resolve()),
        "scene_seconds": SCENE_SECONDS,
        "clips": rendered,
        "camera_motion": "locked",
        "publishing_enabled": False,
    }
    manifest_path = PACK_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
