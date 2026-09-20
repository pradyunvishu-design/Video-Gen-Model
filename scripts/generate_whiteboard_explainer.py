"""Generate a premium 20-second whiteboard concept animation through Magic Hour.

The start/end plates contain deterministic, text-free geometry. Magic Hour is
responsible for natural pen motion and the drawn transition—not factual evidence.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from fractions import Fraction
from pathlib import Path

import av
from dotenv import load_dotenv
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


BASE_PROMPT = """Single unbroken overhead shot of an original educational whiteboard drawing on warm ivory paper. A real black felt-tip pen, with only the pen tip and a small edge of fingertips visible, draws the explanation in chronological order. Natural imperfect ink pressure, subtle line wobble, tiny pauses to think, believable human drawing speed, warm paper fibers and faint graphite smudges. The drawing itself explains how random visual noise is gradually refined into a coherent image.

CAMERA AND CONTINUITY: completely locked 16:9 overhead camera, level paper, no zoom, no pan, no shake, no cuts, no time-lapse jump. Every mark appears only where the pen tip touches the paper. Previously drawn lines remain fixed and readable. Preserve the supplied start and end compositions exactly. Hold on the completed drawing for the final two seconds.

STRICT NEGATIVES: no captions, no words, no letters, no numbers, no logos, no watermark, no UI, no glossy 3D, no cartoon character, no talking head, no extra hands, no deformed fingers, no floating pen, no morphing lines, no disappearing marks, no camera motion, no audio. Original educational whiteboard aesthetic; do not imitate any named studio, artist, or existing animation."""

PROMPT_PART_1 = BASE_PROMPT + """

THIS SHOT: Begin at the supplied nearly blank board. Draw a loose cloud of tiny charcoal dots on the left to represent visual noise, circle the cloud once, then draw a right-pointing arrow and the first two intermediate sketch frames. Inside the first frame draw scattered dots; inside the second frame organize them into a cleaner ring. Finish exactly on the supplied midpoint board and hold it briefly."""

PROMPT_PART_2 = BASE_PROMPT + """

THIS SHOT: Continue exactly from the supplied midpoint board. Draw the third intermediate frame with a small orderly pattern, then a right-pointing arrow. Draw a crisp paper airplane flying toward one small coral-orange sun. Add exactly one short coral pencil emphasis stroke beneath the airplane, remove the pen, and hold on the supplied completed drawing for the final two seconds."""


def _paper() -> Image.Image:
    image = Image.new("RGB", (1920, 1080), (246, 241, 226))
    draw = ImageDraw.Draw(image)
    for y in range(55, 1080, 72):
        shade = 234 + (y // 72) % 4
        draw.line((0, y, 1920, y + 2), fill=(shade, shade - 2, shade - 8), width=1)
    for x in range(95, 1920, 133):
        draw.point((x, (x * 37) % 1080), fill=(221, 216, 203))
    return image


def _pen(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.polygon([(x, y), (x + 155, y + 82), (x + 132, y + 124), (x - 24, y + 42)], fill=(34, 35, 37))
    draw.polygon([(x - 24, y + 42), (x - 52, y + 56), (x - 37, y + 24), (x, y)], fill=(15, 15, 16))
    draw.line((x + 18, y + 14, x + 142, y + 80), fill=(85, 87, 90), width=5)


def create_start(path: Path) -> None:
    image = _paper()
    draw = ImageDraw.Draw(image)
    # The pen is already touching down, so the generated motion begins as an
    # intentional drawing action rather than a floating-object reveal.
    _pen(draw, 235, 760)
    draw.ellipse((170, 812, 184, 826), fill=(42, 42, 43))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, quality=96)


def _arrow(draw: ImageDraw.ImageDraw, x1: int, y: int, x2: int) -> None:
    ink = (42, 42, 43)
    draw.line((x1, y, x2, y), fill=ink, width=9)
    draw.line((x2, y, x2 - 24, y - 18), fill=ink, width=9)
    draw.line((x2, y, x2 - 24, y + 18), fill=ink, width=9)


def _paper_plane(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    ink = (42, 42, 43)
    draw.polygon([(cx - 90, cy - 35), (cx + 95, cy - 90), (cx + 20, cy + 75)], outline=ink, fill=None)
    draw.line((cx - 90, cy - 35, cx + 20, cy + 10, cx + 95, cy - 90), fill=ink, width=9)
    draw.line((cx + 20, cy + 10, cx + 20, cy + 75), fill=ink, width=9)


def create_end(path: Path) -> None:
    image = _paper()
    draw = ImageDraw.Draw(image)
    ink = (42, 42, 43)
    gray = (116, 113, 106)
    coral = (221, 91, 62)

    # Left: deterministic noise cloud.
    dots = [(250 + (i * 47) % 250, 395 + (i * 83) % 280) for i in range(24)]
    for index, (x, y) in enumerate(dots):
        radius = 5 + index % 4
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=gray)
    draw.ellipse((190, 330, 545, 735), outline=ink, width=9)

    _arrow(draw, 565, 535, 690)
    stages = [(720, 390, 910, 680), (985, 390, 1175, 680), (1250, 390, 1440, 680)]
    for stage_index, (x1, y1, x2, y2) in enumerate(stages):
        draw.rounded_rectangle((x1, y1, x2, y2), radius=24, outline=ink, width=8)
        count = 16 - stage_index * 5
        for i in range(count):
            angle = (i / max(1, count)) * math.tau
            radius = 62 - stage_index * 13
            x = (x1 + x2) // 2 + math.cos(angle) * radius
            y = (y1 + y2) // 2 + math.sin(angle) * radius
            r = 4 + stage_index
            draw.ellipse((x - r, y - r, x + r, y + r), fill=ink)
        if stage_index < len(stages) - 1:
            _arrow(draw, x2 + 18, 535, stages[stage_index + 1][0] - 18)

    _arrow(draw, 1460, 535, 1555)
    _paper_plane(draw, 1680, 535)
    draw.ellipse((1700, 255, 1770, 325), outline=coral, width=10)
    for angle in range(0, 360, 45):
        r = math.radians(angle)
        draw.line(
            (1735 + math.cos(r) * 48, 290 + math.sin(r) * 48, 1735 + math.cos(r) * 70, 290 + math.sin(r) * 70),
            fill=coral,
            width=7,
        )
    draw.arc((1560, 695, 1815, 790), start=190, end=350, fill=coral, width=11)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, quality=96)


def create_mid(path: Path) -> None:
    image = _paper()
    draw = ImageDraw.Draw(image)
    ink = (42, 42, 43)
    gray = (116, 113, 106)
    dots = [(250 + (i * 47) % 250, 395 + (i * 83) % 280) for i in range(24)]
    for index, (x, y) in enumerate(dots):
        radius = 5 + index % 4
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=gray)
    draw.ellipse((190, 330, 545, 735), outline=ink, width=9)
    _arrow(draw, 565, 535, 690)
    stages = [(720, 390, 910, 680), (985, 390, 1175, 680)]
    for stage_index, (x1, y1, x2, y2) in enumerate(stages):
        draw.rounded_rectangle((x1, y1, x2, y2), radius=24, outline=ink, width=8)
        count = 16 - stage_index * 5
        for i in range(count):
            angle = (i / max(1, count)) * math.tau
            radius = 62 - stage_index * 13
            x = (x1 + x2) // 2 + math.cos(angle) * radius
            y = (y1 + y2) // 2 + math.sin(angle) * radius
            r = 4 + stage_index
            draw.ellipse((x - r, y - r, x + r, y + r), fill=ink)
        if stage_index == 0:
            _arrow(draw, x2 + 18, 535, stages[1][0] - 18)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, quality=96)


def combine_to_20_seconds(sources: list[Path], destination: Path) -> None:
    outgoing = av.open(str(destination), mode="w")
    output_stream = outgoing.add_stream("libx264", rate=30)
    output_stream.time_base = Fraction(1, 30)
    output_stream.width = 1920
    output_stream.height = 1080
    output_stream.pix_fmt = "yuv420p"
    output_stream.options = {"crf": "16", "preset": "medium", "movflags": "+faststart"}
    output_frame = 0
    for source in sources:
        incoming = av.open(str(source))
        source_frame = 0
        segment_output_frame = 0
        for frame in incoming.decode(video=0):
            if source_frame >= 240:
                break
            # Magic Hour currently returns these Kling masters at 24 fps. Map
            # each ten-second section to exactly 300 frames without changing
            # the drawing speed; selected frames are repeated, never invented.
            target_segment_end = round((source_frame + 1) * 30 / 24)
            while segment_output_frame < target_segment_end:
                normalized = frame.reformat(width=1920, height=1080, format="yuv420p")
                normalized.pts = output_frame
                normalized.time_base = Fraction(1, 30)
                output_frame += 1
                segment_output_frame += 1
                for packet in output_stream.encode(normalized):
                    outgoing.mux(packet)
            source_frame += 1
        incoming.close()
    for packet in output_stream.encode():
        outgoing.mux(packet)
    outgoing.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "whiteboard_concept")
    args = parser.parse_args()
    if args.env_file:
        load_dotenv(args.env_file)
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.worker")

    # Import only after environment loading so the project client never reads
    # or prints a credential during setup.
    from pipeline import magichour

    output_dir = args.output_dir.resolve()
    start = output_dir / "whiteboard_start.png"
    midpoint = output_dir / "whiteboard_midpoint.png"
    end = output_dir / "whiteboard_end.png"
    prompt_file = output_dir / "generation_prompt.txt"
    create_start(start)
    create_mid(midpoint)
    create_end(end)
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(
        "PART 1\n======\n" + PROMPT_PART_1 + "\n\nPART 2\n======\n" + PROMPT_PART_2,
        encoding="utf-8",
    )

    start_remote = magichour.upload_file(str(start), "image")
    midpoint_remote = magichour.upload_file(str(midpoint), "image")
    end_remote = magichour.upload_file(str(end), "image")
    submitted_1 = magichour.image_to_video(
        start_remote,
        PROMPT_PART_1,
        "whiteboard-diffusion-explainer-v1-part-1",
        duration=10,
        model="kling-3.0",
        resolution="1080p",
        end_image_file_path=midpoint_remote,
    )
    submitted_2 = magichour.image_to_video(
        midpoint_remote,
        PROMPT_PART_2,
        "whiteboard-diffusion-explainer-v1-part-2",
        duration=10,
        model="kling-3.0",
        resolution="1080p",
        end_image_file_path=end_remote,
    )
    submissions = [submitted_1, submitted_2]
    (output_dir / "job.json").write_text(
        json.dumps({
            "jobs": [
                {"id": item["id"], "credits_charged": item.get("credits_charged", 0)}
                for item in submissions
            ]
        }, indent=2),
        encoding="utf-8",
    )
    jobs = [magichour.wait_video(item["id"]) for item in submissions]
    raws = [
        magichour.download_all(job, output_dir, f"whiteboard_raw10_part{index}")[0]
        for index, job in enumerate(jobs, start=1)
    ]
    final = output_dir / "whiteboard-diffusion-explainer-20s.mp4"
    combine_to_20_seconds(raws, final)
    print(json.dumps({
        "video": str(final),
        "job_ids": [item["id"] for item in submissions],
        "credits": sum(int(item.get("credits_charged", 0)) for item in submissions),
    }))


if __name__ == "__main__":
    main()
