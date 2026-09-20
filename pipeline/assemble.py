"""Stage 5: assemble scenes into the final video with ffmpeg.

v1: static image per scene with a slow Ken Burns zoom + scene narration audio,
all scenes concatenated. Captions/music/transitions come later.
"""
import json
import subprocess
from pathlib import Path

from .config import FFMPEG_PRESET, FFMPEG_THREADS_PER_JOB, VIDEO_W, VIDEO_H


def _run(cmd: list[str]):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        tail = "\n".join(p.stderr.strip().splitlines()[-12:])
        raise RuntimeError(f"ffmpeg failed ({p.returncode}):\n{tail}")


def _write_concat_list(paths: list[Path], dest: Path):
    # The concat demuxer resolves entries relative to the list file, so use
    # absolute paths and escape quotes.
    lines = []
    for p in paths:
        s = p.resolve().as_posix().replace("'", r"'\''")
        lines.append(f"file '{s}'\n")
    dest.write_text("".join(lines), encoding="utf-8")


def _audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        check=True, capture_output=True, text=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def _concat_audio(files: list[Path], dest: Path):
    lst = dest.with_suffix(".txt")
    _write_concat_list(files, lst)
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
          "-c:a", "libmp3lame", "-q:a", "2", str(dest)])
    lst.unlink()


def run(run_dir: Path) -> Path:
    script = json.loads((run_dir / "script.json").read_text(encoding="utf-8"))
    seg_dir = run_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    segments = []

    for scene in script["scenes"]:
        sid = scene["id"]
        audio_files = [run_dir / "audio" / n for n in scene["audio_files"]]
        scene_audio = seg_dir / f"audio_{sid:02d}.mp3"
        if len(audio_files) == 1:
            scene_audio = audio_files[0]
        elif not scene_audio.exists():
            _concat_audio(audio_files, scene_audio)

        image = run_dir / "images" / f"scene_{sid:02d}.png"
        seg = seg_dir / f"seg_{sid:02d}.mp4"
        if not seg.exists():
            dur = _audio_duration(scene_audio)
            frames = int(dur * 30) + 1
            # Native 1080p zoom path: no hidden 4K intermediate.
            vf = (f"scale={VIDEO_W}:{VIDEO_H},"
                  f"zoompan=z='min(zoom+0.0004,1.25)':d={frames}"
                  f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                  f":s={VIDEO_W}x{VIDEO_H}:fps=30")
            _run(["ffmpeg", "-y", "-loop", "1", "-i", str(image), "-i", str(scene_audio),
                  "-vf", vf, "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", FFMPEG_PRESET,
                  "-threads", str(FFMPEG_THREADS_PER_JOB),
                  "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                  str(seg)])
        segments.append(seg)
        print(f"  segment {sid} ready")

    concat_list = seg_dir / "concat.txt"
    _write_concat_list(segments, concat_list)
    final = run_dir / "final.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
          "-c", "copy", str(final)])
    print(f"Final video -> {final}")
    return final
