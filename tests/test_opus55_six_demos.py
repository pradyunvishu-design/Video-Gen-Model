from copy import deepcopy
import pytest

from scripts.revise_opus55_six_demos import replace_shot, verify_demo_coverage


def sample():
    return {'id':'shot','kind':'article','frames':270,'start_frame':300,
            'annotation_path':'old.json','framing':{'x':10},'path':'old.png',
            'relevance':'Explain the demo','asset_id':'old','source_url':'old'}


def asset():
    return {'id':'gps_clip','path':'gps.mp4','sha256':'abc','duration':12,
            'source_in':20,'source_out':32,'source_id':'gps','source_url':'https://example.org/demo',
            'rights_basis':'Bounded editorial quotation','publication_approval':'pending'}


def test_replacement_preserves_speech_timing_and_removes_article_overlays():
    old=sample();row=replace_shot(old,asset(),1,'Orbital illustration, not benchmark evidence')
    assert old==sample()
    assert (row['start_frame'],row['frames'])==(300,270)
    assert row['kind']=='video' and row['offset']==1
    assert row['source_in']==21 and row['source_out']==30
    assert 'annotation_path' not in row and 'framing' not in row
    assert row['rights_basis'] and row['visual_rationale']


@pytest.mark.parametrize('change,offset', [({'duration':5},0), ({},-1), ({'rights_basis':''},0),
                                        ({'source_out':25},0),({'source_in':-1},0)])
def test_reject_missing_rights_or_out_of_range_clip(change,offset):
    clip=asset();clip.update(change)
    with pytest.raises(ValueError):replace_shot(sample(),clip,offset,'Relevant evidence')


def test_all_six_required_and_no_repeated_source_time_ranges():
    names={'daily','launch','gps','earthrise','daydreams','gravity'}
    rows=[]
    for name in names:
        clip=asset();clip['source_id']=name;clip['id']=name
        rows.append(replace_shot(sample(),clip,0,'Relevant demo'))
    assert verify_demo_coverage(rows,names)==names
    with pytest.raises(ValueError,match='Missing'):
        verify_demo_coverage(rows[:-1],names)
    rows.append(deepcopy(rows[0]))
    with pytest.raises(ValueError,match='Overlapping'):
        verify_demo_coverage(rows,names)


def test_configure_redirects_only_edit_artifacts(tmp_path,monkeypatch):
    from scripts import revise_opus55_six_demos as revision
    monkeypatch.setattr(revision,'REVISION',tmp_path)
    for name in ('EP','OUT','FINAL'):
        monkeypatch.setattr(revision.edit,name,getattr(revision.edit,name))
    revision.configure()
    assert revision.edit.EP==tmp_path
    assert revision.edit.OUT==tmp_path/'edit'
    assert revision.edit.FINAL.parent==tmp_path


def test_plan_preserves_original_and_validates_new_sources(tmp_path,monkeypatch):
    from scripts import revise_opus55_six_demos as revision
    original=tmp_path/'original';new=tmp_path/'revision'
    monkeypatch.setattr(revision,'ORIGINAL',original)
    monkeypatch.setattr(revision,'REVISION',new)
    original.mkdir();source=original/'source.mp4';source.write_bytes(b'fake media for plan-only test')
    rows=[dict(sample(),id=f'shot{i}',frames=300,start_frame=i*300,path=str(source),asset_id=f'source{i}') for i in range(60)]
    revision.edit.dump(original/'edit_plan.json',rows)
    plan_hash=revision.edit.sha(original/'edit_plan.json')
    revision.edit.dump(original/'edit/plan_receipt.json',{'plan_hash':plan_hash})
    for name in ('script.json','narration.json','audio_qc.json','paragraph_timing.json','brief.json'):
        revision.edit.dump(original/name,{'unchanged':True})
    clips=[];placements=[]
    for i,name in enumerate(sorted(revision.EXPECTED)):
        clips.append(dict(asset(),id=name,source_id=name,path=str(source),sha256=revision.edit.sha(source)))
        placements.append({'shot_id':f'shot{i}','clip_id':name,'rationale':'Reviewed match'})
    revision.edit.dump(original/'media/six_demos/ledger.json',clips)
    revision.edit.dump(original/'research/six_demos/placements.json',placements)
    revision.plan()
    assert revision.edit.sha(original/'edit_plan.json')==plan_hash
    output=revision.edit.read(new/'edit_plan.json')
    assert len(output)==60 and output[-1]['start_frame']+output[-1]['frames']==18000
    assert [r['frames'] for r in output]==[r['frames'] for r in rows]
    assert revision.edit.sha(new/'narration.json')==revision.edit.sha(original/'narration.json')
    assert revision.edit.read(new/'edit/plan_receipt.json')['plan_hash']==revision.edit.sha(new/'edit_plan.json')
    clips[0]['sha256']='wrong'
    revision.edit.dump(original/'media/six_demos/ledger.json',clips)
    with pytest.raises(ValueError,match='Source hash changed'):revision.plan()
