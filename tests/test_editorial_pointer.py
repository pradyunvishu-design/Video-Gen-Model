import pytest
from pipeline.editorial_pointer import exact_word_box, validate, smootherstep, write_pointer_ass
from pipeline.models import VisualAnnotation, Shot
from pipeline.visual_director import plan_annotation
from pipeline.models import ScriptBeat


def cue(**updates):
    return dict(kind='cursor',box=[500,400,250,30],quote='test result',start=.3,end=4.8,
                rationale='Narration explains this visible result',**updates)


def test_exact_box_uses_actual_words():
    line={'words':[{'text':'cost','box':[200,80,40,20]},{'text':'$10','box':[252,81,30,19]}]}
    assert exact_word_box(line,'$10') == [252,81,30,19]
    with pytest.raises(ValueError): exact_word_box(line,'$1')
    with pytest.raises(ValueError): exact_word_box(line,'unseen')


def test_ambiguous_quote_fails_closed():
    line={'words':[{'text':'test','box':[200,80,40,20]},{'text':'test','box':[252,81,30,19]}]}
    with pytest.raises(ValueError): exact_word_box(line,'test')


def test_reject_long_underline_and_overlap():
    c=cue();c.update(kind='underline',box=[400,300,850,32])
    with pytest.raises(ValueError): validate([c],5)
    with pytest.raises(ValueError): validate([cue(),cue()],5)


def test_curve_has_no_overshoot_and_holds():
    values=[smootherstep(i/100) for i in range(130)]
    assert values==sorted(values) and values[0]==0 and values[-1]==1


def test_ass_is_vector_only_and_frame_bounded(tmp_path):
    out=write_pointer_ass([cue()],5,tmp_path/'pointer.ass').read_text()
    assert 'PlayResX: 1920' in out and 'PlayResY: 1080' in out
    events=[l for l in out.splitlines() if l.startswith('Dialogue')]
    assert events and all('\\p1}' in l for l in events)
    assert 'test result' not in out  # no duplicate text labels or dialogue captions


def test_renderer_routes_cursor_and_locks_camera(tmp_path,monkeypatch):
    from PIL import Image
    import pipeline.render_v2 as renderer
    source=tmp_path/'source.png';Image.new('RGB',(1920,1080),'white').save(source)
    a=VisualAnnotation(style='cursor',x=.25,y=.35,width=.2,height=.03,
                       target_text='Verified paragraph',verification_method='ocr-words',rationale='Exact evidence')
    shot=Shot(id='one',beat_id='b',asset_type='screenshot',duration_seconds=5,annotations=[a])
    commands=[];monkeypatch.setattr(renderer,'run_command',commands.append)
    renderer.render_shot(shot,source,tmp_path/'render.mp4')
    vf=commands[0][commands[0].index('-vf')+1]
    assert "z='1.0'" in vf and 'pointers.ass' in vf


def test_long_verified_dom_phrase_is_not_annotated():
    beat=ScriptBeat(id='b',purpose='evidence',narration='The model result has changed.',visual_direction='Show this result.')
    text='The model can handle these more complicated research workflows across multiple steps'
    result=plan_annotation(__import__('pathlib').Path('unused.png'),beat,artifact_label=text,artifact_text=text,
                           exact_text_region={'x':.25,'y':.3,'width':.6,'height':.05})
    assert result is None


def test_short_verified_phrase_uses_muted_red_and_no_cursor():
    beat=ScriptBeat(id='b',purpose='evidence',narration='The result is 52.6%.',visual_direction='Underline the result.')
    result=plan_annotation(__import__('pathlib').Path('unused.png'),beat,artifact_label='52.6%',artifact_text='Science score 52.6%',
                           exact_text_region={'x':.4,'y':.3,'width':.08,'height':.03})
    assert result.style=='underline' and result.color=='#B84D45'


def test_multiline_verified_region_is_not_a_valid_underline():
    beat=ScriptBeat(id='b',purpose='evidence',narration='Read the model result.',visual_direction='Show the result.')
    result=plan_annotation(__import__('pathlib').Path('unused.png'),beat,artifact_label='model result',artifact_text='model result',
                           exact_text_region={'x':.3,'y':.3,'width':.25,'height':.15})
    assert result is None
