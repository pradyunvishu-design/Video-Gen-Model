from pipeline.tts import split_text


def test_split_text_never_exceeds_limit_for_a_long_sentence():
    text = "This clause explains the setup, " + "very specific spoken detail " * 40 + "and it finally lands."

    chunks = split_text(text, limit=120)

    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 120 for chunk in chunks)
    assert " ".join(chunks).split() == text.split()
