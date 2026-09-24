"""Bounded, silent quotations from the six user-selected official Claude demos.

No full source master is retained. Public metadata/storyboards support editorial
selection; excerpt rights still require human publication review.
"""
from __future__ import annotations
import argparse, hashlib, io, json, math, re, subprocess, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
import yt_dlp
from PIL import Image, ImageDraw
from pipeline.youtube_radar import _key
from pipeline.youtube_broll import _youtube_get

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / 'data/episodes/episode_20260923_opus55'
RESEARCH = EP / 'research/six_demos'
MEDIA = EP / 'media/six_demos'
CHANNEL = 'UCV03SRZXJEz-hchIAogeJOg'
VIDEOS = {'daily':'jKRl_CSVxyI','launch':'1f13Bl1sYkw','gps':'K-pgPNFcAj4',
          'earthrise':'Ov-B6K1EsaI','daydreams':'lCR9epzSNGc','gravity':'uMsZ21ubIMM'}
DEFAULT_SELECTIONS = ROOT / 'configs/opus55_six_demo_selections.json'
RENDER = {'version':1,'width':1920,'height':1080,'fps':30,'codec':'libx264',
          'preset':'fast','crf':17,'pixel_format':'yuv420p','audio':False}

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)

def validate_selections(rows):
    if not isinstance(rows,list) or not rows:raise ValueError('Selections must be a nonempty list')
    identifiers=set()
    for row in rows:
        ident=row.get('id','')
        if not isinstance(ident,str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,79}',ident):
            raise ValueError('Invalid safe excerpt id')
        if ident in identifiers:raise ValueError('Duplicate excerpt id')
        identifiers.add(ident)
        if row.get('video_key') not in VIDEOS:raise ValueError('Unknown video_key')
        start,end=float(row['source_in']),float(row['source_out'])
        if not all(math.isfinite(v) for v in (start,end)) or not 0<=start<end or end-start>12:
            raise ValueError('Invalid bounded excerpt range')
    return rows

def load_selections():
    runtime=RESEARCH/'selections.json'
    return validate_selections(json.loads((runtime if runtime.exists() else DEFAULT_SELECTIONS).read_text(encoding='utf-8')))

def input_contract(row,data):
    return {'source_video_id':data['id'],'source_channel_id':data['channel_id'],
            'source_in':float(row['source_in']),'source_out':float(row['source_out']),
            'render':dict(RENDER)}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def validate_media(path,duration):
    meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
    streams=meta.get('streams',[])
    if len(streams)!=1:raise ValueError('Excerpt must contain exactly one video stream, no audio')
    stream=streams[0]
    if (stream.get('codec_type'),stream.get('codec_name'),stream.get('width'),stream.get('height'),stream.get('pix_fmt')) != ('video','h264',1920,1080,'yuv420p'):
        raise ValueError('Excerpt must be native1920x1080 H264 yuv420p')
    actual=float(meta.get('format',{}).get('duration','nan'))
    if not math.isfinite(actual) or abs(actual-duration)>.1:raise ValueError('Excerpt duration mismatch')
    return meta

def acquire_excerpt(row,data):
    """Only hash- and input-bound receipts authorize reuse; signed URLs are not keys."""
    validate_selections([row]);key=row['video_key']
    if data.get('id')!=VIDEOS[key] or data.get('channel_id')!=CHANNEL:
        raise ValueError('Official source identity mismatch')
    start,end=float(row['source_in']),float(row['source_out'])
    if end>float(data['duration']):raise ValueError('Excerpt exceeds source duration')
    contract=input_contract(row,data);dest=MEDIA/f"{row['id']}.mp4"
    receipt_path=dest.with_suffix('.receipt.json');dest.parent.mkdir(parents=True,exist_ok=True)
    reused=False
    if dest.exists() and receipt_path.exists():
        try:
            receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
            if receipt.get('inputs')==contract and receipt.get('output_sha256')==digest(dest):
                meta=validate_media(dest,end-start);reused=True
        except (ValueError,KeyError,OSError,subprocess.SubprocessError):pass
    if not reused:
        staged=dest.with_name(dest.stem+'.'+uuid.uuid4().hex+'.staged.mp4')
        try:
            subprocess.run(['ffmpeg','-y','-v','error','-ss',str(start),'-i',data['transport_url'],
                '-t',str(end-start),'-map','0:v:0','-an','-vf',f"fps={RENDER['fps']},setsar=1",
                '-c:v',RENDER['codec'],'-preset',RENDER['preset'],'-crf',str(RENDER['crf']),'-pix_fmt',RENDER['pixel_format'],
                '-movflags','+faststart',str(staged)],check=True,timeout=240)
            meta=validate_media(staged,end-start)
            output_hash=digest(staged)
            staged.replace(dest)
            save(receipt_path,{'schema_version':'six-demo-acquisition/1','inputs':contract,'output_sha256':output_hash})
        finally:
            staged.unlink(missing_ok=True)
    return {**row,'source_id':key,'path':str(dest),'source_url':data['url'],'source_video_id':data['id'],
        'source_title':data['title'],'publisher':'Claude / Anthropic','source_channel_id':CHANNEL,
        'native_dimensions':[1920,1080],'duration':float(meta['format']['duration']),
        'sha256':digest(dest),'source_audio_used':False,
        'rights_basis':'Bounded official first-party excerpt for explanatory editorial commentary; no general reuse license asserted.',
        'publication_approval':'pending','publishing_enabled':False,'full_master_retained':False}

def validate_ledger_ids(ledger,selections):
    actual=[r['id'] for r in ledger];expected=[r['id'] for r in selections]
    if len(actual)!=len(set(actual)) or set(actual)!=set(expected):
        raise ValueError('Acquisition ledger IDs do not match selections')

def metadata(key, refresh=False):
    path = RESEARCH / f'{key}_transport.json'
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding='utf-8'))
    with yt_dlp.YoutubeDL({'quiet':True,'no_warnings':True,'skip_download':True}) as ydl:
        data = ydl.extract_info('https://www.youtube.com/watch?v='+VIDEOS[key], download=False)
    if data.get('channel_id') != CHANNEL:
        raise ValueError('Official Claude channel identity mismatch')
    formats = [f for f in data['formats'] if f.get('height') == 1080 and f.get('width') == 1920
               and f.get('vcodec','').startswith('avc1') and f.get('protocol') == 'https']
    if not formats:
        raise ValueError('No native 1080p AVC transport available; do not upscale')
    selected = max(formats, key=lambda f: f.get('tbr',0))
    story = next(f for f in data['formats'] if f.get('format_id') == 'sb0')
    result = {'id':VIDEOS[key],'title':data['title'],'description':data.get('description',''),
              'channel_id':data['channel_id'],'channel':data.get('channel'),
              'duration':data['duration'],'url':data['webpage_url'],
              'native_dimensions':[selected['width'],selected['height']],
              'transport_url':selected['url'],'headers':selected.get('http_headers',{}),
              'storyboard':story}
    save(path,result)
    return result

def discover():
    response = _youtube_get('videos', {'part':'snippet,contentDetails,status',
                           'id':','.join(VIDEOS.values())}, _key())
    if (len(response.get('items',[])) != 6 or
            {row.get('id') for row in response['items']}!=set(VIDEOS.values())):
        raise ValueError('Not all six official videos are available')
    for row in response['items']:
        if row['snippet']['channelId'] != CHANNEL:
            raise ValueError('Official source mismatch')
    save(RESEARCH/'youtube_api_identity.json',response)
    def one(key):
        data = metadata(key,refresh=True)
        story = data['storyboard']; w,h=story['width'],story['height']
        samples=[]; index=0
        for fragment in story['fragments']:
            response=requests.get(fragment['url'],timeout=30);response.raise_for_status()
            sheet=Image.open(io.BytesIO(response.content)).convert('RGB')
            for cell in range(story['rows']*story['columns']):
                t=index/story['fps'];index+=1
                if t>=data['duration']: break
                if (index-1)%3: continue
                x=(cell%story['columns'])*w;y=(cell//story['columns'])*h
                tile=Image.new('RGB',(w,h+24),'#202020');tile.paste(sheet.crop((x,y,x+w,y+h)),(0,0))
                ImageDraw.Draw(tile).text((8,h+4),f'{key}  {t:06.1f}s',fill='white')
                samples.append(tile)
        cols=4;out=Image.new('RGB',(w*cols,(h+24)*((len(samples)+cols-1)//cols)),'#181818')
        for n,tile in enumerate(samples):out.paste(tile,((n%cols)*w,(n//cols)*(h+24)))
        out.save(RESEARCH/f'{key}_overview.jpg',quality=90)
        print(key,data['title'],data['duration'],data['native_dimensions'],flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(one,VIDEOS))

def acquire():
    selections=load_selections()
    def one(group):
        key,rows=group; data=metadata(key,refresh=True); ledger=[]
        for row in rows:
            ledger.append(acquire_excerpt(row,data))
            print('Acquired',row['id'],row['source_in'],row['source_out'],flush=True)
        return ledger
    groups=[(key,[r for r in selections if r['video_key']==key]) for key in VIDEOS]
    with ThreadPoolExecutor(max_workers=3) as pool:ledger=[r for rows in pool.map(one,groups) for r in rows]
    validate_ledger_ids(ledger,selections)
    save(MEDIA/'ledger.json',ledger)

def tighten():
    raise RuntimeError('Legacy one-time trim retired. Use acquire with updated selections and bound receipts.')

def contacts():
    """Contact strips from actual local excerpts, including both cut edges."""
    rows=json.loads((MEDIA/'ledger.json').read_text(encoding='utf-8'))
    for page in range((len(rows)+5)//6):
        subset=rows[page*6:(page+1)*6]
        sheet=Image.new('RGB',(1280,204*len(subset)),'#181818')
        draw=ImageDraw.Draw(sheet)
        for n,row in enumerate(subset):
            for j,ratio in enumerate((0.015,.34,.67,.985)):
                t=float(row['duration'])*ratio
                result=subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',row['path'],
                    '-frames:v','1','-vf','scale=320:180','-f','image2pipe','-vcodec','mjpeg','pipe:1'],
                    capture_output=True,check=True,timeout=30)
                frame=Image.open(io.BytesIO(result.stdout)).convert('RGB')
                sheet.paste(frame,(j*320,n*204))
                draw.text((j*320+5,n*204+184),f"{row['id']} src{float(row['source_in'])+t:.1f}s",fill='white')
        sheet.save(RESEARCH/f'excerpt_contacts_{page+1}.jpg',quality=92)
        print('Contacts',page+1,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['discover','acquire','tighten','contacts']);args=parser.parse_args()
    globals()[args.stage]()
