from datetime import date

from pipeline.editorial import (
    _spoken_quality_failures, _validate_opening_lab, draft_researched_sections, duration_profile,
    humanize_script, load_conversational_script_profile, load_editorial_voice_profile,
)
from pipeline.models import Brief, Claim, EpisodeProject, Script, ScriptBeat, Source
from pipeline.production import _claims_stage_input


def test_short_episode_uses_measured_voice_speed_for_word_budget():
    project = EpisodeProject(
        episode_id="episode_voice_calibration",
        scheduled_date=date.today().isoformat(),
        episode={"target_minutes": 5, "voice_words_per_minute": 90.8},
    )

    profile = duration_profile(project)

    assert profile["outline_target"] == 454
    assert profile["word_min"] == 390
    assert profile["word_max"] == 481


def test_thirty_second_canary_uses_spoken_canary_budget():
    project = EpisodeProject(
        episode_id="episode_30s_canary", scheduled_date=date.today().isoformat(),
        episode={"target_minutes": 0.5, "voice_words_per_minute": 180},
    )

    profile = duration_profile(project)

    assert (profile["word_min"], profile["word_max"]) == (65, 80)
    assert (profile["beat_min"], profile["beat_max"]) == (6, 7)


def test_short_episode_keeps_default_budget_until_voice_is_measured():
    project = EpisodeProject(
        episode_id="episode_uncalibrated",
        scheduled_date=date.today().isoformat(),
        episode={"target_minutes": 5},
    )

    profile = duration_profile(project)

    assert (profile["word_min"], profile["word_max"]) == (600, 840)


def test_browser_capture_status_does_not_invalidate_verified_claims():
    project = EpisodeProject(
        episode_id="episode_cache",
        scheduled_date=date.today().isoformat(),
        brief=Brief(
            title="Brief", thesis="Thesis", episode_format="deep_dive",
            source_ids=["source_1"], claim_ids=[], why_now="Now",
        ),
        sources=[Source(id="source_1", title="Source", url="https://example.com")],
    )
    before = _claims_stage_input(project)
    project.sources[0].capture_status = "complete"

    assert _claims_stage_input(project) == before


def test_spoken_quality_rejects_template_like_ai_narration():
    narration = (
        "Analysis: this update matters because the workflow changed for creators, teams, and viewers. "
        "The details are useful, but the real impact appears when people use the product in everyday work."
    )
    script = Script(
        title="Title", description="Description", tags=[], thumbnail_text="THIS CHANGES EVERYTHING",
        beats=[ScriptBeat(
            id="beat_01", narration=narration, purpose="analysis",
            visual_direction="Show a clean product workflow",
        )],
    )
    failures = _spoken_quality_failures(script, {
        "beat_min": 1, "beat_max": 1, "word_min": 20, "word_max": 80,
    })

    assert any("template-like narration phrases" in failure for failure in failures)


def test_spoken_quality_rejects_generic_ai_cliches():
    narration = (
        "Here's where things get interesting. This isn't just another release in the rapidly evolving landscape. "
        "The details affect creators because the workflow changes what they can make and how quickly they can evaluate it."
    )
    script = Script(
        title="Title", description="Description", tags=[], thumbnail_text="THIS CHANGES EVERYTHING",
        beats=[ScriptBeat(
            id="beat_01", narration=narration, purpose="analysis",
            visual_direction="Show the product workflow",
        )],
    )
    failures = _spoken_quality_failures(script, {
        "beat_min": 1, "beat_max": 1, "word_min": 20, "word_max": 80,
    })

    assert any("AI-script cliches" in failure for failure in failures)


def test_editorial_voice_profile_has_durable_spoken_contract():
    profile = load_editorial_voice_profile()

    assert profile["profile_id"] == "ai_media_explainer_v1"
    assert "stance" in profile["audience_relationship"]
    assert profile["read_aloud_gate"]


def test_conversational_profile_preserves_multiple_opening_mechanisms():
    profile = load_conversational_script_profile()

    assert profile["profile_id"] == "conversational_ai_news_v2"
    assert len(profile["opening_modes"]) >= 5
    assert "no transcript passages" in profile["research_basis"]["stored_material"]


def test_opening_lab_requires_distinct_evidence_backed_candidates():
    project = EpisodeProject(
        episode_id="opening_lab", scheduled_date=date.today().isoformat(),
        episode={"target_minutes": 10},
        sources=[Source(id="source_1", title="Source", url="https://example.com")],
        claims=[Claim(id=f"claim_{index}", text="Supported fact", source_ids=["source_1"]) for index in range(4)],
    )
    modes = ["verdict_first", "demonstration_first", "relatable_friction", "context_reversal"]
    result = _validate_opening_lab({
        "candidates": [{
            "id": f"opening_{index}", "mode": mode,
            "opening": "A concrete product result changes the ordinary creator workflow, and the source evidence gives us a useful way to test where that improvement helps, where it fails, and what a viewer should actually do with the release today.",
            "claim_ids": [f"claim_{index}"], "proof_target": "Show the source result",
            "promise": "Explain the useful decision", "risk": "Do not overstate the result",
        } for index, mode in enumerate(modes)],
        "selected_id": "opening_1", "selection_reason": "The visible proof arrives fastest.",
    }, project)

    assert result["selected_id"] == "opening_1"


def test_spoken_quality_rejects_factual_hook_without_claim_ids():
    narration = (
        "A concrete release changed the creator workflow this morning, and the visible result makes the practical consequence easy to see. "
        "The useful question is where that improvement survives a real production constraint and where the polished launch demo stops helping."
    )
    script = Script(
        title="Title", description="Description", tags=[], thumbnail_text="THE IMPORTANT CHANGE",
        beats=[ScriptBeat(id="hook", narration=narration, purpose="hook", visual_direction="Show result")],
    )
    failures = _spoken_quality_failures(script, {
        "beat_min": 1, "beat_max": 1, "word_min": 30, "word_max": 80, "target_minutes": 10,
    })

    assert any("factual hook beat without claim IDs" in failure for failure in failures)


def test_spoken_quality_rejects_conversational_filler_as_a_template():
    narration = (
        "So, the release changes one creator workflow with a result the source can show clearly. "
        "Now, the limitation matters because the output still fails under an ordinary constraint. "
        "Okay, the practical choice depends on which part of the process needs help. "
        "Honestly, the evidence is useful once the marketing claim is separated from the visible result. "
        "Basically, creators should judge the usable output instead of trusting the launch-page promise."
    )
    script = Script(
        title="Title", description="Description", tags=[], thumbnail_text="THE IMPORTANT CHANGE",
        beats=[ScriptBeat(id="beat_01", narration=narration, purpose="analysis", visual_direction="Show result")],
    )
    failures = _spoken_quality_failures(script, {
        "beat_min": 1, "beat_max": 1, "word_min": 20, "word_max": 100, "target_minutes": 5,
    })

    assert any("conversational filler" in failure for failure in failures)


def test_spoken_quality_rejects_formal_essay_connectors():
    narration = (
        "Moreover, the release changes a real creator workflow and gives the team a concrete result to compare. "
        "Furthermore, the documented limitation matters because the output still fails under ordinary production constraints. "
        "Consequently, creators need to judge the usable result instead of trusting the launch-page promise."
    )
    script = Script(
        title="Title", description="Description", tags=[], thumbnail_text="THE IMPORTANT CHANGE",
        beats=[ScriptBeat(
            id="beat_01", narration=narration, purpose="analysis",
            visual_direction="Show the source-backed comparison",
        )],
    )
    failures = _spoken_quality_failures(script, {
        "beat_min": 1, "beat_max": 1, "word_min": 20, "word_max": 80,
    })

    assert any("formal essay connectors" in failure for failure in failures)


def test_spoken_quality_rejects_fake_youtube_intro_language():
    narration = (
        "Welcome back. In this video we're going to unlock the power of a model that changes a creator workflow. "
        "The useful evidence is a visible result, a clear limitation, and a decision people can apply without the hype."
    )
    script = Script(
        title="Title", description="Description", tags=[], thumbnail_text="THE IMPORTANT CHANGE",
        beats=[ScriptBeat(id="beat_01", narration=narration, purpose="analysis", visual_direction="Show result")],
    )
    failures = _spoken_quality_failures(script, {
        "beat_min": 1, "beat_max": 1, "word_min": 20, "word_max": 80,
    })
    assert any("AI-script cliches" in failure for failure in failures)


def test_spoken_quality_rejects_copied_creator_catchphrase():
    narration = (
        "AI never sleeps, and this week has been absolutely insane. The release changes a real workflow, "
        "but the useful question is whether the visible output survives ordinary creator constraints."
    )
    script = Script(
        title="Title", description="Description", tags=[], thumbnail_text="THE IMPORTANT CHANGE",
        beats=[ScriptBeat(id="beat_01", narration=narration, purpose="analysis", visual_direction="Show result")],
    )
    failures = _spoken_quality_failures(script, {
        "beat_min": 1, "beat_max": 1, "word_min": 20, "word_max": 80,
    })
    assert any("AI-script cliches" in failure for failure in failures)


def test_spoken_quality_rejects_repeated_link_and_news_handoffs():
    narration = (
        "Also this week, one release changes the workflow. If you're interested, the link is in the description below. "
        "Also this week, another model adds a visible result. If you're interested, use the link in the description."
    )
    script = Script(
        title="Title", description="Description", tags=[], thumbnail_text="THE IMPORTANT CHANGE",
        beats=[ScriptBeat(id="beat_01", narration=narration, purpose="analysis", visual_direction="Show result")],
    )
    failures = _spoken_quality_failures(script, {
        "beat_min": 1, "beat_max": 1, "word_min": 20, "word_max": 80,
    })
    assert any("repetitive creator-style handoffs" in failure for failure in failures)


def test_spoken_quality_rejects_undocumented_first_person_testing():
    narration = (
        "I tested the model all weekend, and it made a huge difference. This is wild because the workflow now feels "
        "faster for everyone, even before we know whether the result holds up outside a demo."
    )
    script = Script(
        title="Title", description="Description", tags=[], thumbnail_text="THE IMPORTANT CHANGE",
        beats=[ScriptBeat(id="beat_01", narration=narration, purpose="analysis", visual_direction="Show result")],
    )
    failures = _spoken_quality_failures(script, {
        "beat_min": 1, "beat_max": 1, "word_min": 20, "word_max": 80,
    })

    assert any("first-person testing language" in failure for failure in failures)


def test_section_drafts_cannot_introduce_claims_from_another_chapter(monkeypatch):
    project = EpisodeProject(
        episode_id="sections", scheduled_date=date.today().isoformat(),
        brief=Brief(
            title="Title", thesis="Thesis", episode_format="deep_dive",
            source_ids=["source_1"], claim_ids=["claim_1", "claim_2"], why_now="Now",
        ),
        sources=[Source(id="source_1", title="Source", url="https://example.com")],
        claims=[
            Claim(id="claim_1", text="First fact", source_ids=["source_1"]),
            Claim(id="claim_2", text="Second fact", source_ids=["source_1"]),
        ],
        editorial_plan={
            "audience": {}, "teaching_contract": {},
            "outline": {"chapters": [{
                "id": "chapter_1", "title": "One", "function": "hook", "listener_question": "Why?",
                "payoff": "Answer", "claim_ids": ["claim_1"], "target_words": 50, "visual_mode": "source_ui",
            }]},
        },
    )
    monkeypatch.setattr("pipeline.editorial.call_openrouter", lambda *args, **kwargs: {"chapters": [{
        "id": "chapter_1", "spoken_draft": "word " * 50, "bridge_to_next": "Continue naturally.",
        "used_claim_ids": ["claim_2"], "humor_opportunity": "",
    }]})
    import pytest
    with pytest.raises(ValueError, match="outside its outline"):
        draft_researched_sections(project)


def test_humanizer_rewrites_delivery_without_changing_evidence_links(monkeypatch):
    original = Script(
        title="Title", description="Description", tags=[], thumbnail_text="THE IMPORTANT CHANGE",
        beats=[ScriptBeat(
            id="beat_01",
            narration=(
                "A clear result gives us somewhere useful to start. The evidence then shows why the workflow changed "
                "and where that change stops helping ordinary creators today."
            ),
            purpose="hook", visual_direction="Show the evidence", claim_ids=["claim_1"], source_ids=["source_1"],
        )],
    )
    project = EpisodeProject(
        episode_id="humanize_test", scheduled_date=date.today().isoformat(),
        sources=[Source(id="source_1", title="Source", url="https://example.com")],
        claims=[Claim(id="claim_1", text="Supported fact", source_ids=["source_1"])],
        editorial_plan={"teaching_contract": {"learning_goal": "Understand the change"}},
    )
    response = {
        "beats": [{
            "id": "beat_01",
            "narration": (
                "There's a useful result right at the start, and it changes how this workflow looks. "
                "Creators gain speed in one part of the process. The same evidence makes the important limit "
                "easier to see before anyone depends on it."
            ),
            "delivery": {
                "pace": "normal", "energy": "normal", "pause_before_ms": 0,
                "pause_after_ms": 450, "emphasis_words": ["limit"],
            },
        }],
    }
    monkeypatch.setattr("pipeline.editorial.call_openrouter", lambda *args, **kwargs: response)
    monkeypatch.setattr("pipeline.editorial.duration_profile", lambda _: {
        "beat_min": 1, "beat_max": 1, "word_min": 20, "word_max": 80,
    })

    rewritten = humanize_script(project, original)

    assert rewritten.beats[0].narration != original.beats[0].narration
    assert rewritten.beats[0].claim_ids == ["claim_1"]
    assert rewritten.beats[0].source_ids == ["source_1"]
    assert rewritten.beats[0].purpose == "hook"
