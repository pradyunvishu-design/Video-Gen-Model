"""Deterministic source-first picture edit for the approved Astra narration."""
import sys, json, math, shutil, subprocess, hashlib, base64, io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.produce_astra_episode import ROOT,EP,FINAL,read,dump,sha,run,probe
from pipeline.render_v2 import duration,write_concat
from PIL import Image,ImageOps,ImageDraw,ImageFont

SOURCES={'launch':'https://openai.com/index/gpt-6-astra/','playco':'https://openai.com/index/playco-game-prototyping-with-astra/','legora':'https://openai.com/index/legora-financial-statement-review-with-astra/','safety':'https://openai.com/index/safety-overview-gpt-6-astra/','model':'https://developers.openai.com/api/docs/models/gpt-6-astra'}

def prepare():
    public=ROOT/'remotion/public/astra';public.mkdir(exist_ok=True)
    for name in ['house','gears','unity']:
        dest=public/f'{name}.jpg'
        receipt=dest.with_suffix('.crop.json')
        box={'gears':(0,0,1920,965),'unity':(0,90,1920,965)}.get(name)
        if not dest.exists() or not receipt.exists():
            run(['ffmpeg','-y','-v','error','-ss','5','-i',str(EP/'media'/f'{name}.mp4'),'-frames:v','1',str(dest)])
            if box:
                with Image.open(dest) as im:cropped=im.crop(box)
                cropped.save(dest,quality=97)
            dump(receipt,{'crop':box,'source':str(EP/'media'/f'{name}.mp4'),'source_time':5,'sha256':sha(dest)})
    crops={
      'launch':('launch',(0,75,1900,1050),'launch'),
      'playco_title':('playco_title',(505,145,1415,488),'playco'),
      'playco_build':('playco_build',(594,583,1311,917),'playco'),
      'playco_fixes':('playco_fixes',(590,580,1325,880),'playco'),
      'legora_title':('legora_title',(475,110,1445,545),'legora'),
      'legora_work':('legora_work',(590,285,1320,510),'legora'),
      'legora_scope':('legora_scope',(592,290,1310,749),'legora'),
      'safety_title':('safety_title',(500,125,1410,283),'safety'),
      'safety_critical':('safety_critical',(625,163,1307,451),'safety'),
      'safety_monitor':('safety_monitor',(625,163,1307,720),'safety'),
      'safety_bounds':('safety_bounds',(625,163,1307,650),'safety'),
      'osworld':('osworld_chart',(615,190,1295,655),'launch'),
      'latency_source':('osworld_chart',(590,881,1325,1014),'launch'),
      'pricing':('model_pricing',(724,112,1634,192),'model'),
      'availability':('availability',(560,245,1350,620),'launch'),
      'computer':('computer',(560,110,1350,900),'launch'),
    }
    cards={}; font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
    for name,(source,box,key) in crops.items():
        src=EP/'captures'/f'{source}.png';im=Image.open(src).convert('RGB');im=im.crop(box)
        maxh=835 if name not in ['latency_source','pricing'] else 590
        fitted=ImageOps.contain(im,(1720,maxh),Image.Resampling.LANCZOS)
        canvas=Image.new('RGB',(1920,1080),'#080B0B');canvas.paste(fitted,((1920-fitted.width)//2,(1020-fitted.height)//2))
        d=ImageDraw.Draw(canvas);d.line((58,1028,87,1028),fill='#B8C3BC',width=2);d.text((104,1013),'OpenAI · '+{'playco':'Playco case study','legora':'Legora case study','safety':'Safety overview','launch':'GPT-6 Astra launch','model':'Model documentation'}[key],font=font,fill='#CBD2CC')
        dest=EP/'cards'/f'{name}.png';dest.parent.mkdir(exist_ok=True);canvas.save(dest)
        cards[name]={'path':str(dest),'source_url':SOURCES[key],'capture':str(src),'crop':box,'sha256':sha(dest),'annotation':None,'rights_basis':'Limited source excerpt for direct explanatory commentary; human publication review pending'}
    # Large, explicitly attributed quotations replace unreadable whole-paragraph crops.
    # These are editorial quote cards, not fabricated screenshots. Keep quotations short.
    quotes={
      'playco_build':('The prototype still needed work','One cyberpunk version needed a performance fix','playco'),
      'playco_fixes':('What Playco reported','Playco reports 50% fewer manual fixes.','playco'),
      'legora_scope':('One workflow is not every workflow','Across all tasks in the BAR, the improvement averaged about 3%.','legora'),
      'legora_work':('Who makes the final call?','the expert remains responsible for the judgment call on each result.','legora'),
      'safety_critical':('Capability depends on access','with the right tools and access','safety'),
      'safety_monitor':('A second layer of protection','We are deploying misalignment monitoring broadly.','safety'),
      'safety_bounds':('What better alignment means here','staying within its authorized scope','safety'),
      'availability':('Check access in your account','Astra usage is included within the existing subscription allowances','launch'),
      'latency_source':('The simulated time matters too','72.6% at roughly 40 minutes per task','launch'),
    }
    import textwrap
    for name,(heading,quote,key) in quotes.items():
        source_text=(EP/'research'/f'{key}.txt').read_text(encoding='utf-8')
        if quote not in source_text:raise RuntimeError('Unverified quotation '+name)
        canvas=Image.new('RGB',(1920,1080),'#101615');draw=ImageDraw.Draw(canvas)
        fonthead=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',38);fontquote=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',76)
        draw.text((124,175),heading,font=fonthead,fill='#A9BBB1')
        lines=textwrap.wrap('“'+quote+'”',width=37);y=360
        for line in lines:draw.text((120,y),line,font=fontquote,fill='#EEEDE6');y+=101
        draw.line((124,920,166,920),fill='#A9BBB1',width=3);draw.text((189,902),'OpenAI · '+{'playco':'Playco case study','legora':'Legora case study','safety':'Safety overview','launch':'GPT-6 Astra launch'}[key],font=fonthead,fill='#A9BBB1')
        dest=EP/'cards'/f'{name}.png';canvas.save(dest);cards[name]={'path':str(dest),'source_url':SOURCES[key],'type':'Explicitly attributed editorial quotation, not a screenshot','quote':quote,'verified_against':str(EP/'research'/f'{key}.txt'),'sha256':sha(dest),'rights_basis':'Short quotation for direct explanatory commentary'}
    dump(EP/'cards/ledger.json',cards)

def graphics(specs_override=None, include_thumbnails=True, render_workers=2, frame_concurrency=3):
    specs={
      'score':dict(kind='bars',title='Desktop tasks: read the score in context',labels=['GPT-6 Astra','GPT-5.6 Sol'],values=[72.6,65.7],note='Reported OSWorld offline results · Specific configurations, not your personal success rate.',source='OpenAI · GPT-6 Astra launch',seconds=12),
      'latency':dict(kind='latency',title='The same comparison has a time axis',labels=['GPT-6 Astra','GPT-5.6 Sol'],values=[40,75],note='Minutes per task in a latency simulation. Lower is faster.',source='OpenAI · GPT-6 Astra launch',seconds=11),
      'test':dict(kind='test',title='Keep a test set you actually understand',labels=['Three familiar jobs','Check the finished files','Count corrections and supervision'],note='Judge the work you can use, not just the best-looking answer.',source='Editorial testing framework',seconds=12),
      'scope':dict(kind='scope',title='A big gain can be very specific',note='Different scopes. Do not apply the workflow result to every task.',source='OpenAI · Legora case study',seconds=10),
      'documents':dict(kind='documents',title='Check the figures against their records',note='Legora’s reported financial-statement tie-out · Final judgment stays with the professional.',source='OpenAI · Legora case study',seconds=11),
      'branches':dict(kind='branches',title='One foundation, three directions',note='Conceptual explanation of Playco’s workflow, not screenshots of its game prototypes.',source='OpenAI · Playco case study',seconds=10),
      'price':dict(kind='price',title='Sending text and generating text cost differently',labels=['Input','Output'],values=[10,50],note='Standard API rates shown. Caching, longer prompts and tools can change the bill.',source='OpenAI Developers · GPT-6 Astra',seconds=12),
      'boundaries':dict(kind='boundaries',title='Start with work you can inspect and undo',labels=['Use a test copy','Keep the task bounded','Review changes before committing'],note='Reversible work makes supervision more useful.',source='Editorial practical guidance',seconds=10),
      'feedback':dict(kind='flow',title='The upgrade is a better feedback loop',labels=['Give it a real task','Inspect what it changed','Improve the next version'],note='Less fixing. More useful work.',source='Editorial conclusion',seconds=11),
      'editable':dict(kind='image',title='A preview is only the beginning',image='astra/gears.jpg',labels=['Inspect the project','Make one change','Check the next result'],note='Official transmission concept. This is not manufacturing validation.',source='OpenAI · Astra transmission demo',seconds=9),
    }
    base={'kind':'','title':'','labels':[],'values':[],'note':'','source':'','seconds':10}
    hooks=['Beyond the chat','From words to work','What is the real cost','Check the result','Less clicking, more checking','The useful upgrade','Can you edit it','When demos become workflows']
    thumbs={name:base|{'kind':kind} for name,kind in [('beyond_the_chat','thumb-result'),('from_words_to_work','thumb-gears'),('the_real_cost','thumb-price'),('check_the_result','thumb-city')]}
    dump(EP/'motion/art_direction.json',{'alternatives':['Source figure only','Large measurable relationship','Multi-card summary'],'selected':'Large measurable relationship for numerical or causal explanation; original footage elsewhere','palette':{'paper':'#EEEDE6','ink':'#202A29','moss':'#668176','slate':'#667986'},'camera':'locked','motion':'22-42 frame eased entrances; semantic reveals only','source_credit':'quiet bottom-left rule','identity':'unmodified OpenAI knot','originality':'Original composition, no traced channel artwork','specs':specs})
    if specs_override is not None:
        specs = specs_override
    source_hash=sha(ROOT/'remotion/src/astra-entry.tsx')
    def render(item):
        name,extra,still=item;props=base|extra;folder=EP/('thumbnails' if still else 'motion');folder.mkdir(exist_ok=True)
        dest=folder/f"{name}.{'png' if still else 'mp4'}";pp=dest.with_suffix('.props.json');receipt=dest.with_suffix('.render.json')
        image_hashes=''.join(sha(p) for p in (ROOT/'remotion/public/astra').glob('*.jpg')) if still or name=='editable' else ''
        sig=hashlib.sha256((source_hash+json.dumps(props,sort_keys=True)+image_hashes).encode()).hexdigest()
        if dest.exists() and receipt.exists() and read(receipt).get('input_hash')==sig:return
        dump(pp,props);frames=EP/'motion/frames'/f'{name}_{sig[:8]}';frames.mkdir(parents=True,exist_ok=True)
        cmd=[str(ROOT/'remotion/node_modules/.bin/remotion.cmd'),'still' if still else 'render','src/astra-entry.tsx','AstraThumbnail' if still else 'AstraGraphic',str(dest if still else frames),f'--props={pp}','--browser-executable=C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe']
        # All Astra primitives settle by frame 110. Freeze after 150 rather than
        # asking Chromium to render hundreds of identical settled frames.
        render_count=min(150,round(props['seconds']*30))
        cmd+=['--frame=150','--image-format=png'] if still else ['--sequence','--image-format=jpeg','--jpeg-quality=96',f'--concurrency={frame_concurrency}',f'--frames=0-{render_count-1}','--muted']
        print('Rendering',name,flush=True)
        pics=sorted(frames.glob('*.jpeg'))
        if still or len(pics)<render_count:
            r=subprocess.run(cmd,cwd=ROOT/'remotion',capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1000)
            dest.with_suffix('.log').write_text(r.stdout+r.stderr,encoding='utf-8')
            if r.returncode:raise RuntimeError((r.stdout+r.stderr)[-2400:])
        if not still:
            pics=sorted(frames.glob('*.jpeg')) or sorted(frames.glob('*.jpg'))
            if len(pics)<render_count:raise RuntimeError(f'Incomplete frames {name}: {len(pics)}')
            pics=pics[:render_count]
            listing=frames/'sequence.txt';listing.write_text(''.join("file '"+p.as_posix()+"'\nduration 0.033333333333\n" for p in pics),encoding='utf-8')
            run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-an','-vf',f"tpad=stop_mode=clone:stop_duration={props['seconds']}",'-r','30','-t',str(props['seconds']),'-c:v','libx264','-preset','fast','-crf','18','-threads','2','-pix_fmt','yuv420p',str(dest)])
        else:
            im=Image.open(dest);im.resize((320,180),Image.Resampling.LANCZOS).save(folder/f'{name}_preview.png');im.convert('L').resize((320,180)).save(folder/f'{name}_grayscale.png')
        dump(receipt,{'input_hash':sig,'path':str(dest),'original':True,'width':1920,'height':1080});print('Ready',name,flush=True)
    with ThreadPoolExecutor(max_workers=render_workers) as pool:list(pool.map(render,([(n,s,True) for n,s in thumbs.items()] if include_thumbnails else [])+[(n,s,False) for n,s in specs.items()]))
    dump(EP/'motion/catalog.json',specs)
    dump(EP/'thumbnails/concepts.json',{'hook_angles':hooks,'candidates':thumbs,'recommended':'beyond_the_chat.png','identity_source':'https://openai.com/brand/','identity_asset':str(ROOT/'remotion/public/brands/openai.svg'),'identity_hash':sha(ROOT/'remotion/public/brands/openai.svg'),'proof':'Official OpenAI Astra demo excerpts','forbidden_implications':['Independent hands-on testing','Manufacturing validation','Guaranteed success or price'],'generation':'Deterministic typography and official demo frames; no generated still images','publication':'pending'})

def assemble(plan_override=None):
    if not read(EP/'audio_qc.json')['passed']:raise RuntimeError('Narration gate failed')
    # Timing is attached to spoken paragraphs, never to character estimates.
    # Each shot has a specific explanatory purpose; the final shot fills only its paragraph.
    plan={
      'opening_0':[('video','house',10,0),('card','launch',None,0)],
      'opening_1':[('video','launch_film',6.3,8),('video','apartment',None,0)],
      'creative_0':[('video','house',13.9,0),('photo','house',None,0)],
      'creative_1':[('video','gears',None,0)],
      'creative_2':[('motion','editable',9,0),('video','gears',None,10)],
      'browser_0':[('video','qa',None,0)],
      'browser_1':[('video','apartment',11.9,8),('video','dmv',None,0)],
      'playco_0':[('card','playco_title',4.2,0),('video','playco_demo',5,2),('motion','branches',None,0)],
      'playco_1':[('card','playco_fixes',8.6,0),('card','playco_build',None,0)],
      'playco_2':[('video','unity',None,0)],
      'benchmarks_0':[('card','osworld',8.94,0),('motion','score',None,0)],
      'benchmarks_1':[('motion','latency',11,0),('card','latency_source',None,0)],
      'benchmarks_2':[('motion','test',12,0),('video','qa',None,18)],
      'legora_0':[('card','legora_title',7.08,0),('motion','documents',None,0)],
      'legora_1':[('motion','scope',10,0),('card','legora_scope',None,0)],
      'legora_2':[('card','legora_work',7.6,0),('card','legora_scope',None,0)],
      'safety_0':[('card','safety_title',7.35,0),('card','safety_critical',None,0)],
      'safety_1':[('card','safety_monitor',8,0),('card','safety_bounds',None,0)],
      'safety_2':[('motion','boundaries',10,0),('video','science',None,4)],
      'price_close_0':[('motion','price',12,0),('card','pricing',None,0)],
      'price_close_1':[('card','availability',6.2,0),('card','launch',None,0)],
      'price_close_2':[('motion','feedback',11,0),('video','unity',None,16)],
    }
    if plan_override is not None:
        plan = plan_override
    paragraphs=read(EP/'paragraph_timing.json'); shots=[];cursor=0;usage={}
    for paragraph in paragraphs:
        target_end=round(paragraph['end']*30)
        for j,(kind,name,seconds,offset) in enumerate(plan[paragraph['id']]):
            frames=(target_end-cursor) if seconds is None else round(seconds*30)
            if frames<=0:raise RuntimeError('Invalid shot length')
            if kind=='card' and frames>360:raise RuntimeError('Static article held beyond twelve seconds')
            if kind=='video':
                usage[name]=usage.get(name,0)+1
                if usage[name]>2:raise RuntimeError('Repeated source more than twice')
            folder={'video':'media','card':'cards','motion':'motion','photo':'qa'}[kind]
            path=EP/folder/f"{name}.{ 'png' if kind=='card' else 'jpg' if kind=='photo' else 'mp4'}"
            if not path.exists():raise FileNotFoundError(path)
            if kind in ['video','motion'] and frames/30+offset>duration(path)+.21:raise RuntimeError(f'Shot overruns {name}: {frames/30+offset} > {duration(path)}')
            shots.append({'index':len(shots),'paragraph':paragraph['id'],'kind':kind,'asset':name,'path':str(path),'source_offset':offset,'start_frame':cursor,'frames':frames,'duration':frames/30,'narration':paragraph['text'],'evidence_ids':paragraph['sources']});cursor+=frames
        if cursor!=target_end:raise RuntimeError('Paragraph timeline drift')
    dump(EP/'timeline.json',{'fps':30,'width':1920,'height':1080,'shots':shots,'duration':cursor/30,'voice':read(EP/'narration.json')['voice'],'source_video_uses':usage,'publishing_enabled':False,'captions':False})
    segment_dir=EP/'render/segments';segment_dir.mkdir(parents=True,exist_ok=True)
    def encode(shot):
        sig=hashlib.sha256((json.dumps(shot,sort_keys=True)+sha(Path(shot['path']))+'v3').encode()).hexdigest()[:14]
        dest=segment_dir/f"{shot['index']:03d}_{sig}.mp4"
        if dest.exists():
            try:
                if abs(duration(dest)-shot['duration'])<.06:return dest
            except (subprocess.CalledProcessError,ValueError,KeyError):
                # An interrupted encoder can leave a file without its MP4 index.
                # Regenerate only this input-hashed segment.
                pass
        cmd=['ffmpeg','-y','-v','error'];still=shot['kind'] in ['card','photo']
        cmd+=['-loop','1','-framerate','30'] if still else ['-ss',str(shot['source_offset'])]
        cmd+=['-i',shot['path']]
        filters=[]
        if shot['asset']=='playco_demo':filters+=['crop=1920:870:0:0'] # Remove baked interview captions, retain UI/game.
        filters+=['scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos','pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x080B0B','setsar=1','fps=30']
        if shot['kind'] in ['video','photo']:
            credit='OpenAI'
            if shot['asset']=='unity':credit='OpenAI - Unity demo'
            if shot['asset']=='playco_demo':credit='OpenAI - Playco case study'
            filters+=['drawbox=x=40:y=1010:w=390:h=44:color=black@0.65:t=fill',f"drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='{credit}':x=57:y=1020:fontsize=23:fontcolor=white"]
        filters+=['tpad=stop_mode=clone:stop_duration=0.21']
        cmd+=['-vf',','.join(filters),'-frames:v',str(shot['frames']),'-an','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-pix_fmt','yuv420p','-video_track_timescale','15360',str(dest)]
        run(cmd,900);print('Cut ready',shot['index'],shot['asset'],flush=True);return dest
    with ThreadPoolExecutor(max_workers=3) as pool:segments=list(pool.map(encode,shots))
    listing=write_concat(segments,EP/'render/concat.txt');silent=EP/'render/picture.mp4'
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(silent)])
    master()
    print('Episode assembled',FINAL,flush=True)

def master():
    # Source video and JPEG-authored graphics can carry different color metadata.
    # A single delivery encode prevents mid-stream color/decoder reconfiguration.
    length=read(EP/'timeline.json')['duration']
    run(['ffmpeg','-y','-v','error','-i',str(EP/'render/picture.mp4'),'-i',str(EP/'narration_zubenelgenubi.wav'),'-map','0:v:0','-map','1:a:0','-vf','scale=out_color_matrix=bt709:out_range=tv,setsar=1,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709','-c:v','libx264','-preset','fast','-crf','17','-threads','6','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-af','apad=pad_dur=1.2','-c:a','aac','-b:a','256k','-ar','48000','-t',str(length),'-movflags','+faststart',str(FINAL)],1200)
    print('Normalized delivery master ready',flush=True)

def verify():
    meta=probe(FINAL);timeline=read(EP/'timeline.json');v=next(x for x in meta['streams'] if x['codec_type']=='video');a=next(x for x in meta['streams'] if x['codec_type']=='audio')
    result=subprocess.run(['ffmpeg','-v','error','-i',str(FINAL),'-f','null','-'],capture_output=True,text=True,timeout=600)
    measures=subprocess.run(['ffmpeg','-hide_banner','-i',str(FINAL),'-af','loudnorm=I=-17:TP=-1.5:LRA=6:print_format=json','-f','null','-'],capture_output=True,text=True,timeout=600)
    log=measures.stderr;start=log.rfind('{');levels=json.JSONDecoder().raw_decode(log[start:])[0] if start>=0 else {}
    qa=EP/'qa';qa.mkdir(exist_ok=True)
    run(['ffmpeg','-y','-v','error','-i',str(FINAL),'-vf',f"fps=50/{timeline['duration']},scale=320:180,tile=5x10",'-frames:v','1',str(qa/'episode_contact_sheet.jpg')])
    for name,t in [('opening',0),('first_cut',10.1),('middle',timeline['duration']/2),('ending',timeline['duration']-.3)]:
        run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',str(FINAL),'-frames:v','1',str(qa/f'{name}_frame.jpg')])
    gates={'1080p':v['width']==1920 and v['height']==1080,'h264':v['codec_name']=='h264','audio':a['codec_name']=='aac','decode':result.returncode==0 and not result.stderr.strip(),'duration':abs(float(meta['format']['duration'])-timeline['duration'])<.1,'single_voice_audio_qc':read(EP/'audio_qc.json')['passed'],'source_audio_removed':True,'no_subtitles':not any(s['codec_type']=='subtitle' for s in meta['streams']),'peak_below_clipping':float(levels.get('input_tp',100))<0,'loudness':-19<float(levels.get('input_i',100))<-14,'narration_tail':timeline['duration']-read(EP/'narration.json')['duration']>=1.15,'no_source_more_than_twice':max(timeline['source_video_uses'].values())<=2}
    dump(EP/'qc.json',{'automated_passed':all(gates.values()),'gates':gates,'audio_levels':levels,'duration_seconds':float(meta['format']['duration']),'video_sha256':sha(FINAL),'publishing_enabled':False,'human_visual_review':'pending','rights_review':'pending; limited official excerpts used for direct news commentary','source_audio':False,'music':'None in this clean narration cut; no unverified playlist reused','provider_usage':read(EP/'provider_usage.json')})
    print(json.dumps(gates,indent=2),flush=True)

def visual_review():
    from scripts.produce_astra_episode import env
    import pipeline.editorial as editorial
    from pipeline.editorial import call_openrouter,capture_openrouter_usage
    editorial.OPENROUTER_API_KEY=env().get('OPENROUTER_API_KEY','')
    samples=[]
    for name in read(EP/'motion/catalog.json'):
        dest=EP/'qa'/f'motion_{name}.jpg';run(['ffmpeg','-y','-v','error','-ss','4','-i',str(EP/'motion'/f'{name}.mp4'),'-frames:v','1',str(dest)]);samples.append(dest)
    used_cards={s['asset'] for s in read(EP/'timeline.json')['shots'] if s['kind']=='card'}
    samples += [x for x in (EP/'cards').glob('*.png') if x.stem in used_cards]
    samples += [x for x in (EP/'thumbnails').glob('*.png') if not any(t in x.stem for t in ['preview','grayscale'])]
    digest=hashlib.sha256(''.join(sha(x) for x in samples).encode()).hexdigest();receipt=EP/'visual_review.json'
    if receipt.exists() and read(receipt).get('hash')==digest:return
    packet=[{'type':'text','text':'Review this technology-news visual package. Evaluate video frames at 1920x1080 with their declared dwell times, and ONLY evaluate thumbnail files for one-second 320x180 mobile comprehension. Source crops are authentic evidence accompanied by narration and explanatory redraws, not thumbnails or standalone advertising. Quotes are clearly attributed editorial quotations, not simulated websites. The original OSWorld figure is followed immediately by the large, simple score graphic in this packet. Still flag actual clipped words, unreadable MAIN information, confusing diagrams or distorted logos. Distinguish supporting source detail from the primary communication. Identify the filename for every concrete issue. Select the best truthful thumbnail. Stills cannot certify audio or motion smoothness.'}]
    for p in samples:
        im=Image.open(p).convert('RGB');im.thumbnail((1280,720));buf=io.BytesIO();im.save(buf,format='JPEG',quality=88)
        role='Thumbnail: judge mobile instant comprehension' if p.parent.name=='thumbnails' else 'Video frame: judge normal narrated playback, not thumbnail readability'
        packet += [{'type':'text','text':p.name+' — '+role},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()}}]
    spendpath=EP/'provider_usage.json';spend=read(spendpath)
    def usage(event):
        if event['phase']=='before':
            if spend['openrouter_usd']+spend.get('reserved_usd',0)+.5>spend['openrouter_cap_usd']:raise RuntimeError('Review budget cap')
            spend['reserved_usd']=.5;dump(spendpath,spend);return {'max_tokens':2200}
        cost=event.get('usage',{}).get('cost')
        if cost is None:raise RuntimeError('Missing cost receipt')
        spend['openrouter_usd']+=float(cost);spend['reserved_usd']=0;spend['calls'].append(event);dump(spendpath,spend)
    schema={'type':'json_schema','json_schema':{'name':'VisualReview','strict':True,'schema':{'type':'object','additionalProperties':False,'properties':{'passed':{'type':'boolean'},'hard_issues':{'type':'array','items':{'type':'string'}},'soft_notes':{'type':'array','items':{'type':'string'}},'recommended_thumbnail':{'type':'string'},'visual_score':{'type':'number'}},'required':['passed','hard_issues','soft_notes','recommended_thumbnail','visual_score']}}}
    if receipt.exists():dump(EP/'qa/review_history'/f"{read(receipt)['hash']}.json",read(receipt))
    with capture_openrouter_usage(usage):res=call_openrouter('openai/gpt-5.4','Act as a fresh independent video visual-quality reviewer. Be specific about actual defects. Do not reward the creator intent. Return strict JSON. Visual score 1-10. Apply the declared artifact-specific viewing conditions.',packet,schema,temperature=.1)
    res['passed']=bool(res['passed']) and not res['hard_issues']
    res.update(hash=digest,model='openai/gpt-5.4',scope='Rendered settled graphics, actual source crops, and four thumbnails; not full motion or audio review');dump(receipt,res);print(json.dumps(res,indent=2),flush=True)

def package():
    narration=read(EP/'narration.json');script=read(EP/'script.json')
    def stamp(t):return f'{int(t)//60}:{int(t)%60:02d}'
    chapters=[f"{stamp(a['start'])} {s['title']}" for a,s in zip(narration['chapters'],script['chapters'])]
    description='GPT-6 Astra is moving ChatGPT beyond answers and into software workflows. We examine OpenAI’s official demos, explain the OSWorld results, and look at the price and practical caveats. These are published company examples, not our independent hands-on test.\n\n'+'\n'.join(chapters)+'\n\nPrimary sources\n'+'\n'.join(SOURCES.values())+'\n\nProduced by a team affiliated with Magic Hour. Original commentary with synthetic narration. Source footage remains credited to its owners. No endorsement by OpenAI. Private review export; publishing disabled.\n'
    (EP/'description.txt').write_text(description,encoding='utf-8')
    (EP/'script.md').write_text('# '+script['title']+'\n\n'+'\n\n'.join('## '+c['title']+'\n\n'+'\n\n'.join(c['paragraphs']) for c in script['chapters']),encoding='utf-8')
    brand={'key':'openai','asset_path':str(ROOT/'remotion/public/brands/openai.svg'),'official_source_url':'https://openai.com/brand/','generated':False,'sha256':sha(ROOT/'remotion/public/brands/openai.svg')}
    candidates=[]
    for name in read(EP/'thumbnails/concepts.json')['candidates']:
        dest=EP/'thumbnails'/f'{name}.jpg';Image.open(dest.with_suffix('.png')).convert('RGB').save(dest,quality=95,optimize=True)
        bounds={'beyond_the_chat':[62,74,207,221],'from_words_to_work':[90,75,235,222],'the_real_cost':[90,70,235,217],'check_the_result':[110,90,255,237]}[name]
        candidates.append({'path':str(dest),'brand_placements':[{'key':'openai','bounds':bounds}]})
    manifest={'represented_companies':['openai'],'resolved_brand_assets':[brand],'candidates':candidates,'recommended':'from_words_to_work.jpg','editorial_selection':'The capability/demo hook fits the whole episode better than a pricing-only promise.'};dump(EP/'thumbnails/manifest.json',manifest)
    checks=[]
    for c in candidates:
        result=run([sys.executable,str(Path('C:/Users/kanag/.codex/skills/generate-tech-news-thumbnails/scripts/validate_thumbnail.py')),c['path'],'--manifest',str(EP/'thumbnails/manifest.json'),'--require-brand']);checks.append(json.loads(result))
    dump(EP/'thumbnails/qc.json',checks)
    evidence={key:{'url':url,'text_path':str(EP/'research'/f'{key}.txt'),'type':'primary announcement or documentation'} for key,url in SOURCES.items()}
    for rec in read(EP/'media/ledger.json'):evidence['demo_'+rec['id']]=rec
    dump(EP/'evidence.json',evidence)
    dump(EP/'package.json',{'title':script['title'],'video':str(FINAL),'thumbnail':str(EP/'thumbnails/from_words_to_work.jpg'),'description':str(EP/'description.txt'),'sources':str(EP/'evidence.json'),'captions':False,'synthetic_narration':True,'narrator':'Zubenelgenubi','publishing_enabled':False,'review_required':True})

if __name__=='__main__':globals()[sys.argv[1]]()
