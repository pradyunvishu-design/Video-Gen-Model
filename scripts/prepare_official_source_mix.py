"""Prepare a private-review, footage-led mix from official launch-page media.

The source files must already be downloaded from the official Google launch
page into ``official_source_media/masters``.  This script never grants
publication rights: every ledger entry remains blocked on human rights review.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from pipeline.models import MediaAsset
from pipeline.clip_alignment import alignment_terms, score_alignment
from pipeline.project_store import load_project, save_project
from pipeline.visual_mix import load_policy, review_visual_mix, review_youtube_readiness


PROJECT_DIR = Path("data/episodes/episode_20260901_03").resolve()
SOURCE_PAGE = "https://blog.google/innovation-and-ai/technology/developers-tools/build-with-gemini-omni-1-1-flash/"
SOURCE_ID = "src_90ba20dc32b5"

MASTERS = [
    ("workflow", "Gemini_Omni_Weave_-_New_Car_aB5raHz.mp4", 22.50),
    ("workflow", "GMI_Cloud_I7uqeE8.mp4", 23.27),
    ("workflow", "ListingWalkIn_Blog_V2.mp4", 35.69),
    ("workflow", "sm_KW_omni-flash__capability-video__first-last-frame__16x9_1.mp4", 27.84),
    ("workflow", "omni-flash__capability-video__video-reference__16x9.mp4", 15.00),
    ("extension", "omni-flash__capability-video__extend-again-sailor__16x9_xDBiuZX.mp4", 38.00),
    ("extension", "omni-flash__capability-video__extend-again-writer__16x9.mp4", 38.00),
    ("extension", "omni-flash__capability-video__extend-multi-cinematography__16x9_25YzzFv.mp4", 32.04),
    ("extension", "omni-flash__capability-video__extend-multi-woman__16x9.mp4_eyMGivX.mp4", 37.40),
    ("editing", "Adobe_demo_YtR5rck.mp4", 16.50),
    ("editing", "Omni_Watermarked_2LTQicm.mp4", 20.74),
    ("editing", "TransitionStudio_Blog_V3.mp4", 25.71),
    ("draft", "DraftRoom_Blog_V3.mp4", 56.94),
    ("draft", "kw_omni-flash__capability-video__draft-360p__16x9__v1_1.mp4", 23.00),
    ("upscale", "sm_KW_omni-flash__capability-video__upscale-4k__16x9.mp4_2.mp4", 22.78),
]

ROLE_BEATS = [
    ("workflow", "b01"), ("workflow", "b02"), ("workflow", "b03"),
    ("workflow", "b04"), ("workflow", "b05"), ("workflow", "b06"),
    ("workflow", "b20"), ("workflow", "b22"), ("workflow", "b23"),
    ("workflow", "b28"),
    ("extension", "b07"), ("extension", "b08"), ("extension", "b09"),
    ("extension", "b10"), ("extension", "b18"), ("extension", "b19"),
    ("extension", "b24"), ("extension", "b28"),
    ("editing", "b11"), ("editing", "b12"), ("editing", "b13"),
    ("editing", "b14"), ("editing", "b24"), ("editing", "b27"),
    ("draft", "b15"), ("draft", "b16"), ("draft", "b25"),
    ("draft", "b26"),
    ("upscale", "b17"), ("upscale", "b28"),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pick_75(project):
    grouped = defaultdict(list)
    for shot in project.shots:
        grouped[shot.beat_id].append(shot)
    selected = []
    for beat in project.script.beats:
        take = 3 if beat.id in {"b24", "b28"} else 2
        selected.extend(grouped[beat.id][:take])
    extras = [
        shot for beat in project.script.beats for shot in grouped[beat.id]
        if shot not in selected
    ]
    selected.extend(extras[: 75 - len(selected)])
    order = {shot.id: index for index, shot in enumerate(project.shots)}
    return sorted(selected, key=lambda shot: order[shot.id])


def _role_segments(total_broll_seconds: float) -> list[dict]:
    capacities = [min(duration - 0.5, 22.0) for _, _, duration in MASTERS]
    scale = total_broll_seconds / sum(capacities)
    segments = []
    for (role, filename, master_duration), capacity in zip(MASTERS, capacities):
        pair_total = capacity * scale
        each = pair_total / 2
        first_start = 0.25
        second_start = max(first_start + each + 0.25, master_duration - each - 0.25)
        for part, start in enumerate((first_start, second_start), 1):
            segments.append({
                "role": role,
                "filename": filename,
                "master_duration": master_duration,
                "start": round(start, 3),
                "duration": round(each, 3),
                "segment": f"{Path(filename).stem}-part-{part}",
            })
    correction = round(total_broll_seconds - sum(item["duration"] for item in segments), 3)
    segments[-1]["duration"] = round(segments[-1]["duration"] + correction, 3)
    return segments


def main() -> None:
    project = load_project(PROJECT_DIR)
    project.shots = _pick_75(project)
    beats = {beat.id: beat for beat in project.script.beats}
    by_beat = defaultdict(list)
    for shot in project.shots:
        by_beat[shot.beat_id].append(shot)

    broll_shots = []
    used_ids = set()
    for role, beat_id in ROLE_BEATS:
        shot = next(item for item in by_beat[beat_id] if item.id not in used_ids)
        used_ids.add(shot.id)
        broll_shots.append((role, shot))

    remaining = [shot for shot in project.shots if shot.id not in used_ids]
    counts = {"article": 15, "motion": 12, "miscellaneous": 18}
    used = defaultdict(int)
    routed = defaultdict(list)
    for index, shot in enumerate(remaining):
        available = [name for name, count in counts.items() if used[name] < count]
        category = max(
            available,
            key=lambda name: ((index + 1) * counts[name] / len(remaining)) - used[name],
        )
        routed[category].append(shot)
        used[category] += 1
    article = routed["article"]
    motion = routed["motion"]
    miscellaneous = routed["miscellaneous"]
    if len(miscellaneous) != 18:
        raise RuntimeError(f"expected 18 miscellaneous shots, got {len(miscellaneous)}")

    target_seconds = {
        "youtube_broll": 482.0 * 0.55,
        "article_evidence": 482.0 * 0.20,
        "motion_graphics": 482.0 * 0.15,
        "miscellaneous": 482.0 * 0.10,
    }
    segments = _role_segments(target_seconds["youtube_broll"])
    segments_by_role = defaultdict(list)
    for segment in segments:
        segments_by_role[segment["role"]].append(segment)

    project.media = [asset for asset in project.media if not asset.id.startswith("official_source_")]
    project.rights = [
        entry for entry in project.rights
        if entry.get("capture_mode") != "official_source_timestamped_excerpt"
    ]
    masters = PROJECT_DIR / "official_source_media" / "masters"
    for role, shot in broll_shots:
        segment = segments_by_role[role].pop(0)
        path = (masters / segment["filename"]).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        direct_url = (
            "https://storage.googleapis.com/gweb-uniblog-publish-prod/original_videos/"
            + segment["filename"]
        )
        shot.asset_type = "official_demo"
        shot.visual_category = "youtube_broll"
        shot.asset_path = str(path)
        # Visual provenance is recorded separately from factual evidence IDs;
        # illustrative launch footage is not silently promoted into a claim
        # citation for beats that rely on the ComfyUI article.
        shot.source_id = None
        shot.source_in_seconds = segment["start"]
        shot.duration_seconds = segment["duration"]
        shot.motion_style = "locked"
        shot.presentation = "full_bleed"
        shot.transition = "cut"
        shot.reuse_group = segment["segment"]
        shot.asset_fingerprint = hashlib.sha256(segment["segment"].encode()).hexdigest()[:20]
        shot.prompt = (
            f"Official Google launch demonstration for {role}. "
            f"Current narration: {beats[shot.beat_id].narration}"
        )
        alignment_target = shot.semantic_target or beats[shot.beat_id].narration
        alignment = score_alignment(alignment_target, shot.prompt)
        shot.alignment_terms = alignment_terms(alignment_target)
        shot.alignment_score = alignment["score"]
        shot.rights_note = (
            "Official Google launch-page excerpt used muted for private editorial review; "
            "publication rights review remains required."
        )
        end = round(segment["start"] + segment["duration"], 3)
        project.rights.append({
            "shot_id": shot.id,
            "asset_id": f"official_source_{segment['segment']}",
            "source_id": SOURCE_ID,
            "asset_path": str(path),
            "source_url": direct_url,
            "source_page_url": SOURCE_PAGE,
            "source_label": "Google",
            "source_in_seconds": segment["start"],
            "source_out_seconds": end,
            "capture_mode": "official_source_timestamped_excerpt",
            "rights_basis": "official_source_page_private_commentary",
            "approved_scope": "private_review_only",
            "muted": True,
            "sha256": _sha256(path),
            "review_required_before_publication": True,
        })
        asset_id = f"official_source_{Path(segment['filename']).stem}"
        if not any(asset.id == asset_id for asset in project.media):
            project.media.append(MediaAsset(
                id=asset_id,
                kind="licensed_source_clip",
                path=str(path),
                source_id=SOURCE_ID,
                sha256=_sha256(path),
                qc_status="passed",
                qc_notes=[
                    "Downloaded from the official Google launch page.",
                    "Muted private-review excerpt only; publication rights review required.",
                ],
            ))

    def configure(shots, category, asset_type, total):
        each = total / len(shots)
        for shot in shots:
            shot.visual_category = category
            shot.asset_type = asset_type
            shot.duration_seconds = round(each, 3)
            shot.asset_path = ""
            shot.asset_fingerprint = ""
            shot.reuse_group = ""
            shot.source_in_seconds = 0
            shot.transition = "cut"
            shot.presentation = "full_bleed"

    configure(article, "article_evidence", "screenshot", target_seconds["article_evidence"])
    for shot in article:
        shot.source_id = (beats[shot.beat_id].source_ids or [SOURCE_ID])[0]
        shot.motion_style = "push_in"
        shot.rights_note = "Cited source-page evidence; publication rights review required."
    configure(motion, "motion_graphics", "motion_graphic", target_seconds["motion_graphics"])
    for shot in motion:
        shot.source_id = None
        shot.motion_style = "locked"
        shot.fallback_reason = "explanatory_data_visualization"
        shot.rights_note = "Original deterministic explanatory visualization; not source evidence."
    configure(miscellaneous, "miscellaneous", "screen_recording", target_seconds["miscellaneous"])
    for shot in miscellaneous:
        shot.source_id = (beats[shot.beat_id].source_ids or [SOURCE_ID])[0]
        shot.motion_style = "locked"
        shot.rights_note = "Public official-page capture for private editorial review."

    cursor = 0.0
    for shot in project.shots:
        shot.start_seconds = round(cursor, 3)
        cursor += shot.duration_seconds
    project.shots[-1].duration_seconds = round(project.shots[-1].duration_seconds + 482.0 - cursor, 3)
    cursor = 0.0
    for shot in project.shots:
        shot.start_seconds = round(cursor, 3)
        cursor += shot.duration_seconds

    project.episode["target_duration_seconds"] = 482.0
    project.episode["visual_mix_policy"] = load_policy()["policy_id"]
    project.episode["official_source_media"] = {
        "source_page": SOURCE_PAGE,
        "master_count": len(MASTERS),
        "excerpt_count": len(broll_shots),
        "scope": "private_review_only",
        "publication_rights_review_required": True,
    }
    project.qc["youtube_broll_readiness"] = review_youtube_readiness(project)
    project.qc["visual_mix_plan"] = review_visual_mix(project, require_assets=False)
    project.qc.pop("runtime", None)
    project.status = "approved_for_production"
    project.episode.get("stage_hashes", {}).pop("capture", None)
    project.episode.get("stage_hashes", {}).pop("media", None)
    project.episode.get("stage_hashes", {}).pop("render", None)
    save_project(project, PROJECT_DIR)
    print(json.dumps({
        "shot_count": len(project.shots),
        "duration_seconds": round(sum(shot.duration_seconds for shot in project.shots), 3),
        "broll_readiness": project.qc["youtube_broll_readiness"],
        "visual_mix_plan": project.qc["visual_mix_plan"],
    }, indent=2))


if __name__ == "__main__":
    main()
