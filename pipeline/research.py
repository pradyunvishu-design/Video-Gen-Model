"""Source enrichment, clustering, and evidence preparation."""
from __future__ import annotations

import hashlib
import html
import re
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from .ingest import UA, normalized_title
from .config import RESEARCH_PARALLELISM
from .models import Source

PRIMARY_DOMAINS = {
    "openai.com", "anthropic.com", "deepmind.google", "ai.google", "huggingface.co",
    "github.com", "arxiv.org", "stability.ai", "magichour.ai", "mistral.ai", "meta.com",
}
COMMUNITY_DOMAINS = {"reddit.com", "www.reddit.com", "news.ycombinator.com"}
STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "with", "on", "is",
    "ai", "new", "how", "this", "that", "from", "by", "as", "it", "its", "your",
}


def source_type(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host in PRIMARY_DOMAINS or any(host.endswith("." + d) for d in PRIMARY_DOMAINS):
        return "primary"
    if host in COMMUNITY_DOMAINS or any(host.endswith("." + d) for d in COMMUNITY_DOMAINS):
        return "community"
    return "secondary"


def cluster_id(title: str) -> str:
    tokens = [token for token in normalized_title(title).split() if token not in STOPWORDS]
    signature = " ".join(sorted(set(tokens))[:10])
    return "clu_" + hashlib.sha256(signature.encode()).hexdigest()[:10]


def extract_entities(title: str, text: str = "") -> list[str]:
    candidates = re.findall(r"\b(?:[A-Z][A-Za-z0-9.+-]{1,}|[A-Z]{2,}[0-9.-]*)\b", f"{title} {text[:1200]}")
    return [item for item, _ in Counter(candidates).most_common(12)]


def _trafilatura_text(raw: str, url: str = "") -> str:
    """Use Trafilatura when installed, retaining the deterministic BS4 fallback."""
    try:
        import trafilatura
    except ImportError:
        return ""
    extracted = trafilatura.extract(
        raw,
        url=url or None,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        output_format="txt",
    )
    return re.sub(r"\n{3,}", "\n\n", extracted or "").strip()


def _clean_html(raw: str, url: str = "") -> tuple[str, list[str]]:
    soup = BeautifulSoup(raw, "lxml")
    for node in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        node.decompose()
    article = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = [re.sub(r"\s+", " ", p.get_text(" ", strip=True)) for p in article.find_all(["p", "h2", "li"])]
    fallback_text = "\n".join(p for p in paragraphs if len(p) >= 40)
    extracted_text = _trafilatura_text(raw, url)
    # Prefer the dedicated article extractor when it found a meaningful body;
    # otherwise preserve the proven local parser for unusual launch pages.
    text = extracted_text if len(extracted_text) >= max(240, len(fallback_text) * 0.45) else fallback_text
    media: list[str] = []
    for tag in soup.find_all(["video", "source", "img"]):
        values = [tag.get("src"), tag.get("data-src"), tag.get("poster")]
        srcset = tag.get("srcset")
        if srcset:
            # Prefer the largest candidate, which is conventionally last.
            values.append(srcset.split(",")[-1].strip().split()[0])
        for value in values:
            if value:
                resolved = urljoin(url, value)
                if resolved.startswith(("http://", "https://")):
                    media.append(resolved)
    for key in ("og:image", "og:video", "og:video:url", "twitter:image"):
        meta = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if meta and meta.get("content"):
            resolved = urljoin(url, meta["content"])
            if resolved.startswith(("http://", "https://")):
                media.append(resolved)
    return html.unescape(text)[:30000], list(dict.fromkeys(media))[:20]


def enrich_story(story: dict) -> Source:
    text = re.sub(r"<[^>]+>", " ", story.get("summary", ""))
    media_urls: list[str] = []
    capture_status = "pending"
    try:
        response = requests.get(story["url"], headers=UA, timeout=25)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" in content_type:
            extracted, media_urls = _clean_html(response.text, story["url"])
            if extracted:
                text = extracted
    except requests.RequestException:
        capture_status = "failed"
    published = None
    if story.get("published_at"):
        try:
            published = datetime.fromisoformat(story["published_at"].replace("Z", "+00:00"))
        except ValueError:
            pass
    role = {
        "primary": "primary_evidence",
        "reporting": "independent_reporting",
        "newsletter": "newsletter_lead",
        "community": "community_signal",
    }.get(story.get("source_role"), "unknown")
    resolved_type = source_type(story["url"])
    if role == "primary_evidence":
        resolved_type = "primary"
    elif role == "community_signal":
        resolved_type = "community"
    elif role in {"independent_reporting", "newsletter_lead"}:
        resolved_type = "secondary"
    trend_score = min(
        100,
        math.log1p(max(0, story.get("score", 0))) * 9
        + math.log1p(max(0, story.get("comments", 0))) * 5
        + (24 if role == "primary_evidence" else 0)
        + (8 if role == "newsletter_lead" else 0)
        + (5 if role == "independent_reporting" else 0),
    )
    return Source(
        id=story["id"], title=story["title"], url=story["url"], publisher=story.get("source", ""),
        author=story.get("author", ""), published_at=published, source_type=resolved_type,
        text=text, summary=text[:800], cluster_id=cluster_id(story["title"]),
        entities=extract_entities(story["title"], text), media_urls=media_urls,
        capture_status=capture_status, trend_score=trend_score, signal_role=role,
        category=str(story.get("category") or ""), importance_score=trend_score,
    )


def enrich_stories(stories: list[dict], limit: int = 100) -> list[Source]:
    selected = stories[:limit]
    with ThreadPoolExecutor(max_workers=min(RESEARCH_PARALLELISM, max(1, len(selected)))) as executor:
        sources = list(executor.map(enrich_story, selected))
    cluster_counts = Counter(source.cluster_id for source in sources if source.cluster_id)
    for source in sources:
        source.trend_score = round(min(100, source.trend_score + max(0, cluster_counts[source.cluster_id] - 1) * 8), 2)
    return sorted(sources, key=lambda source: source.trend_score, reverse=True)
