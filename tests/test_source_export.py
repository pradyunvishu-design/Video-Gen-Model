import json
from pathlib import Path

import pytest

from scripts import export_github_source as exporter


def test_workflow_export_removes_private_bindings():
    workflow = {'active': True, 'pinData': {'private': 'example'}, 'meta': {},
                'nodes': [{'type': 'n8n-nodes-base.googleSheets',
                           'credentials': {'googleSheetsOAuth2Api': {'id': 'private'}},
                           'webhookId': 'private', 'parameters': {
                               'documentId': {'value': 'private-sheet-id'},
                               'sheetName': {'value': 1234, 'cachedResultName': 'Episodes'}}}]}
    clean, changes = exporter.sanitize_workflow(workflow)
    assert clean['active'] is False
    assert 'pinData' not in clean
    node = clean['nodes'][0]
    assert 'credentials' not in node and 'webhookId' not in node
    assert node['parameters']['documentId']['value'] == 'REPLACE_WITH_YOUR_SPREADSHEET_ID'
    assert node['parameters']['sheetName'] == {'__rl': True, 'value': 'Episodes', 'mode': 'name'}
    assert 'replaced_private_spreadsheet_id' in changes


def test_export_excludes_secrets_and_protects_destination_edits(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    dest = tmp_path / 'checkout'
    source.mkdir()
    (source / 'pipeline').mkdir()
    (dest / '.git').mkdir(parents=True)
    (source / '.env').write_text('TEST_API_KEY=private-example-value-123456')
    module = source / 'pipeline' / 'sample.py'
    module.write_text('VALUE = 1\n')
    monkeypatch.setattr(exporter, 'ROOT', source)
    exporter.export(dest)
    assert not (dest / '.env').exists()
    module.write_text('VALUE = 2\n')
    exporter.export(dest)
    assert (dest / 'pipeline' / 'sample.py').read_text() == 'VALUE = 2\n'
    (dest / 'pipeline' / 'sample.py').write_text('USER_EDIT = True\n')
    with pytest.raises(SystemExit):
        exporter.export(dest)
    assert (dest / 'pipeline' / 'sample.py').read_text() == 'USER_EDIT = True\n'


def test_export_fails_closed_on_known_secret(tmp_path, monkeypatch, capsys):
    source, dest = tmp_path / 'source', tmp_path / 'checkout'
    (source / 'pipeline').mkdir(parents=True)
    (dest / '.git').mkdir(parents=True)
    secret = 'private-example-value-987654'
    (source / '.env').write_text('TEST_API_KEY=' + secret)
    (source / 'pipeline' / 'bad.py').write_text('VALUE = ' + repr(secret))
    monkeypatch.setattr(exporter, 'ROOT', source)
    with pytest.raises(SystemExit):
        exporter.export(dest)
    assert secret not in capsys.readouterr().out
    assert not (dest / 'pipeline' / 'bad.py').exists()
