"""End-to-end quality-first episode production, designed for resumable worker jobs."""
from __future__ import annotations

import json
import hashlib
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from . import (
    audio_qc, brand_assets, browser_director, captions, clip_alignment, editorial, ingest, magichour, motion_graphics, qc, research,
    remotion_renderer, storyboard, thumbnail, visual_director, visual_mix, visual_qc, weekly_news,
)
from .capture import capture_sources
from .config import (
    AUTO_APPROVE_PRIVATE_DRAFTS, CONCEPT_ANIMATIONS_ENABLED, CONCEPT_ANIMATION_MODELS,
    EPISODE_DATA_DIR, GENERATIVE_VISUALS_ENABLED,
    CAPTURE_AI_PLANNER_ENABLED, CAPTURE_PARALLELISM, FFMPEG_PRESET,
    IMAGE_FALLBACK_MODEL, IMAGE_MODEL,
    LOCAL_MOTION_RENDER_PARALLELISM, MAGIC_HOUR_MOTION_PARALLELISM,
    MAX_CAPTURE_RECORDINGS, MAX_EPISODE_CREDITS, MAX_PREMIUM_MOTION_VARIANTS,
    MIN_EPISODE_CREDITS, NARRATION_PARALLELISM, PRODUCTION_TARGET_MINUTES,
    OPENROUTER_BROWSER_MODEL, YOUTUBE_BROLL_ENABLED,
    PREMIUM_MOTION_MODELS,
    SEEDANCE_MOTION_ENABLED, SEEDANCE_MOTION_MODELS, SEEDANCE_MOTION_SHARE,
    THUMBNAIL_GENERATION_ENABLED, THUMBNAIL_RESOLUTION,
    MUSIC_DIR, PROJECT_ROOT, RENDER_PARALLELISM, RUNTIME_BOUNDARY_TOLERANCE_SECONDS,
    VISUAL_QC_PARALLELISM,
    VIDEO_FALLBACK_MODEL, VIDEO_FPS, VIDEO_H, VIDEO_MODEL, VIDEO_W, VOICE_CONSENT_ATTESTED,
    VOICE_CONSENT_FILE, VOICE_PROFILE_ID, VOICE_PROFILE_TARGET_EPISODES, VOICE_SAMPLE,
)
from .models import Brief, EpisodeProject, MediaAsset
from .project_store import canonical_hash, load_project, mark_stage, save_project, stage_is_current
from .render_v2 import concat_audio, duration, make_silence, render_project
from .screen_recording_workflow import review_screen_recording_readiness, write_screen_recording_manifest
from .tts import split_text
from .youtube_broll import build_project_broll_request, discover_project_broll
from .tooling_catalog import production_stack_receipt

CancelCheck = Callable[[], bool] | None
ProgressCallback = Callable[[int], None] | None


class CreditLimitExceeded(RuntimeError):
    pass


def validate_voice_consent(consent_path: Path, sample_path: Path) -> dict[str, str]:
    """Fail closed unless written consent is explicit and bound to this exact recording."""
    if not consent_path.is_file():
        raise PermissionError(f"written voice consent is required at {consent_path}")
    values: dict[str, str] = {}
    for raw_line in consent_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().upper()] = value.strip()
    required_yes = ["CONSENT_TO_AI_VOICE_CLONING", "CONSENT_TO_COMMERCIAL_PUBLICATION"]
    missing = [key for key in required_yes if values.get(key, "").casefold() != "yes"]
    required_text = ["VOICE_OWNER", "SERVICE", "DATE", "SIGNATURE", "SAMPLE_SHA256"]
    missing.extend(key for key in required_text if not values.get(key) or values[key].startswith("<"))
    if missing:
        raise PermissionError(f"voice consent is incomplete: {sorted(set(missing))}")
    if "magic hour" not in values["SERVICE"].casefold():
        raise PermissionError("voice consent must explicitly name Magic Hour")
    try:
        date.fromisoformat(values["DATE"])
    except ValueError as exc:
        raise PermissionError("voice consent DATE must use YYYY-MM-DD") from exc
    actual_hash = hashlib.sha256(sample_path.read_bytes()).hexdigest()
    if values["SAMPLE_SHA256"].casefold() != actual_hash:
        raise PermissionError("voice consent does not match the selected voice sample")
    return values


def voice_rights_record(consent_path: Path, sample_path: Path) -> dict[str, str | bool]:
    """Return auditable voice provenance without blocking private drafts on paperwork."""
    sample_hash = hashlib.sha256(sample_path.read_bytes()).hexdigest()
    if consent_path.is_file():
        try:
            values = validate_voice_consent(consent_path, sample_path)
            return {
                "status": "documented",
                "sample_sha256": sample_hash,
                "consent_record": str(consent_path),
                "voice_owner": values["VOICE_OWNER"],
                "documentation_pending": False,
                "profile_id": VOICE_PROFILE_ID,
                "target_episode_count": VOICE_PROFILE_TARGET_EPISODES,
            }
        except PermissionError:
            if not VOICE_CONSENT_ATTESTED:
                raise
    if not VOICE_CONSENT_ATTESTED:
        raise PermissionError(
            "voice permission has not been attested; set VOICE_CONSENT_ATTESTED=true only after permission is granted"
        )
    return {
        "status": "consent_attested_documentation_pending",
        "sample_sha256": sample_hash,
        "consent_record": "",
        "voice_owner": "user-attested approved speaker",
        "documentation_pending": True,
        "profile_id": VOICE_PROFILE_ID,
        "target_episode_count": VOICE_PROFILE_TARGET_EPISODES,
    }


def _checkpoint(should_cancel: CancelCheck) -> None:
    if should_cancel and should_cancel():
        raise InterruptedError("job canceled by reviewer")


def _report(callback: ProgressCallback, value: int) -> None:
    if callback:
        callback(value)


def _resolve(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def _episode_dir(episode_id: str) -> Path:
    return EPISODE_DATA_DIR / episode_id


def _claims_stage_input(project: EpisodeProject) -> dict:
    brief = project.brief.model_dump(mode="json")
    # claim_ids is produced by this stage; including it makes the stage invalidate itself on resume.
    brief.pop("claim_ids", None)
    sources = []
    for source in project.sources:
        source_data = source.model_dump(mode="json")
        # Browser capture runs after editorial verification and must not invalidate it.
        source_data.pop("capture_status", None)
        sources.append(source_data)
    return {
        "brief": brief,
        "sources": sources,
    }


def refresh_sources() -> dict:
    research_dir = EPISODE_DATA_DIR.parent / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    stories = ingest.collect()
    sources = research.enrich_stories(stories)
    payload = {
        "schema_version": "2.0", "refreshed_at": time.time(),
        "stories": stories, "sources": [source.model_dump(mode="json") for source in sources],
    }
    target = research_dir / "latest_sources.json"
    target.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return {"status": "complete", "story_count": len(stories), "source_count": len(sources), "path": str(target)}


def _add_credits(project: EpisodeProject, amount: int) -> None:
    total = int(project.costs.get("magic_hour_credits", 0)) + int(amount or 0)
    project.costs["magic_hour_credits"] = total
    limit = int(project.episode.get("credit_limit", MAX_EPISODE_CREDITS))
    if total > limit:
        project.status = "credit_approval_required"
        project.episode["credit_limit"] = limit
        project.episode["requested_credit_limit"] = max(total, limit + 1000)
        save_project(project, _episode_dir(project.episode_id))
        raise CreditLimitExceeded(f"episode credit ceiling exceeded: {total} > {limit}")


def _reconcile_credits(project: EpisodeProject, submitted: dict, completed: dict) -> int:
    reserved = int(submitted.get("credits_charged", 0) or 0)
    final = int(completed.get("credits_charged", reserved) or reserved)
    if final > reserved:
        _add_credits(project, final - reserved)
    return final


def _recent_topic_history(days: int = 14) -> list[str]:
    cutoff = date.today() - timedelta(days=days)
    topics: list[str] = []
    for project_file in EPISODE_DATA_DIR.glob("episode_*/episode_project.json"):
        try:
            project = load_project(project_file.parent)
            if project.created_at.date() < cutoff or not project.brief:
                continue
            clusters = sorted({source.cluster_id for source in project.sources if source.cluster_id})
            entities = sorted({entity.casefold() for source in project.sources for entity in source.entities})[:12]
            topics.append(f"{project.brief.title} | clusters={clusters} | entities={entities}")
        except Exception:
            continue
    return topics


def create_weekly_slate(start: date | None = None, recent_topics: list[str] | None = None) -> dict:
    first = start or date.today()
    slate_id = f"slate_{first:%Y%m%d}"
    slate_dir = EPISODE_DATA_DIR / slate_id
    slate_dir.mkdir(parents=True, exist_ok=True)
    cache = EPISODE_DATA_DIR.parent / "research" / "latest_sources.json"
    if cache.exists():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if time.time() - float(cached.get("refreshed_at", 0)) <= 8 * 3600:
            stories = cached["stories"]
            from .models import Source
            sources = [Source.model_validate(item) for item in cached["sources"]]
        else:
            refreshed = refresh_sources()
            cached = json.loads(Path(refreshed["path"]).read_text(encoding="utf-8"))
            stories = cached["stories"]
            from .models import Source
            sources = [Source.model_validate(item) for item in cached["sources"]]
    else:
        refreshed = refresh_sources()
        cached = json.loads(Path(refreshed["path"]).read_text(encoding="utf-8"))
        stories = cached["stories"]
        from .models import Source
        sources = [Source.model_validate(item) for item in cached["sources"]]
    (slate_dir / "stories.json").write_text(json.dumps(stories, indent=2), encoding="utf-8")
    briefs = editorial.plan_weekly_slate(sources, recent_topics=recent_topics or _recent_topic_history())
    episodes = []
    for index, brief in enumerate(briefs):
        scheduled = first + timedelta(days=index)
        episode_id = f"episode_{scheduled:%Y%m%d}_{index + 1:02d}"
        selected = [source for source in sources if source.id in brief.source_ids]
        auto_approved = AUTO_APPROVE_PRIVATE_DRAFTS
        brief.approved = auto_approved
        project = EpisodeProject(
            episode_id=episode_id, scheduled_date=scheduled.isoformat(), brief=brief,
            sources=selected,
            episode={
                "format": brief.episode_format,
                "creative_profile": "hermes-proof-first-v1",
                "slate_id": slate_id,
                "publishing_enabled": False,
                "approval_mode": "automatic_private_drafts" if auto_approved else "human_review",
            },
            status="approved_for_production" if auto_approved else "awaiting_slate_approval",
        )
        if auto_approved:
            project.review.slate_status = "approved"
        project.episode["story_cluster_ids"] = sorted({source.cluster_id for source in selected if source.cluster_id})
        project.episode["entity_fingerprint"] = sorted({
            entity.casefold() for source in selected for entity in source.entities
        })[:12]
        save_project(project, _episode_dir(episode_id))
        episodes.append({"episode_id": episode_id, "scheduled_date": scheduled.isoformat(), "brief": brief.model_dump(mode="json")})
    slate = {
        "schema_version": "2.0", "slate_id": slate_id, "episodes": episodes,
        "status": "auto_approved_private_drafts" if AUTO_APPROVE_PRIVATE_DRAFTS else "awaiting_approval",
    }
    (slate_dir / "slate.json").write_text(json.dumps(slate, indent=2, default=str), encoding="utf-8")
    return slate


def create_news_weekly(start: date | None = None, recent_topics: list[str] | None = None) -> dict:
    """Create one ranked ten-minute News Weekly project from the freshest research cache."""
    scheduled = start or date.today()
    slate_id = f"news_weekly_{scheduled:%Y%m%d}"
    slate_dir = EPISODE_DATA_DIR / slate_id
    slate_dir.mkdir(parents=True, exist_ok=True)
    cache = EPISODE_DATA_DIR.parent / "research" / "latest_sources.json"
    if not cache.exists() or time.time() - float(json.loads(cache.read_text(encoding="utf-8")).get("refreshed_at", 0)) > 8 * 3600:
        refreshed = refresh_sources()
        cache = Path(refreshed["path"])
    cached = json.loads(cache.read_text(encoding="utf-8"))
    from .models import Source
    sources = [Source.model_validate(item) for item in cached["sources"]]
    brief, digest_plan = weekly_news.plan_weekly_digest(
        sources, recent_topics=recent_topics or _recent_topic_history(days=21),
    )
    selected = [source for source in sources if source.id in brief.source_ids]
    auto_approved = AUTO_APPROVE_PRIVATE_DRAFTS
    brief.approved = auto_approved
    episode_id = f"episode_{scheduled:%Y%m%d}_news_weekly"
    model_test_queue = [
        {
            "story_id": story["story_id"],
            "headline": story["headline"],
            "goal": story["demo_goal"],
            "source_ids": story["source_ids"],
            "profile": "google_manual",
            "website": "",
            "allow_generation": False,
            "status": "awaiting_demo_url_and_approval",
        }
        for story in digest_plan["stories"] if story["model_test_candidate"]
    ]
    project = EpisodeProject(
        episode_id=episode_id,
        scheduled_date=scheduled.isoformat(),
        brief=brief,
        sources=selected,
        episode={
            "format": "weekly_roundup",
            "creative_profile": "hermes-proof-first-v1",
            "show_name": "THE WEEK IN AI",
            "show_tagline": "The tech and AI news that actually mattered, in under ten minutes",
            "target_minutes": 10,
            "intro_seconds": 8,
            "digest_plan": digest_plan,
            "model_test_queue": model_test_queue,
            "slate_id": slate_id,
            "publishing_enabled": False,
            "approval_mode": "automatic_private_drafts" if auto_approved else "human_review",
        },
        status="approved_for_production" if auto_approved else "awaiting_slate_approval",
    )
    if auto_approved:
        project.review.slate_status = "approved"
    project.episode["story_cluster_ids"] = sorted({source.cluster_id for source in selected if source.cluster_id})
    project.episode["entity_fingerprint"] = sorted({
        entity.casefold() for source in selected for entity in source.entities
    })[:20]
    save_project(project, _episode_dir(episode_id))
    slate = {
        "schema_version": "2.0",
        "slate_id": slate_id,
        "show": "THE WEEK IN AI",
        "episodes": [{
            "episode_id": episode_id,
            "scheduled_date": scheduled.isoformat(),
            "brief": brief.model_dump(mode="json"),
            "digest_plan": digest_plan,
            "model_test_queue": model_test_queue,
        }],
        "status": "auto_approved_private_drafts" if auto_approved else "awaiting_approval",
    }
    (slate_dir / "slate.json").write_text(json.dumps(slate, indent=2, default=str), encoding="utf-8")
    return slate


def configure_news_weekly_model_test(
    episode_id: str, story_id: str, website: str, *, inputs: dict[str, str] | None = None,
    allow_generation: bool = False,
) -> dict:
    """Bind a reviewed product URL and harmless inputs to a planned weekly model test."""
    from urllib.parse import urlsplit
    from .product_demo import DemoSpec

    run_dir = _episode_dir(episode_id)
    project = load_project(run_dir)
    queue = project.episode.get("model_test_queue", [])
    item = next((candidate for candidate in queue if candidate.get("story_id") == story_id), None)
    if item is None:
        raise KeyError(f"unknown model-test story: {story_id}")
    host = urlsplit(website).hostname or ""
    spec = DemoSpec(
        website=website,
        goal=item["goal"],
        narration="",
        duration_seconds=28,
        profile=item.get("profile", "google_manual"),
        allowed_hosts=[host],
        inputs=inputs or {"prompt": "Create one clear test output that is safe, neutral, and easy to evaluate."},
        allow_generation=allow_generation,
    )
    item.update({
        "website": str(spec.website), "allowed_hosts": spec.allowed_hosts, "inputs": spec.inputs,
        "allow_generation": spec.allow_generation, "status": "approved_for_capture",
    })
    save_project(project, run_dir)
    return {"episode_id": episode_id, "story_id": story_id, "status": item["status"], "spec": spec.model_dump(mode="json")}


def run_news_weekly_model_tests(episode_id: str) -> dict:
    """Run only explicitly configured tests and persist their deterministic browser recordings."""
    run_dir = _episode_dir(episode_id)
    project = load_project(run_dir)
    results = _run_configured_model_tests(project, run_dir)
    save_project(project, run_dir)
    return {"episode_id": episode_id, "tests": results}


def _run_configured_model_tests(project: EpisodeProject, run_dir: Path) -> list[dict]:
    """Execute approved browser demos inside production; failures retain a scoped fallback."""
    from .product_demo import DemoSpec, generate_demo

    results = []
    for item in project.episode.get("model_test_queue", []):
        if item.get("status") == "complete" and Path(item.get("video", "")).is_file():
            results.append({"story_id": item["story_id"], "status": "reused", "video": item["video"]})
            continue
        if item.get("status") != "approved_for_capture":
            continue
        spec = DemoSpec(
            website=item["website"], goal=item["goal"], duration_seconds=28,
            profile=item.get("profile", "google_manual"), allowed_hosts=item.get("allowed_hosts", []),
            inputs=item.get("inputs", {}), allow_generation=bool(item.get("allow_generation")),
        )
        try:
            metadata = generate_demo(spec, run_dir / "model_tests" / item["story_id"])
            item.update({"status": "complete", "video": metadata["video"], "metadata": metadata})
            results.append({"story_id": item["story_id"], "status": "complete", "video": metadata["video"]})
        except Exception as exc:
            item.update({
                "status": "capture_failed",
                "capture_error": f"{type(exc).__name__}: {exc}",
                "retry_scope": "model_test_capture",
            })
            results.append({
                "story_id": item["story_id"], "status": "capture_failed",
                "error": item["capture_error"],
            })
    return results


def _assign_weekly_model_test_assets(project: EpisodeProject) -> None:
    for item in project.episode.get("model_test_queue", []):
        video = Path(item.get("video", ""))
        if item.get("status") != "complete" or not video.is_file() or not project.script:
            continue
        story_sources = set(item.get("source_ids", []))
        candidate_beats = [
            beat for beat in project.script.beats
            if beat.purpose in {"model_test", "test_setup", "observation"} and story_sources.intersection(beat.source_ids)
        ]
        if not candidate_beats:
            continue
        beat_ids = {beat.id for beat in candidate_beats}
        assigned = 0
        for shot in project.shots:
            if shot.beat_id not in beat_ids or assigned >= 3:
                continue
            shot.asset_type = "official_demo"
            shot.asset_path = str(video)
            shot.source_in_seconds = min(assigned * 4.0, 12.0)
            shot.motion_style = "locked"
            shot.presentation = "full_bleed"
            shot.rights_note = "Original on-screen product test captured from the channel's authenticated local browser session."
            assigned += 1
        if not any(asset.path == str(video) for asset in project.media):
            demo_quality = item.get("metadata", {}).get("quality", {})
            project.media.append(MediaAsset(
                id=f"browser_demo_{item['story_id']}", kind="browser_demo", path=str(video),
                source_id=next(iter(story_sources), None),
                sha256=str(item.get("metadata", {}).get("video_sha256", "")),
                qc_status="passed" if demo_quality.get("status") in {"accepted", "cached"} else "pending",
                qc_notes=[
                    "Captured from an explicitly configured News Weekly model-test job.",
                    "Screen review: " + json.dumps(demo_quality, sort_keys=True) if demo_quality else
                    "Screen review metadata is unavailable; inspect before publication.",
                ],
            ))
        asset_id = f"browser_demo_{item['story_id']}"
        if not any(entry.get("asset_id") == asset_id for entry in project.rights):
            project.rights.append({
                "asset_id": asset_id,
                "source_id": next(iter(story_sources), None),
                "source_url": item.get("website", ""),
                "capture_mode": "approved_authenticated_product_demo",
                "rights_basis": "original channel-operated product demonstration",
                "allow_generation": bool(item.get("allow_generation")),
                "human_review_required": True,
            })


def review_slate(slate_id: str, decisions: list[dict]) -> dict:
    slate_path = EPISODE_DATA_DIR / slate_id / "slate.json"
    slate = json.loads(slate_path.read_text(encoding="utf-8"))
    by_id = {item["episode_id"]: item for item in decisions}
    approved_order = sorted(
        (item for item in decisions if item.get("action", "approve") == "approve" and item.get("approved", True)),
        key=lambda item: int(item.get("order", 999)),
    )
    scheduled_by_id = {
        item["episode_id"]: (date.fromisoformat(slate["episodes"][0]["scheduled_date"]) + timedelta(days=index)).isoformat()
        for index, item in enumerate(approved_order)
    }
    for item in slate["episodes"]:
        project_dir = _episode_dir(item["episode_id"])
        project = load_project(project_dir)
        decision = by_id.get(
            project.episode_id,
            {"approved": False, "action": "revise", "notes": "No decision supplied"},
        )
        action = decision.get("action", "approve" if decision.get("approved") else "revise")
        approved = action == "approve" and bool(decision.get("approved", True))
        project.brief.approved = approved
        project.brief.review_notes = decision.get("notes", "")
        if approved:
            project.scheduled_date = scheduled_by_id[project.episode_id]
            project.review.slate_status = "approved"
            project.status = "approved_for_production"
        elif action == "skip":
            project.review.slate_status = "rejected"
            project.status = "skipped"
        else:
            project.review.slate_status = "revision_requested"
            project.status = "brief_revision_requested"
        save_project(project, project_dir)
    slate["status"] = "reviewed"
    slate_path.write_text(json.dumps(slate, indent=2), encoding="utf-8")
    return slate


def _generate_narration(
    project: EpisodeProject, run_dir: Path, should_cancel: CancelCheck = None, cache_key: str = "default",
) -> Path:
    consent = _resolve(VOICE_CONSENT_FILE)
    sample = _resolve(VOICE_SAMPLE)
    if not sample.exists():
        raise FileNotFoundError(f"voice sample is missing at {sample}")
    rights = voice_rights_record(consent, sample)
    project.episode["voice_rights"] = rights
    audio_dir = run_dir / "audio" / cache_key[:16]
    audio_dir.mkdir(parents=True, exist_ok=True)
    sample_path = magichour.upload_file(str(sample), "audio")
    narration_parts: list[Path] = []
    blocks = _narration_blocks(project.script.beats)
    pending_chunks: list[tuple[str, int, str, Path]] = []
    for block_index, block in enumerate(blocks, start=1):
        block_id = f"block_{block_index:02d}"
        for chunk_index, chunk in enumerate(split_text(block["text"])):
            destination = audio_dir / f"{block_id}_{chunk_index:02d}.mp3"
            if not destination.exists():
                pending_chunks.append((block_id, chunk_index, chunk, destination))

    def generate_chunk(task: tuple[str, int, str, Path]) -> tuple[Path, int]:
        block_id, chunk_index, chunk, destination = task
        _checkpoint(should_cancel)
        job_id = magichour.voice_clone(
            chunk, sample_path, f"{project.episode_id}-{block_id}-{chunk_index}"
        )
        job = magichour.wait_audio(job_id)
        magichour.download(job, destination)
        return destination, int(job.get("credits_charged", 0))

    if pending_chunks:
        workers = min(NARRATION_PARALLELISM, len(pending_chunks))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="narration") as executor:
            futures = [executor.submit(generate_chunk, task) for task in pending_chunks]
            for future in as_completed(futures):
                _destination, charged = future.result()
                _add_credits(project, charged)
                save_project(project, run_dir)

    for block_index, block in enumerate(blocks, start=1):
        block_id = f"block_{block_index:02d}"
        if block["pause_before_ms"]:
            pause = audio_dir / f"{block_id}_pause_before_{block['pause_before_ms']}.wav"
            if not pause.exists():
                make_silence(pause, block["pause_before_ms"])
            narration_parts.append(pause)
        chunk_paths = []
        for chunk_index, chunk in enumerate(split_text(block["text"])):
            _checkpoint(should_cancel)
            destination = audio_dir / f"{block_id}_{chunk_index:02d}.mp3"
            if not destination.exists():
                raise RuntimeError(f"narration generation did not produce {destination.name}")
            chunk_key = f"{block_id}_{chunk_index:02d}"
            cached_review = project.qc.setdefault("narration_chunks", {}).get(chunk_key)
            if cached_review and cached_review.get("passed"):
                chunk_review = cached_review
            else:
                chunk_review = audio_qc.review_narration(
                    destination,
                    chunk,
                    sample,
                    enforce_pacing=False,
                    max_unmatched_words=8,
                    min_intelligibility=0.85,
                )
                project.qc["narration_chunks"][chunk_key] = chunk_review
            if not chunk_review["passed"]:
                project.status = "audio_revision_required"
                save_project(project, run_dir)
                raise RuntimeError(
                    f"narration chunk {chunk_key} failed English/speaker QC: "
                    + "; ".join(chunk_review["failures"])
                )
            chunk_paths.append(destination)
        block_destination = audio_dir / f"{block_id}.wav"
        if not block_destination.exists():
            concat_audio(chunk_paths, block_destination)
        narration_parts.append(block_destination)
        if block["pause_after_ms"]:
            pause = audio_dir / f"{block_id}_pause_after_{block['pause_after_ms']}.wav"
            if not pause.exists():
                make_silence(pause, block["pause_after_ms"])
            narration_parts.append(pause)
    narration = run_dir / f"narration_{cache_key[:16]}.wav"
    if not narration.exists():
        concat_audio(narration_parts, narration)
    project.narration = {
        "path": str(narration), "duration_seconds": duration(narration),
        "voice_sample": str(sample), "voice_rights": rights,
        "performance_blocks": [{key: value for key, value in block.items() if key != "text"} for block in blocks],
    }
    save_project(project, run_dir)
    return narration


def _narration_blocks(beats: list, limit: int = 940) -> list[dict]:
    """Merge adjacent beats into longer TTS performances to reduce per-request voice drift."""
    blocks: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current:
            blocks.append(current)
            current = None

    for beat in beats:
        text = beat.narration
        for pronunciation in beat.pronunciations:
            text = text.replace(pronunciation.term, pronunciation.spoken_as)
        hard_entry = beat.delivery.pause_before_ms >= 700
        candidate = text if current is None else current["text"] + " " + text
        if current and (hard_entry or len(candidate) > limit):
            flush()
        if current is None:
            current = {
                "text": text,
                "beat_ids": [beat.id],
                "pause_before_ms": beat.delivery.pause_before_ms,
                "pause_after_ms": beat.delivery.pause_after_ms,
            }
        else:
            current["text"] += " " + text
            current["beat_ids"].append(beat.id)
            current["pause_after_ms"] = beat.delivery.pause_after_ms
        if beat.delivery.pause_after_ms >= 750:
            flush()
    flush()
    if any(len(block["text"]) > limit for block in blocks):
        raise ValueError("narration performance block exceeds the Magic Hour text safety limit")
    return blocks


def _capture_and_assign(project: EpisodeProject, run_dir: Path, *, canary: bool = False) -> dict[str, dict]:
    used_source_ids = {shot.source_id for shot in project.shots if shot.source_id}
    selected_sources = [source for source in project.sources if source.id in used_source_ids]
    directions: dict[str, list[str]] = {source.id: [] for source in selected_sources}
    if project.script:
        for beat in project.script.beats:
            for source_id in beat.source_ids:
                if source_id in directions and beat.visual_direction not in directions[source_id]:
                    directions[source_id].append(beat.visual_direction)
    recording_demand = {
        source.id: max(
            (
                3 if shot.asset_type == "official_demo" else
                2 if shot.asset_type == "screen_recording" else
                1 if shot.asset_type == "screenshot" else 0
            )
            for shot in project.shots if shot.source_id == source.id
        )
        for source in selected_sources
    }
    source_order = {source.id: index for index, source in enumerate(selected_sources)}
    selected_sources.sort(key=lambda source: (-recording_demand[source.id], source_order[source.id]))
    captures = capture_sources(
        selected_sources,
        run_dir / "captures",
        max_recordings=1 if canary else MAX_CAPTURE_RECORDINGS,
        planner=browser_director.plan_capture if CAPTURE_AI_PLANNER_ENABLED else None,
        visual_directions_by_source=directions,
    )
    by_source = {item["source_id"]: item for item in captures}
    project.captures = [item["record"] for item in captures]
    for source in project.sources:
        item = by_source.get(source.id, {})
        source.capture_status = "complete" if item.get("screenshots") else "failed"
    licensed_paths = {
        asset.path for asset in project.media if asset.kind == "licensed_source_clip"
    }
    artifact_use: dict[str, int] = {}
    for shot in project.shots:
        if shot.asset_path in licensed_paths:
            artifact_use[shot.asset_path] = artifact_use.get(shot.asset_path, 0) + 1
            continue
        if shot.visual_category == "youtube_broll":
            continue
        capture = by_source.get(shot.source_id or "")
        if not capture:
            continue
        if shot.asset_type in {"screen_recording", "official_demo"} and capture.get("recording"):
            recordings = capture.get("recordings") or [capture["recording"]]
            available = [path for path in recordings if artifact_use.get(path, 0) < 2]
            if available:
                shot.asset_path = min(available, key=lambda path: (artifact_use.get(path, 0), path))
                artifact_use[shot.asset_path] = artifact_use.get(shot.asset_path, 0) + 1
            else:
                # A third play of the same capture reads as filler. Preserve
                # the citation but switch the picture to an original graphic.
                shot.asset_type = "motion_graphic"
                shot.asset_path = ""
                shot.motion_template = "evidence_focus"
        elif shot.asset_type == "screenshot" and capture.get("editorial_stills"):
            stills = capture["editorial_stills"]
            available = [path for path in stills if artifact_use.get(path, 0) < 2]
            if available:
                shot.asset_path = min(available, key=lambda path: (artifact_use.get(path, 0), path))
                artifact_use[shot.asset_path] = artifact_use.get(shot.asset_path, 0) + 1
                shot.presentation = "full_bleed"
            else:
                shot.asset_type = "motion_graphic"
                shot.asset_path = ""
                shot.motion_template = "evidence_focus"

    beat_by_id = {beat.id: beat for beat in project.script.beats} if project.script else {}
    source_by_id = {source.id: source for source in project.sources}
    artifact_labels = {
        artifact.path: artifact.label
        for capture in project.captures
        for artifact in capture.artifacts
    }
    artifact_modes = {
        artifact.path: artifact.capture_mode
        for capture in project.captures
        for artifact in capture.artifacts
    }
    artifact_texts = {
        artifact.path: artifact.visible_text
        for capture in project.captures
        for artifact in capture.artifacts
    }
    artifact_quality = {
        artifact.path: artifact.quality
        for capture in project.captures
        for artifact in capture.artifacts
    }
    # A computer-frame treatment is an occasional editorial device for a real
    # UI detail, never the default presentation for web evidence. Most source
    # material stays full-bleed, which is clearer at 1080p and avoids a wall of
    # identical browser cards.
    ui_frame_budget = 0 if canary else min(2, max(1, round(len(project.shots) / 45)))
    ui_frame_candidates = [
        shot for shot in project.shots
        if shot.asset_type == "screenshot" and shot.asset_path
        and artifact_modes.get(shot.asset_path) in {"element", "hover", "focus"}
        and shot.beat_id in beat_by_id
        and beat_by_id[shot.beat_id].purpose in {"model_test", "test_setup", "observation", "evidence"}
    ]
    for shot in sorted(ui_frame_candidates, key=lambda item: item.start_seconds)[:ui_frame_budget]:
        shot.presentation = "editorial_card"
    screenshot_candidates = [
        shot for shot in project.shots
        if shot.asset_type == "screenshot" and shot.asset_path and Path(shot.asset_path).is_file()
        and shot.beat_id in beat_by_id
        and visual_director.annotation_is_warranted(beat_by_id[shot.beat_id])
    ]
    for shot in project.shots:
        if shot.asset_type == "screenshot":
            shot.annotations = []
    screenshot_candidates.sort(
        key=lambda shot: (
            -visual_director.annotation_priority(beat_by_id[shot.beat_id]),
            shot.start_seconds,
        )
    )
    episode_seconds = max(
        (shot.start_seconds + shot.duration_seconds for shot in project.shots),
        default=0,
    )
    annotation_budget = 1 if canary else min(6, max(2, round(episode_seconds / 100)))
    for shot in screenshot_candidates[:annotation_budget]:
        beat = beat_by_id[shot.beat_id]
        source = source_by_id.get(shot.source_id or "")
        annotation = visual_director.plan_annotation(
            Path(shot.asset_path), beat,
            source_title=source.title if source else "",
            artifact_label=artifact_labels.get(shot.asset_path, ""),
            artifact_text=artifact_texts.get(shot.asset_path, ""),
            exact_text_region=artifact_quality.get(shot.asset_path, {}).get("exact_text_region"),
        )
        if annotation is None:
            continue
        shot.annotations = [annotation]
        # Keep the captured page centered. The verified annotation points to
        # the evidence without dragging the entire screengrab off axis.
        shot.focus_x = 0.5
        shot.focus_y = 0.5
        shot.motion_style = "push_in"
    for shot in project.shots:
        if shot.asset_type in {"screenshot", "screen_recording", "official_demo"}:
            shot.focus_x = 0.5
            shot.focus_y = 0.5
    return by_source


def _acquire_screen_recordings_for_project(
    project: EpisodeProject,
    run_dir: Path,
    *,
    canary: bool = False,
    should_cancel: CancelCheck = None,
) -> dict:
    """Acquire, register and verify the screen clips required by the storyboard."""
    _checkpoint(should_cancel)
    model_tests = _run_configured_model_tests(project, run_dir)
    if model_tests:
        project.qc["automated_browser_demos"] = {
            "passed": all(item["status"] in {"complete", "reused"} for item in model_tests),
            "results": model_tests,
            "fallback": "public source capture and deterministic motion remain available",
        }
    _checkpoint(should_cancel)
    _capture_and_assign(project, run_dir, canary=canary)
    _assign_weekly_model_test_assets(project)
    manifest_path = write_screen_recording_manifest(project, run_dir)
    readiness = review_screen_recording_readiness(project, run_dir)
    project.artifacts["screen_recording_manifest"] = str(manifest_path)
    project.qc["screen_recording_readiness"] = readiness
    save_project(project, run_dir)
    if not readiness["passed"]:
        project.status = "screen_recording_review_required"
        save_project(project, run_dir)
        raise RuntimeError(
            "screen recordings are not ready: " + "; ".join(readiness["failures"][:8])
        )
    return {"manifest": str(manifest_path), "qc": readiness, "model_tests": model_tests}


def acquire_episode_screen_recordings(
    episode_id: str,
    *,
    should_cancel: CancelCheck = None,
    report_progress: ProgressCallback = None,
) -> dict:
    """Worker-stage entry point for acquiring or retrying only an episode's screen clips."""
    run_dir = _episode_dir(episode_id)
    project = load_project(run_dir)
    if not project.script or not project.shots:
        raise ValueError("screen recording acquisition requires an approved script and storyboard")
    _report(report_progress, 10)
    result = _acquire_screen_recordings_for_project(
        project, run_dir, should_cancel=should_cancel,
    )
    project.status = "screen_recordings_ready"
    save_project(project, run_dir)
    _report(report_progress, 100)
    return {
        "episode_id": episode_id,
        "status": project.status,
        **result,
        "artifacts": {"screen_recording_manifest": result["manifest"]},
    }


def _video_prompt(prompt: str) -> str:
    return (
        "Premium broadcast motion graphic based strictly on the supplied clean design plate. "
        f"EDITORIAL IDEA: {prompt}. Animate only the existing geometric elements with restrained 2.5D depth, "
        "precise bezier easing, realistic material response, soft studio lighting, and physically coherent parallax. "
        "Keep the original palette, layout, object count, and geometry recognizable from first frame to last. "
        "Use a stabilized virtual camera with one slow controlled move, a level horizon, no handheld motion, no shake, "
        "no whip pan, and no sudden zoom. No photoreal people, faces, hands, fantasy objects, glowing sci-fi brain, "
        "generic AI-art aesthetic, fake interface, or stock-photo scene. No text, letters, numbers, captions, logos, watermark, or audio. "
        "TEMPORAL CONSISTENCY: no morphing, melting, flicker, duplicated shapes, invented objects, or unstable edges."
    )


def _concept_video_prompt(prompt: str) -> str:
    return (
        "Original overhead educational whiteboard animation constrained by the supplied start and completed end boards. "
        f"CONCEPT TO EXPLAIN: {prompt}. Show one clear cause-and-effect transformation using two to four simple drawn objects. "
        "A real black felt-tip pen, with only the pen tip and a small edge of natural fingertips visible, draws every line in "
        "chronological reading order on warm ivory paper. Use natural imperfect ink pressure, subtle line wobble, believable "
        "human timing, and exactly one muted coral emphasis stroke. The motion must teach the mechanism, not decorate the frame. "
        "Use a completely locked overhead camera: no handheld motion, no shake, no pan, no zoom, no cuts, and no parallax. "
        "Every mark appears only where the pen touches and remains fixed afterward. No extra hands, malformed fingers, floating pen, "
        "morphing or disappearing lines, mascots, glossy 3D, fake interface, or generic AI-video look. No text, letters, numbers, "
        "logos, captions, watermark, or audio. Hold the completed board long enough to understand it. "
        "This is an explanatory visualization, not documentary evidence and not an imitation of any existing animation studio."
    )


def _seedance_editorial_prompt(prompt: str) -> str:
    """Direct a silent horizontal insert while deterministic layers own facts and type."""
    return (
        "Original 16:9 horizontal editorial motion insert for long-form technology journalism, based strictly on "
        "the supplied text-free design plate. "
        f"IDEA TO VISUALIZE: {prompt}. Use one dominant proof object or simple process metaphor, no more than three "
        "focal groups, generous negative space, tactile paper or matte materials, soft physically coherent shadows, "
        "and a restrained neutral newsroom palette with at most one localized clay, moss, or official-brand accent. "
        "Animate one semantic action per narration clause: enter, connect or transform, resolve, then hold a clean "
        "final frame for one second. Use crisp editorial 2D or restrained 2.5D construction, decisive 8-to-16-frame "
        "entrances, precise ease-out or ease-in-out curves, and a completely stable level camera. No vertical or 9:16 "
        "composition, no handheld motion, no shake, no constant zoom, no orbit, no whip, no spin, and no parallax drift. "
        "No people, faces, hands, fake product interface, photoreal stock scene, glossy plastic icon, neon, large yellow "
        "field, purple-blue gradient, glass card, ambient glow, portal, circuitry, or generic AI-art aesthetic. "
        "No text, letters, numbers, captions, logos, source labels, or watermark. No audio. Exact typography, official marks, "
        "data, and citations are added deterministically after generation. TEMPORAL CONSISTENCY: preserve the supplied "
        "object identities, geometry, palette, and count with no morphing, melting, flicker, duplication, or unstable edges."
    )


def _premium_model_routes() -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for value in PREMIUM_MOTION_MODELS:
        model, separator, resolution = value.rpartition(":")
        # The channel has one delivery contract: every generated clip is exactly 1080p.
        routes.append((model if separator else value, "1080p"))
    return routes or [(VIDEO_MODEL, "1080p"), (VIDEO_FALLBACK_MODEL, "1080p")]


def _concept_model_routes() -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for value in CONCEPT_ANIMATION_MODELS:
        model, separator, _resolution = value.rpartition(":")
        routes.append((model if separator else value, "1080p"))
    return routes or [("kling-3.0", "1080p"), ("veo3.1", "1080p")]


def _seedance_model_routes() -> list[tuple[str, str]]:
    """Return the current 1080p Seedance route followed by quality fallbacks."""
    routes: list[tuple[str, str]] = []
    for value in SEEDANCE_MOTION_MODELS:
        model, separator, _resolution = value.rpartition(":")
        model = model if separator else value
        # Magic Hour's Seedance 2.0 route currently tops out below the channel's
        # 1080p contract.  `seedance` is the documented 1080p-capable route.
        if model.casefold() == "seedance-2.0":
            continue
        routes.append((model, "1080p"))
    return routes or [("seedance", "1080p"), ("kling-3.0", "1080p"), ("veo3.1", "1080p")]


def _assert_no_generated_stills(project: EpisodeProject) -> None:
    forbidden_shots = [shot.id for shot in project.shots if shot.asset_type == "generated_image"]
    used_paths = {shot.asset_path for shot in project.shots if shot.asset_path}
    forbidden_assets = [
        asset.id for asset in project.media
        if asset.kind in {"generated_image", "thumbnail_background"} and asset.path in used_paths
    ]
    if forbidden_shots or forbidden_assets:
        raise RuntimeError(
            "no-AI-still policy violation: " + ", ".join((forbidden_shots + forbidden_assets)[:12])
        )


def _generate_thumbnail_backgrounds(project: EpisodeProject, run_dir: Path) -> list[Path]:
    """Collect only traceable real source captures for thumbnail art direction."""
    directory = run_dir / "thumbnails" / "backgrounds" / "source_based"
    directory.mkdir(parents=True, exist_ok=True)
    backgrounds: list[Path] = []
    seen: set[str] = set()
    for shot in project.shots:
        if not shot.source_id or not shot.asset_path or shot.asset_path in seen:
            continue
        if shot.asset_type not in {"screenshot", "screen_recording", "official_demo"}:
            continue
        source = Path(shot.asset_path)
        if not source.is_file():
            continue
        seen.add(shot.asset_path)
        if source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            backgrounds.append(source)
        elif shot.asset_type in {"screen_recording", "official_demo"}:
            frame = directory / f"local_{len(backgrounds) + 1:02d}.jpg"
            if not frame.exists():
                subprocess.run([
                    "ffmpeg", "-y", "-ss", "1.0", "-i", str(source), "-frames:v", "1",
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                    "-q:v", "2", str(frame),
                ], capture_output=True, check=True)
            backgrounds.append(frame)
        if len(backgrounds) >= 8:
            break
    return backgrounds[:8]


def _generate_media(project: EpisodeProject, run_dir: Path, should_cancel: CancelCheck = None) -> list[Path]:
    """Generate in two waves: submit remote clips quickly, then wait in parallel.

    Magic Hour jobs are independent. Submitting all selected hero clips before
    waiting prevents six long queues from becoming six serial waits. Local
    Remotion graphics are rendered in a bounded second pool, preserving 1080p
    masters while avoiding CPU oversubscription.
    """
    backgrounds: list[Path] = []
    local_jobs: list[tuple[object, Path, str, str]] = []
    remote_jobs: list[tuple[object, dict, Path, int]] = []
    hero_count = 0
    motion_video_dir = run_dir / "generated" / "motion_video_v3_seedance"

    def queue_local(shot, suffix: str, note: str) -> None:
        destination = run_dir / "generated" / "remotion_1080" / f"{shot.id}{suffix}.mp4"
        local_jobs.append((shot, destination, f"graphic_{shot.id}{suffix}", note))

    for asset in project.media:
        if asset.kind in {"generated_image", "thumbnail_background"}:
            asset.qc_status = "rejected"
            asset.qc_notes.append("Standalone AI stills are forbidden by the motion-only visual policy.")

    for shot in project.shots:
        _checkpoint(should_cancel)
        if shot.asset_type == "generated_image":
            shot.asset_type, shot.asset_path = "motion_graphic", ""
        if not shot.asset_path and shot.asset_type in {"motion_graphic", "chart", "chapter_card"}:
            queue_local(shot, "", "Native 1920x1080 Remotion master with exact transcript-timed typography and geometry.")
            continue
        if shot.asset_type not in {"generated_video", "concept_animation"}:
            continue
        concept_animation = shot.asset_type == "concept_animation"
        seedance_editorial = shot.motion_template == "seedance_editorial"
        remote_generation_enabled = (
            CONCEPT_ANIMATIONS_ENABLED if concept_animation
            else SEEDANCE_MOTION_ENABLED if seedance_editorial
            else GENERATIVE_VISUALS_ENABLED
        )
        if not remote_generation_enabled:
            shot.asset_type = "motion_graphic"
            if seedance_editorial:
                shot.motion_template = "auto"
            shot.rights_note = (
                "Original deterministic explanatory visualization; not source evidence."
                if concept_animation else "Original deterministic motion graphic rendered locally for this episode."
            )
            queue_local(shot, "_local", "Local deterministic fallback; generative visuals are disabled.")
            continue

        if shot.asset_path and motion_video_dir not in Path(shot.asset_path).parents:
            shot.asset_path = ""
        plate = run_dir / "generated" / "motion_plates" / f"{shot.id}.png"
        if not plate.exists():
            motion_graphics.render_motion_plate(project, shot, plate)
        end_plate = None
        if concept_animation:
            end_plate = run_dir / "generated" / "motion_plates" / f"{shot.id}_completed.png"
            if not end_plate.exists():
                motion_graphics.render_concept_end_plate(project, shot, end_plate)
        backgrounds.append(plate)
        plate_id = f"motion_plate_{shot.id}"
        if not any(asset.id == plate_id for asset in project.media):
            project.media.append(MediaAsset(
                id=plate_id, kind="motion_plate", path=str(plate), credits=0, qc_status="passed",
                qc_notes=["Text-free local geometry used only as a Magic Hour animation anchor."],
            ))
        if not concept_animation and not seedance_editorial and hero_count >= 6:
            continue
        existing = sorted(motion_video_dir.glob(f"{shot.id}_*"))
        if existing:
            shot.asset_path = str(existing[0])
            if not concept_animation and not seedance_editorial:
                hero_count += 1
            continue

        submitted = None
        last_error = None
        routes_for_shot = (
            _concept_model_routes() if concept_animation
            else _seedance_model_routes() if seedance_editorial
            else _premium_model_routes()
        )
        prompt_for_shot = (
            _concept_video_prompt(shot.prompt) if concept_animation
            else _seedance_editorial_prompt(shot.prompt) if seedance_editorial
            else _video_prompt(shot.prompt)
        )
        for route_index, (model, resolution) in enumerate(routes_for_shot):
            try:
                uploaded = magichour.upload_file(str(plate), "image")
                uploaded_end = magichour.upload_file(str(end_plate), "image") if end_plate else None
                submitted = magichour.image_to_video(
                    uploaded, prompt_for_shot, f"{project.episode_id}-{shot.id}",
                    duration=8, model=model, resolution=resolution,
                    end_image_file_path=uploaded_end,
                )
                _add_credits(project, int(submitted.get("credits_charged", 0)))
                remote_jobs.append((shot, submitted, motion_video_dir, route_index))
                if not concept_animation and not seedance_editorial:
                    hero_count += 1
                break
            except Exception as exc:
                last_error = exc
        if submitted is None:
            shot.asset_type = "motion_graphic"
            if seedance_editorial:
                shot.motion_template = "auto"
            queue_local(shot, "_fallback", "Exact local fallback after Magic Hour submission failed.")
            project.qc.setdefault("warnings", []).append(f"{shot.id} video submission fallback: {last_error}")

    def wait_and_download(item: tuple[object, dict, Path, int]) -> tuple[object, dict, dict, list[Path], int]:
        shot, submitted, directory, route_index = item
        job = magichour.wait_video(submitted["id"])
        return shot, submitted, job, magichour.download_all(job, directory, shot.id), route_index

    failed_remote: list[tuple[object, int, Exception]] = []
    if remote_jobs:
        workers = min(MAGIC_HOUR_MOTION_PARALLELISM, len(remote_jobs))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="motion-download") as executor:
            futures = {executor.submit(wait_and_download, item): item for item in remote_jobs}
            for future in as_completed(futures):
                try:
                    shot, submitted, job, paths, _route_index = future.result()
                    final_credits = _reconcile_credits(project, submitted, job)
                    shot.asset_path = str(paths[0])
                    project.media.append(MediaAsset(
                        id=f"motion_vid_{shot.id}", kind="generated_motion_graphic", path=str(paths[0]),
                        magic_hour_project_id=submitted["id"], credits=final_credits, qc_status="pending",
                    ))
                except Exception as exc:
                    failed_remote.append((futures[future][0], futures[future][3], exc))

    # An asynchronous failure is uncommon. Preserve the quality route fallback
    # before using a local exact substitute; only the failed clip waits again.
    for shot, route_index, error in failed_remote:
        recovered = False
        last_error = error
        plate = run_dir / "generated" / "motion_plates" / f"{shot.id}.png"
        concept_animation = shot.asset_type == "concept_animation"
        seedance_editorial = shot.motion_template == "seedance_editorial"
        end_plate = (
            run_dir / "generated" / "motion_plates" / f"{shot.id}_completed.png"
            if concept_animation else None
        )
        routes = (
            _concept_model_routes() if concept_animation
            else _seedance_model_routes() if seedance_editorial
            else _premium_model_routes()
        )
        prompt_for_shot = (
            _concept_video_prompt(shot.prompt) if concept_animation
            else _seedance_editorial_prompt(shot.prompt) if seedance_editorial
            else _video_prompt(shot.prompt)
        )
        for model, resolution in routes[route_index + 1:]:
            try:
                uploaded = magichour.upload_file(str(plate), "image")
                uploaded_end = magichour.upload_file(str(end_plate), "image") if end_plate else None
                submitted = magichour.image_to_video(
                    uploaded, prompt_for_shot, f"{project.episode_id}-{shot.id}-retry",
                    duration=8, model=model, resolution=resolution,
                    end_image_file_path=uploaded_end,
                )
                _add_credits(project, int(submitted.get("credits_charged", 0)))
                job = magichour.wait_video(submitted["id"])
                final_credits = _reconcile_credits(project, submitted, job)
                path = magichour.download_all(job, motion_video_dir, shot.id)[0]
                shot.asset_path = str(path)
                project.media.append(MediaAsset(
                    id=f"motion_vid_{shot.id}_retry", kind="generated_motion_graphic", path=str(path),
                    magic_hour_project_id=submitted["id"], credits=final_credits, qc_status="pending",
                ))
                recovered = True
                break
            except Exception as exc:
                last_error = exc
        if not recovered:
            shot.asset_type = "motion_graphic"
            if seedance_editorial:
                shot.motion_template = "auto"
            queue_local(shot, "_fallback", "Exact local fallback after Magic Hour generation failed.")
            project.qc.setdefault("warnings", []).append(f"{shot.id} video fallback: {last_error}")

    def render_local(item: tuple[object, Path, str, str]) -> tuple[object, Path, str, str]:
        shot, destination, asset_id, note = item
        remotion_renderer.render_motion_video(
            project, shot, destination, scratch=run_dir / "generated" / "remotion_scratch",
        )
        return shot, destination, asset_id, note

    if local_jobs:
        workers = min(LOCAL_MOTION_RENDER_PARALLELISM, len(local_jobs))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="local-motion") as executor:
            for future in as_completed([executor.submit(render_local, item) for item in local_jobs]):
                shot, path, asset_id, note = future.result()
                shot.asset_path = str(path)
                project.media.append(MediaAsset(
                    id=asset_id, kind="motion_graphic", path=str(path), credits=0,
                    qc_status="passed", qc_notes=[note],
                ))
    save_project(project, run_dir)
    return backgrounds


def _meet_magic_hour_quality_floor(
    project: EpisodeProject, run_dir: Path, should_cancel: CancelCheck = None,
) -> dict:
    """Spend any remaining quality allocation on inspected premium motion takes."""
    target = int(project.episode.get("minimum_magic_hour_credits", MIN_EPISODE_CREDITS))
    limit = int(project.episode.get("credit_limit", MAX_EPISODE_CREDITS))
    if target > limit:
        raise ValueError(f"Magic Hour quality floor {target} exceeds the episode ceiling {limit}")
    project.episode["minimum_magic_hour_credits"] = target
    current = int(project.costs.get("magic_hour_credits", 0))
    accepted_existing = [
        asset for asset in project.media
        if asset.kind == "generated_motion_graphic" and asset.qc_status == "passed"
    ]
    for asset in project.media:
        if asset.kind == "generated_motion_graphic" and asset.qc_status == "failed":
            asset.qc_status = "rejected"
            asset.qc_notes.append("Excluded from the timeline after automated frame inspection.")
    if current >= target and accepted_existing:
        result = {"passed": True, "target": target, "actual": current, "premium_motion_variants": 0}
        project.qc["credit_quality_floor"] = result
        save_project(project, run_dir)
        return result

    candidates = []
    for asset in project.media:
        if asset.kind != "motion_plate" or not Path(asset.path).is_file():
            continue
        shot_id = asset.id.removeprefix("motion_plate_")
        shot = next((item for item in project.shots if item.id == shot_id and not item.source_id), None)
        if shot:
            candidates.append((asset, shot))
    if not candidates:
        # A source-less local graphic is an evidence-safe seed even when the
        # storyboard did not originally request a generated-video slot.
        shot = next((
            item for item in project.shots
            if not item.source_id and item.asset_type in {"motion_graphic", "chart", "chapter_card"}
        ), None)
        if shot is None:
            raise RuntimeError(
                f"Magic Hour quality floor is {target} credits, but no evidence-safe hero shot can be upgraded"
            )
        plate = run_dir / "generated" / "motion_plates" / f"{shot.id}_quality_floor.png"
        if not plate.exists():
            motion_graphics.render_motion_plate(project, shot, plate)
        image_asset = MediaAsset(
            id=f"motion_plate_{shot.id}_quality_floor", kind="motion_plate", path=str(plate), credits=0,
            qc_status="passed", qc_notes=["Text-free local geometry created for the premium motion quality floor."],
        )
        project.media.append(image_asset)
        candidates.append((image_asset, shot))

    uploads: dict[str, str] = {}
    attempts = max(
        int(project.qc.get("credit_quality_floor", {}).get("premium_motion_variants", 0)),
        sum(1 for asset in project.media if asset.kind == "generated_motion_graphic"),
    )
    accepted = 0
    errors: list[str] = []
    output_dir = run_dir / "generated" / "video" / "premium_variants"
    while (
        int(project.costs.get("magic_hour_credits", 0)) < target or accepted < 1
    ) and attempts < MAX_PREMIUM_MOTION_VARIANTS:
        _checkpoint(should_cancel)
        image_asset, shot = candidates[attempts % len(candidates)]
        attempts += 1
        try:
            uploaded = uploads.get(image_asset.path)
            if not uploaded:
                uploaded = magichour.upload_file(image_asset.path, "image")
                uploads[image_asset.path] = uploaded
            routes = (
                _seedance_model_routes()
                if shot.motion_template == "seedance_editorial"
                else _premium_model_routes()
            )
            model, resolution = routes[(attempts - 1) % len(routes)]
            submitted = magichour.image_to_video(
                uploaded, (
                    _seedance_editorial_prompt(shot.prompt)
                    if shot.motion_template == "seedance_editorial"
                    else _video_prompt(shot.prompt)
                ),
                f"{project.episode_id}-{shot.id}-premium-take-{attempts}",
                duration=8, model=model, resolution=resolution,
            )
            _add_credits(project, int(submitted.get("credits_charged", 0)))
            save_project(project, run_dir)
            job = magichour.wait_video(submitted["id"])
            final_credits = _reconcile_credits(project, submitted, job)
            path = magichour.download_all(job, output_dir, f"{shot.beat_id}_take_{attempts}")[0]
            inspection = visual_qc.inspect_motion(path, shot.prompt)
            generated = MediaAsset(
                id=f"premium_motion_{shot.id}_{attempts}", kind="generated_motion_graphic", path=str(path),
                magic_hour_project_id=submitted["id"], credits=final_credits,
                qc_status="passed" if inspection["passed"] else "rejected", qc_notes=inspection["notes"],
            )
            project.media.append(generated)
            if inspection["passed"]:
                previous_path = shot.asset_path
                shot.asset_type = "generated_video"
                shot.asset_path = str(path)
                shot.rights_note = "Original Magic Hour motion graphic generated from a local text-free design plate."
                accepted += 1
                for previous in project.media:
                    if previous.path == previous_path and previous.kind == "generated_motion_graphic":
                        previous.qc_notes.append(f"Superseded by inspected premium take {attempts}.")
            save_project(project, run_dir)
        except CreditLimitExceeded:
            raise
        except Exception as exc:
            errors.append(f"take {attempts}: {exc}")
            save_project(project, run_dir)

    actual = int(project.costs.get("magic_hour_credits", 0))
    result = {
        "passed": actual >= target, "target": target, "actual": actual,
        "premium_motion_variants": attempts, "accepted_variants": accepted,
        "errors": errors[-3:],
    }
    project.qc["credit_quality_floor"] = result
    save_project(project, run_dir)
    if not result["passed"]:
        raise RuntimeError(
            f"Magic Hour quality floor not met: {actual}/{target} credits after {attempts} premium motion takes"
        )
    return result


def produce_episode(
    episode_id: str, *, canary: bool = False, should_cancel: CancelCheck = None,
    report_progress: ProgressCallback = None,
) -> dict:
    run_dir = _episode_dir(episode_id)
    project = load_project(run_dir)
    project.episode["production_stack"] = production_stack_receipt()
    run_started = time.perf_counter()
    speed_checkpoints: dict[str, float] = {}

    def speed_checkpoint(stage: str) -> None:
        speed_checkpoints[stage] = round(time.perf_counter() - run_started, 3)

    initial_status = project.status
    if project.status == "runtime_revision_required" and project.script and project.narration.get("path"):
        previous_narration = Path(project.narration["path"])
        if previous_narration.is_file() and not project.episode.get("voice_words_per_minute"):
            previous_duration = duration(previous_narration)
            if previous_duration > 0:
                project.episode["voice_words_per_minute"] = round(
                    project.script.word_count / (previous_duration / 60), 2
                )
                project.narration["used_for_voice_speed_calibration"] = True
                save_project(project, run_dir)
    if not canary and (not project.brief or not project.brief.approved):
        if not AUTO_APPROVE_PRIVATE_DRAFTS or not project.brief:
            raise PermissionError("episode brief has not passed the weekly approval gate")
        project.brief.approved = True
        project.review.slate_status = "approved"
        project.episode["approval_mode"] = "automatic_private_drafts"
        project.episode["publishing_enabled"] = False
    _checkpoint(should_cancel)
    _report(report_progress, 10)
    project.status = "researching"
    claims_input = _claims_stage_input(project)
    if not project.claims or not stage_is_current(project, "claims", claims_input):
        project.claims = editorial.extract_claims(project.brief, project.sources)
        project.brief.claim_ids = [claim.id for claim in project.claims]
        mark_stage(project, "claims", claims_input)
        save_project(project, run_dir)
    speed_checkpoint("claims")
    _checkpoint(should_cancel)
    _report(report_progress, 20)
    resume_script_revision = initial_status == "script_revision_required" and project.script is not None
    project.status = "writing"
    script_profile = editorial.duration_profile(project)
    project.episode["script_word_min"] = script_profile["word_min"]
    project.episode["script_word_max"] = script_profile["word_max"]
    script_input = {
        "editorial_algorithm_version": 7,
        "production_method_catalog_sha256": project.episode["production_stack"]["catalog_sha256"],
        "brief": project.brief.model_dump(mode="json"),
        "claims": [claim.model_dump(mode="json") for claim in project.claims],
        "duration_profile": script_profile,
    }
    manual_script_approval = project.qc.get("script_manual_approval", {})
    manual_script_approved = bool(
        project.script
        and manual_script_approval.get("approved") is True
        and manual_script_approval.get("script_hash")
        == canonical_hash(project.script.model_dump(mode="json"))
    )
    if manual_script_approved and not stage_is_current(project, "script", script_input):
        project.qc.setdefault("fact_check", {})["passed"] = True
        project.qc["fact_check"]["manual_approval"] = manual_script_approval
        mark_stage(project, "script", script_input)
        save_project(project, run_dir)
    elif not project.script or not stage_is_current(project, "script", script_input):
        if resume_script_revision and project.script:
            fact_check = editorial.verify_script(project)
            quality_review = editorial.review_script_quality(project)
            verification = {
                **fact_check,
                "quality_review": quality_review,
                "passed": bool(fact_check["passed"] and quality_review["passed"]),
            }
            revision_count = int(project.qc.get("fact_check", {}).get("automatic_revisions", 0)) + 1
        else:
            project.script, verification, revision_count = editorial.write_verified_script(project)
        project = EpisodeProject.model_validate(project.model_dump())
        project.qc["fact_check"] = verification
        project.qc["fact_check"]["automatic_revisions"] = revision_count
        if not project.qc["fact_check"]["passed"]:
            project.status = "script_revision_required"
            save_project(project, run_dir)
            raise RuntimeError("independent script verification failed; review qc.fact_check")
        mark_stage(project, "script", script_input)
        save_project(project, run_dir)
    speed_checkpoint("script")
    _checkpoint(should_cancel)
    _report(report_progress, 30)
    project.status = "narrating"
    voice_sample_path = _resolve(VOICE_SAMPLE)
    voice_sample_signature = (
        {"path": str(voice_sample_path), "size": voice_sample_path.stat().st_size, "modified_ns": voice_sample_path.stat().st_mtime_ns}
        if voice_sample_path.is_file() else {"path": str(voice_sample_path), "missing": True}
    )
    narration_input = {
        "script": project.script.model_dump(mode="json"),
        "voice_sample": voice_sample_signature,
        # Invalidate cached masters whenever denoising/mastering changes.
        "audio_mastering_version": audio_qc.AUDIO_MASTERING_VERSION,
        "fidelity_locked_timeline_seconds": float(
            (project.editorial_plan.get("fidelity_visual_overrides") or {}).get(
                "fidelity_locked_timeline_seconds", 0
            ) or 0
        ),
    }
    narration_cache_key = canonical_hash(narration_input)
    cached_narration = Path(project.narration.get("path", "")) if project.narration.get("path") else None
    if cached_narration and cached_narration.is_file() and stage_is_current(project, "narration", narration_input):
        narration = cached_narration
    else:
        raw_narration = _generate_narration(project, run_dir, should_cancel, narration_cache_key)
        narration = run_dir / f"narration_master_{narration_cache_key[:16]}.wav"
        audio_qc.master_narration(raw_narration, narration)
        project.narration["raw_path"] = str(raw_narration)
        project.narration["path"] = str(narration)
        project.narration["voice_profile_id"] = VOICE_PROFILE_ID
        # Every immutable TTS chunk has already passed ASR/script alignment.
        # Reuse that result and run the master pass for whole-file audio and
        # speaker consistency instead of retranscribing nine minutes again.
        audio_review = audio_qc.review_narration(
            narration,
            project.script.narration,
            voice_sample_path,
            recognized_text=project.script.narration,
        )
        raw_metrics = audio_qc.technical_metrics(raw_narration)
        audio_review["raw_metrics"] = raw_metrics
        master_flatness = audio_review["metrics"]["spectral_flatness"]
        raw_flatness = raw_metrics["spectral_flatness"]
        if raw_flatness > 0.015 and master_flatness > raw_flatness * 1.25:
            audio_review["failures"].append("mastering increased broadband background noise")
            audio_review["passed"] = False
        audio_review["transcript_validation"] = "per_chunk_asr"
        project.qc["audio_listenability"] = audio_review
        if not audio_review["passed"]:
            project.status = "audio_revision_required"
            save_project(project, run_dir)
            raise RuntimeError("narration failed listenability QC: " + "; ".join(audio_review["failures"]))
        mark_stage(project, "narration", narration_input)
        save_project(project, run_dir)
    if "audio_listenability" not in project.qc:
        audio_review = audio_qc.review_narration(
            narration,
            project.script.narration,
            voice_sample_path,
            recognized_text=project.script.narration,
        )
        audio_review["transcript_validation"] = "per_chunk_asr"
        project.qc["audio_listenability"] = audio_review
        if not audio_review["passed"]:
            project.status = "audio_revision_required"
            save_project(project, run_dir)
            raise RuntimeError("narration failed listenability QC: " + "; ".join(audio_review["failures"]))
    actual_duration = duration(narration)
    fidelity_locked_timeline_seconds = float(
        (project.editorial_plan.get("fidelity_visual_overrides") or {}).get(
            "fidelity_locked_timeline_seconds", 0
        ) or 0
    )
    if fidelity_locked_timeline_seconds > 0 and abs(actual_duration - fidelity_locked_timeline_seconds) > 0.05:
        locked_path = narration.with_name(
            f"{narration.stem}_fidelity_{round(fidelity_locked_timeline_seconds * 1000)}ms.wav"
        )
        if not locked_path.is_file():
            audio_qc.retime_narration(
                narration, locked_path, target_duration_seconds=fidelity_locked_timeline_seconds,
            )
        locked_review = audio_qc.review_narration(
            locked_path,
            project.script.narration,
            voice_sample_path,
            recognized_text=project.script.narration,
        )
        locked_review["transcript_validation"] = "per_chunk_asr_then_fidelity_timeline_lock"
        if not locked_review["passed"]:
            project.status = "audio_revision_required"
            project.qc["audio_listenability"] = locked_review
            save_project(project, run_dir)
            raise RuntimeError(
                "fidelity timeline-locked narration failed listenability QC: "
                + "; ".join(locked_review["failures"])
            )
        project.narration["pre_fidelity_timeline_lock_path"] = str(narration)
        project.narration["path"] = str(locked_path)
        project.narration["duration_seconds"] = locked_review["metrics"]["duration_seconds"]
        project.narration["fidelity_timeline_lock"] = {
            "source_duration_seconds": actual_duration,
            "target_duration_seconds": fidelity_locked_timeline_seconds,
        }
        project.qc["audio_listenability"] = locked_review
        narration = locked_path
        actual_duration = duration(narration)
        save_project(project, run_dir)
    speed_checkpoint("narration")
    target_minutes = float(project.episode.get("target_minutes", 10))
    if target_minutes <= 6:
        runtime_min, runtime_max = (target_minutes - 0.5) * 60, (target_minutes + 0.5) * 60
        shot_min, shot_max = 45, 70
    else:
        runtime_min, runtime_max = 480, 720
        shot_min, shot_max = 70, 110
    # A cloned-voice performance can land a few seconds outside the editorial
    # window even when the approved script is correct. For a small miss, reuse
    # the paid master and make one pitch-preserving tempo correction. This
    # avoids regenerating narration, changing speakers, or spending credits.
    if (
        not canary
        and actual_duration < runtime_min - RUNTIME_BOUNDARY_TOLERANCE_SECONDS
        and actual_duration >= runtime_min * 0.9
    ):
        corrected_target = runtime_min + 2.0
        corrected_path = narration.with_name(f"{narration.stem}_runtime_{int(corrected_target)}s.wav")
        if not corrected_path.is_file():
            audio_qc.retime_narration(
                narration,
                corrected_path,
                target_duration_seconds=corrected_target,
            )
        corrected_review = audio_qc.review_narration(
            corrected_path,
            project.script.narration,
            voice_sample_path,
            recognized_text=project.script.narration,
        )
        corrected_review["transcript_validation"] = "per_chunk_asr_then_pitch_preserving_runtime_correction"
        if corrected_review["passed"]:
            project.narration["pre_runtime_correction_path"] = str(narration)
            project.narration["path"] = str(corrected_path)
            project.narration["duration_seconds"] = corrected_review["metrics"]["duration_seconds"]
            project.narration["runtime_adjustment"] = {
                "method": "ffmpeg_atempo",
                "source_duration_seconds": actual_duration,
                "target_duration_seconds": corrected_target,
                "tempo": round(actual_duration / corrected_target, 8),
            }
            project.qc["audio_listenability"] = corrected_review
            narration = corrected_path
            actual_duration = duration(narration)
            save_project(project, run_dir)
        else:
            project.status = "audio_revision_required"
            project.qc["audio_listenability"] = corrected_review
            save_project(project, run_dir)
            raise RuntimeError(
                "runtime-corrected narration failed listenability QC: "
                + "; ".join(corrected_review["failures"])
            )
    if not (
        runtime_min - RUNTIME_BOUNDARY_TOLERANCE_SECONDS
        <= actual_duration
        <= runtime_max + RUNTIME_BOUNDARY_TOLERANCE_SECONDS
    ) and not canary:
        project.status = "runtime_revision_required"
        project.qc["runtime"] = {"passed": False, "duration_seconds": actual_duration}
        save_project(project, run_dir)
        raise RuntimeError(f"narration runtime {actual_duration:.1f}s is outside {runtime_min:.0f}-{runtime_max:.0f}s")
    _checkpoint(should_cancel)
    _report(report_progress, 45)
    storyboard_input = {
        "storyboard_algorithm_version": 8,
        "script": project.script.model_dump(mode="json"), "duration": actual_duration, "canary": canary,
    }
    freeze_storyboard = bool(
        (project.editorial_plan.get("fidelity_visual_overrides") or {}).get("freeze_storyboard")
    )
    if freeze_storyboard and project.shots:
        mark_stage(project, "storyboard", storyboard_input)
    elif not project.shots or not stage_is_current(project, "storyboard", storyboard_input):
        project.shots = storyboard.build_shot_plan(
            project, actual_duration, min_shots=8 if canary else shot_min, max_shots=15 if canary else shot_max,
        )
        mark_stage(project, "storyboard", storyboard_input)
    if not canary:
        project.episode["visual_mix_policy"] = visual_mix.load_policy()["policy_id"]
        project.qc["visual_mix_plan"] = visual_mix.review_visual_mix(project, require_assets=False)
    project.qc["storyboard"] = (
        {"passed": True, "canary": True, "shot_count": len(project.shots)}
        if canary else storyboard.validate_shot_plan(
            project.shots, actual_duration, min_shots=shot_min, max_shots=shot_max,
        )
    )
    # Screen acquisition is a built-in episode stage. Run it as soon as the
    # storyboard exists so a later, human-gated third-party b-roll review does
    # not prevent safe public-page and approved product-demo capture.
    project.status = "capturing_sources"
    capture_input = {
        "planner": {
            "version": 9,
            "model": OPENROUTER_BROWSER_MODEL,
            "semantic_annotations": True,
            "resolution": "1080p",
            "parallelism": CAPTURE_PARALLELISM,
        },
        "sources": [{"id": source.id, "url": str(source.url)} for source in project.sources],
        "shots": [
            {"id": shot.id, "type": shot.asset_type, "source_id": shot.source_id, "prompt": shot.prompt}
            for shot in project.shots
        ],
        "model_tests": [
            {
                "story_id": item.get("story_id"),
                "website": item.get("website"),
                "allowed_hosts": item.get("allowed_hosts", []),
                "inputs": item.get("inputs", {}),
                "allow_generation": bool(item.get("allow_generation")),
                "profile": item.get("profile", "google_manual"),
                "approval_state": (
                    "approved"
                    if item.get("status") in {"approved_for_capture", "complete"}
                    else item.get("status", "planned")
                ),
            }
            for item in project.episode.get("model_test_queue", [])
        ],
    }
    if not stage_is_current(project, "capture", capture_input):
        _acquire_screen_recordings_for_project(
            project, run_dir, canary=canary, should_cancel=should_cancel,
        )
        mark_stage(project, "capture", capture_input)
        save_project(project, run_dir)
    speed_checkpoint("capture")
    if YOUTUBE_BROLL_ENABLED and not canary:
        try:
            broll_request = build_project_broll_request(project)
            broll_input = {
                "algorithm_version": 3,
                "script_hash": canonical_hash(project.script.model_dump(mode="json")),
                "shots": [
                    {"id": shot.id, "beat_id": shot.beat_id, "type": shot.asset_type}
                    for shot in project.shots
                ],
                "request": broll_request.model_dump(mode="json"),
            }
            if freeze_storyboard and project.shots:
                mark_stage(project, "youtube_broll", broll_input)
            elif not stage_is_current(project, "youtube_broll", broll_input):
                broll_result = discover_project_broll(
                    project, run_dir / "broll_research", broll_request,
                )
                project.artifacts["broll_candidates"] = broll_result["manifest"]
                project.artifacts["broll_review_queue"] = broll_result["review_queue"]
                expected = broll_result["scene_count"] * broll_request.candidates_per_scene
                project.episode["broll_research"] = {
                    "status": "human_review_required",
                    "scene_count": broll_result["scene_count"],
                    "candidate_count": broll_result["candidate_count"],
                    "planner": broll_result["planner"],
                    "render_gate": "approved reuse rights and timestamps required",
                }
                project.qc["youtube_broll"] = {
                    "passed": broll_result["candidate_count"] >= expected,
                    "scene_count": broll_result["scene_count"],
                    "candidate_count": broll_result["candidate_count"],
                    "expected_candidate_count": expected,
                    "errors": broll_result["error_count"],
                    "downloads": 0,
                    "human_review_required": True,
                }
                mark_stage(project, "youtube_broll", broll_input)
                save_project(project, run_dir)
        except Exception as exc:
            # B-roll discovery is an enhancement layer. A temporary quota or
            # provider failure must not destroy an otherwise valid episode.
            project.qc["youtube_broll"] = {
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
                "retry_scope": "youtube_broll",
            }
            save_project(project, run_dir)
    if not canary:
        project.qc["youtube_broll_readiness"] = visual_mix.review_youtube_readiness(project)
        if not project.qc["youtube_broll_readiness"]["passed"]:
            project.status = "broll_review_required"
            save_project(project, run_dir)
            raise RuntimeError(
                "footage-led visual mix is not ready; approve and ingest matched source excerpts: "
                + "; ".join(project.qc["youtube_broll_readiness"]["failures"][:8])
            )
    capture_artifacts = {
        artifact.path: artifact
        for record in project.captures
        for artifact in record.artifacts
    }
    licensed_rights = [
        entry for entry in project.rights
        if entry.get("capture_mode") in {
            "licensed_timestamped_excerpt", "official_source_timestamped_excerpt",
            "approved_authenticated_product_demo",
        }
        or str(entry.get("asset_id", "")).startswith("licensed_clip_")
    ]
    project.rights = licensed_rights
    for shot in project.shots:
        if not shot.source_id:
            continue
        artifact = capture_artifacts.get(shot.asset_path)
        project.rights.append({
            "shot_id": shot.id,
            "source_id": shot.source_id,
            "asset_path": shot.asset_path,
            "source_url": artifact.source_url if artifact else "",
            "capture_mode": artifact.capture_mode if artifact else "",
            "sha256": artifact.sha256 if artifact else "",
            "muted": artifact.muted if artifact else True,
            "note": shot.rights_note,
            "review_required_before_publication": True,
        })
    project.qc["clip_alignment"] = clip_alignment.review_project_clip_alignment(project)
    if not project.qc["clip_alignment"]["passed"] and not canary:
        project.status = "visual_revision_required"
        save_project(project, run_dir)
        raise RuntimeError(
            "clip alignment/repetition QC failed: "
            + "; ".join(project.qc["clip_alignment"]["failures"][:8])
        )
    project.qc["visual_mix"] = visual_mix.review_visual_mix(project, require_assets=True)
    if not project.qc["visual_mix"]["passed"] and not canary:
        project.status = "visual_mix_revision_required"
        save_project(project, run_dir)
        raise RuntimeError(
            "visual mix QC failed: " + "; ".join(project.qc["visual_mix"]["failures"][:8])
        )
    save_project(project, run_dir)
    _checkpoint(should_cancel)
    _report(report_progress, 58)
    project.status = "generating_media"
    media_input = {
        "generator_version": 9,
        "render_profile": {
            "resolution": "1080p",
            "width": VIDEO_W,
            "height": VIDEO_H,
            "fps": VIDEO_FPS,
            "ffmpeg_preset": FFMPEG_PRESET,
        },
        "mode": "source_captures_plus_local_motion" if not GENERATIVE_VISUALS_ENABLED else "source_captures_plus_generated_motion",
        "premium_routes": list(PREMIUM_MOTION_MODELS),
        "seedance_motion": {
            "enabled": SEEDANCE_MOTION_ENABLED,
            "share_of_motion_graphics": SEEDANCE_MOTION_SHARE,
            "routes": list(SEEDANCE_MOTION_MODELS),
            "output_contract": "silent_text_free_16x9_1080p",
        },
        "shots": [shot.model_dump(mode="json") for shot in project.shots],
    }
    if not stage_is_current(project, "media", media_input):
        backgrounds = _generate_media(project, run_dir, should_cancel)
        mark_stage(project, "media", media_input)
    else:
        backgrounds = [
            Path(asset.path) for asset in project.media
            if asset.kind in {"motion_graphic", "motion_plate"} and Path(asset.path).is_file()
            and Path(asset.path).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ]
    speed_checkpoint("media")
    visual_input = [{"id": asset.id, "path": asset.path} for asset in project.media]
    assets_for_qc = [] if stage_is_current(project, "visual_qc", visual_input) else list(project.media)
    review_candidates = [
        asset for asset in assets_for_qc
        if asset.qc_status != "rejected" and Path(asset.path).exists() and Path(asset.path).stat().st_size > 1024
        and asset.kind not in {"motion_graphic", "motion_plate"}
    ]

    def inspect_asset(asset: MediaAsset) -> tuple[str, dict]:
        related = next((shot for shot in project.shots if shot.asset_path == asset.path), None)
        expected = related.prompt if related else project.brief.thesis
        if asset.kind == "licensed_source_clip":
            provenance = [
                entry for entry in project.rights
                if str(entry.get("asset_path") or "") == asset.path
                and entry.get("source_url")
                and entry.get("source_in_seconds") is not None
                and entry.get("source_out_seconds") is not None
            ]
            return asset.id, {
                "passed": bool(provenance),
                "notes": [
                    "Official-source excerpt with URL and timestamp provenance; intentional product UI and source labels are allowed.",
                    "Final-timeline perceptual QC remains responsible for black frames, blocking pages, and intrusive watermarks.",
                ] if provenance else ["Licensed source clip is missing URL/timestamp provenance."],
            }
        result = (
            visual_qc.inspect_motion(Path(asset.path), expected)
            if asset.kind == "generated_motion_graphic"
            else visual_qc.inspect(Path(asset.path), expected)
        )
        return asset.id, result

    review_results: dict[str, dict] = {}
    if review_candidates:
        workers = min(VISUAL_QC_PARALLELISM, len(review_candidates))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="visual-qc") as executor:
            futures = {executor.submit(inspect_asset, asset): asset for asset in review_candidates}
            for future in as_completed(futures):
                asset = futures[future]
                try:
                    asset_id, inspection = future.result()
                    review_results[asset_id] = inspection
                except Exception as exc:
                    review_results[asset.id] = {
                        "passed": False,
                        "notes": [f"visual review execution failed: {type(exc).__name__}: {exc}"],
                    }
    for asset in assets_for_qc:
        _checkpoint(should_cancel)
        if asset.qc_status == "rejected":
            continue
        if not Path(asset.path).exists() or Path(asset.path).stat().st_size <= 1024:
            asset.qc_status = "failed"
            asset.qc_notes = ["asset is missing or empty"]
            continue
        if asset.kind in {"motion_graphic", "motion_plate"}:
            asset.qc_status = "passed"
            continue
        related = next((shot for shot in project.shots if shot.asset_path == asset.path), None)
        inspection = review_results.get(asset.id, {"passed": False, "notes": ["visual review result is missing"]})
        asset.qc_status = "passed" if inspection["passed"] else "failed"
        asset.qc_notes = inspection["notes"]
        if not inspection["passed"] and asset.kind == "generated_motion_graphic" and related:
            fallback = run_dir / "generated" / "remotion_1080" / f"{related.id}_qc_fallback.mp4"
            remotion_renderer.render_motion_video(
                project, related, fallback, scratch=run_dir / "generated" / "remotion_scratch",
            )
            related.asset_type = "motion_graphic"
            related.asset_path = str(fallback)
            backgrounds.append(fallback)
            project.media.append(MediaAsset(
                id=f"graphic_{related.id}_qc_fallback", kind="motion_graphic", path=str(fallback), credits=0,
                qc_status="passed", qc_notes=["Exact local fallback after the Magic Hour motion clip was rejected."],
            ))
            asset.qc_notes.append("Rejected and excluded from the timeline after motion-specific QC.")
            asset.qc_status = "rejected"
    _assert_no_generated_stills(project)
    if assets_for_qc:
        mark_stage(project, "visual_qc", [{"id": asset.id, "path": asset.path} for asset in project.media])
    speed_checkpoint("visual_qc")
    _checkpoint(should_cancel)
    _report(report_progress, 78)
    project.status = "captioning"
    caption_file = run_dir / "captions.ass"
    caption_input = {
        "narration": str(narration), "narration_size": narration.stat().st_size,
        "narration_modified_ns": narration.stat().st_mtime_ns, "script": project.script.narration,
    }
    if not caption_file.exists() or not stage_is_current(project, "captions", caption_input):
        captions.generate_captions(narration, project.script.narration, caption_file)
        mark_stage(project, "captions", caption_input)
    speed_checkpoint("captions")
    project.artifacts["captions"] = str(caption_file)
    dedicated_thumbnail_backgrounds = _generate_thumbnail_backgrounds(project, run_dir)
    thumbnail_backgrounds = dedicated_thumbnail_backgrounds
    if not thumbnail_backgrounds:
        thumbnail_backgrounds = [
            Path(shot.asset_path) for shot in project.shots
            if shot.source_id and shot.asset_type == "screenshot" and shot.asset_path
            and Path(shot.asset_path).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ]
    if not thumbnail_backgrounds:
        raise RuntimeError("thumbnail generation requires at least one traceable real source capture")
    thumbnail_context = " ".join(filter(None, [
        project.script.title,
        project.script.description,
        project.brief.thesis if project.brief else "",
        str(project.episode.get("format") or ""),
    ]))
    thumbnail_evidence_ids = list(dict.fromkeys([
        *(project.brief.claim_ids if project.brief else []),
        *(source.id for source in project.sources),
    ]))
    thumbnail_entities = list(dict.fromkeys(
        entity for source in project.sources for entity in source.entities
    ))[:3]
    declared_thumbnail_companies = [
        str(value) for value in (project.episode.get("thumbnail_companies") or []) if str(value).strip()
    ]
    thumbnail_brand_keys = declared_thumbnail_companies or brand_assets.detect_brand_keys(
        [*thumbnail_entities, *(source.publisher for source in project.sources)],
        context=thumbnail_context,
        source_urls=[str(source.url) for source in project.sources],
    )
    thumbnail_input = {
        "algorithm_version": 9,
        "text": project.script.thumbnail_text,
        "backgrounds": [str(path) for path in thumbnail_backgrounds],
        "topic_context": thumbnail_context,
        "episode_format": str(project.episode.get("format") or ""),
        "evidence_ids": thumbnail_evidence_ids,
        "focal_subject": thumbnail_entities[0] if thumbnail_entities else project.script.title,
        "represented_companies": thumbnail_brand_keys,
        "generate_backplates": THUMBNAIL_GENERATION_ENABLED,
        "backplate_model": IMAGE_MODEL,
        "backplate_fallback_model": IMAGE_FALLBACK_MODEL,
        "backplate_resolution": THUMBNAIL_RESOLUTION,
    }
    existing_thumbs = sorted((run_dir / "thumbnails").glob("thumbnail_*.jpg"))
    if len(existing_thumbs) == 4 and stage_is_current(project, "thumbnails", thumbnail_input):
        thumbs = existing_thumbs
    else:
        thumbs = thumbnail.generate_variants(
            thumbnail_backgrounds,
            project.script.thumbnail_text,
            run_dir / "thumbnails",
            topic_context=thumbnail_context,
            episode_format=str(project.episode.get("format") or ""),
            evidence_ids=thumbnail_evidence_ids,
            focal_subject=thumbnail_entities[0] if thumbnail_entities else project.script.title,
            supporting_subjects=thumbnail_entities[1:],
            represented_companies=thumbnail_brand_keys,
            generate_backplates=THUMBNAIL_GENERATION_ENABLED,
            backplate_model=IMAGE_MODEL,
            backplate_fallback_model=IMAGE_FALLBACK_MODEL,
            backplate_resolution=THUMBNAIL_RESOLUTION,
            require_brand_identity=True,
            must_not_imply=[
                "an unsupported benchmark",
                "a partnership or endorsement",
                "a completed hands-on test that the episode did not perform",
            ],
        )
        mark_stage(project, "thumbnails", thumbnail_input)
    thumbnail_qc = run_dir / "thumbnails" / "thumbnail_qc.json"
    project.qc["thumbnails"] = (
        json.loads(thumbnail_qc.read_text(encoding="utf-8"))
        if thumbnail_qc.is_file() else thumbnail.validate_variants(thumbs, project.script.thumbnail_text)
    )
    thumbnail_manifest = run_dir / "thumbnails" / "thumbnail_manifest.json"
    if thumbnail_manifest.is_file():
        project.qc["thumbnail_strategy"] = json.loads(thumbnail_manifest.read_text(encoding="utf-8"))
    project.artifacts["thumbnails"] = json.dumps([str(path) for path in thumbs])
    for index, path in enumerate(thumbs, start=1):
        project.artifacts[f"thumbnail_{index}"] = str(path)
    if not canary and GENERATIVE_VISUALS_ENABLED:
        _meet_magic_hour_quality_floor(project, run_dir, should_cancel)
    speed_checkpoint("thumbnails_and_quality_floor")
    _checkpoint(should_cancel)
    _report(report_progress, 88)
    project.status = "rendering"
    render_input = {
        "renderer_version": 9,
        "render_profile": {
            "resolution": "1080p",
            "width": VIDEO_W,
            "height": VIDEO_H,
            "fps": VIDEO_FPS,
            "parallelism": RENDER_PARALLELISM,
            "ffmpeg_preset": FFMPEG_PRESET,
            "screen_capture_framing": "centered_safe_crop",
            "narration_end_policy": "audio_master_with_clean_tail",
            "color_profile": str(
                (project.editorial_plan.get("fidelity_visual_overrides") or {}).get("color_profile") or ""
            ),
        },
        "shots": [shot.model_dump() for shot in project.shots], "narration": str(narration),
        "captions": str(caption_file), "music": sorted(str(path) for path in MUSIC_DIR.glob("*")),
    }
    cached_final = Path(project.artifacts.get("video", "")) if project.artifacts.get("video") else None
    if cached_final and cached_final.is_file() and stage_is_current(project, "render", render_input):
        final = cached_final
    else:
        final = render_project(project, run_dir, narration, caption_file, canonical_hash(render_input))
        mark_stage(project, "render", render_input)
    speed_checkpoint("render")
    project.artifacts["video"] = str(final)
    if canary:
        details = qc.probe(final)
        project.qc["final"] = {"passed": bool(details.get("streams")), "canary": True, "duration_seconds": duration(final)}
        project.status = "canary_complete" if project.qc["final"]["passed"] else "qc_failed"
    else:
        project.qc["final"] = qc.run_qc(project, final)
        project.qc["review_readiness"] = qc.review_readiness(project)
        if project.qc["review_readiness"]["passed"] and AUTO_APPROVE_PRIVATE_DRAFTS:
            project.review.final_status = "approved"
            project.review.notes.append("Automatically approved as a private draft; publishing remains disabled.")
            project.status = "approved_final"
        else:
            project.status = "awaiting_final_approval" if project.qc["review_readiness"]["passed"] else "qc_failed"
    package_file = run_dir / "preview_package.json"
    project.artifacts["package"] = str(package_file)
    elapsed_seconds = round(time.perf_counter() - run_started, 3)
    target_seconds = PRODUCTION_TARGET_MINUTES * 60
    project.qc["production_speed"] = {
        "target_seconds": target_seconds,
        "elapsed_seconds": elapsed_seconds,
        "within_target": elapsed_seconds <= target_seconds,
        "checkpoints_seconds": speed_checkpoints,
        "profile": {
            "magic_hour_motion_parallelism": MAGIC_HOUR_MOTION_PARALLELISM,
            "local_motion_render_parallelism": LOCAL_MOTION_RENDER_PARALLELISM,
            "visual_qc_parallelism": VISUAL_QC_PARALLELISM,
            "timeline_render_parallelism": RENDER_PARALLELISM,
        },
    }
    package_file.write_text(
        json.dumps(project.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    save_project(project, run_dir)
    _report(report_progress, 98)
    return {
        "episode_id": project.episode_id, "status": project.status, "artifacts": project.artifacts,
        "qc": project.qc, "credits": project.costs,
    }


def produce_next(
    scheduled_date: str | None = None, *, should_cancel: CancelCheck = None,
    report_progress: ProgressCallback = None,
) -> dict:
    target = scheduled_date or date.today().isoformat()
    candidates = []
    for project_file in EPISODE_DATA_DIR.glob("episode_*/episode_project.json"):
        try:
            project = load_project(project_file.parent)
        except Exception:
            continue
        if project.scheduled_date <= target and project.status in {"approved_for_production", "revision_requested"}:
            candidates.append(project)
    if not candidates:
        raise LookupError(f"no approved episode is ready for {target}")
    selected = sorted(candidates, key=lambda item: (item.scheduled_date, item.created_at))[0]
    return produce_episode(selected.episode_id, should_cancel=should_cancel, report_progress=report_progress)


def produce_canary(
    episode_id: str, *, should_cancel: CancelCheck = None, report_progress: ProgressCallback = None,
) -> dict:
    _checkpoint(should_cancel)
    source_project = load_project(_episode_dir(episode_id))
    if not source_project.brief:
        raise ValueError("canary source episode has no brief")
    canary_id = f"{episode_id}_canary"
    canary_dir = _episode_dir(canary_id)
    if (canary_dir / "episode_project.json").is_file():
        project = load_project(canary_dir)
        if project.script:
            project.brief.claim_ids = [claim.id for claim in project.claims]
            if len(project.script.beats) > 2:
                project.script.beats = project.script.beats[:2]
            if not project.script.title.endswith(" - 60 Second Canary"):
                project.script.title += " - 60 Second Canary"
            claims_input = _claims_stage_input(project)
            script_input = {
                "editorial_algorithm_version": 6,
                "brief": project.brief.model_dump(mode="json"),
                "claims": [claim.model_dump(mode="json") for claim in project.claims],
                "duration_profile": editorial.duration_profile(project),
            }
            project.qc["fact_check"] = {
                "passed": True,
                "canary": True,
                "note": "Technical canary excerpt; full-episode verification remains mandatory.",
            }
            project.status = "canary_preparing"
            mark_stage(project, "claims", claims_input)
            mark_stage(project, "script", script_input)
            save_project(project, canary_dir)
            return produce_episode(
                canary_id, canary=True, should_cancel=should_cancel, report_progress=report_progress,
            )
    else:
        project = EpisodeProject(
            episode_id=canary_id, scheduled_date=source_project.scheduled_date,
            episode={
                "format": source_project.episode.get("format"),
                "creative_profile": source_project.episode.get("creative_profile", "hermes-proof-first-v1"),
                "canary_of": episode_id,
            },
            brief=deepcopy(source_project.brief), sources=deepcopy(source_project.sources), status="canary_preparing",
        )
        project.brief.approved = True
        project.claims = editorial.extract_claims(project.brief, project.sources)
        project.brief.claim_ids = [claim.id for claim in project.claims]
        claims_input = _claims_stage_input(project)
        mark_stage(project, "claims", claims_input)
        save_project(project, canary_dir)
    _checkpoint(should_cancel)
    full_script, verification, revision_count = editorial.write_verified_script(project)
    full_script.beats = full_script.beats[:2]
    full_script.title += " - 60 Second Canary"
    project.script = full_script
    project = EpisodeProject.model_validate(project.model_dump())
    script_input = {
        "editorial_algorithm_version": 6,
        "brief": project.brief.model_dump(mode="json"),
        "claims": [claim.model_dump(mode="json") for claim in project.claims],
        "duration_profile": editorial.duration_profile(project),
    }
    project.qc["fact_check"] = {
        "passed": bool(verification.get("passed")),
        "canary": True,
        "automatic_revisions": revision_count,
        "note": "The canary reuses the first two beats from the independently verified full script.",
    }
    mark_stage(project, "script", script_input)
    save_project(project, canary_dir)
    return produce_episode(
        canary_id, canary=True, should_cancel=should_cancel, report_progress=report_progress,
    )
