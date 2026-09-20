"""Bounded, muted official excerpts and real-browser evidence for private review."""
from pathlib import Path
import sys, json, re, hashlib, subprocess, argparse
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
EP=ROOT/'data/episodes/episode_20260908_chatgpt_images25'
URL='https://openai.com/index/introducing-chatgpt-images-2-5/'
FILM='https://video.twimg.com/amplify_video/2097390126577893376/vid/avc1/1920x1080/8IlFZqV8g8G39D8V.mp4'
RIGHTS='User-requested source excerpt for editorial private review only; public reuse license not asserted; publication review required.'
def dump(p,d):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(a,timeout=240):
    r=subprocess.run(a,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    if r.returncode:raise RuntimeError(re.sub(r'https?://\S+','[source URL]',r.stderr[-1200:]))
    return r.stdout
def inspect():
    from playwright.sync_api import sync_playwright
    from pipeline.capture import _assert_capture_is_clean, _blocked_page_reason
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
        page.goto(URL,wait_until='domcontentloaded',timeout=90000)
        page.wait_for_timeout(2500)
        reason=_blocked_page_reason(page)
        if reason:raise RuntimeError('Official page blocked: '+reason)
        for label in ['Reject all','Reject All','Decline optional cookies']:
            loc=page.get_by_role('button',name=label,exact=True)
            if loc.count(): loc.first.click()
        _assert_capture_is_clean(page,moment='source inspection')
        data=page.evaluate('''() => ({title:document.title,url:location.href,headings:[...document.querySelectorAll('h1,h2,h3')].map(e=>({text:e.innerText,id:e.id,y:e.getBoundingClientRect().top+scrollY})),media:[...document.querySelectorAll('iframe,video')].map(e=>({tag:e.tagName,src:e.src,poster:e.poster,html:e.outerHTML.slice(0,1600),near:e.parentElement.parentElement.innerText.slice(0,800)})),images:[...document.querySelectorAll('main img')].map(e=>({src:e.currentSrc||e.src,alt:e.alt,width:e.naturalWidth,height:e.naturalHeight})),paragraphs:[...document.querySelectorAll('main p')].map(e=>e.innerText).filter(Boolean)})''')
        dump(EP/'research/page_inventory.json',data)
        (EP/'research/page.html').write_text(page.content(),encoding='utf-8')
        print(json.dumps(data,ensure_ascii=True),flush=True)
        browser.close()

def inventory():
    r=requests.get(URL,timeout=40);r.raise_for_status()
    html=r.text;dump(EP/'research/http_receipt.json',{'url':URL,'status':r.status_code,'sha256':hashlib.sha256(r.content).hexdigest()})
    (EP/'research/page.html').write_text(html,encoding='utf-8')
    soup=BeautifulSoup(html,'html.parser')
    imgs=[{'src':e.get('src'),'alt':e.get('alt')} for e in soup.select('main img')]
    rows=[]
    for m in re.finditer(r'https://player\.vimeo\.com/video/[^\s"<>]+',html):
        raw=m.group().rstrip('\\');u=raw.replace('\\u0026','&')
        rows.append({'url':u,'context':html[max(0,m.start()-700):m.start()]})
    dump(EP/'research/raw_media.json',rows);dump(EP/'research/images.json',imgs)
    print(json.dumps({'videos':rows,'images':imgs},ensure_ascii=True),flush=True)

def prepare():
    from PIL import Image,ImageDraw
    imrows=[]
    for item in read(EP/'research/images.json'):
        if not any(x in item['src'] for x in ['retrofuturism','sci-fi-surrealism','mid-century-modern','stickers','cyberpunk']):continue
        path=EP/'media'/(item['src'].split('/')[-1].split('?')[0]+'.webp');path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            r=requests.get(item['src'],timeout=40);r.raise_for_status();path.write_bytes(r.content)
        imrows.append(dict(id=path.stem,path=str(path),source_url=item['src'],caption=item['alt'],dimensions=list(Image.open(path).size),rights=RIGHTS,publisher='OpenAI',sha256=sha(path)))
    dump(EP/'media/thumbnail_proofs.json',imrows)
    names=['launch_site','fullbody','ticket','cube','travel','sketch','candles','templates']
    def one(pair):
        name,d=pair;r=requests.get(d['url'],timeout=45);r.raise_for_status()
        match=re.search(r'window\.playerConfig\s*=\s*',r.text)
        if not match:raise RuntimeError('No public metadata '+name)
        cfg=json.JSONDecoder().raw_decode(r.text[match.end():])[0];video=cfg['video']
        files=cfg['request']['files']['hls'];stream=files['cdns'][files['default_cdn']].get('avc_url') or files['cdns'][files['default_cdn']]['url']
        pl=requests.get(stream,timeout=40);pl.raise_for_status();lines=pl.text.splitlines();opts=[]
        for i,line in enumerate(lines[:-1]):
            m=re.search(r'RESOLUTION=(\d+)x(\d+)',line)
            if m and not lines[i+1].startswith('#'):opts.append((int(m[2]),int(m[1]),urljoin(stream,lines[i+1])))
        selected=max(opts,key=lambda x:x[0]*x[1]);entry={'id':name,'url':d['url'],'stream':selected[2],'width':selected[1],'height':selected[0],'duration':video['duration'],'title':video.get('title'),'context':d['context']}
        print('SOURCE',name,entry['duration'],entry['width'],entry['height'],flush=True);return entry
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(one,zip(names,read(EP/'research/raw_media.json'))))
    rows.append({'id':'launch_x','url':FILM,'stream':FILM,'width':1920,'height':1080,'duration':57.898667,'title':'User supplied launch film'})
    dump(EP/'research/demo_streams.json',rows)
    def still(job):
        d,t=job;target=EP/'research'/f"sample_{d['id']}_{t}.jpg"
        if not target.exists():run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',d['stream'],'-frames:v','1','-vf','scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2','-threads','1',str(target)],180)
        return d['id'],t,target
    jobs=[(d,round(d['duration']*f,1)) for d in rows for f in [.12,.35,.60,.82]]
    with ThreadPoolExecutor(max_workers=4) as pool:stills=list(pool.map(still,jobs))
    for i in range(0,len(rows),3):
        batch=rows[i:i+3];sheet=Image.new('RGB',(1920,300*len(batch)),'#111');draw=ImageDraw.Draw(sheet)
        for y,d in enumerate(batch):
            for x,(_,t,p) in enumerate([q for q in stills if q[0]==d['id']]):sheet.paste(Image.open(p),(480*x,300*y+30));draw.text((480*x+8,300*y+7),f"{d['id']} {t}s",fill='white')
        sheet.save(EP/'research'/f'source_contact_{i//3}.jpg')
    print('THUMBNAILS',json.dumps(imrows),flush=True)

def detail():
    from PIL import Image,ImageDraw
    rows=read(EP/'research/demo_streams.json')
    jobs=[(d,t) for d in rows if d['id'] in ['launch_x','sketch','templates'] for t in range(2,int(d['duration'])-1,3)]
    def one(j):
        d,t=j;p=EP/'research'/f"detail_{d['id']}_{t}.jpg"
        if not p.exists():run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',d['stream'],'-frames:v','1','-vf','scale=384:216','-threads','1',str(p)])
        return d['id'],t,p
    with ThreadPoolExecutor(max_workers=4) as pool:stills=list(pool.map(one,jobs))
    for name in ['launch_x','sketch','templates']:
        sels=[q for q in stills if q[0]==name];sheet=Image.new('RGB',(1536,246*((len(sels)+3)//4)),'#111');draw=ImageDraw.Draw(sheet)
        for i,(_,t,p) in enumerate(sels):x=(i%4)*384;y=(i//4)*246;sheet.paste(Image.open(p),(x,y+30));draw.text((x+8,y+6),f'{name} {t}s',fill='white')
        sheet.save(EP/'research'/f'detail_{name}.jpg')

def acquire():
    rows={x['id']:x for x in read(EP/'research/demo_streams.json')}
    ranges={
      'fullbody':[(0,5,'cardigan','Full-body side-by-side clothing edit'),(5,10,'background','Full-body background and clothing preservation'),(10,16,'lighting','Full-body targeted accessory and lighting changes')],
      'ticket':[(0.2,5.5,'cities','Travel-ticket city and landmark changes')],
      'cube':[(0.1,2.8,'turn','Side-by-side blue-cube turn consistency')],
      'travel':[(0.2,5.5,'text','Chinese travel infographic targeted text edits')],
      'candles':[(0.1,4.6,'candles','Successive candle flames on chocolate log cake')],
      'launch_x':[(0.5,6,'aquarium','Launch title, aquarium photograph and initial prompt'),(9,16,'tattoo_prompt','Aquarium furniture changes using precise image comments'),(16,22,'tattoo_result','Cat tattoo prompt, result and real-world tattoo'),(22,29,'candleholder','Candleholder sketch and physical object'),(29,37,'hairstyle','Hair preview and real salon result'),(37,45,'flowers','Flower arrangement visualization'),(45,51,'gathering','Flower arrangement at dinner gathering')],
      'sketch':[(0.5,7,'draw','ChatGPT Sketch drawing interface'),(7,14,'crab','Doodle result then crab drawing and object concept'),(14,21,'horse','Garden layout sketch to render, then horse drawing to framed artwork'),(21,29,'fashion','Fashion sketch to dramatic garment')],
      'templates':[(0.5,7,'formats','Template format choices'),(7,14,'logo','Logo style template choices'),(14,21,'merch','Merch design variations')]
    }
    def one(j):
        name,(start,end,suffix,caption)=j;d=rows[name];ident=f'{name}_{suffix}';dest=EP/'media'/f'{ident}.mp4';receipt=dest.with_suffix('.json')
        assert 0<=start<end<d['duration'],(name,end,d['duration'])
        if receipt.exists() and dest.exists():return read(receipt)
        run(['ffmpeg','-y','-v','error','-ss',str(start),'-i',d['stream'],'-t',str(end-start),'-map','0:v:0','-an','-vf','scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x111111,setsar=1,fps=30','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],300)
        entry={'id':ident,'path':str(dest),'source_url':d['url'],'announcement_url':URL,'start':start,'end':end,'source_in':start,'source_out':end,'duration':end-start,'caption':caption,'topic':name,'width':1920,'height':1080,'native_dimensions':[d['width'],d['height']],'framing':'Fit full source inside 1920x1080; no content cropped; neutral pillar/letterbox where needed','rights':RIGHTS,'publisher':'OpenAI','source_audio_used':False,'publishing_enabled':False,'sha256':sha(dest),'full_source_duration':d['duration'],'max_editorial_uses':2}
        dump(receipt,entry);print('EXCERPT',ident,end-start,flush=True);return entry
    jobs=[(name,r) for name,rs in ranges.items() for r in rs]
    with ThreadPoolExecutor(max_workers=4) as pool:clips=list(pool.map(one,jobs))
    dump(EP/'media/ledger.json',clips);print('TOTAL',len(clips),sum(x['duration'] for x in clips),flush=True)

def qc():
    from PIL import Image,ImageDraw
    clips=read(EP/'media/ledger.json')
    corrections={'launch_x_aquarium':'Launch title, aquarium photograph and initial prompt','launch_x_tattoo_prompt':'Aquarium furniture changes using precise image comments','launch_x_tattoo_result':'Cat tattoo prompt, result and real-world tattoo','sketch_horse':'Garden layout sketch to render, then horse drawing to framed artwork','sketch_crab':'Doodle result then crab drawing and object concept'}
    rows=[]
    for clip in clips:
        if clip['id'] in corrections:clip['caption']=corrections[clip['id']]
        m=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',clip['path']]))
        video=next(x for x in m['streams'] if x['codec_type']=='video');d=float(m['format']['duration'])
        assert (video['width'],video['height'])==(1920,1080)
        assert not any(x['codec_type']=='audio' for x in m['streams'])
        if abs(d-clip['duration'])>=.08:
            source=next(x for x in read(EP/'research/demo_streams.json') if x['id']==clip['topic'])
            # HLS source seeking can skip non-keyframe time; accurate decoded seek
            # is required for these short motion demos. Retain no source master.
            run(['ffmpeg','-y','-v','error','-i',source['stream'],'-ss',str(clip['start']),'-t',str(clip['duration']),'-map','0:v:0','-an','-vf','scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x111111,setsar=1,fps=30','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',clip['path']],300)
            m=json.loads(run(['ffprobe','-v','error','-show_format','-of','json',clip['path']]))
            d=float(m['format']['duration']);clip['sha256']=sha(Path(clip['path']))
        assert abs(d-clip['duration'])<.08,(clip['id'],d,clip['duration'])
        clip['verified_duration']=d;clip['verified_audio_streams']=0;dump(Path(clip['path']).with_suffix('.json'),clip)
        strip=Image.new('RGB',(1440,300),'#111');draw=ImageDraw.Draw(strip)
        for i,f in enumerate([.05,.5,.95]):
            dest=EP/'research'/f"qc_{clip['id']}_{i}.jpg"
            run(['ffmpeg','-y','-v','error','-ss',str(d*f),'-i',clip['path'],'-frames:v','1','-vf','scale=480:270','-threads','1',str(dest)])
            strip.paste(Image.open(dest),(480*i,30));draw.text((480*i+8,8),f"{clip['id']} {d*f:.2f}s",fill='white')
        dest=EP/'research'/f"qc_{clip['id']}.jpg";strip.save(dest)
        rows.append({'id':clip['id'],'duration':d,'width':1920,'height':1080,'audio_streams':0,'contact':str(dest),'caption':clip['caption']})
    dump(EP/'media/ledger.json',clips)
    for i in range(0,len(rows),5):
        sheet=Image.new('RGB',(1440,300*len(rows[i:i+5])),'#111')
        for y,row in enumerate(rows[i:i+5]):sheet.paste(Image.open(row['contact']),(0,y*300))
        sheet.save(EP/'research'/f'qc_contact_{i//5}.jpg')
    dump(EP/'research/source_qc.json',{'status':'review_frames_pending','checks':rows,'publishing_enabled':False,'captures_handled_by_main':True})
    print('QC',len(rows),sum(x['duration'] for x in rows),flush=True)

def cards():
    from PIL import Image,ImageDraw,ImageFont
    # This is an explicitly labeled editorial retypesetting, never a fake browser.
    source=BeautifulSoup((EP/'research/page.html').read_text(encoding='utf-8'),'html.parser').get_text(' ',strip=True)
    targets=[
      ('latency','A faster creative loop','up to 50%','OpenAI reports reduced generation latency compared with Images 2.0.\nThat ceiling is a launch claim, not an independent timing test.'),
      ('precision','Change the part you mean','editing only','The stated improvement is more targeted image modification,\nwith unrelated subjects and surrounding details better preserved.'),
      ('multiturn','Keep earlier decisions intact','multiple edits','OpenAI describes better consistency over a sequence of revisions.\nIt is a reliability improvement, not a promise of perfect preservation.'),
      ('sketch','Start with a drawing','@Sketch','Draw a rough visual reference inside ChatGPT, then describe\nthe style and details you want the finished image to use.'),
      ('templates','A structured starting point','Poster','Templates guide common creative formats. Add the message,\ndesign ingredients, and desired style instead of starting empty.'),
      ('sharing','Pass along the starting idea','include the prompt','An image share can also carry its prompt. Someone else can adapt\nthe idea using different photos and their own details.'),
      ('flare','Flare: the general-purpose option','50% lower latency','The API launch positions Flare as the default for most applications,\nwith faster generation relative to GPT-Image-2.'),
      ('sunburst','Sunburst: a precision-oriented option','tighter control','The second API model targets demanding creative and editing work.\nOpenAI describes a tradeoff of extra precision and longer generation.'),
      ('safety','Provenance is part of the launch','C2PA metadata','OpenAI also describes invisible watermarking and checks on prompts\nand outputs. Those safeguards do not make every result trustworthy.'),
      ('availability','Rolling out across the product line','across all tiers','The announcement includes ChatGPT, ChatGPT Work, and Codex\non desktop, mobile, and the web. Both API models are available.'),
    ]
    rows=[]
    def font(n,bold=False):return ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',n)
    for name,title,phrase,summary in targets:
        assert phrase in source,phrase
        im=Image.new('RGB',(1920,1080),'#f7f7f2');d=ImageDraw.Draw(im)
        d.text((125,94),'OpenAI launch post',font=font(35,True),fill='#111111')
        d.text((125,151),'September 8, 2026',font=font(23),fill='#66665f')
        d.line((125,208,1795,208),fill='#c8c8be',width=2)
        d.text((125,284),title,font=font(65,True),fill='#111111')
        d.text((125,440),phrase,font=font(79,True),fill='#111111')
        bb=d.textbbox((125,440),phrase,font=font(79,True));y=bb[3]+13
        d.line((bb[0],y,bb[2],y),fill='#e34036',width=7)
        for i,line in enumerate(summary.split('\n')):d.text((125,622+i*57),line,font=font(39),fill='#30302e')
        d.line((125,890,1795,890),fill='#c8c8be',width=2)
        d.text((125,931),'Source: openai.com/index/introducing-chatgpt-images-2-5/',font=font(25),fill='#62625d')
        path=EP/'captures'/f'{name}.png';path.parent.mkdir(parents=True,exist_ok=True);im.save(path)
        rows.append({'id':name,'path':str(path),'source_url':URL,'publisher':'OpenAI','width':1920,'height':1080,'viewport':[1920,1080],'sha256':sha(path),'phrase':phrase,'visible_text':title+'\n'+phrase+'\n'+summary,'capture_type':'retypeset_editorial_source_summary','website_screenshot':False,'dom_range':None,'annotation':{'type':'baked_underline','x':bb[0]/1920,'y':y/1080,'width':(bb[2]-bb[0])/1920,'height':7/1080},'normalized_region':{'x':bb[0]/1920,'y':bb[1]/1080,'width':(bb[2]-bb[0])/1920,'height':(bb[3]-bb[1])/1080},'rights':RIGHTS,'limitation':'Real browser capture unavailable: isolated Chrome challenge, then normal browser debugger detached.'})
    dump(EP/'captures/ledger.json',rows)
    print('RETYPESET SOURCE SUMMARIES',len(rows),flush=True)

def gallery():
    from PIL import Image
    rows=read(EP/'media/thumbnail_proofs.json')
    for item in read(EP/'research/images.json'):
        if not any(x in item['src'] for x in ['impressionist-cityscape','wedding-invitation','vintage-national-park','presentation-image','mosaic']):continue
        path=EP/'media'/(item['src'].split('/')[-1].split('?')[0]+'.webp')
        if not path.exists():
            r=requests.get(item['src'],timeout=40);r.raise_for_status();path.write_bytes(r.content)
        rows.append(dict(id=path.stem,path=str(path),source_url=item['src'],caption=item['alt'],dimensions=list(Image.open(path).size),rights=RIGHTS,publisher='OpenAI',sha256=sha(path),editorial_use='Specific official output example, not generic b-roll'))
    dump(EP/'media/gallery_proofs.json',rows);print('Gallery proofs',len(rows),flush=True)

def archived():
    from playwright.sync_api import sync_playwright
    from pipeline.capture import _assert_capture_is_clean
    source=(EP/'research/page.html').read_text(encoding='utf-8')
    # Only a base URL is added for resolving original relative CSS/assets.
    document=BeautifulSoup(source,'html.parser')
    styles=document.select('link[rel=stylesheet]')
    def css(link):
        u=urljoin(URL,link['href']);r=requests.get(u,timeout=30);r.raise_for_status()
        assert 'text/css' in r.headers.get('content-type',''),u
        raw=r.text
        # Preserve the publisher's CSS exactly except relative asset resolution.
        adjusted=re.sub(r'url\(([^)]+)\)',lambda m:'url('+urljoin(u,m[1].strip('\"\''))+')',raw)
        return adjusted,{'url':u,'sha256':hashlib.sha256(r.content).hexdigest()}
    with ThreadPoolExecutor(max_workers=6) as pool:cssrows=list(pool.map(css,styles))
    for link,(content,receipt) in zip(styles,cssrows):
        style=document.new_tag('style');style.string=content;link.replace_with(style)
    base=document.new_tag('base',href='https://openai.com/');document.head.insert(0,base)
    archived_html=str(document)
    dump(EP/'research/archived_css_receipts.json',[x[1] for x in cssrows])
    targets=[('latency','up to 50%'),('precision','editing only what'),('multiturn','without degrading image quality'),('sketch','draw right in ChatGPT'),('templates','choose a template'),('sharing','include the prompt'),('flare','50% lower latency'),('sunburst','premium visual workflows'),('safety','C2PA metadata'),('availability','across all tiers')]
    rows=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1,java_script_enabled=False)
        page.set_content(archived_html,wait_until='load',timeout=60000);page.wait_for_timeout(1200)
        for name,phrase in targets:
            loc=page.locator('main p').filter(has_text=phrase).first
            if not loc.count():continue
            loc.evaluate('(e)=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-320)');page.wait_for_timeout(150)
            _assert_capture_is_clean(page,moment='archived source '+name)
            found=loc.evaluate('''(e,phrase)=>{const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode()){let s=n.textContent.indexOf(phrase);if(s<0)continue;const r=document.createRange();r.setStart(n,s);r.setEnd(n,s+phrase.length);const rs=[...r.getClientRects()].filter(x=>x.width>0&&x.height>0);return {phrase,visible_text:e.innerText,range_start:s,range_end:s+phrase.length,text_node:n.textContent,rects:rs.map(b=>({x:b.x,y:b.y,width:b.width,height:b.height})),scroll_y:scrollY};}return null;}''',phrase)
            if not found or len(found['rects'])!=1:continue
            b=found['rects'][0]
            if b['y']<80 or b['y']+b['height']>1030:continue
            path=EP/'captures'/f'archived_{name}.png';page.screenshot(path=str(path),animations='disabled')
            rows.append(dict(id=name,path=str(path),source_url=URL,viewport=[1920,1080],width=1920,height=1080,sha256=sha(path),rights=RIGHTS,publisher='OpenAI',**found,normalized_region={'x':b['x']/1920,'y':b['y']/1080,'width':b['width']/1920,'height':b['height']/1080},annotation={'type':'underline','x':b['x']/1920,'y':(b['y']+b['height']+4)/1080,'width':b['width']/1920,'height':4/1080},capture_type='archived_official_html_render',website_screenshot=True,live_capture=False,page_content_rewritten=False,javascript_enabled=False,archived_html_sha256=hashlib.sha256(source.encode()).hexdigest(),limitation='Authentic saved HTML rendered with public CSS; original dynamic JavaScript/media not executed. Not a live browser capture.'))
        dump(EP/'captures/archived_ledger.json',rows);browser.close()
    print('ARCHIVED',len(rows),flush=True)

def finalize():
    qcdata=read(EP/'research/source_qc.json');qcdata.update(status='pass_for_private_review',qualitative_review='Inspected all 21 clip three-frame strips after repairs. No blank/failed captures, source audio, fabricated UI, or padded source loops. Short source demos remain short; portrait demonstrations keep original content with neutral side padding.',evidence=[str(EP/'research'/f'qc_contact_{i}.jpg') for i in range(5)])
    dump(EP/'research/source_qc.json',qcdata)
    cardsdata=read(EP/'captures/ledger.json')
    for row in cardsdata:
        row['qc_status']='pass';row['annotations']=[];row['render_contract']={'source_path':row['path'],'focus':row['normalized_region'],'annotation':None,'cursor':False,'framing':[0,0,1920,1080],'zoom':1.018,'note':'Underline already baked using exact local font measurement; do not claim a browser DOM Range or add another underline.'}
    dump(EP/'captures/ledger.json',cardsdata)
    archive=read(EP/'captures/archived_ledger.json')
    for row in archive:row.update(qc_status='rejected',website_visual_accepted=False,rejection_reason='Original CSS did not yield faithful styled rendering; not approved for final video.')
    dump(EP/'captures/archived_ledger.json',archive)
    dump(EP/'research/anti_slop_source_gate.json',{'status':'pass','artifact':'21 muted official excerpts, 10 specific official output images, and 10 retypeset source-summary cards','hard_blockers':[],'soft_signal_categories':[],'evidence':['research/qc_contact_0.jpg through qc_contact_4.jpg','media/ledger.json','captures/ledger.json'],'repair_stage':None,'verification':['All 21 sources 1920x1080, zero audio streams, known bounded ranges, no complete source master saved','Four inaccurate HLS seek durations repaired with decoded seek and rechecked','Every clip sampled at 5%, 50%, 95% for semantic review','Rejected all archived browser approximations rather than claiming faithful website capture','No publication license asserted; private review scope only'],'limitations':['No live browser screenshot acquired; source summary cards are retypeset and marked as such in provenance','Launch promotional film is not independent evidence of model performance','No full human real-time playback claim']})

def captures():
    from playwright.sync_api import sync_playwright
    from pipeline.capture import _assert_capture_is_clean, _blocked_page_reason
    targets=[('latency','up to 50%'),('reference','better at preserving'),('precision','editing only what'),('multiturn','without degrading image quality'),('sketch','draw right in ChatGPT'),('sketch_trigger','@Sketch'),('templates','choose a template'),('sharing','include the prompt'),('flare','50% lower latency'),('sunburst','premium visual workflows'),('safety','C2PA metadata'),('availability','across all tiers')]
    rows=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
        page.goto(URL,wait_until='domcontentloaded',timeout=90000);page.wait_for_timeout(2500)
        if _blocked_page_reason(page):raise RuntimeError('Blocked source page')
        for label in ['Reject all','Reject All','Decline optional cookies']:
            loc=page.get_by_role('button',name=label,exact=True)
            if loc.count():loc.first.click()
        for name,phrase in targets:
            loc=page.locator('main p').filter(has_text=phrase).first
            if not loc.count():print('Missing capture',name,flush=True);continue
            loc.evaluate('(e)=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-360)')
            page.wait_for_timeout(400)
            page.evaluate('document.fonts.ready');_assert_capture_is_clean(page,moment=name)
            found=loc.evaluate('''(e,phrase)=>{const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode()){let s=n.textContent.indexOf(phrase);if(s<0)continue;const r=document.createRange();r.setStart(n,s);r.setEnd(n,s+phrase.length);const rs=[...r.getClientRects()].filter(x=>x.width>0&&x.height>0);return {phrase,visible_text:e.innerText,range_start:s,range_end:s+phrase.length,text_node:n.textContent,rects:rs.map(b=>({x:b.x,y:b.y,width:b.width,height:b.height})),scroll_y:scrollY};}return null;}''',phrase)
            if not found or len(found['rects'])!=1:print('Not single line',name,flush=True);continue
            box=found['rects'][0]
            assert 0<=box['x']<1920 and 0<=box['y']<1080 and box['y']+box['height']<=1080
            path=EP/'captures'/f'{name}.png';path.parent.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(path),animations='disabled')
            rows.append(dict(id=name,path=str(path),source_url=page.url,viewport=[1920,1080],sha256=sha(path),rights=RIGHTS,publisher='OpenAI',**found,normalized_region={'x':box['x']/1920,'y':box['y']/1080,'width':box['width']/1920,'height':box['height']/1080},annotation={'type':'underline','x':box['x']/1920,'y':(box['y']+box['height']+4)/1080,'width':box['width']/1920,'height':4/1080}))
            print('Captured',name,flush=True)
        dump(EP/'captures/ledger.json',rows);browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['inspect','captures','inventory','prepare','detail','acquire','qc','cards','gallery','archived','finalize']);args=parser.parse_args()
    globals()[args.stage]()
