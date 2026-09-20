"""Native 1080p Remotion renderer for exact, editable motion-design shots."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from .config import (
    REMOTION_BROWSER_EXECUTABLE,
    REMOTION_DIR,
    REMOTION_RENDER_CONCURRENCY,
    REMOTION_RENDER_CRF,
    REMOTION_RENDER_ENABLED,
    REMOTION_RENDER_STRICT,
    FFMPEG_PRESET, VIDEO_H, VIDEO_W,
)
from .models import EpisodeProject, Shot
from .storyboard import motion_template_for


PURPOSE_KICKERS = {
    "hook": "SHOW THE RESULT FIRST",
    "show_intro": "THE WEEK IN TECH + AI",
    "headlines": "THE BIG STORIES",
    "story_intro": "WHY THIS ONE MATTERS",
    "orientation": "WHY THIS MATTERS",
    "context": "THE CONTEXT",
    "test_setup": "CONTROLLED TEST",
    "model_test": "HANDS-ON TEST",
    "observation": "WHAT THE OUTPUT SHOWS",
    "evidence": "SOURCE EVIDENCE",
    "analysis": "CONNECT THE EVIDENCE",
    "limitation": "THE IMPORTANT LIMIT",
    "comparison": "CLAIM VERSUS EVIDENCE",
    "transition": "THE NEXT QUESTION",
    "implication": "WHAT CHANGES NOW",
    "verdict": "THE DECISION",
    "weekly_recap": "THE WATCH LIST",
    "disclosure": "HOW THIS WAS MADE",
    "outro": "THE USEFUL TAKEAWAY",
}


def _short(text: str, max_words: int, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" .")
    words = cleaned.split()
    if len(words) > max_words:
        cleaned = " ".join(words[:max_words]).rstrip(".,;:") + "…"
    return cleaned[:max_chars].rstrip()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_video_frame(source: Path, destination: Path, seconds: float = 1.0) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-ss", f"{seconds:.3f}", "-i", str(source), "-frames:v", "1",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
        "-update", "1", str(destination),
    ], check=True, capture_output=True, text=True)
    return destination


def _source_image(project: EpisodeProject, shot: Shot, scratch: Path) -> Path | None:
    same_beat = [candidate for candidate in project.shots if candidate.beat_id == shot.beat_id]
    candidates = same_beat + [candidate for candidate in project.shots if candidate not in same_beat]
    for candidate in candidates:
        if not candidate.asset_path:
            continue
        path = Path(candidate.asset_path)
        if not path.is_file():
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            return path
        if path.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}:
            frame = scratch / f"{candidate.id}-reference.jpg"
            if not frame.exists():
                _extract_video_frame(path, frame, max(0.5, candidate.source_in_seconds + 0.75))
            return frame
    return None


def _stage_public_asset(source: Path | None) -> str:
    if source is None:
        return ""
    digest = _file_hash(source)[:20]
    suffix = source.suffix.lower() if source.suffix else ".png"
    runtime_dir = REMOTION_DIR / "public" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    destination = runtime_dir / f"{digest}{suffix}"
    if not destination.exists() or destination.stat().st_size != source.stat().st_size:
        # Several distinct 1080p motion cards can be rendered in parallel.
        # A unique temporary avoids one card overwriting another card's staged
        # source asset when they share the same background.
        temporary = destination.with_suffix(destination.suffix + f".{uuid.uuid4().hex}.tmp")
        shutil.copy2(source, temporary)
        temporary.replace(destination)
    return f"runtime/{destination.name}"


def _flow_labels(prompt: str) -> list[str]:
    terms = [
        _short(part, 4, 28).upper()
        for part in re.split(r"[,;:]|\bthen\b|\bto\b|\binto\b", prompt, flags=re.I)
        if part.strip()
    ]
    return (terms + ["EVIDENCE", "MEANING", "DECISION"])[:3]


def _orbit_labels(project: EpisodeProject, shot: Shot) -> list[str]:
    beat = next((item for item in project.script.beats if item.id == shot.beat_id), None) if project.script else None
    source_ids = beat.source_ids if beat else []
    values: list[str] = []
    for source in project.sources:
        if source_ids and source.id not in source_ids:
            continue
        if source.publisher:
            values.append(_short(source.publisher, 3, 24).upper())
        values.extend(_short(entity, 3, 24).upper() for entity in source.entities[:2])
    unique = list(dict.fromkeys(value for value in values if value))
    return (unique + ["SOURCE", "MODEL", "TOOL", "RESULT"])[:4]


def _metric(project: EpisodeProject, shot: Shot) -> str:
    beat = next((item for item in project.script.beats if item.id == shot.beat_id), None) if project.script else None
    for claim in project.claims:
        if beat and claim.id in beat.claim_ids and claim.kind == "number":
            match = re.search(r"\$?[\d,.]+(?:%|x|×|[KMB])?", claim.text, re.I)
            if match:
                return match.group(0)
    match = re.search(r"\$?[\d,.]+(?:%|x|×|[KMB])?", shot.prompt, re.I)
    return match.group(0) if match else "PROOF"


def _mascots_for(text: str, *, template: str) -> list[str]:
    normalized = text.lower()
    matches: list[str] = []
    families = (
        ("claude", ("claude", "anthropic")),
        ("codex", ("codex", "openai", "chatgpt", "gpt-")),
        ("gemini", ("gemini", "google", "deepmind")),
        ("open_source", ("open source", "comfyui", "stable diffusion", "hugging face", "github", "local model")),
    )
    for mascot, terms in families:
        if any(term in normalized for term in terms):
            matches.append(mascot)
    if template in {"news_intro", "orbit_map", "step_flow"}:
        matches.extend(["claude", "codex", "open_source"])
    return list(dict.fromkeys(matches or ["codex", "open_source"]))[:4]


def _chapter_tone(purpose: str) -> str:
    if purpose in {"limitation", "comparison"}:
        return "clay"
    if purpose in {"verdict", "weekly_recap", "outro"}:
        return "moss"
    return "ink"


def _cursor_for(annotation: dict | None, template: str) -> dict | None:
    if annotation is None or template not in {"ui_stage", "evidence_focus"}:
        return None
    target_x = max(0.04, min(0.94, annotation["x"] + annotation["width"] / 2))
    target_y = max(0.06, min(0.92, annotation["y"] + annotation["height"] / 2))
    return {
        "startX": max(0.08, target_x - 0.18),
        "startY": min(0.88, target_y + 0.16),
        "endX": target_x,
        "endY": target_y,
        "click": annotation["style"] in {"zoom", "arrow", "callout"},
    }


def build_props(project: EpisodeProject, shot: Shot, scratch: Path) -> dict:
    beat = next((item for item in project.script.beats if item.id == shot.beat_id), None) if project.script else None
    purpose = beat.purpose if beat else "analysis"
    motion_copy = (
        (project.editorial_plan.get("fidelity_visual_overrides") or {})
        .get("motion_copy", {})
        .get(shot.id, {})
    )
    template = str(
        motion_copy.get("template")
        or (shot.motion_template if shot.motion_template != "auto" else motion_template_for(shot.asset_type, purpose))
    )
    source = _source_image(project, shot, scratch)
    source_id = shot.source_id or (beat.source_ids[0] if beat and beat.source_ids else "")
    source_record = next((item for item in project.sources if item.id == source_id), None)
    source_label = "PRIMARY SOURCE"
    if source_record:
        source_label = source_record.publisher or urlsplit(str(source_record.url)).netloc.removeprefix("www.")
    prompt = shot.prompt or (beat.visual_direction if beat else "")
    title = str(motion_copy.get("title") or _short(prompt, 8, 86)).upper() or "THE EVIDENCE"
    body = str(motion_copy.get("body") or _short(beat.narration if beat else prompt, 28, 200))
    labels = list(motion_copy.get("labels") or [])
    if not labels:
        labels = (
            ["CLAIM", "EVIDENCE"]
            if template == "comparison"
            else _flow_labels(prompt)
            if template in {"step_flow", "timeline"}
            else _orbit_labels(project, shot)
        )
    if template == "news_intro":
        title = "NEWS WEEKLY"
        body = project.episode.get("show_tagline", "The ten-minute recap of the news actually worth knowing.")
        digest_stories = (project.episode.get("digest_plan") or {}).get("stories", [])
        labels = [
            _short(item.get("headline", "TOP STORY"), 5, 32).upper()
            for item in digest_stories[:3]
        ]
        labels = (labels + ["MODELS", "OPEN SOURCE", "BIG TECH"])[:3]
    annotation = shot.annotations[0].model_dump(mode="json") if shot.annotations else None
    mascot_context = " ".join([title, body, prompt, source_label, *labels])
    return {
        "template": template,
        "kicker": str(motion_copy.get("kicker") or PURPOSE_KICKERS.get(purpose, "SOURCE FIRST")),
        "title": title,
        "body": body,
        "metric": _metric(project, shot),
        "sourceImage": _stage_public_asset(source),
        "sourceLabel": source_label,
        "labels": labels,
        "durationSeconds": float(shot.duration_seconds),
        # Motion scenes should explain through the primary visual. Repeated
        # kicker/title rails read like template chrome and compete with source
        # evidence, so they stay disabled unless a future project explicitly
        # opts in.
        "showEditorialHeading": False,
        "accent": "#83938C",
        "accentSecondary": "#607457" if _chapter_tone(purpose) != "clay" else "#A66A4F",
        "annotation": annotation,
        "chapterTone": _chapter_tone(purpose),
        "mascots": _mascots_for(mascot_context, template=template),
        "cursor": _cursor_for(annotation, template),
    }


def _remotion_executable() -> Path:
    name = "remotion.cmd" if os.name == "nt" else "remotion"
    return REMOTION_DIR / "node_modules" / ".bin" / name


def _video_dimensions(path: Path) -> tuple[int, int]:
    process = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", str(path),
    ], capture_output=True, text=True, check=True)
    stream = json.loads(process.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def _browser_executable() -> str:
    if REMOTION_BROWSER_EXECUTABLE:
        return REMOTION_BROWSER_EXECUTABLE
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser") or ""


def render_motion_video(
    project: EpisodeProject, shot: Shot, destination: Path, *, scratch: Path | None = None,
) -> Path:
    """Render the single 1920x1080 master, with an optional emergency fallback."""
    if not REMOTION_RENDER_ENABLED:
        from .motion_graphics import render_motion_video as fallback
        return fallback(project, shot, destination, shot.duration_seconds)
    executable = _remotion_executable()
    if not executable.is_file():
        raise RuntimeError(f"Remotion is enabled but not installed at {executable}")
    scratch = scratch or destination.parent / ".remotion"
    scratch.mkdir(parents=True, exist_ok=True)
    props = build_props(project, shot, scratch)
    props_path = destination.with_suffix(".remotion-props.json")
    props_path.parent.mkdir(parents=True, exist_ok=True)
    props_path.write_text(json.dumps(props, indent=2, ensure_ascii=False), encoding="utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(executable), "render", "src/index.ts", "MotionShot1080", str(destination.resolve()),
        f"--props={props_path.resolve()}", "--codec=h264", f"--crf={REMOTION_RENDER_CRF}",
        "--scale=0.5",
        "--pixel-format=yuv420p", "--image-format=png", "--color-space=bt709",
        f"--x264-preset={FFMPEG_PRESET}", f"--concurrency={REMOTION_RENDER_CONCURRENCY}", "--muted",
    ]
    browser = _browser_executable()
    if browser:
        command.append(f"--browser-executable={browser}")
    try:
        process = subprocess.run(
            command, cwd=REMOTION_DIR, capture_output=True, text=True, timeout=1800,
        )
        if process.returncode:
            tail = "\n".join((process.stdout + "\n" + process.stderr).splitlines()[-30:])
            raise RuntimeError(f"Remotion 1080p render failed for {shot.id}:\n{tail}")
        if not destination.is_file() or destination.stat().st_size < 1024:
            raise RuntimeError(f"Remotion returned no usable output for {shot.id}")
        if _video_dimensions(destination) != (VIDEO_W, VIDEO_H):
            raise RuntimeError(
                f"Remotion master for {shot.id} is {_video_dimensions(destination)}, expected {VIDEO_W}x{VIDEO_H}"
            )
        return destination
    except Exception:
        if REMOTION_RENDER_STRICT:
            raise
        from .motion_graphics import render_motion_video as fallback
        return fallback(project, shot, destination, shot.duration_seconds)
