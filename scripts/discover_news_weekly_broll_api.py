from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "secrets" / "youtube_agent_keys.env"
for raw in SECRETS.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

sys.path.insert(0, str(ROOT))

from pipeline.models import EpisodeProject  # noqa: E402
from pipeline.youtube_broll import (  # noqa: E402
    BrollDiscoveryRequest,
    BrollScene,
    discover_project_broll,
)


OUT = ROOT / "output" / "news_weekly_20260822"
script = json.loads((OUT / "script.json").read_text(encoding="utf-8"))
by_id = {section["id"]: section["narration"] for section in script["sections"]}

scenes = [
    BrollScene(
        scene_id="cyber_pause", beat_id="cyber", shot_ids=["shot_018", "shot_022"],
        narration=by_id["cyber"],
        visual_need="OpenAI cybersecurity research, security operations center, code security testing, cyber defense keynote footage",
        source_hints=["OpenAI", "Anthropic", "cybersecurity", "official keynote"],
        publisher_hints=["OpenAI", "Anthropic"],
    ),
    BrollScene(
        scene_id="computer_use", beat_id="computer_use", shot_ids=["shot_027", "shot_034"],
        narration=by_id["computer_use"],
        visual_need="AI agent controlling a browser, computer-use demo, cursor completing multi-step web tasks",
        source_hints=["Anthropic", "Claude", "computer use", "browser agent demo"],
        publisher_hints=["Anthropic"],
    ),
    BrollScene(
        scene_id="runway_video", beat_id="runway", shot_ids=["shot_042", "shot_049"],
        narration=by_id["runway"],
        visual_need="professional generative video production workflow, film editing interface, enterprise creative team reviewing footage",
        source_hints=["Runway", "generative video", "video production", "official demo"],
        publisher_hints=["Runway"],
    ),
    BrollScene(
        scene_id="chatgpt_platform", beat_id="chatgpt_platform", shot_ids=["shot_055", "shot_061"],
        narration=by_id["chatgpt_platform"],
        visual_need="ChatGPT product interface, platform advertising discussion, teen online safety and parental controls",
        source_hints=["OpenAI", "ChatGPT", "online safety", "product demo"],
        publisher_hints=["OpenAI"],
    ),
    BrollScene(
        scene_id="ports_pike", beat_id="ports_pike", shot_ids=["shot_068", "shot_075"],
        narration=by_id["ports_pike"],
        visual_need="large AI data center campus, server racks, electrical grid infrastructure, Ohio industrial construction aerial footage",
        source_hints=["NVIDIA", "data center", "AI infrastructure", "server campus"],
        publisher_hints=["NVIDIA"],
    ),
    BrollScene(
        scene_id="open_models", beat_id="open_models", shot_ids=["shot_084", "shot_090"],
        narration=by_id["open_models"],
        visual_need="open source AI developer community, model repository interface, machine learning conference and coding workflow",
        source_hints=["Hugging Face", "open models", "machine learning", "developer conference"],
        publisher_hints=["Hugging Face"],
    ),
]

request = BrollDiscoveryRequest(
    scenes=scenes,
    candidates_per_scene=3,
    search_results_per_scene=18,
    published_within_days=730,
    caption_candidates_per_scene=1,
    creative_commons_only=True,
)
project = EpisodeProject(
    episode_id="episode_20260822_news_weekly",
    scheduled_date="2026-08-22",
    episode={"title": script["title"], "publishing_enabled": False},
)
result = discover_project_broll(project, OUT / "broll_api", request)
manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
summary = {
    "manifest": result["manifest"],
    "review_queue": result["review_queue"],
    "candidate_count": len(manifest.get("candidates", [])),
    "scene_count": len(manifest.get("scenes", [])),
    "error_count": len(manifest.get("errors", [])),
    "creative_commons_only": True,
}
print(json.dumps(summary, indent=2))
