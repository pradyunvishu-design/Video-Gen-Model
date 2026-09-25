"""Cross-topic contracts; mocked providers are not a writing-quality benchmark."""
import copy

import pytest
from pydantic import ValidationError

from pipeline import editorial
from pipeline.models import EpisodeProject, Script
from pipeline.script_profiles import ScriptProfile, resolve_contract, script_input_hash
from pipeline import general_scripting as general


def project_for(format="explainer", niche="astronomy", minutes=8):
    return EpisodeProject.model_validate({
        "episode_id": "general_test", "scheduled_date": "2026-09-25",
        "episode": {"target_minutes": minutes},
        "script_profile": {"niche": niche, "subject": "How to understand the evidence",
                           "format": format, "audience": "curious beginners",
                           "viewer_payoff": "Explain the idea without jargon"},
        "brief": {"title": "A concrete question", "thesis": "Evidence before conclusions",
                  "episode_format": "deep_dive", "source_ids": ["s1"], "claim_ids": ["c1"],
                  "why_now": "Evergreen", "approved": True},
        "sources": [{"id": "s1", "title": "Source", "url": "https://example.org/evidence",
                     "source_type": "primary", "text": "A documented observation."}],
        "claims": [{"id": "c1", "text": "A documented observation.", "source_ids": ["s1"]}],
    })


@pytest.mark.parametrize("format,niche", [
    ("explainer", "astronomy"), ("tutorial", "cooking"), ("comparison", "photography"),
    ("history", "architecture"), ("science", "ecology"), ("case_study", "business"),
    ("documentary", "sports"), ("news", "local transport"),
])
def test_cross_topic_contract(format, niche):
    p = project_for(format, niche)
    contract = resolve_contract(p)
    assert contract["profile"]["niche"] == niche
    assert contract["profile"]["format"] == format
    assert len(contract["playbook"]["sequence"]) >= 4
    serialized = str(contract)
    assert "ComfyUI" not in serialized
    assert "THE WEEK IN AI" not in serialized
    assert contract["timing_status"] == "awaiting_actual_timeline"


def test_legacy_remains_opt_in():
    p = project_for(minutes=5)
    p.script_profile = None
    assert editorial.duration_profile(p)["word_min"] == 600


@pytest.mark.parametrize("field,value", [("format", "fiction"), ("niche", "  "),
                                         ("unknown_setting", True), ("words_per_minute", 0)])
def test_invalid_profile(field, value):
    data = project_for().script_profile.model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        ScriptProfile.model_validate(data)


def test_length_scales_and_rejects_non_finite():
    p = project_for(minutes=15)
    assert editorial.duration_profile(p)["outline_target"] == 2175
    p.episode["target_minutes"] = float("nan")
    with pytest.raises(ValueError):
        resolve_contract(p)


def test_cache_changes_with_profile_and_evidence_not_capture():
    p = project_for()
    baseline = script_input_hash(p)
    p.sources[0].capture_status = "complete"
    assert script_input_hash(p) == baseline
    p.sources[0].text += " A correction."
    assert script_input_hash(p) != baseline
    changed = script_input_hash(p)
    p.script_profile.audience = "working researchers"
    assert script_input_hash(p) != changed


def test_preflight_before_any_paid_call(monkeypatch):
    monkeypatch.setattr(editorial, "call_openrouter", lambda *a, **kw: pytest.fail("paid call"))
    p = project_for()
    p.brief.approved = False
    with pytest.raises(PermissionError):
        editorial.build_editorial_plan(p)
    p.brief.approved = True
    p.claims[0].source_ids = ["missing"]
    with pytest.raises(ValueError):
        editorial.build_editorial_plan(p)


def script():
    return Script.model_validate({
        "title": "A concrete question", "description": "Evidence", "tags": [],
        "thumbnail_text": "Follow The Evidence", "beats": [
            {"id": "b1", "narration": "We tested this ourselves.", "purpose": "model_test",
             "visual_direction": "Source", "claim_ids": ["c1"], "source_ids": ["s1"]},
        ],
    })


def test_model_test_label_does_not_prove_hands_on():
    p = project_for()
    failures = general.validate_draft(p, script())
    assert any("first-person" in f for f in failures)


def test_reviewer_failure_cannot_be_overridden(monkeypatch):
    p = project_for()
    p.script = script()
    monkeypatch.setattr(editorial, "call_openrouter", lambda *a, **kw: {
        "passed": False, "unsupported": ["unsupported comparison"], "corrections": [], "visual_gaps": [],
        "detected_risk_domain": "general", "human_expert_review_required": False})
    result = editorial.verify_script(p)
    assert result["passed"] is False
    assert result["unsupported"] == ["unsupported comparison"]


def test_humanizer_preserves_evidence_and_order(monkeypatch):
    p = project_for("tutorial")
    original = script()
    monkeypatch.setattr(editorial, "call_openrouter", lambda *a, **kw: {"beats": [
        {"id": "wrong", "narration": "New", "delivery": original.beats[0].delivery.model_dump()}]})
    with pytest.raises(ValueError, match="order"):
        editorial.humanize_script(p, original)


def test_tutorial_and_history_differ():
    tutorial = resolve_contract(project_for("tutorial"))
    history = resolve_contract(project_for("history"))
    assert "First/Next" in tutorial["playbook"]["guidance"]
    assert "dialogue" in history["playbook"]["guidance"]


def test_stale_plan_not_reused(monkeypatch):
    p = project_for()
    p.editorial_plan = {"script_input_hash": script_input_hash(p), "outline": {"old": True}}
    p.script_profile.niche = "history"
    calls = []
    def stop(*args, **kwargs):
        calls.append(args)
        raise RuntimeError("fresh plan requested")
    monkeypatch.setattr(editorial, "call_openrouter", stop)
    with pytest.raises(RuntimeError, match="fresh plan"):
        editorial.write_script(p)
    assert calls
    assert "old" not in str(p.editorial_plan)


def valid_script():
    # A transport fixture, not a claim that this deliberately repetitive prose is good writing.
    result = script()
    result.beats = [result.beats[0].model_copy(deep=True) for _ in range(3)]
    for i, beat in enumerate(result.beats):
        beat.id = f"b{i}"
        beat.purpose = "hook" if i == 0 else "evidence"
        beat.narration = " ".join(["evidence"] * 48) + "."
    return result


def provider_responses():
    s = valid_script()
    return {
        "AudienceTranslation": {"thesis": "Question", "viewer_promise": "Understanding", "why_care": "Useful",
                                "terms": [], "examples": [], "limitations": [], "unknowns": []},
        "OpeningLab": {"candidates": [
            {"id": f"o{i}", "mode": mode, "opening": " ".join(["opening"] * 35), "claim_ids": ["c1"],
             "proof_target": "source", "promise": "explain", "risk": "none"}
            for i, mode in enumerate(["context_reversal", "relatable_friction", "demonstration_first", "verdict_first"])],
            "selected_id": "o0", "selection_reason": "Evidence"},
        "SpeechOutline": {"chapters": [
            {"id": f"ch{i}", "title": "Chapter", "function": "evidence", "listener_question": "Why?",
             "payoff": "Explain", "claim_ids": ["c1"], "target_words": 48, "visual_mode": "source_document"}
            for i in range(3)]},
        "ResearchedSectionDrafts": {"chapters": [
            {"id": f"ch{i}", "spoken_draft": " ".join(["draft"] * 48), "bridge_to_next": "Because",
             "used_claim_ids": ["c1"], "humor_opportunity": ""} for i in range(3)]},
        "EpisodeScript": s.model_dump(mode="json"),
        "HumanSpokenRewrite": {"beats": [
            {"id": b.id, "narration": b.narration, "delivery": b.delivery.model_dump()} for b in s.beats]},
        "GeneralScriptVerification": {"passed": True, "unsupported": [], "corrections": [], "visual_gaps": [],
                                      "detected_risk_domain": "general", "human_expert_review_required": False},
        "SpokenScriptQuality": {"passed": True, "scores": {k: 9 for k in
            editorial.QUALITY_SCHEMA["json_schema"]["schema"]["properties"]["scores"]["required"]}, "issues": []},
    }


def mock_provider(monkeypatch, responses=None):
    responses = responses or provider_responses()
    calls = []
    def call(model, system, user, schema, **kwargs):
        import json
        body = json.loads(user)
        name = schema["json_schema"]["name"]
        calls.append((name, system, body))
        return copy.deepcopy(responses[name])
    monkeypatch.setattr(editorial, "call_openrouter", call)
    return calls


@pytest.mark.parametrize("format,niche", [("science", "ecology"), ("history", "architecture"),
                                         ("tutorial", "cooking"), ("comparison", "photography"),
                                         ("case_study", "business"), ("documentary", "sports"),
                                         ("explainer", "astronomy"), ("news", "transport")])
def test_complete_writer_room_and_resume(monkeypatch, format, niche):
    p = project_for(format, niche, minutes=1)
    calls = mock_provider(monkeypatch)
    result, verification, revisions = editorial.write_verified_script(p, max_revisions=0)
    assert verification["passed"] and revisions == 0
    assert result.word_count == 144
    assert len(calls) == 8
    for name, system, body in calls:
        assert body["contract"]["profile"]["niche"] == niche
        assert "ComfyUI" not in str(body)
        assert "AI-media news" not in system
        if name in {"GeneralScriptVerification", "SpokenScriptQuality"}:
            assert set(body["material"]) == {"script", "evidence"}
            assert "previous_script" not in body["material"]
    # Simulate serialization/restart: completed requests are reused.
    resumed = EpisodeProject.model_validate_json(p.model_dump_json())
    editorial.write_verified_script(resumed, max_revisions=0)
    assert len(calls) == 8
    assert verification["quality_review"]["opening_retention"]["passed"] is None


def test_bad_response_repaired_without_poisoning_cache(monkeypatch):
    import json
    p = project_for(minutes=1)
    responses = provider_responses()
    calls = []
    def call(model, system, user, schema, **kwargs):
        name = schema["json_schema"]["name"]
        calls.append(name)
        result = copy.deepcopy(responses[name])
        if name == "SpeechOutline" and calls.count(name) == 1:
            result["chapters"][0]["claim_ids"] = ["invented"]
        elif name == "SpeechOutline":
            assert "correction" in json.loads(user)
        return result
    monkeypatch.setattr(editorial, "call_openrouter", call)
    editorial.build_editorial_plan(p)
    assert calls == ["AudienceTranslation", "OpeningLab", "SpeechOutline", "SpeechOutline"]
    p.editorial_plan.pop("outline")
    editorial.build_editorial_plan(p)
    assert len(calls) == 4


def test_detected_health_risk_stops_without_paying_for_rewrites(monkeypatch):
    p = project_for(minutes=1)
    responses = provider_responses()
    responses["GeneralScriptVerification"]["detected_risk_domain"] = "health"
    calls = mock_provider(monkeypatch, responses)
    _, result, revisions = editorial.write_verified_script(p, max_revisions=3)
    assert not result["passed"]
    assert result["human_expert_review_required"]
    assert revisions == 0 and len(calls) == 8


def test_source_role_change_invalidates_cache():
    p = project_for()
    before = script_input_hash(p)
    p.sources[0].signal_role = "community_signal"
    assert before != script_input_hash(p)
    assert general._evidence(p)["sources"][0]["signal_role"] == "community_signal"


def test_section_scope_rejection(monkeypatch):
    p = project_for(minutes=1)
    responses = provider_responses()
    responses["ResearchedSectionDrafts"]["chapters"][0]["used_claim_ids"] = ["unknown"]
    calls = mock_provider(monkeypatch, responses)
    with pytest.raises(ValueError, match="scope"):
        editorial.draft_researched_sections(p)
    assert len(calls) == 5  # Earlier stages reused, only the failed section retried.


def test_review_schema_and_score_fail_closed(monkeypatch):
    p = project_for(minutes=1)
    p.script = valid_script()
    responses = provider_responses()
    responses["SpokenScriptQuality"]["scores"]["clarity"] = 11
    mock_provider(monkeypatch, responses)
    assert editorial.review_script_quality(p)["passed"] is False


def test_equal_writer_reviewer_models_rejected(monkeypatch):
    p = project_for(minutes=1)
    p.script = valid_script()
    monkeypatch.setattr(editorial, "OPENROUTER_VERIFY_MODEL", editorial.OPENROUTER_MODEL)
    with pytest.raises(ValueError, match="models must differ"):
        editorial.verify_script(p)


def test_script_only_dry_run_is_free_and_preserves_publish_gate(monkeypatch, tmp_path):
    from pipeline.script_only import run_script_only
    p = project_for(minutes=1)
    p.episode["publishing_enabled"] = True
    monkeypatch.setattr(editorial, "call_openrouter", lambda *a, **kw: pytest.fail("paid call"))
    result = run_script_only(p, tmp_path)
    assert result.status == "script_ready_to_generate"
    assert result.episode["publishing_enabled"] is False
    assert (tmp_path / "episode_project.json").exists()


def test_script_only_happy_path_and_checkpoints(monkeypatch, tmp_path):
    import sys
    from pipeline.script_only import run_script_only
    from pipeline.project_store import load_project
    p = project_for(minutes=1)
    calls = mock_provider(monkeypatch)
    loaded_before = set(sys.modules)
    result = run_script_only(p, tmp_path, generate=True)
    assert result.status == "script_review_ready"
    assert not {"pipeline.production", "pipeline.tts", "pipeline.assets"} & (set(sys.modules) - loaded_before)
    assert load_project(tmp_path).qc["fact_check"]["passed"]
    run_script_only(project_for(minutes=1), tmp_path, generate=True)
    assert len(calls) == 8


def test_script_only_saves_checkpoint_when_interrupted(monkeypatch, tmp_path):
    from pipeline.script_only import run_script_only
    from pipeline.project_store import load_project
    responses = provider_responses()
    def interrupted(model, system, user, schema, **kwargs):
        name = schema["json_schema"]["name"]
        if name == "OpeningLab":
            raise RuntimeError("simulated provider outage")
        return copy.deepcopy(responses[name])
    monkeypatch.setattr(editorial, "call_openrouter", interrupted)
    with pytest.raises(RuntimeError):
        run_script_only(project_for(minutes=1), tmp_path, generate=True)
    assert load_project(tmp_path).status == "script_stage_failed"
    calls = mock_provider(monkeypatch)
    run_script_only(project_for(minutes=1), tmp_path, generate=True)
    assert len(calls) == 7
    assert calls[0][0] == "OpeningLab"


def test_script_only_rejects_overwriting_another_episode(monkeypatch, tmp_path):
    from pipeline.script_only import run_script_only
    p = project_for(minutes=1)
    run_script_only(p, tmp_path)
    p.episode_id = "another_episode"
    with pytest.raises(ValueError, match="different episode"):
        run_script_only(p, tmp_path)


def test_dry_run_preserves_completed_script_qc_and_human_edits(monkeypatch, tmp_path):
    from pipeline.script_only import run_script_only
    from pipeline.project_store import save_project, load_project
    mock_provider(monkeypatch)
    result = run_script_only(project_for(minutes=1), tmp_path, generate=True)
    result.script.beats[0].narration = "A deliberate human edit."
    save_project(result, tmp_path)
    previous_bytes = (tmp_path / "episode_project.json").read_bytes()
    resumed = run_script_only(project_for(minutes=1), tmp_path)
    assert resumed.status == "script_review_ready"
    assert resumed.qc["fact_check"] == result.qc["fact_check"]
    assert load_project(tmp_path).script.beats[0].narration == "A deliberate human edit."
    assert (tmp_path / "episode_project.json").read_bytes() == previous_bytes


def test_dry_run_rejects_changed_inputs_in_existing_output(tmp_path):
    from pipeline.script_only import run_script_only
    run_script_only(project_for(minutes=1), tmp_path)
    changed = project_for("history", minutes=1)
    with pytest.raises(ValueError, match="different writing inputs"):
        run_script_only(changed, tmp_path)


def test_cli_dry_run(tmp_path, capsys):
    import json
    from pipeline.script_only import main
    source = tmp_path / "input.json"
    source.write_text(project_for(minutes=1).model_dump_json(), encoding="utf-8")
    assert main([str(source), "--output", str(tmp_path / "result")]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "script_ready_to_generate"


def test_invalid_revision_limit(tmp_path):
    from pipeline.script_only import run_script_only
    with pytest.raises(ValueError, match="max_revisions"):
        run_script_only(project_for(), tmp_path, max_revisions=3)


@pytest.mark.parametrize("cancel_after", [1, 3])
def test_cooperative_cancel_persists_canceled_not_failed(monkeypatch, tmp_path, cancel_after):
    from pipeline.script_only import run_script_only
    from pipeline.project_store import load_project
    calls = mock_provider(monkeypatch)
    checks = []
    def should_cancel():
        checks.append(True)
        return len(checks) >= cancel_after
    with pytest.raises(InterruptedError):
        run_script_only(project_for(minutes=1), tmp_path, generate=True, should_cancel=should_cancel)
    assert load_project(tmp_path).status == "script_canceled"
    assert len(calls) <= 1
