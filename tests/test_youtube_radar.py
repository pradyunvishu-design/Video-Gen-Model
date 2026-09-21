import json
from datetime import datetime, timedelta, timezone

from pipeline import youtube_radar as radar

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def item(key='video', **overrides):
    value = {'id': key, 'snippet': {'title': 'Acme diffusion video', 'channelId': 'channel',
             'channelTitle': 'Channel', 'publishedAt': (NOW-timedelta(days=4)).isoformat(),
             'liveBroadcastContent': 'none'}, 'statistics': {'viewCount': '100'},
             'contentDetails': {'duration': 'PT10M'}, 'status': {'privacyStatus': 'public'}}
    value.update(overrides)
    return value


def config(monkeypatch, tmp_path):
    path = tmp_path/'config.json'
    path.write_text(json.dumps({'channels': [{'handle': '@test', 'expected_id': 'channel'}],
        'max_channels': 1, 'uploads_per_channel': 50, 'cache_hours': 6, 'history_days': 29,
        'baseline_upload_days': 120, 'min_duration_seconds': 240, 'max_duration_seconds': 3600,
        'max_nominal_quota_units': 10, 'discovery_queries': []}))
    monkeypatch.setattr(radar, 'CONFIG_PATH', path)


def test_collector_cache_and_growth_history(monkeypatch, tmp_path):
    config(monkeypatch, tmp_path)
    calls = []
    views = [100]

    def api(resource, params, key):
        calls.append(resource)
        if resource == 'channels':
            return {'items': [{'id': 'channel', 'snippet': {'title': 'Test'},
                              'contentDetails': {'relatedPlaylists': {'uploads': 'uploads'}}}]}
        if resource == 'playlistItems':
            return {'items': [{'contentDetails': {'videoId': 'video'}}]}
        return {'items': [item(statistics={'viewCount': str(views[0])})]}

    monkeypatch.setattr(radar, '_youtube_get', api)
    first = radar.collect_youtube_radar(tmp_path/'cache', api_key='fake', now=NOW)
    assert first['status'] == 'complete'
    assert first['videos'][0]['observations'] == []
    cached = radar.collect_youtube_radar(tmp_path/'cache', api_key='fake', now=NOW+timedelta(hours=2))
    assert cached['cache_hit'] and cached['quota_units_this_call'] == 0
    assert calls == ['channels', 'playlistItems', 'videos']
    views[0] = 200
    later = radar.collect_youtube_radar(tmp_path/'cache', api_key='fake', now=NOW+timedelta(hours=6))
    assert later['videos'][0]['observations'] == [{'observed_at': NOW.isoformat(), 'view_count': 100}]
    assert later['videos'][0]['like_count'] is None


def test_identity_mismatch_and_missing_key_fail_honestly(monkeypatch, tmp_path):
    config(monkeypatch, tmp_path)
    monkeypatch.setattr(radar, '_youtube_get', lambda *a: {'items': [{'id': 'wrong'}]})
    result = radar.collect_youtube_radar(tmp_path/'wrong', api_key='fake', now=NOW)
    assert result['status'] == 'unavailable'
    assert 'identity' in result['errors'][0]
    missing = radar.collect_youtube_radar(tmp_path/'missing', api_key='', now=NOW)
    assert missing['status'] == 'unavailable'
    assert missing['quota_units_this_call'] == 0


def test_short_live_private_and_future_uploads_excluded():
    rules = {'baseline_upload_days': 120, 'min_duration_seconds': 240, 'max_duration_seconds': 3600}
    assert radar.normalize_video(item(), NOW, rules)
    assert radar.normalize_video(item(contentDetails={'duration': 'PT59S'}), NOW, rules) is None
    assert radar.normalize_video(item(liveStreamingDetails={'actualEndTime': NOW.isoformat()}), NOW, rules) is None
    assert radar.normalize_video(item(status={'privacyStatus': 'private'}), NOW, rules) is None
    future = item()
    future['snippet']['publishedAt'] = (NOW+timedelta(days=1)).isoformat()
    assert radar.normalize_video(future, NOW, rules) is None


def test_expired_history_pruned_even_without_credentials(monkeypatch, tmp_path):
    config(monkeypatch, tmp_path)
    radar.atomic_json(tmp_path/'history.json', {'observations': {'old': [
        {'observed_at': (NOW-timedelta(days=31)).isoformat(), 'view_count': 20}]}})
    radar.collect_youtube_radar(tmp_path, api_key='', now=NOW)
    assert json.loads((tmp_path/'history.json').read_text())['observations'] == {}


def test_api_error_redacts_key_and_does_not_claim_fresh_success(monkeypatch, tmp_path):
    config(monkeypatch, tmp_path)
    def fail(*args):
        raise RuntimeError('failed request key=super-secret-example')
    monkeypatch.setattr(radar, '_youtube_get', fail)
    result = radar.collect_youtube_radar(tmp_path/'cache', api_key='super-secret-example', now=NOW)
    assert result['status'] == 'unavailable'
    assert 'super-secret-example' not in json.dumps(result)


def test_cached_snapshot_cannot_keep_old_analytics_permission(monkeypatch, tmp_path):
    config(monkeypatch, tmp_path)
    cache = tmp_path/'cache'
    radar.atomic_json(cache/'current.json', {'status': 'complete', 'observed_at': NOW.isoformat(),
        'videos': [], 'derived_metrics_allowed': True})
    result = radar.collect_youtube_radar(cache, api_key='fake', now=NOW)
    assert result['cache_hit']
    assert result['data_origin'] == 'youtube_data_api'
    assert result['derived_metrics_allowed'] is False
