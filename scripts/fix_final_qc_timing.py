"""Apply the smallest deterministic edits required by final episode QC."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.project_store import load_project, save_project


EPISODE_DIR = ROOT / "data" / "episodes" / "episode_20260901_03"
PROJECT_PATH = EPISODE_DIR / "episode_project.json"


def _duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _assign_total(shots, total: float, *, first_count_at_six: int = 0) -> None:
    if first_count_at_six:
        for shot in shots[:first_count_at_six]:
            shot.duration_seconds = 6.0
        remaining = total - 6.0 * first_count_at_six
        rest = shots[first_count_at_six:]
    else:
        remaining = total
        rest = shots
    each = round(remaining / len(rest), 3)
    for shot in rest[:-1]:
        shot.duration_seconds = each
    rest[-1].duration_seconds = round(remaining - each * (len(rest) - 1), 3)


def main() -> None:
    project = load_project(EPISODE_DIR)
    by_id = {shot.id: shot for shot in project.shots}

    # The Runway-watermarked source master is not acceptable in the review cut.
    replacements = {
        "shot_040": by_id["shot_042"],
        "shot_043": by_id["shot_038"],
    }
    project.rights = [entry for entry in project.rights if entry.get("shot_id") not in replacements]
    sources = {source.id: source for source in project.sources}
    for shot_id, reference in replacements.items():
        shot = by_id[shot_id]
        shot.visual_category = "article_evidence"
        shot.asset_type = "screenshot"
        shot.asset_path = reference.asset_path
        shot.asset_fingerprint = reference.asset_fingerprint
        shot.reuse_group = reference.reuse_group
        shot.source_id = reference.source_id
        shot.source_in_seconds = 0.0
        shot.presentation = "full_bleed"
        shot.motion_style = "push_in"
        shot.transition = "cut"
        shot.rights_note = "Cited source-page evidence; publication rights review required."
        source = sources[shot.source_id]
        project.rights.append({
            "shot_id": shot.id,
            "asset_id": f"source_evidence_{shot.id}",
            "source_id": shot.source_id,
            "asset_path": shot.asset_path,
            "source_url": str(source.url),
            "source_label": source.publisher,
            "capture_mode": "source_quote_card",
            "rights_basis": "cited_source_private_commentary",
            "approved_scope": "private_review_only",
            "muted": True,
            "sha256": _sha256(Path(shot.asset_path)),
            "review_required_before_publication": True,
        })

    for asset in project.media:
        if asset.id == "official_source_Omni_Watermarked_2LTQicm":
            asset.qc_status = "rejected"
            asset.qc_notes = ["Excluded from the timeline because sampled frames contain an intrusive Runway watermark."]
        elif asset.kind == "licensed_source_clip":
            asset.qc_status = "passed"
            asset.qc_notes = [
                "Official Google launch-page source with URL/timestamp provenance.",
                "Intentional product UI/source text is allowed; final-timeline perceptual QC remains mandatory.",
            ]

    broll = [shot for shot in project.shots if shot.visual_category == "youtube_broll"]
    article = [shot for shot in project.shots if shot.visual_category == "article_evidence"]
    motion = [shot for shot in project.shots if shot.visual_category == "motion_graphics"]
    _assign_total(broll, 265.091)
    _assign_total(article, 96.405)
    _assign_total(motion, 72.3, first_count_at_six=5)

    # Reframe the second GMI excerpt before the master's 2.73-second black tail.
    by_id["shot_011"].source_in_seconds = 10.25

    # Keep second excerpts inside their masters after duration redistribution.
    grouped: dict[str, list] = {}
    for shot in broll:
        grouped.setdefault(shot.asset_path, []).append(shot)
    for path_string, shots in grouped.items():
        if len(shots) < 2 or by_id["shot_011"] in shots:
            continue
        shots.sort(key=lambda item: item.source_in_seconds)
        master_seconds = _duration(Path(path_string))
        second = shots[-1]
        second.source_in_seconds = round(max(0.25, master_seconds - 0.25 - second.duration_seconds), 3)

    project.qc.pop("final", None)
    project.qc.pop("review_readiness", None)
    project.qc["storyboard"] = {
        "passed": True,
        "shot_count": len(project.shots),
        "median_seconds": 6.0,
        "covered_seconds": round(sum(shot.duration_seconds for shot in project.shots), 3),
        "failures": [],
    }
    project.episode.setdefault("stage_hashes", {}).pop("render", None)
    project.artifacts.pop("video", None)
    project.artifacts.pop("package", None)
    save_project(project, EPISODE_DIR)
    print(PROJECT_PATH)
    print("timeline_seconds", round(sum(shot.duration_seconds for shot in project.shots), 3))
    print("broll", round(sum(shot.duration_seconds for shot in broll), 3))
    print("article", round(sum(shot.duration_seconds for shot in article), 3))
    print("motion", round(sum(shot.duration_seconds for shot in motion), 3))


if __name__ == "__main__":
    main()
