"""FFmpeg timeline renderer for dense mixed-media EpisodeProject shot plans."""
from __future__ import annotations

import json
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageDraw

from .config import (
    FFMPEG_PRESET, FFMPEG_THREADS_PER_JOB, MUSIC_DIR, RENDER_PARALLELISM,
    NARRATION_TAIL_PADDING_SECONDS, VIDEO_FPS, VIDEO_H, VIDEO_W,
)
from .models import EpisodeProject, Shot
from .screenshot_treatment import prepare_editorial_screenshot
from .thumbnail import _font
from .editorial_pointer import write_pointer_ass, ass_filter


def run_command(command: list[str]) -> None:
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode:
        tail = "\n".join(process.stderr.strip().splitlines()[-20:])
        raise RuntimeError(f"command failed ({process.returncode}): {' '.join(command[:8])}\n{tail}")


def duration(path: Path) -> float:
    process = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(process.stdout)["format"]["duration"])


def write_concat(paths: list[Path], destination: Path) -> Path:
    lines = []
    for path in paths:
        escaped = path.resolve().as_posix().replace("'", r"'\''")
        lines.append(f"file '{escaped}'\n")
    destination.write_text("".join(lines), encoding="utf-8")
    return destination


def concat_audio(files: list[Path], destination: Path) -> Path:
    listing = write_concat(files, destination.with_suffix(".txt"))
    run_command([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(destination),
    ])
    return destination


def make_silence(destination: Path, milliseconds: int) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    seconds = max(0.001, milliseconds / 1000)
    run_command([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{seconds:.3f}",
        "-c:a", "pcm_s16le", str(destination),
    ])
    return destination


def chapter_card(title: str, destination: Path) -> Path:
    image = Image.new("RGB", (VIDEO_W, VIDEO_H), "#111311")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((110, 280, 1810, 800), radius=16, fill="#181B19", outline="#4A4F4B", width=2)
    draw.rectangle((110, 280, 116, 800), fill="#83938C")
    words = title.split()
    lines = [" ".join(words[:5]), " ".join(words[5:10])]
    lines = [line for line in lines if line]
    font = _font(88)
    y = 410
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        draw.text(((VIDEO_W - (box[2] - box[0])) / 2, y), line, font=font, fill="white")
        y += 120
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    return destination


def _still_filter(shot: Shot, frames: int) -> str:
    is_screen_capture = shot.asset_type in {"screenshot", "screen_recording", "official_demo"}
    motion_style = shot.motion_style
    if is_screen_capture and motion_style in {"pan_left", "pan_right", "float"}:
        motion_style = "push_in"
    if motion_style == "locked":
        zoom = "1.0"
        x = "(iw-iw/zoom)/2"
        y = "(ih-ih/zoom)/2"
    else:
        hold = min(12, max(4, frames // 10))
        span = max(1, frames - hold * 2)
        progress = f"clip((on-{hold})/{span},0,1)"
        eased = f"(({progress})*({progress})*(3-2*({progress})))"
        amount = 0.045 if shot.presentation == "editorial_card" else (
            0.055 if shot.asset_type in {"screenshot", "chart", "motion_graphic"} else 0.07
        )
        zoom = f"1+{amount:.3f}*(1-({eased}))" if motion_style == "pull_out" else f"1+{amount:.3f}*({eased})"
        if motion_style == "pan_right":
            focus_x = f"0.34+0.26*({eased})"
        elif motion_style == "pan_left":
            focus_x = f"0.66-0.26*({eased})"
        else:
            raw_focus_x = 0.5 if is_screen_capture else shot.focus_x
            mapped_focus_x = 0.0833 + 0.8334 * raw_focus_x if shot.presentation == "editorial_card" else raw_focus_x
            focus_x = f"{mapped_focus_x:.4f}"
        x = f"(iw-iw/zoom)*({focus_x})"
        raw_focus_y = 0.5 if is_screen_capture else shot.focus_y
        mapped_focus_y = 0.1157 + 0.8334 * raw_focus_y if shot.presentation == "editorial_card" else raw_focus_y
        y = f"(ih-ih/zoom)*{mapped_focus_y:.4f}"
    return (
        f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={VIDEO_W}:{VIDEO_H},"
        f"zoompan=z='{zoom}':d={frames}:x='{x}':y='{y}':s={VIDEO_W}x{VIDEO_H}:fps={VIDEO_FPS},"
        "format=yuv420p"
    )


def _source_label_filter(label: str) -> str:
    safe = label.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'").replace("%", r"\%")
    # Static Windows FFmpeg builds can lack a usable Fontconfig installation.
    # Pin a known system font so source labels remain deterministic and do not
    # crash otherwise valid footage renders.
    font = "C\\:/Windows/Fonts/arialbd.ttf"
    return (
        f"drawtext=fontfile='{font}':text='SOURCE · {safe}':fontcolor=white:fontsize=30:"
        "box=1:boxcolor=black@0.68:boxborderw=14:x=42:y=42"
    )


def _animated_underline(shot: Shot, frames: int, seconds: float) -> tuple[str, str] | None:
    annotation = next((item for item in shot.annotations if item.style == "underline"), None)
    if not annotation:
        return None
    if annotation.width > .34 or annotation.height > .065:
        return None
    if shot.presentation == "editorial_card":
        # Backward-compatible mapping for already cached legacy treatments.
        x = round(160 + 1600 * annotation.x)
        y = round(125 + 900 * (annotation.y + annotation.height) + 3)
        width = max(12, min(1580, round(1600 * annotation.width)))
        y = max(130, min(1017, y))
    else:
        # New default: evidence fills the complete 1920x1080 canvas.
        x = round(VIDEO_W * annotation.x)
        y = round(VIDEO_H * (annotation.y + annotation.height) + 3)
        width = max(12, min(VIDEO_W - x - 8, round(VIDEO_W * annotation.width)))
        y = max(8, min(VIDEO_H - 10, y))
    # Underlines have one editorial meaning and one muted red treatment. The
    # legacy annotation default is cyan and must not leak into this treatment.
    color = "B84D45"
    line_input = f"color=c=0x{color}:s={width}x3:r={VIDEO_FPS}:d={seconds:.3f}"
    base = _still_filter(shot, frames)
    graph = (
        f"[0:v]{base}[base];"
        "[1:v]format=rgba,"
        "scale=w='max(2,iw*min(1,max(0,(t-0.22)/0.34)))':h=ih:eval=frame[line];"
        f"[base][line]overlay=x={x}:y={y}:enable='between(t,0.22,{max(0.23, seconds - 0.12):.3f})':"
        "shortest=1,format=yuv420p[v]"
    )
    return line_input, graph


def _editorial_color_grade(profile: str, shot: Shot) -> str:
    """Return a restrained source-footage grade without altering brand graphics.

    The fidelity repair is intentionally limited to tonal cohesion. Authored
    motion graphics and chapter cards already use the approved palette, while
    bright web pages and mixed-source footage need a common neutral treatment.
    """
    if profile != "earthy_neutral_source_v1":
        return ""
    if shot.asset_type in {"motion_graphic", "generated_motion_graphic", "chapter_card"}:
        return ""
    return (
        "eq=contrast=1.045:brightness=-0.022:saturation=0.84:gamma=0.985,"
        "colorbalance=rm=0.018:gm=0.008:bm=-0.014,"
        "vignette=PI/6.5"
    )


def render_shot(
    shot: Shot, source: Path, destination: Path, source_label: str = "", color_profile: str = "",
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    seconds = shot.duration_seconds
    if source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        frames = max(1, round(seconds * VIDEO_FPS))
        if any(a.style == "cursor" or a.verification_method == "ocr-words" for a in shot.annotations):
            # Locked source geometry is essential: an independently zooming page would detach the pointer.
            cues = []
            with Image.open(source) as image:
                iw, ih = image.size
            scale = max(VIDEO_W/iw, VIDEO_H/ih)
            for a in shot.annotations:
                if a.style not in {"cursor", "underline"} or not a.target_text or not a.verification_method:
                    continue
                if shot.presentation == "editorial_card":
                    # Legacy treatment contains the original image in this region.
                    with Image.open(Path(shot.asset_path)) as original:
                        ow, oh = original.size
                    contained = min(1600/ow, 900/oh)
                    cw, ch = ow*contained, oh*contained
                    box = [160+(1600-cw)/2+a.x*cw,125+(900-ch)/2+a.y*ch,a.width*cw,a.height*ch]
                else:
                    box = [a.x*iw*scale-(iw*scale-VIDEO_W)/2,a.y*ih*scale-(ih*scale-VIDEO_H)/2,
                           a.width*iw*scale,a.height*ih*scale]
                cues.append({'kind':a.style,'box':box,'quote':a.target_text,'rationale':a.rationale,
                             'start':a.start_seconds,'end':min(a.end_seconds or seconds-.15,seconds)})
            try:
                pointer = write_pointer_ass(cues, seconds, destination.with_suffix('.pointers.ass'))
            except ValueError:
                # A clipped or unverified target must not acquire a decorative fallback marker.
                pointer = write_pointer_ass([], seconds, destination.with_suffix('.pointers.ass'))
            locked = shot.model_copy(update={'motion_style':'locked','annotations':[]})
            vf = _still_filter(locked,frames)+','+ass_filter(pointer)
            grade = _editorial_color_grade(color_profile, shot)
            if grade: vf += ','+grade
            if source_label: vf += ','+_source_label_filter(source_label)
            run_command(['ffmpeg','-y','-loop','1','-i',str(source),'-an','-vf',vf,
                         '-t',f'{seconds:.3f}','-c:v','libx264','-preset',FFMPEG_PRESET,'-crf','18',
                         '-threads',str(FFMPEG_THREADS_PER_JOB),'-pix_fmt','yuv420p',str(destination)])
            return destination
        underline = _animated_underline(shot, frames, seconds)
        if underline:
            line_input, graph = underline
            grade = _editorial_color_grade(color_profile, shot)
            if grade:
                graph = graph.removesuffix("[v]") + f"[merged];[merged]{grade},format=yuv420p[v]"
            command = [
                "ffmpeg", "-y", "-loop", "1", "-i", str(source),
                "-f", "lavfi", "-i", line_input,
                "-filter_complex", graph, "-map", "[v]",
                "-t", f"{seconds:.3f}", "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", "18",
                "-threads", str(FFMPEG_THREADS_PER_JOB), "-pix_fmt", "yuv420p", str(destination),
            ]
            run_command(command)
            return destination
        command = ["ffmpeg", "-y", "-loop", "1", "-i", str(source), "-vf", _still_filter(shot, frames)]
    else:
        command = [
            "ffmpeg", "-y", "-ss", f"{shot.source_in_seconds:.3f}", "-i", str(source), "-an", "-vf",
            f"setpts=PTS-STARTPTS,scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={VIDEO_W}:{VIDEO_H}:x='(in_w-out_w)/2':y='(in_h-out_h)/2',fps={VIDEO_FPS},"
            f"tpad=stop_mode=clone:stop_duration={seconds:.3f},format=yuv420p",
        ]
    grade = _editorial_color_grade(color_profile, shot)
    if grade:
        command[-1] += "," + grade
    if shot.asset_type == "chapter_card":
        fade_out = max(0, seconds - 0.2)
        command[-1] += f",fade=t=in:st=0:d=0.2,fade=t=out:st={fade_out:.3f}:d=0.2"
    if source_label:
        command[-1] += "," + _source_label_filter(source_label)
    command.extend([
        "-t", f"{seconds:.3f}", "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", "18",
        "-threads", str(FFMPEG_THREADS_PER_JOB), "-pix_fmt", "yuv420p", str(destination),
    ])
    run_command(command)
    return destination


def _subtitle_filter(path: Path) -> str:
    value = path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    return f"ass='{value}'"


def _delivery_timing(narration_seconds: float, video_seconds: float) -> tuple[float, float]:
    """Return final duration and the visual hold required to protect the voice tail."""
    output_seconds = narration_seconds + NARRATION_TAIL_PADDING_SECONDS
    # Add one frame of encoder safety so a rounding difference can never make
    # the video stream shorter than the padded narration.
    video_pad = max(
        NARRATION_TAIL_PADDING_SECONDS,
        output_seconds - video_seconds + 1 / VIDEO_FPS,
    )
    return output_seconds, video_pad


def render_project(
    project: EpisodeProject, run_dir: Path, narration: Path, captions: Path | None, cache_key: str = "default",
) -> Path:
    if not project.script or not project.shots:
        raise ValueError("script and shot plan are required")
    cache_name = cache_key[:16]
    segment_dir = run_dir / "timeline_segments" / cache_name
    fallback_dir = run_dir / "cards" / cache_name
    treatment_dir = run_dir / "screenshot_treatments" / cache_name
    source_by_id = {source.id: source for source in project.sources}
    rights_by_shot = {
        str(entry.get("shot_id")): entry for entry in project.rights if entry.get("shot_id")
    }
    color_profile = str(
        (project.editorial_plan.get("fidelity_visual_overrides") or {}).get("color_profile") or ""
    )
    def render_indexed(item: tuple[int, Shot]) -> Path:
        index, shot = item
        if shot.asset_path and Path(shot.asset_path).exists():
            source = Path(shot.asset_path)
        else:
            beat = next((item for item in project.script.beats if item.id == shot.beat_id), project.script.beats[0])
            if shot.asset_type == "chart":
                claim = next((claim for claim in project.claims if claim.id in beat.claim_ids and claim.kind == "number"), None)
                card_text = claim.text if claim else beat.visual_direction
            else:
                card_text = beat.visual_direction
            source = chapter_card(card_text[:90], fallback_dir / f"{shot.id}.png")
        segment = segment_dir / f"{index:03d}.mp4"
        if not segment.exists():
            source_record = source_by_id.get(shot.source_id or "")
            label = ""
            if source_record:
                label = urlsplit(str(source_record.url)).netloc.casefold().removeprefix("www.")
                label = {"github.com": "GitHub", "arxiv.org": "arXiv"}.get(label, label)
            elif rights_by_shot.get(shot.id):
                rights = rights_by_shot[shot.id]
                label = str(rights.get("source_label") or "").strip()
                if not label and rights.get("source_url"):
                    label = urlsplit(str(rights["source_url"])).netloc.casefold().removeprefix("www.")
            if shot.presentation == "editorial_card" and source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                treated = treatment_dir / f"{shot.id}.jpg"
                if not treated.exists():
                    prepare_editorial_screenshot(source, shot, treated, source_label=label)
                source = treated
                label = ""
            render_shot(shot, source, segment, label, color_profile)
        return segment

    with ThreadPoolExecutor(max_workers=min(RENDER_PARALLELISM, len(project.shots))) as executor:
        segments = list(executor.map(render_indexed, enumerate(project.shots)))
    listing = write_concat(segments, run_dir / f"timeline_segments_{cache_name}.txt")
    silent_video = run_dir / f"timeline_{cache_name}.mp4"
    run_command(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(silent_video)])

    narration_seconds = duration(narration)
    output_seconds, video_pad = _delivery_timing(narration_seconds, duration(silent_video))

    music_files = [path for path in MUSIC_DIR.glob("*") if path.suffix.lower() in {".mp3", ".wav", ".m4a", ".flac"}]
    final = run_dir / f"final_{cache_name}.mp4"
    command = ["ffmpeg", "-y", "-i", str(silent_video), "-i", str(narration)]
    if music_files:
        music = random.choice(sorted(music_files))
        command.extend(["-stream_loop", "-1", "-i", str(music)])
        audio_filter = (
            f"[1:a]loudnorm=I=-16:TP=-1.5:LRA=9,apad=pad_dur={NARRATION_TAIL_PADDING_SECONDS:.3f}[voice];"
            "[2:a]volume=0.126[music];"
            "[music][voice]sidechaincompress=threshold=0.025:ratio=12:attack=20:release=350[ducked];"
            "[voice][ducked]amix=inputs=2:duration=first:normalize=0[aout]"
        )
        command.extend(["-filter_complex", audio_filter, "-map", "0:v", "-map", "[aout]"])
    else:
        command.extend([
            "-filter_complex",
            f"[1:a]loudnorm=I=-16:TP=-1.5:LRA=9,apad=pad_dur={NARRATION_TAIL_PADDING_SECONDS:.3f}[aout]",
            "-map", "0:v", "-map", "[aout]",
        ])
    video_filter = f"tpad=stop_mode=clone:stop_duration={video_pad:.3f}"
    if captions is not None:
        video_filter = f"{_subtitle_filter(captions)},{video_filter}"
    command.extend([
        "-vf", video_filter,
        "-t", f"{output_seconds:.3f}",
        "-c:v", "libx264", "-preset", FFMPEG_PRESET,
        "-b:v", "1800k", "-minrate", "1800k", "-maxrate", "1800k", "-bufsize", "3600k",
        "-x264-params", "nal-hrd=cbr:force-cfr=1",
        "-threads", str(max(FFMPEG_THREADS_PER_JOB, 4)),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final),
    ])
    run_command(command)
    return final
