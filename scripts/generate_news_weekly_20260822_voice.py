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


OUT = ROOT / "output" / "news_weekly_20260822"
SCRIPT = OUT / "script.json"
AUDIO_DIR = OUT / "audio"
REFERENCE = ROOT / "output" / "claude_chips_5m_recreate" / "audio_news_v3" / "approved_narrator_reference.wav"
RAW = AUDIO_DIR / "narration_raw.wav"
MASTER = AUDIO_DIR / "narration_master.m4a"
CAPTIONS = OUT / "captions_monochrome.ass"
MANIFEST = AUDIO_DIR / "manifest.json"
FFMPEG_ROOT = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\tools\ffmpeg\bin")
FFMPEG = FFMPEG_ROOT / "ffmpeg.exe"
FFPROBE = FFMPEG_ROOT / "ffprobe.exe"
TARGET_SPOKEN_SECONDS = 597.0


def run(args: list[str | Path]) -> None:
    subprocess.run([str(value) for value in args], check=True)


def duration(path: Path) -> float:
    value = subprocess.check_output([
        str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], text=True).strip()
    return float(value)


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
        raise ValueError("Narration chunk exceeds Magic Hour's 1,000-character limit")
    return chunks


def ass_time(seconds: float) -> str:
    hundredths = max(0, round(seconds * 100))
    hours, rem = divmod(hundredths, 360000)
    minutes, rem = divmod(rem, 6000)
    secs, hs = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{hs:02d}"


def write_captions(records: list[dict], tempo: float) -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,5,1,2,120,120,72,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    cursor = 0.0
    for record in records:
        adjusted = float(record["seconds"]) / tempo
        words = re.findall(r"\S+", record["text"])
        if not words:
            cursor += adjusted
            continue
        weights = [max(1, len(re.sub(r"[^A-Za-z0-9]", "", word))) for word in words]
        total_weight = sum(weights)
        local = cursor
        index = 0
        while index < len(words):
            group = words[index:index + 4]
            group_weight = sum(weights[index:index + len(group)])
            group_seconds = max(0.42, adjusted * group_weight / total_weight)
            end = min(cursor + adjusted, local + group_seconds)
            text = " ".join(group).replace("{", "(").replace("}", ")")
            events.append(
                f"Dialogue: 0,{ass_time(local)},{ass_time(end)},Caption,,0,0,0,,{text}"
            )
            local = end
            index += len(group)
        cursor += adjusted
    CAPTIONS.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")


def main() -> None:
    if not REFERENCE.exists():
        raise FileNotFoundError(REFERENCE)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    tasks: list[dict] = []
    order: list[dict] = []
    for section in script["sections"]:
        for index, text in enumerate(split_text(section["narration"])):
            destination = AUDIO_DIR / f"{section['id']}_{index:02d}.mp3"
            item = {"section": section["id"], "index": index, "text": text, "file": destination}
            order.append(item)
            if not destination.exists() or destination.stat().st_size < 50_000:
                tasks.append(item)

    projects: list[dict] = []
    credits = 0
    if tasks:
        uploaded = magichour.upload_file(str(REFERENCE), "audio")

        def generate(item: dict) -> dict:
            project_id = magichour.voice_clone(
                item["text"], uploaded,
                f"news-weekly-20260822-{item['section']}-{item['index']:02d}",
            )
            job = magichour.wait_audio(project_id)
            magichour.download(job, item["file"])
            return {
                "section": item["section"], "index": item["index"],
                "project_id": project_id, "credits": int(job.get("credits_charged", 0)),
            }

        with ThreadPoolExecutor(max_workers=min(3, len(tasks))) as pool:
            futures = [pool.submit(generate, item) for item in tasks]
            for future in as_completed(futures):
                result = future.result()
                projects.append(result)
                credits += result["credits"]

    for item in order:
        if not item["file"].exists():
            raise RuntimeError(f"Missing narration chunk: {item['file']}")
        item["seconds"] = duration(item["file"])

    concat = AUDIO_DIR / "chunks.concat.txt"
    concat.write_text("".join(f"file '{item['file'].resolve().as_posix()}'\n" for item in order), encoding="utf-8")
    run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", concat,
         "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", RAW])
    raw_seconds = duration(RAW)
    tempo = raw_seconds / TARGET_SPOKEN_SECONDS
    if not 0.88 <= tempo <= 1.12:
        raise RuntimeError(f"Narration pace is outside the natural range: raw={raw_seconds:.1f}s tempo={tempo:.3f}")
    run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", RAW,
         "-af", f"atempo={tempo:.8f},highpass=f=65,lowpass=f=15500,loudnorm=I=-16:TP=-1.5:LRA=7,apad=pad_dur=6",
         "-t", "600", "-ar", "48000", "-ac", "1", "-c:a", "aac", "-b:a", "192k", MASTER])
    write_captions(order, tempo)
    manifest = {
        "narrator": script["narrator"], "reference": str(REFERENCE),
        "word_count": sum(len(section["narration"].split()) for section in script["sections"]),
        "raw_seconds": raw_seconds, "tempo": tempo, "master_seconds": duration(MASTER),
        "credits_charged_this_run": credits, "projects": projects,
        "caption_style": "white type, black outline and shadow; no colored karaoke",
        "publishing_enabled": False,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
