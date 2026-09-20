from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from pipeline import editorial, fidelity_loop, worker
from pipeline.fidelity_loop import (
    BudgetLimitExceeded,
    FidelityBudget,
    FidelityRun,
    ReferenceVideo,
    _accept_targeted_repair,
    _repair_visual_dimension,
    build_blind_packet,
    choose_lowest_dimension,
    record_milestone,
    score_script_dimensions,
    score_storyboard_dimensions,
    select_reference_videos,
)
from pipeline.models import Claim, EpisodeProject, Script, ScriptBeat, Shot, Source
from pipeline.viral_clips import CaptionCue
from pipeline.project_store import canonical_hash, load_project, save_project


def _reference(index: int, label: str = "explainer") -> ReferenceVideo:
    uploaded = date.today() - timedelta(days=index)
    return ReferenceVideo(
        video_id=f"video_{index:02d}", channel_id="channel", channel_handle="@channel",
        title=f"Reference {index}", url=f"https://youtube.com/watch?v=video_{index:02d}",
        upload_date=uploaded.strftime("%Y%m%d"), duration_seconds=600 + index,
        view_count=1000 * (index + 1), views_per_day=float((index + 1) * 100),
        format_label=label, transcript_available=True,
    )


def _script() -> Script:
    sentence = (
        "A documented model result changes a creator workflow, and the source gives us a concrete way to see why it matters. "
        "The short version is simple. Does that useful result survive an ordinary production limit? "
        "The evidence answers that question, explains the mechanism, and returns to the creator workflow before the verdict."
    )
    purposes = ["hook", "evidence", "analysis", "limitation", "comparison", "verdict"]
    beats = []
    for index in range(24):
        purpose = purposes[min(len(purposes) - 1, index * len(purposes) // 24)]
        beats.append(ScriptBeat(
            id=f"beat_{index:02d}", narration=sentence, purpose=purpose,
            visual_direction="Show the verified creator workflow and result",
            claim_ids=["claim_1"] if purpose not in {"analysis", "verdict"} else [],
            source_ids=["source_1"] if purpose not in {"analysis", "verdict"} else [],
        ))
    return Script(
        title="A useful model test", description="Evidence-backed test", tags=["AI"],
        thumbnail_text="THE REAL MODEL TEST", beats=beats,
    )


def _project() -> EpisodeProject:
    script = _script()
    shots = []
    for index in range(72):
        source = index % 3 == 0
        shots.append(Shot(
            id=f"shot_{index:03d}", beat_id=script.beats[index % len(script.beats)].id,
            asset_type="screen_recording" if source else "motion_graphic",
            duration_seconds=5, motion_style="locked" if source else "push_in",
            transition="cut",
        ))
    return EpisodeProject(
        episode_id="episode_fidelity", scheduled_date=date.today().isoformat(),
        sources=[Source(id="source_1", title="Source", url="https://example.com")],
        claims=[Claim(id="claim_1", text="Supported fact", source_ids=["source_1"])],
        script=script, shots=shots,
        editorial_plan={"fidelity_visual_overrides": {
            "typography_profile": "large_editorial", "palette_profile": "neutral_product_accent",
            "max_information_items": 3, "meaningful_state_change_seconds": 2.5,
        }},
    )


def test_reference_selection_keeps_twenty_newest_then_adds_format_diversity():
    labels = ["weekly_roundup", "tool_test", "deep_dive", "explainer"]
    candidates = [_reference(index, labels[index % len(labels)]) for index in range(40)]

    selected = select_reference_videos(candidates, count=30, transcript_required=True)

    assert len(selected) == 30
    assert [item.video_id for item in selected[:20]] == [f"video_{index:02d}" for index in range(20)]
    assert len({item.format_label for item in selected[20:]}) >= 3


def test_transcript_metrics_collapse_rolling_caption_overlap():
    cues = [
        CaptionCue(start_seconds=0, end_seconds=2, text="AI never sleeps and this week"),
        CaptionCue(start_seconds=1, end_seconds=3, text="this week has been absolutely insane."),
        CaptionCue(start_seconds=2, end_seconds=4, text="absolutely insane. The mysterious"),
        CaptionCue(start_seconds=3, end_seconds=5, text="The mysterious stealth model arrived."),
    ]

    metrics, excerpt, _digest = fidelity_loop._transcript_metrics(cues)

    assert excerpt == "AI never sleeps and this week has been absolutely insane. The mysterious stealth model arrived."
    assert metrics["word_count"] == 15


def test_storyboard_review_packet_is_compact_evenly_sampled_and_frame_honest():
    project = _project()
    project.editorial_plan["fidelity_visual_overrides"]["intra_shot_keyframes"] = [
        {"shot_id": shot.id, "seconds": [0, 2.2, shot.duration_seconds], "editorial_reason": "proof emphasis"}
        for shot in project.shots
    ]

    candidate = fidelity_loop._storyboard_review_candidate(project)

    assert candidate["candidate_frame_status"] == "not rendered at storyboard stage"
    assert len(candidate["stratified_shot_sample"]) <= 3 * len({shot.asset_type for shot in project.shots})
    assert candidate["visual_overrides"]["intra_shot_keyframes"]["count"] == len(project.shots)
    assert "shots" not in candidate


def test_reference_selection_fails_closed_when_transcripts_are_missing():
    candidates = [_reference(index) for index in range(29)]
    candidates[0].transcript_available = False

    with pytest.raises(RuntimeError, match="required 30"):
        select_reference_videos(candidates, count=30, transcript_required=True)


def test_budget_uses_larger_provider_fraction_and_blocks_projected_overspend():
    budget = FidelityBudget(
        openrouter_starting_balance_usd=100, magic_hour_starting_balance_credits=10_000,
        limit_fraction=0.30,
    )
    budget.record_openrouter({"cost": 12, "prompt_tokens": 100, "completion_tokens": 20}, 3)
    budget.record_magic_hour(2000)

    assert budget.consumed_fraction() == pytest.approx(0.20)
    assert budget.prompt_tokens == 100
    with pytest.raises(BudgetLimitExceeded):
        budget.assert_openrouter_estimate(19)
    with pytest.raises(BudgetLimitExceeded):
        budget.record_magic_hour(1001)
    assert budget.magic_hour_spend_credits == 3001


def test_absolute_provider_caps_do_not_require_invented_starting_balances(monkeypatch):
    monkeypatch.setattr(fidelity_loop, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(fidelity_loop, "MAGIC_HOUR_API_KEY", "magic-hour-key")

    budget = fidelity_loop._budget_snapshot(
        openrouter_absolute_cap_usd=10,
        magic_hour_absolute_cap_credits=15_000,
    )
    budget.record_openrouter({"cost": 2.5}, 3)
    budget.record_magic_hour(1000)

    assert budget.openrouter_starting_balance_usd == 0
    assert budget.magic_hour_starting_balance_credits == 0
    assert budget.caps() == {"openrouter_usd": 10, "magic_hour_credits": 15_000}
    assert budget.remaining_openrouter_cap() == pytest.approx(7.5)
    assert budget.remaining_magic_hour_cap() == 14_000
    assert budget.fractions() == pytest.approx({"openrouter": 0.25, "magic_hour": 1 / 15})


def test_lowest_dimension_tie_uses_distance_then_stable_order():
    scores = {"hook_style": 3, "sentence_rhythm": 3, "pacing": 4}
    assert choose_lowest_dimension(scores, {"hook_style": 0.2, "sentence_rhythm": 0.8}) == "sentence_rhythm"
    assert choose_lowest_dimension(scores) == "hook_style"


def test_blind_packet_order_is_stable_and_contains_no_iteration_metadata():
    profile = {
        "script": {name: {"rule": name} for name in fidelity_loop.SCRIPT_DIMENSIONS},
        "visual": {name: {"rule": name} for name in fidelity_loop.VISUAL_DIMENSIONS},
        "reference_clips": {"script": [
            {"video_id": f"ref_{index}", "timecodes": [10, 20], "transcript_segment": "Short transformed excerpt."}
            for index in range(4)
        ]},
        "originality": {"required": True},
    }
    candidate = {"title": "Anonymous draft", "iteration": 99, "_frame_strip_paths": ["private.jpg"]}

    first = build_blind_packet("script", candidate, profile, fidelity_loop.SCRIPT_DIMENSIONS)
    second = build_blind_packet("script", candidate, profile, fidelity_loop.SCRIPT_DIMENSIONS)

    assert first == second
    serialized = str(first)
    assert "_frame_strip_paths" not in serialized
    assert "authorship" not in serialized
    assert first["candidate_packet_id"] in {item["packet_id"] for item in first["packets"]}


def test_originality_report_rejects_verbatim_eight_word_reference_phrase(tmp_path):
    project = _project()
    phrase = " ".join(project.script.narration.split()[:8])
    profile = {
        "reference_clips": {
            "script": [{"video_id": "reference", "transcript_segment": phrase}],
            "visual": [],
        },
    }
    run = FidelityRun(run_id="originality_check")
    report = fidelity_loop.originality_report(project, profile, run)

    assert not report["passed"]
    assert report["script"]["matched_phrase_count"] >= 1
    assert report["visual"]["passed"]


def test_script_score_exposes_all_six_dimensions_and_rejects_generic_hook():
    script = _script()
    good = score_script_dimensions(script)
    script.beats[0].narration = "Welcome back. In this video, let's dive into a game-changer."
    script.beats[0].claim_ids = []
    bad = score_script_dimensions(script)

    assert set(good) == set(fidelity_loop.SCRIPT_DIMENSIONS)
    assert bad["hook_style"] < good["hook_style"]


def test_sentence_rhythm_repair_changes_boundaries_but_preserves_factual_tokens():
    script = _script()
    script.beats[1].narration = (
        "The official source documents the first result, and the same source explains the practical limit for ordinary creators."
    )
    before_hook = script.beats[0].narration
    before_tokens = re.findall(r"[a-z0-9]+", script.beats[1].narration.casefold())

    repaired = fidelity_loop._punctuation_only_rhythm_repair(script)
    after_tokens = re.findall(r"[a-z0-9]+", repaired.beats[1].narration.casefold())

    assert repaired.beats[0].narration == before_hook
    assert repaired.beats[1].narration != script.beats[1].narration
    assert after_tokens == before_tokens
    assert fidelity_loop._fact_locked_script_equivalent(script, repaired)
    repaired.beats[1].claim_ids = []
    assert not fidelity_loop._fact_locked_script_equivalent(script, repaired)


def test_question_repair_uses_existing_words_and_only_changes_punctuation():
    script = _script()
    script.beats[0].narration = "The real question is which documented result survives the production limit."

    repaired = fidelity_loop._punctuation_only_question_repair(script)

    assert repaired.beats[0].narration.endswith("?")
    assert fidelity_loop._fact_locked_script_equivalent(script, repaired)


def test_callback_repair_reuses_only_an_example_covered_by_target_claims():
    script = _script()
    source = script.beats[5]
    source.purpose = "model_test"
    source.claim_ids = ["claim_1"]
    source.narration = "Then stack a second instruction. Add rain. The documented workflow keeps the earlier result."
    target = script.beats[-1]
    target.purpose = "verdict"
    target.claim_ids = ["claim_1"]
    target.narration = "Use the workflow only when the first result is worth keeping."

    repaired = fidelity_loop._evidence_copied_callback_repair(script)

    assert "Remember that earlier example:" in repaired.beats[-1].narration
    assert fidelity_loop._evidence_copied_callback_safe(script, repaired)
    repaired.beats[-1].claim_ids = []
    assert not fidelity_loop._evidence_copied_callback_safe(script, repaired)


def test_visual_repair_changes_only_requested_policy_area():
    project = _project()
    project.editorial_plan["fidelity_visual_overrides"].pop("palette_profile")
    before_shots = [shot.model_dump(mode="json") for shot in project.shots]

    repaired = _repair_visual_dimension(project, "color_palette")

    assert repaired.editorial_plan["fidelity_visual_overrides"]["palette_profile"] == "neutral_product_accent"
    assert [shot.model_dump(mode="json") for shot in repaired.shots] == before_shots
    assert "palette_profile" not in project.editorial_plan["fidelity_visual_overrides"]


def test_targeted_storyboard_review_freezes_unedited_blind_dimensions(monkeypatch):
    project = _project()
    base_scores = {name: 4 for name in fidelity_loop.VISUAL_DIMENSIONS}
    before = fidelity_loop.FidelityScorecard(
        stage="storyboard", deterministic={name: 5 for name in fidelity_loop.VISUAL_DIMENSIONS},
        blind_review=base_scores, final=base_scores,
        distance_from_reference={name: 0.1 for name in fidelity_loop.VISUAL_DIMENSIONS},
        notes={name: "frozen" for name in fidelity_loop.VISUAL_DIMENSIONS},
    )
    monkeypatch.setattr(
        fidelity_loop, "_blind_review",
        lambda _stage, _candidate, _profile, dimensions: (
            {dimensions[0]: 5}, {dimensions[0]: "improved"},
        ),
    )
    repaired = fidelity_loop._repair_visual_dimension(project, "motion_style")

    after = fidelity_loop.score_storyboard_targeted(
        repaired, {"visual": {name: {"references": []} for name in fidelity_loop.VISUAL_DIMENSIONS}},
        before, "motion_style",
    )

    assert after.final["motion_style"] == 5
    assert all(
        after.blind_review[name] == before.blind_review[name]
        for name in fidelity_loop.VISUAL_DIMENSIONS if name != "motion_style"
    )


def test_storyboard_score_reaches_profile_floor_for_compliant_plan():
    scores = score_storyboard_dimensions(_project())

    assert set(scores) == set(fidelity_loop.VISUAL_DIMENSIONS)
    assert scores["typography"] == 5
    assert scores["motion_style"] == 5
    assert scores["color_palette"] == 5
    assert scores["information_density"] == 5


def test_targeted_repair_rejects_non_target_regression():
    before = fidelity_loop.FidelityScorecard(
        stage="script", deterministic={}, blind_review={},
        final={"hook_style": 3, "pacing": 5}, artifact_sha256="before",
    )
    after = fidelity_loop.FidelityScorecard(
        stage="script", deterministic={}, blind_review={},
        final={"hook_style": 4, "pacing": 4}, artifact_sha256="after",
    )

    accepted, reason = _accept_targeted_repair(before, after, "hook_style")

    assert not accepted
    assert "pacing" in reason


def test_progress_records_each_milestone_once(monkeypatch, tmp_path):
    monkeypatch.setattr(fidelity_loop, "FIDELITY_PROGRESS_PATH", tmp_path / "progress.md")
    monkeypatch.setattr(fidelity_loop, "FIDELITY_DATA_DIR", tmp_path / "runs")
    run = FidelityRun(run_id="fidelity_test")

    record_milestone(run, "pattern_library_finalized", "profile.json")
    record_milestone(run, "pattern_library_finalized", "profile.json")

    progress = (tmp_path / "progress.md").read_text(encoding="utf-8")
    assert progress.count("## Pattern library finalized") == 1
    assert len(run.milestones) == 1


def test_openrouter_usage_hook_receives_exact_response_usage(monkeypatch):
    class Response:
        ok = True
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {
                "id": "generation_1", "usage": {"cost": 0.25, "prompt_tokens": 10, "completion_tokens": 5},
                "choices": [{"message": {"content": '{"ok":true}'}}],
            }

    events = []
    monkeypatch.setattr(editorial, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(editorial.requests, "post", lambda *args, **kwargs: Response())
    with editorial.capture_openrouter_usage(events.append):
        result = editorial.call_openrouter(
            "test/model", "system", "user",
            {"type": "json_schema", "json_schema": {"name": "Test", "strict": True, "schema": {}}},
        )

    assert result == {"ok": True}
    assert [event["phase"] for event in events] == ["before", "after"]
    assert events[-1]["usage"]["cost"] == 0.25


def test_adaptive_budget_guard_bounds_late_request_with_current_model_pricing(monkeypatch):
    monkeypatch.setattr(
        fidelity_loop, "_openrouter_pricing",
        lambda _model: {"prompt": 0.000001, "completion": 0.0001, "request": 0, "image": 0},
    )
    run = FidelityRun(
        run_id="adaptive_guard",
        budget=FidelityBudget(
            openrouter_absolute_cap_usd=10,
            magic_hour_absolute_cap_credits=15_000,
            openrouter_spend_usd=9.5,
        ),
    )
    guard = fidelity_loop.OpenRouterBudgetGuard(run, adaptive=True)

    adjustment = guard({
        "phase": "before", "model": "test/model", "max_tokens": 16_000,
        "input_characters": 1000, "input_bytes": 1000, "input_images": 0,
    })

    assert adjustment["max_tokens"] < 5000
    assert adjustment["provider"]["sort"] == "price"
    assert guard.pending_estimate <= run.budget.remaining_openrouter_cap()


def test_predictive_budget_hold_resumes_with_explicitly_higher_absolute_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(fidelity_loop, "FIDELITY_DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(fidelity_loop, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(fidelity_loop, "MAGIC_HOUR_API_KEY", "magic-key")
    run = FidelityRun(
        run_id="raised_cap",
        status="predictive_budget_hold",
        stop_reason="predictive_budget_hold",
        budget=FidelityBudget(
            openrouter_absolute_cap_usd=10,
            magic_hour_absolute_cap_credits=15_000,
            openrouter_spend_usd=9.5,
        ),
    )
    fidelity_loop.save_fidelity_run(run)

    def stop_after_resume(*_args, **_kwargs):
        raise RuntimeError("resumed")

    monkeypatch.setattr(fidelity_loop, "build_reference_corpus", stop_after_resume)
    result = fidelity_loop.run_fidelity_loop({
        "run_id": "raised_cap",
        "openrouter_max_spend_usd": 15,
        "magic_hour_max_credits": 15_000,
        "adaptive_budget": True,
    })
    saved = fidelity_loop.load_fidelity_run("raised_cap")

    assert result["status"] == "blocked"
    assert saved.budget.openrouter_absolute_cap_usd == 15
    assert saved.budget.openrouter_spend_usd == 9.5
    assert saved.artifacts["openrouter_cap_authorization"] == "raised_from_usd_10.000000_to_usd_15.000000"


def test_resumed_absolute_cap_cannot_be_lowered_by_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(fidelity_loop, "FIDELITY_DATA_DIR", tmp_path / "runs")
    run = FidelityRun(
        run_id="monotonic_cap",
        status="budget_limit",
        stop_reason="budget_limit",
        budget=FidelityBudget(openrouter_absolute_cap_usd=15, openrouter_spend_usd=14),
    )
    fidelity_loop.save_fidelity_run(run)

    result = fidelity_loop.run_fidelity_loop({
        "run_id": "monotonic_cap",
        "openrouter_max_spend_usd": 10,
        "adaptive_budget": False,
    })
    saved = fidelity_loop.load_fidelity_run("monotonic_cap")

    assert result["status"] == "budget_limit"
    assert saved.budget.openrouter_absolute_cap_usd == 15


def test_integrated_round_refuses_manual_approval_when_fact_check_fails(monkeypatch, tmp_path):
    project = _project()
    monkeypatch.setattr(fidelity_loop, "EPISODE_DATA_DIR", tmp_path / "episodes")
    save_project(project, tmp_path / "episodes" / project.episode_id)
    monkeypatch.setattr(
        editorial,
        "verify_script",
        lambda _project: {"passed": False, "unsupported": ["unsupported claim"]},
    )
    monkeypatch.setattr(
        editorial,
        "review_script_quality",
        lambda _project: {"passed": True, "issues": []},
    )
    monkeypatch.setattr(fidelity_loop, "OPENROUTER_API_KEY", "test-key")
    run = FidelityRun(
        run_id="pre_render_fact_gate",
        budget=FidelityBudget(
            openrouter_absolute_cap_usd=15,
            magic_hour_absolute_cap_credits=15_000,
        ),
    )

    with pytest.raises(RuntimeError, match="failed factual or spoken-quality verification"):
        fidelity_loop._produce_integrated_round(
            run,
            project,
            fidelity_loop.OpenRouterBudgetGuard(run, adaptive=True),
        )

    saved = load_project(tmp_path / "episodes" / project.episode_id)
    assert saved.status == "script_revision_required"
    assert saved.qc["fact_check"]["passed"] is False
    assert "script_manual_approval" not in saved.qc


def test_worker_routes_fidelity_loop_stage(monkeypatch):
    monkeypatch.setattr(worker, "run_fidelity_loop", lambda payload, **kwargs: {"run_id": payload["run_id"]})

    result = worker._execute("run_fidelity_loop", {"run_id": "fidelity_route"})

    assert result == {"run_id": "fidelity_route"}


def test_worker_routes_free_fidelity_reference_stage(monkeypatch):
    monkeypatch.setattr(
        worker, "build_fidelity_reference_profile",
        lambda payload, **kwargs: {"run_id": payload["run_id"], "budget": None},
    )

    result = worker._execute("build_fidelity_reference_profile", {"run_id": "reference_route"})

    assert result == {"run_id": "reference_route", "budget": None}


def test_missing_openrouter_key_stops_before_corpus_refresh(monkeypatch, tmp_path):
    touched = []
    monkeypatch.setattr(fidelity_loop, "FIDELITY_DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(fidelity_loop, "FIDELITY_PROGRESS_PATH", tmp_path / "progress.md")
    monkeypatch.setattr(fidelity_loop, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(fidelity_loop, "OPENROUTER_STARTING_BALANCE_USD", 0.0)
    monkeypatch.setattr(fidelity_loop, "MAGIC_HOUR_STARTING_BALANCE_CREDITS", 0)
    monkeypatch.setattr(
        fidelity_loop, "build_reference_corpus",
        lambda *args, **kwargs: touched.append(True),
    )

    result = fidelity_loop.run_fidelity_loop({"run_id": "preflight_test", "render_episode": False})

    assert result["status"] == "blocked"
    assert "OPENROUTER_API_KEY" in result["errors"][-1]
    assert touched == []
    assert not (tmp_path / "progress.md").exists()


def test_free_reference_profile_does_not_require_or_create_provider_budget(monkeypatch, tmp_path):
    monkeypatch.setattr(fidelity_loop, "FIDELITY_DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(fidelity_loop, "FIDELITY_PROGRESS_PATH", tmp_path / "progress.md")
    monkeypatch.setattr(fidelity_loop, "FIDELITY_PROFILE_PATH", tmp_path / "profile.json")
    called = {"corpus": 0, "profile": 0}

    def fake_corpus(run, **_kwargs):
        called["corpus"] += 1
        target = tmp_path / "corpus.json"
        payload = {"channels": {}}
        target.write_text(json.dumps(payload), encoding="utf-8")
        run.corpus_path = str(target)
        run.corpus_sha256 = fidelity_loop._canonical_sha256(payload)
        fidelity_loop.save_fidelity_run(run)
        return payload

    def fake_profile(run, _corpus):
        called["profile"] += 1
        profile = {"schema_version": "1.0"}
        (tmp_path / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
        run.pattern_library_path = str(tmp_path / "profile.json")
        run.pattern_library_sha256 = fidelity_loop._canonical_sha256(profile)
        fidelity_loop.record_milestone(run, "pattern_library_finalized", run.pattern_library_path)
        return profile

    monkeypatch.setattr(fidelity_loop, "build_reference_corpus", fake_corpus)
    monkeypatch.setattr(fidelity_loop, "build_pattern_library", fake_profile)

    result = fidelity_loop.build_fidelity_reference_profile({"run_id": "free_reference"})

    assert result["status"] == "pattern_library_finalized"
    assert result["stop_reason"] == "awaiting_paid_budget_preflight"
    assert result["budget"] is None
    assert called == {"corpus": 1, "profile": 1}


def test_cached_reference_profile_enriches_missing_frame_strips_and_rebuilds_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(fidelity_loop, "FIDELITY_DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(fidelity_loop, "FIDELITY_PROGRESS_PATH", tmp_path / "progress.md")
    monkeypatch.setattr(fidelity_loop, "FIDELITY_PROFILE_PATH", tmp_path / "profile.json")
    run = FidelityRun(run_id="cached_reference")
    channels = {}
    for key, channel in fidelity_loop.CHANNELS.items():
        item = _reference(0)
        item.video_id = f"{key}_video"
        item.channel_id = channel["channel_id"]
        item.channel_handle = channel["handle"]
        channels[key] = {**channel, "videos": [item.model_dump(mode="json")]}
    corpus = {"schema_version": "1.0", "channels": channels}
    corpus_path = tmp_path / "runs" / run.run_id / "reference_corpus.json"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps({"stale": True}), encoding="utf-8")
    run.corpus_path = str(corpus_path)
    run.pattern_library_path = str(profile_path)
    fidelity_loop.save_fidelity_run(run)

    def fake_strip(record, channel_key):
        target = tmp_path / f"{channel_key}_{record.video_id}.jpg"
        target.write_bytes(b"frame-strip" * 200)
        return str(target)

    rebuilt = []

    def fake_profile(current_run, refreshed_corpus):
        rebuilt.append(refreshed_corpus)
        profile = {"corpus_sha256": fidelity_loop._canonical_sha256(refreshed_corpus)}
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        current_run.pattern_library_path = str(profile_path)
        current_run.pattern_library_sha256 = fidelity_loop._canonical_sha256(profile)
        fidelity_loop.record_milestone(
            current_run, "pattern_library_finalized", current_run.pattern_library_path,
        )
        return profile

    monkeypatch.setattr(fidelity_loop, "_extract_public_frame_strip", fake_strip)
    monkeypatch.setattr(fidelity_loop, "build_pattern_library", fake_profile)

    result = fidelity_loop.build_fidelity_reference_profile({
        "run_id": run.run_id, "frame_strips_per_channel": 1,
    })
    refreshed = json.loads(corpus_path.read_text(encoding="utf-8"))

    assert result["status"] == "pattern_library_finalized"
    assert len(rebuilt) == 1
    assert all(
        Path(refreshed["channels"][key]["videos"][0]["analysis_frame_strip"]).is_file()
        for key in fidelity_loop.CHANNELS
    )
    assert (json.loads(profile_path.read_text(encoding="utf-8"))["corpus_sha256"]
            == fidelity_loop._canonical_sha256(refreshed))


def _perfect_card(stage: str, artifact_sha256: str = "") -> fidelity_loop.FidelityScorecard:
    dimensions = (
        fidelity_loop.SCRIPT_DIMENSIONS if stage == "script"
        else fidelity_loop.VISUAL_DIMENSIONS if stage == "storyboard"
        else fidelity_loop.ALL_DIMENSIONS
    )
    scores = {name: 5 for name in dimensions}
    return fidelity_loop.FidelityScorecard(
        stage=stage, deterministic=scores, blind_review=scores, final=scores,
        distance_from_reference={name: 0.0 for name in dimensions},
        artifact_sha256=artifact_sha256,
    )


def test_mocked_full_fidelity_run_reaches_perfect_and_resume_is_noop(monkeypatch, tmp_path):
    run_root = tmp_path / "runs"
    episode_root = tmp_path / "episodes"
    profile_path = tmp_path / "channel_fidelity_profile.json"
    progress_path = tmp_path / "progress.md"
    monkeypatch.setattr(fidelity_loop, "FIDELITY_DATA_DIR", run_root)
    monkeypatch.setattr(fidelity_loop, "EPISODE_DATA_DIR", episode_root)
    monkeypatch.setattr(fidelity_loop, "FIDELITY_PROFILE_PATH", profile_path)
    monkeypatch.setattr(fidelity_loop, "FIDELITY_PROGRESS_PATH", progress_path)
    monkeypatch.setattr(fidelity_loop, "OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setattr(fidelity_loop, "MAGIC_HOUR_API_KEY", "test-magic-hour-key")

    def fake_corpus(run, **_kwargs):
        channels = {}
        for key, channel in fidelity_loop.CHANNELS.items():
            videos = []
            for index in range(30):
                item = _reference(index, ["tool_test", "weekly_roundup", "deep_dive"][index % 3])
                item.channel_id = channel["channel_id"]
                item.channel_handle = channel["handle"]
                item.transcript_metrics = {
                    "mean_sentence_words": 16, "sentence_word_stdev": 8,
                    "questions_per_1000_words": 4,
                }
                item.visual_timecodes = [10, 30, 60]
                videos.append(item.model_dump(mode="json"))
            channels[key] = {**channel, "videos": videos}
        payload = {"schema_version": "1.0", "channels": channels}
        target = run_root / run.run_id / "reference_corpus.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")
        run.corpus_path = str(target)
        run.corpus_sha256 = fidelity_loop._canonical_sha256(payload)
        run.artifacts["reference_corpus"] = str(target)
        fidelity_loop.save_fidelity_run(run)
        return payload

    project = _project()
    project.qc["final"] = {"passed": True}
    video = tmp_path / "pilot.mp4"
    video.write_bytes(b"verified-private-preview")
    project.artifacts["video"] = str(video)

    def fake_pilot(run):
        run.pilot_episode_id = project.episode_id
        save_project(project, episode_root / project.episode_id)
        fidelity_loop.save_fidelity_run(run)
        return project.model_copy(deep=True)

    calls = {"produce": 0, "integrated": 0}

    def fake_produce(_run, current, _guard, **_kwargs):
        calls["produce"] += 1
        current.qc["final"] = {"passed": True}
        current.artifacts["video"] = str(video)
        save_project(current, episode_root / current.episode_id)
        return current

    def fake_script_score(script, _profile):
        return _perfect_card("script", canonical_hash(script.model_dump(mode="json")))

    def fake_storyboard_score(current, _profile):
        payload = {
            "shots": [shot.model_dump(mode="json") for shot in current.shots],
            "visual_overrides": current.editorial_plan.get("fidelity_visual_overrides") or {},
        }
        return _perfect_card("storyboard", canonical_hash(payload))

    def fake_integrated(_project_value, _profile, _run):
        calls["integrated"] += 1
        return _perfect_card("integrated", "integrated-perfect")

    monkeypatch.setattr(fidelity_loop, "build_reference_corpus", fake_corpus)
    monkeypatch.setattr(fidelity_loop, "_create_or_select_pilot", fake_pilot)
    monkeypatch.setattr(fidelity_loop, "_produce_integrated_round", fake_produce)
    monkeypatch.setattr(fidelity_loop, "score_script", fake_script_score)
    monkeypatch.setattr(fidelity_loop, "score_storyboard", fake_storyboard_score)
    monkeypatch.setattr(fidelity_loop, "score_integrated", fake_integrated)
    monkeypatch.setattr(
        fidelity_loop, "integrated_verification_gates",
        lambda *_args, **_kwargs: {"passed": True, "checks": {}, "failed_checks": []},
    )

    payload = {
        "run_id": "mocked_perfect", "render_episode": True,
        "openrouter_starting_balance_usd": 100,
        "magic_hour_starting_balance_credits": 10_000,
    }
    first = fidelity_loop.run_fidelity_loop(payload)
    second = fidelity_loop.run_fidelity_loop(payload)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    assert first["status"] == "perfect_fidelity"
    assert first["stop_reason"] == "perfect_fidelity"
    assert set(first["scores"]["integrated"].values()) == {5}
    assert [item["name"] for item in first["milestones"]] == list(fidelity_loop.MILESTONES)
    assert progress_path.read_text(encoding="utf-8").count("\n## ") == 4
    assert calls == {"produce": 1, "integrated": 1}
    assert second["status"] == "perfect_fidelity"
    assert all(
        pattern.get("observed_range") and len(pattern.get("supporting_evidence", [])) >= 4
        and all(evidence.get("video_id") and evidence.get("timecodes") for evidence in pattern["supporting_evidence"])
        for section in ("script", "visual")
        for pattern in profile[section].values()
    )


def test_budget_guard_stops_after_single_underestimated_provider_call(monkeypatch, tmp_path):
    monkeypatch.setattr(fidelity_loop, "FIDELITY_DATA_DIR", tmp_path / "runs")
    monkeypatch.setattr(editorial, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(fidelity_loop, "OPENROUTER_FIDELITY_MAX_REQUEST_USD", 3.0)
    run = FidelityRun(
        run_id="budget_undershoot",
        budget=FidelityBudget(
            openrouter_starting_balance_usd=100,
            magic_hour_starting_balance_credits=10_000,
            limit_fraction=0.30,
        ),
    )
    posts = []

    class Response:
        ok = True
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {
                "id": "over-cap", "usage": {"cost": 31},
                "choices": [{"message": {"content": '{"ok":true}'}}],
            }

    monkeypatch.setattr(
        editorial.requests, "post",
        lambda *args, **kwargs: posts.append((args, kwargs)) or Response(),
    )
    guard = fidelity_loop.OpenRouterBudgetGuard(run)

    with pytest.raises(BudgetLimitExceeded):
        with editorial.capture_openrouter_usage(guard):
            editorial.call_openrouter(
                "test/model", "system", "user",
                {"type": "json_schema", "json_schema": {"name": "Test", "strict": True, "schema": {}}},
            )

    assert len(posts) == 1
    assert run.budget.openrouter_spend_usd == 31
    assert run.status == "budget_limit"


def test_reference_cache_reuses_unchanged_videos_and_refreshes_changed_listing(monkeypatch, tmp_path):
    monkeypatch.setattr(fidelity_loop, "FIDELITY_DATA_DIR", tmp_path / "runs")
    entries_by_channel = {
        channel["url"]: [
            {
                "id": f"{key}_{index:02d}", "title": f"Reference {index}",
                "duration": 600 + index, "upload_date": (date.today() - timedelta(days=index)).strftime("%Y%m%d"),
                "url": f"https://youtube.com/watch?v={key}_{index:02d}",
            }
            for index in range(30)
        ]
        for key, channel in fidelity_loop.CHANNELS.items()
    }
    hydrate_calls = []

    monkeypatch.setattr(
        fidelity_loop, "_discover_entries",
        lambda target, _maximum: [dict(item) for item in entries_by_channel[target]],
    )
    monkeypatch.setattr(
        fidelity_loop, "_hydrate",
        lambda url: hydrate_calls.append(url) or {
            "id": url.rsplit("=", 1)[-1], "title": "Hydrated", "duration": 600,
        },
    )

    def fake_reference(metadata, channel, _cache_dir):
        index = int(str(metadata["id"]).rsplit("_", 1)[-1])
        item = _reference(index, ["tool_test", "weekly_roundup", "deep_dive"][index % 3])
        item.video_id = str(metadata["id"])
        item.channel_id = channel["channel_id"]
        item.channel_handle = channel["handle"]
        item.url = f"https://youtube.com/watch?v={item.video_id}"
        item.content_sha256 = f"content-{item.video_id}"
        return item

    monkeypatch.setattr(fidelity_loop, "_reference_from_metadata", fake_reference)
    monkeypatch.setattr(fidelity_loop, "_extract_public_frame_strip", lambda *_args: "")

    first = FidelityRun(run_id="cache_first")
    fidelity_loop.build_reference_corpus(first, count=30)
    assert len(hydrate_calls) == 60

    hydrate_calls.clear()
    second = FidelityRun(run_id="cache_second")
    fidelity_loop.build_reference_corpus(second, count=30)
    assert hydrate_calls == []

    changed_channel = fidelity_loop.CHANNELS["ai_labs"]["url"]
    entries_by_channel[changed_channel][0]["title"] = "Changed title"
    third = FidelityRun(run_id="cache_third")
    fidelity_loop.build_reference_corpus(third, count=30)
    assert hydrate_calls == [entries_by_channel[changed_channel][0]["url"]]
