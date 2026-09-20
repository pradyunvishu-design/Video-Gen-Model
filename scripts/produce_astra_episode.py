"""Resumable Astra news episode, using existing narration and assembly utilities.

Sources are official launch materials. All source sound is excluded. Publishing
is disabled; excerpt provenance and commentary purpose accompany every edit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EP = ROOT / 'data/episodes/episode_20260905_gpt6_astra'
LAUNCH = 'https://openai.com/index/gpt-6-astra/'
FINAL = EP / 'GPT6_Astra_Explained_1080p.mp4'

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def run(cmd, timeout=600):
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if result.returncode:
        # Do not persist signed media URLs or request credentials in diagnostics.
        err = re.sub(r'https?://\S+', '[media URL]', result.stderr[-1800:])
        raise RuntimeError(err)
    return result.stdout

def probe(path):
    return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))

def env():
    vals = {}
    for p in [Path(r'C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker'), ROOT/'.env']:
        if p.exists():
            vals.update({k:v for k,v in dotenv_values(p).items() if v})
    return vals

def discover():
    """Search the existing YouTube Data API without acquiring YouTube videos."""
    from pipeline.youtube_broll import _youtube_get, _video_details
    e = env()
    key = next((v for k,v in e.items() if 'YOUTUBE' in k and 'KEY' in k), None)
    if not key:
        dump(EP/'research/youtube_search.json', {'status':'key_unavailable'})
        return
    result = _youtube_get('search', {'part':'snippet','q':'GPT-6 Astra OpenAI','type':'video','maxResults':12}, api_key=key)
    ids = [x['id']['videoId'] for x in result.get('items',[]) if x.get('id',{}).get('videoId')]
    details = _video_details(ids, api_key=key)
    dump(EP/'research/youtube_search.json',details)
    print('YouTube candidates', [(x.get('id'), x.get('snippet',{}).get('title'), x.get('snippet',{}).get('channelTitle')) for x in details], flush=True)

def acquire():
    """Retain short, bounded official demo quotations, never the complete film."""
    demos=read(EP/'research/demos.json')
    ranges = {
      'Launch film': ('launch_film', 5, 16),
      'Circuit board': ('circuit', 1, 11),
      'Frontend quality assurance': ('qa', 6, 23),
      'Unreal Engine walkthrough': ('house', 2, 14),
      'Sequencing quality': ('science', 4, 20),
      'Excel competition': ('excel', 10, 24),
      'Car transmission': ('gears', 4, 19),
      'Apartment hunting': ('apartment', 5, 20),
      'DMV appointment': ('dmv', 5, 20),
      'Unity gameplay': ('unity', 8, 30),
      'Playco interview': ('playco_demo', 15, 20),
    }
    def one(d):
        if d['name'] not in ranges or not d.get('iframes'): return None
        name,start,length=ranges[d['name']]
        target=EP/'media'/f'{name}.mp4'
        receipt=target.with_suffix('.json')
        if target.exists() and receipt.exists(): return read(receipt)
        entry=d['iframes'][0]
        u=entry['src'] if isinstance(entry,dict) else entry
        resp=requests.get(u,timeout=40); resp.raise_for_status()
        match=re.search(r'window\.playerConfig\s*=\s*',resp.text)
        if not match: raise RuntimeError('Public player metadata missing: '+name)
        cfg=json.JSONDecoder().raw_decode(resp.text[match.end():])[0]
        video=cfg['video']
        if length >= float(video['duration']): raise RuntimeError('Refusing full-video acquisition')
        files=cfg['request']['files']['hls']
        stream=files['cdns'][files['default_cdn']].get('avc_url') or files['cdns'][files['default_cdn']]['url']
        playlist=requests.get(stream,timeout=40); playlist.raise_for_status()
        lines=playlist.text.splitlines(); options=[]
        for i,line in enumerate(lines[:-1]):
            m=re.search(r'RESOLUTION=(\d+)x(\d+)',line)
            if m and not lines[i+1].startswith('#'):
                options.append((int(m[2]),int(m[1]),urljoin(stream,lines[i+1])))
        eligible=[x for x in options if x[0]>=720]
        if not eligible: raise RuntimeError('Source below usable quality: '+name)
        selected=max(eligible,key=lambda x:x[0]*x[1])
        target.parent.mkdir(parents=True,exist_ok=True)
        run(['ffmpeg','-y','-v','error','-ss',str(start),'-i',selected[2],'-t',str(length),'-map','0:v:0','-an','-vf','scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x121717,setsar=1,fps=30','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(target)])
        data={'id':name,'path':str(target),'source_url':u,'announcement_url':LAUNCH,'publisher':'OpenAI','source_description':d['text'],'source_in':start,'source_out':start+length,'full_source_duration':video['duration'],'source_audio_used':False,'native_dimensions':[selected[1],selected[0]],'sha256':sha(target),'rights_basis':'Limited first-party demo quotation for direct explanatory news commentary; no general reuse license asserted','publication_approval':'pending','publishing_enabled':False}
        dump(receipt,data)
        print('Official excerpt ready',name,length,'seconds',flush=True)
        return data
    records=[];errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs=[(d,pool.submit(one,d)) for d in demos]
        for d,job in jobs:
            try:
                result=job.result()
                if result: records.append(result)
            except Exception as exc:
                errors.append({'name':d['name'],'error':str(exc)});print('Source unavailable',d['name'],str(exc)[:200],flush=True)
    dump(EP/'media/ledger.json',records)
    dump(EP/'media/acquisition_errors.json',errors)

def review():
    from pipeline.editorial import call_openrouter,capture_openrouter_usage
    import pipeline.editorial as editorial
    script=read(EP/'script.json'); digest=sha(EP/'script.json')
    receipt=EP/'script_review.json'
    if receipt.exists() and read(receipt).get('script_hash')==digest:
        print('Using cached review',flush=True); return
    editorial.OPENROUTER_API_KEY=env().get('OPENROUTER_API_KEY','')
    sources={p.stem:p.read_text(encoding='utf-8')[:45000] for p in (EP/'research').glob('*.txt')}
    spend_path=EP/'provider_usage.json'
    spend=read(spend_path) if spend_path.exists() else {'openrouter_usd':0.,'openrouter_cap_usd':1.,'calls':[],'magichour_credits':0}
    def usage(event):
        if event['phase']=='before':
            if spend['openrouter_usd']+spend.get('reserved_usd',0)+.5>spend['openrouter_cap_usd']: raise RuntimeError('Review budget reached')
            spend['reserved_usd']=.5;dump(spend_path,spend);return {'max_tokens':2600}
        cost=event.get('usage',{}).get('cost')
        if cost is None: raise RuntimeError('Provider did not return cost; reserve retained')
        spend['openrouter_usd']+=float(cost);spend['reserved_usd']=0;spend['calls'].append(event);dump(spend_path,spend)
    schema={'type':'json_schema','json_schema':{'name':'review','strict':True,'schema':{'type':'object','additionalProperties':False,'properties':{'passed':{'type':'boolean'},'issues':{'type':'array','items':{'type':'string'}},'naturalness':{'type':'number'},'clarity':{'type':'number'},'evidence_notes':{'type':'array','items':{'type':'string'}}},'required':['passed','issues','naturalness','clarity','evidence_notes']}}}
    with capture_openrouter_usage(usage):
        result=call_openrouter('openai/gpt-5.4','Independently fact-check this spoken news script against the provided primary sources. Do not reward intent. The video reports official demos; it is not a claimed independent model test. Reject unsupported names, numbers, price claims, benchmark interpretations or causal claims. Mark clearly signposted original analogies and proposed viewer tests as commentary, not source assertions. Check that prose is conversational, useful and avoids forced jokes. Scores 1-10. Fail only for material factual or intelligibility issues; put soft notes in evidence_notes. Return strict JSON.',json.dumps({'script':script,'sources':sources}),schema,temperature=.1)
    result.update(script_hash=digest,reviewer_model='openai/gpt-5.4');dump(receipt,result);print(json.dumps(result,indent=2),flush=True)

DIRECTOR='''Read only the transcript. One consistent original Zubenelgenubi male voice, clear American English. A calm, AI-native technology host in his twenties talking to one curious friend. Aim for 170-178 words a minute. Connected, lightly conversational delivery, clean consonants and complete sentence endings. Underplay the voice. No announcer performance, forced bass, vocal fry, breathy endings, whispering, exaggerated excitement, sing-song emphasis or long theatrical pauses. Emphasize only the meaning-bearing contrast in a sentence. Keep the same timbre through every paragraph. No music, sound effects, static, or other voices. Read model names naturally: GPT six Astra. Transcript follows:
'''

def narrate(director_overrides=None):
    from pipeline.gemini_tts import GeminiTTSClient
    from pipeline.render_v2 import concat_audio, make_silence, duration
    approved=read(EP/'script_review.json')
    if not approved['passed'] or approved['script_hash']!=sha(EP/'script.json'): raise RuntimeError('Script review not passed')
    script=read(EP/'script.json');key=env().get('GEMINI_API_KEY')
    def one(ch):
        director=(director_overrides or {}).get(ch['id'],DIRECTOR)
        text='\n\n'.join(ch['paragraphs']);h=hashlib.sha256((director+text).encode()).hexdigest()[:12]
        raw=EP/'audio'/f"{ch['id']}_{h}_raw.wav";dest=raw.with_name(raw.name.replace('_raw','_master'))
        receipt=EP/'audio'/f"{ch['id']}_receipt.json"
        if dest.exists() and receipt.exists() and read(receipt).get('hash')==h:
            return read(receipt)
        result=GeminiTTSClient(key,model='gemini-3.1-flash-tts-preview',voice='Zubenelgenubi',timeout_seconds=240).synthesize(text,raw,director_prompt=director,retries=2)
        if not dest.exists():
            run(['ffmpeg','-y','-v','error','-i',str(raw),'-af','highpass=f=60,loudnorm=I=-17:TP=-1.5:LRA=6','-ar','48000','-ac','1','-c:a','pcm_s16le',str(dest)])
        info={'id':ch['id'],'path':str(dest),'duration':duration(dest),'hash':h,'voice':'Zubenelgenubi','usage':result.usage}
        dump(EP/'audio'/f"{ch['id']}_receipt.json",info);print('Narration ready',ch['id'],round(info['duration'],1),flush=True);return info
    with ThreadPoolExecutor(max_workers=2) as pool: audio=list(pool.map(one,script['chapters']))
    silence=make_silence(EP/'audio/pause.wav',180);paths=[];cursor=0.
    for i,ch in enumerate(audio):
        ch['start']=cursor;paths.append(Path(ch['path']));cursor+=ch['duration']
        if i<len(audio)-1: paths.append(silence);cursor+=.18
    master=concat_audio(paths,EP/'narration_zubenelgenubi.wav')
    dump(EP/'narration.json',{'chapters':audio,'path':str(master),'duration':duration(master),'voice':'Zubenelgenubi','model':'gemini-3.1-flash-tts-preview'})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['discover','acquire','review','narrate']);args=parser.parse_args();globals()[args.stage]()

if __name__=='__main__': main()
