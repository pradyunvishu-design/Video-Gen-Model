"""DreamX review episode. Reuse the channel's existing audio/render utilities.

No publishing, model installation, credential logging, or provider call occurs
in the research stage. Each later stage requires its own verified inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.produce_astra_episode import dump, read, sha, run, probe

EP = ROOT / 'data/episodes/episode_20260907_dreamx_creator'
SOURCES = {
    'repository': 'https://github.com/AMAP-ML/DreamX-Creator',
    'paper': 'https://arxiv.org/html/2608.31106v1',
    'license': 'https://raw.githubusercontent.com/AMAP-ML/DreamX-Creator/main/LICENSE',
    'generation': 'https://raw.githubusercontent.com/AMAP-ML/DreamX-Creator/main/audio_video_generation/README.md',
    'refinement': 'https://raw.githubusercontent.com/AMAP-ML/DreamX-Creator/main/video_refiner/README.md',
    'weights': 'https://raw.githubusercontent.com/AMAP-ML/DreamX-Creator/main/checkpoints/README.md',
}


def research():
    records = []
    for sid, url in SOURCES.items():
        dest = EP / 'research' / f'{sid}.txt'
        if dest.exists():
            print('Cached source', sid, flush=True)
            continue
        response = requests.get(url, timeout=50)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        if sid in {'repository', 'paper'}:
            content = soup.find('article') or soup.find('main') or soup
            for node in content(['script','style','nav','footer']):
                node.decompose()
            text = content.get_text('\n', strip=True)
            if sid == 'paper':
                figures = []
                for figure in content.find_all('figure'):
                    img = figure.find('img')
                    caption = figure.find('figcaption')
                    if img:
                        figures.append({'id':figure.get('id'), 'url':urljoin(url,img.get('src','')), 'caption':caption.get_text(' ',strip=True) if caption else '', 'source_url':url})
                dump(EP/'research/figures.json',figures)
        else:
            text = response.text
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding='utf-8')
        records.append({'id':sid,'url':url,'path':str(dest),'sha256':sha(dest),'source_type':'primary','retrieved_date':'2026-09-07'})
        print('Source saved',sid,len(text),'characters',flush=True)
    existing = EP/'research/sources.json'
    old = read(existing) if existing.exists() else []
    dump(existing,list({r['id']:r for r in old+records}.values()))
    dump(EP/'brief.json',{
        'schema_version':1,'episode_id':EP.name,'title':'This New Open AI Model Generates Video AND Sound',
        'subject':'DreamX-Creator 1.0','format':'source-led release explainer',
        'promise':'Explain whether joint generation addresses sound-to-action timing, what the release contains, and how to judge its demos without confusing a showcase with an independent benchmark.',
        'not_claimed':['Independent model testing','Guaranteed consumer-GPU compatibility','Commercial-model superiority','Native base-generation 2K','Free computing'],
        'duration_policy':'Target eight minutes with substantive explanation; measure actual narration, never pad with repeated footage',
        'target_duration_seconds':480,
        'delivery':{'width':1920,'height':1080,'fps':30,'subtitles':False,'voice':'Zubenelgenubi','publishing_enabled':False},
        'source_audio_policy':'Use only explicitly selected isolated demonstration windows; never mix source speech under narration.',
        'review_required':True,
    })


def assets():
    """Only the versioned Apache-licensed repository teaser, not the demo reel."""
    from PIL import Image
    url='https://raw.githubusercontent.com/AMAP-ML/DreamX-Creator/main/dreamx-creator_teaser.png'
    dest=EP/'media/dreamx_teaser.png'
    if not dest.exists():
        response=requests.get(url,timeout=60)
        response.raise_for_status()
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(response.content)
    with Image.open(dest) as image:
        dimensions=list(image.size)
    dump(EP/'media/ledger.json', [{
        'id':'dreamx_teaser','path':str(dest),'source_url':url,
        'publisher':'DreamX Team','source_type':'official research teaser',
        'rights_basis':'Versioned repository asset under repository Apache-2.0 license; attribution and license retained',
        'license_path':str(EP/'research/license.txt'),'sha256':sha(dest),
        'dimensions':dimensions,'synthetic_media':True,
        'usage':'Published model/research evidence, never independent test footage',
    }])
    print('Teaser ready',dimensions,flush=True)


def narrate(repair_ids=()):
    from scripts import produce_astra_episode as production
    repair_path=EP/'audio/repair_attempt.json'
    if not repair_ids and repair_path.exists():
        repair_ids=read(repair_path)['chapters']
    production.EP=EP
    production.DIRECTOR='''Read only the transcript below in the original Zubenelgenubi voice. Clear American English, one knowledgeable young adult explaining the work to a friend. Aim for 158 to 166 words per minute, not an announcer. Underplay the delivery; connected sentences, light breaths only at changes of thought, normal midrange resonance, clear consonants, complete sentence endings. No forced bass, vocal fry, whispering, dramatic pauses, performed jokes, extra words, background sounds, effects or music. Keep the same voice throughout. Say DreamX as Dream Ex, and two-K as two kay. Transcript follows:\n'''
    overrides={cid:production.DIRECTOR.replace('Transcript follows:\n',
        'Maintain full, steady conversational resonance from the first word to the last. '
        'No breathy or whispered asides, no impersonation, no change of speaker, and no creaky sentence endings. Transcript follows:\n')
        for cid in repair_ids}
    production.narrate(director_overrides=overrides)


def repair_audio():
    report=read(EP/'audio_qc.json')
    failed=[x['chapter'] for x in report['chapters'] if not x['passed']]
    if not failed:
        print('No audio repair required',flush=True)
        return
    attempt_path=EP/'audio/repair_attempt.json'
    if attempt_path.exists() and read(attempt_path).get('completed'):
        raise RuntimeError('One bounded audio repair already completed. Review any remaining defects.')
    if not attempt_path.exists():
        dump(EP/'audio/qc_before_repair.json',report)
        dump(EP/'audio/narration_before_repair.json',read(EP/'narration.json'))
        dump(attempt_path,{'chapters':failed,'reason':'Automatic audio QC rejection',
             'originals_retained':True,'completed':False,'max_attempts':1})
    narrate(read(attempt_path)['chapters'])
    fit_duration()
    dump(attempt_path,{**read(attempt_path),'completed':True})


def audio_qc():
    # Ensure the model is already cached; never spend on external ASR fallback.
    from faster_whisper.utils import download_model
    download_model('small.en',local_files_only=True)
    from pipeline.captions import _whisper_model
    _whisper_model('small.en')
    from scripts import produce_fable_mythos_episode as shared
    shared.EP=EP
    shared.audio_review()
    reuse=EP/'audio/timing_reuse.json'
    if reuse.exists():
        report=read(EP/'audio_qc.json')
        report['timing_reuse']=read(reuse)
        dump(EP/'audio_qc.json',report)


def voice_review():
    """Reuse the existing audio-capable outlier adjudicator; preserve raw flags."""
    from scripts import extend_astra_episode as reviewer
    reviewer.EP=EP
    reviewer.production.EP=EP
    (EP/'qa').mkdir(exist_ok=True)
    reviewer.voice_review()


def reuse_timed_transcripts():
    """Retime cached ASR only for bit-identical source speech after tempo changes.

    The repaired chapter must be transcribed afresh. Waveform/voice QC always
    runs on the actual new audio, including unchanged source performances.
    """
    before=EP/'audio/narration_before_repair.json'
    if not before.exists():
        return
    old={c['id']:c for c in read(before)['chapters']}
    reused=[]
    for current in read(EP/'narration.json')['chapters']:
        previous=old.get(current['id'])
        if not previous or not previous.get('tempo_factor'):
            continue
        old_digest=hashlib.sha256((sha(Path(current['source_path']))+
            f':atempo:{previous["tempo_factor"]:.9f}').encode()).hexdigest()[:12]
        if old_digest!=previous['hash']:
            continue
        source=EP/'audio'/f'{current["id"]}_{previous["hash"]}_words.json'
        target=EP/'audio'/f'{current["id"]}_{current["hash"]}_words.json'
        if source.exists() and not target.exists():
            ratio=previous['tempo_factor']/current['tempo_factor']
            words=[{**w,'start':min(current['duration'],w['start']*ratio),
                    'end':min(current['duration'],w['end']*ratio)} for w in read(source)]
            dump(target,words)
            reused.append({'chapter':current['id'],'source_cache':str(source),
                'target_cache':str(target),'time_scale':ratio,'source_audio_identity_verified':True})
    if reused:
        dump(EP/'audio/timing_reuse.json',{'method':'Pitch-preserving tempo transform of ASR for SHA256-identical source audio. Actual new waveform/voice QC rerun.', 'chapters':reused})


def capture_checkpoint(path: Path, old: dict, rows: list[dict]) -> None:
    """Keep untouched receipts through interrupted refreshes; replace atomically."""
    merged={**old, **{row['id']:row for row in rows}}
    temporary=path.with_suffix('.pending.json')
    dump(temporary,list(merged.values()))
    os.replace(temporary,path)


def source_focus():
    """Capture exact DOM ranges with their screenshot, never estimate text bounds."""
    from playwright.sync_api import sync_playwright
    from pipeline.capture import _exact_text_region, _load_page, _assert_capture_is_clean
    destination=EP/'captures/repository_input_focus.png'
    receipt=EP/'captures/source_focus.json'
    if receipt.exists() and destination.exists() and read(receipt).get('sha256')==sha(destination):
        print('Cached exact source focus',flush=True)
        return
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,channel='chrome')
        page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
        page.route('**/*',lambda r:r.abort() if r.request.resource_type=='media' else r.continue_())
        _load_page(page,SOURCES['repository'])
        page.add_style_tag(content='html{scroll-behavior:auto!important}body{zoom:1.5}video{visibility:hidden}')
        page.evaluate('document.fonts.ready')
        loc=page.locator('article p').filter(has_text='Given a first frame and a text prompt').first
        if not loc.count():
            raise RuntimeError('Exact source paragraph unavailable')
        loc.evaluate("el=>el.scrollIntoView({block:'center',behavior:'instant'})")
        page.wait_for_timeout(300)
        _assert_capture_is_clean(page,moment='Exact DreamX evidence underline')
        bounds=loc.bounding_box()
        annotations=[]
        for phrase,start,end,cue in [
            ('first frame',.45,2.1,'Give it a starting image and a prompt'),
            ('native joint audio-video generation',2.5,5.8,'it generates the picture and sound together'),
        ]:
            region=_exact_text_region(loc,phrase)
            if region is None:
                raise RuntimeError('Exact single-line range unavailable: '+phrase)
            viewport_region={
                'x':(bounds['x']+region['x']*bounds['width'])/1920,
                'y':(bounds['y']+region['y']*bounds['height'])/1080,
                'width':region['width']*bounds['width']/1920,
                'height':region['height']*bounds['height']/1080,
            }
            annotations.append({'phrase':phrase,'region':viewport_region,'start':start,'end':end,
                'narration_cue':cue,'measurement':'exact single-line browser DOM Range'})
        page.screenshot(path=str(destination),animations='disabled')
        dump(receipt,{'path':str(destination),'sha256':sha(destination),'url':page.url,
            'viewport':[1920,1080],'visible_text':loc.inner_text(),'annotations':annotations,
            'source_id':'repository','rights_basis':'Apache-2.0 repository documentation',
            'license_path':str(EP/'research/license.txt')})
        browser.close()
    print('Exact source annotations captured',flush=True)


def underline_filters(annotations: list[dict], seconds: float) -> str:
    """Draw a thin stroke left-to-right, strictly inside a verified source line.

    Input uses crop(60,90,1340,900), scale(1608,1080), then centered pad.
    Twenty-four deterministic segments avoid drifting raster camera movement.
    """
    filters=[]
    for a in annotations:
        if a.get('measurement')!='exact single-line browser DOM Range':
            raise ValueError('Underline lacks verified DOM geometry')
        r=a['region']
        x=(r['x']*1920-60)*1.2+156
        y=((r['y']+r['height'])*1080-90)*1.2+3
        width=r['width']*1920*1.2
        start,end=float(a['start']),float(a['end'])
        if not (0<=start<end<=seconds and 100<=x<x+width<=1820 and 80<=y<=980 and width>5):
            raise ValueError('Annotation outside its time or safe source frame')
        for i in range(24):
            left=round(x+width*i/24)
            right=round(x+width*(i+1)/24)
            threshold=start+.65*math.acos(1-2*i/24)/math.pi
            filters.append(f"drawbox=x={left}:y={round(y)}:w={max(1,right-left)}:h=3:color=0xBA3D36:t=fill:enable='between(t,{threshold:.4f},{end:.4f})'")
    return ','.join(filters)


def opening_preview():
    """Small narrated review export, explicitly not the finished eight-minute edit."""
    narration=read(EP/'narration.json')
    audio=next(c for c in narration['chapters'] if c['id']=='opening')
    qc=read(EP/'audio/opening_qc.json')
    if not qc['passed']:
        raise RuntimeError('Opening narration must pass before preview')
    folder=EP/'preview'
    folder.mkdir(exist_ok=True)
    total_frames=round((audio['duration']+.6)*30)
    shots=[('motion/timing.mp4',300,False),('captures/repository_00.png',300,True),
           ('captures/repository_input_focus.png',180,True),('motion/stages.mp4',210,False),
           ('captures/repository_03.png',total_frames-990,True)]
    if shots[-1][1]<=0 or shots[-1][1]>360:
        raise RuntimeError('Opening length needs an intentional edit')
    focus=read(EP/'captures/source_focus.json')
    if focus['sha256']!=sha(EP/'captures/repository_input_focus.png'):
        raise RuntimeError('Annotation geometry belongs to a different screenshot')
    paths=[]
    for i,(relative,frames,is_still) in enumerate(shots):
        source=EP/relative
        if not source.exists():
            raise RuntimeError('Missing preview source '+relative)
        filt=('crop=1340:1080:60:0,pad=1920:1080:(ow-iw)/2:0:color=0xF3F2ED,' if is_still else '')
        if relative=='captures/repository_input_focus.png':
            filt='crop=1340:900:60:90,scale=1608:1080:flags=lanczos,pad=1920:1080:(ow-iw)/2:0:color=0xF3F2ED,'
            filt+=underline_filters(focus['annotations'],frames/30)+','
        filt+='setsar=1,scale=in_range=auto:out_range=tv:out_color_matrix=bt709,format=yuv420p'
        key=hashlib.sha256(f'{sha(source)}:{frames}:{filt}'.encode()).hexdigest()[:12]
        dest=folder/f'shot_{i}_{key}.mp4'
        if not dest.exists():
            run(['ffmpeg','-y','-v','error',*(['-loop','1','-framerate','30'] if is_still else []),
                 '-i',str(source),'-an','-vf',filt,'-frames:v',str(frames),'-r','30','-c:v','libx264',
                 '-preset','fast','-crf','18','-pix_fmt','yuv420p','-colorspace','bt709','-color_trc','bt709',
                 '-color_primaries','bt709','-color_range','tv',str(dest)])
        paths.append(dest)
    playlist=folder/'opening.concat.txt'
    playlist.write_text(''.join("file '"+str(p.resolve()).replace('\\','/')+"'\n" for p in paths),encoding='utf-8')
    final=folder/'DreamX_Opening_Focused_1080p.mp4'
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(playlist),'-i',audio['path'],
         '-map','0:v:0','-map','1:a:0','-af','apad=pad_dur=0.6','-t',str(total_frames/30),
         '-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(final)])
    run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'])
    dump(folder/'focused_receipt.json',{'artifact':str(final),'duration_seconds':total_frames/30,
        'kind':'Opening review only, not finished eight-minute episode','audio_hash':sha(Path(audio['path'])),
        'script_hash':sha(EP/'script.json'),'sources':[r[0] for r in shots],
        'audio_policy':'One approved synthesized narrator, no source audio or music',
        'centered_source_column':True,'source_annotation_receipt':str(EP/'captures/source_focus.json'),
        'source_annotations_timed_to_narration':True,'full_decode_passed':True,'publishing_enabled':False})
    print('Opening preview ready',str(final),flush=True)


def duration_fit_factor(source_seconds: float, chapter_count: int, target: float = 478.8) -> float:
    if chapter_count < 1 or source_seconds <= 0:
        raise ValueError('A measured narration and at least one chapter are required')
    spoken_target=target-.18*(chapter_count-1)
    if spoken_target <= 0:
        raise ValueError('Chapter gaps exceed the target')
    factor=source_seconds/spoken_target
    if not .94<=factor<=1.06:
        raise ValueError(f'Duration fit needs {factor:.3f}x. Revise delivery, do not pad or cut words.')
    return factor


def fit_duration():
    """Fit a near-eight-minute performance without cuts or pitch changes.

    A large mismatch is an editorial problem, not permission to drag the voice
    or pad the video. Source synthesis files and receipts remain untouched.
    """
    from pipeline.render_v2 import concat_audio, make_silence, duration
    source_path=EP/'narration_source.json'
    narration=read(EP/'narration.json')
    if narration.get('duration_conformed'):
        original=read(source_path)
    else:
        original=narration
        dump(source_path,original)
    target=478.8  # 1.2-second sentence-safe ending yields an eight-minute edit.
    pause=.18
    source_seconds=sum(ch['duration'] for ch in original['chapters'])
    factor=duration_fit_factor(source_seconds,len(original['chapters']),target)
    chapters=[]
    paths=[]
    cursor=0.
    gap=make_silence(EP/'audio/pause.wav',180)
    for i,ch in enumerate(original['chapters']):
        digest=hashlib.sha256((sha(Path(ch['path']))+f':atempo:{factor:.9f}').encode()).hexdigest()[:12]
        dest=EP/'audio'/f'{ch["id"]}_{digest}_timed.wav'
        if not dest.exists():
            run(['ffmpeg','-y','-v','error','-i',ch['path'],'-af',f'atempo={factor:.9f}',
                 '-ar','48000','-ac','1','-c:a','pcm_s16le',str(dest)])
        seconds=duration(dest)
        chapters.append({**ch,'path':str(dest),'source_path':ch['path'],'hash':digest,
                         'duration':seconds,'start':cursor,'tempo_factor':factor})
        paths.append(dest)
        cursor+=seconds
        if i<len(original['chapters'])-1:
            paths.append(gap)
            cursor+=pause
    master=concat_audio(paths,EP/'narration_zubenelgenubi_8min.wav')
    seconds=duration(master)
    dump(EP/'narration.json',{**original,'chapters':chapters,'path':str(master),'duration':seconds,
        'duration_conformed':True,'target_with_end_hold_seconds':480,'end_hold_seconds':1.2,
        'source_manifest':str(source_path),'tempo_factor':factor,'words_removed':0,'pitch_shift':False})
    if abs(seconds-target)>1:
        raise RuntimeError(f'Unexpected conformed duration {seconds}; review before assembly')
    print('Narration fitted',round(seconds,3),'seconds; tempo',round(factor,4),flush=True)


def captures():
    """Clean, exact source views from the Apache-licensed repository docs.

    No account, downloads, source video/audio, cosmetic replacement text, or
    unverified underlines. Browser type is enlarged before rasterization.
    """
    from playwright.sync_api import sync_playwright
    from pipeline.capture import _load_page, _assert_capture_is_clean, _blocked_page_reason
    targets = {
        'repository': ('https://github.com/AMAP-ML/DreamX-Creator', [
            'DreamX-Creator 1.0: Democratizing', 'News', 'weights', 'Gated Cross-Modal Attention', 'Quick Start',
            'audio_video_generation', 'video_refiner', 'License',
        ]),
        'generation': ('https://github.com/AMAP-ML/DreamX-Creator/blob/main/audio_video_generation/README.md', [
            'DreamX', 'checkpoint', 'Dependencies', 'input', 'prompt',
            'seed', 'fps', 'offload',
        ]),
        'refinement': ('https://github.com/AMAP-ML/DreamX-Creator/blob/main/video_refiner/README.md', [
            'DreamX', 'audio', 'checkpoint', 'Usage', 'Speed', 'fp8', 'decoder',
        ]),
        'weights': ('https://github.com/AMAP-ML/DreamX-Creator/blob/main/checkpoints/README.md', [
            'checkpoints', 'Hugging', 'download',
        ]),
    }
    out = EP/'captures'
    out.mkdir(parents=True, exist_ok=True)
    ledger_path=out/'ledger.json'
    old={x['id']:x for x in read(ledger_path)} if ledger_path.exists() else {}
    rows=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,channel='chrome')
        for sid,(url,phrases) in targets.items():
            page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
            page.route('**/*',lambda route: route.abort() if route.request.resource_type=='media' else route.continue_())
            try:
                _load_page(page,url)
                page.add_style_tag(content='html{scroll-behavior:auto!important}body{zoom:1.5}video{visibility:hidden}')
                page.evaluate('document.fonts.ready')
                for i,phrase in enumerate(phrases):
                    asset_id=f'{sid}_{i:02d}'
                    dest=out/f'{asset_id}.png'
                    prior=old.get(asset_id)
                    if prior and dest.exists() and sha(dest)==prior['sha256'] and prior.get('phrase')==phrase:
                        rows.append(prior)
                        continue
                    article=page.locator('article').first
                    if not article.count():
                        raise RuntimeError('No rendered source article; refusing empty capture')
                    matches=article.locator('h1,h2,h3,p,li,pre,td').filter(has_text=re.compile(re.escape(phrase),re.I))
                    candidates=[]
                    for j in range(min(matches.count(),40)):
                        loc=matches.nth(j)
                        if loc.is_visible():
                            text=loc.inner_text().strip()
                            candidates.append((len(text),j))
                    if not candidates:
                        print('No exact source region',asset_id,flush=True)
                        continue
                    loc=matches.nth(min(candidates)[1])
                    loc.evaluate("el=>el.scrollIntoView({block:'center',behavior:'instant'})")
                    page.wait_for_timeout(250)
                    _assert_capture_is_clean(page,moment='DreamX source region')
                    if _blocked_page_reason(page):
                        raise RuntimeError('Source blocked')
                    bounds=loc.bounding_box()
                    if not bounds or bounds['y']>950 or bounds['y']+bounds['height']<120:
                        raise RuntimeError('Source target not visible')
                    page.screenshot(path=str(dest),animations='disabled')
                    rows.append({'id':asset_id,'source_id':sid,'url':page.url,'phrase':phrase,
                        'visible_text':loc.inner_text(),'bounds':bounds,'path':str(dest),'sha256':sha(dest),
                        'rights_basis':'Apache-2.0 repository documentation, source attribution retained',
                        'license_path':str(EP/'research/license.txt'),'dimensions':[1920,1080],
                        'semantic_frame_review':'pending','underlines':False})
                    capture_checkpoint(ledger_path,old,rows)
                print('Source views',sid,len([r for r in rows if r['source_id']==sid]),flush=True)
            finally:
                page.close()
        browser.close()
    capture_checkpoint(ledger_path,{},rows)
    if len(rows)<8:
        raise RuntimeError('Insufficient source views; do not assemble repeated filler')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['research','assets','captures','narrate','fit_duration','audio_qc','repair_audio','reuse_timed_transcripts','opening_preview','source_focus','voice_review'])
    args=parser.parse_args()
    globals()[args.stage]()
