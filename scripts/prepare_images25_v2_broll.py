"""Acquire only bounded official demonstration beats, with endpoint evidence."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse, hashlib, json, re, subprocess
from urllib.parse import urljoin
import requests
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
EP=ROOT/'data/episodes/episode_20260908_chatgpt_images25'
OUT=EP/'revision_v2/media'
URL='https://openai.com/index/introducing-chatgpt-images-2-5/'
SPECS=[
 ('v2_aquarium_comments','launch_x',6.0,14.8,'Aquarium room: targeted furniture comments, changed result and tangible recreation'),
 ('v2_tattoo','launch_x',15.8,22.4,'Cat photograph to tattoo prompt, generated design and actual tattoo'),
 ('v2_candleholder','launch_x',22.6,30.0,'Candleholder drawing to rendered concept and physical object'),
 ('v2_hair_preview','launch_x',30.0,35.3,'Haircut prompt to visual preview and salon result'),
 ('v2_flowers','launch_x',38.0,47.2,'Flower arrangement prompt to generated preview and dinner flowers'),
 ('v2_sketch_frog','sketch',0.5,8.15,'Sketch activation, frog drawing, prompt and finished frog scene'),
 ('v2_sketch_crab','sketch',10.4,13.0,'Crab line drawing to finished crab-shaped object'),
 ('v2_sketch_garden','sketch',13.3,17.5,'Garden layout drawing to completed overhead garden visualization'),
 ('v2_sketch_horse','sketch',18.2,22.35,'Horse line drawing to completed framed artwork'),
 ('v2_sketch_fashion','sketch',22.7,27.5,'Fashion sketch to completed sculptural garment'),
 ('v2_template_logo','templates',4.0,12.3,'Logo template choices, visual direction and finished racing logo'),
 ('v2_template_merch','templates',12.5,18.0,'Apparel template selection to completed branded long-sleeve shirt'),
 ('v2_template_motorcycle','templates',18.0,21.4,'Finished racing identity applied to a motorcycle promotional image'),
 ('v2_fullbody_early','fullbody',0.0,8.0,'Official repeated portrait edits: outfit, backgrounds, accessories'),
 ('v2_fullbody_late','fullbody',8.0,16.6,'Official later portrait-edit sequence preserving subject through style changes'),
]

def dump(p,d):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2),encoding='utf-8')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(a,timeout=300):
 r=subprocess.run(a,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 if r.returncode:raise RuntimeError(re.sub(r'https?://\S+','[source URL]',r.stderr[-1500:]))
 return r.stdout
def sources():
 cache=OUT/'sources.json'
 if cache.exists():return {x['id']:x for x in read(cache)}
 rows=[x for x in read(EP/'research/demo_streams.json') if x['id'] in {s[1] for s in SPECS}]
 def refresh(d):
  if d['id']=='launch_x':return d
  r=requests.get(d['url'],timeout=45);r.raise_for_status()
  m=re.search(r'window\.playerConfig\s*=\s*',r.text);assert m,d['id']
  cfg=json.JSONDecoder().raw_decode(r.text[m.end():])[0]
  hls=cfg['request']['files']['hls'];cdn=hls['cdns'][hls['default_cdn']];stream=cdn.get('avc_url') or cdn['url']
  r=requests.get(stream,timeout=45);r.raise_for_status();lines=r.text.splitlines();opts=[]
  for i,line in enumerate(lines[:-1]):
   m=re.search(r'RESOLUTION=(\d+)x(\d+)',line)
   if m and not lines[i+1].startswith('#'):opts.append((int(m[1]),int(m[2]),urljoin(stream,lines[i+1])))
  w,h,u=max(opts,key=lambda x:x[0]*x[1]);return dict(d,stream=u,width=w,height=h)
 with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(refresh,rows))
 dump(cache,rows);return {x['id']:x for x in rows}
def acquire():
 rows=sources()
 def one(s):
  ident,topic,start,end,caption=s;source=rows[topic];dest=OUT/(ident+'.mp4');receipt=dest.with_suffix('.json')
  targethash=hashlib.sha256(json.dumps(s).encode()).hexdigest()
  if receipt.exists() and dest.exists() and read(receipt).get('input_hash')==targethash:return read(receipt)
  # Reuse a larger acquired excerpt for local boundary repair, never reacquire it.
  source_input=source['stream'];offset=start;target=dest
  if receipt.exists() and dest.exists():
   previous=read(receipt)
   if previous['source_in']<=start and previous['source_out']>=end:
    source_input=str(dest);offset=start-previous['source_in'];target=dest.with_name(dest.stem+'_trim.mp4')
  # Output-side accurate seek prevents HLS keyframes silently truncating short beats.
  run(['ffmpeg','-y','-v','error','-i',source_input,'-ss',str(offset),'-t',str(end-start),'-map','0:v:0','-an','-vf','scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x111111,setsar=1,fps=30','-c:v','libx264','-preset','fast','-crf','17','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(target)])
  if target!=dest:target.replace(dest)
  info=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(dest)]));v=next(x for x in info['streams'] if x['codec_type']=='video');dur=float(info['format']['duration'])
  assert abs(dur-(end-start))<.07,(ident,dur,end-start)
  assert not any(x['codec_type']=='audio' for x in info['streams'])
  entry=dict(id=ident,path=str(dest),topic=topic,caption=caption,source_url=source['url'],announcement_url=URL,source_in=start,source_out=end,start=start,end=end,duration=end-start,verified_duration=dur,available_frames=int(v['nb_frames']),width=1920,height=1080,native_dimensions=[source['width'],source['height']],fps=30,playback_rate=1,source_audio_used=False,publisher='OpenAI',rights='User-requested bounded official launch excerpt for private editorial review. Public licensing not asserted; publication review required.',publishing_enabled=False,max_editorial_uses=2,input_hash=targethash,sha256=sha(dest),endpoint_qa_status='pending',framing='Native complete frame fitted without cropping into 1920x1080; no artificial camera movement')
  dump(receipt,entry);print(ident,dur,flush=True);return entry
 with ThreadPoolExecutor(max_workers=3) as pool:clips=list(pool.map(one,SPECS))
 dump(OUT/'ledger.json',clips)
def contacts():
 rows=read(OUT/'ledger.json')
 def one(c):
  d=c['verified_duration'];times=[0,.2,d*.25,d*.5,d*.75,max(0,d-.25),d-1/30];strip=Image.new('RGB',(1920,600),'#171717');draw=ImageDraw.Draw(strip);paths=[]
  for i,t in enumerate(times):
   dest=OUT/'qa'/f"{c['id']}_{i}.jpg";dest.parent.mkdir(parents=True,exist_ok=True)
   run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',c['path'],'-frames:v','1','-vf','scale=480:270','-threads','1',str(dest)])
   x=(i%4)*480;y=(i//4)*300;strip.paste(Image.open(dest),(x,y+30));draw.text((x+6,y+6),f"{c['id']} source {c['source_in']+t:.3f}s",fill='white');paths.append(str(dest))
  p=OUT/'qa'/f"{c['id']}_contact.jpg";strip.save(p);return dict(id=c['id'],path=str(p),frame_paths=paths,sample_source_times=[c['source_in']+t for t in times])
 with ThreadPoolExecutor(max_workers=3) as pool:qa=list(pool.map(one,rows))
 dump(OUT/'qa/contacts.json',qa)
def finalize():
 """Persist the observed review, only after contact/endpoint inspection."""
 notes={
 'v2_aquarium_comments':('Full aquarium prompt visible','Completed aquarium recreation remains visible','Trimmed outgoing tattoo scene'),
 'v2_tattoo':('Tattoo prompt is being entered','Completed tattoo and satisfied subject','Original prompt-to-result beat retained'),
 'v2_candleholder':('Phone drawing demonstration','Candle lit in finished holder','Removed preceding tattoo subject'),
 'v2_hair_preview':('Selfie with haircut prompt','Completed salon haircut','Removed following flower scene'),
 'v2_flowers':('Flowers setup','Finished flowers on dinner table','Removed outgoing flash transition'),
 'v2_sketch_frog':('ChatGPT Sketch activation','Finished cartoon character on poolside chair','Removed half-written outgoing title; colloquial filename not species identification'),
 'v2_sketch_crab':('Crab drawing strokes','Completed red crab chair in classroom','Removed both adjacent title fragments'),
 'v2_sketch_garden':('Garden creation title begins','Finished garden perspective','Full drawing-to-garden transformation preserved'),
 'v2_sketch_horse':('Create title, no garden image','Finished winged-horse ceiling artwork','First 0.2 seconds removed after final endpoint inspection'),
 'v2_sketch_fashion':('Create a jacket title begins','Finished sculptural garment','Removed previous horse scene'),
 'v2_template_logo':('Logo template choices','Complete racing logo','Removed next merch prompt'),
 'v2_template_merch':('Merch request from existing logo','Finished branded shirt','Complete request-selection-result beat'),
 'v2_template_motorcycle':('Completed shirt','Completed racing identity grid','Removed incomplete outgoing title'),
 'v2_fullbody_early':('Original portrait','Complete glasses edit state','Native repeated-edit montage, no added speedup'),
 'v2_fullbody_late':('Complete accessory edit state','Completed final direct-flash edit','Accurate source duration16.667 used rather than rounded metadata17'),
 }
 rows=read(OUT/'ledger.json')
 def verify(c):
  run(['ffmpeg','-v','error','-i',c['path'],'-map','0:v:0','-f','null','-'])
  assert sha(Path(c['path']))==c['sha256'];assert c['available_frames']>0
  start,end,repair=notes[c['id']]
  c.update(endpoint_qa_status='pass',endpoint_qa={'start_observation':start,'end_observation':end,'repair':repair,'review_scope':'Seven sampled decoded frames including exact first and last; not a full real-time watch','evidence':str(OUT/'qa'/f"{c['id']}_contact.jpg"),'decode_errors':0},editorial_duration_frames=c['available_frames'],editorial_duration_seconds=c['available_frames']/30)
  if c['id']=='v2_sketch_horse':c['endpoint_qa']['final_boundary_evidence']=[str(OUT/'qa/horse_final_first.jpg'),str(OUT/'qa/horse_final_last.jpg')]
  if c['id']=='v2_sketch_frog':c['caption']='Sketch activation, cartoon character drawing and completed rendered scene'
  dump(Path(c['path']).with_suffix('.json'),c);return c
 with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(verify,rows))
 dump(OUT/'ledger.json',rows)
 dump(OUT/'qa/endpoint_review.json',{'status':'pass_for_private_editorial_review','clips':len(rows),'total_frames':sum(x['available_frames'] for x in rows),'total_seconds':sum(x['available_frames'] for x in rows)/30,'checks':['Every clip decoded without error','1920x1080 silent 30fps media probed at acquisition','No artificial speedup, loop, source crop, or padded duration','First and last source states inspected, repaired surrounding actions/title fragments','Travel infographic explicitly excluded'],'limitations':['Official promotional demonstrations are not independent tests','Full-body source is itself a fast repeated-edit montage','Public licensing not asserted; no publishing'],'rejected_ids':['travel_text'],'provider_spend':0,'entries':[{'id':x['id'],'sha256':x['sha256'],'frames':x['available_frames'],'qa':x['endpoint_qa']} for x in rows]})
 print('PASS',len(rows),sum(x['available_frames'] for x in rows)/30,flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['acquire','contacts','finalize']);args=ap.parse_args();globals()[args.stage]()
