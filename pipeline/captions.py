"""Word-timed ASS captions aligned back to the approved script spelling."""
from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass
class TimedWord:
    text: str
    start: float
    end: float


def _normal(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


@lru_cache(maxsize=2)
def _whisper_model(model_size: str):
    from faster_whisper import WhisperModel

    return WhisperModel(model_size, device="cpu", compute_type="int8")


def _openai_transcribe_words(audio_path: Path) -> list[TimedWord]:
    """Use the existing OpenAI credential when local Whisper is policy-blocked."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "local Whisper is unavailable and OPENAI_API_KEY is not configured for transcription fallback"
        )
    upload_path = audio_path
    temporary_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        # OpenAI audio uploads have a finite request-size ceiling. Narration
        # masters can exceed it as PCM WAV, so create a speech-only MP3 copy.
        if audio_path.stat().st_size > 20 * 1024 * 1024:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise RuntimeError("ffmpeg is required to compress narration for transcription")
            temporary_dir = tempfile.TemporaryDirectory(prefix="caption-asr-")
            upload_path = Path(temporary_dir.name) / "speech.mp3"
            subprocess.run(
                [
                    ffmpeg, "-y", "-v", "error", "-i", str(audio_path),
                    "-ac", "1", "-ar", "16000", "-b:a", "64k", str(upload_path),
                ],
                check=True,
            )
        client = OpenAI(api_key=api_key)
        with upload_path.open("rb") as audio_file:
            result = client.audio.transcriptions.create(
                model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1"),
                file=audio_file,
                language="en",
                response_format="verbose_json",
                timestamp_granularities=["word"],
            )
        raw_words = getattr(result, "words", None) or []
        words = [
            TimedWord(
                str(getattr(item, "word", "")).strip(),
                float(getattr(item, "start")),
                float(getattr(item, "end")),
            )
            for item in raw_words
            if getattr(item, "word", None)
            and getattr(item, "start", None) is not None
            and getattr(item, "end", None) is not None
        ]
        if not words:
            raise RuntimeError("OpenAI transcription fallback produced no timed words")
        return words
    finally:
        if temporary_dir is not None:
            temporary_dir.cleanup()


def transcribe_words(audio_path: Path, model_size: str = "small.en") -> list[TimedWord]:
    try:
        model = _whisper_model(model_size)
    except (ImportError, OSError):
        return _openai_transcribe_words(audio_path)

    segments, _ = model.transcribe(str(audio_path), word_timestamps=True, vad_filter=True)
    words = []
    for segment in segments:
        for word in segment.words or []:
            if word.start is not None and word.end is not None:
                words.append(TimedWord(word.word.strip(), float(word.start), float(word.end)))
    if not words:
        raise RuntimeError("caption transcription produced no timed words")
    return words


def align_script_words(script: str, recognized: list[TimedWord]) -> list[TimedWord]:
    script_words = re.findall(r"\S+", script)
    script_norm = [_normal(word) for word in script_words]
    recognized_norm = [_normal(word.text) for word in recognized]
    matcher = difflib.SequenceMatcher(a=script_norm, b=recognized_norm, autojunk=False)
    times: list[tuple[float, float] | None] = [None] * len(script_words)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                times[i1 + offset] = (recognized[j1 + offset].start, recognized[j1 + offset].end)
    for index, timing in enumerate(times):
        if timing:
            continue
        previous = next((times[i] for i in range(index - 1, -1, -1) if times[i]), None)
        following = next((times[i] for i in range(index + 1, len(times)) if times[i]), None)
        start = previous[1] if previous else (following[0] - 0.25 if following else index * 0.25)
        end = following[0] if following else start + 0.25
        end = max(start + 0.08, min(end, start + 0.45))
        times[index] = (max(0, start), end)
    return normalize_word_timings([
        TimedWord(word, timing[0], timing[1]) for word, timing in zip(script_words, times)
    ])


def normalize_word_timings(words: list[TimedWord], min_duration: float = 0.04) -> list[TimedWord]:
    """Make word intervals strictly positive and nonoverlapping without changing text order."""
    normalized: list[TimedWord] = []
    previous_end = 0.0
    for word in words:
        start = max(previous_end, float(word.start), 0.0)
        end = max(float(word.end), start + min_duration)
        normalized.append(TimedWord(word.text, start, end))
        previous_end = end
    return normalized


def alignment_quality(script: str, recognized: list[TimedWord]) -> dict:
    """Measure whether ASR timings are trustworthy before interpolation hides errors."""
    script_words = re.findall(r"\S+", script)
    script_norm = [_normal(word) for word in script_words]
    recognized_norm = [_normal(word.text) for word in recognized]
    matcher = difflib.SequenceMatcher(a=script_norm, b=recognized_norm, autojunk=False)
    matched = 0
    largest_unmatched = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            matched += i2 - i1
        else:
            largest_unmatched = max(largest_unmatched, i2 - i1, j2 - j1)
    ratio = matched / max(1, len(script_words))
    monotonic = all(
        recognized[index].start <= recognized[index].end <= recognized[index + 1].end
        for index in range(max(0, len(recognized) - 1))
    )
    return {
        "passed": ratio >= 0.72 and largest_unmatched <= 10 and monotonic,
        "script_words": len(script_words),
        "recognized_words": len(recognized),
        "matched_words": matched,
        "matched_ratio": round(ratio, 4),
        "largest_unmatched_run": largest_unmatched,
        "timings_monotonic": monotonic,
    }


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def write_ass(words: list[TimedWord], output: Path, group_size: int = 4) -> Path:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Caption,Noto Sans,52,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,4,1,2,110,110,78,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [header]
    for offset in range(0, len(words), group_size):
        group = words[offset:offset + group_size]
        if not group:
            continue
        pieces = []
        for word in group:
            duration_cs = max(1, round((word.end - word.start) * 100))
            clean = word.text.replace("{", "(").replace("}", ")")
            pieces.append(f"{{\\k{duration_cs}}}{clean}")
        lines.append(
            f"Dialogue: 0,{_ass_time(group[0].start)},{_ass_time(group[-1].end)},Caption,,0,0,0,,{' '.join(pieces)}\n"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(lines), encoding="utf-8-sig")
    return output


def generate_captions(audio_path: Path, approved_script: str, output: Path) -> Path:
    recognized = transcribe_words(audio_path)
    report = alignment_quality(approved_script, recognized)
    report_path = output.with_suffix(".alignment.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError(
            "caption alignment QC failed: "
            f"matched={report['matched_ratio']:.1%}, largest_gap={report['largest_unmatched_run']}"
        )
    aligned = align_script_words(approved_script, recognized)
    return write_ass(aligned, output)
