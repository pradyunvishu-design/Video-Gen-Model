"""Timing checks are production contracts, not predictions of viewer retention."""
from copy import deepcopy

import pytest

from pipeline.opening_retention import build_opening_contract, evaluate_opening


@pytest.fixture
def packet():
    return {
        "beats": [
            {"id": "a", "start": 0, "end": 4, "text": "This is the official transparent output.",
             "roles": ["proof"], "evidence_ids": ["e1"], "claim_ids": ["c1"]},
            {"id": "b", "start": 4, "end": 11, "text": "Qwen helps cut out a cleanup step.",
             "roles": ["product", "benefit"], "evidence_ids": ["e1"], "claim_ids": ["c1"]},
            {"id": "c", "start": 11, "end": 19, "text": "Let's see where the cleanup remains.",
             "roles": ["promise"], "promise_id": "p1"},
            {"id": "d", "start": 19, "end": 29, "text": "These are official examples, not our tests. Start with the edges.",
             "roles": ["limitation", "bridge"]},
        ],
        "evidence": {"e1": {"available": True, "kind": "official_output", "source_url": "https://example.com/launch", "claim_ids": ["c1"]}},
        "claims": {"c1": {"source_ids": ["s1"]}},
        "payoffs": [{"id": "later", "promise_id": "p1", "start": 80, "end": 100, "evidence_ids": ["e1"]}],
        "contract": build_opening_contract("open_source_spotlight", product="Qwen"),
    }


def test_valid_opening(packet):
    report = evaluate_opening(**packet)
    assert report["passed"]
    assert report["metrics"]["first_proof_seconds"] == 0
    assert "retention_score" not in report


@pytest.mark.parametrize("role", ["product", "benefit", "limitation", "bridge", "proof"])
def test_missing_role_fails(packet, role):
    for beat in packet["beats"]:
        beat["roles"] = [r for r in beat["roles"] if r != role]
    assert not evaluate_opening(**packet)["passed"]


def test_unknown_and_unavailable_proof_fails(packet):
    packet["evidence"]["e1"]["available"] = False
    assert not evaluate_opening(**packet)["passed"]
    packet["evidence"] = {}
    assert not evaluate_opening(**packet)["passed"]


def test_unknown_claim_fails(packet):
    packet["claims"] = {}
    assert not evaluate_opening(**packet)["passed"]


def test_late_identity_is_not_counted_by_start(packet):
    packet["beats"][1]["end"] = 13
    packet["beats"][2]["start"] = 13
    assert not evaluate_opening(**packet)["passed"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, "invalid", True])
def test_invalid_timing_fails_closed(packet, value):
    packet["beats"][0]["start"] = value
    assert not evaluate_opening(**packet)["passed"]


def test_gap_overlap_cutoff_and_duration(packet):
    for field, value in [("start", 5), ("start", 3), ("speech_end", 12)]:
        copy = deepcopy(packet)
        copy["beats"][1][field] = value
        assert not evaluate_opening(**copy)["passed"]
    packet["beats"][-1]["end"] = 40
    assert not evaluate_opening(**packet)["passed"]


def test_promises_need_real_later_payoff(packet):
    packet["payoffs"] = []
    assert not evaluate_opening(**packet)["passed"]


def test_no_false_first_person_testing(packet):
    packet["beats"][0]["text"] = "I tested this on my own machine."
    assert not evaluate_opening(**packet)["passed"]
    packet["evidence"]["e1"].update(kind="captured_test", test_ledger_id="test-1")
    assert evaluate_opening(**packet)["passed"]


def test_local_proof_asset_must_exist(packet, tmp_path):
    packet.update(require_local_assets=True, asset_root=tmp_path)
    packet["evidence"]["e1"]["path"] = "proof.png"
    assert not evaluate_opening(**packet)["passed"]
    (tmp_path / "proof.png").write_bytes(b"asset")
    assert evaluate_opening(**packet)["passed"]


def test_format_and_evidence_change_recommendation():
    demo = build_opening_contract("tool_test", evidence={"e": {"available": True, "kind": "official_output"}})
    roundup = build_opening_contract("weekly_roundup")
    assert demo["preferred_modes"][0] == "demonstration_first"
    assert roundup["preferred_modes"][0] == "roundup_burst"
    assert "Local production targets" in demo["timing_basis"]
    assert demo["candidate_count"] == 4


def test_repetition_is_warning_not_product_name_ban(packet):
    packet["contract"]["recent_openings"] = [{"opening": "Qwen helps cut out a cleanup step."}]
    report = evaluate_opening(**packet)
    assert report["passed"]
    assert report["warnings"]


def test_brand_and_cta_sequences_rejected(packet):
    packet["beats"][0]["roles"].append("logo_sequence")
    assert not evaluate_opening(**packet)["passed"]


def test_proof_requires_claim_and_precise_timing_works(packet):
    packet["beats"][0]["claim_ids"] = []
    assert not evaluate_opening(**packet)["passed"]
    packet["beats"][0]["claim_ids"] = ["c1"]
    packet["beats"][1].update(end=13, role_times={"product": 9, "benefit": 11})
    packet["beats"][2]["start"] = 13
    assert evaluate_opening(**packet)["passed"]


def test_editorial_generation_adds_contract_without_schema_change(monkeypatch):
    from pipeline import editorial
    from pipeline.models import Claim, EpisodeProject, Source

    project = EpisodeProject(episode_id="hook", scheduled_date="2026-09-21",
                             sources=[Source(id="s1", title="Source", url="https://example.com")],
                             claims=[Claim(id="c1", text="A supported fact", source_ids=["s1"])])
    result = {"selected_id": "0", "selection_reason": "Visible proof",
              "candidates": [{"id": str(i), "mode": mode, "claim_ids": ["c1"],
                              "opening": "This product shows a specific change in the task that creators already do, and the official example lets us see what improves, where the limits remain, and which part of the cleanup still needs attention.",
                              "proof_target": "Official example", "promise": "Identify the cleanup", "risk": "No testing claim"}
                             for i, mode in enumerate(["demonstration_first", "relatable_friction", "context_reversal", "verdict_first"])]}
    requests = []

    def fake_call(*args, **kwargs):
        requests.append(args)
        return deepcopy(result)

    monkeypatch.setattr(editorial, "call_openrouter", fake_call)
    actual = editorial.build_opening_lab(project, evidence={}, audience={}, promise_contract={},
                                        format_playbook={}, voice_profile={}, conversational_profile={})
    assert actual["retention_contract"]["targets"]["first_proof_seconds"] == 5
    assert "FIRST-30-SECOND CONTRACT" in requests[0][2]
    assert requests[0][3] is editorial.OPENING_LAB_SCHEMA


def test_editorial_quality_does_not_claim_unmeasured_timing(monkeypatch):
    from pipeline import editorial
    from pipeline.models import EpisodeProject, Script

    project = EpisodeProject(episode_id="hook-review", scheduled_date="2026-09-21",
                             script=Script(title="Title", description="A description", tags=[],
                                           thumbnail_text="SKIP THE CLEANUP", beats=[]))
    monkeypatch.setattr(editorial, "_spoken_quality_report", lambda *args: {"failures": [], "metrics": {}})
    monkeypatch.setattr(editorial, "call_openrouter", lambda *args, **kwargs: {
        "scores": {"clarity": 9, "natural_speech": 9, "promise_delivery": 9, "voice_consistency": 9},
        "issues": [],
    })
    report = editorial.review_script_quality(project)
    assert report["opening_retention"]["passed"] is None
    project.editorial_plan["opening_timeline"] = {"beats": []}
    report = editorial.review_script_quality(project)
    assert not report["passed"]
    assert any("Opening:" in failure for failure in report["deterministic_failures"])


def test_explicit_spoken_alias_and_punctuation(packet):
    packet["contract"] = build_opening_contract("release_news", product="Qwen-Image2.1",
                                               product_spoken_aliases=["Qwen Image two point one"])
    packet["beats"][1]["text"] = "Qwen Image two point one helps cut out a cleanup step."
    assert evaluate_opening(**packet)["passed"]
    packet["beats"][1]["text"] = "Qwen Image 2.1 helps cut out a cleanup step."
    assert evaluate_opening(**packet)["passed"]


@pytest.mark.parametrize("wrong", ["Qwen Image two point two", "Qwen Image 2.2", "Qwen Image 2.10", "Qwen Image 2.1.5"])
def test_product_alias_does_not_fuzzy_match_versions(packet, wrong):
    packet["contract"] = build_opening_contract("release_news", product="Qwen-Image2.1",
                                               product_spoken_aliases=["Qwen Image two point one"])
    packet["beats"][1]["text"] = wrong + " helps cut out a cleanup step."
    assert not evaluate_opening(**packet)["passed"]


def test_formats_have_different_narrative_focus_and_test_gate(packet):
    formats = ["tool_test", "comparison", "deep_dive", "news", "open_source_spotlight", "weekly_roundup"]
    contracts = [build_opening_contract(mode) for mode in formats]
    assert len({item["format_focus"] for item in contracts}) == len(formats)
    packet["contract"] = contracts[0]
    assert not evaluate_opening(**packet)["passed"]
    packet["evidence"]["e1"].update(kind="captured_test", test_ledger_id="test-1")
    assert evaluate_opening(**packet)["passed"]
