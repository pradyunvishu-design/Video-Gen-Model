from pipeline import research


def test_clean_html_collects_high_resolution_online_media():
    raw = """
    <html><head><meta property="og:image" content="/social/hero.png"></head>
    <body><main><p>This paragraph is deliberately long enough to be retained as article evidence in the parser output.</p>
    <video poster="/media/poster.jpg"><source src="/media/demo.mp4"></video>
    <img src="/small.jpg" srcset="/medium.jpg 800w, /large.jpg 1600w"></main></body></html>
    """
    _, media = research._clean_html(raw, "https://example.com/news/story")
    assert "https://example.com/media/demo.mp4" in media
    assert "https://example.com/media/poster.jpg" in media
    assert "https://example.com/large.jpg" in media
    assert "https://example.com/social/hero.png" in media


def test_trend_scoring_rewards_primary_and_repeated_clusters(monkeypatch):
    stories = [
        {"id": "a", "title": "Model Alpha Launch", "url": "https://openai.com/a", "score": 0},
        {"id": "b", "title": "Model Alpha Launch", "url": "https://example.com/b", "score": 0},
        {"id": "c", "title": "Unrelated Tool", "url": "https://example.com/c", "score": 0},
    ]
    monkeypatch.setattr(research, "enrich_story", lambda story: research.Source(
        id=story["id"], title=story["title"], url=story["url"],
        source_type=research.source_type(story["url"]), cluster_id=research.cluster_id(story["title"]),
        trend_score=20 if research.source_type(story["url"]) == "primary" else 0,
    ))

    sources = research.enrich_stories(stories)
    by_id = {source.id: source for source in sources}

    assert by_id["a"].trend_score > by_id["c"].trend_score
    assert by_id["b"].trend_score > by_id["c"].trend_score


def test_article_extraction_prefers_trafilatura_when_meaningful(monkeypatch):
    raw = "<html><body><article><p>Short fallback paragraph that is long enough for extraction but not ideal.</p></article></body></html>"
    richer = "A precise extracted article body. " * 30
    monkeypatch.setattr(research, "_trafilatura_text", lambda _raw, _url="": richer)

    text, media = research._clean_html(raw, "https://example.com/story")

    assert text.startswith("A precise extracted article body")
    assert media == []
