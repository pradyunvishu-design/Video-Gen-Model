from datetime import date

from fastapi.testclient import TestClient

from pipeline import worker
from pipeline.job_store import JobStore
from pipeline.models import EpisodeProject
from pipeline.project_store import save_project


def _episode(tmp_path):
    episode_id = "episode_test"
    episode_dir = tmp_path / episode_id
    video = episode_dir / "preview.mp4"
    episode_dir.mkdir(parents=True)
    video.write_bytes(b"test-video")
    project = EpisodeProject(
        episode_id=episode_id,
        scheduled_date=date.today().isoformat(),
        artifacts={"video": str(video)},
    )
    save_project(project, episode_dir)
    return episode_id


def test_artifact_accepts_signed_link_without_exposing_bearer(monkeypatch, tmp_path):
    episode_id = _episode(tmp_path)
    monkeypatch.setattr(worker, "EPISODE_DATA_DIR", tmp_path)
    monkeypatch.setattr(worker, "WORKER_API_TOKEN", "x" * 32)
    monkeypatch.setattr(worker, "WORKER_PUBLIC_BASE_URL", "https://review.example")
    link = worker._signed_artifact_url(episode_id, "video")

    response = TestClient(worker.app).get(link)

    assert response.status_code == 200
    assert response.content == b"test-video"
    assert "x" * 32 not in link


def test_artifact_rejects_missing_authorization(monkeypatch, tmp_path):
    episode_id = _episode(tmp_path)
    monkeypatch.setattr(worker, "EPISODE_DATA_DIR", tmp_path)
    monkeypatch.setattr(worker, "WORKER_API_TOKEN", "x" * 32)

    response = TestClient(worker.app).get(f"/artifacts/{episode_id}/video")

    assert response.status_code == 401


def test_cooperative_cancel_stops_job_without_marking_error(monkeypatch, tmp_path):
    job_store = JobStore(tmp_path / "jobs.sqlite3")
    job_store.create("job_cancel", "cancel-key", "produce_episode", {"episode_id": "episode_test"})
    job_store.update("job_cancel", cancel_requested=1)
    monkeypatch.setattr(worker, "store", job_store)

    worker._run_job("job_cancel", "produce_episode", {"episode_id": "episode_test"})

    assert job_store.get("job_cancel")["status"] == "canceled"


def test_credit_approval_raises_episode_limit(monkeypatch, tmp_path):
    episode_id = _episode(tmp_path)
    monkeypatch.setattr(worker, "EPISODE_DATA_DIR", tmp_path)

    result = worker._approve_credits({"episode_id": episode_id, "new_limit": 20_000})

    assert result["credit_limit"] == 20_000
    assert result["status"] == "approved_for_production"
