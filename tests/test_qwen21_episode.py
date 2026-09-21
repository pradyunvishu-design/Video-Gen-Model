from collections import Counter
import pytest
from scripts.assemble_qwen21_episode import BEATS, allocate_frames, require_audio_bytes, frame_selection_expression


def test_boundary_expression_is_balanced_for_long_edits():
    expression=frame_selection_expression(range(118))
    depth=peak=0
    for char in expression:
        if char=='(':depth+=1;peak=max(peak,depth)
        elif char==')':depth-=1
    assert depth==0 and peak<=8
    assert expression.count('eq(n\\,')==118


def test_empty_boundary_list_is_rejected():
    with pytest.raises(ValueError):frame_selection_expression([])


def test_all_paragraphs_have_editorial_beats():
    assert len(BEATS)==28
    assert all(2<=len(v)<=3 for v in BEATS.values())
    assert all(x.split(':')[0] in {'img','cap','motion'} for v in BEATS.values() for x in v)


def test_source_assets_not_overused():
    images=Counter(x.split(':')[1] for v in BEATS.values() for x in v if x.startswith('img:'))
    for source in ['example-06','example-18','example-19']:images[source]+=1
    assert max(images.values())<=2
    motions=[x for v in BEATS.values() for x in v if x.startswith('motion:')]
    assert len(set(motions))==len(motions)


@pytest.mark.parametrize('frames,shots',[(379,2),(539,3),(638,3),(480,2)])
def test_frames_are_complete_and_even(frames,shots):
    result=allocate_frames(frames,shots)
    assert sum(result)==frames
    assert max(result)-min(result)<=1


@pytest.mark.parametrize('frames,shots',[(0,2),(15,2),(1000,2),(100,0)])
def test_reject_abrupt_or_overlong_shots(frames,shots):
    with pytest.raises(ValueError):allocate_frames(frames,shots)


def test_unchanged_audio_is_accepted():
    fingerprint={'master':'approved-master','chapters':{'a':'approved-chapter'}}
    require_audio_bytes(fingerprint,dict(fingerprint))


@pytest.mark.parametrize('current',[
    {'master':'tampered','chapters':{'a':'approved-chapter'}},
    {'master':'approved-master','chapters':{'a':'tampered'}},
    {'master':'approved-master','chapters':{}},
])
def test_audio_byte_changes_block_stale_review(current):
    with pytest.raises(RuntimeError):
        require_audio_bytes({'master':'approved-master','chapters':{'a':'approved-chapter'}},current)


def test_missing_audio_byte_approval_fails_closed():
    with pytest.raises(RuntimeError):require_audio_bytes(None,{'master':'x','chapters':{'a':'y'}})
