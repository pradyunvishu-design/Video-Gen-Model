from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import magichour  # noqa: E402


OUT = ROOT / "output" / "claude_chips_5m_recreate"
SCRIPT = OUT / "script_news_v3.json"
AUDIO_DIR = OUT / "audio_news_v3"
REFERENCE_VIDEO = OUT / "claude_chip_validation_5m_source_only_motion_v2.mp4"
REFERENCE_WAV = AUDIO_DIR / "approved_narrator_reference.wav"
RAW_WAV = AUDIO_DIR / "narration_news_v3_raw.wav"
MASTER = AUDIO_DIR / "narration_news_v3_master.m4a"
MANIFEST = AUDIO_DIR / "narration_news_v3_manifest.json"
_LOCAL_FFMPEG = ROOT / "tools" / "ffmpeg" / "bin"
_HERMES_FFMPEG = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\tools\ffmpeg\bin")
FFMPEG = (_LOCAL_FFMPEG if (_LOCAL_FFMPEG / "ffmpeg.exe").exists() else _HERMES_FFMPEG) / "ffmpeg.exe"
FFPROBE = (_LOCAL_FFMPEG if (_LOCAL_FFMPEG / "ffprobe.exe").exists() else _HERMES_FFMPEG) / "ffprobe.exe"
TARGET_SPOKEN_SECONDS = 297.0


def run(args: list[str | Path]) -> None:
    print("RUN", subprocess.list2cmdline([str(value) for value in args]), flush=True)
    subprocess.run([str(value) for value in args], check=True)


def duration(path: Path) -> float:
    result = subprocess.check_output([
        str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], text=True).strip()
    return float(result)


def split_text(text: str, limit: int = 900) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text.strip()))
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    if any(len(chunk) > 1000 for chunk in chunks):
        raise ValueError("Narration chunk exceeds Magic Hour's verified 1000-character limit")
    return chunks


def build_reference() -> Path:
    if REFERENCE_WAV.exists() and REFERENCE_WAV.stat().st_size > 1_000_000:
        return REFERENCE_WAV
    if not REFERENCE_VIDEO.exists():
        raise FileNotFoundError(REFERENCE_VIDEO)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    # Reuse the already approved, single-voice English narration as the identity
    # reference. This avoids the two-speaker and muffled regions in the raw sample.
    run([
        FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", "18", "-i", REFERENCE_VIDEO, "-t", "32", "-vn",
        "-af", "highpass=f=70,lowpass=f=15000,loudnorm=I=-18:TP=-2:LRA=7",
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", REFERENCE_WAV,
    ])
    return REFERENCE_WAV


def concat_audio(inputs: list[Path], output: Path) -> None:
    listing = output.with_suffix(".concat.txt")
    listing.write_text(
        "".join(f"file '{path.resolve().as_posix()}'\n" for path in inputs),
        encoding="utf-8",
    )
    run([
        FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", listing,
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", output,
    ])


def main() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    tasks: list[tuple[str, int, str, Path]] = []
    ordered: list[Path] = []
    for section in script["sections"]:
        for index, chunk in enumerate(split_text(section["narration"])):
            destination = AUDIO_DIR / f"{section['id']}_{index:02d}.mp3"
            ordered.append(destination)
            if not destination.exists() or destination.stat().st_size < 50_000:
                tasks.append((section["id"], index, chunk, destination))

    credits = 0
    projects: list[dict] = []
    if tasks:
        uploaded = magichour.upload_file(str(build_reference()), "audio")

        def generate(task: tuple[str, int, str, Path]) -> dict:
            section_id, index, chunk, destination = task
            project_id = magichour.voice_clone(
                chunk, uploaded, f"claude-chip-news-v3-{section_id}-{index:02d}",
            )
            job = magichour.wait_audio(project_id)
            magichour.download(job, destination)
            return {
                "section": section_id,
                "chunk": index,
                "project_id": project_id,
                "credits": int(job.get("credits_charged", 0)),
                "characters": len(chunk),
                "file": str(destination),
            }

        with ThreadPoolExecutor(max_workers=min(3, len(tasks))) as pool:
            futures = [pool.submit(generate, task) for task in tasks]
            for future in as_completed(futures):
                record = future.result()
                projects.append(record)
                credits += int(record["credits"])

    if any(not path.exists() for path in ordered):
        missing = [str(path) for path in ordered if not path.exists()]
        raise RuntimeError(f"Missing generated narration chunks: {missing}")
    concat_audio(ordered, RAW_WAV)
    raw_seconds = duration(RAW_WAV)
    tempo = raw_seconds / TARGET_SPOKEN_SECONDS
    if not 0.90 <= tempo <= 1.10:
        raise RuntimeError(
            f"Raw narration is {raw_seconds:.1f}s; revise the script instead of applying {tempo:.3f}x tempo"
        )
    run([
        FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", RAW_WAV,
        "-af", f"atempo={tempo:.8f},highpass=f=65,lowpass=f=15500,loudnorm=I=-16:TP=-1.5:LRA=7,apad=pad_dur=3",
        "-t", "300", "-ar", "48000", "-ac", "1", "-c:a", "aac", "-b:a", "192k", MASTER,
    ])
    manifest = {
        "script": str(SCRIPT),
        "narrator": script["narrator"],
        "reference": str(REFERENCE_WAV),
        "word_count": sum(len(section["narration"].split()) for section in script["sections"]),
        "raw_seconds": raw_seconds,
        "tempo": tempo,
        "master_seconds": duration(MASTER),
        "credits_charged_this_run": credits,
        "projects": sorted(projects, key=lambda item: (item["section"], item["chunk"])),
        "publishing_enabled": False,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
