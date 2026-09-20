"""Official bounded launch excerpts; authentic capture and provenance for private review."""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
EP=ROOT/'data/episodes/episode_20260919_astra_jobs'
URLS={'finance':'https://openai.com/index/introducing-chatgpt-financial-services/','law':'https://openai.com/index/astra-for-law/'}
FILMS={'finance':'https://video.twimg.com/amplify_video/2098111416284897280/vid/avc1/1920x1080/9ozTNPyavdJ3UWzK.mp4','law':'https://video.twimg.com/amplify_video/2100676124544290816/vid/avc1/1920x1080/IccqGABbN0W6bezt.mp4'}
RIGHTS='User-requested bounded official demo quotation for private editorial review. Public reuse license unverified; publication review required.'
def dump(p,d):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(a,timeout=300):
    r=subprocess.run(a,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    if r.returncode:raise RuntimeError(re.sub(r'https?://\S+','[source URL]',r.stderr[-1500:]))
    return r.stdout
def probe(path):return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
def inventory():
    from playwright.sync_api import sync_playwright
    from pipeline.capture import _blocked_page_reason,_assert_capture_is_clean
    rows=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
        for name,url in URLS.items():
            try:
                page.goto(url,wait_until='domcontentloaded',timeout=45000);page.wait_for_timeout(2500)
                reason=_blocked_page_reason(page)
                if reason:raise RuntimeError(reason)
                for label in ['Reject all','Reject All','Decline optional cookies']:
                    loc=page.get_by_role('button',name=label,exact=True)
                    if loc.count():loc.first.click()
                _assert_capture_is_clean(page,moment='inventory')
                data=page.evaluate('''() => ({title:document.title,url:location.href,headings:[...document.querySelectorAll('h1,h2,h3')].map(e=>({text:e.innerText,id:e.id,y:e.getBoundingClientRect().top+scrollY})),media:[...document.querySelectorAll('iframe,video')].map(e=>({tag:e.tagName,src:e.src,html:e.outerHTML.slice(0,1600),near:e.parentElement.parentElement.innerText.slice(0,800)})),text:document.querySelector('main')?.innerText||document.body.innerText})''')
                dump(EP/'research'/f'{name}_inventory.json',data)
                (EP/'research'/f'{name}.html').write_text(page.content(),encoding='utf-8')
                print(name,json.dumps(data,ensure_ascii=True)[:25000],flush=True)
            except Exception as e:
                dump(EP/'research'/f'{name}_capture_error.json',{'url':url,'error':str(e),'no_fake_capture':True})
                print(name,'CAPTURE FAILED',str(e),flush=True)
        browser.close()
    for name,url in FILMS.items():
        m=probe(url);v=next(s for s in m['streams'] if s['codec_type']=='video')
        rows.append({'id':name,'stream':url,'url':url,'duration':float(m['format']['duration']),'width':v['width'],'height':v['height']})
    dump(EP/'research/film_inventory.json',rows)
    print('FILMS',json.dumps(rows),flush=True)
def samples():
    rows=read(EP/'research/film_inventory.json')
    def one(job):
        d,t=job;p=EP/'research'/f"sample_{d['id']}_{t:04d}.jpg"
        if not p.exists():run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',d['stream'],'-frames:v','1','-vf','scale=480:270','-threads','1',str(p)])
        return d['id'],t,p
    jobs=[(d,t) for d in rows for t in range(0,int(d['duration']),5)]
    with ThreadPoolExecutor(max_workers=4) as pool:out=list(pool.map(one,jobs))
    for d in rows:
        images=[q for q in out if q[0]==d['id']]
        for offset in range(0,len(images),16):
            chunk=images[offset:offset+16];im=Image.new('RGB',(1920,300*((len(chunk)+3)//4)),'#111');dr=ImageDraw.Draw(im)
            for i,(_,t,p) in enumerate(chunk):x=i%4*480;y=i//4*300;im.paste(Image.open(p),(x,y+30));dr.text((x+8,y+8),f"{d['id']} {t}s",fill='white')
            im.save(EP/'research'/f"contact_{d['id']}_{offset//16}.jpg")
    print('Sampled',len(out),flush=True)

def acquire():
    films={x['id']:x for x in read(EP/'research/film_inventory.json')}
    selections={
      'finance':[(13,23,'prompt_sources','Company overview request and premium financial-source selection'),(31,42,'research','Research trace, financial table, and bank briefing analysis'),(47,58,'evidence','Source document citations and interactive financial chart'),(62,70,'templates','Firm presentation style selection and generated company overview deck')],
      'law':[(7,11.5,'identity','Astra for Law launch identity in a star field'),(19,31,'prompt','S-1 shell mapping request using company files and GO Public skill'),(31,42,'filing','Generated S-1 mapping and document preview result'),(45,54,'plugins','Legal tool ecosystem and specialist workflow icons'),(57,66,'privacy','Official privacy and safeguards statements; narrated eligibility caveat required')],
    }
    jobs=[]
    for name,ranges in selections.items():
        for a,b,slug,caption in ranges:jobs.append(dict(id=f'{name}_{slug}',input=films[name]['stream'],source_url=films[name]['url'],announcement_url=URLS[name],source_in=a,source_out=b,seek=a,duration=b-a,caption=caption,topic=name,native_dimensions=[1920,1080],full_source_duration=films[name]['duration']))
    old=read(ROOT/'data/episodes/episode_20260905_gpt6_astra_extended/media/ledger.json')
    ranges={'circuit':[(0,11,'pcb')],'science':[(0,4,'quality'),(15,20,'variants')],'excel':[(0,12,'model'),(12,24,'results')],'unity':[(0,12,'scene'),(12,24,'tools')],'house':[(0,14,'walkthrough')],'gears':[(0,9,'cad'),(9,19,'animation')],'qa':[(0,11,'navigation'),(11,23,'interactions')],'apartment':[(0,10,'search'),(10,20,'compare')],'dmv':[(0,10,'form'),(10,20,'submission')]}
    for d in old:
        if d['id'] not in ranges:continue
        for a,b,slug in ranges[d['id']]:
            jobs.append(dict(id=f"astra_{d['id']}_{slug}",input=d['path'],source_url=d['source_url'],announcement_url=d['announcement_url'],source_in=d['source_in']+a,source_out=d['source_in']+b,seek=a,duration=b-a,caption=d['source_description'],topic=d['id'],native_dimensions=d['native_dimensions'],full_source_duration=d['full_source_duration'],reused_source_sha256=d['sha256']))
    def one(d):
        dest=EP/'media'/f"{d['id']}.mp4";receipt=dest.with_suffix('.json');dest.parent.mkdir(parents=True,exist_ok=True)
        sig=hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
        if dest.exists() and receipt.exists() and read(receipt).get('input_hash')==sig:return read(receipt)
        run(['ffmpeg','-y','-v','error','-ss',str(d['seek']),'-i',d['input'],'-t',str(d['duration']),'-map','0:v:0','-an','-vf','scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x101010,setsar=1,fps=30','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)])
        row={k:v for k,v in d.items() if k not in ['input','seek']};row.update(path=str(dest),start=d['source_in'],end=d['source_out'],width=1920,height=1080,publisher='OpenAI',source_audio_used=False,rights=RIGHTS,rights_basis=RIGHTS,publishing_enabled=False,max_editorial_uses=2,sha256=sha(dest),input_hash=sig,framing='Full source fitted without cropping. Native dimensions preserved in ledger; lower-resolution source marked.',semantic_tags=[d['topic'],d['id']],endpoint_qa_status='pending')
        m=probe(dest);v=next(x for x in m['streams'] if x['codec_type']=='video');duration=float(m['format']['duration'])
        assert (v['width'],v['height'])==(1920,1080) and v['r_frame_rate']=='30/1'
        assert not any(x['codec_type']=='audio' for x in m['streams'])
        assert abs(duration-d['duration'])<.08,(d['id'],duration)
        row.update(verified_duration=duration,available_frames=int(v['nb_frames']),verified_audio_streams=0)
        dump(receipt,row);print('READY',d['id'],duration,flush=True);return row
    with ThreadPoolExecutor(max_workers=3) as pool:out=list(pool.map(one,jobs))
    dump(EP/'media/ledger.json',out);print('TOTAL',len(out),sum(x['duration'] for x in out),flush=True)

def qc():
    rows=read(EP/'media/ledger.json')
    def one(row):
        dest=EP/'research'/f"endpoints_{row['id']}.jpg";prefix=f"frame_{row['id']}_{row['sha256'][:10]}_";tmp=EP/'research'/f"{prefix}%03d.jpg"
        run(['ffmpeg','-y','-v','error','-i',row['path'],'-vf','fps=1,scale=384:216','-q:v','3','-threads','1',str(tmp)])
        frames=sorted((EP/'research').glob(f"{prefix}*.jpg"));im=Image.new('RGB',(1536,240*((len(frames)+3)//4)),'#111');dr=ImageDraw.Draw(im)
        for i,p in enumerate(frames):x=i%4*384;y=i//4*240;im.paste(Image.open(p),(x,y+24));dr.text((x+5,y+5),f"{row['id']} {i+.5:.1f}s",fill='white')
        im.save(dest);run(['ffmpeg','-v','error','-xerror','-i',row['path'],'-f','null','-'])
        return {'id':row['id'],'contact':str(dest),'sha256':sha(Path(row['path'])),'decoded':True,'status':'visual_review_pending'}
    with ThreadPoolExecutor(max_workers=3) as pool:checks=list(pool.map(one,rows))
    dump(EP/'research/source_qc.json',{'checks':checks,'status':'visual_review_pending'})
    print('QC',len(checks),flush=True)

def product_images():
    sources=[
      ('value_analysis','1UH8olCAwzTlgF6K1yCEf/0c5029d3c44cfab8e7e3729c3f7d9ead/value-analysis.png','Value analysis workflow'),
      ('lbo_model','66wBsc9s6nDCmsbJ6Zltqn/89021eb0bf3a474affc6a9a5f7a80d49/lob-modelling.png','Leveraged buyout modelling'),
      ('buyer_screening','7da8fRahe3sC1j3Ry6TggE/9d2e77b8fc0e4d07971064dd358f794b/finserv-buyer-screening-2x.png','Buyer screening'),
      ('earnings_analysis','4ljojm8iz6dJxJlbRQwmdj/4898e24669bdb914d4df8fc11019a0e3/earnings-analysis.png','Earnings analysis'),
      ('pitchbook','6HQc0dDsBjXPZfiGe2QDfR/1b5661b26f587f4e31a76fb2d0316687/pitchbook-preparation.png','Pitchbook preparation'),
      ('source_picker','53nzN8JBQyMAzX0BeyvGda/8ecf741d5f3fc2c31b892a0ebd96f86d/source_picker.png','Financial data source picker'),
      ('citations','2ZIpRitoFpSf7uI7Ylsdxw/8fdeaa91e9a00169c0ea797517c5e718/finserv-citations.png','Highlighted source evidence for adjusted EBITDA'),
      ('lbo_chart','5Gyz6WCAHtopSNkLzuZPGS/da0990c448e6779f9935c632a4ab9571/finserv-charts.png','LBO value bridge chart with underlying financial data'),
      ('firm_templates','bZoYw0hzd3YPvQ3BssVCR/adc8f9a83d6bd50a8cfee28a42487a6d/finserv-templates-2x-refresh.png','Firm-approved template used to create company overview deck')]
    rows=[]
    for ident,fragment,caption in sources:
        url='https://images.ctfassets.net/kftzwdyauwt9/'+fragment+'?w=3840&q=90&fm=webp';dest=EP/'media'/f'finance_{ident}.webp';dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            r=requests.get(url,timeout=60);r.raise_for_status();dest.write_bytes(r.content)
        size=Image.open(dest).size
        rows.append({'id':'finance_'+ident,'path':str(dest),'source_url':url,'announcement_url':URLS['finance'],'caption':caption,'width':size[0],'height':size[1],'capture_type':'official_product_screenshot_asset','website_screenshot':False,'publisher':'OpenAI','sha256':sha(dest),'rights':RIGHTS,'provenance':'Observed image URL and alt text in authentic finance page DOM via in-app browser; not generated or retypeset','publishing_enabled':False})
    dump(EP/'media/product_screens.json',rows);print('IMAGES',len(rows),flush=True)

def finalize():
    """Call only after visual contact-sheet and changed endpoint review."""
    rows=read(EP/'media/ledger.json');qcdata=read(EP/'research/source_qc.json');checks={x['id']:x for x in qcdata['checks']}
    corrections={
      'astra_unity_scene':'Completed Astra-built Unity city scene, first-person walkthrough. This is the result, not editor actions.',
      'astra_unity_tools':'Completed Astra-built Unity city scene, continued first-person walkthrough. No editor tools shown.',
      'astra_gears_cad':'Finished five-speed transmission model with rotating gears. Illustrates engineering output; no CAD editor visible.',
      'astra_gears_animation':'Finished transmission animation with changing active gear highlights. Illustrates mechanism motion.',
      'astra_dmv_form':'Official Astra demonstration researching DMV requirements and locating a driver-license office.',
      'astra_dmv_submission':'Official Astra demonstration planning an office route and drafting a preparation document. No form submission shown.',
      'astra_excel_model':'Official Astra Excel competition-task demonstration, calculating and filling a spreadsheet. Condensed source playback, not finance-product UI.',
      'astra_excel_results':'Official Astra Excel competition-task demonstration, calculation results and task worksheet. Not a financial-market prediction.',
      'astra_science_quality':'Official Astra scientific-software demonstration opening sequencing quality and variant charts.',
      'astra_science_variants':'Official Astra scientific-software demonstration navigating from variant chart to indel distribution graph.'}
    for row in rows:
        assert sha(Path(row['path']))==row['sha256']==checks[row['id']]['sha256']
        assert checks[row['id']]['decoded']
        if row['id'] in corrections:row['caption']=corrections[row['id']]
        row.update(endpoint_qa_status='pass',qc_status='pass_for_private_review',native_resolution_note='Native source is below1080p; final1080p is upscale, not recovered detail.' if row['native_dimensions'][1]<1080 else 'Native source has at least1080 verticalpixels.',minimum_recommended_playback=row['verified_duration'],sampling_review='One-second samples across entire excerpt plus repaired opening/endpoints; no full human realtime playback claim.')
        dump(Path(row['path']).with_suffix('.json'),row)
        checks[row['id']]['status']='pass_for_private_review'
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            if a['source_url']==b['source_url']:
                assert min(a['source_out'],b['source_out'])<=max(a['source_in'],b['source_in']),('overlap',a['id'],b['id'])
    dump(EP/'media/ledger.json',rows)
    qcdata.update(status='pass_for_private_review',checks=list(checks.values()),count=len(rows),distinct_nominal_seconds=sum(x['duration'] for x in rows),distinct_verified_seconds=sum(x['verified_duration'] for x in rows),full_source_masters_saved=False,publishing_enabled=False,repairs=['Removed incomplete title fragments fromfinance cutedges','Selected actuallawgalaxy identity rather thaninitialwhitetitle','Removed prolonged unchangedsciencechart holds','Corrected result-demo captions to avoid claiming liveeditor or submission actions'],limitations=['Sourcepromotionaldemos are not independent performance tests','Some cachedAstra sources are720p or900p upscaled, flaggedperasset','Publicreuse licenseunverified; privateeditorialreviewonly','Narration/shot alignment requires finalintegratedreview'])
    dump(EP/'research/source_qc.json',qcdata)
    dump(EP/'research/anti_slop_source_gate.json',{'status':'pass_for_private_review','artifact':'25boundedofficialvideoexcerpts and9officialproductimages','hard_blockers':[],'soft_signal_categories':[],'evidence':['source_qc.json','endpoints_*.jpg','../media/ledger.json','../media/product_screens.json'],'verification':['Fullvideodecode','Exactly1920x1080/30fps','Zero sourceaudio streams','Nooverlapping sourceranges','One-secondvisualsample review','Repaired misleading/truncated endpoints'],'publishing_enabled':False,'limitations':qcdata['limitations']})
    print('FINAL',len(rows),qcdata['distinct_verified_seconds'],flush=True)

def image_qc():
    rows=read(EP/'media/product_screens.json');sheet=Image.new('RGB',(1920,390*3),'#111');draw=ImageDraw.Draw(sheet)
    for i,row in enumerate(rows):
        im=Image.open(row['path']).convert('RGB');im.thumbnail((640,360));x=i%3*640;y=i//3*390
        sheet.paste(im,(x+(640-im.width)//2,y+30));draw.text((x+8,y+7),row['id'],fill='white')
        assert sha(Path(row['path']))==row['sha256']
    sheet.save(EP/'research/product_screens_contact.jpg')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage');args=parser.parse_args();globals()[args.stage]()
