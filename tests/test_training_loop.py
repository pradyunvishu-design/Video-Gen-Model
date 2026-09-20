from pipeline.training_loop import _canonical_sha256, _caption_metrics, _delivery_metrics, lint_visual_spec
from pipeline.art_direction import direct_scene
from pipeline.visual_style_profile import (
    TRAINING_VISUAL_STYLE_PROFILE,
    load_visual_style_profile,
    visual_style_profile_sha256,
)


def _scene(scene_id: str, pattern: str, intent: str, anchor: str = "left") -> dict:
    kind = pattern.split("-", 1)[0]
    composition = (
        "full-frame-proof" if kind in {"source", "terminal"}
        else "mechanism-stage" if kind in {"graph", "timeline", "stack"}
        else "evidence-ledger" if kind in {"compare", "activity", "chat"}
        else "open-reset"
    )
    profile = load_visual_style_profile()
    source = kind == "source"
    context = f"{scene_id} {intent} verified editorial point"
    return {
        "id": scene_id,
        "kind": kind,
        "motionPattern": pattern,
        "semanticIntent": intent,
        "compositionFamily": composition,
        "durationSeconds": 5,
        "proofDominance": profile["dominance"][kind],
        "bodyTextPx": profile["typography"]["minimumBodyPx"],
        "labelTextPx": profile["typography"]["minimumLabelPx"],
        "visualStates": ["context", "proof", "consequence"],
        "meaningfulStateChangeSeconds": 2.5,
        "sourceFocus": ({"x": .1, "y": .1, "width": .4, "height": .2, "label": "claim"} if source else None),
        "annotationPurpose": "identify the narrated claim" if source else "",
        "transitionAfter": "hard-cut",
        "transitionReason": "argument changes to the next verified beat",
        "furnitureIds": [],
        "evidenceIds": [f"evidence-{scene_id}"],
        "anchor": anchor,
        "artDirection": direct_scene(
            scene_id=scene_id, kind=kind, intent=intent, context=context,
            accent="#F0F2F0",
        ),
    }


def test_training_lint_passes_semantic_diverse_timeline() -> None:
    profile = load_visual_style_profile()
    spec = {
        "visualStyleProfileVersion": profile["version"],
        "visualStyleProfile": profile,
        "scenes": [
            _scene("change", "source-browser-proof", "consequence", "left"),
            _scene("proof", "source-repo-metrics", "proof", "right"),
            _scene("mechanism", "graph-dependency-chain", "mechanism", "center"),
            _scene("decision", "activity-verification-pass", "decision", "left"),
        ],
    }
    report = lint_visual_spec(spec)
    assert report["passed"], report["failures"]
    assert report["metrics"]["pattern_diversity"] == 4


def test_training_lint_rejects_small_unproven_repeated_cards() -> None:
    profile = load_visual_style_profile()
    scenes = [_scene(f"scene-{index}", "activity-task-queue", "proof") for index in range(3)]
    for scene in scenes:
        scene.update({
            "proofDominance": .4,
            "bodyTextPx": 20,
            "evidenceIds": [],
            "furnitureIds": ["repeated-full-frame-board"],
        })
    report = lint_visual_spec({
        "visualStyleProfileVersion": profile["version"],
        "visualStyleProfile": profile,
        "scenes": scenes,
    })
    assert not report["passed"]
    assert any("factual beat has no locked evidence" in item for item in report["failures"])
    assert any("adjacent scenes repeat" in item for item in report["failures"])
    assert any("body text" in item for item in report["failures"])


def _v3_spec(scene: dict) -> dict:
    profile = load_visual_style_profile(TRAINING_VISUAL_STYLE_PROFILE)
    evidence_ids = list(scene["evidenceIds"])
    return {
        "visualStyleProfileVersion": profile["version"],
        "visualStyleProfile": profile,
        "visualStyleProfileSha256": visual_style_profile_sha256(profile),
        "lockedEvidenceIds": evidence_ids,
        "scenes": [scene],
    }


def test_training_lint_rejects_tampered_profile_with_same_version() -> None:
    scene = _scene("proof", "source-browser-proof", "proof")
    spec = _v3_spec(scene)
    spec["visualStyleProfile"] = {**spec["visualStyleProfile"], "status": "tampered"}
    report = lint_visual_spec(spec)
    assert not report["passed"]
    assert any("exactly match" in item for item in report["failures"])


def test_training_lint_rejects_evidence_outside_locked_ledger() -> None:
    scene = _scene("proof", "source-browser-proof", "proof")
    spec = _v3_spec(scene)
    scene["evidenceIds"] = ["fake-evidence-id"]
    report = lint_visual_spec(spec)
    assert not report["passed"]
    assert any("not in the locked ledger" in item for item in report["failures"])


def test_delivery_gate_rejects_wrong_shape_codecs_and_frame_count() -> None:
    profile = load_visual_style_profile(TRAINING_VISUAL_STYLE_PROFILE)
    report = _delivery_metrics(
        {"width": 640, "height": 360, "r_frame_rate": "12/1", "nb_read_frames": "1", "codec_name": "vp9"},
        {"codec_name": "mp3", "channels": 1, "sample_rate": "44100"},
        duration=30.0,
        expected_duration=30.0,
        profile=profile,
    )
    assert not report["passed"]
    assert report["checks"] == {
        "duration": True,
        "resolution": False,
        "fps": False,
        "frame_count": False,
        "video_codec": False,
        "audio_present": True,
        "audio_codec": False,
        "audio_channels": False,
        "audio_sample_rate": False,
    }


def test_caption_gate_rejects_zero_duration_overlap_and_wrong_script() -> None:
    profile = load_visual_style_profile(TRAINING_VISUAL_STYLE_PROFILE)
    report = _caption_metrics(
        [
            {"text": "wrong", "startMs": 100, "endMs": 100},
            {"text": " words", "startMs": 90, "endMs": 300},
        ],
        approved_script="approved words",
        expected_duration=1.0,
        profile=profile,
    )
    assert not report["passed"]
    assert not report["checks"]["positive_intervals"]
    assert not report["checks"]["nonoverlapping"]
    assert not report["checks"]["exact_script"]


def test_delivery_and_caption_gates_accept_exact_canary_shape() -> None:
    profile = load_visual_style_profile(TRAINING_VISUAL_STYLE_PROFILE)
    delivery = _delivery_metrics(
        {"width": 1920, "height": 1080, "r_frame_rate": "30/1", "nb_read_frames": "900", "codec_name": "h264"},
        {"codec_name": "aac", "channels": 2, "sample_rate": "48000"},
        duration=30.0,
        expected_duration=30.0,
        profile=profile,
    )
    captions = _caption_metrics(
        [
            {"text": "approved", "startMs": 900, "endMs": 1400},
            {"text": " words", "startMs": 1400, "endMs": 27500},
        ],
        approved_script="approved words",
        expected_duration=30.0,
        profile=profile,
    )
    assert delivery["passed"]
    assert captions["passed"]


def test_private_concept_profile_rejects_tampered_evidence_asset(tmp_path) -> None:
    profile = load_visual_style_profile("buzz-presentation-canary-v1")
    asset = tmp_path / "evidence.png"
    asset.write_bytes(b"locked-evidence")
    scene = _scene("proof", "source-browser-proof", "proof")
    ledger = {
        scene["evidenceIds"][0]: {
            "claim": "Verified local evidence.",
            "sourceUrl": "local://test-evidence",
            "assetPath": str(asset),
            "assetSha256": __import__("hashlib").sha256(asset.read_bytes()).hexdigest(),
        }
    }
    spec = {
        "visualStyleProfileVersion": profile["version"],
        "visualStyleProfile": profile,
        "visualStyleProfileSha256": visual_style_profile_sha256(profile),
        "lockedEvidenceIds": list(ledger),
        "lockedEvidenceLedger": ledger,
        "lockedEvidenceLedgerSha256": _canonical_sha256(ledger),
        "scenes": [scene],
    }
    initial = lint_visual_spec(spec)
    assert not any("ledger" in failure or "asset" in failure for failure in initial["failures"])
    asset.write_bytes(b"changed-after-lock")
    report = lint_visual_spec(spec)
    assert not report["passed"]
    assert any("asset hash does not match" in failure for failure in report["failures"])


def test_private_concept_profile_rejects_tampered_evidence_ledger(tmp_path) -> None:
    profile = load_visual_style_profile("buzz-presentation-canary-v1")
    asset = tmp_path / "evidence.png"
    asset.write_bytes(b"locked-evidence")
    scene = _scene("proof", "source-browser-proof", "proof")
    ledger = {
        scene["evidenceIds"][0]: {
            "claim": "Verified local evidence.", "sourceUrl": "local://test-evidence",
            "assetPath": str(asset),
            "assetSha256": __import__("hashlib").sha256(asset.read_bytes()).hexdigest(),
        }
    }
    spec = {
        "visualStyleProfileVersion": profile["version"], "visualStyleProfile": profile,
        "visualStyleProfileSha256": visual_style_profile_sha256(profile),
        "lockedEvidenceIds": list(ledger), "lockedEvidenceLedger": ledger,
        "lockedEvidenceLedgerSha256": _canonical_sha256(ledger), "scenes": [scene],
    }
    spec["lockedEvidenceLedger"][scene["evidenceIds"][0]]["claim"] = "Tampered claim."
    report = lint_visual_spec(spec)
    assert not report["passed"]
    assert any("ledger hash is missing or invalid" in failure for failure in report["failures"])
