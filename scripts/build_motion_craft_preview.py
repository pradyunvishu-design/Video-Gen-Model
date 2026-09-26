"""Stage the original motion practice composition for private HyperFrames review.

The unlicensed pinned framework is linked locally, never copied or exported.
No provider calls, full source videos, publishing, or final render are performed.
"""
from __future__ import annotations
import argparse
import base64
import json
import hashlib
import shutil
import subprocess
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
GSAP_SHA256 = "c174bfce53a729418d57a8ad8625e7247c793a22fef8e2851e3cfa3de9cd8280"


def build(root: Path, output: Path) -> Path:
    framework = root / "external/recreate-video/framework"
    if not (framework / "ui/draw.js").is_file():
        raise FileNotFoundError("Pinned recreate-video dependency is missing; private evaluation only")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "remotion/hyperframes/motion_craft_v2/index.html", output / "index.html")
    assets = output / "assets"
    assets.mkdir(exist_ok=True)
    runtime = assets / "gsap.min.js"
    if not runtime.is_file():
        response = requests.get("https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js", timeout=30)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != GSAP_SHA256:
            raise ValueError("GSAP 3.14.2 integrity mismatch; runtime not installed")
        runtime.write_bytes(response.content)
    if hashlib.sha256(runtime.read_bytes()).hexdigest() != GSAP_SHA256:
        raise ValueError("Cached GSAP integrity mismatch; restore the pinned runtime")
    linked = output / "framework"
    if linked.exists():
        if linked.resolve() != framework.resolve():
            raise ValueError("Existing framework path is not the pinned private dependency")
    else:
        # Escape literal paths; never pass filesystem actions across shells.
        literal_link = str(linked).replace("'", "''")
        literal_target = str(framework.resolve()).replace("'", "''")
        command = f"$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path '{literal_link}' -Target '{literal_target}' | Out-Null"
        encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
        subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded], check=True)
    (output / "hyperframes.json").write_text(json.dumps({"version": 1, "name": output.name,
        "width": 1920, "height": 1080, "fps": 30, "entry": "index.html"}, indent=2))
    (output / "review_status.json").write_text(json.dumps({
        "status": "awaiting_preview_review", "private_evaluation_only": True,
        "final_render_approved": False, "fidelity_score": None,
        "provider_spend_usd": 0, "magic_hour_credits": 0,
        "note": "Original explanatory diagrams, not product UI or a 99 percent fidelity result."
    }, indent=2))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data/motion_expert_runs/craft_v2/preview")
    args = parser.parse_args()
    print(build(ROOT, args.output))
