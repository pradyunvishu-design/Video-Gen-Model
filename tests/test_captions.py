from pipeline.captions import TimedWord, align_script_words, alignment_quality, normalize_word_timings, write_ass


def test_alignment_preserves_script_spelling(tmp_path):
    recognized = [TimedWord("queen", 0.0, 0.3), TimedWord("three", 0.3, 0.6), TimedWord("ships", 0.6, 1.0)]
    aligned = align_script_words("Qwen3 ships", recognized)
    assert [word.text for word in aligned] == ["Qwen3", "ships"]
    assert aligned[-1].end == 1.0
    destination = write_ass(aligned, tmp_path / "captions.ass", group_size=2)
    rendered = destination.read_text(encoding="utf-8-sig")
    assert "Qwen3 ships" not in rendered
    assert "Qwen3" in rendered and "{\\k" in rendered


def test_alignment_quality_rejects_garbled_or_switched_audio():
    script = "Claude and Codex both completed the workflow with different tradeoffs."
    good = [
        TimedWord(word, index * 0.2, (index + 1) * 0.2)
        for index, word in enumerate(script.split())
    ]
    bad = [TimedWord("static", 0.0, 0.4), TimedWord("purple", 0.4, 0.8)]

    assert alignment_quality(script, good)["passed"] is True
    assert alignment_quality(script, bad)["passed"] is False


def test_normalize_word_timings_repairs_zero_length_and_overlap():
    repaired = normalize_word_timings([
        TimedWord("Codex", 0.10, 0.10),
        TimedWord("checks", 0.08, 0.24),
        TimedWord("Buzz", 0.24, 0.24),
    ])

    assert all(word.end > word.start for word in repaired)
    assert all(left.end <= right.start for left, right in zip(repaired, repaired[1:]))
    assert [word.text for word in repaired] == ["Codex", "checks", "Buzz"]
