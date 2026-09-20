"""Collect a rolling 30-day AI-media story pool from free public sources."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests

FEEDS = [
    # Primary announcements and changelogs. These are evidence, not merely trend signals.
    ("ComfyUI Releases", "https://github.com/Comfy-Org/ComfyUI/releases.atom", "primary", "open_source"),
    ("Hugging Face Diffusers Releases", "https://github.com/huggingface/diffusers/releases.atom", "primary", "open_source"),
    ("Stability AI Releases", "https://github.com/Stability-AI/generative-models/releases.atom", "primary", "open_source"),
    ("LTX Video Releases", "https://github.com/Lightricks/LTX-Video/releases.atom", "primary", "open_source"),
    ("ComfyUI Blog", "https://blog.comfy.org/feed", "primary", "open_source"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml", "primary", "models"),
    ("OpenAI", "https://openai.com/news/rss.xml", "primary", "models"),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml", "primary", "research"),
    ("Google AI", "https://blog.google/technology/ai/rss/", "primary", "products"),
    ("Microsoft AI", "https://blogs.microsoft.com/ai/feed/", "primary", "products"),
    ("Meta AI", "https://ai.meta.com/blog/rss/", "primary", "models"),
    ("NVIDIA", "https://blogs.nvidia.com/feed/", "primary", "hardware"),
    ("AWS Machine Learning", "https://aws.amazon.com/blogs/machine-learning/feed/", "primary", "products"),
    ("Stability AI", "https://stability.ai/news?format=rss", "primary", "models"),
    # Independent reporting provides confirmation and consequence.
    ("Techmeme", "https://www.techmeme.com/feed.xml", "reporting", "technology"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "reporting", "technology"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "reporting", "business"),
    ("MIT Technology Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed", "reporting", "research"),
    ("Ars Technica AI", "https://feeds.arstechnica.com/arstechnica/technology-lab", "reporting", "technology"),
    # Newsletter feeds are discovery/context leads. The claim extractor must still use evidence sources.
    ("The Batch", "https://www.deeplearning.ai/the-batch/feed/", "newsletter", "research"),
    ("Import AI", "https://importai.substack.com/feed", "newsletter", "research"),
    ("Latent Space", "https://www.latent.space/feed", "newsletter", "engineering"),
    ("One Useful Thing", "https://www.oneusefulthing.org/feed", "newsletter", "products"),
    ("Interconnects", "https://www.interconnects.ai/feed", "newsletter", "models"),
]
SUBREDDITS = [
    "StableDiffusion", "comfyui", "FluxAI", "LocalLLaMA", "aivideo", "MachineLearning", "artificial", "technology"
]
UA = {"User-Agent": "AIMediaEditorialBot/2.0 (research; contact: editorial@localhost)"}
LOOKBACK_S = 30 * 24 * 3600
NEWSLETTER_DROP = Path(__file__).resolve().parents[1] / "data" / "newsletters" / "inbox"


def canonical_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))
    except ValueError:
        return url


def normalized_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def story_id(url: str, title: str) -> str:
    return "src_" + hashlib.sha256((canonical_url(url) or normalized_title(title)).encode()).hexdigest()[:12]


def _published(entry: dict) -> tuple[str | None, float | None]:
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if not struct:
        return None, None
    stamp = time.mktime(struct)
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat(), stamp


def fetch_rss() -> list[dict]:
    stories: list[dict] = []
    cutoff = time.time() - LOOKBACK_S
    for source, url, role, category in FEEDS:
        try:
            response = requests.get(url, headers=UA, timeout=30)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except Exception as exc:
            print(f"  ! {source}: {exc}")
            continue
        for entry in feed.entries[:40]:
            published, stamp = _published(entry)
            if stamp and stamp < cutoff:
                continue
            link = canonical_url(entry.get("link", ""))
            title = entry.get("title", "").strip()
            if not link or not title:
                continue
            stories.append({
                "id": story_id(link, title), "source": source, "title": title, "url": link,
                "published_at": published, "author": entry.get("author", ""),
                "summary": (entry.get("summary", "") or "")[:1200], "score": 0,
                "source_role": role, "category": category,
            })
    return stories


def fetch_newsletter_drop(directory: Path | None = None) -> list[dict]:
    """Load newsletter items exported by n8n/Gmail without putting mailbox credentials in the worker."""
    directory = directory or NEWSLETTER_DROP
    if not directory.exists():
        return []
    stories: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"  ! newsletter drop {path.name}: {exc}")
            continue
        items = payload if isinstance(payload, list) else payload.get("items", [payload])
        for item in items:
            title = str(item.get("title") or item.get("subject") or "").strip()
            url = canonical_url(str(item.get("url") or item.get("source_url") or "").strip())
            if not title or not url.startswith(("https://", "http://")):
                continue
            stories.append({
                "id": story_id(url, title),
                "source": str(item.get("publisher") or item.get("newsletter") or path.stem),
                "title": title,
                "url": url,
                "published_at": item.get("published_at"),
                "author": str(item.get("author") or ""),
                "summary": str(item.get("body") or item.get("summary") or "")[:6000],
                "score": int(item.get("score") or 0),
                "source_role": "newsletter",
                "category": str(item.get("category") or "technology"),
                "source_access": "newsletter_drop",
            })
    return stories


def fetch_reddit() -> list[dict]:
    stories: list[dict] = []
    # One combined Atom request avoids Reddit's per-IP burst limit while still
    # preserving the originating subreddit from each permalink.
    combined = "+".join(SUBREDDITS)
    combined_url = f"https://www.reddit.com/r/{combined}/top.rss?t=week&limit=100"
    try:
        combined_response = requests.get(
            combined_url,
            headers={**UA, "Accept": "application/atom+xml, application/rss+xml;q=0.9"},
            timeout=30,
        )
        combined_response.raise_for_status()
        combined_feed = feedparser.parse(combined_response.content)
        for entry in combined_feed.entries[:100]:
            title = (entry.get("title") or "").strip()
            link = canonical_url(entry.get("link") or "")
            subreddit = re.search(r"/r/([^/]+)/", link, flags=re.IGNORECASE)
            if not title or not link or not subreddit:
                continue
            published, stamp = _published(entry)
            if stamp and stamp < time.time() - LOOKBACK_S:
                continue
            stories.append({
                "id": story_id(link, title), "source": f"r/{subreddit.group(1)}", "title": title,
                "url": link, "external_url": "", "published_at": published,
                "author": entry.get("author", ""),
                "summary": (entry.get("summary", "") or "")[:2000],
                "score": 0, "comments": 0, "upvote_ratio": 0,
                "source_access": "public_rss_combined",
                "source_role": "community", "category": "community",
            })
        if stories:
            return stories
    except Exception as exc:
        print(f"  ! combined Reddit RSS unavailable ({exc}); trying individual feeds")

    for sub in SUBREDDITS:
        time.sleep(1)
        posts: list[dict] = []
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=40&raw_json=1"
            response = requests.get(url, headers=UA, timeout=30)
            response.raise_for_status()
            posts = response.json().get("data", {}).get("children", [])
        except Exception as exc:
            # Reddit often denies unauthenticated JSON while leaving its public
            # Atom feeds readable. Reddit remains a lead, never factual proof.
            print(f"  ! r/{sub} JSON unavailable ({exc}); trying public RSS")
            try:
                rss_url = f"https://www.reddit.com/r/{sub}/top.rss?t=week&limit=40"
                rss_response = requests.get(
                    rss_url,
                    headers={**UA, "Accept": "application/atom+xml, application/rss+xml;q=0.9"},
                    timeout=30,
                )
                if rss_response.status_code == 429:
                    retry_after = getattr(rss_response, "headers", {}).get("Retry-After", "10")
                    try:
                        delay = min(max(float(retry_after), 2.0), 30.0)
                    except (TypeError, ValueError):
                        delay = 10.0
                    time.sleep(delay)
                    rss_response = requests.get(
                        rss_url,
                        headers={**UA, "Accept": "application/atom+xml, application/rss+xml;q=0.9"},
                        timeout=30,
                    )
                rss_response.raise_for_status()
                feed = feedparser.parse(rss_response.content)
            except Exception as rss_exc:
                print(f"  ! r/{sub} RSS unavailable: {rss_exc}")
                continue
            for entry in feed.entries[:40]:
                title = (entry.get("title") or "").strip()
                link = canonical_url(entry.get("link") or "")
                if not title or not link:
                    continue
                published, stamp = _published(entry)
                if stamp and stamp < time.time() - LOOKBACK_S:
                    continue
                stories.append({
                    "id": story_id(link, title), "source": f"r/{sub}", "title": title,
                    "url": link, "external_url": "", "published_at": published,
                    "author": entry.get("author", ""),
                    "summary": (entry.get("summary", "") or "")[:2000],
                    "score": 0, "comments": 0, "upvote_ratio": 0,
                    "source_access": "public_rss_fallback",
                    "source_role": "community", "category": "community",
                })
            # Public Reddit feeds are aggressively rate-limited. This runs only
            # once per six-hour refresh, so politeness is preferable to gaps.
            time.sleep(10)
            continue
        for wrapped in posts:
            post = wrapped.get("data", {})
            title = (post.get("title") or "").strip()
            permalink = post.get("permalink") or ""
            if not title or not permalink or post.get("stickied"):
                continue
            link = canonical_url("https://www.reddit.com" + permalink)
            created = float(post.get("created_utc") or 0)
            if created and created < time.time() - LOOKBACK_S:
                continue
            external = post.get("url_overridden_by_dest") or ""
            stories.append({
                "id": story_id(link, title), "source": f"r/{sub}", "title": title,
                "url": link,
                "external_url": canonical_url(external) if external.startswith("http") else "",
                "published_at": datetime.fromtimestamp(created, timezone.utc).isoformat() if created else None,
                "author": post.get("author", ""),
                "summary": (post.get("selftext") or "")[:2000],
                "score": int(post.get("score") or 0),
                "comments": int(post.get("num_comments") or 0),
                "upvote_ratio": float(post.get("upvote_ratio") or 0),
                "source_role": "community", "category": "community",
            })
    return stories


def fetch_hn() -> list[dict]:
    try:
        response = requests.get(
            "https://hn.algolia.com/api/v1/search?query=AI&tags=story"
            f"&numericFilters=created_at_i>{int(time.time()) - LOOKBACK_S},points>40&hitsPerPage=100",
            headers=UA, timeout=30,
        )
        response.raise_for_status()
        hits = response.json()["hits"]
    except Exception as exc:
        print(f"  ! HN: {exc}")
        return []
    result = []
    for hit in hits:
        title = hit.get("title") or ""
        url = canonical_url(hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}")
        result.append({
            "id": story_id(url, title), "source": "Hacker News", "title": title, "url": url,
            "published_at": hit.get("created_at"), "author": hit.get("author", ""),
            "summary": "", "score": hit.get("points", 0),
            "comments": hit.get("num_comments", 0), "source_role": "community", "category": "technology",
        })
    return result


def dedupe(stories: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for story in stories:
        key = canonical_url(story.get("url", "")) or normalized_title(story.get("title", ""))
        if not key:
            continue
        previous = by_key.get(key)
        if previous is None or story.get("score", 0) > previous.get("score", 0):
            by_key[key] = story
    return sorted(by_key.values(), key=lambda item: (item.get("published_at") or "", item.get("score", 0)), reverse=True)


def collect() -> list[dict]:
    return dedupe(fetch_rss() + fetch_reddit() + fetch_hn() + fetch_newsletter_drop())


def run(run_dir: Path) -> Path:
    stories = collect()
    out = run_dir / "stories.json"
    out.write_text(json.dumps(stories, indent=2), encoding="utf-8")
    print(f"Ingested {len(stories)} unique stories -> {out}")
    return out
