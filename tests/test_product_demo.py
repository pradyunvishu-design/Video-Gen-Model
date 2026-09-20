from pipeline.product_demo import DemoSpec, _cinematic_demo_filter, sanitize_plan


def _spec(**overrides):
    data = {
        "website": "https://aistudio.google.com/",
        "goal": "Test one model feature on screen",
        "inputs": {"prompt": "Harmless test prompt"},
    }
    data.update(overrides)
    return DemoSpec(**data)


def _observation():
    return {"candidates": [
        {"candidate_id": "d001", "tag": "textarea", "text": "Prompt", "editable": True,
         "input_type": "", "autocomplete": "", "href": ""},
        {"candidate_id": "d002", "tag": "button", "text": "Generate", "editable": False,
         "input_type": "", "autocomplete": "", "href": ""},
        {"candidate_id": "d003", "tag": "input", "text": "Password", "editable": True,
         "input_type": "password", "autocomplete": "current-password", "href": ""},
        {"candidate_id": "d004", "tag": "button", "text": "Upgrade billing", "editable": False,
         "input_type": "", "autocomplete": "", "href": ""},
    ]}


def test_generation_click_requires_explicit_job_permission():
    raw = {"actions": [
        {"kind": "fill", "candidate_id": "d001", "input_key": "prompt", "label": "Prompt", "duration_seconds": 1, "start_ratio": 0, "end_ratio": .7},
        {"kind": "click", "candidate_id": "d002", "input_key": "", "label": "Generate", "duration_seconds": 1, "start_ratio": 0, "end_ratio": .7},
    ]}
    plan = sanitize_plan(raw, _spec(allow_generation=False), _observation())
    assert [action.kind for action in plan["actions"]] == ["fill"]


def test_generation_click_is_allowed_when_job_opts_in():
    raw = {"actions": [
        {"kind": "click", "candidate_id": "d002", "input_key": "", "label": "Generate", "duration_seconds": 1, "start_ratio": 0, "end_ratio": .7},
    ]}
    plan = sanitize_plan(raw, _spec(allow_generation=True), _observation())
    assert [action.kind for action in plan["actions"]] == ["click"]


def test_credentials_and_billing_controls_are_always_rejected():
    raw = {"actions": [
        {"kind": "fill", "candidate_id": "d003", "input_key": "prompt", "label": "Password", "duration_seconds": 1, "start_ratio": 0, "end_ratio": .7},
        {"kind": "click", "candidate_id": "d004", "input_key": "", "label": "Upgrade", "duration_seconds": 1, "start_ratio": 0, "end_ratio": .7},
    ]}
    plan = sanitize_plan(raw, _spec(allow_generation=True), _observation())
    assert all(action.candidate_id not in {"d003", "d004"} for action in plan["actions"])


def test_cinematic_demo_filter_uses_only_explicit_action_targets():
    filter_graph = _cinematic_demo_filter([{
        "label": "Generate", "kind": "click", "start_seconds": 1.2, "end_seconds": 3.4,
        "x": 0.74, "y": 0.82,
    }])

    assert "0.085" in filter_graph
    assert "0.7400" in filter_graph
    assert "0.8200" in filter_graph
    assert "eval=frame" in filter_graph
