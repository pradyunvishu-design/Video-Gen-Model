"""Thin client for the Magic Hour API (async job model: submit -> poll -> download)."""
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import IMAGE_MODEL, MAGIC_HOUR_API_KEY, VIDEO_MODEL, require

BASE = "https://api.magichour.ai"
SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=4,
    backoff_factor=1,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"GET", "HEAD", "PUT"}),
    respect_retry_after_header=True,
)))


def _headers():
    key = require(MAGIC_HOUR_API_KEY, "MAGIC_HOUR_API_KEY")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _post(path: str, payload: dict) -> dict:
    r = requests.post(f"{BASE}{path}", json=payload, headers=_headers(), timeout=60)
    if r.status_code == 402:
        raise SystemExit("Magic Hour: insufficient credits (402). Top up the account.")
    if r.status_code >= 400:
        try:
            detail = r.json()
        except ValueError:
            detail = {"message": r.text[:500]}
        raise RuntimeError(f"Magic Hour {path} returned {r.status_code}: {detail}")
    r.raise_for_status()
    return r.json()


def upload_file(local_path: str, asset_type: str) -> str:
    """Upload a local file, return the file_path usable in other API calls."""
    p = Path(local_path)
    ext = p.suffix.lstrip(".").lower()
    resp = _post("/v1/files/upload-urls", {"items": [{"type": asset_type, "extension": ext}]})
    item = resp["items"][0]
    with open(p, "rb") as f:
        put = SESSION.put(item["upload_url"], data=f, timeout=300)
    put.raise_for_status()
    return item["file_path"]


def voice_clone(text: str, sample_file_path: str, name: str) -> str:
    """Generate speech in the cloned voice. Returns project id. Text must be <=1000 chars."""
    if len(text) > 1000:
        raise ValueError("Magic Hour voice text exceeds the verified 1000-character limit")
    resp = _post("/v1/ai-voice-cloner", {
        "name": name,
        "assets": {"audio_file_path": sample_file_path},
        "style": {"prompt": text},
    })
    return resp["id"]


def voice_generate(text: str, voice_name: str, name: str) -> str:
    if len(text) > 1000:
        raise ValueError("Magic Hour voice text exceeds the verified 1000-character limit")
    resp = _post("/v1/ai-voice-generator", {
        "name": name,
        "style": {"prompt": text, "voice_name": voice_name},
    })
    return resp["id"]


def image_generate(
    prompt: str, name: str, aspect_ratio: str = "16:9", resolution: str = "2k",
    model: str | None = None, image_count: int = 1,
) -> dict:
    selected_model = model or IMAGE_MODEL
    allowed_models = {
        "default", "flux-schnell", "z-image-turbo", "seedream-v4", "nano-banana",
        "nano-banana-2", "nano-banana-pro", "gpt-image-2",
    }
    if selected_model not in allowed_models:
        raise ValueError(f"unsupported Magic Hour image model: {selected_model}")
    if aspect_ratio not in {"1:1", "16:9", "9:16"}:
        raise ValueError(f"unsupported Magic Hour image aspect ratio: {aspect_ratio}")
    if resolution not in {"640px", "1k", "2k", "4k"}:
        raise ValueError(f"unsupported Magic Hour image resolution: {resolution}")
    if not 1 <= image_count <= 16:
        raise ValueError("Magic Hour image_count must be between 1 and 16")
    if selected_model in {"nano-banana-2", "nano-banana-pro"} and image_count not in {1, 4, 9, 16}:
        raise ValueError(f"{selected_model} image_count must be one of 1, 4, 9, or 16")
    return _post("/v1/ai-image-generator", {
        "name": name,
        "image_count": image_count,
        "model": selected_model,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "style": {"prompt": prompt},
    })


def image_to_video(
    image_file_path: str, prompt: str, name: str, duration: float = 8,
    model: str | None = None, resolution: str = "1080p",
    end_image_file_path: str | None = None,
) -> dict:
    assets = {"image_file_path": image_file_path}
    if end_image_file_path:
        assets["end_image_file_path"] = end_image_file_path
    return _post("/v1/image-to-video", {
        "name": name, "end_seconds": duration, "model": model or VIDEO_MODEL,
        "resolution": resolution, "audio": False, "style": {"prompt": prompt},
        "assets": assets,
    })


def auto_subtitle(video_file_path: str, duration: float, name: str) -> dict:
    return _post("/v1/auto-subtitle-generator", {
        "name": name, "start_seconds": 0, "end_seconds": duration,
        "assets": {"video_file_path": video_file_path},
        "style": {"template": "karaoke", "custom_config": {
            "font": "Noto Sans", "font_size": 64, "font_style": "bold",
            "text_color": "#C8CEC9", "highlighted_text_color": "#FFFFFF",
            "stroke_color": "#000000", "stroke_width": 3,
            "vertical_position": "bottom", "horizontal_position": "center",
        }},
    })


def _wait(path: str, project_id: str, timeout_s: int = 600) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = SESSION.get(f"{BASE}{path}/{project_id}", headers=_headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
        status = data.get("status")
        if status == "complete":
            return data
        if status in ("error", "canceled"):
            raise RuntimeError(f"Magic Hour job {project_id} {status}: {data.get('error')}")
        time.sleep(5)
    raise TimeoutError(f"Magic Hour job {project_id} did not finish in {timeout_s}s")


def wait_audio(project_id: str) -> dict:
    return _wait("/v1/audio-projects", project_id)


def wait_image(project_id: str) -> dict:
    return _wait("/v1/image-projects", project_id)


def wait_video(project_id: str) -> dict:
    return _wait("/v1/video-projects", project_id, timeout_s=1800)


def download_all(job: dict, directory: Path, stem: str) -> list[Path]:
    paths = []
    for index, item in enumerate(job.get("downloads", [])):
        url = item["url"]
        suffix = Path(url.split("?", 1)[0]).suffix or ".bin"
        dest = directory / f"{stem}_{index}{suffix}"
        r = SESSION.get(url, timeout=300)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        paths.append(dest)
    if not paths:
        raise RuntimeError(f"Magic Hour job {job.get('id')} returned no downloads")
    return paths


def download(job: dict, dest: Path) -> Path:
    url = job["downloads"][0]["url"]
    r = SESSION.get(url, timeout=300)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return dest
