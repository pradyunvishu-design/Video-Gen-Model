import json
import pytest
from pydantic import ValidationError
from pipeline.motion_library import MotionSpec, catalog, render_html, choose_style, write_package


def spec(kind='process', **extra):
    count = 1 if kind in {'quote', 'metric'} else 3
    return MotionSpec.model_validate(dict(kind=kind, title='How this works', duration_seconds=12,
        illustrative=True, items=[{'label': f'Step {i+1}', 'detail': '' if kind=='bars' or kind=='hub_spoke' and i==0 else 'A concrete example',
            **({'value': i+1} if kind in {'bars', 'metric'} else {})} for i in range(count)], **extra))


@pytest.mark.parametrize('kind', ['process','timeline','comparison','bars','layers','hub_spoke','checklist','quote','metric'])
@pytest.mark.parametrize('theme', ['charcoal','paper','slate'])
def test_every_layout_theme_is_reusable_and_deterministic(kind, theme):
    item = spec(kind, theme=theme)
    a = render_html(item)
    assert a == render_html(item)
    assert '1920' in a and '1080' in a
    assert 'Math.random' not in a and 'setInterval' not in a
    assert 'Illustrative example' in a
    assert f'data-kind="{kind}"' in a


def test_catalog_contains_real_renderers_not_only_style_names():
    assert {s['id'] for s in catalog()['styles']} == {
        'process','timeline','comparison','bars','layers','hub_spoke','checklist','quote','metric'}


@pytest.mark.parametrize('changes', [dict(kind='unknown'), dict(theme='neon'), dict(duration_seconds=2),
    dict(items=[]), dict(items=[{'label':'x'*90}]), dict(kind='bars',items=[{'label':'A'},{'label':'B'}]),
    dict(kind='metric',items=[{'label':'Amount','value':float('nan')}]),
    dict(illustrative=False, evidence_ids=[],source_label='')])
def test_invalid_or_unsupported_graphics_fail_closed(changes):
    data=spec().model_dump(); data.update(changes)
    with pytest.raises(ValidationError): MotionSpec.model_validate(data)


def test_reading_time_is_enforced_not_silently_truncated():
    data=spec().model_dump(); data.update(duration_seconds=4,items=[
        {'label':'Explanation','detail':'one two three four five six seven eight nine ten'} for _ in range(5)])
    with pytest.raises(ValidationError,match='reading'): MotionSpec.model_validate(data)


def test_html_text_cannot_execute_code():
    data=spec().model_dump(); data['title']='</script> <script>alert(1)</script>'
    html=render_html(MotionSpec.model_validate(data))
    assert '</script><script>alert(1)' not in html
    assert '&lt;/script&gt;' in html


def test_same_topic_can_use_different_semantic_graphics():
    assert choose_style('Show the timeline of releases') == 'timeline'
    assert choose_style('Compare the two choices') == 'comparison'
    assert choose_style('Show the actual product demonstration', strong_footage=True) is None
    assert choose_style('Show a beautiful abstract background') is None


def test_package_is_cached_by_complete_content(tmp_path):
    first=write_package(spec(),tmp_path)
    stamp=(tmp_path/'index.html').stat().st_mtime_ns
    assert write_package(spec(),tmp_path)['input_hash']==first['input_hash']
    assert (tmp_path/'index.html').stat().st_mtime_ns==stamp
    changed=spec(theme='paper')
    assert write_package(changed,tmp_path)['input_hash']!=first['input_hash']
    assert json.loads((tmp_path/'motion_spec.json').read_text())['theme']=='paper'


def test_modified_package_cannot_be_approved(tmp_path):
    from pipeline.motion_library import package_hash
    manifest=write_package(spec(),tmp_path)
    assert package_hash(tmp_path)==manifest['input_hash']
    (tmp_path/'index.html').write_text('changed',encoding='utf-8')
    with pytest.raises(ValueError,match='changed'): package_hash(tmp_path)


def test_render_requires_review_before_any_external_call(tmp_path,monkeypatch):
    from pipeline import motion_library as lib
    manifest=write_package(spec(),tmp_path)
    monkeypatch.setattr(lib.subprocess,'run',lambda *a,**k: pytest.fail('unapproved external call'))
    with pytest.raises(ValueError,match='approve'):
        lib.render_approved_package(tmp_path,tmp_path/'out.mp4',None,12)
    with pytest.raises(ValueError,match='duration'):
        lib.render_approved_package(tmp_path,tmp_path/'out.mp4',manifest['input_hash'],9)


def test_runtime_integrity_and_cached_reuse(tmp_path,monkeypatch):
    import hashlib
    from pipeline import motion_library as lib
    runtime=tmp_path/'runtime.js'; runtime.write_bytes(b'test runtime')
    monkeypatch.setattr(lib,'GSAP_SHA256',hashlib.sha256(runtime.read_bytes()).hexdigest())
    lib.stage_runtime(tmp_path/'package',runtime)
    lib.stage_runtime(tmp_path/'package')
    (tmp_path/'package/assets/gsap.min.js').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='integrity'): lib.stage_runtime(tmp_path/'package',runtime)
