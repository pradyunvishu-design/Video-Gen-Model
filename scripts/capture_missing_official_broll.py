from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.capture import capture_sources  # noqa: E402
from pipeline.models import Source  # noqa: E402


OUT = ROOT / "output" / "news_weekly_20260822" / "sources"


def source(source_id: str, publisher: str, title: str, url: str, published: str) -> Source:
    return Source(
        id=source_id,
        publisher=publisher,
        title=title,
        url=url,
        source_type="primary",
        signal_role="primary_evidence",
        published_at=datetime.fromisoformat(published).replace(tzinfo=timezone.utc),
        summary=title,
    )


SOURCES = [
    source(
        "openai_cyber_pause", "OpenAI",
        "Pacing model development in an era of cyber-critical capabilities",
        "https://openai.com/index/pacing-model-development-cyber-capabilities/", "2026-08-18",
    ),
    source(
        "openai_chatgpt_ads", "OpenAI", "ChatGPT Ads expands across Europe",
        "https://openai.com/index/chatgpt-ads-expands-across-europe/", "2026-08-18",
    ),
    source(
        "openai_chatgpt_teens", "OpenAI", "Introducing ChatGPT for Teens",
        "https://openai.com/index/introducing-chatgpt-for-teens/", "2026-08-18",
    ),
    source(
        "openai_ports_pike", "OpenAI", "OpenAI joins PORTS-Pike project",
        "https://openai.com/index/openai-joins-ports-pike-project/", "2026-08-17",
    ),
    source(
        "runway_enterprise_video", "Runway", "The Next Phase of Enterprise Video Generation",
        "https://runway.com/news/company-news/the-next-phase-of-enterprise-video-generation", "2026-08-20",
    ),
]


def main() -> None:
    results = capture_sources(SOURCES, OUT, max_recordings=len(SOURCES))
    summary = {
        "sources": [
            {
                "source_id": item["source_id"],
                "editorial_stills": len(item.get("editorial_stills") or []),
                "recordings": len(item.get("recordings") or []),
                "errors": item.get("errors") or [],
            }
            for item in results
        ]
    }
    (OUT / "missing_official_capture_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
