"""Semantic, sentence-timed Astra jobs edit; no filler or looping sources."""
from __future__ import annotations
import json, math, hashlib, argparse
import subprocess
import io
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
EP=ROOT/'data/episodes/episode_20260919_astra_jobs'
URL='https://openai.com/index/introducing-chatgpt-financial-services/'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save_png_if_changed(image,path):
    data=io.BytesIO();image.save(data,format='PNG');payload=data.getvalue()
    if not path.exists() or path.read_bytes()!=payload:path.write_bytes(payload)

def normalize_screens():
    output=[];folder=EP/'normalized_screens';folder.mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
    for item in read(EP/'media/product_screens.json'):
        raw=Image.open(item['path']).convert('RGB')
        # Genuine full UI: trim only the surrounding launch-page green matte.
        crop=[round(raw.width*.080),round(raw.height*.065),round(raw.width*.920),round(raw.height*.933)]
        ui=raw.crop(crop);ui.thumbnail((1824,974),Image.Resampling.LANCZOS)
        canvas=Image.new('RGB',(1920,1080),'#F2F1ED');canvas.paste(ui,((1920-ui.width)//2,(1016-ui.height)//2))
        draw=ImageDraw.Draw(canvas);draw.text((52,1028),'Source — OpenAI | Official demo, not our hypothetical example',font=font,fill='#41413c')
        path=folder/(item['id']+'.png');save_png_if_changed(canvas,path)
        output.append({**item,'path':str(path),'kind':'picture','source_path':item['path'],'source_sha256':item['sha256'],'sha256':sha(path),'crop_xyxy':crop,'framing':[0,0,1920,1080],'relevance':item['caption']+'; official example, not an independently performed test','max_editorial_uses':2})
    dump(folder/'ledger.json',output)
    return output

def focused_screens():
    originals={x['id']:x for x in read(EP/'media/product_screens.json')}
    normalized={x['id']:x for x in read(EP/'normalized_screens/ledger.json')}
    regions={'finance_citations':[900,420,1550,680],'finance_lbo_model':[680,175,1780,865]}
    results=[];mapping={}
    for ident,region in regions.items():
        source=originals[ident];record=normalized[ident];raw=Image.open(source['path']).convert('RGB');crop=record['crop_xyxy']
        full=raw.crop(crop);full.thumbnail((1824,974),Image.Resampling.LANCZOS)
        scale=full.width/(crop[2]-crop[0]);ox=(1920-full.width)//2;oy=(1016-full.height)//2
        native=[round((region[0]-ox)/scale+crop[0]),round((region[1]-oy)/scale+crop[1]),round((region[2]-ox)/scale+crop[0]),round((region[3]-oy)/scale+crop[1])]
        detail=raw.crop(native);detail.thumbnail((1810,950),Image.Resampling.LANCZOS)
        frame=Image.new('RGB',(1920,1080),'#F2F1ED');frame.paste(detail,((1920-detail.width)//2,(1010-detail.height)//2))
        draw=ImageDraw.Draw(frame);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
        draw.text((52,1028),'Source — OpenAI | Official example',font=font,fill='#41413c')
        path=EP/'normalized_screens'/f'{ident}_focus.png';save_png_if_changed(frame,path)
        results.append({'id':ident+'_focus','canonical_asset_id':'screen_'+ident,'path':str(path),'sha256':sha(path),'source_path':source['path'],'source_sha256':source['sha256'],'native_crop_xyxy':native,'source_url':source['announcement_url'],'method':'Locked crop from original3840px source, not retyped or generated','repetition_policy':'Counts as the second use of the same canonical product screenshot'})
        mapping['screen_'+ident]=str(path)
    dump(EP/'normalized_screens/focused_ledger.json',results)
    return mapping

def assets():
    table={}
    for item in read(EP/'media/ledger.json'):
        table[item['id']]={'asset_id':item['id'],'path':item['path'],'kind':'video','source_url':item['source_url'],'relevance':item['caption'],'available_frames':item.get('available_frames',round(item['verified_duration']*30))}
    for item in read(EP/'captures/ledger.json'):
        ident='article_'+item['id'];table[ident]={'asset_id':ident,'path':item['path'],'kind':'article','source_url':item['source_url'],'relevance':item['caption'],'framing':[0,0,1920,1080]}
    for item in normalize_screens():
        ident='screen_'+item['id'];table[ident]={'asset_id':ident,'path':item['path'],'kind':'picture','source_url':item['announcement_url'],'relevance':item['relevance'],'framing':[0,0,1920,1080]}
    for name in ['job_tasks','finance_flow','financial_model','finance_benchmark','law_research','law_benchmark','permission_layers','work_handoff','automation_boundary','practical_check']:
        ident='motion_'+name;table[ident]={'asset_id':ident,'path':str(EP/'motion'/f'{name}.mp4'),'kind':'motion','source_url':'editorial://astra-jobs/'+name,'relevance':'Original explanatory graphic: '+name,'available_frames':360}
    # Optional original editorial assets must carry their own semantic ledger.
    extra=EP/'edit/editorial/ledger.json'
    if extra.exists():
        for item in read(extra):table[item['asset_id']]=item
    return table

# Explicitly authored commentary, not invented screenshots or empirical tests.
# Each diagram encodes a different relationship in the approved narration.
EDITORIAL={
 'claim_source':('detail','Does the source support this sentence?','Claim','Matching evidence','Proposed citation check • not a product test'),
 'treasury':('document','The benchmark task','Treasury Bulletins','Tables + footnotes + analysis','OfficeQA Pro • source: OpenAI'),
 'pp':('equation','Read the difference','69.9 − 60.2','9.7 percentage points','OfficeQA Pro • source: OpenAI'),
 'notforecast':('contrast','A benchmark is not a trading strategy','Document questions','Profitable trades','Different questions. Different evidence.'),
 'holdout':('document','Test it on familiar work','Known assignment','Expected answer','Proposed evaluation • use work you can check'),
 'footnote':('detail','The footnote can change the answer','Reported number','Date + definition + exception','Proposed evaluation • inspect the source'),
 'review_time':('clock','Count the time after the answer','Drafting','Review + correction','Proposed evaluation • total time to usable work'),
 'contract':('document','Locate the clause, then inspect it','Contract clause','Source passage + uncertainty','Hypothetical acquisition review • not legal advice'),
 'questions':('equation','What was measured','200 questions','Legal research benchmark','Source: OpenAI • high-reasoning setting'),
 'noterror':('contrast','Do not turn this into a universal error rate','Benchmark score','All real legal work','The denominator and task are different'),
 'uncertainty':('document','A stronger score still leaves questions','What is supported?','What is missing?','Interpretation • not a new product test'),
 'assistant_a':('document','A confident answer is not enough','Proposed answer','Where did it come from?','Hypothetical assistant A'),
 'assistant_b':('detail','Make the handoff reviewable','Proposed answer','Passage + limits + next check','Hypothetical assistant B'),
 'checkout':('branch','Turn “test checkout” into cases','Empty cart','Discount / slow connection','Hypothetical test plan • not an observed Astra run'),
 'axes':('axes','First, read the axes','What is measured?','Against what?','Proposed scientific-chart review'),
 'omissions':('document','Ask what the chart leaves out','Included observations','Missing data or cases','Proposed scientific-chart review'),
 'draft':('document','Permission to draft is not permission to send','Draft email','Stop for review','Hypothetical permission boundary'),
 'send':('branch','One action, one explicit boundary','Human review','Approved action','Illustrative policy • not a product setting screenshot'),
 'review_owner':('document','Who checks the handoff?','Named reviewer','Decision owner','Proposed team workflow'),
 'change':('detail','Show the work that changed','Before → after','Evidence → decision','Proposed review record'),
 'accepted':('contrast','Measure usable work','Response generated','Work accepted','Acceptance requires checking, not just speed'),
 'orgsplit':('branch','The same capability can change teams differently','Less routine work','Different staffing choices','Possible outcomes • not a forecast'),
 'outcomes':('contrast','A capability is not an employment forecast','What software can do','What employers choose','Separate the technology from the organizational decision'),
 'training':('document','Keep the learning in the work','Review a source','Correct and defend the answer','Original commentary • junior training'),
 'verify':('detail','The important question is “why?”','Check the source','Explain the correction','Original commentary • accountable review'),
 'skill':('contrast','A prompt is a tool, not a guarantee','Prompt skill','Judgment + verification','No promise of job security'),
 'smalltask':('document','Start with one reversible task','Non-sensitive input','Recoverable outcome','Proposed evaluation • keep the stakes small'),
 'standard':('detail','Decide what “good” means first','Known standard','Sources you can inspect','Proposed evaluation • before generating'),
 'clock':('clock','Measure the whole handoff','Generate','Check, correct, accept','Proposed evaluation • not a stopwatch result'),
 'software':('branch','A software claim needs a check','Change or test result','Reproduce the behavior','Proposed evaluation • polished output is not proof'),
 'handoff_question':('document','What can you hand over?','Preparation','What must you still check?','The question behind the jobs headline'),
 'outro':('contrast','Better tools. Same need for judgment.','Useful work','Accountable decisions','Diffusion Daily'),
}

def editorial_assets():
    """Three authored states per relationship: establish, reveal, settle."""
    folder=EP/'edit/editorial';folder.mkdir(parents=True,exist_ok=True)
    fonts={k:ImageFont.truetype('C:/Windows/Fonts/'+name,size) for k,name,size in [('head','arialbd.ttf',65),('body','arial.ttf',49),('small','arial.ttf',26),('large','arialbd.ttf',81)]}
    result=[];jobs=[]
    for name,(kind,title,left,right,foot) in EDITORIAL.items():
        states=[]
        for phase in range(3):
            canvas=Image.new('RGB',(1920,1080),'#F2F1ED');d=ImageDraw.Draw(canvas);ink='#202624';muted='#616C65';accent='#577A91';green='#647B6A'
            d.text((125,125),title,font=fonts['head'],fill=ink)
            d.line((125,1015,440,1015),fill=muted,width=2);d.text((125,1030),foot,font=fonts['small'],fill=muted)
            if name=='assistant_a':
                d.rectangle((200,350,1250,780),outline=ink,width=3)
                d.text((250,420),'Proposed answer',font=fonts['large'],fill=ink)
                if phase>0:d.text((260,650),'A confident conclusion',font=fonts['body'],fill=muted)
                if phase>1:d.text((1410,470),'?',font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',190),fill=accent)
            elif name=='assistant_b':
                d.text((170,360),'Proposed answer',font=fonts['large'],fill=ink)
                if phase>0:
                    d.line((190,510,190,665,650,665),fill=accent,width=5);d.text((730,635),'Source passage',font=fonts['body'],fill=green)
                if phase>1:d.text((730,765),'Limits + next check',font=fonts['body'],fill=ink)
            elif name=='holdout':
                d.rectangle((170,330,720,815),outline=ink,width=3);d.text((210,380),'Known assignment',font=fonts['body'],fill=ink)
                if phase>0:
                    d.line((765,545,1020,545),fill=accent,width=5);d.text((1080,375),'Reference answer',font=fonts['body'],fill=green)
                if phase>1:
                    for y,label in [(490,'Source'),(580,'Date'),(670,'Expected result')]:d.text((1100,y),'✓  '+label,font=fonts['body'],fill=ink)
            elif name=='contract':
                d.rectangle((210,320,1660,830),outline=ink,width=3)
                d.text((260,370),'Illustrative contract review',font=fonts['body'],fill=ink)
                for y,w in [(485,1030),(550,1240),(615,915)]:d.line((270,y,270+w,y),fill='#B8BEB9',width=5)
                if phase>0:d.rectangle((250,520,1560,582),outline=accent,width=4)
                if phase>1:d.text((270,705),'Relevant clause → verify context and uncertainty',font=fonts['body'],fill=green)
            elif name=='uncertainty':
                d.text((170,365),'Supported',font=fonts['body'],fill=ink)
                for x in [180,320,460]:d.rectangle((x,490,x+95,585),fill=green)
                if phase>0:
                    d.text((970,365),'Still needs checking',font=fonts['body'],fill=ink)
                    for x in [980,1120,1260]:d.rectangle((x,490,x+95,585),outline=accent,width=4)
                if phase>1:d.text((175,735),'A stronger score does not fill every gap.',font=fonts['body'],fill=ink)
            elif name=='draft':
                d.rectangle((180,365,810,765),outline=ink,width=4);d.line((180,365,495,575,810,365),fill=ink,width=4)
                d.text((290,660),'Draft',font=fonts['body'],fill=ink)
                if phase>0:d.line((865,560,1100,560),fill=accent,width=5)
                if phase>1:
                    d.line((1170,420,1170,730),fill=green,width=10);d.text((1230,510),'Review',font=fonts['body'],fill=ink);d.text((1230,590),'before send',font=fonts['body'],fill=ink)
            elif name=='review_owner':
                d.text((175,370),'Evidence',font=fonts['large'],fill=ink)
                if phase>0:d.line((590,415,875,415),fill=accent,width=5);d.text((985,370),'Decision',font=fonts['large'],fill=ink)
                if phase>1:
                    d.line((980,670,1640,670),fill=ink,width=2);d.text((985,695),'Named reviewer / accountable owner',font=fonts['small'],fill=green)
            elif name=='training':
                d.text((180,380),'First draft',font=fonts['body'],fill=muted)
                d.line((180,470,760,470),fill='#B8BEB9',width=6)
                if phase>0:d.line((180,445,760,495),fill='#947260',width=4);d.text((190,565),'Corrected reasoning',font=fonts['body'],fill=green)
                if phase>1:d.text((1060,565),'Explain why.',font=fonts['large'],fill=ink)
            elif name=='smalltask':
                d.rectangle((220,350,750,820),outline=ink,width=3);d.text((275,420),'One task',font=fonts['large'],fill=ink)
                if phase>0:d.text((275,625),'Non-sensitive',font=fonts['body'],fill=green)
                if phase>1:
                    d.arc((1040,360,1510,820),40,310,fill=accent,width=8);d.polygon([(1090,410),(1105,520),(1190,450)],fill=accent);d.text((1115,575),'Undo',font=fonts['large'],fill=ink)
            elif name=='change':
                d.text((175,360),'Before',font=fonts['body'],fill=muted);d.text((1040,360),'After',font=fonts['body'],fill=ink)
                for y,w in [(490,490),(570,390),(650,510)]:d.line((180,y,180+w,y),fill='#B8BEB9',width=6)
                if phase>0:
                    for y,w in [(490,490),(570,560),(650,510)]:d.line((1040,y,1040+w,y),fill=green if y==570 else '#B8BEB9',width=6)
                if phase>1:d.text((1040,760),'What changed — and why?',font=fonts['body'],fill=green)
            elif name=='handoff_question':
                d.line((250,535,1650,535),fill=ink,width=6);d.polygon([(950,555),(860,800),(1040,800)],outline=ink,width=5)
                d.text((220,420),'Preparation',font=fonts['body'],fill=green)
                if phase>0:d.text((1150,420),'Judgment',font=fonts['body'],fill=ink)
                if phase>1:d.text((560,860),'What still needs you?',font=fonts['large'],fill=ink)
            elif kind=='equation':
                d.text((155,380),left,font=fonts['large'],fill=ink)
                if phase>0:d.text((170,505),'=' if name=='pp' else '→',font=fonts['large'],fill=accent)
                if phase>1:d.text((155,645),right,font=fonts['large'],fill=green)
            elif kind=='contrast':
                d.text((155,410),left,font=fonts['body'],fill=ink)
                if phase>0:d.text((885,440),'≠',font=fonts['large'],fill=accent)
                if phase>1:d.text((1050,575),right,font=fonts['body'],fill=ink)
            elif kind=='clock':
                d.ellipse((170,330,590,750),outline=ink,width=7);d.line((380,540,380,390),fill=accent,width=8)
                if phase>0:d.line((380,540,515,600),fill=green,width=8)
                d.text((770,390),left,font=fonts['body'],fill=ink)
                if phase>1:d.text((770,580),right,font=fonts['body'],fill=green)
            elif kind=='axes':
                d.line((215,370,215,810,1020,810),fill=ink,width=5)
                d.text((275,845),'X: '+right,font=fonts['body'],fill=ink)
                if phase>0:d.text((285,330),'Y: '+left,font=fonts['body'],fill=ink)
                if phase>1:
                    for x,y in [(360,680),(485,560),(610,615),(740,440),(880,470)]:d.ellipse((x-8,y-8,x+8,y+8),fill=accent)
                    d.text((1220,680),'Illustration only',font=fonts['small'],fill=muted)
            elif kind=='branch':
                d.text((150,460),left,font=fonts['body'],fill=ink)
                if phase>0:d.line((710,490,900,490,900,680,1020,680),fill=accent,width=5)
                if phase>1:d.text((1060,660),right,font=fonts['body'],fill=green)
            else:
                # A single document/proof object rather than a repeated card grid.
                d.rectangle((150,320,810,840),outline=ink,width=3)
                d.text((200,365),left,font=fonts['body'],fill=ink)
                for y,w in [(500,420),(552,480),(604,325)]:d.line((205,y,205+w,y),fill='#B8BEB9',width=5)
                if phase>0:d.line((860,580,1040,580),fill=accent,width=5)
                if phase>1:
                    # Wrapped detail to keep every text block inside title-safe.
                    words=right.split();lines=['']
                    for word in words:
                        test=(lines[-1]+' '+word).strip()
                        if d.textbbox((0,0),test,font=fonts['body'])[2]>675:lines.append(word)
                        else:lines[-1]=test
                    for j,line in enumerate(lines):d.text((1080,480+j*65),line,font=fonts['body'],fill=green)
            path=folder/f'{name}_{phase}.png';save_png_if_changed(canvas,path);states.append(path)
        dest=folder/f'{name}.mp4'
        contract={'state_hashes':[sha(p) for p in states],'state_seconds':[1.5,2,8.5],'frames':360,'fps':30,'crf':18,'renderer_version':2}
        sig=hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest();receipt=dest.with_suffix('.json')
        if not(dest.exists() and receipt.exists() and read(receipt).get('input_hash')==sig):
            # Semantic reveals, locked camera, no ambient movement or source audio.
            command=['ffmpeg','-y','-v','error']
            for path,seconds in zip(states,[1.5,2,8.5]):command+=['-loop','1','-framerate','30','-t',str(seconds),'-i',str(path)]
            command+=['-filter_complex','[0:v][1:v][2:v]concat=n=3:v=1:a=0,format=yuv420p[v]','-map','[v]','-an','-frames:v','360','-c:v','libx264','-preset','veryfast','-crf','18','-threads','2','-movflags','+faststart',str(dest)]
            jobs.append((command,receipt,sig,dest))
        result.append({'asset_id':'editorial_'+name,'path':str(dest),'kind':'motion','source_url':'editorial://astra-jobs/'+name,'relevance':title+'. '+foot,'original_editorial':True,'available_frames':360,'visual_relationship':kind,'evidence_type':'original explanatory commentary, not a product screenshot or empirical result'})
    def export(job):
        command,receipt,sig,dest=job
        subprocess.run(command,check=True,capture_output=True)
        dump(receipt,{'input_hash':sig,'sha256':sha(dest)})
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(export,jobs))
    dump(folder/'ledger.json',result)
    return result

def main():
    editorial_assets()
    table=assets()
    focused=focused_screens()
    timing=EP/'paragraph_timing.json'
    if not timing.exists():
        print('Screens normalized; awaiting caption-aligned paragraph_timing.json');return
    # None means allocate only this paragraph's remainder among these exact
    # relevant source or commentary objects. No search-based fallback or loops.
    plans={
      '01_intro_0':[('finance_prompt_sources',10),('law_identity',4.5),('article_finance_data',None),('article_law_firms',None)],
      '01_intro_1':[('finance_research',329/30),('finance_templates',239/30),('law_filing',11),('screen_finance_pitchbook',None)],
      '01_intro_2':[('screen_finance_citations',None),('screen_finance_value_analysis',None)],
      '02_finance_0':[('screen_finance_source_picker',None),('finance_evidence',11),('article_finance_data',None)],
      '02_finance_1':[('screen_finance_value_analysis',None),('screen_finance_buyer_screening',None),('screen_finance_citations',None)],
      '02_finance_2':[('motion_finance_flow',12),('screen_finance_earnings_analysis',None),('screen_finance_firm_templates',None)],
      '03_model_0':[('screen_finance_lbo_model',None),('screen_finance_lbo_chart',None),('screen_finance_earnings_analysis',None)],
      '03_model_1':[('motion_financial_model',12),('screen_finance_lbo_model',None),('screen_finance_lbo_chart',None)],
      '03_model_2':[('finance_evidence',11),('screen_finance_firm_templates',None),('screen_finance_buyer_screening',None)],
      '04_finance_score_0':[('article_finance_benchmark_source',None),('editorial_treasury',None)],
      '04_finance_score_1':[('motion_finance_benchmark',12),('editorial_pp',None),('editorial_notforecast',None)],
      '04_finance_score_2':[('editorial_holdout',None),('editorial_footnote',None),('editorial_review_time',None)],
      '05_law_0':[('article_law_research',None),('law_prompt',12),('law_plugins',9)],
      '05_law_1':[('article_law_firms',None),('law_filing',11),('editorial_contract',None)],
      '05_law_2':[('motion_law_research',12),('article_law_workflow',None),('article_law_research',None)],
      '06_law_score_0':[('article_law_research_benchmark',7),('motion_law_benchmark',12),('editorial_questions',None)],
      '06_law_score_1':[('article_law_research_benchmark',None),('editorial_noterror',None),('editorial_uncertainty',None)],
      '06_law_score_2':[('editorial_assistant_a',None),('editorial_assistant_b',None),('article_law_workflow',None)],
      '07_other_work_0':[('astra_circuit_pcb',8),('astra_excel_model',8),('astra_unity_scene',7),('astra_science_quality',4)],
      '07_other_work_1':[('astra_qa_navigation',11),('astra_qa_interactions',12),('editorial_checkout',None)],
      '07_other_work_2':[('astra_science_variants',5),('astra_science_quality',4),('editorial_axes',None),('editorial_omissions',None)],
      '08_boundaries_0':[('article_finance_governance',None),('article_law_controls',None),('law_privacy',9)],
      '08_boundaries_1':[('editorial_draft',None),('motion_permission_layers',12),('editorial_send',None)],
      '08_boundaries_2':[('editorial_review_owner',None),('finance_templates',239/30),('editorial_accepted',None)],
      '09_jobs_0':[('article_ilo_title',None),('article_ilo_caveat',None),('motion_automation_boundary',12)],
      '09_jobs_1':[('finance_prompt_sources',10),('motion_job_tasks',12),('editorial_orgsplit',None),('editorial_outcomes',None)],
      '09_jobs_2':[('editorial_training',None),('finance_research',329/30),('editorial_skill',None)],
      '10_close_0':[('editorial_smalltask',None),('editorial_standard',None),('editorial_clock',None)],
      '10_close_1':[('astra_excel_results',3.6),('editorial_claim_source',4.9),('astra_qa_interactions',11.9),('motion_practical_check',12)],
      '10_close_2':[('motion_work_handoff',12),('editorial_handoff_question',None),('editorial_outro',None)],
    }
    by_id={r['id']:r for r in read(timing)};sequence=[];review=[];used=Counter();cursor=0
    for key,beats in plans.items():
        t=by_id[key];start=round(t['start']*30);end=math.ceil(t['end']*30) if key=='10_close_2' else round(t['end']*30)
        assert start==cursor,(key,start,cursor)
        durations=[None if duration is None else round(duration*30) for _,duration in beats]
        remaining=end-start-sum(n or 0 for n in durations);flex=[i for i,n in enumerate(durations) if n is None]
        if not flex:
            # A continuous walking result can absorb its paragraph's fractional
            # remainder without truncating or freezing an action.
            assert key in {'07_other_work_0','10_close_1'};durations[2]+=remaining
        else:
            for n,i in enumerate(flex):durations[i]=remaining//len(flex)+(1 if n<remaining%len(flex) else 0)
        beat_review=[]
        for (asset,_),frames in zip(beats,durations):
            assert asset in table,asset
            a=table[asset];assert 1<=frames<=360,(key,asset,frames/30)
            assert frames<=a.get('available_frames',360),(asset,frames)
            used[asset]+=1;assert used[asset]<=(1 if a['kind']=='motion' else 2),(asset,used[asset])
            row={k:v for k,v in a.items() if k!='available_frames'}
            if used[asset]==2 and asset in focused:
                row['path']=focused[asset];row['relevance']+=' | Second use: readable locked crop of exact original evidence; same canonical asset for repetition accounting.'
            row.update(id=f'{len(sequence)+1:03d}_{asset}',start_frame=cursor,frames=frames,paragraph_ids=[key],narration=t['text'],semantic_basis='Selected for this exact narration paragraph; demonstrations illustrate products, not independently performed tests')
            sequence.append(row);cursor+=frames;beat_review.append({'asset':asset,'seconds':frames/30})
        review.append({'paragraph':key,'start':start/30,'end':end/30,'shots':beat_review})
    dump(EP/'edit_plan.json',sequence)
    categories=Counter()
    for r in sequence:categories['original_editorial' if r.get('original_editorial') else r['kind']]+=r['frames']/30
    dump(EP/'edit/semantic_review.json',{'status':'awaiting independent scene and frame review','duration':cursor/30,'shots':len(sequence),'kind_seconds':dict(categories),'uses':dict(used),'paragraphs':review,'publishing_enabled':False,'decisions':['No apartment, DMV, house or gear imagery under finance/legal tasks','No source audio, background music, subtitles or thumbnail footage','Hypothetical model and evaluation commentary is original explanatory imagery, not fake product UI','Full narration plus1.2 second exit tail retained','No source asset over two uses; each original motion graphic once']})
    print(json.dumps({'duration':cursor/30,'shots':len(sequence),'kind_seconds':dict(categories)},indent=2))

if __name__=='__main__':main()
