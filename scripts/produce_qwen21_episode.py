"""Source-led Qwen evaluation episode using existing channel audio/render utilities."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scripts import produce_astra_episode as shared

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT/'data/episodes/episode_20260920_qwen_image21'
SOURCES = {
    'release': 'https://qwen.ai/blog?id=qwen-image-2.1',
    'repository': 'https://raw.githubusercontent.com/QwenLM/Qwen-Image-2.1/main/README.md',
    'model_card': 'https://huggingface.co/Qwen/Qwen-Image-2.1/raw/main/README.md',
    'license': 'https://raw.githubusercontent.com/QwenLM/Qwen-Image-2.1/main/LICENSE',
    'comfy': 'https://blog.comfy.org/p/qwen-image-21-in-comfyui-open-weight',
}
PUBLIC_URLS = {**SOURCES, 'repository':'https://github.com/QwenLM/Qwen-Image-2.1',
               'model_card':'https://huggingface.co/Qwen/Qwen-Image-2.1',
               'license':'https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE'}
DIRECTOR = '''Read only the following transcript, in the original Zubenelgenubi voice. One consistent young adult male, ordinary American English, calmly explaining useful technology to one curious friend. Aim for 165 to 172 words per minute. Connected phrases, short natural pauses when the thought changes. Understated and lightly curious, never a salesman or announcer. No dramatic performance, breathy or muffled endings, forced bass, whispering, vocal fry, exaggerated jokes, other voices, music or sound effects. Complete every sentence. Pronounce Qwen as kwen, ComfyUI as Comfy U I, GPU as G P U, and alpha as al-fuh. Transcript follows:\n'''


def acquire():
    ledger=[]
    for sid,url in SOURCES.items():
        dest=EP/'research'/f'{sid}.txt'
        if not dest.exists():
            response=requests.get(url,timeout=45);response.raise_for_status()
            text=response.text
            if sid in {'release','comfy'}:
                soup=BeautifulSoup(text,'html.parser')
                for node in soup(['script','style','nav','footer','header']):node.decompose()
                text=(soup.find('article') or soup.find('main') or soup).get_text('\n',strip=True)
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text,encoding='utf-8')
        ledger.append({'id':sid,'url':PUBLIC_URLS[sid],'path':str(dest),'sha256':shared.sha(dest)})
    shared.dump(EP/'research/sources.json',ledger)
    readme=(EP/'research/repository.txt').read_text(encoding='utf-8')
    urls=re.findall(r'<img[^>]+src="([^"]+)"',readme)
    model=(EP/'research/model_card.txt').read_text(encoding='utf-8')
    urls+=re.findall(r'https[^\s"<>]+?\.(?:png|jpg)',model)
    urls=[urljoin(SOURCES['repository'],u) for u in urls]
    urls.append('https://raw.githubusercontent.com/QwenLM/Qwen-Image-2.1/main/assets/logo.png')
    assets=[];seen=set()
    for url in urls:
        name=url.rsplit('/',1)[-1]
        if name in seen:continue
        seen.add(name);dest=EP/'media'/name
        if not dest.exists():
            response=requests.get(url,timeout=45);response.raise_for_status()
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(response.content)
        from PIL import Image
        image=Image.open(dest);image.verify()
        assets.append({'id':dest.stem,'path':str(dest),'url':url,'source_url':PUBLIC_URLS['repository'],
            'sha256':shared.sha(dest),'kind':'official_showcase_not_our_generation',
            'rights_basis':'Qwen Research License; private research/evaluation only; commercial publication not cleared',
            'license_path':str(EP/'research/license.txt'),'publishing_enabled':False})
    shared.dump(EP/'media/ledger.json',assets)
    (EP/'NOTICE.txt').write_text('Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, Copyright (c) 2026 Hangzhou Tongyi Laboratory Technology Co., Ltd. All Rights Reserved.\nSource visuals are scaled/cropped and annotated for private evaluation. No affiliation or endorsement is claimed. Original narration and editorial graphics by Diffusion Daily.\n',encoding='utf-8')
    print('Sources',len(ledger),'official assets',len(assets),flush=True)


def prepare():
    draft=EP/'script_draft.md'
    if not draft.exists():draft=ROOT/'research/episodes/qwen_image21_script.md'
    raw=draft.read_text(encoding='utf-8')
    source_map={'01_hook':['release','model_card'],'02_alpha':['model_card'],'03_edit':['repository'],
                '04_references':['repository'],'05_size':['repository','comfy'],'06_license':['license'],
                '07_decision':['model_card','repository','license']}
    chapters=[]
    for block in raw.split('\n## ')[1:]:
        header,body=block.split('\n',1);ident,title=header.split(' | ',1)
        chapters.append({'id':ident,'title':title,'paragraphs':body.strip().split('\n\n'),
                         'sources':[PUBLIC_URLS[x] for x in source_map[ident]],'evidence_ids':source_map[ident]})
    shared.dump(EP/'script.json',{'title':'Qwen-Image 2.1: Better Images Are Only Half the Story',
        'chapters':chapters,'word_count':len(re.findall(r'\S+', ' '.join(p for c in chapters for p in c['paragraphs']))),
        'target_duration_seconds':480,'publishing_enabled':False})
    shared.dump(EP/'brief.json',{'approved_for_private_production':True,'approval_basis':'User delegated topic, hook and production choices',
        'selected_topic':'Qwen-Image 2.1','idea_source':'data/research/latest_ideas.json',
        'selection_reason':'Fresh primary release with concrete editing/transparency examples and a consequential license caveat; no verified viral-demand claim',
        'opening_candidates':[{'mode':'friction','text':'You generate an image, and it looks great. Then you try to use it.'},
          {'mode':'demonstration','text':'That empty space around the subject is the useful part.'},
          {'mode':'context_reversal','text':'A better image model is not always about a prettier image.'},
          {'mode':'verdict','text':'The most useful part of this release might happen after image generation.'}],
        'selected_opening':0,'voice':'Zubenelgenubi','subtitles':False,'width':1920,'height':1080,
        'publishing_enabled':False,'rights_review_required':True,'generated_documentary_stills':False})
    print('Words',shared.read(EP/'script.json')['word_count'],flush=True)


def review():
    shared.EP=EP;shared.review()


def narrate():
    shared.EP=EP;shared.DIRECTOR=DIRECTOR
    overrides=shared.read(EP/'audio/director_overrides.json') if (EP/'audio/director_overrides.json').exists() else {}
    shared.narrate(overrides)


def repair_audio():
    """Regenerate only rejected chapter inputs; retain each paid-attempt receipt."""
    report=shared.read(EP/'audio_qc.json')
    overrides_path=EP/'audio/director_overrides.json'
    overrides=shared.read(overrides_path) if overrides_path.exists() else {}
    attempts_path=EP/'audio/repair_attempts.json'
    attempts=shared.read(attempts_path) if attempts_path.exists() else []
    for row in report['chapters']:
        if row['passed']:continue
        ident=row['chapter'];count=sum(x['chapter']==ident for x in attempts)
        if count>=2:raise RuntimeError('Two audio repairs exhausted: '+ident)
        receipt=shared.read(EP/'audio'/f'{ident}_receipt.json')
        attempts.append({'chapter':ident,'rejected_receipt':receipt,'qc':row,'attempt':count+1})
        overrides[ident]=DIRECTOR+f'\nConsistency pass {count+1}: Keep the same easy conversational tone and vocal placement from beginning to end. Do not lower or soften your voice for the closing sentence. No dramatic range or emphasis.\n'
    shared.dump(overrides_path,overrides);shared.dump(attempts_path,attempts)
    narrate()


def audio_qc():
    from scripts import produce_fable_mythos_episode as audio
    audio.EP=EP;audio.audio_review()
    report=shared.read(EP/'audio_qc.json')
    report.update(narration_hash=shared.sha(EP/'narration.json'),script_hash=shared.sha(EP/'script.json'),audio_files=audio_fingerprints())
    shared.dump(EP/'audio_qc.json',report)


def audio_fingerprints():
    narration=shared.read(EP/'narration.json')
    return {'master':shared.sha(Path(narration['path'])),
            'chapters':{row['id']:shared.sha(Path(row['path'])) for row in narration['chapters']}}


def graphics():
    """Reuse the channel's deterministic React/FFmpeg render path for simple diagrams."""
    public=ROOT/'remotion/public/qwen21';public.mkdir(parents=True,exist_ok=True)
    for name in ['example-06.png','example-18.png','example-19.png','logo.png']:
        shutil.copy2(EP/'media'/name,public/name)
    kinds=['alpha','edit','references','components','workflow','permission','checks','outro','opaque','alpha_channel']
    entry=ROOT/'remotion/src/qwen21-entry.tsx'
    def render(kind):
        dest=EP/'motion'/f'{kind}.mp4';props={'kind':kind,'seconds':12}
        sig=hashlib.sha256((shared.sha(entry)+json.dumps(props,sort_keys=True)+''.join(shared.sha(p) for p in sorted(public.glob('*.png')))).encode()).hexdigest()
        receipt=dest.with_suffix('.render.json')
        if dest.exists() and receipt.exists() and shared.read(receipt).get('input_hash')==sig:return
        frames=EP/'motion/frames'/kind;frames.mkdir(parents=True,exist_ok=True)
        pp=dest.with_suffix('.props.json');shared.dump(pp,props)
        executable=ROOT/'remotion/node_modules/.bin/remotion.cmd'
        cmd=[str(executable),'render','src/qwen21-entry.tsx','Qwen21Graphic',str(frames.resolve()),f'--props={pp.resolve()}',
             '--browser-executable=C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe','--sequence','--image-format=jpeg','--jpeg-quality=95','--concurrency=3','--muted']
        print('Rendering diagram',kind,flush=True)
        r=subprocess.run(cmd,cwd=ROOT/'remotion',capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1200)
        dest.with_suffix('.render.log').write_text(r.stdout+r.stderr,encoding='utf-8')
        if r.returncode:raise RuntimeError((r.stdout+r.stderr)[-2500:])
        pics=sorted(frames.glob('*.jpeg')) or sorted(frames.glob('*.jpg'))
        if len(pics)!=360:raise RuntimeError(f'Incomplete graphic {kind}: {len(pics)}')
        listing=frames/'sequence.txt'
        listing.write_text(''.join("file '"+p.resolve().as_posix()+"'\nduration 0.033333333333\n" for p in pics),encoding='utf-8')
        shared.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-an','-r','30','-t','12','-c:v','libx264','-preset','fast','-crf','17','-threads','2','-pix_fmt','yuv420p',str(dest)])
        shared.dump(receipt,{'input_hash':sig,'output_hash':shared.sha(dest),'width':1920,'height':1080,'original_diagram':True})
        print('Diagram ready',kind,flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(render,kinds))
    shared.dump(EP/'motion/design_contract.json',{'framework':'Existing Remotion source-explainer path; original simple SVG/React scenes',
        'palette':{'paper':'#F2F0E9','ink':'#17221F','sage':'#9CAD9D','clay':'#AB6450'},'font':'Inter',
        'camera':'locked','motion':'clause-level reveals, ease-out, no decorative zoom/spin',
        'source_assets':['example-06','example-18','example-19','logo'],'render':'1920x1080 30fps',
        'private_evaluation_only':True,'framework_implementation_copied':False})


def package():
    """Local review metadata only. No upload or publication capability."""
    narration=shared.read(EP/'narration.json')
    script=shared.read(EP/'script.json')
    chapters=[]
    for spoken,chapter in zip(narration['chapters'],script['chapters']):
        sec=int(spoken['start']);chapters.append(f'{sec//60:02d}:{sec%60:02d} {chapter["title"]}')
    description=('A nice image is only the starting point. Qwen-Image 2.1 brings transparent output, targeted edits, and multiple reference images into one workflow. '
        'We walk through the official examples, explain what to inspect, and cover the research-license restriction before considering paid work.\n\n'
        'This is a private editorial evaluation, not an independent model benchmark. The model was not installed or tested for this episode. '
        'Source imagery is Qwen\'s published material; the compositing explanations are ours. Commercial publication and deployment rights are not cleared.\n\n'
        +'\n'.join(chapters)+'\n\nSources\n'+'\n'.join(dict.fromkeys(PUBLIC_URLS.values())))
    shared.dump(EP/'review_metadata.json',{'title':'Qwen-Image 2.1: Can We Skip the Cleanup?',
        'alternate_title':script['title'],'description':description,'chapters':chapters,
        'tags':['Qwen Image 2.1','image generation','image editing','ComfyUI','transparent images'],
        'channel':'Diffusion Daily','visibility':'private review only','publishing_enabled':False,
        'narration':'Original synthetic Zubenelgenubi voice via Gemini TTS','thumbnail':'thumbnail.jpg',
        'synthetic_media':True,'rights_review_required':True,'source_outputs_not_independently_tested':True})
    (EP/'description.txt').write_text(description,encoding='utf-8')
    usage=shared.read(EP/'provider_usage.json')
    paid_audio=[{'id':c['id'],'usage':c.get('usage',{})} for c in narration['chapters']]
    attempts=EP/'audio/repair_attempts.json'
    if attempts.exists():paid_audio += [{'id':r['chapter']+'_rejected','usage':r['rejected_receipt'].get('usage',{})} for r in shared.read(attempts)]
    shared.dump(EP/'production_usage.json',{'openrouter_usd':usage['openrouter_usd'],
        'openrouter_cap_usd':usage['openrouter_cap_usd'],'magichour_credits':0,
        'gemini_tts_attempts':paid_audio,'gemini_usd':'not returned by provider; no dollar estimate asserted',
        'thumbnail_generation':'Built-in image generation plus exact official-logo compositing; account billing not returned'})
    print('Review package metadata ready',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['acquire','prepare','review','narrate','audio_qc','repair_audio','graphics','package'])
    args=parser.parse_args();globals()[args.stage]()
