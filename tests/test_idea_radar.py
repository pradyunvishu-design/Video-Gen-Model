from datetime import datetime, timedelta, timezone

from pipeline.idea_radar import build_idea_board, score_youtube_videos, match_topic
from pipeline.models import Source

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def video(key, views, *, channel='small', days=4, title='Acme diffusion video model', **extra):
    return dict(id=key, channel_id=channel, channel_title=channel, title=title,
                published_at=(NOW-timedelta(days=days)).isoformat(), observed_at=NOW.isoformat(),
                view_count=views, duration_seconds=600, url=f'https://youtube.com/watch?v={key}',
                observations=[], **extra)


def source(key, *, days=1, primary=True, title='Acme diffusion video model released'):
    return Source(id=key, title=title, url=f'https://{key}.example.com/release',
                  text='Official release documentation and specifications. ' * 8,
                  published_at=NOW-timedelta(days=days), source_type='primary' if primary else 'secondary',
                  signal_role='primary_evidence' if primary else 'independent_reporting',
                  publisher=key, entities=['Acme', 'diffusion'], category='model_release',
                  media_urls=['https://example.com/demo.mp4'])


def test_relative_outlier_beats_large_channel_ordinary_upload():
    videos = [video(f's{i}', 1000) for i in range(6)]
    videos += [video(f'b{i}', 1000000, channel='big') for i in range(6)]
    videos += [video('breakout', 8000), video('ordinary', 1000000, channel='big')]
    scores = {v['id']: v for v in score_youtube_videos(videos, NOW)}
    assert scores['breakout']['demand_score'] > scores['ordinary']['demand_score']
    assert scores['breakout']['outlier_ratio'] == 8
    assert scores['breakout']['baseline_count'] == 6


def test_missing_baseline_and_velocity_are_unknown_not_invented():
    result = score_youtube_videos([video('only', 100000)], NOW)[0]
    assert result['outlier_ratio'] is None
    assert result['recent_views_per_hour'] is None
    assert result['confidence'] == 'low'


def test_velocity_needs_two_distinct_observations_and_rejects_counter_drop():
    item = video('x', 5000)
    item['observations'] = [{'observed_at': (NOW-timedelta(hours=6)).isoformat(), 'view_count': 2000}]
    assert score_youtube_videos([item], NOW)[0]['recent_views_per_hour'] == 500
    item['observations'][0]['view_count'] = 6000
    assert score_youtube_videos([item], NOW)[0]['recent_views_per_hour'] is None


def test_baselines_exclude_short_other_channel_and_wrong_age():
    item = video('new', 1000, days=1)
    peers = [video(str(i), 100, days=40) for i in range(6)]
    peers += [video('short', 2), video('other', 2, channel='else')]
    peers[-2]['duration_seconds'] = 60
    assert score_youtube_videos([item, *peers], NOW)[0]['outlier_ratio'] is None


def test_topics_do_not_match_just_because_both_say_ai_video():
    assert not match_topic('AI video model news', 'Best AI video generator news')
    assert match_topic('Acme diffusion video model', 'Acme diffusion video model released')
    assert not match_topic('Kling 3.0 video release', 'Kling 2.0 video release')


def test_evidence_missing_and_repeat_cannot_be_recommended():
    rows = [video(str(i), 1000) for i in range(6)] + [video('hit', 20000)]
    report = build_idea_board([], {'status': 'complete', 'videos': rows}, now=NOW)
    assert report['ideas']
    assert report['recommended_idea_id'] is None
    assert all(i['status'] == 'research_required' for i in report['ideas'])
    verified = build_idea_board([source('official')], {'status': 'complete', 'videos': rows}, now=NOW)
    assert verified['recommended_idea_id'] is not None
    repeated = build_idea_board([source('official')], {'status': 'complete', 'videos': rows},
                                recent_topics=['Acme diffusion video model released'], now=NOW)
    assert repeated['recommended_idea_id'] is None


def test_fresh_news_without_youtube_has_explicit_exploratory_status():
    report = build_idea_board([source('official')], {'status': 'unavailable', 'videos': []}, now=NOW)
    assert report['youtube_status'] == 'unavailable'
    assert report['ideas'][0]['lane'] == 'news_opportunity'
    assert report['ideas'][0]['status'] == 'exploratory'
    assert report['ideas'][0]['youtube_evidence'] == []
    assert report['recommended_idea_id'] is None


def test_duplicate_video_ids_and_single_channel_cannot_fake_breadth():
    rows = [video(str(i), 1000) for i in range(6)] + [video('hit', 20000)]
    a = build_idea_board([source('official')], {'status': 'complete', 'videos': rows}, now=NOW)
    b = build_idea_board([source('official')], {'status': 'complete', 'videos': rows*3}, now=NOW)
    assert a['ideas'][0]['score'] == b['ideas'][0]['score']
    assert b['ideas'][0]['independent_channels'] == 1


def test_stale_sources_do_not_become_fresh_and_community_is_not_proof():
    stale = build_idea_board([source('official', days=60)], {'status': 'complete', 'videos': []}, now=NOW)
    assert not stale['ideas']
    rumor = source('forum')
    rumor.source_type, rumor.signal_role = 'community', 'community_signal'
    report = build_idea_board([rumor], {'status': 'complete', 'videos': []}, now=NOW)
    assert report['ideas'][0]['status'] == 'research_required'


def test_generic_video_description_and_other_language_do_not_enter_media_lane():
    other = video('coding', 10000, title='API explained in 10 minutes', description='In this video learn APIs.')
    nonenglish = video('otherlang', 50000, title='AI video kaise banaye', language='hi')
    board = build_idea_board([], {'status': 'complete', 'videos': [other, nonenglish]}, now=NOW)
    assert not board['ideas']


def test_source_selection_keeps_primary_evidence_and_youtube_match():
    from pipeline.research import select_enrichment_pool
    stories = [{'id': str(i), 'title': 'Generic programming headline', 'source_role': 'community',
                'source': 'Reddit', 'score': 10000} for i in range(100)]
    stories += [{'id': 'official', 'title': 'Acme diffusion video model released',
                 'source_role': 'primary', 'source': 'Acme', 'score': 0}]
    selected = select_enrichment_pool(stories, limit=10, youtube_topics=['Acme diffusion video model'])
    assert len(selected) == 10
    assert any(s['id'] == 'official' for s in selected)


def test_hyphenated_model_identity_and_description_context():
    assert match_topic('Qwen-Image-2.1 released', 'Qwen Image 2.1 is here')
    rows = [video(str(i), 1000, title='New image demo', description='Acme diffusion review') for i in range(6)]
    rows += [video('hit', 20000, title='A better image workflow', description='Acme diffusion review')]
    board = build_idea_board([source('official')], {'status': 'complete', 'videos': rows}, now=NOW)
    assert board['ideas'][0]['youtube_evidence']


def test_cached_snapshot_does_not_dilute_measured_velocity():
    item = video('x', 5000)
    item['observations'] = [{'observed_at': (NOW-timedelta(hours=6)).isoformat(), 'view_count': 2000}]
    assert score_youtube_videos([item], NOW+timedelta(hours=3))[0]['recent_views_per_hour'] == 500
    assert not score_youtube_videos([item], NOW+timedelta(hours=9))


def test_failed_article_capture_is_not_full_evidence():
    item = source('blocked')
    item.capture_status = 'failed'
    board = build_idea_board([item], {'videos': []}, now=NOW)
    assert not board['ideas'][0]['evidence']['ready']


def test_different_model_releases_do_not_merge_via_comfyui():
    sources = [source('qwen', title='Qwen Image 2.1 in ComfyUI open weight generation'),
               source('wan', title='Wan 3.0 in ComfyUI native video generation'),
               source('gemini', title='Gemini Omni 1.1 in ComfyUI video generation')]
    board = build_idea_board(sources, {'videos': []}, now=NOW)
    assert len(board['ideas']) == 3
    assert all(len(i['source_ids']) == 1 for i in board['ideas'])


def test_fresh_idea_ranking_applies_before_cluster_truncation():
    from pipeline.idea_radar import prioritize_clusters
    clusters = [{'source_ids': [str(i)], 'score': 100-i} for i in range(25)]
    board = {'generated_at': NOW.isoformat(), 'ideas': [
        {'source_ids': ['24'], 'score': 90, 'status': 'recommended'}]}
    assert prioritize_clusters(clusters, board, NOW)[0]['source_ids'] == ['24']
    assert prioritize_clusters(clusters, board, NOW+timedelta(hours=9)) == clusters


def test_unconfirmed_api_permission_prevents_all_derived_youtube_analysis(monkeypatch):
    import pipeline.idea_radar as module
    def forbidden(*args):
        raise AssertionError('derived analysis must not run')
    monkeypatch.setattr(module, 'score_youtube_videos', forbidden)
    board = build_idea_board([source('official')], {'data_origin': 'youtube_data_api',
        'derived_metrics_allowed': False, 'videos': [video('reference', 5000)]}, now=NOW)
    assert board['derived_metrics_status'] == 'permission_required'
    assert board['youtube_reference_videos'][0]['view_count'] == 5000
    assert not board['ideas'][0]['youtube_evidence']
    assert board['recommended_idea_id'] is None


def test_unverified_research_cannot_reorder_evidence_ready_clusters():
    from pipeline.idea_radar import prioritize_clusters
    clusters = [{'source_ids': ['verified'], 'score': 80}, {'source_ids': ['rumor'], 'score': 40}]
    board = {'generated_at': NOW.isoformat(), 'ideas': [
        {'source_ids': ['rumor'], 'score': 100, 'status': 'research_required'}]}
    assert prioritize_clusters(clusters, board, NOW) == clusters


def test_newsletter_sources_do_not_pass_weekly_validation():
    import pytest
    from pipeline.weekly_news import _validate_plan
    sources = [source('a'), source('b')]
    for s in sources:
        s.source_type, s.signal_role = 'secondary', 'newsletter_lead'
    story = {'story_id': 'rumor', 'source_ids': ['a', 'b']}
    with pytest.raises(ValueError, match='community/newsletter'):
        _validate_plan({'thumbnail_text': 'WHAT CHANGED TODAY', 'stories': [story]*5}, sources)


def test_media_filter_rejects_camera_crime_and_merges_specific_release():
    from pipeline.idea_radar import _media_fit, same_event
    assert not _media_fit('Hackers steal camera images')
    assert not _media_fit('3D-printed decoy camera leads to criminal charges')
    assert same_event('Qwen-Image-2.1 released',
                      'Qwen Image 2.1 in ComfyUI open weight generation with transparency')
    assert not same_event('Qwen Image 2.1 released', 'Wan 2.1 video generation released')
