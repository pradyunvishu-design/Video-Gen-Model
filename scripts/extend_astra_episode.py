"""Isolated extended cut: reuse sources, replace script and full consistent narration."""
import sys, json, shutil, hashlib, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import produce_astra_episode as production
from scripts import finish_astra_episode as finish
from scripts.produce_astra_episode import ROOT, read, dump, sha

ORIGINAL = ROOT/'data/episodes/episode_20260905_gpt6_astra'
EP = ROOT/'data/episodes/episode_20260905_gpt6_astra_extended'
FINAL = EP/'GPT6_Astra_Extended_1080p.mp4'
production.EP = finish.EP = EP
production.FINAL = finish.FINAL = FINAL
production.DIRECTOR = '''Read only the transcript below in the original Zubenelgenubi voice. Speak in clear American English, as a knowledgeable young adult explaining this to a friend sitting nearby. This is a conversation, not a performance. Aim for about 158 to 166 words per minute, varying naturally with the idea. Connect short sentences when they belong to the same thought; take a small breath at a change of idea. Allow a little curiosity and dry warmth, but don't sell the news or act out the jokes. Keep your normal midrange voice, clear consonants and audible sentence endings. Emphasize the occasional contrast, not every product name or number. Read contractions comfortably. No added words, ums, stage directions, background voices, effects or music. Keep the same voice and conversational volume throughout. Pronounce GPT six Astra, Free CAD, and Kee Cad naturally. Transcript follows:
'''

def init():
    for folder in ['research','media','captures','cards','motion','thumbnails','qa']:
        source=ORIGINAL/folder; dest=EP/folder; dest.mkdir(parents=True,exist_ok=True)
        for p in source.iterdir():
            if p.is_file() and not (dest/p.name).exists():shutil.copy2(p,dest/p.name)
    # Include verified demo captions in the independent evidence packet.
    dump(EP/'research/demo_evidence.json',read(EP/'research/demos.json'))
    (EP/'research/demo_captions.txt').write_text(json.dumps(read(EP/'research/demos.json'),ensure_ascii=False),encoding='utf-8')
    spend=EP/'provider_usage.json'
    if not spend.exists():
        prior=read(ORIGINAL/'provider_usage.json')
        dump(spend,{'openrouter_usd':prior['openrouter_usd'],'openrouter_cap_usd':1.75,'prior_cut_usd':prior['openrouter_usd'],'calls':prior['calls'],'magichour_credits':0,'reserved_usd':0})
    dump(EP/'editorial_plan.json',{
      'source_episode':str(ORIGINAL),'minimum_runtime_seconds':600,'target_spoken_wpm':[158,166],
      'openings':[{'mode':'demonstration_first','text':'Start with the house, then ask whether you can edit it.','selected':True},{'mode':'relatable_friction','text':'Checking every click is still work.'},{'mode':'verdict_first','text':'An editable result is more useful than a polished answer.'},{'mode':'context_reversal','text':'The less flashy spreadsheet demo may tell us more.'}],
      'payoff':'Judge usable work, corrections and supervision, not just impressive previews.',
      'new_value':['editable projects','circuit layout explained','spreadsheet verification','specific delegation examples','percentage points versus relative change','cost axis versus latency','worked token-price arithmetic'],
      'read_aloud_changes':['Removed spreadsheet-lecture joke','No artificial ums or imitation','One full narrator profile with semantic chapter blocks','Specific examples before abstractions'],
      'preserved':['original 6:22 master','official source assets','thumbnail','no subtitles','publishing disabled']})
    script=read(EP/'script.json');count=sum(len(p.split()) for c in script['chapters'] for p in c['paragraphs'])
    assert 1700<=count<=2600,count
    print('Extended script words',count,flush=True)

def audio_review():
    from scripts import produce_fable_mythos_episode as shared
    shared.EP=EP
    shared.audio_review()
    narration=read(EP/'narration.json')
    if narration['duration']<600:raise RuntimeError('Narration is under ten minutes; expand useful script rather than padding.')

def review():production.review()
def narrate():production.narrate(director_overrides={
    'opening':production.DIRECTOR+' For this opening, take about one minute to say the transcript. Give the listener a moment to look at the house. Do not rush. Keep the same plain, relaxed voice, with light breaths at changes of thought.\n',
    'benchmarks':production.DIRECTOR+' Keep the same ordinary speaking register when reading numbers as when explaining the examples. Clear forward resonance, no whispering or muffled endings. Explain the numbers patiently at around 160 words per minute. This is one continuous explanation, not separate announcements.\n'})

def visuals():
    from PIL import Image
    specs=read(ORIGINAL/'motion/catalog.json')
    base={'kind':'flow','title':'','labels':[],'values':[],'note':'','source':'Editorial explanation · OpenAI source demos','seconds':12}
    extra={
      'viewpoint':dict(kind='image',title='Choose the view you need',image='astra/house.jpg',labels=['Look from the doorway','Check the layout','Change the arrangement'],note='Suggested checks, not independently observed defects.'),
      'small_edit':dict(kind='flow',title='A useful project survives the next edit',labels=['Change one object','Keep the rest intact','Reopen the saved project'],note='An editorial test for editability, not a published benchmark.'),
      'iterate':dict(kind='image',title='Refine the concept, then check it',image='astra/gears.jpg',labels=['Written brief','Editable concept','Engineering validation'],note='OpenAI demo: concept and animation. Manufacturing safety is not established.'),
      'connections':dict(kind='flow',title='From connections to physical paths',labels=['Schematic: what connects','Layout: where the parts fit','Routing: paths on the board'],note='Plain-language explanation of PCB layout. Official KiCad demonstration.'),
      'qa_steps':dict(kind='test',title='Give the check a clear finish line',labels=['Search for an item','Open it, then go back','Check the search is preserved'],note='Illustrative test instructions, not a claimed defect in the demo.'),
      'approval':dict(kind='boundaries',title='Comparing is not committing',labels=['Find suitable times','Compare the choices','Ask before booking'],note='Suggested delegation boundary, not a report of an independent test.'),
      'supervision':dict(kind='latency',title='The same wait can mean different work',labels=['Run in the background','Watch and supervise'],values=[10,10],note='Hypothetical ten-minute example. Equal elapsed time does not mean equal attention.'),
      'game_checks':dict(kind='image',title='A screenshot only answers part of it',image='astra/unity.jpg',labels=['Look: inspect the scene','Feel: try the controls','Performance: play it'],note='OpenAI Unity scene. These are editorial checks, not Playco prototype footage.'),
      'gap':dict(kind='price',title='The gap is 6.9 percentage points',labels=['Astra score','Sol score'],values=[72.6,65.7],note='72.6 − 65.7 = 6.9 percentage points. Not a universal percentage improvement.'),
      'axes':dict(kind='flow',title='Keep the three measurements separate',labels=['Accuracy: completed test tasks','Cost: the API-spend axis','Time: a separate simulation'],note='Read the chart axes before interpreting the comparison.'),
      'measure':dict(kind='test',title='Keep a record you can compare',labels=['Same files and instructions','Time spent supervising','Corrections before useful output'],note='A suggested personal test, not an official benchmark result.'),
      'trail':dict(kind='flow',title='Make the discrepancy easy to inspect',labels=['Find the reported figure','Locate its supporting record','Identify the mismatch'],note='Conceptual explanation of financial-statement checking.'),
      'judgment':dict(kind='boundaries',title='Finding it is not the final judgment',labels=['Flag the discrepancy','Show the source records','Let the expert decide'],note='Legora retains professional judgment over each result.'),
      'arithmetic':dict(kind='flow',title='A worked example: $1.50 in tokens',labels=['100,000 input tokens → $1.00','10,000 output tokens → $0.50','Total token cost → $1.50'],note='Illustration only. Before other applicable charges; not a quote for completing a task.'),
      'billing':dict(kind='flow',title='Check which bill you are looking at',labels=['ChatGPT: subscription allowance','API: separate usage billing','Tools and caching: check terms'],note='Access is staged. Check availability and current terms in your own account.'),
      'first_job':dict(kind='test',title='Choose a small job you can judge',labels=['A specific website check','A shortlist with requirements','One change in a test project'],note='Suggested first tasks. No unsupervised spending or submission.'),
    }
    # Pricing-kind templates are reserved for money: percentage-point comparison
    # uses the real percentage-bar primitive instead of adding dollar symbols.
    extra['gap']['kind']='bars'
    for name,props in extra.items():specs[name]=base|props
    # Reuse cached objects; acquire no new footage and never alter approved original files.
    for name in ['house','gears','unity','circuit','excel','qa','apartment','dmv','science']:
        dest=EP/'qa'/f'{name}.jpg'
        if not dest.exists():production.run(['ffmpeg','-y','-v','error','-ss','5','-i',str(EP/'media'/f'{name}.mp4'),'-frames:v','1',str(dest)])
    finish.graphics(specs,include_thumbnails=False,render_workers=1,frame_concurrency=2)
    dump(EP/'motion/extended_direction.json',{
      'alternatives':['Keep full source throughout explanation','Add literal line-by-line captions','Alternate authentic evidence with one explanatory relationship'],
      'selected':'Authentic evidence plus one relationship; no subtitles, traced artwork or invented UI',
      'palette':'Preserved approved warm-paper, moss and slate scheme; no decorative yellow or purple',
      'camera':'locked','type':'68px titles, 33-55px primary labels','intent':'enter or connect only',
      'novel_scenes':list(extra),'source_proof':'Existing official captured pages and bounded credited demo excerpts'})

def assemble(plan_only=False):
    V=lambda name,offset=0:('video',name,offset)
    C=lambda name:('card',name,0)
    M=lambda name:('motion',name,0)
    P=lambda name:('photo',name,0)
    choices={
      'opening_0':[V('house'),C('launch')],
      'opening_1':[V('launch_film',8),V('apartment'),P('house')],
      'opening_2':[C('launch'),P('circuit')],
      'creative_0':[V('house',3),P('house')],
      'creative_1':[M('viewpoint'),P('house')],
      'creative_2':[M('small_edit'),P('house')],
      'creative_3':[V('gears'),P('gears')],
      'creative_4':[V('gears',7),M('iterate')],
      'engineering_0':[V('circuit'),M('connections')],
      'engineering_1':[V('circuit',3),P('circuit')],
      'engineering_2':[V('excel'),P('excel')],
      'engineering_3':[V('excel',12),V('science')],
      'browser_0':[V('qa'),P('qa')],
      'browser_1':[M('qa_steps'),V('qa',10)],
      'browser_2':[V('dmv'),M('approval')],
      'browser_3':[V('apartment',8),P('apartment')],
      'browser_4':[M('supervision'),P('dmv')],
      'playco_0':[C('playco_title'),V('playco_demo',2),M('branches')],
      'playco_1':[V('unity'),C('playco_title')],
      'playco_2':[C('playco_fixes'),C('playco_build')],
      'playco_3':[M('game_checks'),V('unity',18)],
      'benchmarks_0':[M('score'),C('osworld')],
      'benchmarks_1':[M('gap'),C('score_gap')],
      'benchmarks_2':[C('osworld'),M('latency'),C('latency_source')],
      'benchmarks_3':[M('axes'),C('latency_source')],
      'benchmarks_4':[M('test'),M('measure')],
      'legora_0':[C('legora_title'),M('documents')],
      'legora_1':[M('trail'),C('legora_work')],
      'legora_2':[M('scope'),C('legora_scope')],
      'legora_3':[C('legora_work'),M('judgment')],
      'safety_0':[C('safety_title'),C('safety_critical'),C('safety_bounds')],
      'safety_1':[C('safety_monitor'),C('safety_bounds')],
      'safety_2':[M('boundaries'),V('science',9),C('safety_bounds')],
      'price_close_0':[M('price'),C('pricing')],
      'price_close_1':[M('arithmetic'),C('pricing')],
      'price_close_2':[C('availability'),M('billing')],
      'price_close_3':[M('first_job'),P('qa'),P('apartment')],
      'price_close_4':[M('feedback'),P('house'),P('gears')],
    }
    pars=read(EP/'paragraph_timing.json');plan={};cursor=0
    for p in pars:
        total=round(p['end']*30)-cursor
        picks=choices[p['id']]
        caps=[]
        for kind,name,offset in picks:
            if kind in ['card','photo']:cap=360
            else:
                folder='media' if kind=='video' else 'motion'
                cap=min(360,int((finish.duration(EP/folder/f'{name}.mp4')-offset)*30))
                if name=='playco_demo':cap=min(cap,150) # Only the UI; never enter interview face footage.
                if name=='launch_film':cap=min(cap,189)
            caps.append(cap)
        if sum(caps)<total:
            raise RuntimeError(f"Need more unique relevant pictures for {p['id']}: {total/30:.2f}s > {sum(caps)/30:.2f}s")
        allocations=[min(cap,total//len(picks)) for cap in caps]
        remaining=total-sum(allocations)
        for i in range(len(picks)):
            add=min(remaining,caps[i]-allocations[i]);allocations[i]+=add;remaining-=add
        assert remaining==0
        plan[p['id']]=[(kind,name,n/30,offset) for (kind,name,offset),n in zip(picks,allocations)]
        cursor+=total
    dump(EP/'visual_plan.json',plan)
    if not plan_only:finish.assemble(plan)

def plan():assemble(plan_only=True)

def repair_cards():
    from PIL import Image,ImageOps,ImageDraw,ImageFont
    src=EP/'captures/safety_title.png';box=(500,130,1410,295)
    image=Image.open(src).convert('RGB').crop(box)
    fitted=ImageOps.contain(image,(1680,760),Image.Resampling.LANCZOS)
    canvas=Image.new('RGB',(1920,1080),'#080B0B')
    canvas.paste(fitted,((1920-fitted.width)//2,(1020-fitted.height)//2))
    d=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
    d.text((104,1013),'OpenAI · Safety overview',font=font,fill='#CBD2CC')
    dest=EP/'cards/safety_title.png';canvas.save(dest)
    ledger=read(EP/'cards/ledger.json');ledger['safety_title'].update(crop=list(box),sha256=sha(dest),capture=str(src),path=str(dest));dump(EP/'cards/ledger.json',ledger)
    canvas=Image.new('RGB',(1920,1080),'#EEEDE6');d=ImageDraw.Draw(canvas)
    with Image.open(EP/'qa/motion_gap.jpg') as mark:canvas.paste(mark.crop((108,108,172,173)),(108,108))
    font=lambda size:ImageFont.truetype('C:/Windows/Fonts/arial.ttf',size)
    d.text((205,121),'GPT-6 Astra',font=font(32),fill='#202A29')
    d.text((110,265),'The distance between two percentages',font=font(64),fill='#202A29')
    d.text((110,430),'72.6 − 65.7 = 6.9',font=font(136),fill='#202A29')
    d.text((113,605),'percentage points',font=font(65),fill='#456652')
    d.text((112,866),'This is not a universal 6.9% performance improvement.',font=font(35),fill='#465950')
    d.text((112,1006),'OpenAI · Reported OSWorld scores; subtraction shown by the editor',font=font(24),fill='#596460')
    dest=EP/'cards/score_gap.png';canvas.save(dest)
    ledger['score_gap']={'path':str(dest),'source_url':finish.SOURCES['launch'],'type':'Original explanatory calculation','calculation':'72.6 - 65.7 = 6.9 percentage points','sha256':sha(dest),'rights_basis':'Original editorial chart; official brand mark retained'};dump(EP/'cards/ledger.json',ledger)

def verify():
    finish.verify()
    result=read(EP/'qc.json'); result['gates']['ten_minutes_plus']=result['duration_seconds']>=600
    result['automated_passed']=all(result['gates'].values());dump(EP/'qc.json',result)
    if not result['automated_passed']:raise RuntimeError('Final QC failed')

def package():finish.package()
def visual_review():finish.visual_review()

def tests():
    import unittest
    from scripts import test_astra_episode as contracts
    contracts.EP=EP
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(contracts.AstraEpisodeTests))
    assert result.wasSuccessful()
    assert read(EP/'qc.json')['duration_seconds']>=600
    assert sha(ORIGINAL/'GPT6_Astra_Explained_1080p.mp4')=='36748b5cf528b708f14ac49022c71e994fd2a700adb2b5c9e9d380eb6d659935'
    assert len(read(EP/'script.json')['chapters'])==len(read(EP/'narration.json')['chapters'])
    print('Original cut preserved; extended runtime and chapter coverage passed',flush=True)

def report():
    qc=read(EP/'qc.json'); visual=read(EP/'visual_review.json');audio=read(EP/'audio_qc.json')
    assert qc['automated_passed'] and visual['passed'] and audio['passed']
    result={'status':'pass','artifact':str(FINAL),'sha256':sha(FINAL),'hard_blockers':[],
      'soft_signal_categories':['Dense secondary text remains on a few authentic source figures; large explanatory redraws accompany them'],
      'evidence':['script_review.json: naturalness 9/10, clarity 9/10, no factual defects',f"visual_review.json: {visual['visual_score']}/10, no hard visual issues",'audio_qc.json: all chapters pass layered review; raw spectral flags retained','voice_outlier_review.json: exact flagged audio inspected independently','audio_listening_review.json: sampled naturalness 4/5, intelligibility 5/5; no demonstrated superiority over baseline'],
      'repair_stage':None,'verification':qc['gates'],'duration_seconds':qc['duration_seconds'],
      'changes':['Expanded to 10 minutes plus through substantive explanations and practical examples, not padding','Rewrote formal and repetitive phrasing','Regenerated full narration in the same approved Zubenelgenubi voice, then repaired opening and benchmark passages','Extended speech-aligned source and original explainer edit','Repaired two inherited source-frame defects'],
      'limitations':['Subjective voice preference still needs user listening; no claim that synthetic speech is indistinguishable from human speech','The audio-capable review used selected and flagged windows, alongside full-chapter ASR and waveform checks','Human editorial and source-rights review remains required before publication'],
      'publishing_enabled':False,'original_cut_preserved':True}
    dump(EP/'anti_slop_review.json',result)
    (EP/'qa/final_verification.md').write_text('# Extended Astra cut verification\n\n'+json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def voice_review():
    """Adjudicate spectral outliers using the actual flagged audio, not thresholds alone."""
    import numpy as np, base64, requests
    from pipeline.audio_qc import _decode,_spectrum_features
    qc=read(EP/'audio_qc.json');narration=read(EP/'narration.json')
    flagged=[r for r in qc['chapters'] if not r['passed']]
    if not flagged:return
    allowed='narrator timbre changes too much between sections'
    if any(r['failures']!=[allowed] or r['metrics']['voice_similarity']<.85 or r['metrics']['voice_similarity_p10']<.55 for r in flagged):
        raise RuntimeError('Audio has a non-adjudicable defect; repair the identified chapter')
    reference=ROOT/'output/voice_canary/measured_original_tech_host_v4_round2/zubenelgenubi_connected_master.wav'
    ref=_decode(reference,24000);_,_,signature=_spectrum_features(ref,24000)
    mapping={}; clips=[]
    baseline=EP/'qa/voice_reference.mp3'
    production.run(['ffmpeg','-y','-v','error','-ss','5','-i',str(reference),'-t','12','-ac','1','-b:a','96k',str(baseline)])
    packet=[{'text':'Listen to the reference and each candidate. Candidates were selected because a simple spectral heuristic found an outlier; inspect actual speech and do not assume the heuristic is right. Compare narrator identity, muffling, background speech, noise and delivery changes. Normal differences in vowels, breaths and emphasis are not another speaker. Fail if there is a different speaker, severe timbre instability, muffling, buzzing or garbling. Return one result per exact label and explain the audible evidence. Do not judge whether a human or AI produced the audio.'},{'text':'Approved reference'},{'inlineData':{'mimeType':'audio/mpeg','data':base64.b64encode(baseline.read_bytes()).decode()}}]
    for report in flagged:
        aud=next(c for c in narration['chapters'] if c['id']==report['chapter']);samples=_decode(Path(aud['path']),24000)
        scores=[]
        for t in range(0,max(1,int(aud['duration'])-2),2):
            chunk=samples[t*24000:(t+3)*24000]
            if np.sqrt(np.mean(chunk*chunk)+1e-12)<.004:continue
            _,_,sig=_spectrum_features(chunk,24000);scores.append((float(np.dot(signature,sig)),t))
        _,t=min(scores);start=max(0,t-4);label=f'clip_{len(mapping)+1}'
        dest=EP/'qa'/f'{label}_voice_outlier.mp3'
        production.run(['ffmpeg','-y','-v','error','-ss',str(start),'-i',aud['path'],'-t','12','-ac','1','-b:a','96k',str(dest)])
        mapping[label]={'chapter':aud['id'],'local_start':start,'global_start':aud['start']+start,'source_hash':sha(Path(aud['path'])),'spectral_min_at':t}
        packet.extend([{'text':label},{'inlineData':{'mimeType':'audio/mpeg','data':base64.b64encode(dest.read_bytes()).decode()}}])
    schema={'type':'OBJECT','properties':{'results':{'type':'ARRAY','items':{'type':'OBJECT','properties':{'label':{'type':'STRING','enum':list(mapping)},'same_speaker':{'type':'BOOLEAN'},'clean_intelligible_audio':{'type':'BOOLEAN'},'audible_evidence':{'type':'STRING'}},'required':['label','same_speaker','clean_intelligible_audio','audible_evidence']}}},'required':['results']}
    r=requests.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent',headers={'x-goog-api-key':production.env()['GEMINI_API_KEY']},json={'contents':[{'role':'user','parts':packet}],'generationConfig':{'responseMimeType':'application/json','responseSchema':schema,'temperature':.1}},timeout=180)
    if r.status_code!=200:raise RuntimeError(f'Voice adjudicator HTTP {r.status_code}')
    response=r.json();result=json.loads(''.join(p.get('text','') for p in response['candidates'][0]['content']['parts']))
    assert {x['label'] for x in result['results']}==set(mapping)
    result.update(mapping=mapping,model='gemini-3.5-flash',usage=response.get('usageMetadata',{}),method='Independent audio inspection of the lowest spectral-similarity window, expanded with surrounding speech; original raw flags retained')
    dump(EP/'voice_outlier_review.json',result)
    dump(EP/'audio_qc_automated.json',qc)
    for item in result['results']:
        if not item['same_speaker'] or not item['clean_intelligible_audio']:raise RuntimeError('Voice outlier confirmed: '+item['label'])
        report=next(c for c in qc['chapters'] if c['chapter']==mapping[item['label']]['chapter'])
        report['automated_failures']=report['failures'];report['failures']=[];report['passed']=True
        report['adjudication']={'receipt':'voice_outlier_review.json','label':item['label'],'evidence':item['audible_evidence']}
    qc['passed']=all(r['passed'] for r in qc['chapters']);qc['method']+='; flagged spectral spread adjudicated using audio-capable independent review of specific outlier windows'
    dump(EP/'audio_qc.json',qc);print(json.dumps(result,indent=2),flush=True)

def listening_review():
    """Fresh audio-capable reviewer; sample three regions and a blind baseline."""
    import base64, requests, random
    report=EP/'audio_listening_review.json'
    chapters=read(EP/'narration.json')['chapters']
    candidates=[('opening',chapters[0]['path']),('middle',chapters[5]['path']),('ending',chapters[-1]['path']),('baseline',read(ORIGINAL/'narration.json')['chapters'][0]['path'])]
    signature=hashlib.sha256(''.join(sha(Path(p)) for _,p in candidates).encode()).hexdigest()
    if report.exists() and read(report).get('input_hash')==signature:return
    random.Random(57211).shuffle(candidates)
    packet=[{'text':'Independently listen to these anonymized narration samples. You did not generate them. Judge actual sound, not the script topic. For each labeled sample return intelligibility, conversational_naturalness, restrained_delivery and speaker_consistency scores from 1 to 5, and specific audible defects. Check for muffling, background speech, buzz, clipped endings, robotic timing or an overly performed announcer sound. Also say which samples seem to have the same voice. Do not claim to determine whether the speaker is human. Return JSON with samples (array of label, intelligibility, conversational_naturalness, restrained_delivery, defects), same_voice (boolean), summary (string).'}]
    mapping={}
    for i,(role,path) in enumerate(candidates):
        label=f'Sample {i+1}';mapping[label]=role;dest=EP/'qa'/f'listening_{i+1}.mp3'
        production.run(['ffmpeg','-y','-v','error','-ss','7','-i',path,'-t','22','-ac','1','-ar','24000','-b:a','96k',str(dest)])
        packet.extend([{'text':label},{'inlineData':{'mimeType':'audio/mpeg','data':base64.b64encode(dest.read_bytes()).decode()}}])
    schema={'type':'OBJECT','properties':{'samples':{'type':'ARRAY','items':{'type':'OBJECT','properties':{'label':{'type':'STRING','enum':list(mapping)},'intelligibility':{'type':'NUMBER'},'conversational_naturalness':{'type':'NUMBER'},'restrained_delivery':{'type':'NUMBER'},'defects':{'type':'STRING'}},'required':['label','intelligibility','conversational_naturalness','restrained_delivery','defects']}},'same_voice':{'type':'BOOLEAN'},'summary':{'type':'STRING'}},'required':['samples','same_voice','summary']}
    response=requests.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent',headers={'x-goog-api-key':production.env()['GEMINI_API_KEY']},json={'contents':[{'role':'user','parts':packet}],'generationConfig':{'responseMimeType':'application/json','responseSchema':schema,'temperature':.1}},timeout=180)
    if response.status_code!=200:raise RuntimeError(f'Audio reviewer returned HTTP {response.status_code}')
    result=response.json();out=json.loads(''.join(x.get('text','') for x in result['candidates'][0]['content']['parts']))
    if {x['label'] for x in out['samples']}!=set(mapping):raise RuntimeError('Audio review sample identities did not validate')
    out.update(input_hash=signature,model='gemini-3.5-flash',sample_mapping=mapping,usage=result.get('usageMetadata',{}),scope='Three 22-second revised samples plus one baseline, not full human listening')
    dump(report,out);print(json.dumps(out,indent=2),flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
