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


OUT = ROOT / "output" / "claude_chips_8m"
PUBLIC = ROOT / "remotion" / "public" / "episode" / "claude-chips"
FFMPEG = ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"
TARGET_SECONDS = 480.0


SECTIONS = [
    {
        "id": "cold_open",
        "title": "CLAUDE GOT A HARDWARE JOB",
        "kicker": "THE CLAIM, WITHOUT THE HYPE",
        "narration": """Claude Code just got a job where “works on my machine” is not a punchline. It can become a very expensive production run. Anthropic and engineering company UST say they are bringing Claude into the process used to test computer chips before those products ship. That sounds like Claude has put on a clean-room suit and is poking a wafer with tiny robot fingers. It has not. Claude is being added to the software-heavy validation loop around the hardware: reading schematics and pinouts, writing tests, running regression checks, and helping engineers notice when real equipment behaves differently from its digital model. The interesting story is not “chatbot builds chip.” It is that an AI coding agent is moving into one of engineering’s least glamorous and most important jobs: proving a design actually works. Let’s unpack what Claude is testing, what UST says is already faster, and the giant asterisk nobody should skip.""",
        "evidence": ["E1", "E2"],
    },
    {
        "id": "validation_101",
        "title": "VALIDATION IS THE BOUNCER",
        "kicker": "NO TEST, NO SHIP",
        "narration": """First, what does chip validation even mean? A chip starts as diagrams, specifications, interfaces, timing rules, and a heroic number of tiny details. Validation asks whether the real device behaves the way that plan says it should. Engineers feed it inputs, measure outputs, push edge cases, change firmware, rerun old tests, and investigate whatever breaks. Think of it as a nightclub bouncer for hardware. The design can look confident and know someone at the door. Validation still checks the ID. A regression test asks: after we changed one thing, did we accidentally break three things that worked yesterday? Engineers often write these tests by hand, run them, inspect logs, and repeat. The work is specialized, repetitive, and full of context. You need the schematic, the pinout mapping signals to physical connections, the expected behavior, and previous failures. That is why a coding agent is tempting. Much of the loop is code and text, but the consequences eventually become physical.""",
        "evidence": ["E2", "E6"],
    },
    {
        "id": "what_claude_does",
        "title": "READ → TEST → RUN → COMPARE",
        "kicker": "THE ACTUAL WORKFLOW",
        "narration": """According to Anthropic’s case study, Claude Code can read schematics and pinouts, then write and run tests against the design. It can hold context across a longer task instead of treating every prompt like a new conversation. Inside UST’s iDEC platform, the loop is: read the design, generate a test, run the regression, collect equipment data, compare it with a digital twin, and flag suspicious differences. A digital twin is a software model of how the physical system should behave. If the equipment says one thing and the twin says another, someone investigates. Claude is being integrated as a reasoning layer connecting the documents, test code, and results. That can remove copy-paste work, but it changes the failure mode. A beautifully written AI test that checks the wrong assumption is dangerous because it looks competent. The test generator needs tests too. Welcome to engineering, where every solution earns its own checklist.""",
        "evidence": ["E2", "E3"],
    },
    {
        "id": "speed_claim",
        "title": "4 DAYS → 48 HOURS",
        "kicker": "UST-REPORTED RESULT",
        "narration": """Now for the number that made this announcement travel. UST reports that iDEC’s existing closed-loop pipeline reduced validation cycle times by fifty to seventy percent, turning a standard four-day turnaround into forty-eight hours. Read that carefully. This is UST reporting results from its platform; it is not an independent benchmark proving Claude alone produced a seventy-percent speedup. The case study says Claude is now being integrated as the reasoning layer. So the honest headline is not “Claude makes chips seventy percent faster.” UST already automated much of its validation loop, and now wants Claude to reduce hand scripting and catch faults earlier. That is still meaningful. If the agent drafts the boring part of a test, carries context between steps, or turns a messy result into a first-pass diagnosis, engineers can focus on what should be tested and why. Saving two days in a loop that repeats across a program matters. Keep the attribution attached to the number.""",
        "evidence": ["E2", "E4"],
    },
    {
        "id": "why_now",
        "title": "WHY AN AGENT FITS THIS JOB",
        "kicker": "CONTEXT IS THE PRODUCT",
        "narration": """Why now? Because this job is not one autocomplete. It is a chain. Open design files. Understand the interface. Find the test framework. Write the test. Run it. Read the error. Change something. Run it again. A useful agent must survive that chain without forgetting why it started. Claude Code was built around inspecting projects, editing files, executing commands, and reacting to results. UST is applying that pattern where software touches hardware. The boring superpower is continuity. Nobody wants to explain the same pin definition fourteen times while a test rig waits. UST also wants the agent inside systems engineers already use, not another shiny dashboard everyone avoids after launch week. Anthropic says UST plans to train twenty thousand engineers, architects, and consultants on Claude. That scale says this is not framed as a cute lab demo. It is an attempt to make the model part of a repeatable process.""",
        "evidence": ["E1", "E2", "E5"],
    },
    {
        "id": "failure_modes",
        "title": "THE VERIFIER CAN BE WRONG",
        "kicker": "WHERE THIS BREAKS",
        "narration": """Here is the giant asterisk. Language models optimize for plausible continuations, not electrical truth. Claude can misunderstand a schematic, invent an API, miss an edge case, or write a test that passes while proving almost nothing. In software, a hallucination might give you a broken button. In chip validation, it can give accounting a personality. There is also automation bias. Clean, fast output formatted like a real artifact earns too much trust. The defense is specific controls, not a poster saying “keep a human in the loop.” Engineers define intent and coverage. Generated code gets reviewed. Important results are reproduced. Changes are logged. Draft suggestions stay separate from approved actions. Sensitive designs remain inside the right boundaries. Teams measure false negatives, not just scripts produced before lunch. Anthropic emphasizes human approvals in other high-stakes UST workflows, and the announcement mentions safe, secure deployment. Those controls are not bureaucracy attached to the product. Here, they are part of the product.""",
        "evidence": ["E2", "E7"],
    },
    {
        "id": "physical_ai",
        "title": "PHYSICAL AI IS BIGGER THAN ROBOTS",
        "kicker": "SOFTWARE MEETS THE FACTORY",
        "narration": """The phrase “physical AI” is doing a lot of work. It includes robots, but can also mean intelligence embedded in the equipment and processes used to make physical things. A model needs no arms to affect a factory. If it chooses a diagnostic step, compares sensor data, identifies a firmware regression, or prepares a validation test, it influences a physical system through the workflow. UST’s iDEC material describes sensor collection, digital twins, simulations, remote diagnostics, and predictive maintenance. Claude sits above that machinery as a reasoning interface, not underneath it as a motor controller. Earlier Anthropic robotics experiments showed how difficult end-to-end autonomy can be when a model must discover unfamiliar hardware. Here, UST provides a structured environment, existing tools, and human checkpoints. That is more believable than dropping a chatbot into a fab and asking it to figure things out. The near-term opportunity is less “robot scientist” and more “very fast junior collaborator with access to the test bench—and strict supervision.”""",
        "evidence": ["E1", "E3", "E8"],
    },
    {
        "id": "who_should_care",
        "title": "THE BORING LOOP IS THE BUSINESS",
        "kicker": "WHY THIS MATTERS",
        "narration": """Who should care? Chip companies, because mistakes get more expensive the later they are found. Hardware teams, because validation is often the schedule, not a final box. AI builders, because this tests whether agents create value outside a chat window. The durable deployments may be painfully specific. Not “do engineering,” but “read this pinout, generate this regression suite, compare measurements with this digital twin, then ask a human before anything consequential.” UST says nine of the top ten semiconductor companies rely on its silicon engineering work, and it has described previous automation cutting motherboard test and debugging cycles from four days to two. Those are company claims, but they explain the fit. UST already lives inside the workflow. Claude supplies a flexible language-and-code layer. That combination has a better chance than a generic assistant knocking on the factory door with a résumé and absolutely no safety shoes.""",
        "evidence": ["E4", "E6"],
    },
    {
        "id": "verdict",
        "title": "NOT A CHIP DESIGNER. STILL IMPORTANT.",
        "kicker": "THE USEFUL VERDICT",
        "narration": """My verdict: Claude is not independently designing and testing a chip. It is being wired into UST’s validation system to help engineers write tests, carry context, compare results, and investigate faults. The speed gains belong to the broader iDEC pipeline; Claude’s additional impact still needs clear measurement. That sounds less dramatic than the viral version, but it is more useful. AI adoption becomes real in the ugly middle between a clever demo and a product that can safely ship. Chip validation is almost entirely ugly middle. If Claude reduces repetitive scripting without reducing skepticism, this is a strong example of agents moving from conversation into production engineering. If fluent output substitutes for coverage and evidence, teams will automate confidence instead of quality. The big question is not whether Claude can write a test. It is whether the system proves the right things were tested, preserves an audit trail, and helps a human make a better decision. That is how an AI assistant earns a badge in the fab: not by sounding smart, but by making fewer expensive surprises.""",
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
        project_id = magichour.voice_clone(chunk, uploaded, f"claude-chips-s{section_index:02d}-c{chunk_index:02d}")
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
        "episodeId": "claude-tests-computer-chips-private-canary-v1",
        "title": "Claude Is Testing Computer Chips — Here’s What That Actually Means",
        "durationSeconds": TARGET_SECONDS,
        "privateDraft": True,
        "subtitles": False,
        "narrator": "channel_narrator_approved_english_v1",
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
    captures = [] if args.skip_capture else capture_pages()
    narration, durations, metrics = generate_narration(force=args.force_voice)
    episode_path = package(durations, metrics, captures)
    words = sum(len(re.findall(r"\b[\w’'-]+\b", section["narration"])) for section in SECTIONS)
    print(json.dumps({"episode": str(episode_path), "narration": str(narration), "words": words, "metrics": metrics, "captures": captures}, indent=2))


if __name__ == "__main__":
    main()
