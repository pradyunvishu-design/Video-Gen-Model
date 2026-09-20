"""Resumable Astra finance/law episode; no publishing actions."""
import argparse
import re
from pathlib import Path
from scripts import produce_astra_episode as shared
from scripts import produce_fable_mythos_episode as audio_tools

EP = Path(__file__).resolve().parents[1] / 'data/episodes/episode_20260919_astra_jobs'
SOURCES = {
 'F': 'https://openai.com/index/introducing-chatgpt-financial-services/',
 'L': 'https://openai.com/index/astra-for-law/',
 'A': 'https://openai.com/index/gpt-6-astra/',
 'I': 'https://www.ilo.org/resource/news/one-four-jobs-risk-being-transformed-genai-new-ilo%E2%80%93nask-global-index-shows',
}
DIRECTOR = '''Read only the transcript below in the original Zubenelgenubi voice. One consistent young adult male technology host, clear ordinary American English, explaining something to one curious friend. Aim for 160 to 166 words per minute, connected conversational phrases with short natural pauses where a thought changes. Stay understated and matter-of-fact, lightly curious, not performing. No announcer voice, forced bass, breathy endings, vocal fry, whispering, sing-song inflection, exaggerated punchlines, background voices, music or effects. Keep stable full resonance and finish every sentence. Pronounce ChatGPT as Chat G P T, Astra as AS-truh, API as A P I, NASK as nask. Do not read any extra words. Transcript follows:\n'''

def prepare():
    raw = (EP/'script_draft.md').read_text(encoding='utf-8')
    chapters=[]
    mapping={'01_intro':['F','L'],'02_finance':['F'],'03_model':[], '04_finance_score':['F'], '05_law':['L'], '06_law_score':['L'], '07_other_work':['A'], '08_boundaries':['F'], '09_jobs':['I'], '10_close':['F','L']}
    for block in raw.split('\n## ')[1:]:
        header,body=block.split('\n',1)
        ident,title=header.split(' | ',1)
        paragraphs=[p.strip() for p in body.strip().split('\n\n') if p.strip()]
        chapters.append({'id':ident,'title':title,'paragraphs':paragraphs,'sources':[SOURCES[x] for x in mapping[ident]],'evidence_ids':mapping[ident],'commentary_policy':'Original hypothetical examples and proposed evaluation steps are explicitly labeled. Product assertions reference attached evidence IDs.'})
    words=sum(len(re.findall(r'\S+',p)) for c in chapters for p in c['paragraphs'])
    shared.dump(EP/'script.json',{'title':'Is Astra Coming for Our Jobs? Finance, Law and What Actually Changes','target_duration_seconds':900,'word_count':words,'publishing_enabled':False,'chapters':chapters})
    shared.dump(EP/'editorial_brief.json',{'episode':'astra_jobs','angle':'Task handoff, not an unsupported mass-layoff prediction','format':'evidence-backed product explainer and original analysis','sources':SOURCES,'narrator':'Zubenelgenubi','subtitles':False,'opening_candidates':['OpenAI now has a version of ChatGPT for financial services, and another Astra offering aimed at lawyers.','A spreadsheet can look finished long before the work is checked. Astra makes that distinction worth paying attention to.','What does an AI assistant actually change between the assignment and the finished workbook?','The interesting part of the Astra launch is not the chat window. It is the handoff.'],'selected_opening':0,'opening_reason':'Names the two concrete releases immediately, then a useful jobs question rather than a doom prediction.','visual_policy':'Muted official excerpts; source-led evidence views; original explanatory graphics; no fictitious UI; one motion family use each; no subtitles; no music unless separately approved.'})
    print('Script words:',words,'estimated minutes at171wpm:',round(words/171,2),flush=True)

def review():
    shared.EP=EP;shared.review()

def narrate():
    shared.EP=EP;shared.DIRECTOR=DIRECTOR;shared.narrate()

def audio_qc():
    audio_tools.EP=EP;audio_tools.audio_review()

def time_audio():
    """Small transparent cadence adjustment, never cut speech or repeat audio."""
    import hashlib
    from pipeline.render_v2 import concat_audio, make_silence, duration
    record=shared.read(EP/'narration.json')
    if record.get('timing_adjustment'): return
    shared.dump(EP/'narration_original.json',record)
    gap=.18*(len(record['chapters'])-1)
    factor=(record['duration']-gap)/(898.8-gap)
    if not .90<=factor<=1.10: raise RuntimeError('Needs delivery revision, not extreme time stretch')
    pause=make_silence(EP/'audio/pause.wav',180)
    paths=[];chapters=[];cursor=0
    for c in record['chapters']:
        h=hashlib.sha256((shared.sha(Path(c['path']))+f':tempo:{factor:.8f}').encode()).hexdigest()[:12]
        target=EP/'audio'/f"{c['id']}_{h}_timed.wav"
        if not target.exists(): shared.run(['ffmpeg','-y','-v','error','-i',c['path'],'-af',f'atempo={factor:.8f}','-ar','48000','-ac','1','-c:a','pcm_s16le',str(target)])
        d=duration(target);chapters.append({**c,'path':str(target),'duration':d,'start':cursor,'hash':h,'tempo_factor':factor});paths.append(target);cursor+=d
        if len(chapters)<len(record['chapters']): paths.append(pause);cursor+=.18
    master=concat_audio(paths,EP/'narration_zubenelgenubi_timed.wav')
    shared.dump(EP/'narration.json',{**record,'chapters':chapters,'path':str(master),'duration':duration(master),'timing_adjustment':factor})
    print('Timed narration',duration(master),'tempo',factor,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','review','narrate','time_audio','audio_qc']);a=p.parse_args();globals()[a.stage]()
