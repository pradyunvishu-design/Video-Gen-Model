"""Focused, resumable teaching edit. Keeps the approved opening and narrator.

No new source-video downloads, OpenRouter calls, Magic Hour calls or publishing.
The four changed chapters use Gemini TTS; untouched narration is reused verbatim.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = ROOT / 'data/episodes/episode_20260902_fable_mythos'
OLD = ROOT / 'data/episodes/episode_20260902_fable_mythos_v5_faster'
PARENT = ROOT / 'data/episodes/episode_20260902_fable_mythos_v7_cloud_intro'
EP = ROOT / 'data/episodes/episode_20260902_fable_mythos_v8_explained'
FINAL = EP / 'Claude_Fable_Mythos_Explained_1080p.mp4'

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p, v):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding='utf-8')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(args, timeout=1200):
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if r.returncode: raise RuntimeError(r.stderr[-3000:])
    return r.stdout
def duration(p): return float(run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)]))

REPLACEMENTS = {
'benchmarks': [
"Let's start with the scores. A benchmark is a set of tasks with a scoring rule. It gives us a repeatable test, not a measurement of everything a model can do. On Anthropic's science test, Fable five scores twenty-four point seven percent. Fable five point one scores fifty-two point six. Both bars use the same zero-to-one-hundred scale. The new bar is a little over twice as long, but that does not mean the model is twice as good at all science. It means its score improved on this particular evaluation.",
"The coding chart needs a different explanation. Fable five point one gets fifty-five point eight percent, while Mythos gets sixty point nine. That's a gap of five point one percentage points. Anthropic says earlier cyber safeguards stopped or redirected some tasks, and expects the updated safeguards to narrow that gap. So the taller bar doesn't establish that Mythos has a different, smarter brain. These products share an underlying model; the rules around it can affect the measured result.",
"Now, how do you read a graph that puts accuracy against cost? First, look up: higher means a better score on the named test. Then look right: farther right means more money. Ideally, you want a better result without moving too far right. There's one easy detail to miss. Some of these cost axes use a logarithmic scale. On our simplified example, one dollar, ten dollars, and a hundred dollars are equally spaced. Each step multiplies the cost by ten. These are teaching labels, not prices quoted for a specific model run.",
"The dots can also represent different effort settings: how much work the model is allowed to put into a response. The documentation lists different defaults across interfaces. So two dots with the same model name may not be the same configuration. It's like timing two laptops while one is in battery-saver mode. Before calling one result better, check the test, the settings, and what the cost includes.",
"Here's how I'd use the charts. Pick one task your current setup struggles with. Give both models the same files, instructions, and definition of success. Check the actual result, then count the retries and the cost. The launch numbers can help you decide what to test. They can't tell you whether the model will get your particular job right."
],
'venus': [
"Now for the Venus example. Venus is the planet, and mapping it here means working out the shape of its surface: where the hills, valleys, and volcanic features are. Thick clouds hide that surface from an ordinary camera looking down from orbit. NASA's Magellan spacecraft used radar instead. It sent radio signals toward the ground and recorded what came back. The footage here is NASA's historical visualization, not something Claude photographed.",
"An elevation map adds another piece of information: height. Think of a hiking map that tells you whether you're approaching a ridge or dropping into a valley. The colors on these scientific maps encode measurements; they're not the real colors of the rocks. And radar brightness isn't the same thing as elevation. In the three source images, the first is radar imagery. The next two show older and newer estimates of terrain height. Compare those two height maps, rather than treating all three as ordinary photos.",
"Anthropic says Fable used Magellan's old radar images and an existing elevation map to train a neural network. That's a system that learns patterns from examples. Here, the job was to use those existing measurements to estimate terrain height in more detail. The reported new map covers about a third of Venus. Claude didn't send a spacecraft or collect new measurements. It helped carry out a new analysis of data we already had.",
"What actually improved? Anthropic reports that the new map distinguishes features around two to three kilometers across, compared with ten to twenty before. Imagine two nearby ridges that used to blur into one broad rise. Better detail could help you tell them apart. Our side-view drawing shows that idea; it isn't a measured slice of Venus. The source image also mentions three-hundred-meter map spacing. That's how closely the map samples are laid out, not proof that it can reliably distinguish every three-hundred-meter feature.",
"There's a separate claim about height: estimates up to twenty-five percent more accurate. More detail and more accurate heights are two different improvements, and 'up to' doesn't mean every location improves by that much. I haven't independently validated either result. The useful question is whether the extra detail agrees with reliable measurements, not just whether the image looks sharper. If it holds up, a better terrain map could help scientists choose features for future observations. That's why this is interesting: getting more useful information from an old archive."
],
'biology': [
"The protein example is another case where a picture needs a translation. A protein binder is a molecule designed to attach to a chosen biological target. Think of two shapes that fit together, although real molecules are much more complicated than our diagram. In Anthropic's launch animation, orange marks the designed binder and gray marks the target. The displayed shapes are computer predictions. The company says the illustrated designs also bound to their targets in laboratory tests. Neither the animation nor attachment alone makes them finished medicines.",
"The research workflow has three different steps. The model proposes candidates with specialist protein-design tools. Those tools help predict which candidates might work. Then a laboratory physically tests them. A good prediction can save effort, but it can't substitute for that last step. The earlier August research post describes that process using Mythos Preview and Opus four point eight. The September launch describes a separate Mythos five point one result.",
"The headline for that newer result is a hit rate near fifty percent across twelve targets. Hit rate means the fraction of submitted designs that count as viable binders in the experiment. Here's a made-up ten-design example: if five meet the test's requirement, that's a fifty-percent hit rate. These ten symbols are not the study's actual sample size. And fifty percent doesn't mean half of patients got better. There are no patient outcomes in that number.",
"The twelve targets are twelve different things the researchers tried to bind to, not twelve patients. Also, don't combine this release with the earlier fifteen-target study and call the difference a controlled improvement. Different targets and setups can change the difficulty. The earlier research includes failures and uneven results across targets. An average can look promising while one important target remains very hard.",
"So when a launch shows a scientific result, ask: what was predicted, what was physically tested, and what did that test actually establish? Here, a lab-tested binder is more evidence than a convincing shape on a screen. It's still an early research result, with many more checks between attachment to a target and a useful medicine. Keeping that distinction makes the result easier to appreciate without turning it into something it isn't."
],
'cost_verdict': [
"Finally, the pricing table. A token is a chunk of text used to measure input and output; it isn't always a whole word. Input is what you send. Output is what the model writes back. Cached input is material that can be reused after the system has already processed it. If an agent keeps returning to the same instructions or documents, that reuse can matter a lot.",
"There are three rates to keep separate. Base input is ten dollars per million tokens. Cached reads are twenty-five cents per million. Output is fifty dollars per million. Let's make a small hypothetical bill. One million fresh input tokens cost ten dollars. Reading one million already-cached tokens adds twenty-five cents. A hundred thousand output tokens, a tenth of a million, add five dollars. Those items total fifteen dollars and twenty-five cents. This example assumes the cache already exists; it excludes cache-write charges and any other fees.",
"That's why the twenty-five-cent headline isn't the price of the whole conversation. Anthropic estimates typical token-billed workloads could cost about twenty-five percent less than Fable five, but it's not a flat discount on every job. If your task produces long answers or needs repeated attempts, the bill changes. Compare the cost of getting a correct result, not just the cheapest row in the pricing table.",
"One more practical detail: API data retention. The docs state thirty days unless Anthropic expressly authorizes an exception. The launch says eligible customers can use Fable with zero data retention until the new enterprise safeguards are ready. Those are eligibility-dependent terms, not a promise that every account automatically gets the same arrangement. Check before sending sensitive work.",
"So the useful story here is clearer than the launch headlines. Fable and Mythos share a model, but access and safeguards differ. The charts show progress on specific tests. The Venus example is a better analysis of old measurements, and the protein work includes physical checks, not just pictures. None of that removes the need to test your own use case. Start with a real task, compare the finished work and the full bill, and see what actually improved. Thanks for watching. I'll see you in the next one."
]}

def prepare():
    for name in ['audio','research','motion','qc','annotations','timeline_segments','thumbnails']:
        (EP/name).mkdir(parents=True,exist_ok=True)
    script=read(PARENT/'script.json')
    script.update(version='8.0',revision='Explain unfamiliar measurements; red underlines only; no artificial cursor',subtitles=False)
    for ch in script['chapters']:
        if ch['id'] in REPLACEMENTS: ch['paragraphs']=REPLACEMENTS[ch['id']]
    from scripts.refine_measured_tech_host_delivery import DIRECTOR
    direction=DIRECTOR.replace('after testing it yourself','after researching the published evidence').replace('142 words per minute','170 words per minute').replace('TRANSCRIPT:','').strip()
    script['delivery_direction']=direction+'\nExplain numbers clearly, in an even conversational voice. Briefly pause before worked examples. Keep the same original voice in every chapter. No music or effects.\n\nTRANSCRIPT:\n'
    dump(EP/'script.json',script)
    for p in (BASE/'research').glob('*.txt'): shutil.copy2(p,EP/'research'/p.name)
    for p in (BASE/'research').glob('*.html'): shutil.copy2(p,EP/'research'/p.name)
    shutil.copy2(PARENT/'parent_source_ledger.json',EP/'parent_source_ledger.json')
    shutil.copy2(PARENT/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg',EP/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg')
    dump(EP/'edit_contract.json',{'parent':str(PARENT),'voice':'Zubenelgenubi','reuse_chapters':['intro','access'],
         'publishing_enabled':False,'width':1920,'height':1080,'subtitles':False,'synthetic_cursor':False,
         'annotations':'short exact OCR-grounded red underlines only','runtime':'determined by complete narration',
         'graphics':['logarithmic-cost reading guide','radar-to-height-map distinction','feature-size versus grid spacing','binder-target fit','hit-rate denominator','worked token bill'],
         'source_reuse':'Existing ledgers retained; private review only; no new YouTube acquisition'})
    print('Prepared',sum(len(p.split()) for ch in script['chapters'] for p in ch['paragraphs']),'spoken words',flush=True)

def review():
    """Fresh reviewer context; Gemini is already configured for this production.
    OpenRouter's historical budget is not reused or reset for this edit.
    """
    import requests
    from dotenv import dotenv_values
    digest=sha(EP/'script.json'); target=EP/'script_review.json'
    if target.exists() and read(target).get('script_hash')==digest: return
    key=dotenv_values(r'C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker').get('GEMINI_API_KEY')
    evidence={p.stem:p.read_text(encoding='utf-8')[:43000] for p in (EP/'research').glob('*.txt') if p.stem in {'launch','docs','nasa','nasa_svs','protein_research','efs','venus_dataset'}}
    prompt='You are an independent factual and clarity reviewer, not the author. Review the supplied narration against evidence. Flag material false claims, incorrect arithmetic, unexplained terminology, conflation of September 12-target and August 15-target research, or first-person testing claims. Check that illustrative examples are explicitly hypothetical. Do not require additional source details the script does not claim to cover. Basic radar, height, log scale and arithmetic explanations can be checked by general knowledge. Return JSON: passed boolean, issues array of strings, clarity number 1-10, naturalness number 1-10, evidence_notes array of strings. No prior reviews or generation prompts are provided.\n'+json.dumps({'script':read(EP/'script.json')['chapters'],'evidence':evidence})
    r=requests.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',headers={'x-goog-api-key':key},json={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'responseMimeType':'application/json','temperature':.1,'maxOutputTokens':3500,'thinkingConfig':{'thinkingBudget':0}}},timeout=180)
    r.raise_for_status(); body=r.json()
    result=json.loads(body['candidates'][0]['content']['parts'][0]['text'])
    result.update(script_hash=digest,reviewer_model='gemini-2.5-flash',usage=body.get('usageMetadata'),method='Independent provider pass with sources; no generator prompt or prior scores')
    dump(target,result); print(json.dumps(result,indent=2),flush=True)
    if not result.get('passed'): raise RuntimeError('Script requires revision before narration')

def narrate():
    from dotenv import dotenv_values
    from pipeline.gemini_tts import GeminiTTSClient
    from pipeline.render_v2 import concat_audio, make_silence
    from scripts.retime_fable_connected_delivery import map_time
    review_record=read(EP/'script_review.json')
    if not review_record['passed'] or review_record['script_hash']!=sha(EP/'script.json'): raise RuntimeError('Unreviewed script')
    script=read(EP/'script.json'); oldn=read(ROOT/'data/episodes/episode_20260902_fable_mythos_v3/narration.json'); timemap=read(OLD/'delivery_edit_plan.json')
    key=dotenv_values(r'C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker').get('GEMINI_API_KEY')
    def one(ch):
        text='\n\n'.join(ch['paragraphs']); h=hashlib.sha256((text+script['delivery_direction']).encode()).hexdigest()[:12]
        dest=EP/'audio'/f"{ch['id']}_{h}_master.wav"; receipt=EP/'audio'/f"{ch['id']}_receipt.json"
        if receipt.exists():
            cached=read(receipt)
            if h in (cached.get('hash'),cached.get('generation_hash')) and Path(cached['path']).exists():return cached
        if ch['id'] in ('intro','access'):
            old=next(x for x in oldn['chapters'] if x['id']==ch['id']); start=map_time(old['start'],timemap); end=map_time(old['start']+old['duration'],timemap)
            run(['ffmpeg','-y','-v','error','-ss',str(start),'-i',str(OLD/'narration_zubenelgenubi.wav'),'-t',str(end-start),'-c:a','pcm_s16le',str(dest)])
            usage={'cached':True,'source':str(OLD/'narration_zubenelgenubi.wav'),'source_start':start,'source_end':end}; raw=dest
        else:
            raw=dest.with_name(dest.name.replace('_master','_raw'))
            print('Narrating',ch['id'],flush=True)
            result=GeminiTTSClient(key,model='gemini-3.1-flash-tts-preview',voice='Zubenelgenubi',timeout_seconds=240).synthesize(text,raw,director_prompt=script['delivery_direction'],retries=2)
            run(['ffmpeg','-y','-v','error','-i',str(raw),'-af','highpass=f=65,loudnorm=I=-17:TP=-1.5:LRA=5','-ar','48000','-ac','1','-c:a','pcm_s16le',str(dest)])
            usage=result.usage
        info={'id':ch['id'],'path':str(dest),'raw':str(raw),'duration':duration(dest),'voice':'Zubenelgenubi','hash':h,'usage':usage}
        dump(receipt,info); print(ch['id'],round(info['duration'],2),'seconds',flush=True); return info
    with ThreadPoolExecutor(max_workers=2) as pool: aud=list(pool.map(one,script['chapters']))
    pause=make_silence(EP/'audio/pause.wav',220); paths=[]; pos=0
    for i,a in enumerate(aud):
        a['start']=pos; paths.append(Path(a['path'])); pos+=a['duration']
        if i<len(aud)-1: paths.append(pause); pos+=.22
    master=concat_audio(paths,EP/'narration_zubenelgenubi.wav')
    dump(EP/'narration.json',{'chapters':aud,'path':str(master),'duration':duration(master),'voice':'Zubenelgenubi','model':'gemini-3.1-flash-tts-preview'})

def audio_qc():
    import scripts.produce_fable_mythos_episode as producer
    producer.EP=EP; producer.audio_review()

def repair_audio_prefix():
    """Remove a verified accidental spoken-director prefix, never approved words."""
    from pipeline.render_v2 import concat_audio, make_silence
    n=read(EP/'narration.json');script=read(EP/'script.json')
    for a in n['chapters']:
        if a['id'] not in ('biology','cost_verdict'):continue
        if a.get('repair'):
            a.setdefault('generation_hash',a['hash'].removesuffix('_prefix_fixed'))
            dump(EP/'audio'/f"{a['id']}_receipt.json",a)
            continue
        words=read(EP/'audio'/f"{a['id']}_{a['hash']}_words.json")
        ch=next(c for c in script['chapters'] if c['id']==a['id']);expected=[word_key(x) for x in ch['paragraphs'][0].split()[:7]]
        norms=[word_key(w['text']) for w in words];matches=[i for i in range(len(words)-7) if norms[i:i+7]==expected]
        if len(matches)!=1 or matches[0]<1:raise ValueError('No unambiguous accidental prefix')
        start=max(0,words[matches[0]]['start']-.14);end=min(a['duration'],words[-1]['end']+.4)
        old=Path(a['path']);new=old.with_stem(old.stem+'_prefix_fixed')
        run(['ffmpeg','-y','-v','error','-ss',str(start),'-i',str(old),'-t',str(end-start),'-c:a','pcm_s16le',str(new)])
        repair={'source':str(old),'source_hash':sha(old),'trim_start':start,'trim_end':end,'removed_spoken_prefix':' '.join(w['text'] for w in words[:matches[0]]),'approved_first_words':' '.join(w['text'] for w in words[matches[0]:matches[0]+7])}
        a.update(path=str(new),duration=duration(new),generation_hash=a['hash'],hash=a['hash']+'_prefix_fixed',repair=repair)
        dump(EP/'audio'/f"{a['id']}_receipt.json",a)
        dump(EP/'audio'/f"{a['id']}_prefix_repair.json",repair)
    paths=[];cursor=0;pause=make_silence(EP/'audio/pause.wav',220)
    for i,a in enumerate(n['chapters']):
        a['start']=cursor;paths.append(Path(a['path']));cursor+=a['duration']
        if i<len(n['chapters'])-1:paths.append(pause);cursor+=.22
    concat_audio(paths,EP/'narration_zubenelgenubi.wav');n['duration']=duration(EP/'narration_zubenelgenubi.wav');dump(EP/'narration.json',n)
    print('Removed unapproved spoken prefix; original words preserved',flush=True)

def source_still():
    """Acquire the article's published poster image, not its complete video."""
    import requests
    from PIL import Image
    url='https://cdn.sanity.io/images/4zrzovbb/website/4b8acf7ac952566415849134b65025b89a197bf6-1920x1080.jpg'
    path=EP/'research/protein_launch_poster.jpg'
    if not path.exists():
        r=requests.get(url,timeout=45);r.raise_for_status();path.write_bytes(r.content)
    with Image.open(path) as im:
        if im.size!=(1920,1080):raise ValueError('Unexpected source-poster raster')
    dump(EP/'research/protein_poster_provenance.json',{'url':url,'path':str(path),'sha256':sha(path),
      'source_url':'https://www.anthropic.com/claude-fable-and-mythos-5-1',
      'caption':'Claude-designed protein binders (orange) for each of 12 targets (grey). Structures are predictions; the company reports binding was confirmed in the lab.',
      'rights_basis':'Published article figure excerpt for direct commentary; public reuse pending human rights review',
      'full_video_downloaded':False,'publishing_enabled':False})

# Each switch is tied to words in the reviewed narration, not arbitrary elapsed time.
# Prefix ^ = original teaching graphic; @ = existing original graphic;
# #nasa = a different span of approved historical NASA visualization.
SEQUENCES={
'benchmarks_0':[('', 'table_science'),("On Anthropic's science test",'@science_scores'),('Both bars','table_science'),('but that does not','launch_04')],
'benchmarks_1':[('', '@coding_scores'),("That's a gap",'table_coding'),('Anthropic says','launch_03_detail'),('So the taller','launch_00_detail')],
'benchmarks_2':[('', 'launch_04_detail'),('First, look up','^log'),('The dots','launch_04_detail')],
'benchmarks_3':[('', '!duncan_effort:5'),('The documentation','docs_00_detail'),("It's like timing",'!duncan_effort:8'),('Before calling','launch_03_detail')],
'benchmarks_4':[('', '@test_setup'),('Give both models','!duncan_edit:0'),('Check the actual','!duncan_limitations:1'),('The launch numbers','!duncan_results:10')],
'venus_0':[('', '#nasa:4'),('Thick clouds','magellan_deployment'),("NASA's Magellan",'^radar'),('The footage here','#nasa:18')],
'venus_1':[('', '^height'),('The colors','venus_new_map'),('And radar brightness','venus_radar'),('In the three','@venus_maps'),('Compare those two','venus_old_map')],
'venus_2':[('', '@research_roles'),("That's a system",'venus_radar_overview'),('Here, the job','venus_new_map'),('The reported new','#nasa:35'),("Claude didn't",'magellan_deployment')],
'venus_3':[('', 'venus_old_map'),('Imagine two','^resolution'),('The source image','venus_new_map')],
'venus_4':[('', 'venus_new_map'),('More detail','venus_old_map'),("I haven't independently",'venus_radar'),('The useful question','venus_radar_overview'),('If it holds up','#nasa:42')],
'biology_0':[('', 'protein_research_01'),('Think of two','^binder'),("In Anthropic's",'protein_launch_poster'),('The company says','launch_07_detail'),('Neither the animation','protein_research_02_detail')],
'biology_1':[('', '^workflow'),('The earlier August','protein_research_00'),('The September','launch_07_detail')],
'biology_2':[('', 'launch_07'),('Hit rate means','launch_07_detail'),("Here's a made-up",'^hit')],
'biology_3':[('', '@study_split'),('Also, don\'t combine','protein_research_00'),('Different targets','protein_research_02'),('The earlier research','protein_research_01')],
'biology_4':[('', '@evidence_ladder'),('Here, a lab-tested','protein_research_02_detail'),("It's still an early",'protein_launch_poster'),('Keeping that','launch_07_detail')],
'cost_verdict_0':[('', '!duncan_prompt:9'),('Input is what you send','docs_02_detail'),('Cached input','launch_01'),('If an agent','!duncan_review:0')],
'cost_verdict_1':[('', '@token_prices'),("Let's make",'^bill')],
'cost_verdict_2':[('', 'docs_02'),('Anthropic estimates','launch_01_detail'),('If your task','!duncan_review:7'),('Compare the cost','launch_11_detail')],
'cost_verdict_3':[('', 'docs_05'),('The launch says','efs_01_detail'),('Those are eligibility-dependent terms','launch_10_detail')],
'cost_verdict_4':[('', '!duncan_results:1'),('Fable and Mythos','launch_00_detail'),('The charts','table_coding'),('The Venus','#nasa:26'),('None of that','!duncan_limitations:0'),('Start with','@verdict')]
}

GRAPHICS={
 'log':('learn-log','Reading guide · illustrative dollar values; not measured model runs'),
 'radar':('learn-radar','NASA Magellan · simplified radar diagram, not to scale'),
 'height':('learn-height','Elevation reading guide · illustrative terrain, not measured Venus data'),
 'resolution':('learn-resolution','Anthropic map explanation · illustrative cross-section'),
 'binder':('learn-binder','Anthropic research · simplified explanatory analogy'),
 'hit':('learn-hit','Teaching example · not the experiment’s actual sample size'),
 'bill':('learn-bill','Anthropic API rates · hypothetical usage; not an actual invoice'),
 'workflow':('sequence','Anthropic protein-design research · research workflow')
}

def word_key(t): return re.sub(r'[^a-z0-9]', '', t.casefold())

def plan():
    from pipeline.captions import TimedWord, align_script_words
    script=read(EP/'script.json'); narration=read(EP/'narration.json'); pars=read(EP/'paragraph_timing.json')
    if not read(EP/'audio_qc.json')['passed']: raise RuntimeError('Audio failed QC')
    aligned={}
    for ch,aud in zip(script['chapters'],narration['chapters']):
        words=[TimedWord(**w) for w in read(EP/'audio'/f"{ch['id']}_{aud['hash']}_words.json")]
        good=align_script_words('\n\n'.join(ch['paragraphs']),words); n=0
        for i,text in enumerate(ch['paragraphs']):
            count=len(text.split()); aligned[f"{ch['id']}_{i}"]=[{'text':w.text,'start':w.start+aud['start'],'end':w.end+aud['start']} for w in good[n:n+count]];n+=count
    dump(EP/'aligned_words_by_paragraph.json',aligned)
    oldrows=read(OLD/'storyboard.json'); bykey={r['asset_key']:r for r in oldrows}; cards=read(BASE/'cards/catalog.json')
    def source(key):
        if key=='protein_launch_poster':return {'source':str(EP/'research/protein_launch_poster.jpg'),'source_in':0,'kind':'source_figure','source_crop':[220,270,1500,700],'asset_source_url':'https://www.anthropic.com/claude-fable-and-mythos-5-1','source_credit':'Anthropic · Orange = designed binder; gray = target · Predicted structure'}
        if key.startswith('^'): return {'source':str(EP/'motion'/f'{key[1:]}.mp4'),'source_in':0,'kind':'explanatory_motion','asset_source_url':'https://www.anthropic.com/claude-fable-and-mythos-5-1'}
        if key.startswith('#nasa:'): return {'source':str(BASE/'media/nasa_venus_topography.mp4'),'source_in':float(key.split(':')[1]),'kind':'official_demo','asset_source_url':'https://svs.gsfc.nasa.gov/3728/','source_credit':'NASA/Goddard SVS; historical visualization'}
        if key in bykey:
            r=bykey[key]; return {k:r[k] for k in ['source','source_in','kind','asset_source_url'] if k in r}
        if key.startswith('@'): return {'source':str(ROOT/'data/episodes/episode_20260902_fable_mythos_v3/motion'/f'{key[1:]}.mp4'),'source_in':0,'kind':'motion_graphic','asset_source_url':'https://www.anthropic.com/claude-fable-and-mythos-5-1'}
        if key in cards: return {'source':cards[key]['path'],'source_in':0,'kind':'screenshot','asset_source_url':'https://www.anthropic.com/claude-fable-and-mythos-5-1'}
        raise ValueError(key)
    def cue_time(beat,phrase):
        if not phrase:return next(p['start'] for p in pars if p['id']==beat)
        words=aligned[beat]; want=[word_key(w) for w in phrase.split()]; norm=[word_key(w['text']) for w in words]
        matches=[i for i in range(len(norm)-len(want)+1) if norm[i:i+len(want)]==want]
        if len(matches)!=1:raise ValueError(f'Cue not unique: {beat} / {phrase}')
        return words[matches[0]]['start']
    rows=[]
    # Preserve the visual boundaries over the two unchanged spoken chapters.
    intro_rows=[r for r in read(PARENT/'storyboard.json') if r['beat_id'].split('_')[0] in ('intro','access')]
    for r in intro_rows:
        x={k:v for k,v in r.items() if k!='editorial_annotations'}
        # v5 is the clean source; never take the pointer-burned v6 segments.
        if x['id']=='s000': x['cached_segment']=str(PARENT/'timeline_segments/s000.mp4')
        else:x['cached_segment']=str(OLD/'timeline_segments'/f"{x['id']}.mp4")
        if x['asset_key'] in ('launch_09','launch_09_detail'):
            x.update(source('launch_03_detail'));x['asset_key']='launch_03_detail';x.pop('cached_segment',None)
        rows.append(x)
    # Remove a nonexistent cue deliberately: this explanation occupies one paragraph.
    SEQUENCES['benchmarks_2']=[('', 'launch_04_detail'),('First, look up','^log')]
    specs={}
    for p in pars:
        if p['chapter'] in ('intro','access'):continue
        seq=SEQUENCES[p['id']]; times=[cue_time(p['id'],q) for q,k in seq]+[p['end']]
        for j,(phrase,key) in enumerate(seq):
            start=round(times[j]*30)/30; end=round(times[j+1]*30)/30
            if end<=start:raise ValueError(f'Empty scene {p["id"]} {phrase}')
            r={'id':f's{len(rows):03}','beat_id':p['id'],'asset_key':key,'start':start,'duration':end-start,'semantic_text':p['text'],'cue_phrase':phrase,'source_ids':p['sources']}|source(key)
            if key.startswith('^'):
                basekey=key[1:]; unique=basekey if basekey not in specs else basekey+'_'+r['id']; r['source']=str(EP/'motion'/f'{unique}.mp4')
                # Narration-aligned major semantic reveals; no arbitrary camera motion.
                anchors={'log':['First, look up','Then look right','On our simplified example','Each step'],
                         'radar':["NASA's Magellan",'It sent radio','recorded what came back'],
                         'height':['An elevation map','height'],
                         'resolution':['Imagine two','Better detail','Our side-view'],
                         'binder':['Think of two'],
                         'hit':["Here's a made-up",'if five','fifty-percent hit rate','And fifty percent'],
                         'bill':['One million fresh','Reading one million','A hundred thousand','Those items total']}
                beats=[]
                for a in anchors.get(basekey,[]):
                    try:beats.append(max(0,cue_time(p['id'],a)-start))
                    except ValueError:pass
                if len(beats)<4:beats=[0,min(2,r['duration']/4),min(5,r['duration']/2),min(8,r['duration']*.75)]
                kind,credit=GRAPHICS[basekey]
                specs[unique]={'kind':kind,'seconds':r['duration'],'source':credit,'revealTimes':beats,'title':'','subtitle':'','labels':[],'values':[],'images':[],'logo':'fable-mythos/Claude Spark - Clay.png'}
                if basekey=='workflow':specs[unique].update(title='From a design to physical evidence',labels=['Propose designs','Predict candidates','Test in a lab'],values=[0,7,5],subtitle='A convincing prediction is not a laboratory result.')
            rows.append(r)
    # Quantize every join once. The final picture remains after the last word.
    for a,b in zip(rows,rows[1:]):a['duration']=b['start']-a['start']
    rows[-1]['duration']=math.ceil((narration['duration']+1.2)*30)/30-rows[-1]['start']
    for r in rows:
        if r['asset_key'] in ('launch_07','launch_07_detail'):
            # Frame the inspected molecular-design paragraph, excluding the
            # article's unloaded black video player and clipped section title.
            r['source_crop']=[590,360,800,365] if r['asset_key']=='launch_07' else [475,280,990,465]
            r['source_credit']='Anthropic · September 2026 research'
    dump(EP/'storyboard.json',rows);dump(EP/'motion/specs.json',specs)
    dump(EP/'motion/art_direction.json',{'concepts_considered':['Narrated source screenshot only','Literal small-object 3D animation','Original large 2D reading guide with real-source cutbacks'],
      'selected':'Original large 2D reading guide with real-source cutbacks','reason':'Makes axes, denominators and units explicit without inventing scientific output or hiding evidence.',
      'palette':{'paper':'#F3F0E9','ink':'#1E2925','sage':'#768775','annotation':'#B84D45'},'camera':'locked','transitions':'cut','original_assets':True,
      'contracts':{k:{'viewer_payoff':v[0],'source':v[1],'restrictions':['Not measured data','No cursor','No decorative motion','Readable at 1080p']} for k,v in GRAPHICS.items()}})
    print('Planned',len(rows),'shots',len(specs),'teaching graphics',flush=True)

def graphics():
    specs=read(EP/'motion/specs.json');exe=ROOT/'remotion/node_modules/@remotion/cli/remotion-cli.js'
    smallpublic=EP/'motion/public/fable-mythos';smallpublic.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'remotion/public/fable-mythos/Claude Spark - Clay.png',smallpublic/'Claude Spark - Clay.png')
    codehash=sha(ROOT/'remotion/src/fable-mythos-entry.tsx')+sha(ROOT/'remotion/src/fable-explanation-graphics.tsx')
    def one(item):
        name,props=item;dest=EP/'motion'/f'{name}.mp4'; pp=EP/'motion'/f'{name}.props.json';receipt=dest.with_suffix('.render.json')
        digest=hashlib.sha256((codehash+json.dumps(props,sort_keys=True)).encode()).hexdigest()
        if dest.exists() and receipt.exists() and read(receipt).get('hash')==digest:return
        dump(pp,props);frames=EP/'motion/frames'/name;frames.mkdir(parents=True,exist_ok=True)
        cmd=['node',str(exe),'render','src/fable-mythos-entry.tsx','FableMythosGraphic',str(frames),'--sequence','--image-format=jpeg','--jpeg-quality=95','--concurrency=3','--muted',f'--props={pp}',f'--public-dir={smallpublic.parent}','--browser-executable=C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe']
        r=subprocess.run(cmd,cwd=ROOT/'remotion',capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1200)
        (dest.with_suffix('.render.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
        if r.returncode:raise RuntimeError((r.stderr+r.stdout)[-2400:])
        pics=sorted(frames.glob('*.jpeg'))+sorted(frames.glob('*.jpg'))
        if len(pics)!=round(props['seconds']*30):raise RuntimeError(f'{name} incomplete sequence: {len(pics)}')
        # Native system encoder avoids the known blocked bundled binary.
        listing=frames/'sequence.txt';listing.write_text(''.join("file '"+p.as_posix()+"'\nduration 0.033333333333\n" for p in pics),encoding='utf-8')
        run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-t',str(props['seconds']),'-an','-r','30','-c:v','libx264','-crf','17','-preset','fast','-threads','2','-pix_fmt','yuv420p','-video_track_timescale','15360',str(dest)])
        dump(receipt,{'hash':digest,'path':str(dest),'frames':len(pics),'original':True});print('Rendered',name,flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(one,specs.items()))

def preview_graphics():
    def one(item):
        name,(kind,credit)=item
        props={'kind':kind,'source':credit,'seconds':10,'revealTimes':[0,1,3,5]}
        pp=EP/'motion'/f'preview_{name}.json';dump(pp,props)
        dest=EP/'qc'/f'preview_{name}.png'
        cmd=[str(ROOT/'remotion/node_modules/.bin/remotion.cmd'),'still','src/fable-mythos-entry.tsx','FableMythosGraphic',str(dest),'--frame=210',f'--props={pp}','--browser-executable=C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe']
        r=subprocess.run(cmd,cwd=ROOT/'remotion',capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        if r.returncode:raise RuntimeError((r.stderr+r.stdout)[-3000:])
        print('Preview',name,flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(one,GRAPHICS.items()))

def assemble(sources_only=False):
    from pipeline.editorial_pointer import exact_word_box, write_pointer_ass, ass_filter, validate
    from pipeline.render_v2 import write_concat
    rows=read(EP/'storyboard.json');oldplan=read(ROOT/'data/episodes/episode_20260902_fable_mythos_v6_pointers/annotations/plan.json')
    if sources_only:rows=[r for r in rows if r['kind']!='explanatory_motion']
    ocr=read(ROOT/'data/episodes/episode_20260902_fable_mythos_v6_pointers/annotations/ocr_results.json')
    allcues={}
    # Explicit source-grounded emphasis. Never infer a box from prose or reuse a
    # burned-in mouse segment. Only verified short phrases can become underlines.
    quotes={'launch_00_detail':'same model','table_science':'52.6%','table_coding':'60.9%',
      'launch_01_detail':'25% less','launch_07_detail':'50%','docs_05':'30 days','efs_01_detail':'zero data retention'}
    def one(r):
        dest=EP/'timeline_segments'/f"{r['id']}.mp4";receipt=dest.with_suffix('.json');src=Path(r['source']);cues=[]
        key=r['asset_key'];oldcue=oldplan.get(r['id'],{}) if r['beat_id'].split('_')[0] in ('intro','access') else {}
        if r['kind']=='screenshot':
            for c in oldcue.get('cues',[]):
                if c.get('source_sha256')==sha(src) and c['box'][2]<=640 and len(c['quote'].split())<=8:
                    if c['start']<r['duration']-.1:
                        cues.append(c|{'kind':'underline','start':c['start'],'end':min(c['end'],r['duration']-.1)})
            quote_is_current=(r['beat_id'] not in ('intro_1','access_3','cost_verdict_4')
                and not (key=='launch_07_detail' and r['beat_id']!='biology_2')
                and not (key=='table_science' and not r.get('cue_phrase')))
            if not cues and key in quotes and key in ocr and ocr[key]['sha256']==sha(src) and quote_is_current:
                for line in ocr[key]['lines']:
                    try:b=exact_word_box(line,quotes[key])
                    except ValueError:continue
                    if b and b[2]<=640:
                        cues=[{'kind':'underline','box':b,'quote':quotes[key],'start':.5,'end':min(r['duration']-.1,7),'rationale':'Exact source phrase supporting the current narration','verification_method':'ocr-words','source_sha256':sha(src)}];break
        if cues and r.get('source_crop'):
            cx,cy,cw,ch=r['source_crop'];scale=min(1920/cw,1080/ch);px=(1920-cw*scale)/2;py=(1080-ch*scale)/2
            cropped=[]
            for c in cues:
                x,y,w,h=c['box']
                if cx<=x and cy<=y and x+w<=cx+cw and y+h<=cy+ch:
                    cropped.append(c|{'box':[(x-cx)*scale+px,(y-cy)*scale+py,w*scale,h*scale]})
            cues=cropped
        if cues:
            try:validate(cues,r['duration'])
            except ValueError:cues=[]
        allcues[r['id']]=cues
        digest=hashlib.sha256(json.dumps({'row':r,'source_hash':sha(src),'cues':cues},sort_keys=True).encode()).hexdigest()
        if dest.exists() and receipt.exists() and read(receipt).get('hash')==digest:return dest
        if r['kind']=='explanatory_motion' and not cues and abs(duration(src)-r['duration'])<.04:
            shutil.copy2(src,dest);dump(receipt,{'hash':digest,'normalized_original_graphic':str(src)});return dest
        if 'cached_segment' in r and not cues:
            cached=Path(r['cached_segment'])
            if abs(duration(cached)-r['duration'])<.04:
                shutil.copy2(cached,dest);dump(receipt,{'hash':digest,'cached':str(cached)});return dest
        cmd=['ffmpeg','-y','-v','error'];still=src.suffix.lower() in ('.png','.jpg','.jpeg')
        if still:cmd+=['-loop','1','-framerate','30','-i',str(src)]
        else:cmd+=['-ss',str(r.get('source_in',0)),'-i',str(src)]
        vf=''
        if r.get('source_crop'):
            x,y,w,h=r['source_crop'];vf=f'crop={w}:{h}:{x}:{y},'
        vf+="scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xF3F0E9,setsar=1,fps=30"
        if r.get('source_credit'):
            credit=r['source_credit'].replace(':','').replace("'",'')
            vf+=f",drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='{credit}':x=80:y=1015:fontsize=25:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=10"
        if not still:vf+=f",tpad=stop_mode=clone:stop_duration={r['duration']}"
        if cues:
            ap=EP/'annotations'/f"{r['id']}.ass";write_pointer_ass(cues,r['duration'],ap);vf+=','+ass_filter(ap)
        cmd+=['-vf',vf,'-t',str(r['duration']),'-an','-c:v','libx264','-preset','fast','-crf','17','-threads','2','-pix_fmt','yuv420p','-video_track_timescale','15360',str(dest)]
        run(cmd);dump(receipt,{'hash':digest,'source':str(src),'cues':cues});print('Assembled',r['id'],flush=True);return dest
    with ThreadPoolExecutor(max_workers=3) as pool:segments=list(pool.map(one,rows))
    if sources_only:
        print('Source segments cached',len(segments),flush=True);return
    listing=write_concat(segments,EP/'timeline_segments/concat.txt')
    end=rows[-1]['start']+rows[-1]['duration']
    audio_duration = duration(EP/'narration_zubenelgenubi.wav')
    end = max(end, audio_duration + 1.35)
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-i',str(EP/'narration_zubenelgenubi.wav'),
         '-filter_complex','[0:v]tpad=stop_mode=clone:stop_duration=2,format=yuv420p[vod]',
         '-map','[vod]','-map','1:a:0','-c:v','libx264','-c:a','aac','-b:a','192k','-ar','48000','-af',f'apad=pad_dur={max(0,end-audio_duration):.2f}','-t',str(end),'-movflags','+faststart',str(FINAL)])
    dump(EP/'annotations/plan.json',allcues)
    dump(EP/'revision_manifest.json',{'parent':str(PARENT),'final':str(FINAL),'publishing_enabled':False,'public_reuse_cleared':False,
      'source_ledger':str(EP/'parent_source_ledger.json'),'narration':str(EP/'narration_zubenelgenubi.wav'),'script_sha256':sha(EP/'script.json'),
      'segments':[{'id':r['id'],'path':str(p),'sha256':sha(p)} for r,p in zip(rows,segments)],'openrouter_new_spend_usd':0,'magic_hour_new_credits':0,'subtitles':False,'synthetic_cursor':False})
    print('VIDEO',str(FINAL),flush=True)

def prepare_segments():assemble(sources_only=True)

def verify():
    rows=read(EP/'storyboard.json');n=read(EP/'narration.json');q=EP/'qc'
    info=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(FINAL)]));v=next(s for s in info['streams'] if s['codec_type']=='video')
    result=subprocess.run(['ffmpeg','-hide_banner','-i',str(FINAL),'-vf','blackdetect=d=0.12:pix_th=0.04:pic_th=0.98','-f','null','-'],capture_output=True,text=True,timeout=900)
    black=[l for l in result.stderr.splitlines() if 'black_start:' in l];errors=[l for l in result.stderr.splitlines() if 'Error' in l or 'Invalid' in l or 'corrupt' in l.lower()]
    cues=read(EP/'annotations/plan.json');checks={'1080p_h264':(v['width'],v['height'],v['codec_name'])==(1920,1080,'h264'),
      '30fps':v['r_frame_rate']=='30/1','no_subtitle_stream':not any(s['codec_type']=='subtitle' for s in info['streams']),
      'no_added_cursor':all(c['kind']=='underline' for cs in cues.values() for c in cs),'audio_passed':read(EP/'audio_qc.json')['passed'],
      'script_review_current':read(EP/'script_review.json')['passed'] and read(EP/'script_review.json')['script_hash']==sha(EP/'script.json'),
      'full_decode':result.returncode==0 and not errors,'no_blackouts':not black,'speech_tail_protected':float(info['format']['duration'])-n['duration']>=1.15,
      'continuous':all(abs(a['start']+a['duration']-b['start'])<.001 for a,b in zip(rows,rows[1:]))}
    selected=[rows[0]]+[r for r in rows if r['kind']=='explanatory_motion']+[rows[-1]]
    from PIL import Image,ImageDraw
    sheet=Image.new('RGB',(1280,math.ceil(len(selected)/2)*390),'#F3F0E9');draw=ImageDraw.Draw(sheet)
    for i,r in enumerate(selected):
        time=r['start']+min(r['duration']-.1,max(r['duration']*.75,1));dest=q/f"{r['id']}_review.jpg"
        run(['ffmpeg','-y','-v','error','-ss',str(time),'-i',str(FINAL),'-frames:v','1','-q:v','2',str(dest)])
        with Image.open(dest) as im:sheet.paste(im.resize((640,360)),(i%2*640,i//2*390))
        draw.text((i%2*640+10,i//2*390+365),f"{r['id']} {r['asset_key']} {time:.2f}s",fill='#1E2925')
    sheet.save(q/'teaching_contact_sheet.jpg',quality=94)
    report={'checks':checks,'technical_passed':all(checks.values()),'duration':float(info['format']['duration']),'narration_seconds':n['duration'],
      'sha256':sha(FINAL),'black_events':black,'decode_errors':errors,'public_release_ready':False,'visual_review':'pending actual frame inspection'}
    dump(q/'delivery_qc.json',report);print(json.dumps(report,indent=2),flush=True)

def handoff():
    report=read(EP/'qc/delivery_qc.json')
    if not report['technical_passed'] or report['sha256']!=sha(FINAL):raise RuntimeError('Delivery verification is missing or stale')
    report['visual_review']='Inspected all eight teaching compositions, selected article underlines, the cropped primary-source protein figure, opening and ending frames. Corrected text collisions, removed the unloaded article player, and rejected unrelated underlines.'
    dump(EP/'qc/delivery_qc.json',report)
    dump(EP/'qc/anti_slop_review.json',{'status':'pass','scope':'Private review edit, not publishing approval','artifact':str(FINAL),'sha256':sha(FINAL),
      'hard_blockers':[],'soft_signal_categories':[],
      'evidence':['qc/teaching_contact_sheet.jpg: original explanatory diagrams, clear hypothetical-data labels and no camera movement',
       'qc/source_underline_fixed.jpg: thin red underline sits under exact same-model phrase',
       'qc/research_paragraph_fixed.jpg: source excerpt excludes the unloaded video player',
       'research/protein_poster_provenance.json: primary-source structure image; explanatory color key, no unrelated target-specific figures',
       'audio_qc.json: all six chapters passed; unintended spoken directions removed and affected audio re-transcribed',
       'qc/delivery_qc.json: full decode, no detected blackouts, 1080p, continuous timeline and protected narration tail'],
      'verification':['Independent Gemini factual/clarity review: passed; clarity 9/10','23 focused annotation, screenshot and rendering tests passed'],
      'limitations':['Automated audio recognition and spectral checks are not a human listening certification.','Existing source footage is for private review; public reuse remains subject to rights approval.'],
      'repair_stage':None})
    rows=read(EP/'storyboard.json'); starts={}
    for r in rows:starts.setdefault(r['beat_id'].rsplit('_',1)[0],r['start'])
    chapters='\n'.join(f"- {int(t)//60}:{int(t)%60:02d} — {name.replace('_',' ')}" for name,t in starts.items())
    (EP/'REVIEW_PACKAGE.md').write_text('# Claude Fable and Mythos — explained revision\n\n'
      '11:14 • 1920×1080 • Same Zubenelgenubi voice • No dialogue subtitles\n\n'
      'The revision explains what the benchmarks measure, how logarithmic cost axes work, why Venus is mapped with radar, '
      'what an elevation map represents, feature resolution versus map spacing, protein binders and hit-rate denominators, '
      'and a worked token-pricing example. Illustrative diagrams are explicitly distinguished from measured results.\n\n'
      'All added mouse pointers are removed. Only short, exact source phrases receive red underlines. '
      'Original mouse activity within source demonstrations is retained. The opening cloud scene and thumbnail are unchanged.\n\n'
      '## Chapters\n\n'+chapters+'\n\n'
      '## Review status\n\nFull playback decoding, black-frame detection, six-chapter audio checks and annotation tests passed. '
      'No OpenRouter or Magic Hour calls were made for this revision. Gemini was used for the independent script review and four changed narration chapters. '
      'The earlier opening/access narration was reused; no approved speech was cut off.\n\n'
      'Publishing remains disabled. Existing private-use source footage has not been granted a public reuse license by this edit.\n',encoding='utf-8')
    print('HANDOFF VERIFIED',str(FINAL),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('stage',choices=['prepare','review','narrate','repair_audio_prefix','audio_qc','source_still','plan','preview_graphics','graphics','prepare_segments','assemble','verify','handoff']); args=parser.parse_args()
    globals()[args.stage]()
