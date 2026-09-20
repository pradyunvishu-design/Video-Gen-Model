from pipeline import ingest
from pipeline.ingest import canonical_url, dedupe, normalized_title


def test_canonical_url_removes_query_and_fragment():
    assert canonical_url("HTTPS://Example.COM/post/?utm_source=x#section") == "https://example.com/post"


def test_dedupe_prefers_higher_score_for_same_url():
    stories = [
        {"url": "https://example.com/a?x=1", "title": "Story", "score": 1},
        {"url": "https://example.com/a?x=2", "title": "Story updated", "score": 9},
    ]
    assert dedupe(stories)[0]["score"] == 9


def test_normalized_title_is_stable():
    assert normalized_title("AI's NEW Model!") == "ais new model"


def test_reddit_falls_back_to_public_rss(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, content=b""):
            self.status_code = status_code
            self.content = content
            self.headers = {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return {}

    atom = b"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>ComfyUI</title>
      <entry>
        <title>A useful ComfyUI release</title>
        <link href="https://www.reddit.com/r/comfyui/comments/example/release/" />
        <author><name>workflow_author</name></author>
        <updated>2026-08-06T10:00:00+00:00</updated>
        <content type="html">A reproducible workflow and repository link.</content>
      </entry>
    </feed>"""

    def fake_get(url, **_kwargs):
        return FakeResponse(403) if url.endswith("raw_json=1") else FakeResponse(200, atom)

    monkeypatch.setattr(ingest, "SUBREDDITS", ["comfyui"])
    monkeypatch.setattr(ingest.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(ingest.requests, "get", fake_get)

    stories = ingest.fetch_reddit()

    assert len(stories) == 1
    assert stories[0]["source"] == "r/comfyui"
    assert stories[0]["source_access"] == "public_rss_combined"
    assert stories[0]["score"] == 0
