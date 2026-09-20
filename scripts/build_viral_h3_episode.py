"""Build the 2:30 MiniMax H3 news draft with one English cloned narrator."""
from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
from pathlib import Path

from pipeline import audio_qc, captions, magichour
from pipeline.config import LOCAL_FFMPEG_BIN, PROJECT_ROOT, VOICE_PROFILE_ID, VOICE_SAMPLE
from pipeline.render_v2 import concat_audio, duration, make_silence
from pipeline.tts import split_text


EPISODE_ID = "episode_20260807_minimax_h3_viral"
RUN_DIR = PROJECT_ROOT / "output" / "viral_h3_2m30"
PUBLIC_DIR = PROJECT_ROOT / "remotion" / "public" / "episode" / "h3-news"
FFMPEG = str(LOCAL_FFMPEG_BIN / "ffmpeg.exe") if (LOCAL_FFMPEG_BIN / "ffmpeg.exe").is_file() else "ffmpeg"

BEATS = [
    {
        "id": "b01", "purpose": "hook", "source_ids": ["comfy_day_zero"],
        "visual_direction": "Open on the ComfyUI day-zero announcement, then punch into an OPEN WEIGHTS card.",
        "narration": "Your gaming PC just got a second job as a part-time movie studio. MiniMax H3, the video model people were testing behind closed doors, now has public weights and day-zero ComfyUI workflows. That sounds like Hollywood in a box. The box, unfortunately, would also like forty-something gigabytes of memory and perhaps its own electrical substation. Here is why this matters.",
    },
    {
        "id": "b02", "purpose": "what_changed", "source_ids": ["minimax_launch", "minimax_repo"],
        "visual_direction": "Show the official launch and underline text, image, video, audio, 2K, and stereo audio.",
        "narration": "H3 can take text, images, video, and audio as references, then generate a clip with stereo sound. The official system supports four to fifteen seconds, defaults to seven-sixty-eight-p, and can reach 2K through a separate regeneration stage. So it is not picture-to-video with elevator music stapled on afterward. The genuinely interesting part is the release itself: MiniMax published the base checkpoints, and ComfyUI immediately added text-to-video and reference-to-video templates.",
    },
    {
        "id": "b03", "purpose": "open_release", "source_ids": ["minimax_repo", "comfy_day_zero"],
        "visual_direction": "Move through the official repository and ComfyUI workflow links with a small LOCAL badge.",
        "narration": "That means developers can inspect the weights, build custom pipelines, and fine-tune the complete model instead of renting every experiment by the second. Your terrible prompt can now fail privately on hardware you already regret buying.",
    },
    {
        "id": "b04", "purpose": "asterisk", "source_ids": ["minimax_repo", "comfy_day_zero"],
        "visual_direction": "Reveal a giant LOCAL asterisk, then compare 123.6 GB with 42.5 GB as a sourced community optimization claim.",
        "narration": "But local needs an asterisk visible from space. ComfyUI says its optimized package cuts memory from roughly one hundred twenty-three point six gigabytes to forty-two point five. It also says offloading can make a small variant run on an RTX 3060. Run is doing heroic work there. A bicycle also runs across America.",
    },
    {
        "id": "b05", "purpose": "reality_check", "source_ids": ["community_speed"],
        "visual_direction": "Show the community test report and animate a ten-second clip against a thirty-minute clock.",
        "narration": "One early community test reported thirty to thirty-four minutes for a ten-second clip on a forty-eight-gigabyte 4090 setup without acceleration. That is one setup, not a universal benchmark, but it explains the trade. Open weights remove the cloud bill, not physics. You pay with time, electricity, heat, and your room slowly becoming a bakery.",
    },
    {
        "id": "b06", "purpose": "why_it_matters", "source_ids": ["minimax_repo", "minimax_launch"],
        "visual_direction": "Build a clean three-step flow: reference media, local base model, editable result.",
        "narration": "For creators, the win is control. You can keep footage local, automate batches in ComfyUI, test quantized versions, and eventually train adapters for a specific look. H3 generates audio and video together, reducing the classic problem where the mouth finishes speaking while the soundtrack is still searching for the meeting link. That combination is rare in public-weight video models.",
    },
    {
        "id": "b07", "purpose": "limitation", "source_ids": ["minimax_repo"],
        "visual_direction": "Highlight the repository caveats: hosted Context IR, full attention today, 768p local base.",
        "narration": "Just do not confuse public weights with the entire commercial product. MiniMax says its Context IR, the system that interprets complicated multimodal instructions, is still hosted, not included. The first open release also uses full attention while sparse-attention inference is promised later, and local H3 Base produces seven-sixty-eight-p. The official 2K workflow still calls MiniMax services. Open, yes. Completely independent, not quite.",
    },
    {
        "id": "b08", "purpose": "verdict", "source_ids": ["comfy_day_zero", "minimax_repo"],
        "visual_direction": "End with a practical verdict card: download if you build workflows; wait if you only need quick clips.",
        "narration": "My verdict: H3 matters because this capability is no longer trapped behind one website. If you build workflows, own serious hardware, or care about customization, test the ComfyUI templates. If you only want your dog playing a medieval accountant, use the hosted version and enjoy a normal room temperature. Either way, open AI video became harder to ignore.",
    },
]

SOURCES = {
    "minimax_launch": {"title": "MiniMax H3 official launch", "url": "https://minimaxi.com/blog/minimax-h3", "publisher": "MiniMax"},
    "minimax_repo": {"title": "MiniMax H3 official repository", "url": "https://github.com/MiniMax-AI/MiniMax-H3", "publisher": "MiniMax"},
    "comfy_day_zero": {"title": "ComfyUI day-zero H3 workflows", "url": "https://www.reddit.com/r/StableDiffusion/comments/1ve1756/day_0_minimax_support_for_comfyui/", "publisher": "ComfyUI / r/StableDiffusion"},
    "community_speed": {"title": "Community generation-time report", "url": "https://www.reddit.com/r/comfyui/comments/1vg8tyt/comfyui_breakthrough_release_minimax_h3_the_new/", "publisher": "r/comfyui"},
}

PAID_CHUNK_SCRIPTS = [
    "Your gaming PC just got a second job as a part-time movie studio. MiniMax H3, the video model people were testing behind closed doors, now has public weights and day-zero ComfyUI workflows. That sounds like Hollywood in a box. The box, unfortunately, would also like forty-something gigabytes of memory and perhaps its own electrical substation. Here is why this matters. H3 can take text, images, video, and audio as references, then generate a clip with stereo sound. The official system supports four to fifteen seconds, defaults to seven-sixty-eight-p, and can reach 2K through a separate regeneration stage. So it is not picture-to-video with elevator music stapled on afterward. The genuinely interesting part is the release itself: MiniMax published the base checkpoints, and ComfyUI immediately added text-to-video and reference-to-video templates.",
    "That means developers can inspect the weights, build custom pipelines, and fine-tune the complete model instead of renting every experiment by the second. Your terrible prompt can now fail privately on hardware you already regret buying. But local needs an asterisk visible from space. ComfyUI says its optimized package cuts memory from roughly one hundred twenty-three point six gigabytes to forty-two point five. It also says offloading can make a small variant run on an RTX 3060. Run is doing heroic work there. A bicycle also runs across America. One early community test reported thirty to thirty-four minutes for a ten-second clip on a forty-eight-gigabyte 4090 setup without acceleration. That is one setup, not a universal benchmark, but it explains the trade. Open weights remove the cloud bill, not physics. You pay with time, electricity, heat, and your room slowly becoming a bakery. For creators, the win is control.",
    "You can keep footage local, automate batches in ComfyUI, test quantized versions, and eventually train adapters for a specific look. H3 generates audio and video together, reducing the classic problem where the mouth finishes speaking while the soundtrack is still searching for the meeting link. That combination is rare in public-weight video models. Just do not confuse public weights with the entire commercial product. MiniMax says its Context IR, the system that interprets complicated multimodal instructions, is still hosted, not included. The first open release also uses full attention while sparse-attention inference is promised later, and local H3 Base produces seven-sixty-eight-p. The official 2K workflow still calls MiniMax services. Open, yes. Completely independent, not quite. My verdict: H3 matters because this capability is no longer trapped behind one website.",
    "If you build workflows, own serious hardware, or care about customization, test the ComfyUI templates. If you only want your dog playing a medieval accountant, use the hosted version and enjoy a normal room temperature. Either way, open AI video became harder to ignore.",
]


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _word_count(text: str) -> int:
    return len(text.replace("—", " ").split())


def _make_silence_24(destination: Path, milliseconds: int) -> Path:
    seconds = max(0.001, milliseconds / 1000)
    _run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
        "-t", f"{seconds:.3f}", "-c:a", "pcm_s24le", str(destination),
    ])
    return destination


def _concat_audio_24(files: list[Path], destination: Path) -> Path:
    command = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    for path in files:
        command.extend(["-i", str(path)])
    inputs = "".join(f"[{index}:a]" for index in range(len(files)))
    command.extend([
        "-filter_complex", f"{inputs}concat=n={len(files)}:v=0:a=1[out]",
        "-map", "[out]", "-ar", "48000", "-ac", "1",
        "-c:a", "pcm_s24le", str(destination),
    ])
    _run(command)
    return destination


def _asset_package() -> dict[str, dict[str, str]]:
    manifest = json.loads((RUN_DIR / "source_manifest.json").read_text(encoding="utf-8"))
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    packaged: dict[str, dict[str, str]] = {}
    for source in manifest:
        item: dict[str, str] = {}
        for key, candidates in (("viewport", source["screenshots"]), ("screen_recording", source["recordings"])):
            if not candidates:
                continue
            origin = PROJECT_ROOT / candidates[0]
            destination = PUBLIC_DIR / origin.name
            shutil.copy2(origin, destination)
            item[key] = f"episode/h3-news/{destination.name}"
        packaged[source["id"]] = item
    return packaged


def _make_narration(script: str) -> tuple[Path, int, list[captions.TimedWord]]:
    audio_dir = RUN_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    sample = PROJECT_ROOT / VOICE_SAMPLE
    paid_mastered = [audio_dir / f"chunk_{index:02d}.wav" for index in range(len(PAID_CHUNK_SCRIPTS))]
    if all(path.exists() for path in paid_mastered):
        chunks = PAID_CHUNK_SCRIPTS
        use_paid_take = True
    else:
        chunks = split_text(script)
        use_paid_take = False
    missing_raw = []
    for index, chunk in enumerate(chunks):
        chunk_key = hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:10]
        raw = audio_dir / f"chunk_{index:02d}_{chunk_key}_raw.mp3"
        if not raw.exists():
            missing_raw.append(raw)
    uploaded = magichour.upload_file(str(sample), "audio") if missing_raw and not use_paid_take else None
    mastered_chunks: list[Path] = []
    credits = 0
    for index, chunk in enumerate(chunks):
        chunk_key = hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:10]
        raw = audio_dir / f"chunk_{index:02d}_{chunk_key}_raw.mp3"
        mastered = audio_dir / f"chunk_{index:02d}_{chunk_key}.wav"
        if use_paid_take:
            mastered = paid_mastered[index]
        else:
            if not raw.exists():
                assert uploaded is not None
                project_id = magichour.voice_clone(chunk, uploaded, f"{EPISODE_ID}-{VOICE_PROFILE_ID}-{index}")
                job = magichour.wait_audio(project_id)
                credits += int(job.get("credits_charged", 0) or 0)
                magichour.download(job, raw)
            audio_qc.master_narration(raw, mastered)
        if not use_paid_take:
            review = audio_qc.review_narration(
                mastered,
                chunk,
                sample,
                enforce_pacing=False,
                max_unmatched_words=6,
                min_intelligibility=0.88,
            )
            if not review["passed"]:
                raise RuntimeError(f"voice chunk {index} failed: {review['failures']}")
        mastered_chunks.append(mastered)

    intro = _make_silence_24(audio_dir / "intro.wav", 350)
    gap = _make_silence_24(audio_dir / "gap.wav", 450)
    parts: list[Path] = [intro]
    for index, chunk in enumerate(mastered_chunks):
        parts.append(chunk)
        if index < len(mastered_chunks) - 1:
            parts.append(gap)
    joined = _concat_audio_24(parts, audio_dir / "joined.wav")
    joined_duration = duration(joined)
    if joined_duration > 148.8:
        rate = joined_duration / 148.4
        if rate > 1.16:
            raise RuntimeError(f"narration is too long for 2:30 ({joined_duration:.2f}s)")
        adjusted = audio_dir / "joined_adjusted.wav"
        _run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(joined), "-af", f"atempo={rate:.6f}", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(adjusted)])
        joined = adjusted
    speech_duration = duration(joined)
    tail_ms = max(800, round((150.0 - speech_duration) * 1000))
    tail = _make_silence_24(audio_dir / "tail.wav", tail_ms)
    padded = _concat_audio_24([joined, tail], audio_dir / "padded.wav")
    final = RUN_DIR / "narration.wav"
    audio_qc.master_narration(padded, final)
    if duration(final) > 150.02:
        trimmed = RUN_DIR / "narration_trimmed.wav"
        _run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(final), "-t", "150", "-c:a", "pcm_s24le", str(trimmed)])
        trimmed.replace(final)
    recognized = captions.transcribe_words(final)
    recognized_text = " ".join(word.text for word in recognized)
    final_review = audio_qc.review_narration(
        final,
        script,
        sample,
        recognized_text=recognized_text,
        enforce_pacing=False,
        max_unmatched_words=14,
        min_intelligibility=0.88,
    )
    if not final_review["passed"]:
        raise RuntimeError(f"final narration failed: {final_review['failures']}")
    (RUN_DIR / "audio_qc.json").write_text(json.dumps(final_review, indent=2), encoding="utf-8")
    return final, credits, recognized


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    script = "\n\n".join(beat["narration"] for beat in BEATS)
    print(f"Script words: {_word_count(script)}")
    narration, credits, recognized = _make_narration(script)
    aligned = captions.align_script_words(script, recognized)
    caption_data = [
        {"text": word.text, "startMs": round(word.start * 1000), "endMs": round(word.end * 1000), "timestampMs": round(word.start * 1000), "confidence": None}
        for word in aligned
    ]
    all_words = script.split()
    offset = 0
    for beat in BEATS:
        count = len(beat["narration"].split())
        beat["startMs"] = caption_data[min(offset, len(caption_data) - 1)]["startMs"]
        beat["endMs"] = caption_data[min(offset + count - 1, len(caption_data) - 1)]["endMs"]
        beat["wordCount"] = count
        beat["claim_ids"] = []
        offset += count
    assets = _asset_package()
    shutil.copy2(narration, PUBLIC_DIR / "narration.wav")
    episode = {
        "episodeId": EPISODE_ID,
        "title": "This AI Video Model Just Escaped the Cloud",
        "description": "MiniMax H3 public weights, ComfyUI day-zero support, and the very large local-hardware asterisk.",
        "disclosure": "AI-assisted research and a consistent synthetic narrator. No AI-generated visuals are used.",
        "durationSeconds": 150,
        "beats": BEATS,
        "sources": SOURCES,
        "assets": assets,
        "credits": credits,
    }
    (PUBLIC_DIR / "episode.json").write_text(json.dumps(episode, indent=2), encoding="utf-8")
    (PUBLIC_DIR / "captions.json").write_text(json.dumps(caption_data, indent=2), encoding="utf-8")
    (RUN_DIR / "script.txt").write_text(script, encoding="utf-8")
    (RUN_DIR / "episode.json").write_text(json.dumps(episode, indent=2), encoding="utf-8")
    print(json.dumps({"narration": str(narration), "duration": duration(narration), "credits": credits, "public": str(PUBLIC_DIR)}, indent=2))


if __name__ == "__main__":
    main()
