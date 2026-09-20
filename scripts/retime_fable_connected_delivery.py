"""Faster private-review delivery without replacing the selected narrator.

Shorten only waveform-silent gaps that do not overlap recognized words. Then
apply <=10% pitch-preserving tempo adjustment and subtle meaning-led gain.
No identity cloning, new wording, changed pitch, or new generation is involved.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import math
import re
import shutil
import statistics
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.captions import TimedWord, align_script_words
from pipeline.render_v2 import write_concat

EP = ROOT / 'data/episodes/episode_20260902_fable_mythos_v5_faster'
PARENT = ROOT / 'data/episodes/episode_20260902_fable_mythos_v4_private'
VOICE_EP = ROOT / 'data/episodes/episode_20260902_fable_mythos_v3'
SOURCE_AUDIO = VOICE_EP / 'narration_zubenelgenubi.wav'
FINAL = EP / 'Claude_Fable_51_and_Mythos_Faster_Private_Review_1080p.mp4'
SR = 48000
TEMPO = 1.10
EMPHASIS = {
    'intro_0': 'same', 'intro_1': 'details', 'intro_2': 'published',
    'access_0': 'surrounding', 'access_1': 'not', 'access_2': 'not',
    'access_3': 'both', 'access_4': 'general-access',
    'benchmarks_0': 'particular', 'benchmarks_1': 'different', 'benchmarks_2': 'logarithmic',
    'benchmarks_3': 'configuration', 'benchmarks_4': 'finished',
    'venus_0': 'radar', 'venus_1': 'features', 'venus_2': 'claim',
    'venus_3': 'workflow', 'venus_4': 'already',
    'biology_0': 'not', 'biology_1': 'physical', 'biology_2': 'twelve',
    'biology_3': 'failures', 'biology_4': 'tested',
    'cost_verdict_0': 'cached', 'cost_verdict_1': 'not', 'cost_verdict_2': 'estimate',
    'cost_verdict_3': 'eligible', 'cost_verdict_4': 'genuinely',
}


def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def dump(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if p.returncode: raise RuntimeError(p.stderr[-3000:])
    return p.stdout
def duration(p):
    return float(run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)]).strip())
def norm(t): return re.sub(r'[^a-z0-9-]', '', t.casefold())
def word_count(t): return len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", t))


def caption_measurements():
    def secs(t):
        h,m,s=t.split(':'); return int(h)*3600 + int(m)*60 + float(s)
    results=[]
    for p in sorted((ROOT/'data/fidelity_runs/_caption_cache/ai_search').glob('*.vtt')):
        words={}; end=0
        for block in re.split(r'\r?\n\s*\r?\n',p.read_text(encoding='utf-8-sig')):
            match=re.search(r'(\d\d:\d\d:\d\d\.\d+) --> (\d\d:\d\d:\d\d\.\d+)',block)
            if not match: continue
            start=secs(match[1]); end=max(end,secs(match[2]))
            for line in block.splitlines():
                if not re.search(r'<\d\d:',line): continue  # Ignore repeated rolling-caption lines.
                now=start
                for part in re.split(r'(<\d\d:\d\d:\d\d\.\d+>)',line):
                    if re.fullmatch(r'<\d\d:\d\d:\d\d\.\d+>',part): now=secs(part[1:-1])
                    else:
                        plain=re.sub('<[^>]+>','',part).strip()
                        if plain: words[(round(now,3),plain)]=word_count(plain)
        if words and end>180:
            results.append({'id':p.stem.removesuffix('.en'),'sha256':sha(p),'seconds':end,
                            'caption_word_count':sum(words.values()),'gross_wpm':sum(words.values())/end*60})
    return {'source':'Existing user-specified caption cache; no new acquisition.',
            'count':len(results),'median_gross_wpm':statistics.median(r['gross_wpm'] for r in results),
            'limitations':['Caption-derived timing, not an exact measurement of enunciation or vocal stress.',
                          'Prior two-audio sample profile was slower; this larger caption collection governs this requested faster revision.'],
            'videos':results}


def prepare_audio():
    (EP/'audio').mkdir(parents=True,exist_ok=True)
    refs=caption_measurements()
    dump(EP/'reference_pacing.json',refs)
    script=read(VOICE_EP/'script.json'); narration=read(VOICE_EP/'narration.json')
    recognized=[]; marks=[]
    for chapter,aud in zip(script['chapters'],narration['chapters']):
        words=[TimedWord(**w) for w in read(VOICE_EP/'audio'/f"{chapter['id']}_{aud['hash']}_words.json")]
        recognized.extend((w.start+aud['start'], w.end+aud['start']) for w in words)
        aligned=align_script_words('\n\n'.join(chapter['paragraphs']),words)
        offset=0
        for i,text in enumerate(chapter['paragraphs']):
            key=f"{chapter['id']}_{i}"; count=len(text.split()); target=EMPHASIS[key]
            matched=[w for w in aligned[offset:offset+count] if norm(w.text)==norm(target)]
            if not matched: raise RuntimeError(f'Unaligned emphasis word: {key} {target}')
            w=matched[0]
            marks.append({'beat':key,'word':target,'start':w.start+aud['start'],'end':w.end+aud['start'],'gain_db':1.1})
            offset+=count
    decoded=subprocess.run(['ffmpeg','-v','error','-i',str(SOURCE_AUDIO),'-f','f32le','-ar',str(SR),'-ac','1','-'],capture_output=True,check=True).stdout
    pcm=np.frombuffer(decoded,dtype=np.float32).copy(); original_seconds=len(pcm)/SR
    frame=SR//100
    rms=np.sqrt(np.mean(pcm[:len(pcm)//frame*frame].reshape(-1,frame)**2,axis=1))
    quiet=rms<10**(-48/20)
    edges=np.diff(np.r_[False,quiet,False].astype(int))
    cuts=[]
    for a,b in zip(np.flatnonzero(edges==1)/100,np.flatnonzero(edges==-1)/100):
        if b-a<.42 or a<.2 or b>original_seconds-.5: continue
        left,right=a+.13,b-.13
        if any(left<we+.015 and right>ws-.015 for ws,we in recognized): continue
        cuts.append({'start':round(left,4),'end':round(right,4),'seconds':round(right-left,4),'reason':'RMS below -48 dBFS throughout, outside all recognized words including 15ms guard.'})
    # Meaning-led gain has gentle sample-level ramps, not hard volume jumps.
    for m in marks:
        a=max(0,int(m['start']*SR)); b=min(len(pcm),int(m['end']*SR))
        if b<=a: continue
        envelope=np.ones(b-a,dtype=np.float32)
        attack=min(round(.045*SR),(b-a)//3); release=min(round(.065*SR),(b-a)//3)
        if attack: envelope[:attack]=(1-np.cos(np.linspace(0,np.pi,attack)))/2
        if release: envelope[-release:]=(1+np.cos(np.linspace(0,np.pi,release)))/2
        pcm[a:b] *= 1+(10**(m['gain_db']/20)-1)*envelope
    chunks=[]; pos=0
    for cut in cuts:
        a,b=round(cut['start']*SR),round(cut['end']*SR)
        chunks.append(pcm[pos:a]); pos=b
    chunks.append(pcm[pos:]); joined=np.concatenate(chunks)
    # At the edits, only sub--48dB material meets; do not crossfade spoken samples.
    pre=EP/'audio/compacted_emphasis.wav'
    p=subprocess.run(['ffmpeg','-y','-v','error','-f','f32le','-ar',str(SR),'-ac','1','-i','pipe:0','-c:a','pcm_s24le',str(pre)],input=joined.tobytes(),capture_output=True)
    if p.returncode: raise RuntimeError('Compacted PCM write failed')
    target=EP/'narration_zubenelgenubi.wav'
    # No denoising, pitch shift or resynthesis: retain the approved voice texture.
    run(['ffmpeg','-y','-v','error','-i',str(pre),'-af',f'atempo={TEMPO},alimiter=limit=0.841395:level=false:latency=true',
         '-ar',str(SR),'-ac','1','-c:a','pcm_s24le',str(target)])
    new_seconds=duration(target)
    count=sum(word_count(' '.join(c['paragraphs'])) for c in script['chapters'])
    for name in ('script.json','script_review.json','voice_selection.json'):
        shutil.copy2(VOICE_EP/name,EP/name)
    (EP/'thumbnails').mkdir(exist_ok=True)
    shutil.copy2(PARENT/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg',EP/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg')
    for name in ('source_ledger.json','revision_manifest.json'):
        shutil.copy2(PARENT/name,EP/('parent_'+name))
    plan={'source':str(SOURCE_AUDIO),'source_sha256':sha(SOURCE_AUDIO),'source_seconds':original_seconds,
          'narration_sha256':sha(target),'narration_seconds':new_seconds,'tempo':TEMPO,
          'removed_silence_seconds':sum(c['seconds'] for c in cuts),'silence_edits':cuts,'word_emphasis':marks,
          'words':count,'before_wpm':count/original_seconds*60,'after_wpm':count/new_seconds*60,
          'reference_median_wpm':refs['median_gross_wpm'],'voice':'Zubenelgenubi',
          'no_pitch_shift':True,'no_new_synthesis':True,'new_paid_generation_calls':0,
          'publishing_enabled':False,'public_reuse_cleared':False,'private_source_record':str(PARENT/'broll/private_use_record.json')}
    dump(EP/'delivery_edit_plan.json',plan)
    print(json.dumps({k:v for k,v in plan.items() if k not in ('silence_edits','word_emphasis')},indent=2),flush=True)
    run(['ffmpeg','-y','-v','error','-i',str(target),'-t','42','-c:a','libmp3lame','-b:a','192k',str(EP/'audio/faster_voice_preview.mp3')])


def map_time(t,plan):
    duration0=plan['source_seconds']
    removed=sum(max(0,min(t,c['end'])-c['start']) for c in plan['silence_edits'] if t>c['start'])
    scale=plan['narration_seconds']/(duration0-plan['removed_silence_seconds'])
    if t<=duration0: return (t-removed)*scale
    return plan['narration_seconds']+(t-duration0)  # Protect complete final words and final hold.


def render():
    plan=read(EP/'delivery_edit_plan.json')
    original=read(PARENT/'storyboard.json'); rows=[]
    for i,r in enumerate(original):
        row=dict(r)
        a=round(map_time(r['start'],plan)*30)
        b=round(map_time(original[i+1]['start'],plan)*30) if i+1<len(original) else math.ceil((plan['narration_seconds']+1.2)*30)
        row.update({'start':a/30,'duration':(b-a)/30,'parent_start':r['start'],'parent_duration':r['duration']})
        assert .5<row['duration']<=r['duration']+.1
        rows.append(row)
    dump(EP/'storyboard.json',rows)
    def segment(row):
        source=PARENT/'timeline_segments'/f"{row['id']}.mp4"
        if not source.exists(): source=VOICE_EP/'timeline_segments/fable-v1'/f"{row['id']}.mp4"
        assert source.is_file()
        target=EP/'timeline_segments'/f"{row['id']}.mp4"
        receipt=target.with_suffix('.json')
        digest=hashlib.sha256((sha(source)+str(row['duration'])).encode()).hexdigest()
        if target.exists() and receipt.exists() and read(receipt).get('hash')==digest: return target
        target.parent.mkdir(parents=True,exist_ok=True)
        # Keep footage/animation at its native speed. Trim the hold/end, not the mouse action speed.
        run(['ffmpeg','-y','-v','error','-i',str(source),'-an','-t',str(row['duration']),'-r','30',
             '-c:v','libx264','-preset','fast','-crf','17','-threads','2','-pix_fmt','yuv420p',
             '-video_track_timescale','15360',str(target)])
        dump(receipt,{'hash':digest,'parent_segment':str(source),'parent_sha256':sha(source)})
        return target
    with ThreadPoolExecutor(max_workers=3) as pool: paths=list(pool.map(segment,rows))
    listing=write_concat(paths,EP/'timeline_segments/concat.txt')
    final_seconds=rows[-1]['start']+rows[-1]['duration']
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-i',str(EP/'narration_zubenelgenubi.wav'),
         '-map','0:v:0','-map','1:a:0','-c:v','copy','-af','apad=pad_dur=1.3','-t',str(final_seconds),
         '-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(FINAL)])
    (EP/'REVIEW_PACKAGE.md').write_text('# Faster private-review version\n\nSame script, selected narrator, source order and thumbnail. '
        'Speech is pitch-preserving, long verified silent gaps are tightened, and selected meaning-bearing words have gentle emphasis. '
        'Visuals are retimed without faster cursor movement. No subtitles.\n\n'
        'Publishing remains disabled; the Anthropic launch excerpts are not cleared for public reuse. '
        'See parent_source_ledger.json, storyboard.json and delivery_edit_plan.json for provenance and time mapping.\n',encoding='utf-8')
    print(str(FINAL),flush=True)


def verify():
    from pipeline.captions import transcribe_words
    from pipeline.audio_qc import review_narration
    plan=read(EP/'delivery_edit_plan.json'); script=read(EP/'script.json')
    source=EP/'narration_zubenelgenubi.wav'
    words_path=EP/'audio'/f"full_{sha(source)[:12]}_words.json"
    if words_path.exists(): words=[TimedWord(**w) for w in read(words_path)]
    else:
        from dataclasses import asdict
        words=transcribe_words(source,model_size='small.en')
        dump(words_path,[asdict(w) for w in words])
    approved='\n\n'.join(p for c in script['chapters'] for p in c['paragraphs'])
    report=review_narration(source,approved,SOURCE_AUDIO,recognized_text=' '.join(w.text for w in words),min_intelligibility=.9)
    dump(EP/'audio_qc.json',report)
    dump(EP/'ending_check.json',{'recognized_last_words':[w.text for w in words[-22:]],
         'last_word_end':words[-1].end,'narration_seconds':duration(source),
         'video_seconds':duration(FINAL),'protected_tail_seconds':duration(FINAL)-duration(source)})
    print(json.dumps({'audio_passed':report['passed'],'metrics':report['metrics'],'failures':report.get('failures',[])},indent=2),flush=True)


def verify_video():
    from PIL import Image, ImageDraw, ImageFont
    plan=read(EP/'delivery_edit_plan.json'); rows=read(EP/'storyboard.json')
    original=read(PARENT/'storyboard.json')
    info=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(FINAL)]))
    video=next(s for s in info['streams'] if s['codec_type']=='video')
    decoded=subprocess.run(['ffmpeg','-v','error','-i',str(FINAL),'-f','null','-'],capture_output=True,text=True,timeout=600)
    black=subprocess.run(['ffmpeg','-hide_banner','-i',str(FINAL),'-vf','blackdetect=d=0.12:pix_th=0.04:pic_th=0.98','-an','-f','null','-'],capture_output=True,text=True,timeout=600)
    events=[line.strip() for line in black.stderr.splitlines() if 'black_start:' in line]
    checks={
        'exact_1080p_h264':(video['width'],video['height'],video['codec_name'])==(1920,1080,'h264'),
        '30fps':video['r_frame_rate']=='30/1',
        'full_decode_clean':decoded.returncode==0 and not decoded.stderr.strip(),
        'no_blackouts':black.returncode==0 and not events,
        'same_source_order':[(r['id'],r['asset_key']) for r in rows]==[(r['id'],r['asset_key']) for r in original],
        'no_missing_speech_tail':float(video['duration'])-plan['narration_seconds']>=1.15,
        'no_subtitle_stream':not any(s['codec_type']=='subtitle' for s in info['streams']),
        'source_voice_unchanged':sha(SOURCE_AUDIO)==plan['source_sha256'],
        'script_unchanged':sha(EP/'script.json')==sha(VOICE_EP/'script.json'),
        'close_to_caption_pace':abs(plan['after_wpm']-plan['reference_median_wpm'])<=3,
        'continuous_timeline':all(abs(a['start']+a['duration']-b['start'])<.001 for a,b in zip(rows,rows[1:])),
        'publishing_disabled':plan['publishing_enabled'] is False,
    }
    selected=[r for r in rows if r['kind']=='motion_graphic' or r['kind']=='official_source_excerpt']
    selected.append(rows[-1])
    folder=EP/'qc'; folder.mkdir(exist_ok=True)
    sheet=Image.new('RGB',(1440,math.ceil(len(selected)/3)*304),'#edeae4')
    draw=ImageDraw.Draw(sheet); font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    for i,row in enumerate(selected):
        t=row['start']+row['duration']-.08; frame=folder/f"{row['id']}_end.jpg"
        run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',str(FINAL),'-frames:v','1',str(frame)])
        with Image.open(frame) as image: sheet.paste(image.resize((480,270)),(i%3*480,i//3*304))
        draw.text((i%3*480+8,i//3*304+275),f"{row['id']} end {t:.2f}s",font=font,fill='#202520')
    sheet.save(folder/'motion_and_clip_endings.jpg',quality=94)
    report={'technical_passed':all(checks.values()),'checks':checks,'duration':info['format']['duration'],
            'sha256':sha(FINAL),'black_events':events,'public_release_ready':False,
            'visual_review':'Pending actual ending-frame review; original art direction unchanged.'}
    dump(folder/'delivery_qc.json',report)
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('stage',choices=['prepare_audio','render','verify','verify_video'])
    globals()[parser.parse_args().stage]()
