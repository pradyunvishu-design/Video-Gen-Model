"""Customer composition contracts and discovery routing, without paid calls."""
import pytest
from pydantic import ValidationError

from pipeline import video_composer as composer
from pipeline.models import Script, ScriptBeat, MediaAsset


def request(**kwargs):
    data = {"topic": "How telescopes collect light", "instructions": "Explain this simply using demonstrations.",
            "niche": "astronomy", "audience": "curious beginners", "viewer_payoff": "Understand the mechanism",
            "sources": [{"title": "Customer research", "url": "https://example.org/research",
                         "text": "A documented optical explanation.", "facts": ["A documented optical explanation."]}]}
    return composer.CompositionRequest.model_validate({**data, **kwargs})


def project():
    p = composer.create_project("episode_comp_test", "customer_a", request())
    p.brief.approved = True
    p.script = Script(title="Telescopes explained", description="A source-backed explanation.", tags=[],
                      thumbnail_text="See The Difference", beats=[
        ScriptBeat(id="b1", narration="Light enters the telescope.", purpose="evidence",
                   visual_direction="telescope light demonstration", claim_ids=["claim_1_1"], source_ids=["source_1"]),
        ScriptBeat(id="b2", narration="Compare these optical paths.", purpose="comparison",
                   visual_direction="compare the two optical paths", claim_ids=["claim_1_1"], source_ids=["source_1"]),
    ])
    from pipeline.project_store import canonical_hash
    p.qc["fact_check"] = {"passed": True, "reviewed_script_hash": canonical_hash(p.script.model_dump(mode="json"))}
    composer.approve(p, "script", composer.approval_hash(p, "script"))
    return p


def test_customer_defaults_search_and_no_publication():
    p = composer.create_project("episode_comp_test", "customer_a", request())
    assert p.episode["composition"]["request"]["footage_mode"] == "search"
    assert not p.episode["publishing_enabled"]
    assert p.script_profile.niche == "astronomy"
    assert not p.brief.approved
    assert p.episode["composition"]["owner_id"] == "customer_a"


def graphic(kind='process'):
    from pipeline.motion_library import MotionSpec
    count=1 if kind in {'quote','metric'} else 3
    return MotionSpec(kind=kind,title='Explain the evidence',duration_seconds=8,
        source_label='Customer research',evidence_ids=['claim_1_1'],
        items=[{'label':f'Part {i+1}',**({'value':i+1} if kind in {'bars','metric'} else {})}
               for i in range(count)])


@pytest.mark.parametrize('kind',['process','timeline','comparison','bars','layers','hub_spoke','checklist','quote','metric'])
def test_every_library_style_compiles_through_existing_shot_contract(kind,tmp_path,monkeypatch):
    from pipeline import motion_library as library
    staged=[]
    monkeypatch.setattr(library,'stage_runtime',lambda path: staged.append(path))
    p=project(); add_clip(p,tmp_path); add_clip(p,tmp_path,'clip2',b'different')
    p.narration['beat_timings']=[{'beat_id':'b1','start_seconds':0,'end_seconds':8},
                              {'beat_id':'b2','start_seconds':8,'end_seconds':32}]
    composer.set_motion_spec(p,'b1',graphic(kind))
    plan=composer.plan_composition(p)
    assert plan['status']=='ready_for_review'
    composer.approve(p,'plan',composer.approval_hash(p,'plan'))
    result=composer.compile_plan(p,tmp_path)
    assert result['motion_package_count']==1 and len(staged)==1
    assert p.shots[0].motion_template=='library_graphic'
    assert (tmp_path/'motion_graphics/composition_1/index.html').is_file()
    from pipeline.remotion_renderer import render_motion_video
    with pytest.raises(ValueError,match='approve'):
        render_motion_video(p,p.shots[0],tmp_path/'not-approved.mp4')


def test_explicit_same_family_is_reusable_but_budget_failure_is_visible():
    p=project()
    p.narration['beat_timings']=[{'beat_id':'b1','start_seconds':0,'end_seconds':20},
                              {'beat_id':'b2','start_seconds':20,'end_seconds':40}]
    composer.composition_state(p)['request']['max_motion_fraction']=.7
    composer.approve(p,'script',composer.approval_hash(p,'script'))
    composer.set_motion_spec(p,'b1',graphic()); composer.set_motion_spec(p,'b2',graphic())
    plan=composer.plan_composition(p)
    assert sum('motion_spec' in s for s in plan['scenes'])==2
    composer.composition_state(p)['request']['max_motion_fraction']=.1
    composer.approve(p,'script',composer.approval_hash(p,'script'))
    plan=composer.plan_composition(p)
    assert any('Assigned graphic' in g['reason'] for g in plan['gaps'])


def test_graphic_assignment_requires_binding_and_invalidates_approval():
    p=project(); state=composer.composition_state(p)
    state['approvals']['plan']='old'; state['motion_preview_approvals']={'old':'hash'}
    before=composer.plan_input_hash(p)
    composer.set_motion_spec(p,'b1',graphic())
    assert composer.plan_input_hash(p)!=before
    assert 'plan' not in state['approvals'] and 'motion_preview_approvals' not in state
    with pytest.raises(ValueError,match='binding'):
        composer.set_motion_spec(p,'b1',graphic().model_copy(update={'illustrative':True,'evidence_ids':[]}))
    with pytest.raises(ValueError,match='claims'):
        composer.set_motion_spec(p,'b1',graphic().model_copy(update={'evidence_ids':['other']}))


def test_motion_api_auth_owner_and_stale_input(api,tmp_path):
    from pipeline.project_store import save_project
    client,headers,_=api
    assert client.get('/motion-styles').status_code==401
    assert len(client.get('/motion-styles',headers=headers).json()['styles'])==9
    p=project(); save_project(p,tmp_path/p.episode_id)
    url=f'/composition-projects/{p.episode_id}/motion-specs'
    payload={'beat_id':'b1','expected_script_hash':composer.approval_hash(p,'script'),'spec':graphic().model_dump()}
    assert client.post(url,headers={**headers,'X-Customer-ID':'other'},json=payload).status_code==404
    assert client.post(url,headers=headers,json={**payload,'expected_script_hash':'0'*64}).status_code==409
    assert client.post(url,headers=headers,json=payload).status_code==200
    assert client.get(f'/composition-projects/{p.episode_id}/motion-previews',headers=headers).json()['previews']==[]


def test_motion_preview_approval_is_owned_and_bound_to_compiled_plan(api,tmp_path,monkeypatch):
    from pipeline.project_store import save_project,load_project
    from pipeline import motion_library as library
    monkeypatch.setattr(library,'stage_runtime',lambda path: None)
    client,headers,_=api
    p=project(); directory=tmp_path/p.episode_id; directory.mkdir()
    add_clip(p,directory); add_clip(p,directory,'clip2',b'second')
    p.narration['beat_timings']=[{'beat_id':'b1','start_seconds':0,'end_seconds':8},
                               {'beat_id':'b2','start_seconds':8,'end_seconds':32}]
    composer.set_motion_spec(p,'b1',graphic()); composer.plan_composition(p)
    composer.approve(p,'plan',composer.approval_hash(p,'plan')); composer.compile_plan(p,directory)
    save_project(p,directory)
    url=f'/composition-projects/{p.episode_id}/motion-previews'
    preview=client.get(url,headers=headers).json()['previews'][0]
    assert not preview['approved'] and 'path' not in str(preview)
    endpoint=url+'/'+preview['scene_id']+'/approve'
    body={'expected_hash':preview['expected_hash']}
    assert client.post(endpoint,headers={**headers,'X-Customer-ID':'other'},json=body).status_code==404
    assert client.post(endpoint,headers=headers,json={'expected_hash':'0'*64}).status_code==409
    assert client.post(endpoint,headers=headers,json=body).status_code==200
    p=load_project(directory)
    state=composer.composition_state(p)
    annotation=next(iter(state['asset_annotations'].values()))
    annotation['start_seconds']=1
    save_project(p,directory)
    assert client.get(url,headers=headers).status_code==409
    annotation['start_seconds']=0
    composer.set_motion_spec(p,'b1',graphic().model_copy(update={'theme':'paper'}))
    composer.plan_composition(p); composer.approve(p,'plan',composer.approval_hash(p,'plan'))
    save_project(p,directory)
    assert client.post(endpoint,headers=headers,json=body).status_code==409
    assert client.get(url,headers=headers).status_code==409


@pytest.mark.parametrize("preset", ["explainer", "tutorial", "comparison", "documentary", "news"])
def test_presets(preset):
    p = composer.create_project("episode_comp_test", "customer_a", request(preset=preset))
    assert p.script_profile.format == preset


def test_custom_profile():
    p = composer.create_project("episode_comp_test", "customer_a", request(mode="custom", custom_format="history"))
    assert p.script_profile.format == "history"


@pytest.mark.parametrize("values", [{"mode": "custom"}, {"width": 3840}, {"preset": "unknown"},
                                    {"local_path": "C:/secret"}, {"target_seconds": float("nan")}])
def test_bad_requests(values):
    with pytest.raises(ValidationError):
        request(**values)


def test_approval_bound_to_content():
    p = project()
    p.script.beats[0].narration += " Changed."
    with pytest.raises(ValueError, match="approved script"):
        composer.build_search_request(p)


def test_search_is_general_and_evergreen():
    p = project()
    search = composer.build_search_request(p)
    assert len(search.scenes) == 2
    assert search.published_within_days is None
    assert search.caption_candidates_per_scene == 0
    assert all(scene.search_context == "general" for scene in search.scenes)
    from pipeline.youtube_broll import plan_scene_queries
    plans, _ = plan_scene_queries(search.scenes, api_key="")
    assert "official demo keynote" not in str(plans)


def test_missing_sources_not_invented():
    p = composer.create_project("episode_comp_test", "customer_a", request(sources=[]))
    assert not p.claims
    assert composer.project_summary(p)["next_action"] == "add_sources"
    with pytest.raises(ValueError):
        composer.approve(p, "brief", composer.approval_hash(p, "brief"))


def test_missing_footage_is_a_gap_not_fake_motion():
    p = project()
    plan = composer.plan_composition(p)
    assert plan["status"] == "needs_assets"
    assert plan["gaps"]
    assert plan["timing_status"] == "estimated"
    assert any(scene["kind"] == "motion_graphic" and scene["template"] == "comparison" for scene in plan["scenes"])
    with pytest.raises(ValueError):
        composer.compile_plan(p)


def test_internal_summary_does_not_leak_paths_or_sources():
    p = project()
    p.media.append(MediaAsset(id="private", kind="licensed_source_clip", path="C:/private/file.mp4"))
    summary = composer.project_summary(p)
    assert "C:/private" not in str(summary)
    assert "documented optical explanation" not in str(summary)


def add_clip(p, root, id="clip1", data=b"fixture video bytes"):
    import hashlib
    path = root / f"{id}.mp4"
    path.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    p.media.append(MediaAsset(id=id, kind="licensed_source_clip", path=str(path), sha256=sha, qc_status="passed"))
    p.rights.append({"asset_id": id, "rights_basis": "owned", "attribution": "Test-owned footage", "rights_ledger": "test receipt"})
    p.episode["composition"]["asset_annotations"][id] = {"claim_ids": ["claim_1_1"],
        "start_seconds": 0, "end_seconds": 40, "alignment_reviewed": True, "expected_sha256": sha}
    return path


def test_compile_approved_aligned_plan(tmp_path):
    p = project()
    add_clip(p, tmp_path)
    add_clip(p, tmp_path, "clip2", b"second fixture")
    p.narration["beat_timings"] = [{"beat_id": "b1", "start_seconds": 0, "end_seconds": 12},
                                  {"beat_id": "b2", "start_seconds": 12, "end_seconds": 24}]
    plan = composer.plan_composition(p)
    assert plan["status"] == "ready_for_review"
    composer.approve(p, "plan", composer.approval_hash(p, "plan"))
    result = composer.compile_plan(p, tmp_path)
    assert result["video_rendered"] is False
    assert result["shot_count"] == 4
    assert sum(s.duration_seconds for s in p.shots) == 24
    assert all(s.motion_style == "locked" for s in p.shots)


def test_hash_duplicate_does_not_evade_reuse_limit(tmp_path):
    p = project()
    add_clip(p, tmp_path)
    add_clip(p, tmp_path, "duplicate")
    p.narration["beat_timings"] = [{"beat_id": "b1", "start_seconds": 0, "end_seconds": 16},
                                  {"beat_id": "b2", "start_seconds": 16, "end_seconds": 32}]
    plan = composer.plan_composition(p)
    assert sum(s["kind"] == "clip" for s in plan["scenes"]) <= 2
    assert plan["gaps"]


def test_changed_asset_rejected_at_compile(tmp_path):
    p = project()
    path = add_clip(p, tmp_path)
    p.narration["beat_timings"] = [{"beat_id": "b1", "start_seconds": 0, "end_seconds": 4},
                                  {"beat_id": "b2", "start_seconds": 4, "end_seconds": 12}]
    # 8 seconds exceeds the motion fraction, so both beats use the registered clip.
    composer.plan_composition(p)
    composer.approve(p, "plan", composer.approval_hash(p, "plan"))
    path.write_bytes(b"replaced")
    with pytest.raises(ValueError, match="bytes changed"):
        composer.compile_plan(p, tmp_path)


def test_registered_path_must_be_contained(tmp_path):
    p = project()
    add_clip(p, tmp_path)
    p.narration["beat_timings"] = [{"beat_id": "b1", "start_seconds": 0, "end_seconds": 4},
                                  {"beat_id": "b2", "start_seconds": 4, "end_seconds": 12}]
    composer.plan_composition(p)
    composer.approve(p, "plan", composer.approval_hash(p, "plan"))
    with pytest.raises(ValueError, match="contained"):
        composer.compile_plan(p, tmp_path / "different_project")


@pytest.mark.parametrize("timings", [[], [{"beat_id": "b2"}],
    [{"beat_id": "b1", "start_seconds": 0, "end_seconds": float("inf")},
     {"beat_id": "b2", "start_seconds": 3, "end_seconds": 8}]])
def test_bad_alignment_rejected(timings):
    p = project()
    p.narration["beat_timings"] = timings
    with pytest.raises(ValueError):
        composer.plan_composition(p)


def test_unknown_rights_not_accepted(tmp_path):
    p = project()
    add_clip(p, tmp_path)
    p.rights[0]["rights_basis"] = "found_on_youtube"
    plan = composer.plan_composition(p)
    assert not any(s["kind"] == "clip" for s in plan["scenes"])


def test_evergreen_search_omits_date_filter(monkeypatch):
    from pipeline import youtube_broll
    captured = []
    monkeypatch.setattr(youtube_broll, "_youtube_get", lambda resource, params, api_key: captured.append(params) or {"items": []})
    youtube_broll._search_video_ids("museum optics", composer.build_search_request(project()), "test")
    assert "publishedAfter" not in captured[0]


@pytest.fixture
def api(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from pipeline import worker
    from pipeline.job_store import JobStore
    monkeypatch.setattr(worker, "EPISODE_DATA_DIR", tmp_path)
    monkeypatch.setattr(worker, "WORKER_API_TOKEN", "test-worker-secret")
    monkeypatch.setattr(worker, "store", JobStore(tmp_path / "jobs.sqlite"))
    submitted = []
    monkeypatch.setattr(worker.executor, "submit", lambda *args: submitted.append(args))
    headers = {"Authorization": "Bearer test-worker-secret", "X-Customer-ID": "customer_a"}
    return TestClient(worker.app), headers, submitted


def test_api_catalog_and_create(api):
    client, headers, _ = api
    assert client.get("/video-models").status_code == 401
    catalog = client.get("/video-models", headers=headers).json()
    assert catalog["models"][0]["live_magic_hour_product"] is False
    response = client.post("/composition-projects", headers=headers, json=request().model_dump(mode="json"))
    assert response.status_code == 201
    assert response.json()["footage_mode"] == "search"
    assert response.headers["Location"].endswith(response.json()["project_id"])


def test_api_owner_scope(api):
    client, headers, _ = api
    item = client.post("/composition-projects", headers=headers, json=request().model_dump(mode="json")).json()
    other = {**headers, "X-Customer-ID": "customer_b"}
    assert client.get(f"/composition-projects/{item['project_id']}", headers=other).status_code == 404
    assert client.get("/composition-projects/..%5Csecret", headers=headers).status_code == 404
    assert client.get(f"/composition-projects/{item['project_id']}", headers={"Authorization": headers["Authorization"]}).status_code == 422


def test_paid_job_requires_approval_and_is_idempotent(api):
    client, headers, submitted = api
    item = client.post("/composition-projects", headers=headers, json=request().model_dump(mode="json")).json()
    base = f"/composition-projects/{item['project_id']}"
    assert client.post(base + "/jobs", headers=headers, json={"stage": "write_script"}).status_code == 409
    response = client.post(base + "/approvals", headers=headers, json={"stage": "brief", "expected_hash": item["approval_hashes"]["brief"]})
    assert response.status_code == 200
    body = {"stage": "write_script", "paid_generation_approved": True, "idempotency_key": "my-request"}
    one = client.post(base + "/jobs", headers=headers, json=body)
    two = client.post(base + "/jobs", headers=headers, json=body)
    assert one.status_code == two.status_code == 202
    assert one.json()["job_id"] == two.json()["job_id"]
    assert len(submitted) == 1


def test_discovery_job_uses_existing_api_without_paid_planner(monkeypatch, tmp_path):
    from pipeline.composer_api import execute_job
    from pipeline.project_store import canonical_hash, save_project
    from pipeline import youtube_broll
    p = project()
    save_project(p, tmp_path / p.episode_id)
    def discover(project, output, req, **kwargs):
        assert kwargs["openai_api_key"] == ""
        assert req.scenes[0].search_context == "general"
        return {"manifest": str(output / "manifest.json"), "review_queue": str(output / "review.csv"),
                "scene_count": 2, "candidate_count": 6, "error_count": 0}
    monkeypatch.setattr(youtube_broll, "discover_project_broll", discover)
    result = execute_job({"episode_id": p.episode_id, "owner_id": "customer_a", "operation": "discover_clips",
                          "input_hash": composer.operation_input_hash(p, "discover_clips")}, tmp_path)
    assert result["downloads"] == 0 and result["rights_review_required"]


def test_stale_fact_review_rejected():
    p = project()
    p.script.beats[0].narration = "A new unreviewed claim."
    with pytest.raises(ValueError, match="independent review"):
        composer.approve(p, "script", composer.approval_hash(p, "script"))


def test_stale_asset_alignment_rejected(tmp_path):
    p = project()
    add_clip(p, tmp_path)
    p.media[0].sha256 = "f" * 64
    assert all(s["kind"] != "clip" for s in composer.plan_composition(p)["scenes"])


@pytest.mark.parametrize("operation", ["write_script", "discover_clips", "plan_edit"])
def test_operation_hash_survives_checkpoint_and_output_writes(operation):
    p = project()
    before = composer.operation_input_hash(p, operation)
    p.status = "checkpoint"
    p.editorial_plan["response_cache"] = {"completed": "result"}
    p.artifacts["broll_review_queue"] = "internal/review.csv"
    p.qc["new_qc"] = {"passed": True}
    assert composer.operation_input_hash(p, operation) == before
    p.brief.thesis += " Changed scope."
    if operation == "discover_clips":
        with pytest.raises(ValueError):
            composer.operation_input_hash(p, operation)
    else:
        assert composer.operation_input_hash(p, operation) != before


def test_summary_after_discovery():
    p = project()
    p.artifacts["broll_review_queue"] = "internal/review.csv"
    assert composer.project_summary(p)["next_action"] == "review_clips"


def test_job_scope_redaction_cancel_and_restart(api):
    from pipeline import worker
    client, headers, submitted = api
    item = client.post("/composition-projects", headers=headers, json=request().model_dump(mode="json")).json()
    base = f"/composition-projects/{item['project_id']}"
    client.post(base + "/approvals", headers=headers, json={"stage": "brief", "expected_hash": item["approval_hashes"]["brief"]})
    body = {"stage": "write_script", "paid_generation_approved": True, "idempotency_key": "restart"}
    job = client.post(base + "/jobs", headers=headers, json=body).json()
    status = client.get(job["status_url"], headers=headers)
    assert status.status_code == 200
    assert "payload" not in status.json() and "owner_id" not in status.text
    assert client.get(job["status_url"], headers={**headers, "X-Customer-ID": "customer_b"}).status_code == 404
    worker.store.update(job["job_id"], error="secret path /internal")
    assert "/internal" not in client.get(job["status_url"], headers=headers).text
    # Simulate process-local scheduling state lost on restart. Durable queued job re-enqueues once.
    worker._composition_scheduled.discard(job["job_id"])
    client.post(base + "/jobs", headers=headers, json=body)
    client.post(base + "/jobs", headers=headers, json=body)
    assert len(submitted) == 2
    assert client.post(job["status_url"] + "/cancel", headers=headers).json()["cancel_requested"]


def test_job_cancel_before_work(tmp_path):
    from pipeline.composer_api import execute_job
    from pipeline.project_store import save_project
    p = project()
    save_project(p, tmp_path / p.episode_id)
    with pytest.raises(InterruptedError):
        execute_job({"episode_id": p.episode_id, "owner_id": "customer_a", "operation": "plan_edit",
                     "input_hash": composer.operation_input_hash(p, "plan_edit")}, tmp_path, should_cancel=lambda: True)


def test_clip_review_response_and_owner_scope(api, tmp_path):
    import json
    from pipeline.project_store import save_project
    p = project()
    directory = tmp_path / p.episode_id
    directory.mkdir()
    manifest = directory / "candidates.json"
    manifest.write_text(json.dumps({"candidates": [{"candidate_id": "c1", "source_url": "https://youtube.com/watch?v=test",
                                                   "caption_file": "C:/private", "rights_status": "research_only"}]}))
    p.artifacts["broll_candidates"] = str(manifest)
    save_project(p, directory)
    client, headers, _ = api
    response = client.get(f"/composition-projects/{p.episode_id}/clips", headers=headers)
    assert response.status_code == 200
    assert response.json()["candidates"][0]["rights_status"] == "research_only"
    assert "C:/private" not in response.text


def test_api_script_and_asset_alignment_validation(api, tmp_path):
    from pipeline.project_store import save_project
    p = project()
    directory = tmp_path / p.episode_id
    directory.mkdir()
    add_clip(p, directory)
    save_project(p, directory)
    client, headers, _ = api
    base = f"/composition-projects/{p.episode_id}"
    assert client.get(base + "/script", headers=headers).json()["script"]["title"] == p.script.title
    body = {"asset_id": "clip1", "expected_sha256": p.media[0].sha256, "claim_ids": ["claim_1_1"],
            "start_seconds": 0, "end_seconds": 12, "alignment_reviewed": True}
    result = client.post(base + "/asset-alignments", headers=headers, json=body)
    assert result.status_code == 200 and not result.json()["rights_granted"]
    for changes, expected in [({"expected_sha256": "f" * 64}, 409), ({"claim_ids": ["unknown"]}, 422),
                              ({"start_seconds": 20}, 422)]:
        assert client.post(base + "/asset-alignments", headers=headers, json={**body, **changes}).status_code == expected
    assert client.post(base + "/approvals", headers=headers,
                       json={"stage": "plan", "expected_hash": "f" * 64}).status_code == 409


def test_execute_plan_compile_and_stale_queue(tmp_path):
    from pipeline.composer_api import execute_job
    from pipeline.project_store import save_project, load_project
    p = project()
    directory = tmp_path / p.episode_id
    directory.mkdir()
    add_clip(p, directory)
    p.narration["beat_timings"] = [{"beat_id": "b1", "start_seconds": 0, "end_seconds": 4},
                                  {"beat_id": "b2", "start_seconds": 4, "end_seconds": 12}]
    save_project(p, directory)
    payload = {"episode_id": p.episode_id, "owner_id": "customer_a", "operation": "plan_edit",
               "input_hash": composer.operation_input_hash(p, "plan_edit")}
    progress = []
    assert execute_job(payload, tmp_path, report_progress=progress.append)["status"] == "ready_for_review"
    assert progress == [10, 100]
    p = load_project(directory)
    composer.approve(p, "plan", composer.approval_hash(p, "plan"))
    save_project(p, directory)
    payload.update(operation="compile_edit", input_hash=composer.operation_input_hash(p, "compile_edit"))
    assert execute_job(payload, tmp_path)["video_rendered"] is False
    payload["input_hash"] = "f" * 64
    with pytest.raises(ValueError, match="changed after enqueue"):
        execute_job(payload, tmp_path)


def test_write_job_forwards_cancellation(monkeypatch, tmp_path):
    from pipeline.composer_api import execute_job
    from pipeline.project_store import save_project
    from pipeline import script_only
    p = project()
    composer.approve(p, "brief", composer.approval_hash(p, "brief"))
    save_project(p, tmp_path / p.episode_id)
    cancel = lambda: False
    def write(current, directory, **kwargs):
        assert kwargs["should_cancel"] is cancel
        return current
    monkeypatch.setattr(script_only, "run_script_only", write)
    result = execute_job({"episode_id": p.episode_id, "owner_id": "customer_a", "operation": "write_script",
                          "input_hash": composer.operation_input_hash(p, "write_script")}, tmp_path, should_cancel=cancel)
    assert result["project_id"] == p.episode_id
