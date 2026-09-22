"""Non-destructive opening revision; reuse approved body audio and picture segments."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import re
from collections import Counter
from pathlib import Path
from scripts import produce_qwen21_episode as episode
from scripts import produce_astra_episode as shared

ROOT=Path(__file__).resolve().parents[1]
BASE=episode.EP
REV=BASE/'revisions/hook_v2'
FINAL=REV/'Qwen_Image_21_HookV2_1080p.mp4'
HOOK_ASSETS={'example-04.png':('picture','example-04'),
             'repo_local_masks.png':('article','repo_local_masks'), 'logo.png':('brand','logo')}
PARAGRAPHS=[
    "That background isn't white. It's gone. Qwen Image two point one can generate the cutout directly, instead of leaving you to remove the background afterward.",
    "This is their published example, not our own test. And it isn't just cutouts: you can mark the part you want changed.",
    "So can you actually skip the cleanup? We'll look at what these examples show, what still needs checking, and the license limit before you use it for paid work.",
]

def bind():
    episode.EP=REV
    shared.EP=REV

def hook_sources(base,body_rows):
    """Trace every embedded source to its original ledger and enforce repetition."""
    media={r['id']:r for r in shared.read(base/'media/ledger.json')}
    captures={r['id']:r for r in shared.read(base/'captures/ledger.json')}
    used=set(re.findall(r"pic\('([^']+)'\)",(ROOT/'remotion/src/qwen21-hook-entry.tsx').read_text(encoding='utf-8')))
    if used!=set(HOOK_ASSETS):raise RuntimeError('Hook composition and source manifest differ')
    counts=Counter(r['asset_id'] for r in body_rows if r['kind'] in {'picture','article'})
    for r in body_rows:
        for ident in {'alpha':['example-06'],'edit':['example-18','example-19']}.get(r['asset_id'],[]):counts[ident]+=1
    manifest=[]
    for filename,(kind,ident) in HOOK_ASSETS.items():
        record=dict((captures if kind=='article' else media)[ident]);source=Path(record['path'])
        if not source.is_file() or record['sha256']!=shared.sha(source):raise RuntimeError('Source changed: '+ident)
        if not record.get('url'):raise RuntimeError('Exact source URL missing: '+ident)
        record.update(filename=filename,kind=kind,occurrences_in_hook=1)
        manifest.append(record)
        if kind!='brand':counts[ident]+=1
    if max(counts.values(),default=0)>2:raise RuntimeError('Source exceeds two appearances: '+str(counts))
    return {'assets':manifest,'source_counts':dict(counts),'publishing_enabled':False}

def prepare():
    REV.mkdir(parents=True,exist_ok=True)
    # Receipts and unchanged chapters are retained; only the opening has new inputs.
    for name in ['audio','research']:
        if not (REV/name).exists():shutil.copytree(BASE/name,REV/name)
    script=shared.read(BASE/'script.json')
    script['chapters'][0]['paragraphs']=PARAGRAPHS
    script['chapters'][0]['sources']=[episode.PUBLIC_URLS[k] for k in ['repository','license']]
    script['chapters'][0]['evidence_ids']=['repository','license']
    script['word_count']=sum(len(p.split()) for ch in script['chapters'] for p in ch['paragraphs'])
    shared.dump(REV/'script.json',script)
    shared.dump(REV/'revision.json',{'base_export':str(BASE/'Qwen_Image_21_Beyond_Generate_1080p.mp4'),
        'base_export_hash':shared.sha(BASE/'Qwen_Image_21_Beyond_Generate_1080p.mp4'),
        'scope':'Opening script, opening narration and first visual sequence only. Body chapters retained.',
        'research':'research/first_30_seconds_hook_system.md','publishing_enabled':False})
    print('Opening words',len(' '.join(PARAGRAPHS).split()),flush=True)

def review():
    bind();episode.review()

def narrate():
    bind();episode.narrate()

def audio_qc():
    bind();episode.audio_qc()

def repair_audio():
    bind();episode.repair_audio()

def plan():
    bind()
    qc=shared.read(REV/'audio_qc.json')
    if not qc['passed'] or qc['script_hash']!=shared.sha(REV/'script.json'):
        raise RuntimeError('Current narration review required')
    from scripts.assemble_qwen21_episode import require_audio_bytes
    require_audio_bytes(qc['audio_files'],episode.audio_fingerprints())
    n=shared.read(REV/'narration.json');old=shared.read(BASE/'narration.json')
    if not 24<=n['chapters'][1]['start']<=35:raise RuntimeError('Opening outside 24-35 second production target')
    for before,after in zip(old['chapters'][1:],n['chapters'][1:]):
        if shared.sha(Path(before['path']))!=shared.sha(Path(after['path'])):raise RuntimeError('Body audio changed')
    frames=round(n['chapters'][1]['start']*30)
    paras=shared.read(REV/'paragraph_timing.json')[:3]
    words=shared.read(REV/'audio'/f"01_hook_{n['chapters'][0]['hash']}_words.json")
    edit_start=next(w['start'] for w in words if str(w['text']).strip('.,:').lower()=='and' and w['start']>=paras[1]['start'])
    props={'seconds':frames/30,'editStart':edit_start,'questionStart':paras[2]['start']}
    shared.dump(REV/'hook.props.json',props)
    old_rows=shared.read(BASE/'edit_plan.json')
    body=[r for r in old_rows if not r['paragraph_id'].startswith('01_hook_')]
    manifest=hook_sources(BASE,body)
    shared.dump(REV/'hook_source_manifest.json',manifest)
    cursor=frames;rows=[{'id':'hook_v2','start_frame':0,'frames':frames,'kind':'motion','path':str(REV/'hook_silent.mp4'),
                       'source_url':episode.PUBLIC_URLS['repository'],'asset_id':'qwen_hook_proof','relevance':'Native transparency, targeted editing, honest cleanup question',
                       'source_assets':manifest['assets']}]
    for source in body:
        row=dict(source);row['start_frame']=cursor
        row['cached_segment']=str(BASE/'edit/segments'/f"{row['id']}.mp4")
        if not Path(row['cached_segment']).is_file():raise RuntimeError('Missing cached body segment')
        rows.append(row);cursor+=row['frames']
    shared.dump(REV/'edit_plan.json',rows)
    shared.dump(REV/'plan_receipt.json',{'script_hash':shared.sha(REV/'script.json'),'audio_files':episode.audio_fingerprints(),
        'plan_hash':shared.sha(REV/'edit_plan.json'),'props_hash':shared.sha(REV/'hook.props.json'),
        'audio_qc_hash':shared.sha(REV/'audio_qc.json'),'script_review_hash':shared.sha(REV/'script_review.json'),
        'source_manifest_hash':shared.sha(REV/'hook_source_manifest.json'),
        'body_segment_hashes':{r['id']:shared.sha(Path(r['cached_segment'])) for r in rows[1:]},
        'frames':cursor,'opening_seconds':frames/30,'body_audio_byte_identical':True})
    hook_gate()
    print('New opening',frames/30,'seconds; full video',cursor/30,flush=True)

def hook_gate():
    from pipeline.opening_retention import build_opening_contract,evaluate_opening
    n=shared.read(REV/'narration.json');paras=shared.read(REV/'paragraph_timing.json')[:3]
    words=shared.read(REV/'audio'/f"01_hook_{n['chapters'][0]['hash']}_words.json")
    def end_of(token,after=0):
        return next(w['end'] for w in words if str(w['text']).lower().strip('.,:?!')==token and w['start']>=after)
    # ASR may render the spoken version as numeric tokens ("2", ".1"). The
    # start of "can" is the measured end of the preceding complete product name.
    product_end=next(w['start'] for w in words if str(w['text']).lower()=='can')
    evidence={
        'alpha':{'available':True,'kind':'official_output','source_url':next(r['url'] for r in shared.read(BASE/'media/ledger.json') if r['id']=='example-04'),
                 'path':str(BASE/'media/example-04.png'),'claim_ids':['native_alpha']},
        'edits':{'available':True,'kind':'source_capture','source_url':episode.PUBLIC_URLS['repository'],
                 'path':str(BASE/'captures/repo_local_masks.png'),'claim_ids':['local_edit']},
        'license':{'available':True,'kind':'source_capture','source_url':episode.PUBLIC_URLS['license'],
                 'path':str(BASE/'research/license.txt'),'claim_ids':['license_limit']},
    }
    contract=build_opening_contract('open_source_spotlight',product='Qwen-Image 2.1',
       product_spoken_aliases=['Qwen Image two point one'],evidence=evidence)
    beats=[
        {'id':'result','start':0,'end':paras[0]['end'],'text':PARAGRAPHS[0],
         'roles':['proof','product','benefit'],'role_times':{'proof':2.94,'product':product_end,'benefit':end_of('background',5)},
         'evidence_ids':['alpha'],'claim_ids':['native_alpha'],'speech_end':paras[0]['end']},
        {'id':'scope','start':paras[1]['start'],'end':paras[1]['end'],'text':PARAGRAPHS[1],
         'roles':['limitation'],'role_times':{'limitation':end_of('test')},'evidence_ids':['edits'],'claim_ids':['local_edit']},
        {'id':'promise','start':paras[2]['start'],'end':round(n['chapters'][1]['start']*30)/30,'text':PARAGRAPHS[2],
         'roles':['promise','bridge'],'role_times':{'promise':end_of('cleanup'),'bridge':end_of('work')},
         'promise_id':'cleanup','evidence_ids':['alpha','license'],'claim_ids':['native_alpha','license_limit'],
         'speech_end':end_of('work')},
    ]
    payoffs=[{'id':'practical_checks','promise_id':'cleanup','start':n['chapters'][-1]['start'],
              'end':n['duration'],'evidence_ids':['alpha','edits','license']}]
    packet={'contract':contract,'beats':beats,'evidence':evidence,'claims':{'native_alpha':{},'local_edit':{},'license_limit':{}},'payoffs':payoffs}
    result=evaluate_opening(beats,contract=contract,evidence=evidence,claims=packet['claims'],payoffs=payoffs,require_local_assets=True,asset_root=BASE)
    result.update(script_hash=shared.sha(REV/'script.json'),narration_hash=shared.sha(REV/'narration.json'))
    shared.dump(REV/'opening_packet.json',packet);shared.dump(REV/'opening_gate.json',result)
    if not result['passed']:raise RuntimeError('Hook gate: '+str(result['failures']))

def render_hook():
    props=shared.read(REV/'hook.props.json');entry=ROOT/'remotion/src/qwen21-hook-entry.tsx'
    public=ROOT/'remotion/public/qwen21'
    for name in ['example-04.png','example-18.png','example-19.png','logo.png']:
        shutil.copy2(BASE/'media'/name,public/name)
    shutil.copy2(BASE/'captures/repo_local_masks.png',public/'repo_local_masks.png')
    signature=hashlib.sha256((shared.sha(entry)+shared.sha(REV/'hook.props.json')+''.join(shared.sha(public/n) for n in ['example-04.png','repo_local_masks.png','logo.png'])).encode()).hexdigest()
    dest=REV/'hook_silent.mp4';receipt=REV/'hook_render.json'
    if dest.exists() and receipt.exists() and shared.read(receipt).get('input_hash')==signature and shared.read(receipt).get('output_hash')==shared.sha(dest):return
    frames=REV/'frames';frames.mkdir(exist_ok=True)
    count=round(props['seconds']*30)
    command=[str(ROOT/'remotion/node_modules/.bin/remotion.cmd'),'render','src/qwen21-hook-entry.tsx','QwenHook',str(frames),
       f'--props={REV/"hook.props.json"}','--browser-executable=C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
       '--sequence','--image-format=jpeg','--jpeg-quality=95','--concurrency=3','--muted']
    r=subprocess.run(command,cwd=ROOT/'remotion',capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1200)
    (REV/'render.log').write_text(r.stdout+r.stderr,encoding='utf-8')
    if r.returncode:raise RuntimeError((r.stdout+r.stderr)[-1500:])
    pics=sorted(frames.glob('*.jpeg')) or sorted(frames.glob('*.jpg'))
    if len(pics)!=count:raise RuntimeError('Incomplete opening frames')
    listing=frames/'sequence.txt'
    listing.write_text(''.join("file '"+p.resolve().as_posix()+"'\nduration 0.033333333333\n" for p in pics),encoding='utf-8')
    shared.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-an','-frames:v',str(count),'-r','30',
        '-c:v','libx264','-preset','fast','-crf','17','-threads','3','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709',
        '-color_primaries','bt709','-color_trc','bt709','-video_track_timescale','15360',str(dest)])
    shared.dump(receipt,{'input_hash':signature,'output_hash':shared.sha(dest),'frames':count})

def package_metadata():
    metadata=shared.read(BASE/'review_metadata.json')
    narration=shared.read(REV/'narration.json')
    old=metadata['chapters']
    if len(old)!=len(narration['chapters']):raise RuntimeError('Chapter metadata mismatch')
    chapters=[]
    for index,(label,chapter) in enumerate(zip(old,narration['chapters'])):
        seconds=int(chapter['start'])
        title='Can you skip the cleanup?' if index==0 else label.split(' ',1)[1]
        chapters.append(f'{seconds//60:02}:{seconds%60:02} {title}')
    metadata['description']=metadata['description'].replace('\n'.join(old),'\n'.join(chapters))
    metadata.update(chapters=chapters,video=str(FINAL),publishing_enabled=False)
    shared.dump(REV/'review_metadata.json',metadata)
    (REV/'description.txt').write_text(metadata['description'],encoding='utf-8')
    shutil.copy2(BASE/'NOTICE.txt',REV/'NOTICE.txt')


def render():
    bind()
    hook_gate()
    from pipeline.render_v2 import write_concat
    from scripts.assemble_qwen21_episode import require_audio_bytes
    receipt=shared.read(REV/'plan_receipt.json')
    require_audio_bytes(receipt['audio_files'],episode.audio_fingerprints())
    for key,path in [('script_hash','script.json'),('plan_hash','edit_plan.json'),('props_hash','hook.props.json'),
                     ('audio_qc_hash','audio_qc.json'),('script_review_hash','script_review.json'),('source_manifest_hash','hook_source_manifest.json')]:
        if receipt[key]!=shared.sha(REV/path):raise RuntimeError('Stale '+path)
    if not shared.read(REV/'audio_qc.json')['passed'] or not shared.read(REV/'script_review.json')['passed']:raise RuntimeError('Review gate is not passed')
    render_hook()
    rows=shared.read(REV/'edit_plan.json');paths=[REV/'hook_silent.mp4']
    for r in rows[1:]:
        p=Path(r['cached_segment'])
        if shared.sha(p)!=receipt['body_segment_hashes'][r['id']]:raise RuntimeError('Body segment changed')
        paths.append(p)
    listing=write_concat(paths,REV/'concat.txt');narration=Path(shared.read(REV/'narration.json')['path'])
    duration=receipt['frames']/30
    if float(shared.probe(narration)['format']['duration'])>duration:raise RuntimeError('Would truncate narration')
    staged=REV/'rendering.mp4'
    shared.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-i',str(narration),'-map','0:v:0','-map','1:a:0',
        '-c:v','copy','-af','apad','-c:a','aac','-b:a','192k','-ar','48000','-t',str(duration),'-movflags','+faststart',str(staged)])
    shared.run(['ffmpeg','-v','error','-i',str(staged),'-f','null','-'],timeout=1200)
    from scripts import assemble_dreamx_full as audio
    audio.OUT=REV;report=audio.audio_export_check(staged,narration)
    meta=shared.probe(staged);v=next(s for s in meta['streams'] if s['codec_type']=='video')
    checks={'1080p':(v['width'],v['height'])==(1920,1080),'fps30':v['r_frame_rate']=='30/1','h264':v['codec_name']=='h264',
            'one_audio':sum(s['codec_type']=='audio' for s in meta['streams'])==1,'duration':abs(float(meta['format']['duration'])-duration)<.07,
            'narration_only':report['passed'],'full_decode':True,'body_audio_unchanged':True}
    if not all(checks.values()):raise RuntimeError(str(checks))
    staged.replace(FINAL)
    shared.dump(REV/'technical_qc.json',{'checks':checks,'duration':duration,'sha256':shared.sha(FINAL),'publishing_enabled':False})
    shared.run(['ffmpeg','-y','-v','error','-i',str(FINAL),'-t',str(receipt['opening_seconds']),'-c','copy','-movflags','+faststart',str(REV/'First_30_Seconds_Preview.mp4')])
    shutil.copy2(BASE/'thumbnail.jpg',REV/'thumbnail.jpg')
    package_metadata()
    print(FINAL,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','review','narrate','audio_qc','repair_audio','plan','hook_gate','render']);a=p.parse_args();globals()[a.stage]()
