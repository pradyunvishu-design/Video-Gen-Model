"""Correct verifier-identified evidence mappings while preserving the episode argument."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.project_store import load_project, save_project
from pipeline.models import Claim


EPISODE_DIR = ROOT / "data" / "episodes" / "episode_20260901_03"


REPAIRS = {
    "b01": {
        "claims": ["c23", "c5", "c7", "c13", "c28"],
        "narration": (
            "ComfyUI says this is already live as one node with five jobs, including scene extension. The launch "
            "material talks about ten-second increments and scenes up to forty seconds. So what does the node actually "
            "prove, and what still comes straight from the launch posts? We'll keep those two things separate."
        ),
    },
    "b02": {
        "claims": ["c23"],
        "narration": (
            "The ComfyUI blog says the Gemini Video Omni node provides five tasks in one place: make a clip from "
            "text, from an image, from reference images, by editing, or by extending an existing shot."
        ),
    },
    "b03": {
        "claims": ["c2", "c20", "c21"],
        "narration": (
            "Google says Omni 1.1 is production-ready through the Gemini API in AI Studio. ComfyUI says the Flash "
            "version already ships in its Gemini Video Omni node."
        ),
    },
    "b05": {
        "claims": ["c29", "c22", "c25", "c30", "c32"],
        "narration": (
            "Most of the node is straightforward: choose the model, the task, and either sixteen by nine or nine by "
            "sixteen. The image and video inputs are optional. The next beat shows the exact reference-tag syntax "
            "from the ComfyUI writeup."
        ),
    },
    "b06": {
        "claims": ["c25", "c29", "c30"],
        "narration": (
            "The node accepts an image and a video alongside the prompt. Its task menu lists text-to-video, "
            "image-to-video, reference-to-video, edit, and extend. That gives you five routes in one place, but the "
            "source does not test how reliably each route follows its inputs. The exact reference tags stay on screen "
            "where they are easier to read than hear."
        ),
    },
    "b04": {
        "claims": ["c32"],
        "narration": (
            "ComfyUI's setup guide begins here: update ComfyUI, or use Comfy Cloud. Then find the Gemini Video Omni "
            "node in the Node Library or Templates panel."
        ),
    },
    "b07": {
        "claims": ["c5"],
        "narration": (
            "DeepMind's documented comparison is up to ten seconds of prior context for Omni 1.1 versus only the "
            "final second for earlier models."
        ),
    },
    "b08": {
        "claims": ["c5", "c7"],
        "purpose": "evidence",
        "visual_direction": (
            "Source explainer labeled 'Google DeepMind says': highlight the documented 10-second context window, "
            "then show four 10-second blocks reaching the stated 40-second cap. Never label this as our test."
        ),
        "narration": (
            "The model can inspect up to ten seconds of the existing clip before it continues. That's the input side. "
            "On the output side, video can be extended in ten-second increments, up to forty seconds total."
        ),
    },
    "b09": {
        "claims": ["c5", "c6", "c7"],
        "narration": (
            "DeepMind says the added context improves visual consistency and narrative adherence. This episode does "
            "not provide an independent measurement of how often that holds, so the reliability question stays open."
        ),
    },
    "b11": {
        "claims": ["c28"],
        "narration": (
            "Extension answers what happens next. Editing asks the harder question: can one change happen "
            "without breaking the rest of the shot? For editing, the thing to watch is simple: what stayed intact. "
            "That matters more than a flashy before-and-after."
        ),
    },
    "b12": {
        "claims": ["c28", "c30"],
        "purpose": "evidence",
        "visual_direction": (
            "Full-screen ComfyUI article capture positioned on the documented beach-edit example. Underline only "
            "the exact overcast-sky instruction and label it 'documented example,' never 'our test.'"
        ),
        "narration": (
            "Conversational editing just means you describe one change in normal language and the model tries to "
            "leave the rest of the shot alone. ComfyUI documents that behavior through its edit task. It doesn't tell us how often "
            "the result will hold up, so check whether only the requested part changed before adding another edit."
        ),
    },
    "b13": {
        "claims": ["c28", "c33"],
        "narration": (
            "The source says edits can stack because the model keeps context from the previous result. In plain "
            "English, a second instruction should build on the edited clip instead of resetting to the original. "
            "Check what changed before you stack another edit."
        ),
    },
    "b14": {
        "claims": ["c28"],
        "narration": (
            "When checking an edit by eye, watch water texture and faces first. This episode does not provide "
            "independent measurements. Be explicit about the single change you want, then check everything that "
            "was supposed to stay untouched before accepting the result."
        ),
    },
    "b15": {
        "claims": [],
        "narration": (
            "A sensible first pass is 360p. Use it to check framing, camera movement, and timing before spending more. "
            "If the basic shot doesn't work there, extra pixels just give you a sharper version of the wrong idea. "
            "Better to find that out on the cheap."
        ),
    },
    "b16": {
        "claims": ["c24", "c11", "c12", "c31"],
        "narration": (
            "ComfyUI's recommendation is straightforward: iterate at 720p, then rerun the keeper at 1080p or 4K. "
            "Google's launch post separately claims 360p can be faster and cheaper than 720p. That 360p figure is a "
            "performance claim, not the usage recommendation or an independent benchmark from this episode."
        ),
    },
    "b17": {"claims": ["c13"]},
    "b19": {"claims": ["c7", "c29"]},
    "b20": {
        "claims": ["c24"],
        "emphasis_words": ["generated audio"],
        "narration": (
            "The ComfyUI writeup says every clip includes generated audio. Check the visuals first, then listen to "
            "the generated track separately and decide whether it is worth "
            "keeping."
        ),
    },
    "b21": {
        "claims": ["c18", "c19"],
        "narration": (
            "Google DeepMind says Omni 1.1 is available to Google AI Plus, Pro, and Ultra subscribers globally in "
            "Google Flow, starting that day. It separately says scene extension is available to those tiers globally "
            "in the Gemini app."
        ),
    },
    "b22": {
        "claims": [],
        "narration": (
            "There's one more limit, and it isn't in the menu. Most of the impressive numbers still come from launch "
            "posts, not outside testing. So yes, you can plan around the documented workflow. You just shouldn't bet "
            "a client deadline on the performance claims until you've repeated the shot yourself."
        ),
    },
    "b23": {
        "claims": [],
        "narration": (
            "If you want one quick reliability check, rerun the exact same ten-second shot once more. Same prompt, "
            "same input, same resolution. Then look for drift in identity, camera path, and lighting. That won't tell "
            "you everything about the model, but it will show how much variance appears before you trust a real job to it. This is a "
            "suggested check, not a test result from this episode."
        ),
    },
    "b25": {
        "claims": [],
        "narration": (
            "If you open this tonight, spend money at the end. Start with a cheap draft, check the movement, and try "
            "the edit before paying for resolution. Treat the draft as the decision pass and higher "
            "resolution as the finishing pass. That keeps the order simple right now. If the motion fails at draft "
            "quality, extra pixels will only make the same failure sharper and more expensive. It's the fastest way "
            "to protect your budget."
        ),
    },
    "b26": {
        "claims": ["c11", "c12", "c34"],
        "narration": (
            "Here is one possible workflow, not a rule from the source: try 360p first and check the framing, camera "
            "move, and timing before spending more. The ComfyUI writeup also favors a detailed prompt: not a beach "
            "at sunset, but a wide empty beach at low golden sunset, slow "
            "dolly-in, warm side light, calm mood. Now the draft has one clear job: show whether the movement and "
            "composition match that brief."
        ),
    },
    "b24": {
        "claims": ["c6", "c7", "c28"],
        "narration": (
            "Remember the edit example, because it captures the whole split. The source says a plain-language change "
            "can be applied while the rest of the clip is left alone, but identity and lighting still have to hold up in the "
            "result. A forty-second extension works the same way: the option is documented; final-grade reliability "
            "still has to be tested before you trust it."
        ),
    },
    "b27": {
        "claims": ["c7", "c11", "c12", "c13", "c28"],
        "narration": (
            "A possible order is to try 360p first. If the motion or composition is wrong, stop there. Once the shot works, "
            "rerun the keeper at 1080p or 4K. For an edit, change one variable at a time. For a longer scene, keep "
            "the forty-second extension limit in view. That's the whole rule. Keep those three decisions separate, "
            "and you can see exactly where a bad result entered the process."
        ),
    },
    "b28": {
        "claims": [],
        "narration": (
            "So my read is not use it or skip it. The node makes five tasks convenient. Reliability is still "
            "shot-by-shot. Draft low, change one thing, watch identity, lighting, and continuity, then pay for 4K "
            "only after the shot works. Convenience is documented. Trust is earned shot by shot. Use it that way, "
            "and the node is useful now without pretending the launch post proved more than it did."
        ),
    },
}


def main() -> None:
    project = load_project(EPISODE_DIR)
    if not project.script:
        raise RuntimeError("episode script is missing")
    if not any(claim.id == "c33" for claim in project.claims):
        project.claims.append(Claim(
            id="c33",
            text=(
                "The ComfyUI Blog says edits can be stacked because the model retains context from the previous "
                "result, allowing a later edit to build on an earlier one without re-describing the scene."
            ),
            source_ids=["src_09022b345bc4"],
            kind="commentary",
        ))
    if not any(claim.id == "c34" for claim in project.claims):
        project.claims.append(Claim(
            id="c34",
            text=(
                "The ComfyUI Blog says detailed prompts that cover the scene, camera move, lighting, and mood "
                "outperform short prompts."
            ),
            source_ids=["src_09022b345bc4"],
            kind="commentary",
        ))
    beats = {beat.id: beat for beat in project.script.beats}
    for beat_id, repair in REPAIRS.items():
        beat = beats[beat_id]
        beat.claim_ids = list(repair["claims"])
        if repair.get("narration"):
            beat.narration = str(repair["narration"])
        if repair.get("purpose"):
            beat.purpose = str(repair["purpose"])
        if repair.get("visual_direction"):
            beat.visual_direction = str(repair["visual_direction"])
        if repair.get("emphasis_words") is not None:
            beat.delivery.emphasis_words = list(repair["emphasis_words"])
    contractions = (
        ("That is", "That's"), ("that is", "that's"),
        ("It is", "It's"), ("it is", "it's"),
        ("does not", "doesn't"), ("do not", "don't"),
        ("You are", "You're"), ("you are", "you're"),
        ("We are", "We're"), ("we are", "we're"),
        ("is not", "isn't"), ("are not", "aren't"),
        ("will not", "won't"), ("would not", "wouldn't"),
        ("cannot", "can't"),
    )
    for beat in project.script.beats:
        for before, after in contractions:
            beat.narration = beat.narration.replace(before, after)
        beat.narration = beat.narration.replace("It'sn't", "It isn't").replace("it'sn't", "it isn't")
    if project.script.narration.count("?") != 2:
        raise RuntimeError("evidence repair changed the locked question count")
    for stage in ("script", "narration", "captions", "render"):
        project.episode.setdefault("stage_hashes", {}).pop(stage, None)
    project.qc.pop("fact_check", None)
    project.qc.pop("script_manual_approval", None)
    project.qc.pop("final", None)
    project.qc.pop("review_readiness", None)
    project.status = "fidelity_evidence_repair"
    save_project(project, EPISODE_DIR)
    print(f"repaired {len(REPAIRS)} evidence mappings; words={project.script.word_count}")


if __name__ == "__main__":
    main()
