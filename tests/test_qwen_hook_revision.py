import re
import pytest
from scripts import revise_qwen21_hook as hook

def test_hook_embedded_images_are_all_declared():
    text=(hook.ROOT/'remotion/src/qwen21-hook-entry.tsx').read_text(encoding='utf-8')
    assert set(re.findall(r"pic\('([^']+)'\)",text))==set(hook.HOOK_ASSETS)

@pytest.fixture
def sources(tmp_path,monkeypatch):
    media=[];captures=[]
    for name,(kind,ident) in hook.HOOK_ASSETS.items():
        p=tmp_path/name;p.write_bytes(b'test-source')
        record={'id':ident,'path':str(p),'sha256':hook.shared.sha(p),'url':'https://example.com/'+name}
        (captures if kind=='article' else media).append(record)
    monkeypatch.setattr(hook.shared,'read',lambda p:captures if p.name=='ledger.json' and p.parent.name=='captures' else media)
    return tmp_path,media,captures

def test_hook_preserves_exact_asset_urls(sources):
    root,_,_=sources
    manifest=hook.hook_sources(root,[])
    assert all(a['url'].endswith(a['filename']) for a in manifest['assets'])
    assert manifest['source_counts']=={'example-04':1,'repo_local_masks':1}

def test_hook_blocks_third_source_appearance(sources):
    root,_,_=sources
    with pytest.raises(RuntimeError,match='two appearances'):
        hook.hook_sources(root,[{'kind':'picture','asset_id':'example-04'}]*2)

def test_hook_blocks_changed_asset(sources):
    root,_,_=sources
    (root/'example-04.png').write_bytes(b'changed')
    with pytest.raises(RuntimeError,match='Source changed'):hook.hook_sources(root,[])
