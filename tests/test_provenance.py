import json
from datetime import date

from pipeline.models import EpisodeProject, MediaAsset, Source
from pipeline.provenance import build_manifest


def test_provenance_manifest_hashes_final_and_records_synthetic_assets(tmp_path):
    final = tmp_path / "episode.mp4"
    final.write_bytes(b"video-data")
    generated = tmp_path / "motion.mp4"
    generated.write_bytes(b"motion-data")
    project = EpisodeProject(
        episode_id="episode_provenance",
        scheduled_date=date.today().isoformat(),
        sources=[Source(id="src_1", title="Official release", url="https://example.com/release", text="facts")],
        media=[MediaAsset(
            id="motion_1",
            kind="generated_motion_graphic",
            path=str(generated),
            magic_hour_project_id="mh_123",
            qc_status="passed",
        )],
        rights=[{"asset_id": "motion_1", "basis": "generated for the episode"}],
    )

    destination = build_manifest(project, final, tmp_path / "provenance.json")
    manifest = json.loads(destination.read_text(encoding="utf-8"))

    assert manifest["final_video"]["sha256"]
    assert manifest["media"][0]["synthetic"] is True
    assert manifest["content_credentials"]["c2pa_sidecar_ready"] is True
