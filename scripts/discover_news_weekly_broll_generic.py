from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for raw in (ROOT / "secrets" / "youtube_agent_keys.env").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if line and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
sys.path.insert(0, str(ROOT))

from pipeline.models import EpisodeProject  # noqa: E402
from pipeline.youtube_broll import BrollDiscoveryRequest, BrollScene, discover_project_broll  # noqa: E402


OUT = ROOT / "output" / "news_weekly_20260822"
targets = [
    ("cyber_ops", "widescreen cybersecurity operations center documentary security analysts at monitors"),
    ("browser_work", "widescreen browser automation software desktop workflow screen recording"),
    ("video_workflow", "widescreen professional video editing studio workflow editors working"),
    ("online_safety", "widescreen teen online safety documentary technology family computers"),
    ("data_center", "widescreen data center server racks cooling infrastructure cinematic footage"),
    ("open_developers", "widescreen open source software developers coding conference community"),
]
scenes = [
    BrollScene(
        scene_id=scene_id, beat_id=scene_id, shot_ids=[f"shot_generic_{index:02d}"],
        narration=visual, visual_need=visual, source_hints=[],
    )
    for index, (scene_id, visual) in enumerate(targets)
]
request = BrollDiscoveryRequest(
    scenes=scenes, candidates_per_scene=3, search_results_per_scene=25,
    published_within_days=730, caption_candidates_per_scene=0,
    creative_commons_only=True,
)
project = EpisodeProject(
    episode_id="episode_20260822_news_weekly", scheduled_date="2026-08-22",
    episode={"title": "AI Crossed a Line This Week", "publishing_enabled": False},
)
result = discover_project_broll(
    project, OUT / "broll_api_generic", request,
    youtube_api_key=os.environ["YOUTUBE_API_KEY"], openai_api_key="",
)
manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
print(json.dumps({
    "manifest": result["manifest"], "review_queue": result["review_queue"],
    "candidates": len(manifest.get("candidates", [])), "errors": len(manifest.get("errors", [])),
}, indent=2))
