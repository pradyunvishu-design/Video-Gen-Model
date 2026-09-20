"""Discover rights-reviewable YouTube b-roll for the 2026-08-22 weekly episode."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EXTERNAL_ENV = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker")
load_dotenv(EXTERNAL_ENV if EXTERNAL_ENV.is_file() else ROOT / ".env.worker")

from pipeline.models import EpisodeProject  # noqa: E402
from pipeline.youtube_broll import (  # noqa: E402
    BrollDiscoveryRequest, BrollScene, discover_project_broll,
)
import pipeline.youtube_broll as youtube_broll  # noqa: E402


SCENES = [
    # Cyber/security: 66 seconds.
    ("cyber_soc", "cyber", [3, 4], "Analysts monitoring a cybersecurity operations center with real dashboards.", ["cybersecurity operations center", "security monitoring"]),
    ("cyber_redteam", "cyber", [6, 7], "A security researcher red-teaming an AI system and reviewing code.", ["AI red team", "cybersecurity researcher"]),
    ("cyber_datacenter", "cyber", [9, 10], "Secure data-center racks and engineers monitoring server activity.", ["secure data center", "server monitoring"]),
    ("cyber_scan", "cyber", [12, 13], "A vulnerability scanner finding issues in a codebase and showing results.", ["vulnerability scanning", "code security"]),
    ("cyber_oss", "cyber", [15, 16], "Open-source maintainers reviewing and patching a security vulnerability.", ["open source security", "software patch review"]),
    ("cyber_human", "cyber", [19], "A human security reviewer responding to a high-priority alert.", ["security incident response", "human review"]),
    # Computer-use agents: 60 seconds.
    ("agent_claude", "computer_use", [22, 23], "A clear Claude computer-use demo controlling a desktop or browser.", ["Claude computer use demo", "Anthropic agent"]),
    ("agent_browser", "computer_use", [25, 26], "A browser agent clicking fields, completing forms, and navigating a web app.", ["browser agent demo", "web automation"]),
    ("agent_claims", "computer_use", [28, 29], "A digital worker processing a form or claims workflow in enterprise software.", ["claims automation", "enterprise workflow automation"]),
    ("agent_files", "computer_use", [32, 33], "A coding agent using a terminal, files, and reusable instructions.", ["AI coding agent terminal", "agent files workflow"]),
    ("agent_review", "computer_use", [36, 37], "An agent workflow with logs, checkpoints, permissions, and human approval.", ["AI agent observability", "human in the loop"]),
    # AI video production: 48 seconds.
    ("runway_ui", "runway", [39, 40], "Runway's AI video generation interface producing or editing a shot.", ["Runway AI video demo", "video generation interface"]),
    ("runway_edit", "runway", [42, 43], "A professional editor and creative team working in a video timeline.", ["professional video editing", "creative production team"]),
    ("runway_workflow", "runway", [46, 47], "An AI video production workflow moving from brief to review to final edit.", ["AI video workflow", "creative review process"]),
    ("runway_output", "runway", [50, 51], "A high-quality AI-generated video example shown inside an editing or review context.", ["AI generated video demo", "Runway showcase"]),
    # ChatGPT as a platform: 36 seconds.
    ("chatgpt_ui", "chatgpt", [53, 54], "A clean ChatGPT interface demo on desktop or mobile.", ["ChatGPT interface demo", "OpenAI ChatGPT"]),
    ("chatgpt_ads", "chatgpt", [57, 58], "A clearly labeled sponsored result or advertising experience inside software.", ["sponsored result interface", "digital advertising product UI"]),
    ("chatgpt_teens", "chatgpt", [61, 62], "A student using an AI study tool with parental or safety controls.", ["AI study tool", "teen online safety"]),
    # Physical AI infrastructure: 54 seconds.
    ("ports_build", "ports", [64, 65], "Large data-center construction, cranes, and an industrial technology campus.", ["data center construction", "AI infrastructure campus"]),
    ("ports_gpu", "ports", [67, 68], "NVIDIA GPU servers and data-center racks operating at scale.", ["NVIDIA data center", "GPU server racks"]),
    ("ports_grid", "ports", [70, 71], "Electrical substations, power transmission, and grid infrastructure.", ["electrical substation", "power grid infrastructure"]),
    ("ports_cooling", "ports", [73, 74], "Industrial cooling equipment serving a large computing facility.", ["data center cooling", "industrial cooling infrastructure"]),
    ("ports_workers", "ports", [76], "Construction workers building a large industrial or data-center site in Ohio.", ["Ohio construction", "industrial campus workers"]),
    # Open-model ecosystem: 66 seconds.
    ("open_hub", "open_models", [78, 79], "Browsing model cards and repositories on the Hugging Face Hub.", ["Hugging Face Hub", "model repository"]),
    ("open_qwen", "open_models", [81, 82], "A Qwen open model demo running a real task.", ["Qwen model demo", "open source AI"]),
    ("open_small", "open_models", [84, 85], "A small language model running locally on a normal laptop or compact device.", ["small language model local", "local LLM demo"]),
    ("open_download", "open_models", [87, 88], "A terminal downloading and launching a model repository.", ["download AI model terminal", "model repository CLI"]),
    ("open_agents", "open_models", [90, 91], "Claude Code or another coding agent selecting tools and running terminal commands.", ["Claude Code agent", "coding agent terminal"]),
    ("open_release", "open_models", [93], "Open-source contributors publishing, signing, or documenting a software release.", ["open source release", "GitHub contributors"]),
]

NARRATION = {
    "cyber": "Frontier models, their sandboxes, monitoring systems, vulnerability scans, and human review are becoming part of the security perimeter.",
    "computer_use": "Computer-using agents can operate browsers, complete forms, work with files, and return finished tasks, but reliable deployments need permissions, logs, and checkpoints.",
    "runway": "AI video is moving from one-off generations into professional production workflows with editing, collaboration, review, and approval.",
    "chatgpt": "ChatGPT is becoming a platform with different product experiences, advertising economics, and stronger safety defaults for younger users.",
    "ports": "AI infrastructure now depends on data-center construction, NVIDIA compute, power transmission, cooling, and years of physical buildout.",
    "open_models": "Open models live in repositories that people and agents browse, download, run locally, extend, document, and secure.",
}


def main() -> None:
    scenes = [
        BrollScene(
            scene_id=scene_id,
            beat_id=section,
            shot_ids=[f"slot_{slot:03d}" for slot in slots],
            narration=NARRATION[section],
            visual_need=visual_need,
            source_hints=hints,
            publisher_hints=[],
        )
        for scene_id, section, slots, visual_need, hints in SCENES
    ]
    request = BrollDiscoveryRequest(
        scenes=scenes,
        candidates_per_scene=3,
        search_results_per_scene=50,
        published_within_days=3650,
        caption_candidates_per_scene=0,
        creative_commons_only=True,
        require_reputable_or_viral=True,
        min_channel_subscribers=10_000,
        min_video_views=25_000,
        min_views_per_day=50,
        min_semantic_score=20,
    )
    # Curated visual queries are intentionally literal. A broad LLM-written
    # query tended to optimize for the story's words instead of what should be
    # visible on screen, starving generic but useful CC footage such as server
    # racks, substations, and editing timelines.
    youtube_broll.plan_scene_queries = lambda items, _api_key=None: ([
        {
            "scene_id": item.scene_id,
            "query": item.source_hints[0],
            "visual_target": item.visual_need,
            "avoid": "war footage, reaction videos, vertical shorts, reuploads, unrelated talking heads",
        }
        for item in items
    ], "curated_visible_subject_queries")
    project = EpisodeProject(
        episode_id="episode_20260822_news_weekly", scheduled_date="2026-08-22",
    )
    result = discover_project_broll(
        project,
        ROOT / "output" / "news_weekly_20260822" / "broll_research_55_broad",
        request,
    )
    print(json.dumps({
        "scene_count": result["scene_count"],
        "candidate_count": result["candidate_count"],
        "error_count": result["error_count"],
        "manifest": result["manifest"],
        "review_queue": result["review_queue"],
    }, indent=2))


if __name__ == "__main__":
    main()
