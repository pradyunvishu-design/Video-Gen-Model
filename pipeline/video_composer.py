"""Internal product adapter: customer brief -> searched footage -> reviewable edit.

This is an orchestration product, not a trained video foundation model. Ownership
is assigned by the authenticated Magic Hour backend, never by customer JSON.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from .models import Brief, Claim, EpisodeProject, Shot, Source
from .project_store import canonical_hash
from .script_profiles import ScriptProfile
from .youtube_broll import BrollDiscoveryRequest, BrollScene

MODEL_ID = "editorial-composer-v1"
PRESETS = {
    "explainer": "Explain an idea with evidence, footage and useful diagrams.",
    "tutorial": "Teach an ordered process with demonstrations and checkpoints.",
    "comparison": "Compare choices on shared criteria and show the tradeoffs.",
    "documentary": "Tell an evidence-backed story with footage and context.",
    "news": "Explain a recent development, its evidence and consequences.",
}


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class CustomerSource(StrictInput):
    title: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    text: str = Field(min_length=20, max_length=25000)
    facts: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def bounded_facts(self):
        if any(not value.strip() or len(value) > 1000 for value in self.facts):
            raise ValueError("facts must be nonempty and at most 1000 characters")
        return self


class CompositionRequest(StrictInput):
    model: Literal["editorial-composer-v1"] = MODEL_ID
    mode: Literal["preset", "custom"] = "preset"
    preset: Literal["explainer", "tutorial", "comparison", "documentary", "news"] = "explainer"
    custom_format: Literal["explainer", "tutorial", "comparison", "history", "science",
                           "case_study", "documentary", "news"] | None = None
    topic: str = Field(min_length=3, max_length=240)
    instructions: str = Field(min_length=10, max_length=5000)
    niche: str = Field(min_length=1, max_length=160)
    audience: str = Field(min_length=3, max_length=400)
    viewer_payoff: str = Field(min_length=3, max_length=400)
    target_seconds: int = Field(default=120, ge=60, le=1200, strict=True)
    width: Literal[1920] = 1920
    height: Literal[1080] = 1080
    voice: Literal["conversational", "calm_documentary", "precise_teacher", "warm_guide"] = "conversational"
    humor: Literal["none", "light"] = "light"
    timeliness: Literal["evergreen", "current"] = "evergreen"
    risk_domain: Literal["general", "health", "finance", "law", "safety"] = "general"
    footage_mode: Literal["search", "provided", "hybrid"] = "search"
    max_motion_fraction: float = Field(default=.3, ge=.1, le=.7)
    sources: list[CustomerSource] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def valid_mode(self):
        if (self.mode == "custom") != (self.custom_format is not None):
            raise ValueError("custom mode requires custom_format; presets must not supply it")
        return self


def model_catalog():
    return {"models": [{"id": MODEL_ID, "name": "Video Composer", "type": "composition_workflow",
        "status": "integration_preview", "presets": [{"id": k, "description": v} for k, v in PRESETS.items()],
        "inputs": ["customer_brief", "source_text", "searched_clip_candidates", "existing_generated_clips"],
        "outputs": ["script", "clip_review_queue", "edit_plan", "pipeline_shots"],
        "resolution": {"width": 1920, "height": 1080}, "duration_seconds": {"min": 60, "max": 1200},
        "footage_discovery": "youtube_data_api", "generated_still_broll": False,
        "publishing_enabled": False, "live_magic_hour_product": False}]}


def create_project(episode_id: str, owner_id: str, request: CompositionRequest) -> EpisodeProject:
    sources, claims = [], []
    for index, item in enumerate(request.sources, 1):
        source_id = f"source_{index}"
        sources.append(Source(id=source_id, title=item.title, url=item.url, text=item.text,
                              source_type="unknown", signal_role="unknown", publisher="Customer-supplied reference"))
        claims.extend(Claim(id=f"claim_{index}_{n}", text=fact, source_ids=[source_id])
                      for n, fact in enumerate(item.facts, 1))
    format = request.custom_format if request.mode == "custom" else request.preset
    profile = ScriptProfile(niche=request.niche, subject=request.topic, audience=request.audience,
                            viewer_payoff=request.viewer_payoff, format=format, timeliness=request.timeliness,
                            voice=request.voice, humor=request.humor, risk_domain=request.risk_domain)
    return EpisodeProject(episode_id=episode_id, scheduled_date=date.today().isoformat(),
        status="composition_brief_review", script_profile=profile, sources=sources, claims=claims,
        brief=Brief(title=request.topic, thesis=request.instructions, episode_format="deep_dive",
                    source_ids=[s.id for s in sources], claim_ids=[c.id for c in claims],
                    why_now="Current topic; verify dates" if request.timeliness == "current" else "Evergreen explanation",
                    approved=False),
        episode={"target_minutes": request.target_seconds / 60, "publishing_enabled": False,
                 "composition": {"version": "1.0", "owner_id": owner_id, "request": request.model_dump(mode="json"),
                                 "asset_annotations": {}, "approvals": {}}})


def composition_state(project):
    state = project.episode.get("composition")
    if not isinstance(state, dict) or state.get("version") != "1.0":
        raise ValueError("not a composition project")
    return state


def approval_hash(project, stage):
    state = composition_state(project)
    if stage == "brief":
        # approval itself is excluded from the digest
        brief = project.brief.model_dump(mode="json")
        brief.pop("approved", None)
        return canonical_hash({"brief": brief, "request": state["request"],
                               "sources": [s.model_dump(mode="json") for s in project.sources],
                               "claims": [c.model_dump(mode="json") for c in project.claims]})
    if stage == "script":
        return canonical_hash({"brief_hash": approval_hash(project, "brief"),
                               "script": project.script.model_dump(mode="json") if project.script else None})
    if stage == "plan":
        return canonical_hash(state.get("plan"))
    raise ValueError("unknown approval stage")


def approve(project, stage, expected_hash):
    state = composition_state(project)
    if expected_hash != approval_hash(project, stage):
        raise ValueError("content changed; review the current version")
    if stage == "brief":
        if not project.sources or not project.claims:
            raise ValueError("source text and claim records are required")
        project.brief.approved = True
    elif stage == "script":
        report = project.qc.get("fact_check", {})
        if (not project.script or report.get("passed") is not True
                or report.get("reviewed_script_hash") != canonical_hash(project.script.model_dump(mode="json"))):
            raise ValueError("script has not passed its independent review")
    elif stage == "plan":
        plan = state.get("plan") or {}
        if plan.get("status") != "ready_for_review" or plan.get("input_hash") != plan_input_hash(project):
            raise ValueError("plan has gaps, estimated timing, or stale inputs")
    state["approvals"][stage] = expected_hash
    project.episode["publishing_enabled"] = False


def require_script(project):
    state = composition_state(project)
    if not project.script or state["approvals"].get("script") != approval_hash(project, "script"):
        raise ValueError("a current approved script is required")


def build_search_request(project):
    require_script(project)
    req = CompositionRequest.model_validate(composition_state(project)["request"])
    if req.footage_mode == "provided":
        raise ValueError("footage discovery is disabled for provided-only projects")
    if len(project.script.beats) > 70:
        raise ValueError("split scripts with more than 70 beats into discovery batches")
    return BrollDiscoveryRequest(scenes=[BrollScene(scene_id=f"scene_{b.id}", beat_id=b.id,
        narration=b.narration, visual_need=b.visual_direction or b.narration[:600],
        source_hints=[req.topic, req.niche], search_context="general") for b in project.script.beats],
        published_within_days=90 if req.timeliness == "current" else None,
        caption_candidates_per_scene=0, candidates_per_scene=3, search_results_per_scene=12,
        require_reputable_or_viral=True)


def plan_input_hash(project):
    state = composition_state(project)
    return canonical_hash({"version": "composition-plan-v1", "script": approval_hash(project, "script"),
        "media": [m.model_dump() for m in project.media], "rights": project.rights,
        "annotations": state["asset_annotations"], "narration": project.narration,
        "request": state["request"]})


def operation_input_hash(project, operation):
    """Checkpoint/output writes must not invalidate retryable semantic inputs."""
    if operation == "write_script":
        from .script_profiles import script_input_hash
        return canonical_hash({"script_inputs": script_input_hash(project), "brief": approval_hash(project, "brief")})
    if operation == "discover_clips":
        return canonical_hash({"script": approval_hash(project, "script"),
                               "search": build_search_request(project).model_dump(mode="json")})
    if operation == "plan_edit":
        return plan_input_hash(project)
    if operation == "compile_edit":
        return canonical_hash({"inputs": plan_input_hash(project), "plan": approval_hash(project, "plan"),
                               "approval": composition_state(project)["approvals"].get("plan")})
    raise ValueError("unsupported composition operation")


def _timings(project):
    supplied = project.narration.get("beat_timings")
    if supplied is None:
        weights = [max(1, len(b.narration.split())) for b in project.script.beats]
        seconds = composition_state(project)["request"]["target_seconds"]
        return [seconds * weight / sum(weights) for weight in weights], "estimated"
    if [item.get("beat_id") for item in supplied] != [b.id for b in project.script.beats]:
        raise ValueError("aligned beat IDs must match the script order exactly")
    cursor, durations = 0.0, []
    for item in supplied:
        start, end = float(item["start_seconds"]), float(item["end_seconds"])
        if not all(math.isfinite(n) for n in (start, end)) or abs(start - cursor) > .01 or end <= start:
            raise ValueError("narration timing must be finite, contiguous and increasing")
        durations.append(end - start)
        cursor = end
    if not 0 < cursor <= 1320:
        raise ValueError("aligned narration exceeds composition limits")
    return durations, "aligned"


def _motion_template(beat):
    direction = beat.visual_direction.casefold()
    if beat.purpose == "comparison" or "compare" in direction:
        return "comparison"
    if any(word in direction for word in ("timeline", "chronology")):
        return "timeline"
    if any(word in direction for word in ("diagram", "mechanism", "process", "steps")):
        return "step_flow"
    if "list" in direction:
        return "list_reveal"
    return None


def plan_composition(project):
    require_script(project)
    state = composition_state(project)
    durations, timing_status = _timings(project)
    assets = {m.id: m for m in project.media}
    rights = {r.get("asset_id"): r for r in project.rights}
    used = Counter()
    motion_families = set()
    scenes, gaps = [], []
    cursor, motion_seconds = 0.0, 0.0
    total = sum(durations)
    for beat, seconds in zip(project.script.beats, durations):
        count = max(1, math.ceil(seconds / 8))
        for part in range(count):
            span = seconds / count
            template = _motion_template(beat) if part == 0 else None
            scene = {"id": f"composition_{len(scenes)+1}", "beat_id": beat.id,
                     "start_seconds": round(cursor, 4), "duration_seconds": round(span, 4),
                     "claim_ids": beat.claim_ids, "visual_need": beat.visual_direction,
                     "kind": "missing", "asset_id": None, "template": None, "source_in_seconds": 0,
                     "source_audio": "muted", "transition": "cut", "camera": "locked"}
            if template and template not in motion_families and motion_seconds + span <= total * state["request"]["max_motion_fraction"]:
                scene.update(kind="motion_graphic", template=template, reason="Explanation benefits from a structured visual")
                motion_families.add(template)
                motion_seconds += span
            else:
                for asset_id, annotation in sorted(state["asset_annotations"].items()):
                    asset, right = assets.get(asset_id), rights.get(asset_id, {})
                    if not asset or asset.qc_status != "passed" or asset.kind not in {"licensed_source_clip", "generated_video", "screen_recording"}:
                        continue
                    if right.get("rights_basis") not in {"owned", "written_permission", "public_domain", "creative_commons"}:
                        continue
                    if not right.get("attribution") or not asset.sha256:
                        continue
                    if not set(annotation.get("claim_ids", [])) & set(beat.claim_ids):
                        continue
                    if annotation.get("alignment_reviewed") is not True:
                        continue
                    if annotation.get("expected_sha256") != asset.sha256:
                        continue
                    identity = asset.sha256
                    if used[identity] >= 2:
                        continue
                    start = float(annotation.get("start_seconds", 0))
                    end = float(annotation.get("end_seconds", 0))
                    if not all(math.isfinite(n) for n in (start, end)) or start < 0 or end - start < span:
                        continue
                    scene.update(kind="clip", asset_id=asset_id, source_in_seconds=start,
                                 reason="Reviewed clip matches this claim; reuse rights recorded")
                    used[identity] += 1
                    break
            if scene["kind"] == "missing":
                gaps.append({"scene_id": scene["id"], "beat_id": beat.id, "reason": "No matching approved clip; search or review more footage"})
            scenes.append(scene)
            cursor += span
    plan = {"version": "1.0", "model": MODEL_ID, "input_hash": plan_input_hash(project),
            "status": "needs_assets" if gaps else "needs_alignment" if timing_status != "aligned" else "ready_for_review",
            "timing_status": timing_status, "duration_seconds": round(total, 4), "scenes": scenes, "gaps": gaps,
            "motion_fraction": round(motion_seconds / total, 4), "publishing_enabled": False,
            "review_required": True}
    state["plan"] = plan
    state["approvals"].pop("plan", None)
    return plan


def compile_plan(project, project_dir: Path | None = None):
    """Compile an approved edit into the existing Shot contract, not a final MP4."""
    require_script(project)
    state = composition_state(project)
    plan = state.get("plan") or {}
    if (not project_dir or plan.get("status") != "ready_for_review"
            or plan.get("input_hash") != plan_input_hash(project)
            or state["approvals"].get("plan") != approval_hash(project, "plan")):
        raise ValueError("current aligned plan, approved assets and plan review are required")
    root = Path(project_dir).resolve()
    assets = {a.id: a for a in project.media}
    compiled = []
    for scene in plan["scenes"]:
        asset = assets.get(scene["asset_id"])
        asset_path = ""
        if asset:
            path = Path(asset.path).resolve()
            if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in {".mp4", ".mov", ".webm", ".mkv"}:
                raise ValueError("clip file is not a contained registered video")
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != asset.sha256:
                raise ValueError("clip bytes changed after review")
            asset_path = str(path)
        compiled.append(Shot(id=scene["id"], beat_id=scene["beat_id"],
            asset_type="official_demo" if asset else "motion_graphic", asset_path=asset_path,
            source_id=asset.source_id if asset else None, prompt=scene["visual_need"],
            start_seconds=scene["start_seconds"], duration_seconds=scene["duration_seconds"],
            source_in_seconds=scene["source_in_seconds"], motion_style="locked", transition="cut",
            motion_template=scene["template"] or "auto", presentation="full_bleed",
            visual_category="youtube_broll" if asset else "motion_graphics",
            fallback_reason="" if asset else "explanatory_data_visualization"))
    project.shots = compiled
    project.episode["publishing_enabled"] = False
    project.status = "composition_ready_for_motion_render"
    return {"episode_id": project.episode_id, "status": project.status, "shot_count": len(compiled),
            "video_rendered": False, "publishing_enabled": False}


def project_summary(project):
    state = composition_state(project)
    next_action = ("add_sources" if not project.sources or not project.claims else "approve_brief" if not project.brief.approved
                   else "write_script" if not project.script else "review_script" if state["approvals"].get("script") != approval_hash(project, "script")
                   else ("review_clips" if project.artifacts.get("broll_review_queue") else "discover_clips")
                   if "plan" not in state else state["plan"]["status"])
    return {"project_id": project.episode_id, "model": MODEL_ID, "status": project.status,
            "next_action": next_action, "topic": project.brief.title, "preset": state["request"]["preset"],
            "footage_mode": state["request"]["footage_mode"], "publishing_enabled": False,
            "approval_hashes": {stage: approval_hash(project, stage) for stage in ("brief", "script", "plan")},
            "clip_count": len(project.media), "plan": state.get("plan")}
