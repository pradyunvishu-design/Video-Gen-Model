"""Authenticated FastAPI worker called by n8n; large binaries stay on worker storage."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .clipping_format import ClipFormatRequest, write_clipping_spec
from .ai_labs_motion_expert import (
    build_ai_labs_motion_expert,
    load_motion_expert_run,
    motion_expert_run_path,
    motion_expert_status,
)
from .config import EPISODE_DATA_DIR, JOB_DB_PATH, REMOTION_DIR, WORKER_API_TOKEN, WORKER_PUBLIC_BASE_URL
from .editorial_motion_system import render_editorial_spec, validate_editorial_spec, write_editorial_spec
from .fidelity_loop import (
    build_fidelity_reference_profile, fidelity_run_path, fidelity_status,
    load_fidelity_run, run_fidelity_loop,
)
from .job_store import JobStore
from .licensed_clips import LicensedClipRequest, ingest_licensed_clip
from .models import MediaAsset
from .production import (
    CreditLimitExceeded, acquire_episode_screen_recordings,
    configure_news_weekly_model_test, create_news_weekly, create_weekly_slate,
    produce_canary, produce_episode, produce_next, refresh_sources, research_video_ideas, review_slate, run_news_weekly_model_tests,
)
from .project_store import load_project, save_project
from .viral_clips import (
    ClipApproval, ClipDiscoveryRequest, ClipMoment, build_licensed_request, discover_viral_clips, load_candidate,
)
from .youtube_broll import (
    BrollDiscoveryRequest, build_project_broll_request, discover_project_broll,
)

app = FastAPI(title="Magic Hour Video Worker", version="2.1.0", docs_url=None, redoc_url=None)
store = JobStore(JOB_DB_PATH)
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="video-worker")

SUPPORTED_STAGES = {
    "refresh_sources", "research_video_ideas", "research_slate", "research_news_weekly", "review_slate",
    "produce_episode", "produce_next", "produce_canary", "review_final", "approve_credits",
    "acquire_screen_recordings", "generate_browser_demo", "configure_model_test", "run_model_tests",
    "render_editorial", "ingest_licensed_clip", "discover_viral_clips", "discover_broll",
    "approve_and_ingest_clip", "build_clip_segment", "run_fidelity_loop",
    "build_fidelity_reference_profile", "build_ailabs_motion_expert",
}


class JobRequest(BaseModel):
    stage: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


def authenticate(authorization: str = Header(default="")) -> None:
    if not WORKER_API_TOKEN or WORKER_API_TOKEN == "change-me":
        raise HTTPException(503, "WORKER_API_TOKEN is not configured")
    if authorization != f"Bearer {WORKER_API_TOKEN}":
        raise HTTPException(401, "invalid worker token")


def _job_key(request: JobRequest) -> str:
    if request.idempotency_key:
        return request.idempotency_key
    raw = json.dumps({"stage": request.stage, "payload": request.payload}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _artifact_signature(episode_id: str, name: str, expires: int) -> str:
    payload = f"{episode_id}:{name}:{expires}".encode()
    return hmac.new(WORKER_API_TOKEN.encode(), payload, hashlib.sha256).hexdigest()


def _signed_artifact_url(episode_id: str, name: str, ttl_seconds: int = 86_400) -> str:
    expires = int(time.time()) + ttl_seconds
    signature = _artifact_signature(episode_id, name, expires)
    base = WORKER_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/artifacts/{episode_id}/{name}?expires={expires}&signature={signature}"


def _preview_links(episode_id: str) -> dict[str, str]:
    project = load_project(EPISODE_DATA_DIR / episode_id)
    return {
        name: _signed_artifact_url(episode_id, name)
        for name, path in project.artifacts.items()
        if path and not path.startswith("[")
    }


def _ledger_snapshot() -> dict[str, list[dict]]:
    episodes, weekly_slate, reviews, sources = [], [], [], []
    for project_file in sorted(EPISODE_DATA_DIR.glob("episode_*/episode_project.json")):
        try:
            project = load_project(project_file.parent)
        except Exception:
            continue
        updated_at = datetime.fromtimestamp(project_file.stat().st_mtime, timezone.utc).isoformat()
        preview_urls = _preview_links(project.episode_id) if project.artifacts else {}
        final_qc = project.qc.get("final", {})
        episodes.append({
            "episode_id": project.episode_id,
            "scheduled_date": project.scheduled_date,
            "title": project.script.title if project.script else (project.brief.title if project.brief else ""),
            "format": project.episode.get("format", project.brief.episode_format if project.brief else ""),
            "status": project.status,
            "word_count": project.script.word_count if project.script else 0,
            "duration_seconds": round(float(project.narration.get("duration_seconds", 0)), 2),
            "magic_hour_credits": int(project.costs.get("magic_hour_credits", 0)),
            "qc_passed": bool(final_qc.get("passed", False)),
            "preview_url": preview_urls.get("video", ""),
            "package_url": preview_urls.get("package", ""),
            "synthetic_media": any(asset.kind.startswith("generated_") for asset in project.media),
            "voice_rights_status": (project.episode.get("voice_rights") or {}).get("status", ""),
            "voice_documentation_pending": bool(
                (project.episode.get("voice_rights") or {}).get("documentation_pending", False)
            ),
            "approval_mode": project.episode.get("approval_mode", "human_review"),
            "publishing_enabled": bool(project.episode.get("publishing_enabled", False)),
            "updated_at": updated_at,
        })
        if project.brief:
            weekly_slate.append({
                "slate_id": project.episode.get("slate_id", ""),
                "episode_id": project.episode_id,
                "scheduled_date": project.scheduled_date,
                "title": project.brief.title,
                "format": project.brief.episode_format,
                "thesis": project.brief.thesis,
                "why_now": project.brief.why_now,
                "source_count": len(project.brief.source_ids),
                "visual_opportunities": "; ".join(project.brief.visual_opportunities),
                "decision": project.review.slate_status,
                "review_notes": project.brief.review_notes,
                "production_order": project.scheduled_date,
                "updated_at": updated_at,
            })
        if project.review.slate_status != "pending" or project.review.final_status != "pending":
            reviews.append({
                "episode_id": project.episode_id,
                "review_stage": "final" if project.review.final_status != "pending" else "slate",
                "decision": project.review.final_status if project.review.final_status != "pending" else project.review.slate_status,
                "revision_scope": ", ".join(project.episode.get("invalidated_stages", [])),
                "notes": " | ".join(project.review.notes + ([project.brief.review_notes] if project.brief and project.brief.review_notes else [])),
                "reviewer": "n8n review form",
                "reviewed_at": updated_at,
            })
        rights_by_source = {item.get("source_id"): item.get("note", "") for item in project.rights}
        for source in project.sources:
            sources.append({
                "episode_id": project.episode_id,
                "source_id": source.id,
                "source_type": source.source_type,
                "publisher": source.publisher,
                "title": source.title,
                "url": str(source.url),
                "published_at": source.published_at.isoformat() if source.published_at else "",
                "rights_note": rights_by_source.get(source.id, "Human rights review required before publication."),
            })
    jobs = store.list_all()
    job_rows, activity = [], []
    for job in jobs:
        result = job.get("result") or {}
        credits = int((result.get("credits") or {}).get("magic_hour_credits", 0))
        episode_id = result.get("episode_id") or job["payload"].get("episode_id", "")
        job_rows.append({
            "job_id": job["id"], "stage": job["stage"], "status": job["status"],
            "progress": float(job["progress"]) / 100, "episode_id": episode_id,
            "credits": credits, "error": job.get("error") or "",
            "created_at": job["created_at"], "updated_at": job["updated_at"],
        })
        activity.append({
            "event_id": job["id"], "event_type": job["stage"], "workflow": "video-worker",
            "slate_id": result.get("slate_id", ""), "episode_id": episode_id,
            "status": job["status"], "title": result.get("title", ""), "credits": credits,
            "qc_passed": bool((result.get("qc") or {}).get("final", {}).get("passed", False)),
            "preview_url": result.get("preview_url", ""),
            "details_json": json.dumps({"error": job.get("error"), "result": result}, default=str)[:45000],
            "event_time": job["updated_at"],
        })
    return {
        "activity_log": activity, "episodes": episodes, "weekly_slate": weekly_slate,
        "reviews": reviews, "sources": sources, "jobs": job_rows,
    }


def _review_final(payload: dict) -> dict:
    project_dir = EPISODE_DATA_DIR / payload["episode_id"]
    project = load_project(project_dir)
    approved = bool(payload.get("approved"))
    notes = payload.get("notes", "")
    if notes:
        project.review.notes.append(notes)
    project.review.final_status = "approved" if approved else "revision_requested"
    project.status = "approved_final" if approved else "revision_requested"
    if not approved:
        stages = set(payload.get("stages") or ["render"])
        revision = int(project.episode.get("revision", 0)) + 1
        project.episode["revision"] = revision
        project.episode["invalidated_stages"] = sorted(stages)
        archive = project_dir / "archive" / f"revision_{revision:02d}"
        archive.mkdir(parents=True, exist_ok=True)
        targets = set()
        if "script" in stages:
            project.claims = []
            project.script = None
            project.shots = []
            project.media = []
            project.captures = []
            project.narration = {}
            project.artifacts = {}
            project.qc = {}
            targets.update(["audio", "generated", "captures", "timeline_segments", "thumbnails"])
        elif "media" in stages:
            project.shots = []
            project.media = []
            project.captures = []
            project.artifacts.pop("video", None)
            project.qc.pop("final", None)
            targets.update(["generated", "captures", "timeline_segments", "thumbnails"])
        elif "captions" in stages:
            project.artifacts.pop("captions", None)
            project.artifacts.pop("video", None)
            project.qc.pop("final", None)
            targets.update(["captions.ass", "timeline_segments"])
        else:
            project.artifacts.pop("video", None)
            project.qc.pop("final", None)
            targets.add("timeline_segments")
        for name in targets:
            target = project_dir / name
            if target.exists():
                shutil.move(str(target), archive / target.name)
    save_project(project, project_dir)
    return {"episode_id": project.episode_id, "status": project.status, "review": project.review.model_dump()}


def _approve_credits(payload: dict) -> dict:
    project_dir = EPISODE_DATA_DIR / payload["episode_id"]
    project = load_project(project_dir)
    current = int(project.costs.get("magic_hour_credits", 0))
    previous_limit = int(project.episode.get("credit_limit", 15_000))
    new_limit = int(payload["new_limit"])
    if new_limit <= max(current, previous_limit):
        raise ValueError(f"new_limit must exceed both current spend ({current}) and prior limit ({previous_limit})")
    project.episode["credit_limit"] = new_limit
    project.episode.pop("requested_credit_limit", None)
    project.status = "approved_for_production"
    save_project(project, project_dir)
    return {"episode_id": project.episode_id, "status": project.status, "credit_limit": new_limit, "current_credits": current}


def _render_editorial(payload: dict) -> dict:
    project_dir = EPISODE_DATA_DIR / payload["episode_id"]
    project = load_project(project_dir)
    editorial_dir = project_dir / "editorial"
    spec_path = write_editorial_spec(project, editorial_dir / "episode.json", REMOTION_DIR / "public")
    output = render_editorial_spec(spec_path, editorial_dir / "editorial_preview_1080p.mp4", REMOTION_DIR)
    report = validate_editorial_spec(json.loads(spec_path.read_text(encoding="utf-8")), REMOTION_DIR / "public")
    project.artifacts["editorial_preview"] = str(output)
    project.artifacts["editorial_spec"] = str(spec_path)
    project.qc["editorial_motion"] = report.as_dict()
    save_project(project, project_dir)
    return {
        "episode_id": project.episode_id,
        "status": "editorial_preview_ready",
        "artifacts": {"editorial_preview": str(output), "editorial_spec": str(spec_path)},
        "qc": {"editorial_motion": report.as_dict()},
    }


def _ingest_licensed_clip(payload: dict) -> dict:
    episode_id = payload["episode_id"]
    project_dir = EPISODE_DATA_DIR / episode_id
    project = load_project(project_dir)
    request = LicensedClipRequest.model_validate(payload["request"])
    shot_ids = set(payload.get("shot_ids", []))
    unknown_shots = shot_ids - {shot.id for shot in project.shots}
    if unknown_shots:
        raise ValueError(f"unknown shot IDs for licensed clip: {sorted(unknown_shots)}")
    result = ingest_licensed_clip(request, project_dir / "licensed_clips")
    clip_path = result["clip"]
    asset_id = f"licensed_clip_{request.clip_id}"
    project.media = [asset for asset in project.media if asset.id != asset_id]
    project.media.append(MediaAsset(
        id=asset_id,
        kind="licensed_source_clip",
        path=clip_path,
        source_id=request.source_id or None,
        sha256=result["output_sha256"],
        qc_status="passed",
        qc_notes=[
            f"Rights basis: {result['rights']['basis']}",
            f"Attribution: {result['rights']['attribution']}",
            "Publication rights review remains required.",
        ],
    ))
    for shot in project.shots:
        if shot.id not in shot_ids:
            continue
        shot.asset_type = "official_demo"
        shot.visual_category = "youtube_broll"
        shot.asset_path = clip_path
        if payload.get("alignment_score") is not None:
            shot.alignment_score = float(payload["alignment_score"])
        if payload.get("alignment_context"):
            shot.prompt = f"{shot.prompt} {payload['alignment_context']}".strip()
        shot.motion_style = "locked"
        shot.presentation = "full_bleed"
        shot.rights_note = (
            f"Licensed third-party excerpt ({result['rights']['basis']}); "
            f"attribution: {result['rights']['attribution']}"
        )
    project.rights = [entry for entry in project.rights if entry.get("asset_id") != asset_id]
    project.rights.append({
        "asset_id": asset_id,
        "source_id": request.source_id,
        "asset_path": clip_path,
        "source_url": str(request.url),
        "capture_mode": "licensed_timestamped_excerpt",
        "rights_basis": result["rights"]["basis"],
        "muted": True,
        "rights_ledger": result["ledger"],
        "attribution": result["rights"]["attribution"],
        "review_required_before_publication": True,
    })
    project.artifacts[f"licensed_clip_{request.clip_id}"] = clip_path
    project.artifacts[f"licensed_clip_{request.clip_id}_ledger"] = result["ledger"]
    save_project(project, project_dir)
    return {
        "episode_id": episode_id,
        "status": "licensed_clip_ready",
        "artifacts": {"clip": clip_path, "rights_ledger": result["ledger"]},
        "rights": result["rights"],
        "quality": result["quality"],
    }


def _discover_viral_clips(payload: dict) -> dict:
    episode_id = payload["episode_id"]
    project_dir = EPISODE_DATA_DIR / episode_id
    project = load_project(project_dir)
    request = ClipDiscoveryRequest.model_validate(payload["request"])
    result = discover_viral_clips(request, project_dir / "clip_research")
    project.artifacts["viral_clip_candidates"] = result["manifest"]
    project.artifacts["viral_clip_permission_queue"] = result["permission_queue"]
    project.episode["clip_research"] = {
        "candidate_count": result["candidate_count"],
        "error_count": result["error_count"],
        "status": "research_only",
        "render_gate": "approved rights required",
    }
    save_project(project, project_dir)
    return {
        "episode_id": episode_id, "status": "viral_clip_research_ready",
        "artifacts": {
            "viral_clip_candidates": result["manifest"],
            "viral_clip_permission_queue": result["permission_queue"],
        },
        "candidate_count": result["candidate_count"], "error_count": result["error_count"],
        "top_candidates": result["top_candidates"],
    }


def _discover_broll(payload: dict) -> dict:
    """Create three scene-specific YouTube candidates without downloading video."""
    episode_id = payload["episode_id"]
    project_dir = EPISODE_DATA_DIR / episode_id
    project = load_project(project_dir)
    request = (
        BrollDiscoveryRequest.model_validate(payload["request"])
        if payload.get("request") else build_project_broll_request(project)
    )
    result = discover_project_broll(project, project_dir / "broll_research", request)
    project.artifacts["broll_candidates"] = result["manifest"]
    project.artifacts["broll_review_queue"] = result["review_queue"]
    expected = result["scene_count"] * request.candidates_per_scene
    project.episode["broll_research"] = {
        "status": "human_review_required",
        "scene_count": result["scene_count"],
        "candidate_count": result["candidate_count"],
        "planner": result["planner"],
        "render_gate": "approved reuse rights and timestamps required",
    }
    project.qc["youtube_broll"] = {
        "passed": result["candidate_count"] >= expected,
        "scene_count": result["scene_count"],
        "candidate_count": result["candidate_count"],
        "expected_candidate_count": expected,
        "errors": result["error_count"],
        "downloads": 0,
        "human_review_required": True,
    }
    save_project(project, project_dir)
    return {
        "episode_id": episode_id,
        "status": "broll_review_ready",
        "artifacts": {
            "broll_candidates": result["manifest"],
            "broll_review_queue": result["review_queue"],
        },
        "scene_count": result["scene_count"],
        "candidate_count": result["candidate_count"],
        "candidates_by_scene": result["candidates_by_scene"],
        "planner": result["planner"],
    }


def _approve_and_ingest_clip(payload: dict) -> dict:
    """Promote a discovered moment only after its rights contract validates."""
    episode_id = payload["episode_id"]
    project_dir = EPISODE_DATA_DIR / episode_id
    project = load_project(project_dir)
    manifest_raw = (
        project.artifacts.get(str(payload.get("manifest_artifact") or ""), "")
        or project.artifacts.get("broll_candidates", "")
        or project.artifacts.get("viral_clip_candidates", "")
    )
    if not manifest_raw:
        raise ValueError("episode has no viral clip candidate manifest")
    manifest_path = Path(manifest_raw)
    if not manifest_path.is_file() or project_dir.resolve() not in manifest_path.resolve().parents:
        raise PermissionError("candidate manifest must be an artifact inside the episode directory")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_candidate = next(
        (item for item in manifest.get("candidates", []) if item.get("candidate_id") == payload["candidate_id"]),
        None,
    )
    if not raw_candidate:
        raise KeyError(f"clip candidate not found: {payload['candidate_id']}")
    candidate = load_candidate(manifest_path, payload["candidate_id"])
    approval = ClipApproval.model_validate(payload["approval"])
    if payload.get("start_seconds") is not None or payload.get("end_seconds") is not None:
        start_seconds = float(payload.get("start_seconds", -1))
        end_seconds = float(payload.get("end_seconds", -1))
        if start_seconds < 0 or end_seconds <= start_seconds or end_seconds - start_seconds > 45:
            raise ValueError("manual b-roll range must be between 0 and 45 seconds")
        candidate = candidate.model_copy(update={
            "moments": [ClipMoment(
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                score=100,
                reason="Human-selected timestamp range",
                requires_manual_timestamp_review=False,
            )]
        })
        approval = approval.model_copy(update={"moment_index": 0})
    request = build_licensed_request(candidate, approval)
    shot_ids = payload.get("shot_ids") or raw_candidate.get("shot_ids") or []
    result = _ingest_licensed_clip({
        "episode_id": episode_id,
        "request": request.model_dump(mode="json"),
        "shot_ids": shot_ids,
        "alignment_score": raw_candidate.get("semantic_score"),
        "alignment_context": " ".join(filter(None, [
            str(raw_candidate.get("title") or ""),
            str(raw_candidate.get("channel") or ""),
            str(raw_candidate.get("clip_kind") or ""),
            str(raw_candidate.get("visual_target") or ""),
        ])),
    })

    for item in manifest.get("candidates", []):
        if item.get("candidate_id") != candidate.candidate_id:
            continue
        item["rights_status"] = "approved"
        item["approved_rights"] = {
            "basis": approval.rights_basis, "approved_by": approval.approved_by,
            "attribution": approval.attribution, "ledger": result["artifacts"]["rights_ledger"],
        }
        item["moments"] = [moment.model_dump(mode="json") for moment in candidate.moments]
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    result["candidate_id"] = candidate.candidate_id
    return result


def _build_clip_segment(payload: dict) -> dict:
    episode_id = payload["episode_id"]
    project_dir = EPISODE_DATA_DIR / episode_id
    project = load_project(project_dir)
    request = ClipFormatRequest.model_validate(payload["format"])
    segment_dir = project_dir / "clip_segments" / request.segment_id
    spec_path = write_clipping_spec(
        project, request, segment_dir / "segment.json", REMOTION_DIR / "public",
    )
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    report = validate_editorial_spec(spec, REMOTION_DIR / "public")
    artifacts = {"clip_segment_spec": str(spec_path)}
    if bool(payload.get("render")):
        output = render_editorial_spec(
            spec_path, segment_dir / "clip_segment_1080p.mp4", REMOTION_DIR,
        )
        artifacts["clip_segment_video"] = str(output)
    project.artifacts[f"clip_segment_{request.segment_id}_spec"] = str(spec_path)
    if "clip_segment_video" in artifacts:
        project.artifacts[f"clip_segment_{request.segment_id}_video"] = artifacts["clip_segment_video"]
    project.qc[f"clip_segment_{request.segment_id}"] = report.as_dict()
    save_project(project, project_dir)
    return {
        "episode_id": episode_id,
        "status": "clip_segment_ready" if "clip_segment_video" in artifacts else "clip_segment_planned",
        "artifacts": artifacts,
        "qc": report.as_dict(),
    }


def _execute(
    stage: str, payload: dict, should_cancel=None, report_progress=None,
) -> dict:
    if stage == "refresh_sources":
        return refresh_sources()
    if stage == "research_video_ideas":
        return research_video_ideas(force_youtube=bool(payload.get("force_youtube", False)))
    if stage == "research_slate":
        start = date.fromisoformat(payload["start_date"]) if payload.get("start_date") else None
        return create_weekly_slate(start=start, recent_topics=payload.get("recent_topics"))
    if stage == "research_news_weekly":
        start = date.fromisoformat(payload["start_date"]) if payload.get("start_date") else None
        return create_news_weekly(start=start, recent_topics=payload.get("recent_topics"))
    if stage == "review_slate":
        return review_slate(payload["slate_id"], payload["decisions"])
    if stage == "produce_episode":
        return produce_episode(
            payload["episode_id"], canary=bool(payload.get("canary")),
            should_cancel=should_cancel, report_progress=report_progress,
        )
    if stage == "produce_next":
        return produce_next(
            payload.get("scheduled_date"), should_cancel=should_cancel, report_progress=report_progress,
        )
    if stage == "produce_canary":
        return produce_canary(
            payload["episode_id"], should_cancel=should_cancel, report_progress=report_progress,
        )
    if stage == "acquire_screen_recordings":
        return acquire_episode_screen_recordings(
            payload["episode_id"], should_cancel=should_cancel, report_progress=report_progress,
        )
    if stage == "review_final":
        return _review_final(payload)
    if stage == "approve_credits":
        return _approve_credits(payload)
    if stage == "generate_browser_demo":
        from .product_demo import DemoSpec, generate_demo
        return generate_demo(DemoSpec.model_validate(payload["spec"]))
    if stage == "configure_model_test":
        return configure_news_weekly_model_test(
            payload["episode_id"], payload["story_id"], payload["website"],
            inputs=payload.get("inputs"), allow_generation=bool(payload.get("allow_generation")),
        )
    if stage == "run_model_tests":
        return run_news_weekly_model_tests(payload["episode_id"])
    if stage == "render_editorial":
        return _render_editorial(payload)
    if stage == "ingest_licensed_clip":
        return _ingest_licensed_clip(payload)
    if stage == "discover_viral_clips":
        return _discover_viral_clips(payload)
    if stage == "discover_broll":
        return _discover_broll(payload)
    if stage == "approve_and_ingest_clip":
        return _approve_and_ingest_clip(payload)
    if stage == "build_clip_segment":
        return _build_clip_segment(payload)
    if stage == "run_fidelity_loop":
        return run_fidelity_loop(payload, should_cancel=should_cancel, report_progress=report_progress)
    if stage == "build_fidelity_reference_profile":
        return build_fidelity_reference_profile(
            payload, should_cancel=should_cancel, report_progress=report_progress,
        )
    if stage == "build_ailabs_motion_expert":
        return build_ai_labs_motion_expert(
            payload, should_cancel=should_cancel, report_progress=report_progress,
        )
    raise ValueError(f"unsupported stage: {stage}")


def _run_job(job_id: str, stage: str, payload: dict) -> None:
    try:
        job = store.get(job_id)
        if job["cancel_requested"]:
            store.update(job_id, status="canceled", progress=0)
            return
        store.update(job_id, status="running", progress=5)
        result = _execute(
            stage,
            payload,
            should_cancel=lambda: store.get(job_id)["cancel_requested"],
            report_progress=lambda value: store.update(job_id, progress=value),
        )
        if result.get("episode_id") and result.get("artifacts"):
            result["preview_urls"] = _preview_links(result["episode_id"])
            result["preview_url"] = result["preview_urls"].get("video", "")
        job = store.get(job_id)
        if job["cancel_requested"]:
            store.update(job_id, status="canceled", progress=100, result=result)
        else:
            store.update(job_id, status="complete", progress=100, result=result, error=None)
    except InterruptedError as exc:
        store.update(job_id, status="canceled", error=str(exc))
    except CreditLimitExceeded as exc:
        store.update(job_id, status="paused", error=str(exc))
    except Exception as exc:
        store.update(job_id, status="error", error=f"{type(exc).__name__}: {exc}")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.post("/jobs", dependencies=[Depends(authenticate)])
def create_job(request: JobRequest) -> dict:
    if request.stage not in SUPPORTED_STAGES:
        raise HTTPException(422, "unsupported stage")
    job_id = "job_" + uuid.uuid4().hex
    job, created = store.create(job_id, _job_key(request), request.stage, request.payload)
    if created:
        executor.submit(_run_job, job_id, request.stage, request.payload)
    return job


@app.get("/jobs/{job_id}", dependencies=[Depends(authenticate)])
def get_job(job_id: str) -> dict:
    try:
        return store.get(job_id)
    except KeyError:
        raise HTTPException(404, "job not found")


@app.get("/fidelity-runs/{run_id}", dependencies=[Depends(authenticate)])
def get_fidelity_run(run_id: str) -> dict:
    if motion_expert_run_path(run_id).is_file():
        return motion_expert_status(load_motion_expert_run(run_id))
    if not fidelity_run_path(run_id).is_file():
        raise HTTPException(404, "fidelity run not found")
    return fidelity_status(load_fidelity_run(run_id))


@app.get("/slates/{slate_id}", dependencies=[Depends(authenticate)])
def get_slate(slate_id: str) -> dict:
    slate_path = EPISODE_DATA_DIR / slate_id / "slate.json"
    if not slate_path.is_file():
        raise HTTPException(404, "slate not found")
    return json.loads(slate_path.read_text(encoding="utf-8"))


@app.post("/jobs/{job_id}/cancel", dependencies=[Depends(authenticate)])
def cancel_job(job_id: str) -> dict:
    try:
        return store.update(job_id, cancel_requested=1)
    except KeyError:
        raise HTTPException(404, "job not found")


@app.get("/packages/{episode_id}", dependencies=[Depends(authenticate)])
def get_package(episode_id: str) -> dict:
    try:
        project = load_project(EPISODE_DATA_DIR / episode_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "episode not found")
    return {
        "episode_id": episode_id,
        "status": project.status,
        "qc": project.qc,
        "costs": project.costs,
        "preview_urls": _preview_links(episode_id),
    }


@app.get("/ledger", dependencies=[Depends(authenticate)])
def get_ledger() -> dict[str, list[dict]]:
    return _ledger_snapshot()


@app.get("/artifacts/{episode_id}/{name}")
def get_artifact(
    episode_id: str,
    name: str,
    authorization: str = Header(default=""),
    expires: int | None = Query(default=None),
    signature: str = Query(default=""),
):
    bearer_ok = bool(WORKER_API_TOKEN and authorization == f"Bearer {WORKER_API_TOKEN}")
    signed_ok = bool(
        expires
        and expires >= int(time.time())
        and secrets.compare_digest(signature, _artifact_signature(episode_id, name, expires))
    )
    if not bearer_ok and not signed_ok:
        raise HTTPException(401, "valid bearer authorization or unexpired signed link required")
    project_dir = (EPISODE_DATA_DIR / episode_id).resolve()
    try:
        project = load_project(project_dir)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "episode not found")
    raw = project.artifacts.get(name)
    if not raw or raw.startswith("["):
        raise HTTPException(404, "artifact not found or is a collection")
    artifact = Path(raw).resolve()
    if project_dir not in artifact.parents or not artifact.is_file():
        raise HTTPException(404, "artifact is unavailable")
    return FileResponse(artifact)
