import json
from pathlib import Path

from pipeline import magichour, visual_qc
from pipeline.creative_profile import build_thumbnail_concepts
from pipeline.thumbnail_automation import generate_magic_hour_backplates


def test_magic_hour_backplates_use_three_art_directed_jobs_plus_local_plate_and_resume(tmp_path: Path, monkeypatch) -> None:
    concepts = build_thumbnail_concepts(
        topic_class="release",
        headline="THE MODEL SHIPPED",
        focal_subject="Verified model launch",
        evidence_ids=["claim-1"],
        asset_ids=["source-1"],
        required_logos=["openai"],
    )
    calls = []

    def fake_generate(prompt, name, **kwargs):
        calls.append({"prompt": prompt, "name": name, **kwargs})
        return {"id": f"mh-project-{len(calls)}", "credits_charged": 50}

    def fake_download(_job, directory, stem):
        paths = []
        for index in range(4):
            path = directory / f"{stem}_{index}.png"
            path.write_bytes(b"image")
            paths.append(path)
        return paths

    monkeypatch.setattr(magichour, "image_generate", fake_generate)
    monkeypatch.setattr(
        magichour, "wait_image",
        lambda project_id: {"id": project_id, "status": "complete", "credits_charged": 50},
    )
    monkeypatch.setattr(magichour, "download_all", fake_download)
    monkeypatch.setattr(
        visual_qc, "inspect_thumbnail_backplate",
        lambda *_args, **_kwargs: {
            "passed": True, "unwanted_text": False, "logos_or_ui": False,
            "people_or_faces": False, "generic_ai_aesthetic": False,
            "severe_distortion": False, "usable_negative_space": True,
            "professional_art_direction": True, "notes": [],
        },
    )

    paths, record = generate_magic_hour_backplates(concepts, tmp_path)
    assert len(paths) == 4
    assert len(calls) == 3
    assert {call["model"] for call in calls} == {"nano-banana-2"}
    assert {call["resolution"] for call in calls} == {"2k"}
    assert {call["image_count"] for call in calls} == {1}
    assert len({call["prompt"] for call in calls}) == 3
    assert all("STRICTLY EXCLUDE" in call["prompt"] for call in calls)
    assert all("gears, circuit boards" in call["prompt"] for call in calls)
    assert record["credits_charged"] == 150
    assert len(record["project_ids"]) == 3
    assert record["prompt_review"]["passed"] is True
    assert record["replacement_jobs"] == 0
    assert all(review["passed"] for review in record["quality_reviews"])

    cached_paths, cached_record = generate_magic_hour_backplates(concepts, tmp_path)
    assert cached_paths == paths
    assert len(calls) == 3
    assert cached_record["cache_hit"] is True
    manifest = json.loads((tmp_path / "generated-backplates" / "magic_hour_backplates.json").read_text())
    assert manifest["project_ids"] == ["mh-project-1", "mh-project-2", "mh-project-3"]
