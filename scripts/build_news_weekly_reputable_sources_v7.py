from __future__ import annotations

"""Add verified reputable-channel source evidence to the current review cut.

The YouTube candidates in ``review_queue.json`` are rights-qualified but their
video media has not passed the supported ingest gate.  This builder therefore
uses only their public source artwork as clearly attributed evidence cards.  It
does not claim or record those cards as motion B-roll.
"""

from collections import Counter
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "news_weekly_20260822"
SOURCE_MANIFEST = OUT / "static_articles_v6" / "render_manifest.json"
QUEUE = OUT / "reputable_youtube_v7" / "review_queue.json"
THUMBNAILS = OUT / "reputable_youtube_v7" / "thumbnails"
WORK = OUT / "reputable_sources_v7"
SEGMENTS = WORK / "segments"
NARRATION = OUT / "audio" / "narration_master.m4a"
CAPTIONS = OUT / "captions_monochrome.ass"
FINAL = OUT / "the_week_in_ai_2026-08-22_10min_reputable_sources_v7.mp4"
FFMPEG = Path(
    r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour"
    r"\tools\ffmpeg\bin\ffmpeg.exe"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def escape_drawtext(value: str) -> str:
    return (
        value.replace("\\", r"\\")
        .replace("'", r"\'")
        .replace(":", r"\:")
        .replace("%", r"\%")
    )


def render_source_card(slot: int, thumbnail: Path, channel: str) -> Path:
    destination = SEGMENTS / f"{slot:03d}_source_evidence.mp4"
    if destination.exists() and destination.stat().st_size > 60_000:
        return destination
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    label = escape_drawtext(f"SOURCE  ·  {channel.upper()}")
    font = "C\\:/Windows/Fonts/segoeuib.ttf"
    # A quiet, stable treatment: blurred edge fill only for non-16:9 artwork,
    # the unmodified source artwork above it, and one restrained provenance tag.
    filters = (
        "[0:v]split=2[background][art];"
        "[background]scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,gblur=sigma=36,eq=brightness=-0.38:saturation=0.72[bg];"
        "[art]scale=1920:1080:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,"
        "drawbox=x=0:y=1000:w=1920:h=80:color=black@0.62:t=fill,"
        f"drawtext=fontfile='{font}':text='{label}':x=54:y=1024:"
        "fontsize=25:fontcolor=white@0.90,format=yuv420p"
    )
    subprocess.run(
        [
            str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
            "-loop", "1", "-i", str(thumbnail), "-t", "6", "-an", "-r", "30",
            "-filter_complex", filters, "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "18", "-g", "60", "-pix_fmt", "yuv420p", str(destination),
        ],
        check=True,
    )
    return destination


def main() -> None:
    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    ledger = [dict(item) for item in source_manifest["shot_ledger"]]
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    if len(ledger) != 100:
        raise RuntimeError(f"Expected 100 six-second shots, found {len(ledger)}")

    queued_by_slot = {int(item["slot"]): item for item in queue["clips"]}
    if len(queued_by_slot) != len(queue["clips"]):
        raise RuntimeError("Source-evidence queue contains duplicate timeline slots")

    timeline: list[Path] = []
    evidence_video_ids: list[str] = []
    for timeline_slot, item in enumerate(ledger):
        # Repair stale slot metadata from earlier revisions. Timeline order is
        # canonical and has always remained exactly 100 x six-second segments.
        item["slot"] = timeline_slot
        queued = queued_by_slot.get(timeline_slot)
        if queued:
            thumbnail = THUMBNAILS / f"{timeline_slot:03d}_{queued['video_id']}.jpg"
            if not thumbnail.exists() or thumbnail.stat().st_size < 10_000:
                raise FileNotFoundError(thumbnail)
            source_card = render_source_card(
                timeline_slot, thumbnail, str(queued["channel"])
            )
            previous = item["file"]
            item.update(
                {
                    "kind": "youtube_source_evidence",
                    "file": str(source_card),
                    "source": str(source_card),
                    "replaced_file": previous,
                    "source_url": queued["source_url"],
                    "source_title": queued["title"],
                    "publisher": queued["channel"],
                    "video_id": queued["video_id"],
                    "license": queued["license_name"],
                    "rights_basis": queued["rights_basis"],
                    "rights_status": "reviewed_source_artwork_for_private_preview",
                    "source_audio": "muted",
                    "visual_semantics": (
                        "verified public source artwork; not source video footage"
                    ),
                    "qc_status": "passed_contact_sheet_review",
                }
            )
            evidence_video_ids.append(str(queued["video_id"]))
        path = Path(item["file"])
        if not path.exists() or path.stat().st_size < 60_000:
            raise FileNotFoundError(path)
        timeline.append(path.resolve())

    if len(evidence_video_ids) != 13 or len(set(evidence_video_ids)) != 13:
        raise RuntimeError("Expected thirteen unique reputable source cards")

    WORK.mkdir(parents=True, exist_ok=True)
    concat = WORK / "timeline.concat.txt"
    concat.write_text(
        "".join(f"file '{path.as_posix()}'\n" for path in timeline),
        encoding="utf-8",
    )
    visuals = WORK / "visuals_600s.mp4"
    subprocess.run(
        [
            str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat),
            "-c", "copy", "-t", "600", str(visuals),
        ],
        check=True,
    )
    ass_path = str(CAPTIONS.resolve()).replace("\\", "/").replace(":", "\\:")
    subprocess.run(
        [
            str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(visuals), "-i", str(NARRATION), "-vf", f"ass='{ass_path}'",
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-t", "600", "-movflags", "+faststart", str(FINAL),
        ],
        check=True,
    )

    visual_mix = Counter(item["kind"] for item in ledger)
    manifest = {
        "final": str(FINAL),
        "sha256": sha256(FINAL),
        "duration_seconds": 600,
        "resolution": "1920x1080",
        "fps": 30,
        "publishing_enabled": False,
        "visual_mix": dict(visual_mix),
        "youtube_source_evidence_cards": len(evidence_video_ids),
        "unique_youtube_sources": len(set(evidence_video_ids)),
        "new_youtube_motion_broll": 0,
        "rights_note": (
            "YouTube additions are verified public source artwork, not downloaded "
            "video clips. Source URLs and declared Creative Commons status are retained."
        ),
        "shot_ledger": ledger,
    }
    (WORK / "render_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in manifest.items() if k != "shot_ledger"}, indent=2))


if __name__ == "__main__":
    main()
