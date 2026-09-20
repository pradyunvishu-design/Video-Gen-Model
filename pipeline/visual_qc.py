"""Independent multimodal inspection for generated images and video keyframes."""
from __future__ import annotations

import base64
import json
import mimetypes
import statistics
import subprocess
from pathlib import Path

import requests
from PIL import Image, ImageFilter

from .config import OPENROUTER_API_KEY, OPENROUTER_VERIFY_MODEL, require

SCHEMA = {"type": "json_schema", "json_schema": {"name": "VisualQC", "strict": True, "schema": {
    "type": "object", "additionalProperties": False,
    "required": ["passed", "subject_match", "unwanted_text", "severe_distortion", "notes"],
    "properties": {
        "passed": {"type": "boolean"}, "subject_match": {"type": "boolean"},
        "unwanted_text": {"type": "boolean"}, "severe_distortion": {"type": "boolean"},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
}}}

MOTION_SCHEMA = {"type": "json_schema", "json_schema": {"name": "MotionGraphicQC", "strict": True, "schema": {
    "type": "object", "additionalProperties": False,
    "required": [
        "passed", "subject_match", "unintended_text", "severe_distortion", "temporal_instability",
        "ai_art_aesthetic", "professional_motion_design", "realistic_motion_and_lighting", "notes",
    ],
    "properties": {
        "passed": {"type": "boolean"}, "subject_match": {"type": "boolean"},
        "unintended_text": {"type": "boolean"}, "severe_distortion": {"type": "boolean"},
        "temporal_instability": {"type": "boolean"}, "ai_art_aesthetic": {"type": "boolean"},
        "professional_motion_design": {"type": "boolean"},
        "realistic_motion_and_lighting": {"type": "boolean"},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
}}}

THUMBNAIL_BACKPLATE_SCHEMA = {"type": "json_schema", "json_schema": {
    "name": "ThumbnailBackplateQC", "strict": True, "schema": {
        "type": "object", "additionalProperties": False,
        "required": [
            "passed", "unwanted_text", "logos_or_ui", "people_or_faces", "generic_ai_aesthetic",
            "severe_distortion", "usable_negative_space", "professional_art_direction", "notes",
        ],
        "properties": {
            "passed": {"type": "boolean"}, "unwanted_text": {"type": "boolean"},
            "logos_or_ui": {"type": "boolean"}, "people_or_faces": {"type": "boolean"},
            "generic_ai_aesthetic": {"type": "boolean"}, "severe_distortion": {"type": "boolean"},
            "usable_negative_space": {"type": "boolean"}, "professional_art_direction": {"type": "boolean"},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
    },
}}


def _frames(path: Path, count: int = 3) -> list[Path]:
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        return [path]
    frame_dir = path.parent / ".qc_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    pattern = frame_dir / f"{path.stem}_%02d.jpg"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(path), "-vf", f"fps={count}/8,scale=768:-2", "-frames:v", str(count), str(pattern)
    ], capture_output=True, check=True)
    return sorted(frame_dir.glob(f"{path.stem}_*.jpg"))[:count]


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def inspect(path: Path, expected_subject: str) -> dict:
    images = _frames(path)
    content = [{"type": "text", "text": (
        "Inspect these generated-media frames for a professional AI-news video. Expected subject: "
        f"{expected_subject}. Fail only for a materially wrong subject, unintended readable text/logo/watermark, "
        "or severe anatomy/geometry distortion visible during normal playback."
    )}]
    content.extend({"type": "image_url", "image_url": {"url": _data_url(frame)}} for frame in images)
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {require(OPENROUTER_API_KEY, 'OPENROUTER_API_KEY')}", "Content-Type": "application/json"},
        json={
            "model": OPENROUTER_VERIFY_MODEL, "temperature": 0.1,
            "messages": [{"role": "system", "content": "You are a strict visual continuity and artifact inspector."},
                         {"role": "user", "content": content}],
            "response_format": SCHEMA,
        }, timeout=300,
    )
    response.raise_for_status()
    result = json.loads(response.json()["choices"][0]["message"]["content"])
    result["passed"] = bool(
        result["passed"] and result["subject_match"] and not result["unwanted_text"] and not result["severe_distortion"]
    )
    return result


def inspect_thumbnail_backplate(path: Path, expected_layout: str) -> dict:
    """Reject generated plates that would make a thumbnail look synthetic or contaminated."""
    content = [
        {"type": "text", "text": (
            "Inspect this generated BACKGROUND PLATE for an original, faceless technology-news thumbnail. "
            f"Expected layout: {expected_layout}. The final editor will add all real screenshots, exact official logos, "
            "mascots, arrows, and headline typography later. Reject any readable or pseudo-readable text, numbers, "
            "logos, product UI, people, faces, hands, watermarks, fake screens, malformed geometry, obvious generative "
            "artifacts, glossy generic AI imagery, neon sci-fi styling, gears, circuitry, portals, glowing orbs, or a "
            "composition without a clean usable headline/identity area. Require believable materials, physically coherent "
            "shadows, restrained color, and deliberate professional art direction. Return only the schema."
        )},
        {"type": "image_url", "image_url": {"url": _data_url(path)}},
    ]
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {require(OPENROUTER_API_KEY, 'OPENROUTER_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENROUTER_VERIFY_MODEL,
            "temperature": 0.05,
            "messages": [
                {"role": "system", "content": "You are a strict senior YouTube thumbnail art director and generative-artifact inspector."},
                {"role": "user", "content": content},
            ],
            "response_format": THUMBNAIL_BACKPLATE_SCHEMA,
        },
        timeout=300,
    )
    response.raise_for_status()
    result = json.loads(response.json()["choices"][0]["message"]["content"])
    result["passed"] = bool(
        result["passed"] and result["usable_negative_space"] and result["professional_art_direction"]
        and not result["unwanted_text"] and not result["logos_or_ui"] and not result["people_or_faces"]
        and not result["generic_ai_aesthetic"] and not result["severe_distortion"]
    )
    return result


def inspect_identity_arena_backplate(path: Path, expected_layout: str) -> dict:
    """Review a generated mascot plate without rejecting the requested mascot concept."""
    content = [
        {"type": "text", "text": (
            "Inspect this generated IDENTITY-ARENA PLATE for a premium original technology-news thumbnail. "
            f"Expected layout: {expected_layout}. The requested subjects are one to four stylized, faceless, "
            "soft-vinyl or painted-resin mascot bodies with large blank, flat, front-facing square display heads. "
            "Those mascot bodies and their simple mitten-like arms are intentional and MUST NOT be classified as "
            "people, faces, hands, generic robots, or an automatic generic-AI failure. The editor will composite "
            "exact official logos onto the blank panels and add the headline later. Reject real people, facial "
            "features, skin, anatomy, armor, weapons, extra characters, duplicate limbs, malformed hands, readable "
            "or pseudo-readable text, logos, brand marks, UI, watermarks, fake screens, unstable geometry, clutter, "
            "plastic-looking low-detail CGI, neon sci-fi styling, or weak hierarchy. Require the exact requested "
            "character count, unobstructed blank display panels, clean headline negative space, believable floor "
            "contact, coherent product-photography lighting, tactile materials, crisp edges, and deliberate campaign "
            "art direction. A polished physical mascot photograph is acceptable; reject only when it looks like "
            "generic prompt output rather than a professionally art-directed miniature set. Return only the schema."
        )},
        {"type": "image_url", "image_url": {"url": _data_url(path)}},
    ]
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {require(OPENROUTER_API_KEY, 'OPENROUTER_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENROUTER_VERIFY_MODEL,
            "temperature": 0.05,
            "messages": [
                {"role": "system", "content": (
                    "You are a strict senior YouTube thumbnail art director. Judge the supplied image against its "
                    "declared identity-arena art direction, not against a neutral-background contract."
                )},
                {"role": "user", "content": content},
            ],
            "response_format": THUMBNAIL_BACKPLATE_SCHEMA,
        },
        timeout=300,
    )
    response.raise_for_status()
    result = json.loads(response.json()["choices"][0]["message"]["content"])
    result["passed"] = bool(
        result["passed"] and result["usable_negative_space"] and result["professional_art_direction"]
        and not result["unwanted_text"] and not result["logos_or_ui"] and not result["people_or_faces"]
        and not result["generic_ai_aesthetic"] and not result["severe_distortion"]
    )
    return result


def inspect_motion(path: Path, expected_subject: str) -> dict:
    """Reject AI-looking motion, even when individual frames seem superficially clean."""
    images = _frames(path, count=6)
    content = [{"type": "text", "text": (
        "Inspect this Magic Hour clip as a sequence for a premium editorial YouTube video. Expected idea: "
        f"{expected_subject}. It must look like deliberate professional motion design, not an AI-generated picture "
        "being moved. Fail for dreamy cinematic AI-art, surreal symbolism, fake interfaces, glowing sci-fi brains, "
        "stock-photo people, malformed details, invented text, unstable geometry, morphing, melting, flicker, object "
        "duplication, implausible physics, or camera shake. Motion and lighting must feel physically coherent and "
        "the supplied clean geometric design must remain recognizable across the sequence."
    )}]
    content.extend({"type": "image_url", "image_url": {"url": _data_url(frame)}} for frame in images)
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {require(OPENROUTER_API_KEY, 'OPENROUTER_API_KEY')}", "Content-Type": "application/json"},
        json={
            "model": OPENROUTER_VERIFY_MODEL, "temperature": 0.05,
            "messages": [
                {"role": "system", "content": "You are a strict broadcast motion-design and generative-artifact inspector."},
                {"role": "user", "content": content},
            ],
            "response_format": MOTION_SCHEMA,
        }, timeout=300,
    )
    response.raise_for_status()
    result = json.loads(response.json()["choices"][0]["message"]["content"])
    result["passed"] = bool(
        result["passed"] and result["subject_match"] and result["professional_motion_design"]
        and result["realistic_motion_and_lighting"] and not result["unintended_text"]
        and not result["severe_distortion"] and not result["temporal_instability"]
        and not result["ai_art_aesthetic"]
    )
    return result


def frame_near_black_ratio(path: Path, threshold: int = 40) -> float:
    """Return the fraction of pixels whose RGB channels are all near black."""
    image = Image.open(path).convert("RGB")
    pixels = image.getdata()
    near_black = sum(1 for red, green, blue in pixels if max(red, green, blue) <= threshold)
    return near_black / max(1, image.width * image.height)


def frame_dark_structure(path: Path, *, edge_threshold: int = 12, light_threshold: int = 80) -> dict[str, float]:
    """Measure readable structure without penalizing an intentionally near-black canvas."""
    image = Image.open(path).convert("L")
    if image.width > 2 and image.height > 2:
        image = image.crop((1, 1, image.width - 1, image.height - 1))
    edges = image.filter(ImageFilter.FIND_EDGES)
    edge_ratio = sum(1 for value in edges.getdata() if value >= edge_threshold) / max(1, image.width * image.height)
    light_ratio = sum(1 for value in image.getdata() if value >= light_threshold) / max(1, image.width * image.height)
    return {"edge_ratio": edge_ratio, "readable_light_ratio": light_ratio}


def inspect_dark_editorial_structure(
    path: Path, *, ffmpeg: Path | str = "ffmpeg", min_p10_edge_ratio: float = 0.015,
    min_mean_light_ratio: float = 0.05, max_unstructured_frames: int = 0,
) -> dict:
    """Fail only on genuinely empty dark frames, not on a deliberate black editorial field."""
    frame_dir = path.parent / ".structure_frames" / path.stem
    frame_dir.mkdir(parents=True, exist_ok=True)
    pattern = frame_dir / "frame_%04d.png"
    subprocess.run([
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-vf", "fps=1,scale=320:180", str(pattern),
    ], capture_output=True, text=True, check=True)
    frames = sorted(frame_dir.glob("frame_*.png"))
    if not frames:
        raise RuntimeError("dark-editorial structure sampling produced no frames")
    metrics = [frame_dark_structure(frame) for frame in frames]
    edges = [item["edge_ratio"] for item in metrics]
    lights = [item["readable_light_ratio"] for item in metrics]
    p10_edge = sorted(edges)[max(0, int(len(edges) * 0.10) - 1)]
    unstructured = [
        index for index, item in enumerate(metrics)
        if item["edge_ratio"] < 0.002 and item["readable_light_ratio"] < 0.001
    ]
    mean_light = statistics.fmean(lights)
    passed = bool(
        p10_edge >= min_p10_edge_ratio and mean_light >= min_mean_light_ratio
        and len(unstructured) <= max_unstructured_frames
    )
    return {
        "passed": passed, "sample_count": len(frames), "p10_edge_ratio": round(p10_edge, 4),
        "mean_edge_ratio": round(statistics.fmean(edges), 4),
        "mean_readable_light_ratio": round(mean_light, 4),
        "minimum_edge_ratio": round(min(edges), 4),
        "minimum_readable_light_ratio": round(min(lights), 4),
        "unstructured_frames": unstructured,
        "limits": {
            "min_p10_edge_ratio": min_p10_edge_ratio,
            "min_mean_light_ratio": min_mean_light_ratio,
            "max_unstructured_frames": max_unstructured_frames,
        },
    }


def inspect_black_space_occupancy(
    path: Path, *, ffmpeg: Path | str = "ffmpeg", threshold: int = 40,
    max_mean_ratio: float = 0.35, max_median_ratio: float = 0.35,
    max_frames_over_eighty_percent: int = 0,
) -> dict:
    """Sample a video at 1 fps and fail when the usable frame is mostly near black."""
    frame_dir = path.parent / ".occupancy_frames" / path.stem
    frame_dir.mkdir(parents=True, exist_ok=True)
    pattern = frame_dir / "frame_%04d.png"
    subprocess.run([
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-vf", "fps=1,scale=320:180", str(pattern),
    ], capture_output=True, text=True, check=True)
    frames = sorted(frame_dir.glob("frame_*.png"))
    if not frames:
        raise RuntimeError("black-space occupancy sampling produced no frames")
    ratios = [frame_near_black_ratio(frame, threshold=threshold) for frame in frames]
    mean_ratio = statistics.fmean(ratios)
    median_ratio = statistics.median(ratios)
    over_eighty = [index for index, ratio in enumerate(ratios) if ratio > 0.80]
    worst_index = max(range(len(ratios)), key=ratios.__getitem__)
    passed = bool(
        mean_ratio <= max_mean_ratio and median_ratio <= max_median_ratio
        and len(over_eighty) <= max_frames_over_eighty_percent
    )
    return {
        "passed": passed, "sample_count": len(ratios), "near_black_threshold": threshold,
        "mean_near_black_ratio": round(mean_ratio, 4),
        "median_near_black_ratio": round(median_ratio, 4),
        "frames_over_eighty_percent": len(over_eighty),
        "worst_frame_second": worst_index,
        "worst_frame_ratio": round(ratios[worst_index], 4),
        "limits": {
            "max_mean_ratio": max_mean_ratio, "max_median_ratio": max_median_ratio,
            "max_frames_over_eighty_percent": max_frames_over_eighty_percent,
        },
    }
