"""Build rights-aware podcast and product-release segments for the editorial renderer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .editorial_motion_system import _stage_asset, validate_editorial_spec
from .models import EpisodeProject, MediaAsset


class ClipFormatRequest(BaseModel):
    segment_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    media_asset_id: str = Field(min_length=3, max_length=100)
    clip_type: Literal["podcast", "release_video", "keynote", "interview", "official_demo"]
    headline: str = Field(min_length=8, max_length=92)
    hook: str = Field(min_length=12, max_length=150)
    context: str = Field(min_length=12, max_length=220)
    key_points: list[str] = Field(min_length=2, max_length=4)
    claim: str = Field(min_length=8, max_length=120)
    evidence: str = Field(min_length=8, max_length=160)
    why_it_matters: str = Field(min_length=12, max_length=180)
    source_label: str = Field(min_length=2, max_length=60)
    target_seconds: float = Field(default=45, ge=36, le=60)
    second_excerpt_offset_seconds: float = Field(default=7, ge=0, le=35)


def _licensed_asset(project: EpisodeProject, asset_id: str) -> tuple[MediaAsset, dict[str, Any]]:
    asset = next((item for item in project.media if item.id == asset_id), None)
    if not asset:
        raise ValueError(f"unknown media asset: {asset_id}")
    if asset.kind != "licensed_source_clip" or asset.qc_status != "passed":
        raise PermissionError("clip segments require a QC-passed licensed_source_clip asset")
    if not Path(asset.path).is_file():
        raise FileNotFoundError(f"licensed clip is missing: {asset.path}")
    rights = next((item for item in project.rights if item.get("asset_id") == asset_id), None)
    if not rights:
        raise PermissionError("licensed clip has no project rights record")
    ledger_path = Path(str(rights.get("rights_ledger", "")))
    if not ledger_path.is_file():
        raise PermissionError("licensed clip rights ledger is missing")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("quality", {}).get("status") != "accepted":
        raise PermissionError("licensed clip did not pass source-media QC")
    if ledger.get("rights", {}).get("basis") not in {
        "owned", "written_permission", "creative_commons", "public_domain",
    }:
        raise PermissionError("licensed clip has an unsupported rights basis")
    if ledger.get("output_sha256") != asset.sha256:
        raise PermissionError("licensed clip hash does not match its rights ledger")
    return asset, ledger


def _scene(scene_id: str, kind: str, duration: float, **overrides: Any) -> dict[str, Any]:
    scene: dict[str, Any] = {
        "id": scene_id,
        "kind": kind,
        "durationSeconds": round(duration, 3),
        "chapter": "NEWS CLIP",
        "title": "",
        "subtitle": "",
        "anchor": "left",
        "accent": "#F2F1ED",
        "logos": [],
        "messages": [],
        "nodes": [],
        "edges": [],
        "items": [],
        "sourceAsset": "",
        "sourceLabel": "",
        "sourceUrl": "",
        "evidenceIds": [],
        "sourceStartSeconds": 0,
        "sourceObjectPosition": "50% 16%",
        "sourceFocus": None,
        "claim": "",
        "evidence": "",
    }
    scene.update(overrides)
    return scene


def _durations(target_seconds: float, clip_seconds: float) -> list[float]:
    # Six scenes with five six-frame fades. Add the one second of overlap so
    # the rendered segment lands on the requested wall-clock duration.
    total = target_seconds + 1.0
    weights = [0.10, 0.18, 0.17, 0.22, 0.18, 0.15]
    values = [total * weight for weight in weights]
    source_cap = min(10.0, clip_seconds)
    deficit = 0.0
    for index in (1, 4):
        if values[index] > source_cap:
            deficit += values[index] - source_cap
            values[index] = source_cap
    # Put time saved by a short source clip into explanation, not a loop.
    values[2] += deficit * 0.45
    values[3] += deficit * 0.35
    values[5] += deficit * 0.20
    return [round(value, 3) for value in values]


def build_clipping_spec(
    project: EpisodeProject, request: ClipFormatRequest, public_dir: Path,
) -> dict[str, Any]:
    """Create an original clip/context/evidence/takeaway segment from a licensed asset."""
    asset, ledger = _licensed_asset(project, request.media_asset_id)
    clip_seconds = float(ledger["end_seconds"]) - float(ledger["start_seconds"])
    if clip_seconds < 6:
        raise ValueError("clip-format source excerpts must be at least six seconds")
    durations = _durations(request.target_seconds, clip_seconds)
    staged_asset = _stage_asset(asset.path, public_dir)
    source_url = str(ledger.get("source_webpage_url") or ledger.get("source_url") or "")[:180]
    source_label = request.source_label[:60]
    evidence_ids = [f"asset:{asset.id}"]
    second_offset = min(request.second_excerpt_offset_seconds, max(0, clip_seconds - durations[4]))
    scenes = [
        _scene(
            f"{request.segment_id}-hook", "title", durations[0], chapter="BREAKING DOWN THE CLIP",
            title=request.headline, subtitle=request.hook, anchor="left",
        ),
        _scene(
            f"{request.segment_id}-source-a", "source", durations[1], chapter=request.clip_type.upper(),
            sourceAsset=staged_asset, sourceLabel=source_label, sourceUrl=source_url,
            evidenceIds=evidence_ids,
            sourceStartSeconds=0, anchor="center",
        ),
        _scene(
            f"{request.segment_id}-context", "activity", durations[2], chapter="THE CONTEXT",
            title="What you need to know", subtitle=request.context, items=request.key_points,
            anchor="right",
        ),
        _scene(
            f"{request.segment_id}-evidence", "compare", durations[3], chapter="CLAIM CHECK",
            title="What the evidence says", subtitle=request.context, claim=request.claim,
            evidence=request.evidence, accent="#83938C", anchor="left",
        ),
        _scene(
            f"{request.segment_id}-source-b", "source", durations[4], chapter="WATCH THE DETAIL",
            sourceAsset=staged_asset, sourceLabel=source_label, sourceUrl=source_url,
            evidenceIds=evidence_ids,
            sourceStartSeconds=round(second_offset, 3), anchor="center",
        ),
        _scene(
            f"{request.segment_id}-takeaway", "title", durations[5], chapter="WHY IT MATTERS",
            title=request.why_it_matters, subtitle="The source clip is evidence; the explanation is the story.",
            anchor="right",
        ),
    ]
    narration_path = str(project.narration.get("master_path") or project.narration.get("path") or "")
    spec = {
        "episodeId": f"{project.episode_id}-{request.segment_id}",
        "seriesName": "AI NEWS / CLIP EXPLAINED",
        "footer": "LICENSED SOURCE · ORIGINAL COMMENTARY",
        "audioSrc": _stage_asset(narration_path, public_dir),
        "captions": project.timeline.get("captions") or [],
        "scenes": scenes,
    }
    report = validate_editorial_spec(spec, public_dir)
    if not report.passed:
        raise ValueError("Generated clipping spec failed validation:\n" + "\n".join(report.errors))
    return spec


def write_clipping_spec(
    project: EpisodeProject, request: ClipFormatRequest, destination: Path, public_dir: Path,
) -> Path:
    spec = build_clipping_spec(project, request, public_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination
