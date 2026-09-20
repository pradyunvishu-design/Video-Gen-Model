"""Reassemble the Claude chip episode with semantic clip order and v7 motion.

All third-party shots come from the two existing Intel Newsroom press-kit
masters in rights_ledger.json.  Every B-roll asset is used at most twice and
never inside a three-shot cooldown.  The script reuses normalized v6 cache
segments, so only the eight new motion inserts are encoded.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "output" / "claude_chips_5m_recreate"
CACHE = RUN / "assembly_cache_v6"
MOTION = RUN / "motion_v3_ailabs" / "motion_pack_v7_premium.mp4"
OUT_DIR = RUN / "assembly_cache_v7_semantic"
FINAL = RUN / "claude_chip_validation_5m_premium_semantic_v7.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

PACKAGING_URL = "https://newsroom.intel.com/press-kit/global-manufacturing"
EVENT_URL = "https://newsroom.intel.com/press-kit/intel-vision-2024"
ANTHROPIC_URL = "https://www.anthropic.com/news/ust-claude"

# Slot, kind, identifier, semantic target. Every slot is exactly six seconds.
# Motion identifiers are the scene index in the 48-second motion pack.
TIMELINE = [
    ("b", "broll_002_packaging", "chip manufacturing facility establishes the physical setting"),
    ("b", "broll_004_packaging", "engineers and equipment inside a semiconductor clean room"),
    ("m", 0, "Claude enters the software-heavy chip validation lab workflow"),
    ("b", "broll_006_packaging", "automated semiconductor equipment running a real manufacturing process"),
    ("b", "broll_008_packaging", "close view of chip production machinery"),
    ("e", 0, "primary Anthropic and UST case-study evidence for the announcement"),
    ("b", "broll_010_packaging", "wafer inspection equipment performing a physical measurement"),
    ("b", "broll_012_packaging", "clean-room technician operating semiconductor equipment"),
    ("m", 1, "lock the claim to the Anthropic source and define the supported scope"),
    ("b", "broll_014_packaging", "clean-room operator during validation work"),
    ("b", "broll_016_packaging", "technician moving through the semiconductor facility"),
    ("e", 1, "source-backed explanation of chip tests and physical measurements"),
    ("b", "broll_018_packaging", "semiconductor production aisle and controlled equipment"),
    ("b", "broll_020_packaging", "equipment row used for repeated production checks"),
    ("m", 2, "show the validation chain from specification to measured proof"),
    ("b", "broll_022_packaging", "semiconductor tools that produce physical evidence"),
    ("b", "broll_024_packaging", "specialized chamber used in a controlled hardware process"),
    ("e", 2, "primary source describing schematics tests regressions and equipment data"),
    ("b", "broll_026_packaging", "silicon wafer as the object being tested"),
    ("b", "broll_027_event", "engineering equipment and monitors used to inspect results"),
    ("m", 3, "separate Claude's real validation role from autonomous chip design"),
    ("b", "broll_025_event", "robotic test equipment executing a controlled procedure"),
    ("b", "broll_029_event", "physical chip display connects the software loop to hardware"),
    ("b", "broll_033_event", "instrument panel and engineering demonstration"),
    ("e", 3, "case-study evidence for the iDEC closed-loop workflow"),
    ("b", "broll_013_event", "official Intel chip demonstration supports the hardware context"),
    ("b", "broll_023_event", "official keynote view of processor components"),
    ("m", 5, "attribute the reported 50 to 70 percent and four-day to 48-hour result"),
    ("b", "broll_028_packaging", "large semiconductor facility illustrates production-scale cycle time"),
    ("b", "broll_040_packaging", "fab exterior illustrates the operational scale behind the reported result"),
    ("b", "broll_041_packaging", "second exterior angle maintains scale without repeating the same clip"),
    ("e", 4, "primary source keeps the company-reported performance claim attributed"),
    ("b", "broll_015_event", "official chip presentation as context for the company-reported claim"),
    ("b", "broll_017_event", "official demo screen and presenter tie the claim to a real product context"),
    ("m", 4, "show failure isolation rerun and evidence review"),
    ("b", "broll_011_event", "engineers reviewing a chip demonstration together"),
    ("b", "broll_021_event", "two people discussing technical output supports human review"),
    ("b", "broll_031_event", "technical interview illustrates accountable human judgment"),
    ("e", 5, "source-backed control requirements and independent rerun"),
    ("b", "broll_019_event", "human presenter explains a consequential technical decision"),
    ("m", 6, "show the explicit human approval gate after generation and reproduction"),
    ("b", "broll_037_event", "engineering conversation illustrates review rather than autonomous approval"),
    ("b", "broll_010_packaging", "repeat the measurement device only after a long cooldown for independent rerun"),
    ("b", "broll_012_packaging", "repeat the technician only after a long cooldown for qualified review"),
    ("e", 6, "primary-source summary of what Claude does and does not prove"),
    ("b", "broll_016_packaging", "physical semiconductor work grounds the final verdict"),
    ("b", "broll_013_event", "official processor demonstration supports the narrow adoption claim"),
    ("m", 7, "final verdict: useful when grounded in evidence audit trails and review"),
    ("b", "broll_002_packaging", "return to the fab after a long cooldown to close on real-world stakes"),
    ("b", "broll_025_event", "controlled test equipment closes on proof rather than fluent output"),
]


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ledger = json.loads((RUN / "shot_ledger.json").read_text(encoding="utf-8"))
    broll = {Path(item["source"]).stem: Path(item["output"]) for item in ledger if item["kind"] == "b"}
    evidence = {int(item["label"].split("_")[-1]): Path(item["output"]) for item in ledger if item["kind"] == "e"}

    motion_segments: dict[int, Path] = {}
    for scene_index in sorted({int(identifier) for kind, identifier, _ in TIMELINE if kind == "m"}):
        destination = OUT_DIR / f"motion_{scene_index:02d}.mp4"
        motion_segments[scene_index] = destination
        if not destination.exists():
            run([
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", str(scene_index * 6), "-i", str(MOTION), "-t", "6",
                "-an", "-vf", "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-g", "60",
                "-video_track_timescale", "90000", str(destination),
            ])

    selected: list[Path] = []
    manifest: list[dict] = []
    last_seen: dict[str, int] = {}
    uses: dict[str, int] = {}
    for slot, (kind, identifier, target) in enumerate(TIMELINE):
        if kind == "b":
            path = broll[str(identifier)]
            source_url = PACKAGING_URL if str(identifier).endswith("packaging") else EVENT_URL
            source_id = "E6"
            key = str(identifier)
        elif kind == "e":
            path = evidence[int(identifier)]
            source_url = ANTHROPIC_URL
            source_id = ["E1", "E2", "E2", "E3", "E1", "E7", "E2"][int(identifier)]
            key = f"evidence_{int(identifier):02d}"
        else:
            path = motion_segments[int(identifier)]
            source_url = ANTHROPIC_URL
            source_id = "derived_editorial_graphic"
            key = f"motion_{int(identifier):02d}"
        uses[key] = uses.get(key, 0) + 1
        if uses[key] > 2:
            raise RuntimeError(f"asset reuse exceeds two: {key}")
        if key in last_seen and slot - last_seen[key] <= 3:
            raise RuntimeError(f"asset repeats inside three-shot cooldown: {key}")
        last_seen[key] = slot
        selected.append(path)
        manifest.append({
            "slot": slot, "timeline_start": slot * 6, "duration": 6,
            "kind": kind, "asset": str(path), "reuse_key": key,
            "use_number": uses[key], "semantic_target": target,
            "source_id": source_id, "source_url": source_url,
            "source_audio_muted": True,
        })

    concat_file = OUT_DIR / "timeline.concat.txt"
    concat_file.write_text(
        "".join(f"file '{path.as_posix()}'\n" for path in selected), encoding="utf-8",
    )
    silent = OUT_DIR / "visuals_300s.mp4"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(silent)])
    run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(silent),
        "-i", str(CACHE / "narration_300s_v2.m4a"), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(FINAL),
    ])
    (RUN / "semantic_timeline_v7.json").write_text(
        json.dumps({
            "version": "2.0-semantic-v7", "final": str(FINAL),
            "policy": {"max_asset_uses": 2, "cooldown_shots": 3, "publishing_enabled": False},
            "shots": manifest,
        }, indent=2), encoding="utf-8",
    )
    probe = subprocess.check_output([
        FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height,r_frame_rate",
        "-of", "json", str(FINAL),
    ], text=True)
    print(probe)


if __name__ == "__main__":
    main()
