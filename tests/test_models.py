from datetime import date

import pytest
from pydantic import ValidationError

from pipeline.models import CaptureArtifact, Claim, EpisodeProject, Script, ScriptBeat, Source, VisualAnnotation


def source() -> Source:
    return Source(id="src_1", title="A model shipped", url="https://example.com/model")


def test_episode_project_rejects_unknown_claim_source():
    with pytest.raises(ValidationError):
        EpisodeProject(
            episode_id="episode_test", scheduled_date=date.today().isoformat(), sources=[source()],
            claims=[Claim(id="claim_1", text="A fact", source_ids=["missing"])],
        )


def test_episode_project_rejects_unknown_beat_claim():
    script = Script(
        title="Title", description="Description", tags=["AI"], thumbnail_text="THE NEW MODEL",
        beats=[ScriptBeat(
            id="beat_1", narration="A supported sentence.", claim_ids=["missing"], purpose="evidence",
            visual_direction="Show the product", source_ids=["src_1"],
        )],
    )
    with pytest.raises(ValidationError):
        EpisodeProject(episode_id="episode_test", scheduled_date=date.today().isoformat(), sources=[source()], script=script)


def test_script_word_count_uses_approved_narration():
    script = Script(
        title="Title", description="Description", tags=[], thumbnail_text="THIS IS A TEST",
        beats=[ScriptBeat(id="b1", narration="one two three", purpose="hook", visual_direction="x")],
    )
    assert script.word_count == 3


def test_thumbnail_copy_requires_three_to_five_words():
    with pytest.raises(ValidationError, match="3-5 words"):
        Script(
            title="Title", description="Description", tags=[], thumbnail_text="TOO SHORT",
            beats=[ScriptBeat(id="b1", narration="words", purpose="hook", visual_direction="x")],
        )


def test_visual_annotation_must_stay_inside_source_image():
    with pytest.raises(ValidationError, match="inside"):
        VisualAnnotation(style="outline", x=0.8, y=0.2, width=0.3, height=0.2)


def test_capture_artifact_retains_recording_qc():
    artifact = CaptureArtifact(
        kind="screen_recording", path="capture.mp4", quality={"status": "accepted", "fps": 30},
    )
    assert artifact.quality["status"] == "accepted"
    assert artifact.quality["fps"] == 30


def test_capture_artifact_retains_exact_dom_evidence():
    artifact = CaptureArtifact(
        kind="element", path="headline.png", label="Exact launch line",
        candidate_id="c012", visible_text="Exact launch line appears here",
        quality={"exact_text_region": {"x": 0.1, "y": 0.2, "width": 0.4, "height": 0.06}},
    )
    assert artifact.candidate_id == "c012"
    assert artifact.label in artifact.visible_text
