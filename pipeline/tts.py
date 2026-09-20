"""Stage 3: narration audio per scene via Magic Hour voice cloner."""
import json
import re
from pathlib import Path

from . import magichour
from .config import TTS_CHUNK_LIMIT, VOICE_SAMPLE, require


def _split_oversize_sentence(sentence: str, limit: int) -> list[str]:
    """Split an unusually long spoken sentence at clauses, then words as a last resort."""
    clauses = re.split(r"(?<=[,;:—–])\s+", sentence.strip())
    pieces: list[str] = []
    current = ""
    for clause in clauses:
        candidate = clause if not current else current + " " + clause
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            pieces.append(current)
            current = ""
        if len(clause) <= limit:
            current = clause
            continue
        word_group = ""
        for word in clause.split():
            candidate = word if not word_group else word_group + " " + word
            if len(candidate) > limit and word_group:
                pieces.append(word_group)
                word_group = word
            else:
                word_group = candidate
        if word_group:
            current = word_group
    if current:
        pieces.append(current)
    return pieces


def split_text(text: str, limit: int = TTS_CHUNK_LIMIT) -> list[str]:
    """Split at spoken boundaries while guaranteeing every Magic Hour chunk fits."""
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    units = [piece for sentence in sentences for piece in _split_oversize_sentence(sentence, limit)]
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = unit if not current else current + " " + unit
        if len(candidate) > limit and current:
            chunks.append(current.strip())
            current = unit
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    if any(len(chunk) > limit for chunk in chunks):
        raise ValueError("TTS text splitting produced a chunk above the configured safety limit")
    return chunks


def run(run_dir: Path) -> Path:
    script = json.loads((run_dir / "script.json").read_text(encoding="utf-8"))
    sample = require(VOICE_SAMPLE, "VOICE_SAMPLE")
    audio_dir = run_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    print("Uploading voice sample...")
    sample_path = magichour.upload_file(sample, "audio")

    for scene in script["scenes"]:
        sid = scene["id"]
        chunk_files = []
        for i, chunk in enumerate(split_text(scene["narration"])):
            dest = audio_dir / f"scene_{sid:02d}_{i}.mp3"
            if dest.exists():
                chunk_files.append(dest)
                continue
            job_id = magichour.voice_clone(chunk, sample_path, f"scene {sid}.{i}")
            job = magichour.wait_audio(job_id)
            magichour.download(job, dest)
            chunk_files.append(dest)
            print(f"  scene {sid} chunk {i}: {job['credits_charged']} credits")
        scene["audio_files"] = [str(f.name) for f in chunk_files]

    (run_dir / "script.json").write_text(json.dumps(script, indent=2), encoding="utf-8")
    print(f"Audio done -> {audio_dir}")
    return audio_dir
