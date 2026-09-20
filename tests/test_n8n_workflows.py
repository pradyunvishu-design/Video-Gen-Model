import json
from pathlib import Path


def test_all_n8n_workflows_parse_and_contain_no_secrets():
    workflows = list(Path("n8n").glob("*.json"))
    assert len(workflows) >= 6
    for path in workflows:
        raw = path.read_text(encoding="utf-8")
        workflow = json.loads(raw)
        assert workflow["nodes"] and workflow["connections"]
        assert "sk-or-" not in raw and "mhk_live_" not in raw


def test_worker_nodes_use_one_explicit_https_base_url():
    for path in Path("n8n").glob("*.json"):
        raw = path.read_text(encoding="utf-8")
        assert "127.0.0.1:8080" not in raw
        workflow = json.loads(raw)
        worker_nodes = [
            node for node in workflow["nodes"]
            if node["type"] == "n8n-nodes-base.httpRequest"
        ]
        for node in worker_nodes:
            url = node["parameters"]["url"].lstrip("=")
            assert url.startswith("https://")
            assert "$vars." not in url


def test_daily_workflow_has_final_preview_not_upload():
    workflow = json.loads(Path("n8n/daily_production.json").read_text(encoding="utf-8"))
    node_names = {node["name"] for node in workflow["nodes"]}
    assert "Preview Ready" in node_names
    assert all("youtube" not in node["type"].lower() for node in workflow["nodes"])


def test_weekly_form_presents_seven_decisions_without_json_paste():
    workflow = json.loads(Path("n8n/weekly_slate_approval.json").read_text(encoding="utf-8"))
    review = next(node for node in workflow["nodes"] if node["name"] == "Review Seven Briefs")
    labels = [field["fieldLabel"] for field in review["parameters"]["formFields"]["values"]]
    assert sum(label.endswith(" decision") for label in labels) == 7
    assert "Production order (episode IDs)" in labels
    assert "Decisions JSON" not in labels


def test_google_sheets_sync_covers_every_ledger_tab():
    workflow = json.loads(Path("n8n/google_sheets_sync.json").read_text(encoding="utf-8"))
    node_names = {node["name"] for node in workflow["nodes"]}
    assert {
        "Sync Activity Log",
        "Sync Episodes",
        "Sync Weekly Slate",
        "Sync Reviews",
        "Sync Sources",
        "Sync Jobs",
    }.issubset(node_names)
    assert workflow["active"] is False
