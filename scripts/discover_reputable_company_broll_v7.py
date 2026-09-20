"""Discover HD Creative-Commons YouTube footage from official/reputable publishers."""
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
from pipeline.youtube_broll import BrollDiscoveryRequest, BrollScene, discover_project_broll  # noqa: E402
import pipeline.youtube_broll as youtube_broll  # noqa: E402


SCENES = [
    (6, "DEF CON official generative AI red team security talk", "DEFCONConference", "A reputable security researcher red-teaming an AI system."),
    (8, "OpenAI cybersecurity Preparedness Framework presentation", "OpenAI", "An official OpenAI security or preparedness presentation."),
    (12, "OpenAI frontier model safety monitoring data center", "OpenAI", "Frontier-model monitoring or secure research infrastructure."),
    (20, "Anthropic Claude Security code vulnerability demo", "Anthropic", "Claude scanning code and presenting security findings."),
    (21, "OpenSSF official open source security response", "The Linux Foundation", "Open-source maintainers coordinating a real security response."),
    (24, "Chrome for Developers official browser agent demo", "Chrome for Developers", "A clean browser-agent demo with visible actions and no reaction host."),
    (28, "Anthropic Claude computer use official demo", "Anthropic", "Claude operating a real browser or desktop application."),
    (32, "Anthropic browser use agent form official demo", "Anthropic", "A browser agent completing a real multi-step web workflow."),
    (34, "Anthropic Claude agent multi action official demo", "Anthropic", "An agent executing several visible actions in sequence."),
    (36, "CNCF official AI agent GitOps workflow", "CNCF", "An agent workflow with logs, checkpoints, and human approval."),
    (38, "CNCF official AI agent observability demo", "CNCF", "A trustworthy agent observability dashboard or conference demo."),
    (40, "Runway official AI video production demo", "Runway", "A polished Runway generation result or editing workflow."),
    (44, "Runway official AI video enterprise production", "Runway", "A polished Runway production or enterprise video workflow."),
    (50, "Runway official video editor workflow demo", "Runway", "A shot moving through editing, review, and final output."),
    (52, "Runway official filmmaker AI video workflow", "Runway", "Professional filmmakers reviewing or finishing generated footage."),
    (54, "OpenAI official ChatGPT product demo", "OpenAI", "A clean current ChatGPT interface with a visible task being completed."),
    (56, "OpenAI ChatGPT official interface demo", "OpenAI", "A clean, current ChatGPT product interface."),
    (62, "OpenAI ChatGPT education study tools official", "OpenAI", "Students using official ChatGPT education or study features."),
    (66, "NVIDIA official AI factory data center keynote", "NVIDIA", "NVIDIA systems, racks, or data-center infrastructure in a professional presentation."),
    (68, "Dell NVIDIA official Project Helix data center", "SiliconANGLE theCUBE", "Dell and NVIDIA enterprise infrastructure shown in reputable event coverage."),
    (70, "NVIDIA official data center construction infrastructure", "NVIDIA", "Large-scale AI infrastructure or data-center construction."),
    (72, "NVIDIA official AI education students keynote", "NVIDIA", "Students or workforce training connected to AI infrastructure."),
    (74, "NVIDIA official data center power cooling", "NVIDIA", "Power, cooling, and physical systems around NVIDIA compute."),
    (76, "NVIDIA official data center construction workforce", "NVIDIA", "Workers or engineers building large-scale AI infrastructure."),
    (80, "Hugging Face official Hub model repository demo", "Hugging Face", "A real Hugging Face Hub or model repository interface."),
    (84, "Qwen official open model demo Hugging Face", "Hugging Face", "A reputable demonstration of a Qwen or open model."),
    (86, "Hugging Face official small model local inference", "Hugging Face", "A small model running locally on a normal computer."),
    (88, "Hugging Face official agents download models", "Hugging Face", "An agent or developer downloading and running a model repository."),
    (90, "CNCF official open source AI agent tooling", "CNCF", "Open-source agent tools being demonstrated in a reputable conference session."),
    (92, "EuroPython official open source maintainer talk", "EuroPython Conference", "Open-source maintainers publishing and supporting a real release."),
]

RECOGNIZED_PUBLISHERS = [
    "OpenAI", "Anthropic", "Runway", "NVIDIA", "Hugging Face", "GitLab",
    "Chrome for Developers", "The Linux Foundation", "CNCF",
    "CNCF Cloud Native Computing Foundation", "DEFCONConference", "OWASP Foundation",
    "EuroPython Conference", "SiliconANGLE theCUBE", "Google DeepMind", "Meta AI",
    "Microsoft Developer", "Microsoft Azure", "AWS Events", "IBM Technology",
]


def main() -> None:
    from scripts.render_news_weekly_custom_motion import narration_by_slot
    narration = narration_by_slot()
    scenes = [
        BrollScene(
            scene_id=f"company_slot_{slot:03d}", beat_id=f"slot_{slot:03d}",
            shot_ids=[f"slot_{slot:03d}"], narration=narration[slot],
            visual_need=visual, source_hints=[query], publisher_hints=[publisher],
        )
        for slot, query, publisher, visual in SCENES
    ]
    request = BrollDiscoveryRequest(
        scenes=scenes, candidates_per_scene=3, search_results_per_scene=35,
        published_within_days=3650, caption_candidates_per_scene=1,
        creative_commons_only=True, require_reputable_or_viral=True,
        min_channel_subscribers=100_000, min_video_views=100_000,
        min_views_per_day=100, min_semantic_score=35,
        recognized_publishers_only=True,
        recognized_publishers=RECOGNIZED_PUBLISHERS,
    )
    query_by_id = {f"company_slot_{slot:03d}": query for slot, query, _, _ in SCENES}
    youtube_broll.plan_scene_queries = lambda items, _api_key=None: ([
        {
            "scene_id": item.scene_id, "query": query_by_id[item.scene_id],
            "visual_target": item.visual_need,
            "avoid": "reaction videos, tutorials from unofficial creators, reuploads, compilations, vertical shorts",
        }
        for item in items
    ], "official_company_visible_subject_queries")
    project = EpisodeProject(episode_id="episode_20260822_news_weekly", scheduled_date="2026-08-22")
    result = discover_project_broll(project, OUT := ROOT / "output" / "news_weekly_20260822" / "reputable_youtube_v7", request)
    print(json.dumps({
        "scene_count": result["scene_count"], "candidate_count": result["candidate_count"],
        "error_count": result["error_count"], "manifest": result["manifest"],
        "review_queue": result["review_queue"], "output": str(OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
