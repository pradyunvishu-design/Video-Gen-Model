"""Silent original Images 2.5 editorial diagrams. Existing Remotion sequence pipeline."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, time, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/episodes/episode_20260908_chatgpt_images25/motion'
SPECS={k:{'kind':k,'seconds':10} for k in ('latency','edit','continuity','sketch','tradeoff','check')}
TIMINGS={'latency':{'old_index':.67,'new_index':2.8,'caveat':5.4,'hold':6.5},'edit':{'selected_region':.93,'friday_removed':3.17,'saturday_revealed':3.83,'unchanged_contract':5.17,'hold':6.5},'continuity':{'original':0,'color':2.17,'background':3.77,'crop':5.37,'hold':6.8},'sketch':{'structure':.33,'brief':1.83,'output_direction':3.83,'layers':5.7,'hold':6.7},'tradeoff':{'flare':0,'sunburst':2.5,'tradeoff':5.17,'hold':6.5},'check':{'unchanged_regions':.67,'spelling':2.73,'small_details':4.83,'hold':6.5}}
EVIDENCE={'latency':['E05'],'edit':['E02'],'continuity':['E03'],'sketch':['E06'],'tradeoff':['E07'],'check':['EDITORIAL_TEST_GUIDANCE']}
def dump(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2),encoding='utf-8')
def run(cmd,cwd=None,timeout=1800):
 r=subprocess.run([str(x) for x in cmd],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 if r.returncode: raise RuntimeError((r.stdout+r.stderr)[-5000:])
 return r.stdout
def render(name,stills=False):
 props=SPECS[name];source=ROOT/'remotion/src/images25-entry.tsx'
 sig=hashlib.sha256(source.read_bytes()+json.dumps(props,sort_keys=True).encode()).hexdigest()
 pp=OUT/f'{name}.props.json';dump(pp,props)
 assetdir=OUT/'public_assets';(assetdir/'brands').mkdir(parents=True,exist_ok=True)
 shutil.copy2(ROOT/'remotion/public/brands/openai.svg',assetdir/'brands/openai.svg')
 cmd=[ROOT/'remotion/node_modules/.bin/remotion.cmd'];base=['src/images25-entry.tsx','Images25Graphic',f'--public-dir={assetdir}'];browser='--browser-executable=C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
 if stills:
  for label,frame in [('opening',0),('developing',105),('settled',209),('exit',299)]:
   run(cmd+['still']+base+[OUT/f'{name}_{label}.png',f'--props={pp}',browser,f'--frame={frame}','--image-format=png'],cwd=ROOT/'remotion')
  print('Stills ready',name,flush=True);return
 dest=OUT/f'{name}.mp4';receipt=OUT/f'{name}.render.json'
 if dest.exists() and receipt.exists() and json.loads(receipt.read_text()).get('input_hash')==sig:
  print('Cached',name,flush=True);return
 start=time.monotonic();framesdir=OUT/'frames'/f'{name}_{sig[:10]}';framesdir.mkdir(parents=True,exist_ok=True)
 if len(list(framesdir.glob('*.jpeg')))!=210:
  logs=run(cmd+['render']+base+[framesdir,f'--props={pp}',browser,'--sequence','--image-format=jpeg','--jpeg-quality=96','--concurrency=3','--frames=0-209','--muted'],cwd=ROOT/'remotion')
  (OUT/f'{name}.log').write_text(logs,encoding='utf-8')
 frames=sorted(framesdir.glob('*.jpeg'))
 if len(frames)!=210:raise RuntimeError(f'Incomplete sequence {name}: {len(frames)}')
 listing=framesdir/'sequence.txt';listing.write_text(''.join("file '"+f.as_posix()+"'\nduration 0.033333333333\n" for f in frames),encoding='utf-8')
 run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',listing,'-an','-vf','tpad=stop_mode=clone:stop_duration=3,scale=out_color_matrix=bt709:out_range=tv,setsar=1,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709','-r','30','-t','10','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',dest])
 meta=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',dest]));v=next(s for s in meta['streams'] if s['codec_type']=='video')
 run(['ffmpeg','-v','error','-i',dest,'-f','null','-'])
 checks={'1920x1080':v['width']==1920 and v['height']==1080,'fps30':v['r_frame_rate']=='30/1','h264':v['codec_name']=='h264','bt709_limited_yuv420p':v['pix_fmt']=='yuv420p' and v.get('color_space')=='bt709' and v.get('color_range')=='tv','silent':not any(s['codec_type']=='audio' for s in meta['streams']),'duration10':abs(float(meta['format']['duration'])-10)<.05,'decode':True}
 if not all(checks.values()):raise RuntimeError(str(checks))
 dump(receipt,{'input_hash':sig,'path':str(dest),'duration':10,'fps':30,'elapsed_seconds':round(time.monotonic()-start,2),'checks':checks,'semantic_reveals_seconds':TIMINGS[name],'source_ids':EVIDENCE[name],'source_url':'https://openai.com/index/introducing-chatgpt-images-2-5/','original_editorial_illustration':True,'not_model_output':True,'publishing_enabled':False,'max_episode_uses':1})
 run(['ffmpeg','-y','-v','error','-i',dest,'-vf','fps=1,scale=384:216,tile=5x2','-frames:v','1',OUT/f'{name}_contact.png'])
 print('Ready',name,checks,flush=True)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--stills',action='store_true');parser.add_argument('--name',choices=list(SPECS));args=parser.parse_args()
 dump(OUT/'art_direction.json',{'concepts':['Source-dominant callout crops','Original changing object with persistent invariants','Sequential text ledger'],'selected':'Original changing object with persistent invariants, plus normalized launch-claim chart and qualitative tradeoff','reason':'Makes continuity and selective changes visible without inventing UI or claiming model output; source crops are used elsewhere by editor.','proof_objects':{'latency':'normalized 100/50 visual based on E05','edit':'original poster schematic with selected vase','continuity':'same poster retains prior selected changes','sketch':'original wireframe and deterministic paper-cut output','tradeoff':'qualitative clock and precision target','check':'original poster and magnifier'},'frame_contract':{'canvas':'warm paper','ink':'black','accent':'red only selected region','camera':'locked','safe_inset':108,'max_focal_groups':3,'font':'Inter Variable','body_min_px':28,'label_min_px':23,'reading_order':'headline, object, relationship, takeaway'},'motion_intents':['enter','connect','emphasize'],'bounded_automatic_repairs':1,'semantic_reveals_seconds':TIMINGS,'brand':{'asset_path':'remotion/public/brands/openai.svg','source_url':'https://openai.com/brand/','verification':'Existing brand ledger and SOURCES.md; unmodified monochrome SVG preserved','sha256':hashlib.sha256((ROOT/'remotion/public/brands/openai.svg').read_bytes()).hexdigest(),'usage':'small product identification only'},'source_evidence':EVIDENCE,'duration_seconds':10,'rendered_motion_frames':210,'hold_frames':90,'publishing_enabled':False})
 direction=json.loads((OUT/'art_direction.json').read_text(encoding='utf-8'))
 direction['proof_objects']['edit']='Original Night Market event poster, Friday to Saturday; layout, artwork and other lettering stay fixed'
 direction['proof_objects']['sketch']='Original rough room wireframe to layout brief and flat illustrated room: window left, chair beside, clear wall for headline; not model output'
 direction['script_alignment_correction']='Main requested Friday-to-Saturday date edit, then room-layout sketch alignment. Each corrected clip rerendered independently; other final MP4s preserved.'
 dump(OUT/'art_direction.json',direction)
 for name in ([args.name] if args.name else SPECS):render(name,args.stills)
if __name__=='__main__':main()
