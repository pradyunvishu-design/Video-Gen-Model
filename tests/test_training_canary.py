import json

import pytest
from PIL import Image

from scripts import build_training_canary


def test_finalize_rejects_still_changed_after_approval(tmp_path, monkeypatch):
    props = tmp_path / "canary.props.json"
    pre_render = tmp_path / "canary.pre-render-review.json"
    still_review = tmp_path / "canary.still-review.json"
    video = tmp_path / "canary.mp4"
    final_review = tmp_path / "canary.final-review.json"
    stills = {
        "opening": tmp_path / "opening.png",
        "exit": tmp_path / "exit.png",
    }

    props.write_text("{}", encoding="utf-8")
    for still in stills.values():
        Image.new("RGB", (1920, 1080), color=(32, 32, 32)).save(still)
    pre_render.write_text(
        json.dumps(
            {
                "passed": True,
                "publishing_enabled": False,
                "props_sha256": build_training_canary._sha256(props),
            }
        ),
        encoding="utf-8",
    )
    video.write_bytes(b"not reached")

    monkeypatch.setattr(build_training_canary, "PROPS", props)
    monkeypatch.setattr(build_training_canary, "PRE_RENDER", pre_render)
    monkeypatch.setattr(build_training_canary, "STILL_REVIEW", still_review)
    monkeypatch.setattr(build_training_canary, "VIDEO", video)
    monkeypatch.setattr(build_training_canary, "FINAL_REVIEW", final_review)
    monkeypatch.setattr(build_training_canary, "STILLS", stills)
    monkeypatch.setattr(build_training_canary, "frame_near_black_ratio", lambda _: 0.1)
    monkeypatch.setattr(
        build_training_canary,
        "post_render_metrics",
        lambda *_args, **_kwargs: pytest.fail("post-render QC ran before still integrity validation"),
    )

    approved = build_training_canary.approve_stills(
        "Independent creative approval.", "Cyclops", "approve"
    )
    assert approved["passed"] is True
    assert approved["stills"]["opening"]["sha256"] == build_training_canary._sha256(
        stills["opening"]
    )

    Image.new("RGB", (1920, 1080), color=(64, 64, 64)).save(stills["opening"])

    with pytest.raises(RuntimeError, match="representative-still review is stale for: opening"):
        build_training_canary.finalize()
