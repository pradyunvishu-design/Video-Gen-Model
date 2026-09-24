"""Public first-party Opus 5.5 source discovery and bounded media quotations."""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, time
from pathlib import Path
from urllib.parse import urljoin
import requests
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
EP=ROOT/'data/episodes/episode_20260923_opus55'
URLS={'launch':'https://www.anthropic.com/claude-opus-5-5','docs':'https://platform.claude.com/docs/en/models/opus-5-5/overview','migration':'https://platform.claude.com/docs/en/models/opus-5-5/migration-guide','github':'https://github.blog/changelog/2026-09-22-claude-opus-5-5-is-now-available-in-github-copilot/','analysis':'https://artificialanalysis.ai/articles/claude-opus-5-5','cursor':'https://prod.cursor.com/docs/models/claude-opus-5-5'}
def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
def discover():
    rows=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        for key,url in URLS.items():
            page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
            page.goto(url,wait_until='domcontentloaded',timeout=90000);page.wait_for_timeout(5000)
            text=page.locator('body').inner_text()
            data=page.evaluate("""() => ({title:document.title,headings:[...document.querySelectorAll('h1,h2,h3,h4')].map(e=>e.innerText),videos:[...document.querySelectorAll('video')].map(e=>({src:e.currentSrc||e.src,poster:e.poster,sources:[...e.querySelectorAll('source')].map(s=>s.src),outer:e.outerHTML})),iframes:[...document.querySelectorAll('iframe')].map(e=>({src:e.src,title:e.title})),images:[...document.images].map(e=>({src:e.currentSrc||e.src,alt:e.alt,width:e.naturalWidth,height:e.naturalHeight})),links:[...document.querySelectorAll('a[href]')].map(e=>({url:e.href,text:e.innerText}))})""")
            data.update(url=page.url,text=text)
            dump(EP/'research'/f'{key}_discovery.json',data)
            (EP/'research'/f'{key}.txt').write_text(text,encoding='utf-8')
            (EP/'research'/f'{key}.html').write_text(page.content(),encoding='utf-8')
            rows.append({'id':key,'url':page.url,'title':data['title'],'text_path':str(EP/'research'/f'{key}.txt'),'sha256':hashlib.sha256(text.encode()).hexdigest(),'publisher':'Anthropic'})
            print(key,json.dumps({k:data[k] for k in ['headings','videos','iframes','images']},ensure_ascii=True),flush=True)
            page.close()
        browser.close()
    dump(EP/'research/sources.json',rows)
def validate_media():
    media_path=EP/'media/ledger.json'
    if media_path.exists():
        media=json.loads(media_path.read_text(encoding='utf-8'))
        for row in media:
            meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',row['path']]))
            assert all(s['codec_type']=='video' for s in meta['streams'])
            assert all((s['width'],s['height'])==(1920,1080) for s in meta['streams'])
            row['duration']=float(meta['format']['duration'])
            if row['id'].startswith('site_'):row['source_out']=row['duration']
        dump(media_path,media)
def text_sources():
    from bs4 import BeautifulSoup
    for key in ('github','analysis','cursor'):
        response=requests.get(URLS[key],timeout=60);response.raise_for_status();soup=BeautifulSoup(response.text,'html.parser')
        for el in soup(['script','style','nav','footer']):el.decompose()
        text=soup.get_text(' ',strip=True)
        (EP/'research'/f'{key}.txt').write_text(text,encoding='utf-8');print(key,len(text),flush=True)
def finalize():
    validate_media()
    publishers={'launch':'Anthropic','docs':'Anthropic','migration':'Anthropic','github':'GitHub','analysis':'Artificial Analysis','cursor':'Cursor'}
    rows=[]
    for key,url in URLS.items():
        path=EP/'research'/f'{key}.txt'
        if path.exists():rows.append({'id':key,'url':url,'text_path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'publisher':publishers[key]})
    dump(EP/'research/sources.json',rows)
    captures=json.loads((EP/'captures/ledger.json').read_text(encoding='utf-8'))
    for row in captures:
        path=Path(row['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
        if row['id'].endswith('_chart'):row['framing']={'x':240,'y':90,'width':1440,'height':810,'units':'pixels','measurement':'Measured complete source chart and caption, fixed 16:9 crop'}
    dump(EP/'captures/ledger.json',captures)
    dump(EP/'research/acquisition_summary.json',{'sources':len(rows),'captures':len(captures),'launch_youtube':'https://www.youtube.com/watch?v=1f13Bl1sYkw','launch_x':'https://x.com/claudeai/status/2102435511222890900','launch_native_dimensions':[1920,1080],'full_launch_film_retained':False,'source_audio_used':False,'paid_calls':0,'publication_permission_asserted':False,'caveats':['Official launch film is abstract branding, not a coding demonstration.','Anthropic and Artificial Analysis benchmark scores come from different evaluation setups and must not be swapped.','Browser comparison recordings show published examples, not our own model test.']})
def acquire():
    tweet='2102435511222890900';url=f'https://x.com/claudeai/status/{tweet}'
    response=requests.get('https://cdn.syndication.twimg.com/tweet-result',params={'id':tweet,'lang':'en','token':'a'},timeout=40);response.raise_for_status();data=response.json()
    if data['user']['screen_name']!='claudeai':raise ValueError('Official identity mismatch')
    dump(EP/'research/launch_tweet.json',data)
    details=next(m for m in data['mediaDetails'] if m['type']=='video')
    selected=max((v for v in details['video_info']['variants'] if v['content_type']=='video/mp4'),key=lambda v:v.get('bitrate',0))
    ledger=[]
    # Only short non-overlapping quotations of a twenty-second launch film.
    for ident,start,duration,description in [('launch_open',0,5,'Opening visual of official Opus 5.5 launch film'),('launch_mid',9,5,'Middle visual of official Opus 5.5 launch film')]:
        path=EP/'media'/f'{ident}.mp4';path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            subprocess.run(['ffmpeg','-y','-v','error','-ss',str(start),'-i',selected['url'],'-t',str(duration),'-map','0:v:0','-an','-vf','scale=1920:1080:flags=lanczos,fps=30,setsar=1','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(path)],check=True,timeout=180)
        ledger.append({'id':ident,'path':str(path),'source_url':url,'media_url':selected['url'],'youtube_url':'https://www.youtube.com/watch?v=1f13Bl1sYkw','announcement_url':URLS['launch'],'publisher':'Anthropic / Claude','source_description':description,'source_in':start,'source_out':start+duration,'full_source_duration':20,'source_audio_used':False,'native_dimensions':[1920,1080],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rights_basis':'Bounded quotation of official first-party launch film for direct explanatory news commentary; no general reuse license or publication permission asserted.','publication_approval':'pending','publishing_enabled':False})
    dump(EP/'media/ledger.json',ledger)
    print('Acquired',len(ledger),'bounded launch excerpts',flush=True)
def record_comparisons():
    import sys
    sys.path.insert(0,str(ROOT))
    from pipeline.capture import _load_page,_assert_capture_is_clean
    ledger_path=EP/'media/ledger.json';ledger=json.loads(ledger_path.read_text(encoding='utf-8'))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        for ident,tab,next_tab in [('site_bug_comparison','Explaining a bug','Summarizing a thread'),('site_design_comparison','Explaining a design change','Explaining a bug')]:
            dest=EP/'media'/f'{ident}.mp4'
            context=browser.new_context(viewport={'width':1920,'height':1080},device_scale_factor=1,record_video_dir=str(EP/'media/recording_work'),record_video_size={'width':1920,'height':1080},color_scheme='light')
            begun=time.monotonic();page=context.new_page();_load_page(page,URLS['launch'],freeze_motion=False)
            page.evaluate("()=>{document.body.style.zoom=1.5;document.documentElement.style.scrollBehavior='auto'}")
            button=page.get_by_role('tab',name=tab,exact=True);button.click()
            button.evaluate("e=>{window.scrollTo({top:window.scrollY+e.getBoundingClientRect().top-125,behavior:'instant'})}")
            page.wait_for_timeout(2000);_assert_capture_is_clean(page,moment=ident)
            video=page.video;start=time.monotonic()-begun+.8;page.wait_for_timeout(3800)
            page.get_by_role('tab',name=next_tab,exact=True).click();page.wait_for_timeout(5500)
            context.close();source=Path(video.path())
            subprocess.run(['ffmpeg','-y','-v','error','-ss',str(start),'-i',str(source),'-t','8','-an','-vf','fps=30,setsar=1','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],check=True,timeout=180)
            row={'id':ident,'path':str(dest),'source_url':URLS['launch'],'announcement_url':URLS['launch'],'publisher':'Anthropic','source_description':f'Original browser recording of actual public comparison tabs: {tab} followed by {next_tab}. No claim that these are our own model runs.','source_in':0,'source_out':8,'source_audio_used':False,'native_dimensions':[1920,1080],'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'rights_basis':'Original capture of bounded public first-party product comparison for direct explanatory commentary; no general reuse license or publication permission asserted.','publication_approval':'pending','publishing_enabled':False,'capture_actions':[tab,next_tab]}
            meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(dest)]));row['duration']=float(meta['format']['duration']);row['source_out']=row['duration']
            ledger=[r for r in ledger if r['id']!=ident]+[row];dump(ledger_path,ledger)
            print('Recorded',ident,flush=True)
        browser.close()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['discover','acquire','text_sources','record_comparisons','finalize'],default='discover',nargs='?');args=parser.parse_args();globals()[args.stage]()
