"""Bounded public YouTube research; uses the existing API credential and transport."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values

from .config import PROJECT_ROOT, YOUTUBE_API_KEY
from .youtube_broll import _youtube_get, _iso_duration_seconds

CONFIG_PATH = PROJECT_ROOT / 'configs' / 'youtube_idea_radar.json'


def stamp(value: str) -> datetime | None:
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     suffix='.tmp', delete=False) as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, allow_nan=False)
        temporary = handle.name
    os.replace(temporary, path)


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _key() -> str:
    if YOUTUBE_API_KEY:
        return YOUTUBE_API_KEY
    # Existing user-provided YouTube credentials are kept separate from voice/media secrets.
    values = dotenv_values(PROJECT_ROOT / 'secrets' / 'youtube_agent_keys.env')
    return values.get('YOUTUBE_API_KEY') or values.get('YOUTUBE_DATA_API_KEY') or ''


def normalize_video(item: dict, now: datetime, config: dict) -> dict | None:
    snippet, stats = item.get('snippet', {}), item.get('statistics', {})
    published = stamp(snippet.get('publishedAt'))
    duration = _iso_duration_seconds(item.get('contentDetails', {}).get('duration', ''))
    if (not published or published > now or (now-published).days > config['baseline_upload_days']
            or not config['min_duration_seconds'] <= duration <= config['max_duration_seconds']
            or snippet.get('liveBroadcastContent', 'none') != 'none'
            or item.get('liveStreamingDetails')
            or item.get('status', {}).get('privacyStatus') != 'public'
            or 'viewCount' not in stats or not item.get('id')):
        return None
    thumbnails = snippet.get('thumbnails', {})
    return {
        'id': item['id'], 'channel_id': snippet.get('channelId', ''),
        'channel_title': snippet.get('channelTitle', ''), 'title': snippet.get('title', ''),
        'description': snippet.get('description', '')[:2500], 'published_at': published.isoformat(),
        'language': snippet.get('defaultAudioLanguage') or snippet.get('defaultLanguage') or '',
        'observed_at': now.isoformat(), 'duration_seconds': duration,
        'view_count': max(0, int(stats['viewCount'])),
        'like_count': int(stats['likeCount']) if 'likeCount' in stats else None,
        'comment_count': int(stats['commentCount']) if 'commentCount' in stats else None,
        'url': f"https://www.youtube.com/watch?v={item['id']}",
        'thumbnail_url': next((thumbnails[k]['url'] for k in ('maxres', 'high', 'medium', 'default')
                               if thumbnails.get(k, {}).get('url')), ''),
    }


def collect_youtube_radar(output_dir: Path, *, now: datetime | None = None,
                         force: bool = False, api_key: str | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    config = _read(CONFIG_PATH)
    permission = config.get('derived_metrics_permission', {})
    derived_allowed = permission.get('status') == 'approved' and bool(permission.get('approval_reference', '').strip())
    current_path = output_dir / 'current.json'
    previous = _read(current_path)
    cached_at = stamp(previous.get('observed_at'))
    if (not force and cached_at and 0 <= (now-cached_at).total_seconds() < config['cache_hours']*3600
            and previous.get('status') == 'complete'):
        return {**previous, 'cache_hit': True, 'quota_units_this_call': 0,
                'data_origin': 'youtube_data_api', 'derived_metrics_allowed': derived_allowed}
    key = _key() if api_key is None else api_key
    report = {'schema_version': 'youtube-radar/1', 'status': 'unavailable',
              'data_origin': 'youtube_data_api', 'derived_metrics_allowed': derived_allowed,
              'observed_at': now.isoformat(), 'videos': [], 'channels': [], 'errors': [],
              'quota_units_this_call': 0, 'cache_hit': False,
              'quota_note': 'Nominal estimate; shared transport may retry each request up to three times.'}
    history_path = output_dir / 'history.json'
    history = _read(history_path).get('observations', {})
    cutoff = now-timedelta(days=min(29, config['history_days']))
    history = {key_: [p for p in values if stamp(p.get('observed_at'))
                     and cutoff <= stamp(p['observed_at']) < now]
               for key_, values in history.items()}
    history = {key_: values for key_, values in history.items() if values}
    atomic_json(history_path, {'observations': history})
    if not key:
        report['errors'] = ['YOUTUBE_API_KEY is unavailable; no YouTube demand has been measured.']
        atomic_json(current_path, report)
        return report

    def get(resource, params):
        cost = 100 if resource == 'search' else 1
        if report['quota_units_this_call'] + cost > config['max_nominal_quota_units']:
            raise RuntimeError('configured research quota ceiling reached')
        report['quota_units_this_call'] += cost
        return _youtube_get(resource, params, key)

    videos, channels = {}, {}

    def hydrate(ids):
        ids = list(dict.fromkeys(ids))
        for start in range(0, len(ids), 50):
            payload = get('videos', {'part': 'snippet,contentDetails,statistics,status,liveStreamingDetails',
                                     'id': ','.join(ids[start:start+50])})
            for item in payload.get('items', []):
                normalized = normalize_video(item, now, config)
                if normalized:
                    videos[normalized['id']] = normalized

    def load_channel(channel):
        channel_id = channel['id']
        if channel_id in channels or len(channels) >= min(8, config['max_channels']):
            return
        uploads = channel.get('contentDetails', {}).get('relatedPlaylists', {}).get('uploads')
        if not uploads:
            raise ValueError('channel uploads playlist missing')
        items = get('playlistItems', {'part': 'contentDetails', 'playlistId': uploads,
                                      'maxResults': min(50, config['uploads_per_channel'])})
        ids = [i['contentDetails']['videoId'] for i in items.get('items', [])
               if i.get('contentDetails', {}).get('videoId')]
        hydrate(ids)
        channels[channel_id] = {'id': channel_id, 'title': channel.get('snippet', {}).get('title', ''),
                                'baseline_method': 'recent uploads, including low performers',
                                'upload_ids_requested': len(ids)}

    for seed in config['channels'][:8]:
        try:
            items = get('channels', {'part': 'snippet,contentDetails', 'forHandle': seed['handle']}).get('items', [])
            if len(items) != 1 or (seed.get('expected_id') and items[0]['id'] != seed['expected_id']):
                raise ValueError('channel identity did not match configured reference')
            load_channel(items[0])
        except (RuntimeError, ValueError, KeyError) as exc:
            report['errors'].append(f"{seed['handle']}: {str(exc).replace(key, '[redacted]')[:300]}")
    for query in config['discovery_queries'][:2]:
        try:
            found = get('search', {'part': 'snippet', 'type': 'video', 'q': query,
                                   'order': 'relevance', 'maxResults': 20, 'relevanceLanguage': 'en',
                                   'publishedAfter': (now-timedelta(days=30)).isoformat()})
            hydrate([i['id']['videoId'] for i in found.get('items', []) if i.get('id', {}).get('videoId')])
        except (RuntimeError, ValueError, KeyError) as exc:
            report['errors'].append(f"discovery: {str(exc).replace(key, '[redacted]')[:300]}")
    extra_ids = sorted({v['channel_id'] for v in videos.values()} - channels.keys())
    for channel_id in extra_ids[:max(0, min(8, config['max_channels'])-len(channels))]:
        try:
            for item in get('channels', {'part': 'snippet,contentDetails', 'id': channel_id}).get('items', []):
                load_channel(item)
        except (RuntimeError, ValueError, KeyError) as exc:
            report['errors'].append(f"baseline: {str(exc).replace(key, '[redacted]')[:300]}")
    # Only measured history is exposed. A second call at the same instant cannot invent growth.
    for video in videos.values():
        video['observations'] = history.get(video['id'], [])
        history[video['id']] = [*video['observations'], {'observed_at': now.isoformat(),
                                                     'view_count': video['view_count']}][-120:]
    # Remove deleted/inaccessible IDs on refresh; historical counts are retained only for refreshed IDs.
    history = {k: history[k] for k in videos}
    report.update(videos=sorted(videos.values(), key=lambda v: v['published_at'], reverse=True),
                  channels=list(channels.values()),
                  status=('partial' if report['errors'] else 'complete') if videos else 'unavailable')
    atomic_json(history_path, {'observations': history})
    atomic_json(current_path, report)
    return report
