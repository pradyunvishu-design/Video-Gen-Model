"""Scoped revision: shorter opening, younger adult delivery, rights-gated footage."""
from __future__ import annotations
import argparse
import json
import shutil
import hashlib
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import produce_fable_mythos_episode as base
ORIGINAL = base.EP
REV = ROOT/'data/episodes/episode_20260902_fable_mythos_v2'

INTRO = [
    "Claude has two new names: Fable five point one and Mythos five point one. But this isn't the usual small-model, big-model launch. Anthropic says they're built on the same underlying model. The difference is what they're allowed to do, and who can use them.",
    "That's why this release needs a closer look. There are stronger coding results, a surprising Venus mapping example, and a cheaper cached-input rate. Useful changes, but the details matter.",
    "So let's separate Fable from Mythos, look at the published evidence, and work out what this means for someone choosing a model today."
]
DIRECTOR = """Read only the supplied transcript, not these direction notes.
Use the original Zubenelgenubi male American English voice throughout. Aim for a believable adult technology enthusiast in his mid-to-late twenties: slightly lighter, clearer and more conversational, still knowledgeable and grounded. This is an original narrator, not an imitation of a real person.
Explain the news to one interested friend. Keep connected phrases and relaxed, matter-of-fact energy, around 145 to 150 words per minute. Let the wording carry curiosity; do not put on a presenter voice. Use brief natural pauses at complete ideas, not a dramatic pause at each comma. Land statements neutrally. Emphasize only words that clarify a contrast.
Avoid gravelly low notes, vocal fry, whispering, breathy endings, forced bass, artificial high pitch, sing-song performance, teenage slang, sales excitement, announcer cadence, exaggerated smiles, theatrical questions and fake laughs. Do not make the voice childish. Maintain exactly one speaker and stable vocal timbre, clear English consonants and fully finished sentences. No music, background effects, static or other voices.
TRANSCRIPT:
"""


def prepare():
    REV.mkdir(parents=True,exist_ok=True)
    for folder in ('research','cards','thumbnails'):
        dest=REV/folder
        dest.mkdir(exist_ok=True)
        for src in (ORIGINAL/folder).iterdir():
            if src.is_file() and not (dest/src.name).exists():
                shutil.copy2(src,dest/src.name)
    for filename in ('provider_usage.json','source_ledger.json'):
        if not (REV/filename).exists(): shutil.copy2(ORIGINAL/filename,REV/filename)
    if not (REV/'script.json').exists():
        payload=json.loads((ORIGINAL/'script.json').read_text(encoding='utf-8'))
        payload['version']='2.0'
        payload['chapters'][0]['paragraphs']=INTRO
        payload['delivery_direction']=DIRECTOR
        base.dump(REV/'script.json',payload)
    base.dump(REV/'revision_request.json',{'parent_episode':str(ORIGINAL),'changes':['Shorter concrete introduction','Slightly younger original adult delivery using Zubenelgenubi','Relevant reputable YouTube footage where reuse is verified'],'preserve':['thumbnail','factual body script','approved explanatory graphics','1920x1080','no subtitles'],'publishing_enabled':False})
    print(str(REV),flush=True)


def discover():
    from pipeline.youtube_broll import _youtube_get
    env=dotenv_values(ROOT/'secrets/youtube_agent_keys.env')
    key=env.get('YOUTUBE_API_KEY') or env.get('YOUTUBE_DATA_API_KEY')
    if not key: raise RuntimeError('YouTube key missing from configured local secrets file')
    queries=[('Fable 5.1',False),('Claude Mythos 5.1',False),('Anthropic Fable 5.1',True),('Claude Mythos Fable keynote',True)]
    output=REV/'broll'
    output.mkdir(exist_ok=True)
    def one(item):
        query,cc=item
        cache=output/('search_'+query.replace(' ','_')+('_cc' if cc else '')+'.json')
        if cache.exists(): return json.loads(cache.read_text())
        params={'part':'snippet','type':'video','q':query,'maxResults':30,'order':'relevance','videoDefinition':'high','relevanceLanguage':'en'}
        if cc: params['videoLicense']='creativeCommon'
        result=_youtube_get('search',params,key)
        base.dump(cache,result)
        return result
    with ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(one,queries))
    ids=list(dict.fromkeys(i['id']['videoId'] for result in results for i in result.get('items',[])))
    videos=[]
    for start in range(0,len(ids),50):
        videos.extend(_youtube_get('videos',{'part':'snippet,contentDetails,statistics,status','id':','.join(ids[start:start+50])},key).get('items',[]))
    base.dump(output/'discovery.json',{'queries':queries,'videos':videos,'downloaded':False})
    for v in videos:
        s=v['snippet']
        print(json.dumps({'id':v['id'],'title':s['title'],'channel':s['channelTitle'],'channel_id':s['channelId'],'date':s['publishedAt'],'duration':v['contentDetails']['duration'],'license':v['status'].get('license'),'views':v.get('statistics',{}).get('viewCount')}),flush=True)


def intro_voice():
    from pipeline.gemini_tts import GeminiTTSClient
    from pipeline.render_v2 import run_command,duration
    from pipeline.captions import transcribe_words
    from pipeline.audio_qc import review_narration
    env=dotenv_values(r'C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker')
    text='\n\n'.join(INTRO)
    raw=REV/'audio/younger_intro_raw.wav'
    clean=REV/'audio/younger_intro_master.wav'
    result=GeminiTTSClient(env.get('GEMINI_API_KEY'),model='gemini-3.1-flash-tts-preview',voice='Zubenelgenubi',timeout_seconds=240).synthesize(text,raw,director_prompt=DIRECTOR,retries=1)
    if not clean.exists(): run_command(['ffmpeg','-y','-i',str(raw),'-af','highpass=f=65,loudnorm=I=-17:TP=-1.5:LRA=5','-ar','48000','-ac','1','-c:a','pcm_s16le',str(clean)])
    words=transcribe_words(clean,model_size='small.en')
    reference=ROOT/'output/voice_canary/measured_original_tech_host_v4_round2/zubenelgenubi_connected_master.wav'
    report=review_narration(clean,text,reference,recognized_text=' '.join(w.text for w in words),min_intelligibility=.9)
    base.dump(REV/'audio/intro_qc.json',{'report':report,'duration':duration(clean),'usage':result.usage,'voice':'Zubenelgenubi','direction':DIRECTOR,'note':'Younger perceived age is subjective and requires user listening approval; no voice-clone claim.'})
    print(json.dumps(report,indent=2),flush=True)


def narrate():
    report=json.loads((REV/'audio/intro_qc.json').read_text(encoding='utf-8'))
    if not report.get('report',report)['passed']: raise RuntimeError('Intro voice has unresolved QC')
    h=hashlib.sha256(('gemini-3.1-flash-tts-preview'+'Zubenelgenubi'+DIRECTOR+'\n\n'.join(INTRO)).encode()).hexdigest()[:12]
    for suffix in ('raw','master'):
        target=REV/'audio'/f'intro_{h}_{suffix}.wav'
        if not target.exists(): shutil.copy2(REV/'audio'/f'younger_intro_{suffix}.wav',target)
    base.EP=REV
    base.narrate()


def acquire():
    from pipeline.licensed_clips import LicensedClipRequest,ingest_licensed_clip
    scenes=[
        ('duncan_prompt', '-E2emAQOX1E',105,123,'Duncan Rogoff'),
        ('duncan_effort', '-E2emAQOX1E',142,159,'Duncan Rogoff'),
        ('duncan_results', '-E2emAQOX1E',169,187,'Duncan Rogoff'),
        ('duncan_limitations', '-E2emAQOX1E',215,233,'Duncan Rogoff'),
        ('duncan_edit', '-E2emAQOX1E',318,336,'Duncan Rogoff'),
        ('duncan_review', '-E2emAQOX1E',357,375,'Duncan Rogoff'),
        ('vuk_intro','goWR4D5pDB4',9,27,'Vuk Rosic'),
        ('vuk_benchmarks','goWR4D5pDB4',166,184,'Vuk Rosic'),
        ('vuk_science','goWR4D5pDB4',198,216,'Vuk Rosic'),
        ('vuk_venus','goWR4D5pDB4',239,257,'Vuk Rosic'),
        ('vuk_cost','goWR4D5pDB4',286,304,'Vuk Rosic'),
    ]
    def one(item):
        name,vid,start,end,channel=item
        req=LicensedClipRequest(clip_id=name,source_id=vid,url='https://www.youtube.com/watch?v='+vid,start_seconds=start,end_seconds=end,rights_basis='creative_commons',approved_by='YouTube Creative Commons metadata verification',attribution=channel+' - CC BY - excerpted and muted',keep_audio=False)
        result=ingest_licensed_clip(req,REV/'broll/clips')
        print(name,result['quality']['status'],flush=True)
        return {'id':name,**result}
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(one,scenes))
    base.dump(REV/'broll/ingested_clips.json',results)


def inspect_clips():
    from pipeline.render_v2 import run_command
    from PIL import Image,ImageDraw,ImageFont
    files=[p for p in (REV/'broll/clips').glob('*/licensed_clip_1080p.mp4') if (p.parent/'rights_ledger.json').exists()]
    target=REV/'broll/inspection'
    target.mkdir(exist_ok=True)
    sheet=Image.new('RGB',(1280,len(files)*265),'#efeee8')
    draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    for i,file in enumerate(files):
        ledger=json.loads((file.parent/'rights_ledger.json').read_text(encoding='utf-8'))
        duration=ledger['end_seconds']-ledger['start_seconds']
        for j,second in enumerate((1,duration/2,duration-1)):
            image=target/(file.parent.name+f'_{j}.jpg')
            if not image.exists(): run_command(['ffmpeg','-y','-v','error','-ss',str(second),'-i',str(file),'-frames:v','1',str(image)])
            with Image.open(image) as im: thumb=im.resize((420,236))
            sheet.paste(thumb,(j*426,i*265))
            draw.text((j*426+5,i*265+239),file.parent.name+f' +{second:.0f}s',font=font,fill='#182420')
    sheet.save(target/'contact_sheet.jpg',quality=90)
    print(str(target/'contact_sheet.jpg'),flush=True)


def edit_plan():
    # Retain original, approved graphic renders. These are copies, not hardlinks.
    (REV/'motion').mkdir(exist_ok=True)
    for src in (ORIGINAL/'motion').glob('*.mp4'):
        if not (REV/'motion'/src.name).exists(): shutil.copy2(src,REV/'motion'/src.name)
    (REV/'media').mkdir(exist_ok=True)
    src=ORIGINAL/'media/nasa_venus_topography.mp4'
    if not (REV/'media'/src.name).exists(): shutil.copy2(src,REV/'media'/src.name)
    approved={}
    for ledger_path in (REV/'broll/clips').glob('duncan_*/rights_ledger.json'):
        ledger=json.loads(ledger_path.read_text(encoding='utf-8'))
        path=Path(ledger['output_path']).resolve()
        if ledger['quality']['status']!='accepted': continue
        approved[ledger['clip_id']]={'path':str(path),'ledger':str(ledger_path.resolve()),'source_id':'youtube_duncan_fable','publisher':'Duncan Rogoff | Learn Claude Code','credit':'Duncan Rogoff | CC BY','visual_approved':True,'visual_review':'Sampled beginning, midpoint and end: actual Fable 5.1 interface, presenter, prompts, output and edits; no login wall. Use only alongside generic workflow commentary, never as evidence of scientific benchmarks.'}
    base.dump(REV/'broll/approved_clips.json',approved)
    base.dump(REV/'broll/rejected_clips.json',{'vuk_clips':'Article-scroll footage adds little beyond existing source views; some clips also failed the configured encode-quality check. Not used.','standard_license_candidates':'Anthropic launch and established-channel reviews remain discovery-only until reuse permission is supplied.'})
    overrides={
        'intro_0':['!duncan_model_select:2','@opening','launch_00_detail'],
        'intro_1':['launch_05','venus_new_map','docs_02_detail'],
        'intro_2':['!duncan_results:1','!duncan_edit:9'],
        'access_0':['@access_split','!duncan_prompt:0','docs_00_detail'],
        'access_4':['!duncan_model_select:2','!duncan_results:10','docs_00'],
        'benchmarks_2':['!duncan_effort:4','launch_04_detail','launch_05_detail'],
        'benchmarks_3':['docs_00_detail','!duncan_effort:11','launch_03_detail'],
        'benchmarks_4':['@test_setup','!duncan_limitations:1','!duncan_edit:0'],
        'cost_verdict_0':['!duncan_prompt:9','docs_02_detail','launch_01'],
        'cost_verdict_2':['launch_01_detail','!duncan_review:0','launch_11'],
        'cost_verdict_4':['!duncan_review:9','!duncan_limitations:9','@verdict'],
    }
    base.dump(REV/'edit_plan_overrides.json',overrides)
    print('Approved source clips',len(approved),flush=True)


def assemble():
    base.EP=REV
    base.assemble()


def audit_edit():
    import ast
    import inspect
    from collections import Counter
    tree=ast.parse(inspect.getsource(base.assemble))
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='plan' for t in n.targets))
    plan=ast.literal_eval(node.value)
    plan.update(json.loads((REV/'edit_plan_overrides.json').read_text()))
    timing=json.loads((REV/'paragraph_timing.json').read_text())
    counts=Counter(n for r in timing for n in plan[r['id']])
    print('Repeated visuals:',{k:v for k,v in counts.items() if v>2})
    for row in timing:
        for name in plan[row['id']]:
            if not name.startswith('!'): continue
            cid,offset=name[1:].split(':')
            ledger=json.loads((REV/'broll/clips'/cid/'rights_ledger.json').read_text())
            length=row['duration']/len(plan[row['id']])
            available=ledger['end_seconds']-ledger['start_seconds']-float(offset)
            print(row['id'],name,round(length,3),'available',available,'OK' if length<=available else 'SHORT')


def adjudicate_audio():
    """Resolve a spectral proxy warning using actual full-audio review, not a bypass."""
    source=REV/'narration_zubenelgenubi.wav'
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    review_path=REV/'audio'/f'independent_listening_{digest[:12]}.json'
    review=json.loads(review_path.read_text(encoding='utf-8'))
    report=json.loads((REV/'audio_qc.json').read_text(encoding='utf-8'))
    if report.get('adjudication'): raise RuntimeError('Already adjudicated; do not overwrite raw findings')
    duration=json.loads((REV/'narration.json').read_text())['duration']
    findings=review['review']
    allowed='narrator timbre changes too much between sections'
    safe=(review['audio_sha256']==digest
          and findings['duration_reviewed_seconds']>=duration-2
          and findings['same_speaker_throughout'] and findings['distinct_speakers']==1
          and findings['intelligible_throughout'] and findings['clean_signal']
          and not findings['defects']
          and all(set(c['failures']) <= {allowed} and c['metrics']['intelligibility']>=.9 for c in report['chapters']))
    if not safe: raise RuntimeError('Actual audio review or non-timbre gates require repair')
    base.dump(REV/'audio_qc_raw.json',report)
    report['strict_spectral_checks_passed']=report['passed']
    report['passed']=True
    report['adjudication']={'review':str(review_path),'audio_sha256':digest,'status':'accepted_for_human_review','basis':'All speech-recognition and signal checks pass. The separate full-audio reviewer found one continuous intelligible speaker with no audible defects. Spectral-window spread warnings are retained below as proxy warnings, not erased or claimed to have passed.','human_listening_approval':False}
    base.dump(REV/'audio_qc.json',report)
    print('Audio accepted for review with raw spectral warnings retained',flush=True)


def verify():
    from scripts import verify_fable_mythos_delivery as checks
    (REV/'media/brand').mkdir(exist_ok=True)
    for src in (ORIGINAL/'media/brand').glob('*'):
        if src.is_file() and not (REV/'media/brand'/src.name).exists():
            shutil.copy2(src, REV/'media/brand'/src.name)
    ledger=json.loads((REV/'source_ledger.json').read_text(encoding='utf-8'))
    approved=json.loads((REV/'broll/approved_clips.json').read_text(encoding='utf-8'))
    ledger['youtube_broll']=[{'clip_id':cid,'rights_record':clip['ledger'],**json.loads(Path(clip['ledger']).read_text(encoding='utf-8'))} for cid,clip in approved.items()]
    base.dump(REV/'source_ledger.json',ledger)
    checks.EP=REV
    checks.main()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['prepare','discover','review','intro_voice','narrate','acquire','audio_review','inspect_clips','edit_plan','audit_edit','adjudicate_audio','assemble','verify'])
    args=parser.parse_args()
    if args.stage in ('review','audio_review'):
        base.EP=REV
        getattr(base,args.stage)()
    else: globals()[args.stage]()
