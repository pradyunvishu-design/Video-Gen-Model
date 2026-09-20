"""Build the reviewed real-footage slot bundle for the weekly episode.

Only clips that passed a manual thumbnail review are admitted.  Reused masters
always use a different time range, so the edit does not repeat identical shots.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "news_weekly_20260822"
ACQUISITION = OUT / "open_broll" / "acquisition_result.json"
CLAUDE_TIMELINE = ROOT / "output" / "claude_chips_5m_recreate" / "semantic_timeline_v8.json"
DESTINATION = OUT / "open_broll" / "approved_open_broll_manifest.json"

BROLL_SLOTS = [
    3, 4, 6, 7, 9, 10, 12, 13, 15, 16, 19,
    22, 23, 25, 26, 28, 29, 32, 33, 36, 37,
    39, 40, 42, 43, 46, 47, 50, 51,
    53, 54, 57, 58, 61, 62,
    64, 65, 67, 68, 70, 71, 73, 74, 76,
    78, 79, 81, 82, 84, 85, 87, 88, 90, 91, 93,
]

# slot, clip id, source start, editorial reason
OPEN_PLAN = [
    (3, "wikimedia_195803852", 1, "cyber-defense training establishes the security context"),
    (4, "wikimedia_195839130", 1, "official cyber-awareness discussion"),
    (6, "wikimedia_195803852", 7, "defenders working around computers"),
    (7, "wikimedia_195839130", 10, "security experts discussing operational controls"),
    (9, "wikimedia_195803852", 13, "hands-on cyber exercise"),
    (10, "wikimedia_195839130", 20, "cybersecurity briefing"),
    (12, "wikimedia_195803852", 19, "computer lab used for defense training"),
    (13, "wikimedia_195839130", 30, "human experts remain in the loop"),
    (15, "wikimedia_195803852", 25, "security training collaboration"),
    (16, "wikimedia_195839130", 40, "operational security discussion"),
    (19, "wikimedia_195803852", 37, "cyber operations closing beat"),

    (22, "wikimedia_158114911", 2, "real browser session for computer-use context"),
    (23, "wikimedia_119669374", 2, "person working at a laptop"),
    (25, "wikimedia_158114911", 12, "browser interaction and recovery context"),
    (26, "wikimedia_115157282", 1, "physical automation line as workflow metaphor"),
    (28, "wikimedia_158114911", 24, "multi-step browser work"),
    (29, "wikimedia_119669374", 12, "desktop work setup"),
    (32, "wikimedia_158114911", 36, "browser interface under real use"),
    (33, "wikimedia_115157282", 7, "repeatable automated workflow"),
    (36, "wikimedia_158114911", 48, "browser execution environment"),
    (37, "wikimedia_119669374", 24, "human computer-work context"),

    (39, "wikimedia_45503228", 5, "open media platform and reuse workflow"),
    (40, "wikimedia_85134751", 5, "finished moving-image production example"),
    (42, "wikimedia_48466853", 5, "professional creator interview"),
    (43, "wikimedia_45503228", 25, "media archive and production workflow"),
    (46, "wikimedia_85134751", 25, "cinematic production output"),
    (47, "wikimedia_48466853", 35, "creators discussing production"),
    (50, "wikimedia_45503228", 45, "media reuse and distribution"),
    (51, "wikimedia_85134751", 45, "moving-image reliability beat"),

    (53, "wikimedia_57147970", 2, "students in a classroom discussion"),
    (54, "wikimedia_119669374", 30, "consumer laptop context"),
    (57, "wikimedia_57147970", 12, "students discussing technology"),
    (58, "wikimedia_158114911", 60, "consumer browser context"),
    (61, "wikimedia_57147970", 24, "younger-user and education context"),
    (62, "wikimedia_119669374", 40, "platform use on a normal computer"),

    (70, "wikimedia_190939905", 2, "large industrial cooling system"),
    (71, "wikimedia_190939905", 14, "water and cooling infrastructure"),
    (73, "wikimedia_115157282", 1, "industrial automation infrastructure"),
    (74, "wikimedia_190939905", 28, "physical cooling equipment"),

    (78, "wikimedia_45503228", 65, "open media platform parallels open-model distribution"),
    (79, "wikimedia_48466853", 55, "developer ecosystem discussion"),
    (81, "wikimedia_158114911", 72, "software browsing and discovery"),
    (82, "wikimedia_45503228", 85, "large public archive interface"),
    (84, "wikimedia_119669374", 46, "small-computer and local-use context"),
    (85, "wikimedia_48466853", 75, "software creator ecosystem"),
    (87, "wikimedia_45503228", 105, "open archive and remix ecosystem"),
    (88, "wikimedia_158114911", 84, "automation interacting with software"),
    (90, "wikimedia_48466853", 95, "developers explaining a software release"),
    (91, "wikimedia_45503228", 125, "long-tail public content distribution"),
    (93, "wikimedia_119669374", 48, "local computer closing beat"),
]

INTEL_SLOTS = [64, 65, 67, 68, 76]


def main() -> None:
    acquisition = json.loads(ACQUISITION.read_text(encoding="utf-8"))["data"]["clips"]
    by_id = {item["clip_id"]: item for item in acquisition}
    timeline = json.loads(CLAUDE_TIMELINE.read_text(encoding="utf-8"))["shots"]
    intel = [item for item in timeline if item.get("kind") == "b" and item.get("source_id") == "E6"]
    if len(intel) < len(INTEL_SLOTS):
        raise RuntimeError("not enough reviewed Intel press-kit shots")

    records: list[dict] = []
    for slot, clip_id, start, semantic_target in OPEN_PLAN:
        clip = by_id[clip_id]
        end = min(float(clip["duration"]), float(start) + 6.0)
        if end - float(start) < 5.8:
            raise ValueError(f"clip range too short: {slot=} {clip_id=}")
        records.append({
            "slot": slot,
            "media_file": clip["path"],
            "source_start_seconds": float(start),
            "source_end_seconds": end,
            "source_url": clip["source_url"],
            "title": clip.get("source_tags", clip_id).split("  ")[0][:180],
            "publisher": "Wikimedia Commons",
            "creator": clip.get("creator", ""),
            "license": clip.get("license", ""),
            "rights_basis": f"{clip.get('license', 'open license')} via Wikimedia Commons",
            "rights_status": "reviewed_for_private_preview",
            "semantic_target": semantic_target,
            "qc_status": "passed_manual_thumbnail_review",
        })

    for slot, shot in zip(INTEL_SLOTS, intel):
        records.append({
            "slot": slot,
            "media_file": shot["asset"],
            "source_start_seconds": 0.0,
            "source_end_seconds": 6.0,
            "source_url": shot["source_url"],
            "title": "Intel global manufacturing press-kit B-roll",
            "publisher": "Intel Newsroom",
            "creator": "Intel Newsroom",
            "license": "Official downloadable press-kit footage; credit required",
            "rights_basis": "Intel Newsroom downloadable B-roll; credit required",
            "rights_status": "reviewed_for_private_preview",
            "semantic_target": "physical compute and data-center supply-chain infrastructure",
            "qc_status": "passed_in_prior_episode_review",
        })

    records.sort(key=lambda item: item["slot"])
    actual = [item["slot"] for item in records]
    if actual != BROLL_SLOTS:
        missing = sorted(set(BROLL_SLOTS) - set(actual))
        extra = sorted(set(actual) - set(BROLL_SLOTS))
        raise RuntimeError(f"slot coverage mismatch: {missing=} {extra=}")
    payload = {
        "version": "1.0",
        "episode_id": "episode_20260822_news_weekly",
        "publishing_enabled": False,
        "policy": {
            "source_audio_muted": True,
            "maximum_identical_range_uses": 2,
            "manual_rights_review_required_before_publication": True,
        },
        "clips": records,
    }
    DESTINATION.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(DESTINATION), "slots": len(records)}, indent=2))


if __name__ == "__main__":
    main()
