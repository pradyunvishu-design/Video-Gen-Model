from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import magichour  # noqa: E402
from pipeline.config import VOICE_SAMPLE  # noqa: E402


OUT = ROOT / "output" / "claude_chips_8m_v2"
PUBLIC = ROOT / "remotion" / "public" / "episode" / "claude-chips-v2"
FFMPEG = ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"
TARGET_SECONDS = 480.0


SECTIONS = [
    {
        "id": "cold_open",
        "title": "CLAUDE IS MOVING INTO CHIP TESTING",
        "kicker": "WHAT THE ANNOUNCEMENT ACTUALLY SAYS",
        "narration": """Claude is moving into computer-chip testing. Not designing a processor from scratch, and not operating a factory by itself. Anthropic and engineering company UST are adding Claude to the software-heavy work around real hardware. It can read design documents, prepare tests, run checks, and help engineers compare expected behavior with equipment results. That distinction matters, because the viral version of this story is easy to overstate. The useful version is more specific. Chip validation involves a large amount of code, documentation, log analysis, and repetition. Those are exactly the conditions where an agent can save time, as long as a human still decides what counts as proof. So let’s look at what validation is, where Claude fits, and which speed claim belongs to UST’s existing platform. Then we can judge why this matters, even if the AI never touches a silicon wafer.""",
        "evidence": ["E1", "E2"],
    },
    {
        "id": "validation_101",
        "title": "WHAT CHIP VALIDATION MEANS",
        "kicker": "THE WORK BETWEEN A DESIGN AND A PRODUCT",
        "narration": """Before a chip becomes part of a product, engineers have to prove that the real device behaves like the design says it should. They feed it inputs, measure outputs, change firmware, push unusual edge cases, and rerun old tests after every meaningful change. That last part is regression testing: make one improvement, then check that it did not quietly break something that worked yesterday. Most of this job looks less like science fiction and more like opening the same logs for the fifteenth time. But the details are specialized. An engineer needs the schematic, the pinout that maps signals to physical connections, the expected timing, the test framework, and a history of earlier failures. A single passing test is not enough; the test also has to cover the right behavior. This is why an agent is appealing. Much of the work is expressed through code and text, while the result is measured on physical equipment.""",
        "evidence": ["E2", "E6"],
    },
    {
        "id": "what_claude_does",
        "title": "WHERE CLAUDE FITS",
        "kicker": "READ, TEST, RUN, COMPARE",
        "narration": """Anthropic’s case study says Claude Code can read schematics and pinouts, then help write and run tests. Inside UST’s iDEC platform, that sits inside a longer loop. The system reads the design, prepares a test, runs the regression, collects equipment data, and compares the result with a digital twin. A digital twin is a software model of how the physical system should behave. If the measured result and the model disagree, the difference becomes an investigation. Claude is being added as a reasoning layer across those documents, scripts, and results. In practical terms, it might draft a test from a requirement, revise the code after an error, or summarize why a measurement looks unusual. That can reduce handoffs and copy-paste work. It does not remove the need for engineering judgment, because a polished test can still check the wrong assumption. Fast and wrong is still wrong; it just arrives earlier.""",
        "evidence": ["E2", "E3"],
    },
    {
        "id": "speed_claim",
        "title": "THE FOUR-DAYS-TO-FORTY-EIGHT-HOURS CLAIM",
        "kicker": "KEEP THE ATTRIBUTION ATTACHED",
        "narration": """The number getting the most attention is a reported fifty-to-seventy-percent reduction in validation cycle time, including a standard turnaround moving from four days to forty-eight hours. That figure comes from UST and describes its iDEC closed-loop pipeline. It is not an independent benchmark showing that Claude alone created the entire speedup. The case study says Claude is now being integrated into that established process as the reasoning layer. The accurate interpretation is that UST had already automated parts of the validation loop, and it now expects Claude to reduce manual scripting and help identify problems earlier. That is still valuable. A two-day saving can matter when the same cycle repeats across a hardware program and blocks other teams. But good reporting keeps the boundary clear: the measured result belongs to UST’s broader platform, while Claude’s additional contribution still needs its own evidence over time.""",
        "evidence": ["E2", "E4"],
    },
    {
        "id": "why_now",
        "title": "WHY AN AGENT FITS THIS WORK",
        "kicker": "THE TASK IS A CHAIN, NOT A PROMPT",
        "narration": """This job is a better match for an agent than for simple autocomplete because it unfolds as a chain. Open the design files. Understand the interface. Find the test framework. Write a test. Run it. Read the error. Change the code. Run it again. The value comes from carrying the original goal through every step. Claude Code is designed to inspect projects, edit files, execute commands, and react to the output. UST is applying that pattern where software meets hardware. The quiet advantage is continuity: the engineer should not have to re-explain the same signal mapping every time the workflow advances. UST also wants Claude inside tools and processes its teams already use. Anthropic says the company plans to train twenty thousand engineers, architects, and consultants on Claude. That does not prove the deployment will succeed, but it shows this is being treated as an operating change rather than a one-off demonstration.""",
        "evidence": ["E1", "E2", "E5"],
    },
    {
        "id": "failure_modes",
        "title": "THE TEST WRITER CAN ALSO BE WRONG",
        "kicker": "WHAT A SAFE WORKFLOW HAS TO CATCH",
        "narration": """The hard part is that a language model is built to produce plausible output, not electrical truth. Claude can misunderstand a schematic, invent a function, miss an edge case, or generate a test that passes while proving very little. Clean formatting makes that problem easier to trust, not easier to detect. A useful safety process therefore has to be concrete. Engineers define the intent and required coverage. Generated code is reviewed. Important results are reproduced. Every change and approval is logged. Draft suggestions remain separate from actions that can affect equipment or a release decision. Sensitive designs stay inside the correct security boundary. Teams should measure missed failures and false confidence, not just how many scripts the agent produced. Anthropic’s UST material emphasizes human approvals in other high-stakes workflows and describes secure deployment. In this setting, those controls are not paperwork around the product. They are part of whether the product works at all.""",
        "evidence": ["E2", "E7"],
    },
    {
        "id": "physical_ai",
        "title": "PHYSICAL AI WITHOUT A HUMANOID ROBOT",
        "kicker": "SOFTWARE CAN STILL CHANGE A FACTORY WORKFLOW",
        "narration": """The announcement uses the phrase physical AI, which is broader than robots walking around a factory. A model can affect a physical process by choosing a diagnostic step, preparing a validation test, comparing sensor data, or identifying a firmware regression. UST’s iDEC material describes sensor collection, simulation, digital twins, remote diagnostics, and predictive maintenance. Claude sits above that machinery as a reasoning interface. It is not the motor controller and it is not being handed unrestricted control of the test floor. That structure is important. Earlier robotics experiments from Anthropic showed how difficult open-ended autonomy becomes when a model has to discover unfamiliar hardware on its own. Here, UST supplies the tools, the data flow, the defined task, and the human checkpoints. The near-term opportunity is not a robot scientist. It is a capable software assistant working inside a carefully bounded engineering system.""",
        "evidence": ["E1", "E3", "E8"],
    },
    {
        "id": "who_should_care",
        "title": "WHY THIS MATTERS BEYOND ONE CHIP TEAM",
        "kicker": "SPECIFIC WORKFLOWS BEAT GENERIC PROMISES",
        "narration": """Chip companies should care because failures become more expensive the later they are found. Hardware teams should care because validation often determines the schedule. And AI builders should care because this is a serious test of whether agents create value outside a chat window. The durable use case is extremely specific. Read this pinout, generate this regression test, compare these measurements with a digital twin, then ask a qualified human before anything consequential happens. UST says nine of the top ten semiconductor companies rely on its silicon-engineering work. The company has also described automation reducing motherboard test and debugging cycles from four days to two. Those are company-reported claims, but they explain why this partnership is plausible. UST already understands the workflow and the equipment. Claude supplies a flexible language-and-code layer. The combination is more credible than dropping a general assistant into a lab and hoping it learns the job on the way in.""",
        "evidence": ["E4", "E6"],
    },
    {
        "id": "verdict",
        "title": "THE HONEST TAKEAWAY",
        "kicker": "IMPORTANT, BUT NOT THE VIRAL VERSION",
        "narration": """Here is the clean conclusion. Claude is not independently designing and validating a computer chip. It is being integrated into UST’s existing validation system to help engineers prepare tests, maintain context, compare results, and investigate faults. The reported speed gains belong to the broader iDEC pipeline, and Claude’s incremental impact still needs clear measurement. That is less dramatic than saying an AI now builds chips, but it may be more important. Real adoption usually happens in the long middle between a clever demo and a product that can safely ship. Validation is almost entirely that middle. If Claude reduces repetitive scripting while preserving review, evidence, and skepticism, this is a strong example of agents moving into production engineering. If fluent output replaces coverage and proof, the team will automate confidence instead of quality. The decisive question is not whether Claude can write a test. It is whether the whole system can show that the right things were tested, preserve an audit trail, and help a human make a better decision.""",
        "evidence": ["E2", "E3", "E7"],
    },
]


SOURCES = [
    {"id": "E1", "publisher": "Anthropic", "title": "UST is bringing Claude to physical AI", "url": "https://www.anthropic.com/news/ust-claude", "date": "2026-07-09", "type": "primary announcement"},
    {"id": "E2", "publisher": "Anthropic / UST", "title": "How UST is putting Claude into production processes", "url": "https://www.anthropic.com/news/ust-claude", "date": "2026-07-09", "type": "primary case study"},
    {"id": "E3", "publisher": "UST", "title": "UST iDEC digital twin platform", "url": "https://www.ust.com/en/ust-idec", "type": "official product page"},
    {"id": "E4", "publisher": "UST", "title": "Silicon engineering and validation services", "url": "https://www.ust.com/en/silicon-engineering", "type": "official company page"},
    {"id": "E5", "publisher": "Anthropic", "title": "Introducing Claude Code", "url": "https://www.youtube.com/watch?v=AJpK3YTTKZ4", "type": "official product demo; referenced, not downloaded"},
    {"id": "E6", "publisher": "Intel Newsroom", "title": "Global Manufacturing press kit", "url": "https://newsroom.intel.com/press-kit/global-manufacturing", "type": "official press kit"},
    {"id": "E7", "publisher": "Anthropic", "title": "Human approval controls described in UST workflows", "url": "https://www.anthropic.com/news/ust-claude", "date": "2026-07-09", "type": "primary announcement"},
    {"id": "E8", "publisher": "Anthropic", "title": "Project Fetch phase two", "url": "https://www.anthropic.com/news/project-fetch-phase-two", "type": "official research note"},
]


CAPTURES = [
    ("anthropic_story.png", "https://www.anthropic.com/news/ust-claude", "UST is bringing Claude to physical AI"),
    ("anthropic_speed_claim.png", "https://www.anthropic.com/news/ust-claude", "50 to 70%"),
    ("ust_idec.png", "https://www.ust.com/en/ust-idec", "digital twin"),
    ("ust_silicon.png", "https://www.ust.com/en/silicon-engineering", "Silicon Engineering"),
    ("intel_presskit.png", "https://newsroom.intel.com/press-kit/global-manufacturing", "B-roll Video"),
]


def run(args: list[str]) -> None:
    subprocess.run([str(a) for a in args], check=True)


def duration(path: Path) -> float:
    value = subprocess.check_output([
        str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], text=True).strip()
    return float(value)


def split_text(text: str, limit: int = 930) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text.strip()))
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = sentence
    if current:
        chunks.append(current)
    if any(len(chunk) > 1000 for chunk in chunks):
        raise ValueError("A narration chunk exceeds Magic Hour's 1000 character cap")
    return chunks


def concat_audio(inputs: list[Path], output: Path) -> None:
    listing = output.with_suffix(".concat.txt")
    listing.write_text("".join(f"file '{p.resolve().as_posix().replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n" for p in inputs), encoding="utf-8")
    run([str(FFMPEG), "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(output)])


def capture_pages() -> list[dict]:
    capture_dir = OUT / "captures"
    capture_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
            for filename, url, needle in CAPTURES:
                target = capture_dir / filename
                page = context.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(2500)
                    for label in ("Accept", "Accept all", "Allow all", "I agree"):
                        button = page.get_by_role("button", name=re.compile(label, re.I))
                        if button.count():
                            try:
                                button.first.click(timeout=1200)
                            except Exception:
                                pass
                    page.add_style_tag(content="""
                        dialog,[role=dialog],.modal,.popup,.newsletter,.cookie-banner,
                        [class*=cookie],[class*=subscribe],[id*=cookie],[id*=subscribe]{display:none!important}
                        html{scroll-behavior:auto!important} *{animation:none!important;transition:none!important}
                    """)
                    match = page.get_by_text(re.compile(re.escape(needle), re.I)).first
                    if match.count():
                        try:
                            match.scroll_into_view_if_needed(timeout=4000)
                            page.evaluate("window.scrollBy(0,-170)")
                            page.wait_for_timeout(500)
                        except Exception:
                            pass
                    page.screenshot(path=str(target), full_page=False)
                    records.append({"file": filename, "url": url, "status": "captured"})
                except Exception as exc:
                    records.append({"file": filename, "url": url, "status": "failed", "error": str(exc)[:240]})
                finally:
                    page.close()
            browser.close()
    except Exception as exc:
        records.append({"status": "capture_runtime_failed", "error": str(exc)[:300]})
    return records


def generate_narration(force: bool = False) -> tuple[Path, list[float], dict]:
    audio_dir = OUT / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    sample = Path(VOICE_SAMPLE)
    if not sample.is_absolute():
        sample = ROOT / sample
    if not sample.exists():
        fallback = ROOT / "assets" / "voices" / "channel_narrator_approved_english_clean.wav"
        sample = fallback
    if not sample.exists():
        raise FileNotFoundError("Approved English narrator sample is missing")

    uploaded = magichour.upload_file(str(sample), "audio")
    tasks: list[tuple[int, int, str, Path]] = []
    for section_index, section in enumerate(SECTIONS):
        for chunk_index, chunk in enumerate(split_text(section["narration"])):
            destination = audio_dir / f"s{section_index:02d}_c{chunk_index:02d}.mp3"
            if force or not destination.exists():
                tasks.append((section_index, chunk_index, chunk, destination))

    def make(task: tuple[int, int, str, Path]) -> tuple[Path, int]:
        section_index, chunk_index, chunk, destination = task
        project_id = magichour.voice_clone(chunk, uploaded, f"claude-chips-v2-s{section_index:02d}-c{chunk_index:02d}")
        job = magichour.wait_audio(project_id)
        magichour.download(job, destination)
        return destination, int(job.get("credits_charged", 0))

    credits = 0
    if tasks:
        with ThreadPoolExecutor(max_workers=min(3, len(tasks))) as pool:
            futures = [pool.submit(make, task) for task in tasks]
            for future in as_completed(futures):
                _, charged = future.result()
                credits += charged

    section_wavs: list[Path] = []
    raw_section_durations: list[float] = []
    for section_index, section in enumerate(SECTIONS):
        chunk_paths = [audio_dir / f"s{section_index:02d}_c{index:02d}.mp3" for index, _ in enumerate(split_text(section["narration"]))]
        section_wav = audio_dir / f"section_{section_index:02d}.wav"
        concat_audio(chunk_paths, section_wav)
        section_wavs.append(section_wav)
        raw_section_durations.append(duration(section_wav))

    raw = audio_dir / "narration_raw.wav"
    concat_audio(section_wavs, raw)
    raw_seconds = duration(raw)
    spoken_target = 477.0
    tempo = raw_seconds / spoken_target
    if not 0.82 <= tempo <= 1.18:
        raise RuntimeError(f"Narration is {raw_seconds:.1f}s; script needs revision before safe tempo correction")
    mastered = PUBLIC / "narration.wav"
    mastered.parent.mkdir(parents=True, exist_ok=True)
    run([
        str(FFMPEG), "-y", "-i", str(raw), "-af",
        f"atempo={tempo:.8f},loudnorm=I=-16:TP=-1.5:LRA=7,apad=pad_dur=3",
        "-t", str(TARGET_SECONDS), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(mastered),
    ])
    adjusted = [value / tempo for value in raw_section_durations]
    return mastered, adjusted, {"credits_charged_this_run": credits, "raw_seconds": raw_seconds, "tempo": tempo, "final_seconds": duration(mastered)}


def package(section_durations: list[float], narration_metrics: dict, captures: list[dict]) -> Path:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    source_dir = OUT / "sources"
    for filename in ("intel_packaging_broll.mp4", "intel_vision_broll.mp4"):
        source = source_dir / filename
        if not source.exists():
            raise FileNotFoundError(f"Required official press B-roll is missing: {source}")
        shutil.copy2(source, PUBLIC / filename)
    for record in captures:
        source = OUT / "captures" / str(record.get("file", ""))
        if source.is_file():
            shutil.copy2(source, PUBLIC / source.name)

    timeline = []
    cursor = 0.0
    scale = 477.0 / max(1.0, sum(section_durations))
    for index, (section, measured) in enumerate(zip(SECTIONS, section_durations)):
        length = measured * scale
        if index == len(SECTIONS) - 1:
            length = 477.0 - cursor
        timeline.append({**section, "start": round(cursor, 3), "duration": round(length, 3)})
        cursor += length

    episode = {
        "episodeId": "claude-tests-computer-chips-private-cut-v2",
        "title": "Claude Is Testing Computer Chips — Here’s What That Actually Means",
        "durationSeconds": TARGET_SECONDS,
        "privateDraft": True,
        "subtitles": False,
        "narrator": "channel_narrator_approved_english_v1_single_voice",
        "chapters": timeline,
        "sources": SOURCES,
        "captures": captures,
        "media": [
            {"file": "intel_packaging_broll.mp4", "publisher": "Intel Newsroom", "label": "SOURCE · INTEL NEWSROOM", "rights": "Intel Newsroom downloadable B-roll; credit required", "url": "https://newsroom.intel.com/press-kit/global-manufacturing"},
            {"file": "intel_vision_broll.mp4", "publisher": "Intel Newsroom", "label": "SOURCE · INTEL NEWSROOM", "rights": "Intel Newsroom downloadable B-roll; credit required", "url": "https://newsroom.intel.com/press-kit/intel-vision-2024"},
        ],
        "narrationMetrics": narration_metrics,
    }
    episode_path = PUBLIC / "episode.json"
    episode_path.write_text(json.dumps(episode, indent=2), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "episode_project.json").write_text(json.dumps(episode, indent=2), encoding="utf-8")
    (OUT / "rights_ledger.json").write_text(json.dumps({"sources": SOURCES, "media": episode["media"], "captures": captures}, indent=2), encoding="utf-8")
    script_lines = [f"# {episode['title']}", "", "Private quality canary. No subtitles.", ""]
    for section in SECTIONS:
        script_lines.extend([f"## {section['title']}", "", section["narration"], "", f"Evidence: {', '.join(section['evidence'])}", ""])
    (OUT / "script.md").write_text("\n".join(script_lines), encoding="utf-8")
    return episode_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-voice", action="store_true")
    parser.add_argument("--skip-capture", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.skip_capture:
        capture_dir = OUT / "captures"
        captures = [
            {"file": filename, "url": url, "status": "captured", "reused": True}
            for filename, url, _ in CAPTURES
            if (capture_dir / filename).is_file()
        ]
    else:
        captures = capture_pages()
    narration, durations, metrics = generate_narration(force=args.force_voice)
    episode_path = package(durations, metrics, captures)
    words = sum(len(re.findall(r"\b[\w’'-]+\b", section["narration"])) for section in SECTIONS)
    print(json.dumps({"episode": str(episode_path), "narration": str(narration), "words": words, "metrics": metrics, "captures": captures}, indent=2))


if __name__ == "__main__":
    main()
