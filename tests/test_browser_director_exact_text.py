from pipeline.browser_director import _exact_visible_label


def test_capture_label_must_be_exact_visible_text() -> None:
    candidate = {"text": "Claude Code can work across schematics and regression tests."}
    assert _exact_visible_label("schematics and regression tests", candidate) == "schematics and regression tests"
    fallback = _exact_visible_label("invented editorial paraphrase", candidate)
    assert fallback in candidate["text"]
    assert "invented" not in fallback
