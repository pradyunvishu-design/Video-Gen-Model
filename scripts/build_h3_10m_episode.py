"""Build a source-backed ten-minute MiniMax H3 episode and narration package."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import requests

from pipeline import audio_qc, captions, magichour
from pipeline.config import LOCAL_FFMPEG_BIN, PROJECT_ROOT, VOICE_PROFILE_ID, VOICE_SAMPLE
from pipeline.render_v2 import duration
from pipeline.tts import split_text


EPISODE_ID = "episode_20260818_minimax_h3_deep_dive"
RUN_DIR = PROJECT_ROOT / "output" / "minimax_h3_10m"
PUBLIC_DIR = PROJECT_ROOT / "remotion" / "public" / "episode" / "h3-10m"
FFMPEG = str(LOCAL_FFMPEG_BIN / "ffmpeg.exe") if (LOCAL_FFMPEG_BIN / "ffmpeg.exe").is_file() else "ffmpeg"
TARGET_SECONDS = 600.0

SOURCES = {
    "minimax_launch": {
        "title": "MiniMax H3 open-source announcement",
        "url": "https://www.minimax.io/news/minimax-h3-open-source",
        "publisher": "MiniMax",
    },
    "minimax_model": {
        "title": "MiniMax H3 model card and official assets",
        "url": "https://huggingface.co/MiniMaxAI/MiniMax-H3",
        "publisher": "MiniMax / Hugging Face",
    },
    "comfy_workflow": {
        "title": "Official ComfyUI MiniMax H3 workflow",
        "url": "https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_i2v.json",
        "publisher": "ComfyUI",
    },
    "comfy_day_zero": {
        "title": "ComfyUI day-zero MiniMax H3 support",
        "url": "https://www.reddit.com/r/comfyui/comments/1ve18f9/day_0_minimax_support_for_comfyui/",
        "publisher": "ComfyUI / r/comfyui",
    },
    "community_update": {
        "title": "MiniMax H3 community update — August 18",
        "url": "https://www.reddit.com/r/comfyui/comments/1vrsspo/a_quick_minimax_h3_news_roundup_18th_august_2026/",
        "publisher": "r/comfyui",
    },
}

OFFICIAL_ASSETS = {
    "t2va": "assets/t2va.mp4",
    "fl2va": "assets/fl2va.mp4",
    "i2va": "assets/i2va.mp4",
    "r2va": "assets/r2va.mp4",
    "ref2va": "assets/ref2va.mp4",
    "t2va_2k": "assets/t2va_2k.mp4",
    "i2va_2k": "assets/i2va_2k.mp4",
    "r2va_2k": "assets/r2va_2k.mp4",
    "direct_2k": "assets/h3_direct_2k.mp4",
    "direct_768": "assets/h3_direct_768p.mp4",
    "i2va_direct_2k": "assets/i2va_direct_2k.mp4",
    "i2va_direct_768": "assets/i2va_direct_768p.mp4",
    "r2va_direct_2k": "assets/r2va_direct_2k.mp4",
    "r2va_direct_768": "assets/r2va_direct_768p.mp4",
    "architecture": "assets/full-arch.png",
    "overview": "assets/overview.png",
    "hero": "assets/minimax-h3.png",
}


BEATS = [
    {
        "id": "b01", "purpose": "hook", "source_ids": ["minimax_launch", "comfy_day_zero"],
        "broll": ["direct_2k", "t2va_2k", "hero"],
        "overlay": "AI VIDEO JUST WENT LOCAL", "accent": "OPEN WEIGHTS · VIDEO + STEREO AUDIO",
        "narration": "MiniMax just put part of H3 on local machines. That sounds huge, but the useful question is smaller: can you turn it into a repeatable video workflow, or are you buying yourself a very slow weekend? ComfyUI had templates ready on day zero, and H3 can make video with stereo sound. The answer depends on what actually runs on your own computer, what MiniMax's official clips really prove, and which important pieces still route back through the company today.",
    },
    {
        "id": "b02", "purpose": "what_it_is", "source_ids": ["minimax_launch", "minimax_model"],
        "broll": ["overview", "t2va", "fl2va"],
        "overlay": "ONE MODEL, FOUR KINDS OF INPUT", "accent": "TEXT · IMAGES · VIDEO · AUDIO",
        "narration": "Think of it like directing one shot. You give H3 a prompt, then you can add examples of who is in the scene, how it should begin, how it should end, and what it should sound like. MiniMax says the reference setup can take up to nine images, three short clips, and three audio clips. That matters because basic image-to-video often means: here is one picture, please animate it. H3 can instead start on this frame, end on that frame, keep this character recognizable, and make the room sound like a room.",
    },
    {
        "id": "b03", "purpose": "native_audio", "source_ids": ["minimax_launch", "minimax_model"],
        "broll": ["r2va", "ref2va", "i2va"],
        "overlay": "THE AUDIO IS GENERATED WITH THE VIDEO", "accent": "32 kHz STEREO · JOINT OUTPUT",
        "narration": "What stands out is that H3 generates the picture and sound together. That gives lip movement, ambience, and effects a better shot at lining up. The export is 24 frames per second with 32-kilohertz stereo audio, but the sync matters more than the specs. If a character turns toward a sound too late, or closes their mouth before a word ends, you notice immediately. MiniMax's pitch is that solving picture and sound at the same time should reduce that mismatch instead of leaving the editor to repair it later.",
    },
    {
        "id": "b04", "purpose": "open_release", "source_ids": ["minimax_model", "comfy_workflow"],
        "broll": ["architecture", "direct_768", "t2va"],
        "overlay": "THE BASE WEIGHTS ARE PUBLIC", "accent": "FL2VA · REF2VA · DIFFUSERS · COMFYUI",
        "narration": "MiniMax also lets people download the core parts that generate the video and audio. The official ComfyUI template shows how those parts connect. In principle, a team could keep more reference material on its own machines instead of uploading every test to a web app. That matters when the footage is private, unfinished, or too large to keep sending back and forth. The web version is still convenient. It simply is not the only way into H3 anymore.",
    },
    {
        "id": "b05", "purpose": "comfyui", "source_ids": ["comfy_workflow", "comfy_day_zero"],
        "broll": ["fl2va", "i2va", "overview"],
        "overlay": "COMFYUI SUPPORT LANDED ON DAY ZERO", "accent": "TEXT-TO-VIDEO · FIRST/LAST FRAME · REFERENCES",
        "narration": "The good news is that ComfyUI does not make you start from scratch. The official template lays out the main path in the graph: load the model, add a prompt or reference frames, then follow the branches to the video and audio outputs. You still choose the draft resolution and duration, but the connections are already there. The graph may look like somebody turned a server rack into a board game. Day-zero support matters because people could download H3 and try a first render right away, instead of spending the first night wiring nodes together and guessing what MiniMax meant.",
    },
    {
        "id": "b06", "purpose": "hardware", "source_ids": ["comfy_day_zero", "minimax_model"],
        "broll": ["architecture", "r2va_direct_768", "direct_768"],
        "overlay": "123.6 GB → 42.5 GB", "accent": "COMFYUI'S OPTIMIZED MEMORY FOOTPRINT",
        "narration": "Here is the hardware reality check. According to ComfyUI's published workflow notes, its memory-saving version can drop H3's footprint from about 124 gigabytes to 42.5. We have not verified that ourselves, so take it as an encouraging report, not a promise that your machine will suddenly feel comfortable. ComfyUI also says an RTX 3060 can run H3 by moving parts of the model between graphics memory and normal system memory. And that distinction matters. A setup that barely fits can still be slow enough that testing one bad camera move takes a painful amount of time. Local access and practical access are not the same thing.",
    },
    {
        "id": "b07", "purpose": "quality", "source_ids": ["minimax_launch", "minimax_model"],
        "broll": ["t2va_2k", "i2va_2k", "r2va_2k"],
        "overlay": "LOOK AT THE OFFICIAL OUTPUTS", "accent": "MOTION · CONTINUITY · CAMERA · SOUND",
        "narration": "The official samples make the quality easier to judge. In the starship showcase, the edit moves from a wide view to a closer one. The same short silver hair, red collar detail, dark uniform, and cool window light remain consistent across those presented shots. The dinner-table example is busier. People pass food across the same long table, the large bowl stays in the foreground, steam keeps rising, and the warm side light remains consistent. In the clips MiniMax chose to show, the strongest results are the simpler ones. That is not a law; it is only the safest takeaway from this sample set.",
    },
    {
        "id": "b08", "purpose": "resolution", "source_ids": ["minimax_launch", "minimax_model"],
        "broll": ["direct_768", "direct_2k", "i2va_direct_768", "i2va_direct_2k"],
        "overlay": "768P BASE → 2K REGENERATION", "accent": "NOT A NORMAL UPSCALE",
        "narration": "There is an important catch with the advertised 2K output. This is not a normal upscale. H3 makes a smaller draft, then runs a second pass with the same prompt and references to rebuild the shot at higher resolution. MiniMax says that can recover detail instead of only stretching the first render, and its own comparisons do look cleaner. But the 2K regeneration module is not part of the open release yet. So if you want the full 2K path today, local H3 is only part of the trip. You still lean on MiniMax's hosted tools to finish the job.",
    },
    {
        "id": "b09", "purpose": "not_fully_local", "source_ids": ["minimax_launch", "minimax_model"],
        "broll": ["overview", "architecture", "ref2va"],
        "overlay": "OPEN WEIGHTS ≠ THE WHOLE SYSTEM", "accent": "CONTEXT IR AND 2K REGEN ARE HOSTED",
        "narration": "One important planning layer is still cloud-only. It organizes your prompt, images, clips, and audio into a shot plan for H3. MiniMax calls that Context IR. It tells the model what each reference should contribute and what the final shot should do. Because that planner stays hosted, local H3 is not a complete offline tool. MiniMax's published notes also suggest the local route is slower and clunkier for now because some online helpers and speedups are missing.",
    },
    {
        "id": "b10", "purpose": "community", "source_ids": ["community_update", "comfy_day_zero"],
        "broll": ["r2va", "fl2va_2k", "i2va_direct_2k"],
        "overlay": "THE COMMUNITY MOVED FAST", "accent": "PREVIEWS · KEYFRAMES · UPSCALERS · LoRAs",
        "narration": "Unverified community reports already point to two useful add-ons. One ComfyUI project shows a rough motion preview while the full generation is still running. The idea is to catch a camera move going the wrong way before wasting the entire render. Another reported workflow adds keyframes beyond the beginning and end, giving creators more control over the middle of a shot. We have not tested those add-ons, so treat them as leads, not guarantees. Public weights matter because outside developers can patch obvious workflow gaps instead of waiting for the company to do it.",
    },
    {
        "id": "b11", "purpose": "workflow", "source_ids": ["comfy_workflow", "minimax_model"],
        "broll": ["fl2va", "r2va_2k", "overview"],
        "overlay": "A PRACTICAL CREATOR WORKFLOW", "accent": "PREVIEW LOW · LOCK REFERENCES · FINISH HIGH",
        "narration": "If you follow the official template's logic, the sensible order appears to be this. Start at a lower resolution, keep the clip short, and check the motion before spending time on a heavier render. We have not completed that test ourselves, so this is a workflow recommendation, not a benchmark. If a character's walk or the camera direction is wrong, more quality only gives you a cleaner bad shot. If the draft behaves, lock the start and end frames, add identity references, then use the highest-quality pass you can access locally or through MiniMax. I would still check the audio in the edit, because sync mistakes become obvious there.",
    },
    {
        "id": "b12", "purpose": "who_for", "source_ids": ["minimax_model", "comfy_workflow"],
        "broll": ["t2va", "i2va_2k", "r2va_direct_2k"],
        "overlay": "WHO SHOULD ACTUALLY DOWNLOAD IT?", "accent": "BUILDERS · STUDIOS · RESEARCHERS",
        "narration": "The people most likely to benefit are tool builders, studios working with private footage, and power users who do not mind trading convenience for control. If you only need a few polished clips this week, the hosted product is probably the better bargain. Local generation gives you ownership and flexibility, but it also gives you huge downloads, software conflicts, storage pressure, and a new hobby called watching a progress bar. Free weights do not create free afternoons.",
    },
    {
        "id": "b13", "purpose": "why_now", "source_ids": ["minimax_launch", "community_update"],
        "broll": ["direct_2k", "ref2va", "hero"],
        "overlay": "AI VIDEO IS BECOMING INFRASTRUCTURE", "accent": "NOT JUST ANOTHER WEBSITE",
        "narration": "That preview-low, finish-high pattern is the clue. H3 seems to fit best inside a hybrid pipeline: sketch the idea in a hosted tool, move into ComfyUI when you need deeper control, and use an API when a team needs scale. At that point, the prettiest demo is not enough. The tool also has to be affordable, automatable, and safe enough for private footage. H3 is useful evidence that AI video is moving in that direction, even if the complete workflow is not local yet.",
    },
    {
        "id": "b13a_test", "purpose": "creator_test", "source_ids": ["comfy_workflow", "minimax_model"],
        "broll": ["fl2va", "i2va", "r2va"],
        "overlay": "THE FIRST TEST SHOULD BE BORING", "accent": "ONE SUBJECT · ONE MOVE · ONE SOUND CUE",
        "narration": "If you try H3, make the first test boring on purpose. Use one subject, one clear camera move, and one sound cue you can judge immediately. A person turns toward a closing door. A product rotates while the camera pushes in. A character speaks one short line in a quiet room. Those tests are useful because you can see which part broke. Did the identity drift? Did the camera move smoothly? Did the sound arrive at the right moment? Once those basics hold, add complexity one piece at a time. Otherwise, when the result falls apart, you will not know which instruction caused it.",
    },
    {
        "id": "b13b_limits", "purpose": "sample_limits", "source_ids": ["minimax_launch", "minimax_model"],
        "broll": ["t2va_2k", "i2va_2k", "r2va_2k"],
        "overlay": "OFFICIAL DEMOS ARE A BEST-CASE WINDOW", "accent": "USEFUL EVIDENCE · NOT A RANDOM TEST SET",
        "narration": "Official examples have limits. MiniMax chose these clips carefully. They let us inspect motion and how picture and sound fit together. They do not show the failure rate across random prompts, how often a character survives separate shots, or how many attempts produced the published result. That is normal for a launch page, but it changes how we read it. The demos prove H3 can make convincing moments. They do not prove every creator gets one on the first try.",
    },
    {
        "id": "b13c_license", "purpose": "license", "source_ids": ["minimax_model"],
        "broll": ["hero", "architecture", "overview"],
        "overlay": "OPEN WEIGHTS STILL COME WITH TERMS", "accent": "READ THE H3 COMMUNITY LICENSE",
        "narration": "Open weights do not mean no rules. H3 comes with MiniMax's license, and teams should read it before building a product. Record the model version, save that license, and keep a source note for every reference image, clip, and audio file. Local generation gives you more control. It does not automatically give you permission to use somebody else's face, voice, footage, or brand. The model and the material you feed it are separate rights questions.",
    },
    {
        "id": "b13d_choice", "purpose": "decision", "source_ids": ["minimax_launch", "comfy_workflow", "minimax_model"],
        "broll": ["direct_768", "direct_2k", "overview"],
        "overlay": "LOCAL OR HOSTED? PICK BY THE JOB", "accent": "CONTROL · SPEED · PRIVACY · COST",
        "narration": "Choose local H3 when privacy or custom controls justify the setup. Choose the hosted path when speed matters more, when you need 2K, or when the team cannot maintain model files. Many projects will use both. A studio might explore sensitive footage locally, send an approved draft into a hosted finishing step, then bring it back into the edit. The right answer keeps the creative loop fast without giving up the control the project needs.",
    },
    {
        "id": "b14", "purpose": "verdict", "source_ids": ["minimax_launch", "minimax_model", "comfy_workflow"],
        "broll": ["t2va_2k", "r2va_2k", "direct_2k"],
        "overlay": "THE VERDICT", "accent": "REAL RELEASE · REAL CONTROL · REAL HARDWARE COST",
        "narration": "So here is my takeaway. H3 looks real enough to experiment with locally, especially for simpler shots. But because the planner and the 2K path still lean on MiniMax, the best workflow today is hybrid: preview low, lock references, finish high. If your work needs privacy or custom control, H3 deserves a serious look. And if all you need is one polished shot by Friday, the hosted version may still save your weekend, because convenience is part of the workflow too.",
    },
]


def _naturalize(text: str) -> str:
    """Prefer contractions that sound natural without adding slang or hype."""
    replacements = {
        "That does not ": "That doesn't ",
        "It does not ": "It doesn't ",
        "You do not ": "You don't ",
        "you do not ": "you don't ",
        "It is not ": "It isn't ",
        "it is not ": "it isn't ",
        "That is ": "That's ",
        "that is ": "that's ",
        "It is ": "It's ",
        "it is ": "it's ",
        "There is ": "There's ",
        "there is ": "there's ",
        "cannot ": "can't ",
        "is not ": "isn't ",
        "does not ": "doesn't ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _expand_spoken_beats(beats: list[dict]) -> list[dict]:
    """Split long written sections into natural 35–80 word spoken/visual beats."""
    expanded: list[dict] = []
    for beat in beats:
        sentences = re.split(r"(?<=[.!?])\s+", _naturalize(beat["narration"]).strip())
        groups: list[list[str]] = []
        current: list[str] = []
        count = 0
        for sentence in sentences:
            sentence_words = len(sentence.split())
            if current and count + sentence_words > 78:
                groups.append(current)
                current = []
                count = 0
            current.append(sentence)
            count += sentence_words
        if current:
            groups.append(current)
        if (
            len(groups) > 1
            and len(" ".join(groups[-1]).split()) < 28
            and len(" ".join(groups[-2] + groups[-1]).split()) <= 80
        ):
            groups[-2].extend(groups.pop())
        for index, group in enumerate(groups):
            item = dict(beat)
            item["id"] = f"{beat['id']}{chr(97 + index)}"
            item["narration"] = " ".join(group)
            expanded.append(item)
    return expanded


BEATS = _expand_spoken_beats(BEATS)


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> Path:
    if destination.is_file() and destination.stat().st_size > 1024:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    handle.write(chunk)
    return destination


def _prepare_official_assets() -> tuple[dict[str, str], list[dict]]:
    media_dir = RUN_DIR / "official_media"
    public_media = PUBLIC_DIR / "media"
    public_media.mkdir(parents=True, exist_ok=True)
    packaged: dict[str, str] = {}
    rights: list[dict] = []
    for asset_id, relative in OFFICIAL_ASSETS.items():
        url = f"https://huggingface.co/MiniMaxAI/MiniMax-H3/resolve/main/{relative}?download=true"
        extension = Path(relative).suffix
        local = _download(url, media_dir / f"{asset_id}{extension}")
        destination = public_media / local.name
        shutil.copy2(local, destination)
        packaged[asset_id] = f"episode/h3-10m/media/{destination.name}"
        rights.append({
            "asset_id": asset_id,
            "source_url": url,
            "source_page": "https://huggingface.co/MiniMaxAI/MiniMax-H3",
            "owner": "MiniMaxAI",
            "license": "MiniMax H3 Community License Agreement",
            "use": "official model-output example or diagram; muted editorial excerpt",
            "sha256": _sha256(local),
        })
    return packaged, rights


def _package_source_captures() -> dict[str, dict[str, str]]:
    manifest_path = RUN_DIR / "source_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"run scripts/capture_h3_10m_sources.py first: {manifest_path}")
    captures_dir = PUBLIC_DIR / "sources"
    captures_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, dict[str, str]] = {}
    for source in json.loads(manifest_path.read_text(encoding="utf-8")):
        item: dict[str, str] = {}
        for key, candidates in (("viewport", source["screenshots"]), ("screen_recording", source["recordings"])):
            # Hugging Face currently injects a model-provider popover into this
            # viewport. The official H3 media is cleaner evidence, so never
            # package a capture with that obstruction into the edit.
            if source["id"] == "minimax_model" and key == "viewport":
                continue
            if not candidates:
                continue
            origin = PROJECT_ROOT / candidates[0]
            if not origin.is_file():
                continue
            destination = captures_dir / origin.name
            shutil.copy2(origin, destination)
            item[key] = f"episode/h3-10m/sources/{destination.name}"
        result[source["id"]] = item
    return result


def _silence(destination: Path, seconds: float) -> Path:
    _run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{seconds:.3f}", "-c:a", "pcm_s24le", str(destination)])
    return destination


def _concat(files: list[Path], destination: Path) -> Path:
    command = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    for path in files:
        command.extend(["-i", str(path)])
    inputs = "".join(f"[{index}:a]" for index in range(len(files)))
    command.extend(["-filter_complex", f"{inputs}concat=n={len(files)}:v=0:a=1[out]", "-map", "[out]", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(destination)])
    _run(command)
    return destination


def _make_narration(script: str) -> tuple[Path, int, list[captions.TimedWord], dict]:
    final = RUN_DIR / "narration.wav"
    audio_dir = RUN_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    chunks = split_text(script)
    sample = PROJECT_ROOT / VOICE_SAMPLE
    mastered: list[Path] = []
    missing = []
    for index, chunk in enumerate(chunks):
        key = hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:12]
        raw = audio_dir / f"chunk_{index:02d}_{key}_raw.mp3"
        wave = audio_dir / f"chunk_{index:02d}_{key}.wav"
        mastered.append(wave)
        if not wave.is_file():
            missing.append((index, chunk, raw, wave))
    uploaded = magichour.upload_file(str(sample), "audio") if missing else None
    credits = 0
    for index, chunk, raw, wave in missing:
        if not raw.is_file():
            project_id = magichour.voice_clone(chunk, uploaded, f"{EPISODE_ID}-{VOICE_PROFILE_ID}-{index}")
            job = magichour.wait_audio(project_id)
            credits += int(job.get("credits_charged", 0) or 0)
            magichour.download(job, raw)
        audio_qc.master_narration(raw, wave)
    gap = _silence(audio_dir / "gap.wav", 0.28)
    parts: list[Path] = []
    for index, wave in enumerate(mastered):
        parts.append(wave)
        if index < len(mastered) - 1:
            parts.append(gap)
    joined = _concat(parts, audio_dir / "joined.wav")
    joined_seconds = duration(joined)
    if joined_seconds > TARGET_SECONDS - 1.0:
        rate = joined_seconds / (TARGET_SECONDS - 1.5)
        if rate > 1.10:
            raise RuntimeError(f"narration is too long for ten minutes: {joined_seconds:.2f}s")
        adjusted = audio_dir / "joined_adjusted.wav"
        _run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(joined), "-af", f"atempo={rate:.6f}", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(adjusted)])
        joined = adjusted
        joined_seconds = duration(joined)
    elif joined_seconds < TARGET_SECONDS - 2.0:
        rate = joined_seconds / (TARGET_SECONDS - 1.5)
        if rate < 0.88:
            raise RuntimeError(
                f"narration is too short for a natural ten-minute delivery: {joined_seconds:.2f}s"
            )
        adjusted = audio_dir / "joined_adjusted.wav"
        _run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(joined), "-af", f"atempo={rate:.6f}", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(adjusted)])
        joined = adjusted
        joined_seconds = duration(joined)
    tail = _silence(audio_dir / "tail.wav", max(0.5, TARGET_SECONDS - joined_seconds))
    padded = _concat([joined, tail], audio_dir / "padded.wav")
    audio_qc.master_narration(padded, final)
    if duration(final) > TARGET_SECONDS + 0.02:
        trimmed = RUN_DIR / "narration_trimmed.wav"
        _run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(final), "-t", str(TARGET_SECONDS), "-c:a", "pcm_s24le", str(trimmed)])
        trimmed.replace(final)
    recognized = captions.transcribe_words(final)
    recognized_text = " ".join(word.text for word in recognized)
    review = audio_qc.review_narration(final, script, sample, recognized_text=recognized_text, enforce_pacing=False, max_unmatched_words=24, min_intelligibility=0.87)
    (RUN_DIR / "audio_qc.json").write_text(json.dumps(review, indent=2), encoding="utf-8")
    if not review["passed"]:
        raise RuntimeError(f"final narration failed: {review['failures']}")
    return final, credits, recognized, review


def _apply_timings(script: str, recognized: list[captions.TimedWord]) -> list[dict]:
    aligned = captions.align_script_words(script, recognized)
    caption_data = [{"text": word.text, "startMs": round(word.start * 1000), "endMs": round(word.end * 1000), "timestampMs": round(word.start * 1000), "confidence": None} for word in aligned]
    offset = 0
    for beat in BEATS:
        count = len(beat["narration"].split())
        if caption_data:
            beat["startMs"] = caption_data[min(offset, len(caption_data) - 1)]["startMs"]
            beat["endMs"] = caption_data[min(offset + count - 1, len(caption_data) - 1)]["endMs"]
        else:
            beat["startMs"] = round(offset / max(1, len(script.split())) * TARGET_SECONDS * 1000)
            beat["endMs"] = round((offset + count) / max(1, len(script.split())) * TARGET_SECONDS * 1000)
        beat["wordCount"] = count
        beat["claim_ids"] = [f"claim_{beat['id']}_{index+1}" for index, _ in enumerate(beat["source_ids"])]
        offset += count
    return caption_data


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    script = "\n\n".join(beat["narration"] for beat in BEATS)
    word_count = len(script.replace("—", " ").split())
    if not 1250 <= word_count <= 1750:
        raise RuntimeError(f"script word count outside ten-minute band: {word_count}")
    official_media, rights = _prepare_official_assets()
    source_assets = _package_source_captures()
    narration, credits, recognized, audio_review = _make_narration(script)
    captions_data = _apply_timings(script, recognized)
    shutil.copy2(narration, PUBLIC_DIR / "narration.wav")
    episode = {
        "episodeId": EPISODE_ID,
        "title": "AI Video Just Escaped the Cloud",
        "description": "MiniMax H3's open weights, native stereo audio, ComfyUI workflows, consumer-hardware tradeoffs, and the hosted pieces that remain.",
        "disclosure": "AI-assisted research and a consistent synthetic narrator. Visuals are official model examples, licensed source captures, and deterministic editorial graphics.",
        "durationSeconds": int(TARGET_SECONDS),
        "beats": BEATS,
        "sources": SOURCES,
        "assets": source_assets,
        "broll": official_media,
        "credits": credits,
    }
    (PUBLIC_DIR / "episode.json").write_text(json.dumps(episode, indent=2), encoding="utf-8")
    (PUBLIC_DIR / "captions.json").write_text(json.dumps(captions_data, indent=2), encoding="utf-8")
    (RUN_DIR / "episode.json").write_text(json.dumps(episode, indent=2), encoding="utf-8")
    (RUN_DIR / "script.txt").write_text(script, encoding="utf-8")
    (RUN_DIR / "rights_ledger.json").write_text(json.dumps(rights, indent=2), encoding="utf-8")
    print(json.dumps({"episode_id": EPISODE_ID, "words": word_count, "duration": duration(narration), "credits": credits, "audio_qc": audio_review, "public_dir": str(PUBLIC_DIR)}, indent=2))


if __name__ == "__main__":
    main()
