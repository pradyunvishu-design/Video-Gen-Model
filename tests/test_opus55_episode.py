from pathlib import Path
import pytest

from scripts.assemble_opus55_episode import distribute, validate
from scripts.assemble_qwen21_episode import require_audio_bytes


def test_diagrams_and_launch_quotes_play_complete():
    assert distribute(630, ['motion:price', 'cap:source']) == [360, 270]
    assert distribute(420, ['video:launch', 'cap:source']) == [150, 270]
    assert distribute(601, ['cap:a', 'cap:b']) == [300, 301]


@pytest.mark.parametrize('length,choices', [
    (800, ['cap:a', 'cap:b']),
    (390, ['motion:price', 'cap:a']),
    (200, ['video:launch']),
])
def test_no_overlong_holds_or_truncated_diagrams(length, choices):
    with pytest.raises(ValueError):
        distribute(length, choices)


def timeline(tmp_path):
    media = tmp_path/'source.mp4';media.touch()
    return [{'id':str(i),'start_frame':i*300,'frames':300,'path':str(media),
             'asset_id':str(i),'kind':'article','relevance':'Matched spoken paragraph',
             'source_url':'https://www.anthropic.com/claude-opus-5-5'} for i in range(60)]


def test_exact_ten_minute_contiguous_timeline(tmp_path):
    rows = timeline(tmp_path)
    assert validate(rows) == 18000
    rows[-1]['frames'] = 299
    with pytest.raises(ValueError, match='exactly ten'):
        validate(rows)


def test_reject_repetition_and_gaps(tmp_path):
    rows = timeline(tmp_path)
    rows[1]['start_frame'] += 1
    with pytest.raises(ValueError, match='Gap'):
        validate(rows)
    rows = timeline(tmp_path)
    rows[1]['asset_id'] = rows[0]['asset_id']
    rows[2]['asset_id'] = rows[0]['asset_id']
    with pytest.raises(ValueError, match='Repeated'):
        validate(rows)


def test_changed_narration_cannot_pass_old_review():
    approved = {'master':'abc','chapters':{'one':'def'}}
    require_audio_bytes(approved, approved)
    with pytest.raises(RuntimeError, match='bytes differ'):
        require_audio_bytes(approved, {'master':'changed','chapters':{'one':'def'}})


def test_changed_chapter_bytes_stop_before_asr(tmp_path, monkeypatch):
    from scripts import produce_opus55_episode as production
    monkeypatch.setattr(production,'EP',tmp_path)
    monkeypatch.setattr(production,'configure',lambda:None)
    wav=tmp_path/'chapter.wav';wav.write_bytes(b'new waveform')
    production.shared.dump(tmp_path/'narration.json', {'chapters':[
        {'id':'chapter','path':str(wav),'output_audio_hash':'old waveform hash'}]})
    with pytest.raises(RuntimeError, match='Timed audio bytes changed'):
        production.audio_qc()


def test_stale_paragraph_timing_stops_plan(tmp_path, monkeypatch):
    from scripts import assemble_opus55_episode as edit
    monkeypatch.setattr(edit,'EP',tmp_path)
    for name in ['script.json','narration.json','paragraph_timing.json']:
        (tmp_path/name).write_text('{}')
    fingerprints={'master':'abc','chapters':{'one':'def'}}
    monkeypatch.setattr(edit,'audio_fingerprints',lambda:fingerprints)
    edit.dump(tmp_path/'audio_qc.json',{'passed':True,'script_hash':edit.sha(tmp_path/'script.json'),
        'narration_hash':edit.sha(tmp_path/'narration.json'),'audio_files':fingerprints,
        'paragraph_timing_hash':'stale'})
    with pytest.raises(RuntimeError, match='Paragraph timing differs'):
        edit.make_plan()


def test_real_comparison_clip_lengths():
    assert distribute(450,['video:site_design_comparison','cap:bug']) == [143,307]
    assert distribute(510,['video:site_bug_comparison','cap:writing']) == [198,312]


def test_locked_source_framing_is_supported(tmp_path, monkeypatch):
    from scripts import render_dreamx_source_motion as source
    image=tmp_path/'source.png';image.touch()
    def reached_probe(path):
        raise RuntimeError('valid zoom reached media probe')
    monkeypatch.setattr(source,'probe',reached_probe)
    with pytest.raises(RuntimeError,match='valid zoom reached'):
        source.render_source_shot(image,tmp_path/'clip.mp4',3,zoom=1.0)
    with pytest.raises(ValueError,match='Directed zoom'):
        source.render_source_shot(image,tmp_path/'clip.mp4',3,zoom=.99)
