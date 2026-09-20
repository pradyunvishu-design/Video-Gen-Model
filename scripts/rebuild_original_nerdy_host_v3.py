"""Build an original understated tech host and tighter news-explainer bookends."""
from __future__ import annotations

from pathlib import Path

import scripts.rebuild_manager_feedback_v2 as build


EPISODE = build.EPISODE
REVISION_DIR = EPISODE / "manager_feedback_v3"

build.PROJECT_BACKUP = EPISODE / "episode_project.pre_manager_feedback_v3.json"
build.REVISION_DIR = REVISION_DIR
build.AUDIO_DIR = REVISION_DIR / "audio"
# Keep the approved design, but render a v3 master at the new word-timed duration.
build.MOTION_DIR = REVISION_DIR / "motion"
build.SOURCE_SEGMENTS = EPISODE / "timeline_segments" / "manager-feedback-v2"
build.SEGMENT_DIR = EPISODE / "timeline_segments" / "manager-feedback-v3"
build.FINAL_NARRATION = EPISODE / "narration_gemini_31_original_nerdy_host_v3.wav"
build.FINAL_TIMELINE = EPISODE / "timeline_manager_feedback_v3.mp4"
build.FINAL_VIDEO = EPISODE / "final_original_nerdy_host_v3_1080p.mp4"
build.VOICE = "Charon"
build.REVISION_VERSION = "v3"
build.VOICE_PROFILE_ID = "gemini_31_charon_original_understated_tech_host_v3"
build.QC_PREFIX = "manager_v3"
build.REVIEW_NOTE = (
    "Manager feedback v3: original understated nerdy tech host, product-first intro, "
    "and verdict-led conclusion. No imitation or cloned creator voice."
)

build.NEW_B00 = (
    "ComfyUI just added Google's Gemini Omni 1.1 Flash as a Partner Node, which means five "
    "different video jobs now live inside the same graph. You can generate a clip, use reference "
    "images, edit a shot, or extend one without bouncing between tools."
)
build.NEW_B01 = (
    "That's the useful part. The harder question is whether the result still holds together when "
    "you ask for a precise change. So we'll compare the documented controls with the launch examples, "
    "look at where edits and extensions can fail, and finish with the cheapest test that tells you "
    "whether 1080p or 4K is actually worth it."
)
build.NEW_B28 = (
    "After the controls, examples, and failure points, my answer is pretty simple. Gemini Omni is "
    "useful in ComfyUI because it removes setup, not uncertainty. If you already work in graphs, try it. "
    "Just test cheaply: render low, watch the movement, change one thing, then check identity, lighting, "
    "and continuity before paying for resolution. If the same ten-second shot survives that loop twice, "
    "finish it. If it doesn't, 4K is just a sharper version of the same mistake."
)

build.OPENING_CANDIDATES = [
    {
        "mode": "product_first",
        "text": build.NEW_B00 + " " + build.NEW_B01,
        "selected": True,
        "reason": "Names the product and workflow immediately, then previews the exact reliability decision and test sequence.",
    },
    {
        "mode": "verdict_first",
        "text": "Gemini Omni makes ComfyUI easier to use. It does not automatically make a fragile edit reliable.",
        "selected": False,
        "reason": "Clear verdict, but it gives the viewer less visual context than the selected product-first opening.",
    },
    {
        "mode": "relatable_friction",
        "text": "The expensive time to find a motion mistake is after the final render.",
        "selected": False,
        "reason": "Relatable creator problem, but the product arrives too late.",
    },
    {
        "mode": "context_reversal",
        "text": "Five separate video jobs now fit inside one ComfyUI graph. Fewer tools do not mean fewer failure points.",
        "selected": False,
        "reason": "Good contrast, but less concrete than showing the supported jobs immediately.",
    },
]

build.DIRECTOR = """Read only the transcript below. Never read these notes aloud.

Use an original male technology explainer voice. Do not imitate, reproduce, or evoke any identifiable real creator. Speak like a technically curious person talking to one viewer after actually reading the source material: understated, slightly nerdy, relaxed, and matter-of-fact.

Keep a small natural pitch range, ordinary American English, and an unhurried conversational pace around 145 to 150 words per minute. Do not compress clause endings to save time. Let some sentences be plain. Use tiny pauses only when the thought changes. Keep lists connected instead of performing every item. End most statements neutrally or slightly downward. Sound interested, not impressed.

Avoid announcer polish, radio voice, theatrical warmth, breathy intimacy, sales energy, trailer pacing, sing-song rhythm, dramatic pauses, exaggerated emphasis, fake chuckles, and a fresh performance reset at each paragraph. Do not perform punctuation, headlines, jokes, contrasts, or the final sentence. Finish every word cleanly and keep the same speaker identity throughout.

TRANSCRIPT:
"""


if __name__ == "__main__":
    build.main()
