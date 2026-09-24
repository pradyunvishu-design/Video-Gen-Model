"""Acquisition receipts are tested without network calls or episode media writes."""
import json
from pathlib import Path
import subprocess
import pytest
from scripts import acquire_opus55_six_demos as m

@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'MEDIA',tmp_path/'media')
    monkeypatch.setattr(m,'RESEARCH',tmp_path/'research')
    row={'id':'example','video_key':'daily','source_in':23,'source_out':35,'semantic':'coding'}
    data={'id':m.VIDEOS['daily'],'channel_id':m.CHANNEL,'duration':213,
          'transport_url':'https://example.invalid/video','url':'https://youtube.com/example','title':'Demo'}
    calls=[]
    def encode(args,**kwargs):
        calls.append(args)
        Path(args[-1]).write_bytes(('encoded:'+args[args.index('-ss')+1]).encode())
    monkeypatch.setattr(m.subprocess,'run',encode)
    monkeypatch.setattr(m,'validate_media',lambda path,duration:{'format':{'duration':str(duration)}})
    return row,data,calls

def test_matching_receipt_reuses_output(setup):
    row,data,calls=setup
    first=m.acquire_excerpt(row,data);second=m.acquire_excerpt(row,data)
    assert first==second and len(calls)==1
    receipt=json.loads(Path(first['path']).with_suffix('.receipt.json').read_text())
    assert receipt['inputs']['source_video_id']==m.VIDEOS['daily']
    assert receipt['output_sha256']==first['sha256']

def test_same_duration_different_range_regenerates(setup):
    row,data,calls=setup
    first=m.acquire_excerpt(row,data)
    second=m.acquire_excerpt({**row,'source_in':36,'source_out':48},data)
    assert len(calls)==2 and first['sha256']!=second['sha256']

def test_corrupted_output_does_not_reuse(setup):
    row,data,calls=setup
    result=m.acquire_excerpt(row,data);Path(result['path']).write_bytes(b'changed')
    m.acquire_excerpt(row,data)
    assert len(calls)==2

def test_missing_receipt_regenerates_legacy_file(setup):
    row,data,calls=setup
    m.MEDIA.mkdir();(m.MEDIA/'example.mp4').write_bytes(b'legacy')
    m.acquire_excerpt(row,data)
    assert len(calls)==1

def test_failed_encode_preserves_previous_asset(setup,monkeypatch):
    row,data,calls=setup
    result=m.acquire_excerpt(row,data);old=Path(result['path']).read_bytes()
    def fail(args,**kwargs):
        Path(args[-1]).write_bytes(b'partial')
        raise subprocess.CalledProcessError(1,args)
    monkeypatch.setattr(m.subprocess,'run',fail)
    with pytest.raises(subprocess.CalledProcessError):
        m.acquire_excerpt({**row,'source_in':36,'source_out':48},data)
    assert Path(result['path']).read_bytes()==old
    assert not list(m.MEDIA.glob('*.staged.mp4'))

def test_render_contract_change_invalidates_resume(setup,monkeypatch):
    row,data,calls=setup;m.acquire_excerpt(row,data)
    monkeypatch.setitem(m.RENDER,'version',2);m.acquire_excerpt(row,data)
    assert len(calls)==2

@pytest.mark.parametrize('patch',[{'video_key':'unknown'},{'id':'../bad'},
    {'source_in':float('nan')},{'source_out':float('inf')},{'source_out':99}])
def test_invalid_selection_rejected_before_transport(patch):
    row={'id':'valid','video_key':'daily','source_in':23,'source_out':35}
    with pytest.raises(ValueError):m.validate_selections([{**row,**patch}])

def test_duplicate_ids_and_incomplete_ledger_rejected():
    row={'id':'valid','video_key':'daily','source_in':23,'source_out':35}
    with pytest.raises(ValueError):m.validate_selections([row,row])
    with pytest.raises(ValueError):m.validate_ledger_ids([], [row])
    with pytest.raises(ValueError):m.validate_ledger_ids([row,row],[row])

def test_fallback_config_and_runtime_override(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'RESEARCH',tmp_path/'research')
    fallback=tmp_path/'fallback.json';row={'id':'valid','video_key':'daily','source_in':23,'source_out':35}
    fallback.write_text(json.dumps([row]));monkeypatch.setattr(m,'DEFAULT_SELECTIONS',fallback)
    assert m.load_selections()==[row]
    m.RESEARCH.mkdir();(m.RESEARCH/'selections.json').write_text(json.dumps([{**row,'id':'runtime'}]))
    assert m.load_selections()[0]['id']=='runtime'

def test_discover_refreshes_signed_metadata(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'RESEARCH',tmp_path)
    monkeypatch.setattr(m,'_key',lambda:'unused')
    monkeypatch.setattr(m,'_youtube_get',lambda *args:{'items':[{'id':video,'snippet':{'channelId':m.CHANNEL}} for video in m.VIDEOS.values()]})
    calls=[]
    def stop(key,refresh=False):
        calls.append(refresh);raise RuntimeError('test stop before fetching frames')
    monkeypatch.setattr(m,'metadata',stop)
    with pytest.raises(RuntimeError,match='test stop'):m.discover()
    assert calls and all(calls)

def test_real_media_validation_is_not_assert(monkeypatch,tmp_path):
    bad={'streams':[{'codec_type':'audio'}],'format':{'duration':'12'}}
    monkeypatch.setattr(m.subprocess,'check_output',lambda *args:json.dumps(bad).encode())
    with pytest.raises(ValueError):m.validate_media(tmp_path/'bad.mp4',12)

def test_default_config_contains_all_six_sources():
    rows=m.validate_selections(json.loads(m.DEFAULT_SELECTIONS.read_text()))
    assert len(rows)==23
    assert {r['video_key'] for r in rows}==set(m.VIDEOS)
