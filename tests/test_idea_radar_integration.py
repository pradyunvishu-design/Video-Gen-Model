import json

from pipeline import production, worker
from pipeline.models import Source


def test_existing_refresh_writes_board_and_preserves_source_ids(monkeypatch, tmp_path):
    from pipeline import research, youtube_radar
    from datetime import datetime, timezone
    monkeypatch.setattr(production, 'EPISODE_DATA_DIR', tmp_path/'episodes')
    monkeypatch.setattr(production, '_recent_topic_history', lambda: [])
    monkeypatch.setattr(production.ingest, 'collect', lambda: [{'id': 'official'}])
    source = Source(id='official', title='Acme diffusion image release',
                    url='https://example.org/release', text='Source body. '*20,
                    published_at=datetime.now(timezone.utc), source_type='primary')
    monkeypatch.setattr(research, 'enrich_stories', lambda stories, **kw: [source])
    monkeypatch.setattr(youtube_radar, 'collect_youtube_radar', lambda *a, **kw: {
        'status': 'complete', 'videos': [], 'errors': [], 'quota_units_this_call': 0,
        'data_origin': 'youtube_data_api', 'derived_metrics_allowed': False})
    result = production.refresh_sources()
    board = json.loads((tmp_path/'research'/'latest_ideas.json').read_text())
    assert result['source_count'] == 1
    assert board['ideas'][0]['source_ids'] == ['official']
    assert board['publishing_enabled'] is False
    standalone = production.research_video_ideas()
    assert standalone['derived_metrics_status'] == 'permission_required'


def test_existing_worker_dispatches_research_without_production(monkeypatch):
    seen = []
    monkeypatch.setattr(worker, 'research_video_ideas', lambda **kw: seen.append(kw) or {'status': 'complete'})
    assert 'research_video_ideas' in worker.SUPPORTED_STAGES
    assert worker._execute('research_video_ideas', {'force_youtube': True})['status'] == 'complete'
    assert seen == [{'force_youtube': True}]


def test_research_refresh_does_not_relabel_stale_source_cache(monkeypatch, tmp_path):
    from pipeline import youtube_radar
    from pipeline.idea_radar import planner_context
    from datetime import datetime, timezone
    monkeypatch.setattr(production, 'EPISODE_DATA_DIR', tmp_path/'episodes')
    monkeypatch.setattr(production, '_recent_topic_history', lambda: [])
    directory = tmp_path/'research'
    directory.mkdir()
    item = Source(id='old', title='Acme diffusion image', url='https://example.org',
                  published_at=datetime.now(timezone.utc), text='Original source '*20, source_type='primary')
    (directory/'latest_sources.json').write_text(json.dumps({'refreshed_at': 1,
        'sources': [item.model_dump(mode='json')]}))
    monkeypatch.setattr(youtube_radar, 'collect_youtube_radar', lambda *a, **kw: {
        'status': 'complete', 'videos': [], 'errors': [], 'quota_units_this_call': 0})
    result = production.research_video_ideas()
    board = json.loads((directory/'latest_ideas.json').read_text())
    assert result['source_cache_status'] == 'refresh_required'
    assert not board['ideas']
    assert not planner_context(board, {'old'}).startswith('{')
