"""Service-to-service integration routes; never expose the worker token to a browser.

X-Customer-ID must be set by an authenticated upstream application. It is an
ownership scope, not an independently authenticated customer credential.
"""
from __future__ import annotations

import re
import json
import threading
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import Field

from . import video_composer as composer
from .project_store import canonical_hash, load_project, save_project

_mutation_lock = threading.RLock()


class Approval(composer.StrictInput):
    stage: Literal["brief", "script", "plan"]
    expected_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class CompositionJob(composer.StrictInput):
    stage: Literal["write_script", "discover_clips", "plan_edit", "compile_edit"]
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    paid_generation_approved: bool = False


class AssetAlignment(composer.StrictInput):
    asset_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,120}$")
    expected_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    claim_ids: list[str] = Field(min_length=1, max_length=30)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    alignment_reviewed: Literal[True]


class MotionAssignment(composer.StrictInput):
    beat_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,120}$')
    expected_script_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    spec: composer.MotionSpec


class MotionPreviewApproval(composer.StrictInput):
    expected_hash: str = Field(pattern=r'^[a-f0-9]{64}$')


def owned_project(root: Path, project_id: str, owner: str):
    if not re.fullmatch(r"episode_comp_[a-z0-9]{1,64}", project_id):
        raise HTTPException(404, "composition project not found")
    directory = (root / project_id).resolve()
    if not directory.is_relative_to(root.resolve()):
        raise HTTPException(404, "composition project not found")
    try:
        project = load_project(directory)
        if composer.composition_state(project)["owner_id"] != owner:
            raise ValueError("wrong owner")
    except (OSError, ValueError, KeyError):
        raise HTTPException(404, "composition project not found") from None
    return project, directory


def create_router(authenticate, root_getter, enqueue, get_job=None, cancel_job=None):
    router = APIRouter(dependencies=[Depends(authenticate)])

    def customer(x_customer_id: str = Header(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")):
        return x_customer_id

    def owned_job(project_id, job_id, owner):
        owned_project(root_getter(), project_id, owner)
        try:
            item = get_job(job_id)
            if (item["stage"] != "compose_customer_video" or item["payload"].get("owner_id") != owner
                    or item["payload"].get("episode_id") != project_id):
                raise KeyError(job_id)
        except KeyError:
            raise HTTPException(404, "composition job not found") from None
        return item

    def safe_job(item):
        # Provider exceptions and stored results may include local paths; keep them internal.
        return {"job_id": item["id"], "status": item["status"], "progress": item["progress"],
                "cancel_requested": item["cancel_requested"],
                "error": "Job failed; contact support with this job ID" if item.get("error") else None}

    @router.get("/composition-projects/{project_id}/jobs/{job_id}")
    def status(project_id: str, job_id: str, owner: str = Depends(customer)):
        return safe_job(owned_job(project_id, job_id, owner))

    @router.post("/composition-projects/{project_id}/jobs/{job_id}/cancel")
    def cancel(project_id: str, job_id: str, owner: str = Depends(customer)):
        owned_job(project_id, job_id, owner)
        return safe_job(cancel_job(job_id))

    @router.get("/video-models")
    def models():
        return composer.model_catalog()

    @router.get('/motion-styles')
    def motion_styles():
        return composer.motion_catalog()

    @router.post('/composition-projects/{project_id}/motion-specs')
    def motion_spec(project_id: str, request: MotionAssignment, owner: str = Depends(customer)):
        with _mutation_lock:
            project, directory = owned_project(root_getter(), project_id, owner)
            if composer.approval_hash(project, 'script') != request.expected_script_hash:
                raise HTTPException(409, 'script changed; refresh before assigning graphics')
            try:
                result = composer.set_motion_spec(project, request.beat_id, request.spec)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
            save_project(project, directory)
            return result

    @router.get('/composition-projects/{project_id}/motion-previews')
    def motion_previews(project_id: str, owner: str = Depends(customer)):
        from .motion_library import package_hash
        project, directory = owned_project(root_getter(), project_id, owner)
        state = composer.composition_state(project)
        previews = []
        if (any(k.startswith('motion_package_') for k in project.artifacts)
                and (state.get('compiled_plan_hash') != composer.approval_hash(project, 'plan')
                     or state.get('approvals',{}).get('plan') != composer.approval_hash(project,'plan')
                     or state.get('plan',{}).get('input_hash') != composer.plan_input_hash(project))):
            raise HTTPException(409, 'compile the current plan before reviewing previews')
        for scene in state.get('plan', {}).get('scenes', []):
            if not scene.get('motion_spec'):
                continue
            raw = project.artifacts.get('motion_package_'+scene['id'])
            if not raw:
                continue
            path = Path(raw).resolve()
            if not path.is_relative_to(directory):
                raise HTTPException(409, 'motion preview unavailable')
            try:
                digest = package_hash(path.parent)
            except (OSError, ValueError):
                raise HTTPException(409, 'motion preview changed; rebuild it') from None
            previews.append({'scene_id':scene['id'], 'kind':scene['motion_spec']['kind'],
                             'expected_hash':digest, 'duration_seconds':scene['duration_seconds'],
                             'approved':state.get('motion_preview_approvals',{}).get(scene['id'])==digest})
        return {'previews':previews, 'review_required':True}

    @router.post('/composition-projects/{project_id}/motion-previews/{scene_id}/approve')
    def approve_motion_preview(project_id: str, scene_id: str, request: MotionPreviewApproval, owner: str = Depends(customer)):
        from .motion_library import package_hash
        with _mutation_lock:
            project, directory = owned_project(root_getter(), project_id, owner)
            state = composer.composition_state(project)
            if (state.get('approvals', {}).get('plan') != composer.approval_hash(project,'plan')
                    or state.get('compiled_plan_hash') != composer.approval_hash(project,'plan')
                    or state.get('plan',{}).get('input_hash') != composer.plan_input_hash(project)):
                raise HTTPException(409,'current plan approval required')
            raw = project.artifacts.get('motion_package_'+scene_id)
            if not raw:
                raise HTTPException(404,'motion preview not found')
            path = Path(raw).resolve()
            if not path.is_relative_to(directory):
                raise HTTPException(409,'motion preview unavailable')
            try:
                digest = package_hash(path.parent)
            except (OSError, ValueError):
                raise HTTPException(409,'motion preview changed; rebuild it') from None
            if digest != request.expected_hash:
                raise HTTPException(409,'preview changed; refresh before approving')
            state.setdefault('motion_preview_approvals',{})[scene_id] = digest
            save_project(project,directory)
            return {'scene_id':scene_id,'approved':True,'video_rendered':False}

    @router.post("/composition-projects", status_code=201)
    def create(request: composer.CompositionRequest, response: Response, owner: str = Depends(customer)):
        project_id = "episode_comp_" + uuid.uuid4().hex
        project = composer.create_project(project_id, owner, request)
        save_project(project, root_getter() / project_id)
        response.headers["Location"] = f"/composition-projects/{project_id}"
        return composer.project_summary(project)

    @router.get("/composition-projects/{project_id}")
    def get(project_id: str, owner: str = Depends(customer)):
        project, _ = owned_project(root_getter(), project_id, owner)
        return composer.project_summary(project)

    @router.get("/composition-projects/{project_id}/clips")
    def clips(project_id: str, owner: str = Depends(customer)):
        project, directory = owned_project(root_getter(), project_id, owner)
        raw = project.artifacts.get("broll_candidates")
        if not raw:
            return {"candidates": [], "review_required": True}
        path = Path(raw).resolve()
        if not path.is_relative_to(directory) or not path.is_file() or path.stat().st_size > 10_000_000:
            raise HTTPException(409, "clip review file unavailable")
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            fields = {"candidate_id", "video_id", "source_url", "title", "channel", "duration_seconds",
                      "scene_id", "beat_id", "semantic_score", "rights_status", "license_name", "moments"}
            candidates = [{k: v for k, v in item.items() if k in fields} for item in manifest["candidates"]]
        except (ValueError, KeyError, TypeError):
            raise HTTPException(409, "clip review file invalid") from None
        return {"candidates": candidates, "review_required": True}

    @router.get("/composition-projects/{project_id}/script")
    def script(project_id: str, owner: str = Depends(customer)):
        project, _ = owned_project(root_getter(), project_id, owner)
        return {"script": project.script.model_dump(mode="json") if project.script else None,
                "approval_hash": composer.approval_hash(project, "script"),
                "sources": [{"id": s.id, "title": s.title, "url": str(s.url)} for s in project.sources],
                "claims": [c.model_dump(mode="json") for c in project.claims], "review_required": True}

    @router.post("/composition-projects/{project_id}/approvals")
    def approve(project_id: str, request: Approval, owner: str = Depends(customer)):
        with _mutation_lock:
            project, directory = owned_project(root_getter(), project_id, owner)
            try:
                composer.approve(project, request.stage, request.expected_hash)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
            save_project(project, directory)
            return composer.project_summary(project)

    @router.post("/composition-projects/{project_id}/asset-alignments")
    def annotate(project_id: str, request: AssetAlignment, owner: str = Depends(customer)):
        with _mutation_lock:
            project, directory = owned_project(root_getter(), project_id, owner)
            asset = next((a for a in project.media if a.id == request.asset_id), None)
            if not asset or asset.sha256 != request.expected_sha256:
                raise HTTPException(409, "registered asset missing or changed")
            if request.end_seconds <= request.start_seconds:
                raise HTTPException(422, "end must follow start")
            if not set(request.claim_ids) <= {c.id for c in project.claims}:
                raise HTTPException(422, "unknown claim IDs")
            state = composer.composition_state(project)
            state["asset_annotations"][asset.id] = request.model_dump()
            state["approvals"].pop("plan", None)
            save_project(project, directory)
            return {"asset_id": asset.id, "alignment_saved": True, "rights_granted": False}

    @router.post("/composition-projects/{project_id}/jobs", status_code=202)
    def job(project_id: str, request: CompositionJob, owner: str = Depends(customer)):
        project, _ = owned_project(root_getter(), project_id, owner)
        if request.stage == "write_script" and not request.paid_generation_approved:
            raise HTTPException(409, "explicit paid generation approval required")
        state = composer.composition_state(project)
        if request.stage == "write_script":
            if not project.brief.approved or state["approvals"].get("brief") != composer.approval_hash(project, "brief"):
                raise HTTPException(409, "current brief approval required")
        else:
            try:
                composer.require_script(project)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
        payload = {"episode_id": project_id, "owner_id": owner, "operation": request.stage,
                   "input_hash": composer.operation_input_hash(project, request.stage)}
        key = canonical_hash({"owner": owner, "project": project_id, "operation": request.stage,
                              "key": request.idempotency_key or payload["input_hash"]})
        return enqueue(payload, "composition_" + key)

    return router


def execute_job(payload, root, should_cancel=None, report_progress=None):
    """Called by the existing durable worker queue, not a second queue system."""
    with _mutation_lock:
        project, directory = owned_project(root, payload["episode_id"], payload["owner_id"])
        if composer.operation_input_hash(project, payload["operation"]) != payload["input_hash"]:
            raise ValueError("composition changed after enqueue; submit a new job")
        def checkpoint(current=None):
            if should_cancel and should_cancel():
                raise InterruptedError("composition canceled")
        checkpoint()
        if report_progress:
            report_progress(10)
        operation = payload["operation"]
        if operation == "write_script":
            from .script_only import run_script_only
            state = composer.composition_state(project)
            if state["approvals"].get("brief") != composer.approval_hash(project, "brief"):
                raise ValueError("brief approval changed")
            # script_only owns its response persistence; final state remains a human review draft.
            project = run_script_only(project, directory, generate=True, max_revisions=1, should_cancel=should_cancel)
            result = composer.project_summary(project)
        elif operation == "discover_clips":
            from .youtube_broll import discover_project_broll
            request = composer.build_search_request(project)
            # No additional paid language-model call. Use general-topic deterministic queries.
            result = discover_project_broll(project, directory / "broll_research", request, openai_api_key="",
                                            should_cancel=should_cancel)
            project.artifacts["broll_candidates"] = result["manifest"]
            project.artifacts["broll_review_queue"] = result["review_queue"]
            project.status = "composition_clip_review"
            result = {"status": project.status, "candidate_count": result["candidate_count"],
                      "scene_count": result["scene_count"], "error_count": result["error_count"],
                      "downloads": 0, "rights_review_required": True}
        elif operation == "plan_edit":
            result = composer.plan_composition(project)
            project.status = "composition_" + result["status"]
        elif operation == "compile_edit":
            result = composer.compile_plan(project, directory)
        else:
            raise ValueError("unsupported composition operation")
        checkpoint()
        save_project(project, directory)
        if report_progress:
            report_progress(100)
        return {"episode_id": project.episode_id, **result}
