from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from pipeline import ai_labs_motion_expert as expert
from pipeline.fidelity_loop import ReferenceVideo


def _reference(index: int, *, frame_strip: str = "") -> ReferenceVideo:
    uploaded = date.today() - timedelta(days=index)
    labels = ["explainer", "tool_test", "deep_dive", "weekly_roundup"]
    return ReferenceVideo(
        video_id=f"labs_{index:03d}",
        channel_id=expert.AI_LABS_CHANNEL["channel_id"],
        channel_handle=expert.AI_LABS_CHANNEL["handle"],
        title=f"AI LABS reference {index}",
        url=f"https://www.youtube.com/watch?v=labs_{index:03d}",
        upload_date=uploaded.strftime("%Y%m%d"),
        duration_seconds=600 + index,
        view_count=10_000 + index * 100,
        views_per_day=1000 - index,
        format_label=labels[index % len(labels)],
        transcript_available=True,
        visual_timecodes=[0, 20, 40, 60],
        analysis_frame_strip=frame_strip,
    )


def _strip(path: Path, offset: int) -> str:
    image = Image.new("RGB", (960, 540), (12 + offset, 15 + offset, 17 + offset))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 90, 680, 410), fill=(235, 234, 228))
    draw.rectangle((110, 130, 540, 160), fill=(72, 82, 78))
    draw.line((120, 220, 720, 220), fill=(210, 105, 70), width=8)
    image.save(path, quality=90)
    return str(path)


def _catalog(tmp_path: Path) -> tuple[dict, list[ReferenceVideo]]:
    strips = [_strip(tmp_path / f"strip_{index}.jpg", index) for index in range(8)]
    training = [_reference(index, frame_strip=strips[index % len(strips)]) for index in range(49)]
    return expert.build_motion_pattern_catalog(training), training


def _review(visual: float, placement: float, *, note: str = "") -> expert.HeldoutFidelityReview:
    score = expert.SegmentAxisScore(
        segment_id="segment_01", visual_fidelity=visual,
        placement_fidelity=placement, notes=[note] if note else [],
    )
    return expert.HeldoutFidelityReview(
        reviewer_model="reviewer", independent=True, blind_packet_hash=f"{visual}-{placement}",
        segment_scores=[score], mean_score=(visual + placement) / 2,
        minimum_score=min(visual, placement), passed=False,
    )


def test_exact_channel_identity_is_required():
    verified = expert.verify_channel_identity({
        "channel": "AI LABS",
        "channel_id": "UCelfWQr9sXVMTvBzviPGlFw",
        "uploader_id": "@AILABS-393",
    })
    assert verified["handle"] == "@AILABS-393"
    with pytest.raises(RuntimeError, match="identity mismatch"):
        expert.verify_channel_identity({"channel_id": "wrong", "uploader_id": "@ailabs"})


def test_corpus_selection_and_stratified_sealed_split_are_exact():
    selected = expert.select_motion_reference_videos([_reference(index) for index in range(70)], count=56)
    training, holdout, split_hash = expert.stratified_train_holdout_split(selected)

    assert len(selected) == 56
    assert len(training) == 49
    assert len(holdout) == 7
    assert len(split_hash) == 64
    assert {item.video_id for item in training}.isdisjoint({item.video_id for item in holdout})
    assert len({item.format_label for item in holdout}) == 4


def test_split_is_deterministic():
    records = expert.select_motion_reference_videos([_reference(index) for index in range(70)], count=56)
    first = expert.stratified_train_holdout_split(records)
    second = expert.stratified_train_holdout_split(list(reversed(records)))
    assert sorted(item.video_id for item in first[0]) == sorted(item.video_id for item in second[0])
    assert sorted(item.video_id for item in first[1]) == sorted(item.video_id for item in second[1])
    assert first[2] == second[2]


def test_ineligible_wrong_channel_and_short_videos_are_excluded():
    records = [_reference(index) for index in range(57)]
    records[0].duration_seconds = 40
    records[1].channel_id = "wrong"
    with pytest.raises(RuntimeError, match="required 56"):
        expert.select_motion_reference_videos(records, count=56)


def test_pattern_catalog_is_evidence_linked_and_contains_no_holdout(tmp_path: Path):
    catalog, training = _catalog(tmp_path)
    holdout = [_reference(100 + index) for index in range(7)]
    expert.assert_holdout_isolation(
        [item.video_id for item in training], [item.video_id for item in holdout], catalog,
    )
    assert catalog["training_video_count"] == 49
    assert len(catalog["patterns"]) >= 15
    assert catalog["saturation"]["saturated"]
    assert catalog["saturation"]["consecutive_eligible_training_videos_without_new_signal"] >= 8
    assert all(len(item["supporting_evidence"]) >= 2 for item in catalog["patterns"])
    assert all(item["originality_warning"] for item in catalog["patterns"])


def test_motion_trace_measurements_are_recorded_in_catalog(tmp_path: Path):
    strips = [_strip(tmp_path / f"trace_strip_{index}.jpg", index) for index in range(8)]
    training = []
    for index in range(49):
        trace = tmp_path / f"trace_{index}.json"
        trace.write_text(json.dumps({"windows": [{
            "mean_delta": 0.04 + index / 10000,
            "motion_distance_proxy": 0.08,
            "fitted_easing": "power3.out",
        }]}), encoding="utf-8")
        training.append(ReferenceVideo.model_validate({
            **_reference(index, frame_strip=strips[index % len(strips)]).model_dump(mode="json"),
            "motion_trace_path": str(trace),
        }))
    catalog = expert.build_motion_pattern_catalog(training)
    measurements = catalog["training_motion_measurements"]
    assert measurements["trace_count"] == 49
    assert measurements["fitted_easing_distribution"]["power3.out"] == 49
    assert all("measured_delta_band" in pattern["visual_spec"]["motion"] for pattern in catalog["patterns"])


def test_adjacent_frame_trace_measures_change(tmp_path: Path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (320, 180), "black").save(first)
    changed = Image.new("RGB", (320, 180), "black")
    ImageDraw.Draw(changed).rectangle((150, 70, 250, 140), fill="white")
    changed.save(second)
    intensity, displacement = expert._frame_motion_delta(first, second)
    assert intensity > 0
    assert displacement > 0


def test_holdout_leakage_is_rejected():
    with pytest.raises(RuntimeError, match="holdout leakage"):
        expert.assert_holdout_isolation(["a", "b"], ["b", "c"])
    with pytest.raises(RuntimeError, match="training artifact"):
        expert.assert_holdout_isolation(["a"], ["secret"], {"reference": "secret"})


def test_placement_uses_graphics_for_explanation_and_real_visuals_for_proof(tmp_path: Path):
    catalog, _training = _catalog(tmp_path)
    model = expert.build_placement_model(catalog)
    decisions = expert.plan_graphic_placements([
        {"id": "mechanism", "text": "Under the hood the request flows through three stages.", "start_seconds": 0, "end_seconds": 8},
        {"id": "proof", "text": "According to the announcement this is the result.", "start_seconds": 8, "end_seconds": 16, "source_visual_available": True, "evidence_ids": ["s1"]},
        {"id": "metric", "text": "The benchmark is 30 percent faster.", "start_seconds": 16, "end_seconds": 24, "evidence_ids": ["s2"]},
    ], catalog, model)
    assert decisions[0].pattern_id == "mechanism-flow"
    assert decisions[1].decision == "no_graphic"
    assert "aligned real evidence" in decisions[1].rejection_reasons[0]
    assert decisions[2].pattern_id == "direct-data-story"


def test_missing_evidence_blocks_evidence_dependent_graphic(tmp_path: Path):
    catalog, _training = _catalog(tmp_path)
    model = expert.build_placement_model(catalog)
    decision = expert.plan_graphic_placements([
        {"id": "metric", "text": "The benchmark is 30 percent faster.", "start_seconds": 0, "end_seconds": 8},
    ], catalog, model)[0]
    assert decision.decision == "no_graphic"
    assert "required evidence is unavailable" in decision.rejection_reasons


def test_adjacent_family_repetition_is_rejected(tmp_path: Path):
    catalog, _training = _catalog(tmp_path)
    model = expert.build_placement_model(catalog)
    decisions = expert.plan_graphic_placements([
        {"id": "a", "text": "What if this changes the workflow?", "start_seconds": 0, "end_seconds": 6},
        {"id": "b", "text": "The verdict is now obvious.", "start_seconds": 6, "end_seconds": 12},
    ], catalog, model)
    assert decisions[0].decision == "graphic"
    assert decisions[1].decision == "no_graphic"


def test_budget_refuses_projected_spend_over_ten_dollars():
    budget = expert.MotionExpertBudget(cap_usd=10, spent_usd=9.4)
    with pytest.raises(RuntimeError, match="budget stop"):
        budget.reserve(0.61)
    budget.reserve(0.6)
    budget.reconcile({"cost": 0.5, "prompt_tokens": 100, "completion_tokens": 20}, 0.6)
    assert budget.spent_usd == pytest.approx(9.9)
    assert budget.requests == 1


def test_openrouter_preflight_rejects_wrong_provider_key(monkeypatch):
    class Response:
        status_code = 401

    monkeypatch.setattr(expert, "OPENROUTER_API_KEY", "sk-not-an-openrouter-key")
    monkeypatch.setattr(expert.requests, "get", lambda *_args, **_kwargs: Response())
    with pytest.raises(expert.OpenRouterCredentialError, match="rejected by OpenRouter"):
        expert.validate_openrouter_credential()


def test_blind_packet_removes_video_ids_and_generation_metadata(tmp_path: Path):
    catalog, _training = _catalog(tmp_path)
    model = expert.build_placement_model(catalog)
    decisions = expert.plan_graphic_placements(expert._evaluation_segments(), catalog, model)
    holdout = [_reference(100 + index) for index in range(7)]
    packet = expert._anonymized_blind_packet(decisions, holdout, {"resolution": [1920, 1080]})
    serialized = json.dumps(packet)
    assert not any(item.video_id in serialized for item in holdout)
    assert "iteration" not in serialized.casefold()
    assert "generation prompt" not in serialized.casefold()
    assert "previous score" not in serialized.casefold()


def test_deterministic_heldout_measurements_gate_visuals_and_placement(tmp_path: Path):
    candidate = Path(_strip(tmp_path / "candidate.jpg", 0))
    reference = Path(_strip(tmp_path / "reference.jpg", 3))
    decisions = [expert.PlacementDecision(
        segment_id="mechanism", narrative_role="mechanism", pattern_id="mechanism-flow",
        decision="graphic", start_seconds=0, end_seconds=7, trigger="mechanism",
        confidence=0.9,
    )]
    result = expert.deterministic_heldout_measurements(
        [candidate], [reference], decisions,
        {"graphics_per_minute": 4, "repeated_adjacent_families": 0},
    )
    assert result["visual_score"] >= 4.5
    assert result["placement_score"] == 5
    assert not result["hard_failures"]


def test_deterministic_heldout_measurements_reject_near_duplicate(tmp_path: Path):
    candidate = Path(_strip(tmp_path / "candidate.jpg", 0))
    reference = tmp_path / "reference.jpg"
    reference.write_bytes(candidate.read_bytes())
    result = expert.deterministic_heldout_measurements(
        [candidate], [reference], [],
        {"graphics_per_minute": 4, "repeated_adjacent_families": 0},
    )
    assert result["hard_failures"]
    assert "near-duplicate" in result["hard_failures"][0]


def test_lowest_review_weakness_selects_one_stable_dimension():
    target = expert.select_lowest_review_weakness(_review(3.2, 4.1, note="Typography is too loose."))
    assert target["axis"] == "visual"
    assert target["dimension"] == "typography"
    assert target["segment_id"] == "segment_01"


def test_visual_repair_freezes_placement_and_can_revert_on_regression(monkeypatch, tmp_path: Path):
    catalog, _training = _catalog(tmp_path)
    placement_model = expert.build_placement_model(catalog)
    monkeypatch.setattr(expert, "AI_LABS_MOTION_DATA_DIR", tmp_path / "runs")
    run = expert.MotionExpertRun(run_id="repair")
    project_dir, _decisions, _metrics = expert.write_evaluation_package(run, catalog, placement_model)
    placements_before = (project_dir / "placements.json").read_bytes()
    html_before = (project_dir / "index.html").read_bytes()
    before = _review(3.2, 5.0, note="Typography needs tighter hierarchy.")
    expert.apply_targeted_repair(run, before, catalog, placement_model)
    assert (project_dir / "placements.json").read_bytes() == placements_before
    assert (project_dir / "index.html").read_bytes() != html_before
    assert "repair-typography" in (project_dir / "index.html").read_text(encoding="utf-8")
    after = _review(4.0, 4.8, note="Typography improved, timing regressed.")
    assert not expert.finalize_or_revert_repair(run, before, after)
    assert (project_dir / "placements.json").read_bytes() == placements_before
    assert (project_dir / "index.html").read_bytes() == html_before
    assert run.repair_iterations[-1]["accepted"] is False


def test_repair_reverts_when_overall_score_drops_even_if_other_axis_is_stable(monkeypatch, tmp_path: Path):
    catalog, _training = _catalog(tmp_path)
    placement_model = expert.build_placement_model(catalog)
    monkeypatch.setattr(expert, "AI_LABS_MOTION_DATA_DIR", tmp_path / "runs")
    run = expert.MotionExpertRun(run_id="repair-overall-regression")
    project_dir, _decisions, _metrics = expert.write_evaluation_package(run, catalog, placement_model)
    html_before = (project_dir / "index.html").read_bytes()
    before = _review(4.8, 5.0, note="Typography needs a small hierarchy repair.")
    expert.apply_targeted_repair(run, before, catalog, placement_model)
    after = _review(4.7, 5.0, note="Typography became less faithful.")
    assert not expert.finalize_or_revert_repair(run, before, after)
    assert (project_dir / "index.html").read_bytes() == html_before
    assert run.repair_iterations[-1]["accepted"] is False
    assert "overall fidelity regressed" in run.repair_iterations[-1]["reason"]


def test_scoped_review_keeps_untouched_segment_scores_frozen():
    before = expert.HeldoutFidelityReview(
        reviewer_model="reviewer", independent=True, blind_packet_hash="before",
        segment_scores=[
            expert.SegmentAxisScore(segment_id="segment_01", visual_fidelity=4.85, placement_fidelity=5),
            expert.SegmentAxisScore(segment_id="segment_02", visual_fidelity=4.9, placement_fidelity=5),
        ],
        mean_score=4.9375, minimum_score=4.85, passed=False,
        deterministic={"visual_score": 5, "placement_score": 5},
    )
    raw_after = expert.HeldoutFidelityReview(
        reviewer_model="reviewer", independent=True, blind_packet_hash="after",
        segment_scores=[
            expert.SegmentAxisScore(segment_id="segment_01", visual_fidelity=4.95, placement_fidelity=4.8),
            expert.SegmentAxisScore(segment_id="segment_02", visual_fidelity=4.6, placement_fidelity=4.7),
        ],
        mean_score=4.7625, minimum_score=4.6, passed=False,
        deterministic={"visual_score": 5, "placement_score": 5},
    )
    scoped = expert.scope_post_repair_review(
        before, raw_after, {"target": {"segment_id": "segment_01", "axis": "visual"}},
    )
    assert scoped.segment_scores[0].visual_fidelity == 4.95
    assert scoped.segment_scores[0].placement_fidelity == 5
    assert scoped.segment_scores[1] == before.segment_scores[1]
    assert scoped.passed


def test_resume_audit_reverts_legacy_accepted_regression(monkeypatch, tmp_path: Path):
    catalog, _training = _catalog(tmp_path)
    placement_model = expert.build_placement_model(catalog)
    monkeypatch.setattr(expert, "AI_LABS_MOTION_DATA_DIR", tmp_path / "runs")
    run = expert.MotionExpertRun(run_id="legacy-regression")
    project_dir, _decisions, _metrics = expert.write_evaluation_package(run, catalog, placement_model)
    html_before = (project_dir / "index.html").read_bytes()
    before = _review(4.8, 5.0)
    after = _review(4.6, 5.0)
    expert.apply_targeted_repair(run, before, catalog, placement_model)
    iteration = run.repair_iterations[-1]
    iteration.update({
        "accepted": True,
        "before_review_hash": before.blind_packet_hash,
        "after_review_hash": after.blind_packet_hash,
        "before_axis_means": {"visual": 4.8, "placement": 5.0},
        "after_axis_means": {"visual": 4.6, "placement": 5.0},
    })
    run.reviews = [before, after]
    run.accepted_review_index = 1
    expert.reconcile_repair_state(run)
    assert (project_dir / "index.html").read_bytes() == html_before
    assert run.repair_iterations[-1]["accepted"] is False
    assert run.accepted_review_index == 0


def test_motion_trace_resume_reuses_completed_checkpoint(monkeypatch, tmp_path: Path):
    trace = tmp_path / "trace.json"
    trace.write_text('{"windows": [{"mean_delta": 0.1}]}', encoding="utf-8")
    record = ReferenceVideo.model_validate({
        **_reference(1).model_dump(mode="json"), "motion_trace_path": str(trace),
    })
    calls = []
    monkeypatch.setattr(expert, "extract_public_motion_trace", lambda *_args, **_kwargs: calls.append(1) or "")
    enriched = expert.ensure_training_motion_traces([record])
    assert enriched[0].model_extra["motion_trace_path"] == str(trace)
    assert not calls


def test_paid_repair_loop_accepts_only_reviewed_improvement(monkeypatch, tmp_path: Path):
    catalog, _training = _catalog(tmp_path)
    placement_model = expert.build_placement_model(catalog)
    monkeypatch.setattr(expert, "AI_LABS_MOTION_DATA_DIR", tmp_path / "runs")
    run = expert.MotionExpertRun(run_id="paid-loop")
    project_dir, decisions, metrics = expert.write_evaluation_package(run, catalog, placement_model)
    reviews = [_review(3.0, 5.0, note="Typography is too loose."), _review(5.0, 5.0)]
    reviews[1].passed = True

    def fake_review(current_run, *_args, **_kwargs):
        result = reviews.pop(0)
        current_run.reviews.append(result)
        return result

    monkeypatch.setattr(expert, "run_independent_blind_review", fake_review)
    monkeypatch.setattr(
        expert, "render_evaluation_package",
        lambda _run, _project: (_project / "render.mp4", {"passed": True}),
    )
    result = expert.run_paid_fidelity_repair_loop(
        run, decisions, [], metrics, catalog, placement_model, project_dir,
        max_rounds=2, estimated_review_usd=1,
    )
    assert result.passed
    assert run.accepted_review_index == 1
    assert run.repair_iterations[0]["accepted"] is True


def test_paid_repair_loop_reuses_accepted_review_on_resume(monkeypatch, tmp_path: Path):
    catalog, _training = _catalog(tmp_path)
    placement_model = expert.build_placement_model(catalog)
    monkeypatch.setattr(expert, "AI_LABS_MOTION_DATA_DIR", tmp_path / "runs")
    run = expert.MotionExpertRun(run_id="paid-loop-resume")
    project_dir, decisions, metrics = expert.write_evaluation_package(run, catalog, placement_model)
    accepted = _review(5.0, 5.0)
    accepted.passed = True
    run.reviews = [accepted]
    run.accepted_review_index = 0
    monkeypatch.setattr(
        expert, "run_independent_blind_review",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("paid review must be reused")),
    )
    monkeypatch.setattr(
        expert, "render_evaluation_package",
        lambda _run, _project: (_project / "render.mp4", {"passed": True}),
    )
    result = expert.run_paid_fidelity_repair_loop(
        run, decisions, [], metrics, catalog, placement_model, project_dir,
        max_rounds=2, estimated_review_usd=1,
    )
    assert result.passed
    assert len(run.reviews) == 1


def test_evaluation_package_is_exactly_1080p_and_sixty_seconds(monkeypatch, tmp_path: Path):
    catalog, _training = _catalog(tmp_path)
    model = expert.build_placement_model(catalog)
    monkeypatch.setattr(expert, "AI_LABS_MOTION_DATA_DIR", tmp_path / "runs")
    run = expert.MotionExpertRun(run_id="evaluation")
    project_dir, decisions, metrics = expert.write_evaluation_package(run, catalog, model)
    html = (project_dir / "index.html").read_text(encoding="utf-8")
    assert metrics["resolution"] == [1920, 1080]
    assert metrics["duration_seconds"] == 60
    assert 'data-duration="60"' in html
    assert "repeat: -1" not in html
    assert "rotate" not in html.casefold()
    assert 'data-track-index="5"' in html
    assert "source-grid" in html
    assert "compare-grid" in html
    assert decisions


def test_visual_repairs_compose_without_replacing_an_accepted_scene(monkeypatch, tmp_path: Path):
    catalog, _training = _catalog(tmp_path)
    model = expert.build_placement_model(catalog)
    monkeypatch.setattr(expert, "AI_LABS_MOTION_DATA_DIR", tmp_path / "runs")
    run = expert.MotionExpertRun(run_id="composed-repairs")
    project_dir, _decisions, _metrics = expert.write_evaluation_package(
        run,
        catalog,
        model,
        {
            "repairs": [
                {"axis": "visual", "dimension": "typography", "segment_id": "hook", "round": 1},
                {"axis": "visual", "dimension": "hierarchy", "segment_id": "list", "round": 2},
                {"axis": "visual", "dimension": "typography", "segment_id": "hook", "round": 3},
            ]
        },
    )
    html = (project_dir / "index.html").read_text(encoding="utf-8")
    assert 'scene hook repair-visual repair-typography' in html
    assert 'repair-typography-v2' in html
    assert 'scene list repair-visual repair-hierarchy' in html
    motion = json.loads((project_dir / "index.motion.json").read_text(encoding="utf-8"))
    assert motion["assertions"][0]["selector"] == "#scene-hook #hook-title-refined"


def test_render_evaluation_package_reuses_matching_passed_checkpoint(monkeypatch, tmp_path: Path):
    project_dir = tmp_path / "evaluation_60s"
    project_dir.mkdir()
    (project_dir / "index.html").write_text("<html>checkpoint</html>", encoding="utf-8")
    composition_hash = expert.hashlib.sha256((project_dir / "index.html").read_bytes()).hexdigest()[:10]
    output = project_dir / "renders" / f"ai_labs_motion_expert_60s_{composition_hash}.mp4"
    output.parent.mkdir()
    output.write_bytes(b"0" * 2048)
    qc = {
        "passed": True,
        "video": str(output),
        "proof_snapshot_count": 5,
        "hyperframes_check": {"ok": True},
    }
    (project_dir / "local_qc.json").write_text(json.dumps(qc), encoding="utf-8")
    monkeypatch.setattr(expert, "save_motion_expert_run", lambda _run: None)
    monkeypatch.setattr(
        expert.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("checkpoint should skip HyperFrames")),
    )
    run = expert.MotionExpertRun(run_id="resume-render")
    rendered, loaded_qc = expert.render_evaluation_package(run, project_dir)
    assert rendered == output
    assert loaded_qc == qc
    assert run.artifacts["evaluation_video"] == str(output)


def test_status_reports_exact_split_budget_and_remaining_work(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(expert, "AI_LABS_MOTION_DATA_DIR", tmp_path)
    run = expert.MotionExpertRun(
        run_id="status", training_ids=[f"t{i}" for i in range(49)],
        holdout_ids=[f"h{i}" for i in range(7)], split_hash="abc",
    )
    status = expert.motion_expert_status(run)
    assert status["split"] == {"training_count": 49, "holdout_count": 7, "split_hash": "abc", "isolated": True}
    assert status["budget"]["cap_usd"] == 10
    assert status["budget"]["remaining_usd"] == 10
    assert status["remaining_work"] == ["run independent held-out review"]


def test_worker_accepts_motion_expert_stage(monkeypatch):
    from pipeline import worker

    monkeypatch.setattr(worker, "build_ai_labs_motion_expert", lambda payload, **_kwargs: {"run_id": payload["run_id"]})
    assert worker._execute("build_ailabs_motion_expert", {"run_id": "motion"}) == {"run_id": "motion"}
