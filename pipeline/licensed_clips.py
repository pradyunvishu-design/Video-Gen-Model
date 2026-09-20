"""Rights-gated extraction of short, attributable YouTube source clips.

This module intentionally has no "fair use" or "transform it so it is ours"
switch. Automation cannot decide that. It accepts only material whose reuse
rights are machine-verifiable or backed by a local approval record.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, HttpUrl, model_validator

from .capture import _recording_quality, _safe_url, _sha256
from .config import FFMPEG_PRESET, FFMPEG_THREADS_PER_JOB, PROJECT_ROOT

RIGHTS_PROOF_ROOT = PROJECT_ROOT / "assets" / "rights"


class LicensedClipRequest(BaseModel):
    clip_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    source_id: str = ""
    url: HttpUrl
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    rights_basis: Literal["owned", "written_permission", "creative_commons", "public_domain"]
    rights_proof_file: str = ""
    rights_proof_url: str = ""
    approved_by: str = Field(min_length=2, max_length=120)
    attribution: str = Field(min_length=2, max_length=500)
    keep_audio: bool = False
    avoid_faces: bool = False

    @model_validator(mode="after")
    def validate_clip_contract(self) -> "LicensedClipRequest":
        duration = self.end_seconds - self.start_seconds
        if duration <= 0 or duration > 45:
            raise ValueError("licensed source clips must be between 0 and 45 seconds")
        host = (urlsplit(str(self.url)).hostname or "").casefold()
        if host not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
            raise ValueError("licensed clip ingestion currently supports YouTube URLs only")
        if self.rights_basis in {"owned", "written_permission"} and not self.rights_proof_file:
            raise ValueError("owned or permissioned footage requires a local rights_proof_file")
        if self.rights_basis == "public_domain" and not (self.rights_proof_file or self.rights_proof_url):
            raise ValueError("public-domain footage requires a proof file or authoritative proof URL")
        return self


def _proof_record(request: LicensedClipRequest) -> dict:
    proof: dict = {"proof_url": request.rights_proof_url}
    if request.rights_proof_file:
        path = Path(request.rights_proof_file).expanduser().resolve()
        root = RIGHTS_PROOF_ROOT.resolve()
        if not path.is_relative_to(root):
            raise PermissionError(f"rights proof files must be stored under {root}")
        if not path.is_file():
            raise PermissionError(f"rights proof file does not exist: {path}")
        proof.update({"proof_file": str(path), "proof_sha256": _sha256(path)})
    return proof


_SCREEN_FOCUS_TERMS = {
    "demo",
    "walkthrough",
    "interface",
    "ui",
    "screen",
    "terminal",
    "code",
    "repository",
    "api",
    "release",
    "launch",
    "keynote",
}
_TALKING_HEAD_TERMS = {
    "interview",
    "podcast",
    "talk",
    "speaker",
    "discuss",
    "discussion",
    "conversation",
    "qa",
    "fireside",
    "host",
}


def _metadata_text(metadata: dict) -> str:
    text = " ".join(
        str(item or "")
        for item in (
            metadata.get("title"),
            metadata.get("description"),
            metadata.get("channel"),
            metadata.get("uploader"),
            metadata.get("channel_id"),
        )
    )
    return text.casefold()


def _looks_like_speaker_focused(metadata: dict) -> bool:
    text = _metadata_text(metadata)
    return (
        any(term in text for term in _TALKING_HEAD_TERMS)
        and not any(term in text for term in _SCREEN_FOCUS_TERMS)
    )


def _video_dimensions(path: Path) -> tuple[int, int]:
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-of", "json", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", str(path),
    ], capture_output=True, text=True, check=True)
    payload = json.loads(probe.stdout or "{}")
    stream = payload.get("streams", [{}])[0]
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    return width, height


def _speaker_safe_crop_filter(path: Path, metadata: dict) -> str | None:
    width, height = _video_dimensions(path)
    if width <= 0 or height <= 0:
        return None

    target_ratio = 16 / 9
    source_ratio = width / height
    if math.isclose(source_ratio, target_ratio, rel_tol=1e-4, abs_tol=1e-4):
        # Slight vertical crop avoids forehead/face blocks while keeping most of
        # the full frame.
        crop_h = max(360, int(height * 0.90))
        crop_y = int((height - crop_h) * 0.33)
        return f"crop={width}:{crop_h}:0:{crop_y}"

    if source_ratio > target_ratio:
        crop_h = height
        crop_w = int(crop_h * target_ratio)
        if crop_w >= width:
            return None
        left_x = 0
        right_x = width - crop_w
        text = _metadata_text(metadata)
        selector = int(hashlib.sha256(
            f"{metadata.get('id', '')}:{metadata.get('webpage_url', '')}".encode("utf-8")
        ).hexdigest()[:8], 16)
        if "left" in text or selector % 2 == 0:
            crop_x = left_x
        else:
            crop_x = right_x
        return f"crop={crop_w}:{crop_h}:{crop_x}:0"

    # Portrait source: center on lower half to avoid presenter framing.
    crop_h = int(width / target_ratio)
    if crop_h >= height:
        return None
    crop_y = int((height - crop_h) * 0.40)
    return f"crop={width}:{crop_h}:0:{crop_y}"


def _build_video_filter(path: Path, metadata: dict, avoid_faces: bool) -> str:
    """Build a stable 1080p normalization chain with optional face-safe framing."""
    base_scale = "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos"
    pad = "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
    if not avoid_faces:
        return ",".join([base_scale, pad, "fps=30", "format=yuv420p"])

    crop = _speaker_safe_crop_filter(path, metadata)
    if crop is None:
        return ",".join([base_scale, pad, "fps=30", "format=yuv420p"])
    return ",".join([crop, base_scale, pad, "fps=30", "format=yuv420p"])


def _metadata(url: str) -> dict:
    _safe_url(url)
    process = subprocess.run([
        sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs",
        "--js-runtimes", "node",
        "--dump-single-json", "--skip-download", "--no-playlist", url,
    ], capture_output=True, text=True, timeout=180)
    if process.returncode:
        raise RuntimeError("yt-dlp metadata check failed: " + "\n".join(process.stderr.splitlines()[-8:]))
    return json.loads(process.stdout)


def _verify_rights(request: LicensedClipRequest, metadata: dict) -> dict:
    license_name = str(metadata.get("license") or "").strip()
    proof = _proof_record(request)
    if request.rights_basis == "creative_commons" and "creative commons" not in license_name.casefold():
        raise PermissionError(
            "YouTube metadata does not identify this video as Creative Commons; supply written permission instead"
        )
    if metadata.get("is_live"):
        raise PermissionError("live streams are not eligible for automatic licensed-clip ingestion")
    return {
        "basis": request.rights_basis,
        "approved_by": request.approved_by,
        "attribution": request.attribution,
        "youtube_license": license_name,
        "uploader": metadata.get("uploader") or metadata.get("channel") or "",
        "channel_id": metadata.get("channel_id") or "",
        "video_id": metadata.get("id") or "",
        **proof,
    }


def _download_section(request: LicensedClipRequest, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    template = str((directory / "source.%(ext)s").resolve())
    section = f"*{request.start_seconds:.3f}-{request.end_seconds:.3f}"
    process = subprocess.run([
        sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs",
        "--js-runtimes", "node",
        "--no-playlist", "--no-overwrites",
        "--download-sections", section, "--force-keyframes-at-cuts",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]", "--merge-output-format", "mp4",
        "-o", template, str(request.url),
    ], capture_output=True, text=True, timeout=900)
    if process.returncode:
        # Some YouTube CDNs reject FFmpeg's range request even when yt-dlp can
        # fetch the same Creative-Commons file natively. For short sources,
        # download a bounded progressive MP4 and cut it locally. The 500 MB
        # cap prevents this compatibility path from pulling long source masters.
        full_template = str((directory / "full_source.%(ext)s").resolve())
        fallback = subprocess.run([
            sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs",
            "--js-runtimes", "node", "--no-playlist", "--no-overwrites",
            "--max-filesize", "500M", "-f", "b[ext=mp4][height<=1080]/b[height<=1080]",
            "-o", full_template, str(request.url),
        ], capture_output=True, text=True, timeout=900)
        if fallback.returncode:
            raise RuntimeError(
                "licensed section download failed: " + "\n".join(process.stderr.splitlines()[-6:])
                + "\nprogressive fallback failed: " + "\n".join(fallback.stderr.splitlines()[-6:])
            )
        full_candidates = [path for path in directory.glob("full_source.*") if path.suffix.lower() not in {".part", ".ytdl"}]
        if not full_candidates:
            raise RuntimeError("progressive fallback completed without a source file")
        full_source = max(full_candidates, key=lambda path: path.stat().st_size)
        section_source = directory / "source_section.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-ss", f"{request.start_seconds:.3f}", "-i", str(full_source),
            "-t", f"{request.end_seconds - request.start_seconds:.3f}", "-c", "copy", str(section_source),
        ], check=True, capture_output=True, text=True)
        return section_source
    candidates = [path for path in directory.glob("source.*") if path.suffix.lower() not in {".json", ".part", ".ytdl"}]
    if not candidates:
        raise RuntimeError("yt-dlp completed without a source section")
    return max(candidates, key=lambda path: path.stat().st_size)


def ingest_licensed_clip(request: LicensedClipRequest, output_dir: Path) -> dict:
    """Verify rights, download only the approved section, normalize, and ledger it."""
    request_contract = request.model_dump(mode="json")
    request_hash = hashlib.sha256(
        json.dumps(request_contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    target = output_dir / request.clip_id
    ledger_path = target / "rights_ledger.json"
    if ledger_path.is_file():
        cached = json.loads(ledger_path.read_text(encoding="utf-8"))
        cached_output = Path(cached.get("output_path", ""))
        if cached.get("request_hash") != request_hash:
            raise ValueError("clip_id is already bound to a different source, time range, or rights contract")
        if cached_output.is_file() and cached.get("quality", {}).get("status") == "accepted":
            return {
                "clip": str(cached_output), "ledger": str(ledger_path), "rights": cached["rights"],
                "quality": cached["quality"], "output_sha256": cached["output_sha256"], "cached": True,
            }
    metadata = _metadata(str(request.url))
    rights = _verify_rights(request, metadata)
    source = _download_section(request, target / "download")
    final = target / "licensed_clip_1080p.mp4"
    duration = request.end_seconds - request.start_seconds
    avoid_faces = request.avoid_faces or _looks_like_speaker_focused(metadata)
    vf_chain = _build_video_filter(source, metadata, avoid_faces=avoid_faces)
    command = [
        "ffmpeg", "-y", "-i", str(source), "-t", f"{duration:.3f}",
        "-vf", vf_chain,
    ]
    if not request.keep_audio:
        command.append("-an")
    command.extend([
        "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", "14",
        "-threads", str(FFMPEG_THREADS_PER_JOB),
    ])
    if request.keep_audio:
        command.extend(["-c:a", "aac", "-b:a", "192k"])
    command.append(str(final))
    subprocess.run(command, check=True, capture_output=True, text=True)
    quality = _recording_quality(final, expected_seconds=duration)
    ledger = {
        "schema_version": 1,
        "request_hash": request_hash,
        "clip_id": request.clip_id,
        "source_url": str(request.url),
        "source_title": metadata.get("title") or "",
        "source_webpage_url": metadata.get("webpage_url") or str(request.url),
        "source_sha256": _sha256(source),
        "output_path": str(final),
        "output_sha256": _sha256(final),
        "start_seconds": request.start_seconds,
        "end_seconds": request.end_seconds,
        "audio_retained": request.keep_audio,
        "face_safe": avoid_faces,
        "rights": rights,
        "quality": quality,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "publication_review_required": True,
    }
    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "clip": str(final), "ledger": str(ledger_path), "rights": rights, "quality": quality,
        "output_sha256": ledger["output_sha256"],
    }
