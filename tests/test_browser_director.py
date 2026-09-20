import inspect

import pytest

from pipeline import browser_director, capture
from pipeline.models import Source


def source() -> Source:
    return Source(id="src_1", title="Product launch", url="https://example.com/news")


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "http://localhost:8080/health",
    "http://169.254.169.254/latest/meta-data",
    "file:///etc/passwd",
    "ftp://example.com/file",
])
def test_capture_rejects_private_and_non_http_destinations(url):
    with pytest.raises(ValueError):
        capture._safe_url(url)


def test_browser_director_uses_only_observed_candidates(monkeypatch):
    monkeypatch.setattr(browser_director, "call_openrouter", lambda *args, **kwargs: {
        "source_id": "src_1",
        "rationale": "Show the actual launch evidence.",
        "actions": [
            {
                "kind": "element", "candidate_id": "c002", "label": "Product UI",
                "start_ratio": 0, "end_ratio": 0.8, "duration_seconds": 4,
            },
            {
                "kind": "element", "candidate_id": "invented", "label": "Unsafe guess",
                "start_ratio": 0, "end_ratio": 0.8, "duration_seconds": 4,
            },
            {
                "kind": "scroll", "candidate_id": "c002", "label": "Evidence scroll",
                "start_ratio": 0.9, "end_ratio": 0.2, "duration_seconds": 7,
            },
        ],
    })
    observation = {
        "page_title": "Launch",
        "final_url": "https://example.com/news",
        "candidates": [
            {"candidate_id": "c001", "tag": "h1", "text": "Launch", "width": 900, "height": 80, "y": 20},
            {"candidate_id": "c002", "tag": "figure", "text": "Product UI", "width": 1200, "height": 700, "y": 500},
        ],
    }

    plan = browser_director.plan_capture(source(), observation, ["Show the product interface"])

    assert [action.kind for action in plan.actions] == ["element", "scroll"]
    assert plan.actions[0].candidate_id == "c002"
    assert plan.actions[1].candidate_id == ""
    assert plan.actions[1].start_ratio == 0.05
    assert plan.actions[1].end_ratio == 0.85


def test_browser_director_falls_back_without_candidates(monkeypatch):
    monkeypatch.setattr(
        browser_director,
        "call_openrouter",
        lambda *args, **kwargs: pytest.fail("OpenRouter should not be called without candidates"),
    )

    plan = browser_director.plan_capture(source(), {"candidates": []}, [])

    assert plan.source_id == "src_1"
    assert any(action.kind == "scroll" for action in plan.actions)


def test_browser_director_allows_safe_reveal_and_rejects_mutating_click(monkeypatch):
    monkeypatch.setattr(browser_director, "call_openrouter", lambda *args, **kwargs: {
        "source_id": "src_1", "rationale": "Reveal the demo panel", "actions": [
            {"kind": "click_reveal", "candidate_id": "c001", "label": "Features tab", "start_ratio": 0,
             "end_ratio": 0.8, "duration_seconds": 4, "settle_seconds": 0.6},
            {"kind": "click_reveal", "candidate_id": "c002", "label": "Buy now", "start_ratio": 0,
             "end_ratio": 0.8, "duration_seconds": 4, "settle_seconds": 0.6},
        ],
    })
    observation = {"page_title": "Demo", "final_url": "https://example.com/news", "candidates": [
        {"candidate_id": "c001", "tag": "button", "role": "tab", "text": "Features", "aria_label": "", "href": ""},
        {"candidate_id": "c002", "tag": "button", "role": "button", "text": "Buy now", "aria_label": "", "href": ""},
    ]}
    plan = browser_director.plan_capture(source(), observation, [])
    assert [(action.kind, action.candidate_id) for action in plan.actions] == [("click_reveal", "c001")]


class _FakeBody:
    def __init__(self, text):
        self.text = text

    def inner_text(self, timeout=0):
        return self.text


class _FakePage:
    def __init__(self, title, body):
        self._title = title
        self._body = body

    def title(self):
        return self._title

    def locator(self, selector):
        assert selector == "body"
        return _FakeBody(self._body)


def test_capture_rejects_reddit_network_security_page():
    page = _FakePage("Blocked", "You've been blocked by network security. File a ticket below.")
    assert "network security" in capture._blocked_page_reason(page)


def test_capture_does_not_reject_normal_article_mentioning_access_denied():
    body = ("This long technical article explains why access denied errors happen in proxies. " * 300)
    page = _FakePage("Proxy debugging guide", body)
    assert capture._blocked_page_reason(page) == ""


def test_reddit_capture_has_old_reddit_fallback():
    urls = capture._capture_urls("https://www.reddit.com/r/comfyui/comments/abc/story/")
    assert urls[0].startswith("https://www.reddit.com/")
    assert urls[1].startswith("https://old.reddit.com/")


def test_browser_recordings_use_stable_interpolated_cadence():
    video_filter = capture._recording_filter()
    assert "minterpolate=fps=30" in video_filter
    assert "mi_mode=mci" in video_filter
    assert "deshake" not in video_filter


def test_capture_policy_rejects_access_overlays_instead_of_hiding_them():
    source = inspect.getsource(capture._load_page)
    assert "[class*='subscribe']" not in source
    assert "_assert_no_paywall_overlay" in source
