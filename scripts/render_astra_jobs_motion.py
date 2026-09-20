"""Original silent Astra work explainer scenes. Reuses the existing Remotion render contract."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, shutil, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/episodes/episode_20260919_astra_jobs/motion'
KINDS=('job_tasks','finance_flow','financial_model','finance_benchmark','law_research','law_benchmark','permission_layers','work_handoff','automation_boundary','practical_check')
SOURCE=ROOT/'remotion/src/astra-jobs-entry.tsx'
FIN='https://openai.com/index/introducing-chatgpt-financial-services/'
LAW='https://openai.com/index/astra-for-law/'
TIMES={'job_tasks':[0,.5,1.67,2.83,4.73,6.53,7.23],'finance_flow':[0,1.47,2.43,5.1,6.03,6.83],'financial_model':[0,1.63,2.37,4.2,5.77,7.77],'finance_benchmark':[.67,2.77,5.8],'law_research':[0,2.23,3,4.9,6.03,6.83,7.6],'law_benchmark':[.67,2.77,5.8],'permission_layers':[0,2.6,5.2,8.3],'work_handoff':[0,1.23,2.53,3.3,4.1,5.33,6.57,7.87],'automation_boundary':[0,2.13,3.87,6.8],'practical_check':[0,.4,2.27,4.13,6,8.03]}
PROOFS={'job_tasks':'Task document forks preparation from accountability without quantities','finance_flow':'Data cylinder, cited workbook, explicit analyst signoff','financial_model':'Simplified hypothetical units: revenue100 minus fuel20 minus other60 gives profit20; fuel30 gives profit10','finance_benchmark':'Zero-based 0–100 bars: Sol 60.2, Astra 69.9 OfficeQA Pro','law_research':'Facts document routes to authority, jurisdiction and currency checks, then lawyer','law_benchmark':'Zero-based 0–100 bars: 38.7 web-only vs 54.0 tailored law; 15.3pp and ~40%relative','permission_layers':'Nested decision boundaries for reading, team/matter scope, action','work_handoff':'Draft manuscript to review checklist to human decision','automation_boundary':'Clock is not an employment forecast: explicit not-equal relationship','practical_check':'One review record progressively checks source, date, assumptions, reviewer'}
def dump(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(cmd,cwd=None,timeout=2400):
 r=subprocess.run([str(v) for v in cmd],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 if r.returncode:raise RuntimeError((r.stdout+r.stderr)[-7000:])
 return r.stdout
def render(name,stills=False):
 props={'kind':name,'seconds':12};pp=OUT/f'{name}.props.json';dump(pp,props)
 assets=OUT/'public_assets';(assets/'brands').mkdir(parents=True,exist_ok=True)
 logo=ROOT/'remotion/public/brands/openai.svg'
 if not (assets/'brands/openai.svg').exists():shutil.copy2(logo,assets/'brands/openai.svg')
 sig=hashlib.sha256(SOURCE.read_bytes()+Path(__file__).read_bytes()+logo.read_bytes()+json.dumps(props,sort_keys=True).encode()).hexdigest()
 cmd=[ROOT/'remotion/node_modules/.bin/remotion.cmd'];base=['src/astra-jobs-entry.tsx','AstraJobsGraphic',f'--public-dir={assets}',f'--props={pp}','--browser-executable=C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe']
 if stills:
  for label,frame in [('opening',0),('developing',126),('settled',270),('exit',359)]:
   run(cmd+['still']+base+[OUT/f'{name}_{label}.png',f'--frame={frame}','--image-format=png'],cwd=ROOT/'remotion')
  print('Stills',name,flush=True);return
 dest=OUT/f'{name}.mp4';receipt=OUT/f'{name}.render.json'
 if dest.exists() and receipt.exists():
  record=json.loads(receipt.read_text())
  if record.get('input_hash')==sig and record.get('sha256')==sha(dest):print('Cached',name,flush=True);return
 start=time.monotonic();framesdir=OUT/'frames'/f'{name}_{sig[:10]}';framesdir.mkdir(parents=True,exist_ok=True)
 if len(list(framesdir.glob('*.jpeg')))!=285:
  log=run(cmd+['render']+base+[framesdir,'--sequence','--image-format=jpeg','--jpeg-quality=96','--concurrency=2','--frames=0-284','--muted'],cwd=ROOT/'remotion')
  (OUT/f'{name}.log').write_text(log,encoding='utf-8')
 frames=sorted(framesdir.glob('*.jpeg'))
 if len(frames)!=285:raise RuntimeError(f'Incomplete render: {name}: {len(frames)}')
 listing=framesdir/'sequence.txt';listing.write_text(''.join("file '"+f.as_posix()+"'\nduration 0.033333333333\n" for f in frames),encoding='utf-8')
 run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',listing,'-an','-vf','tpad=stop_mode=clone:stop_duration=2.5,scale=out_color_matrix=bt709:out_range=tv,setsar=1,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709','-r','30','-t','12','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',dest])
 meta=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',dest]));v=next(s for s in meta['streams'] if s['codec_type']=='video')
 run(['ffmpeg','-v','error','-i',dest,'-f','null','-'])
 checks={'1920x1080':v['width']==1920 and v['height']==1080,'fps30':v['r_frame_rate']=='30/1','h264':v['codec_name']=='h264','bt709_limited':v.get('color_space')=='bt709' and v.get('color_range')=='tv','silent':not any(s['codec_type']=='audio' for s in meta['streams']),'duration12':abs(float(meta['format']['duration'])-12)<.04,'decoded':True}
 if not all(checks.values()):raise RuntimeError(str(checks))
 dump(receipt,{'input_hash':sig,'sha256':sha(dest),'path':str(dest),'duration':12,'frames':360,'fps':30,'elapsed_seconds':round(time.monotonic()-start,2),'checks':checks,'semantic_reveals_seconds':TIMES[name],'source_url':FIN if name.startswith('finance') or name=='financial_model' else LAW if name.startswith('law') or name=='permission_layers' else None,'original_editorial_illustration':True,'not_product_ui':True,'max_episode_uses':1,'publishing_enabled':False})
 run(['ffmpeg','-y','-v','error','-i',dest,'-vf','fps=1,scale=384:216,tile=4x3','-frames:v','1',OUT/f'{name}_contact.png'])
 for label,sec in [('opening',0),('developing',4.2),('settled',9),('exit',11.9667)]:
  run(['ffmpeg','-y','-v','error','-ss',sec,'-i',dest,'-frames:v','1',OUT/f'{name}_{label}.png'])
 print('Ready',name,checks,flush=True)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--name',choices=KINDS);parser.add_argument('--stills',action='store_true');args=parser.parse_args()
 dump(OUT/'art_direction.json',{'version':'astra-jobs-motion-v1','concepts':['Article-led chart/table extracts','Single changing proof object with checkable consequences','Sequential text-only ledger'],'selected':'Original relationship-specific diagrams, exact source benchmark plots, hypothetical model arithmetic','reason':'Source footage is handled elsewhere; these inserts explain assumptions, handoffs, benchmark interpretation and boundaries rather than imitate product UI. Vary geometry with each relationship.','proof_objects':PROOFS,'frame_contract':{'size':[1920,1080],'safe_inset':108,'camera':'locked','canvas':'#F2F1ED','ink':'#202624','accents':['#577A91','#647B6A'],'yellow_purple':False,'body_min_px':28,'metadata_min_px':23,'font':'Inter Variable','max_focal_groups':3,'reading_order':'question, proof relationship, consequence','underlines':False},'motion_intents':['enter','connect','emphasize'],'semantic_reveals_seconds':TIMES,'brand':{'asset':'remotion/public/brands/openai.svg','source_url':'https://openai.com/brand/','sha256':sha(ROOT/'remotion/public/brands/openai.svg'),'modified':False},'duration_per_clip':12,'all_duration':120,'original_assets':True,'publishing_enabled':False})
 names=[args.name] if args.name else list(KINDS)
 if args.stills:
  for name in names:render(name,True)
 else:
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(render,names))
if __name__=='__main__':main()
