"""Stage 2: rank stories and write a scene-by-scene video script via OpenRouter."""
import json
import re
from pathlib import Path

import requests

from .config import OPENROUTER_API_KEY, OPENROUTER_MODEL, require

SYSTEM = """You are the head writer for a YouTube channel like "AI Search": AI news \
explained simply and engagingly for a general audience. You write retention-optimized \
long-form scripts: strong hook in the first 15 seconds, conversational tone, short \
sentences, concrete numbers and comparisons, occasional dry humor. You always add \
original commentary and context — never just read headlines (YouTube demonetizes that)."""

PROMPT = """Below is this week's pool of candidate AI stories (JSON).

1. Pick the 5-8 most video-worthy stories (viral demos, big model releases, tools \
viewers can try). Prefer stories multiple sources mention.
2. Write a ~10 minute video script covering them, structured as scenes.

Rules:
- Scene 1 is the hook (tease the 2-3 craziest stories).
- One story may span multiple scenes. Each scene's narration MUST be under 900 characters.
- For each scene give a "visual": a vivid text-to-image prompt for b-roll matching the \
narration (photorealistic, no text/logos in the image).
- End with a quick outro inviting comments + subscribe.

Return ONLY valid JSON:
{"title": "...", "description": "...", "tags": ["..."],
 "scenes": [{"id": 1, "narration": "...", "visual": "..."}]}

STORIES:
%s"""


def _call_openrouter(messages: list[dict]) -> str:
    key = require(OPENROUTER_API_KEY, "OPENROUTER_API_KEY")
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": OPENROUTER_MODEL, "messages": messages, "temperature": 0.8},
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    return json.loads(m.group(1) if m else text)


def run(run_dir: Path) -> Path:
    stories = json.loads((run_dir / "stories.json").read_text(encoding="utf-8"))
    raw = _call_openrouter([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": PROMPT % json.dumps(stories, indent=1)},
    ])
    script = _extract_json(raw)
    for scene in script["scenes"]:
        if len(scene["narration"]) > 1000:
            raise ValueError(f"Scene {scene['id']} narration exceeds 1000 chars; regenerate.")
    out = run_dir / "script.json"
    out.write_text(json.dumps(script, indent=2), encoding="utf-8")
    total = sum(len(s["narration"]) for s in script["scenes"])
    print(f"Script: '{script['title']}' — {len(script['scenes'])} scenes, "
          f"{total} chars (~{total // 900} min) -> {out}")
    return out
