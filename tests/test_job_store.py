from pipeline.job_store import JobStore
from pipeline.models import EpisodeProject
from pipeline.project_store import mark_stage, stage_is_current
from datetime import date


def test_job_creation_is_idempotent(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    first, created = store.create("job_1", "same-key", "refresh_sources", {})
    second, created_again = store.create("job_2", "same-key", "refresh_sources", {})
    assert created is True
    assert created_again is False
    assert first["id"] == second["id"] == "job_1"


def test_running_job_is_requeued_after_restart(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    store.create("job_1", "key", "refresh_sources", {})
    store.update("job_1", status="running", progress=50)
    restarted = JobStore(path)
    assert restarted.get("job_1")["status"] == "queued"


def test_stage_hash_invalidates_only_when_inputs_change():
    project = EpisodeProject(episode_id="episode_test", scheduled_date=date.today().isoformat())
    mark_stage(project, "script", {"claims": ["a"]})
    assert stage_is_current(project, "script", {"claims": ["a"]})
    assert not stage_is_current(project, "script", {"claims": ["b"]})


def test_job_store_lists_recent_jobs(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create("job_1", "key-1", "refresh_sources", {})
    store.create("job_2", "key-2", "research_slate", {})
    assert {job["id"] for job in store.list_all()} == {"job_1", "job_2"}
