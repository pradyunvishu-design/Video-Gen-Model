"""Frame-exact, resumable source-led edit for the Images 2.5 episode."""
from __future__ import annotations
import argparse, hashlib, json, math, subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from scripts.produce_images25_episode import EP, read, dump, sha, run, probe
from scripts.render_dreamx_source_motion import render_source_shot
from pipeline.render_v2 import write_concat

OUT=EP/'edit'
FINAL=EP/'ChatGPT_Images_25_1080p.mp4'
FPS=30

def validate(rows):
    cursor=0;seen=Counter();ids=set()
    for row in rows:
        if row['id'] in ids:raise ValueError('Duplicate shot ID')
        ids.add(row['id'])
        if row['start_frame']!=cursor or not 1<=row['frames']<=360:
            raise ValueError('Gap or overlong shot: '+row['id'])
        cursor+=row['frames']
        p=Path(row['path'])
        if not p.is_file() or not row.get('relevance') or not row.get('source_url'):
            raise ValueError('Missing media/provenance: '+row['id'])
        seen[row['asset_id']]+=1
        if seen[row['asset_id']]>(1 if row['kind']=='motion' else 2):
            raise ValueError('Repeated media: '+row['asset_id'])
    if not 420<=cursor/FPS<=480:raise ValueError('Video must be seven to eight minutes')
    return cursor

def shot(row):
    dest=OUT/'segments'/(row['id']+'.mp4');dest.parent.mkdir(parents=True,exist_ok=True)
    seconds=row['frames']/FPS
    digest=hashlib.sha256(json.dumps({'row':row,'hash':sha(Path(row['path'])),'renderer':sha(Path(__file__))},sort_keys=True).encode()).hexdigest()
    receipt=dest.with_suffix('.json')
    if dest.exists() and receipt.exists() and read(receipt).get('input_hash')==digest and read(receipt).get('output_hash')==sha(dest):return dest
    if row['kind'] in {'article','picture'}:
        annotation=read(Path(row['annotation_path'])) if row.get('annotation_path') else None
        if annotation:
            annotation=json.loads(json.dumps(annotation))
            for a in annotation.get('annotations',[]):
                a['start']=min(.8,seconds*.15);a['end']=seconds-.15
        base=dest.with_name(dest.stem+'_base.mp4')
        result=render_source_shot(row['path'],base,seconds,annotation=annotation,cursor=False,framing=row.get('framing'),focus=row.get('focus'),zoom=1.014)
        if annotation and not result.get('validated_underlines'):
            raise ValueError('Article underline did not validate: '+row['id'])
        command=['ffmpeg','-y','-v','error','-i',str(base)]
    else:
        offset=float(row.get('offset',0));available=float(probe(Path(row['path']))['format']['duration'])
        if offset+seconds>available+.065:raise ValueError('Clip would freeze or loop: '+row['id'])
        command=['ffmpeg','-y','-v','error','-ss',str(offset),'-i',row['path']]
    filters=['scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos','pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xF4F3EF','fps=30','setsar=1','format=yuv420p']
    # Sole source identification: no content-type badges, headers or subtitles.
    if row['kind']=='video':
        filters.append("drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='Source — OpenAI':fontsize=23:fontcolor=white:shadowcolor=black:shadowx=1:shadowy=1:box=1:boxcolor=black@0.45:boxborderw=8:x=52:y=h-55")
    command+=['-an','-frames:v',str(row['frames']),'-vf',','.join(filters),'-c:v','libx264','-preset','veryfast','-crf','18','-threads','2','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',str(dest)]
    run(command)
    exported=probe(dest);stream=next(s for s in exported['streams'] if s['codec_type']=='video')
    if int(stream.get('nb_frames',0))!=row['frames']:
        raise ValueError('Rendered frame count does not cover planned speech: '+row['id'])
    dump(receipt,{'input_hash':digest,'output_hash':sha(dest),'path':str(dest)})
    print('Rendered',row['id'],flush=True);return dest

def render(segments_only=False):
    rows=read(EP/'edit_plan.json');frames=validate(rows)
    OUT.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:paths=list(pool.map(shot,rows))
    if segments_only:return
    if not read(EP/'audio_qc.json')['passed']:raise RuntimeError('Narration QC unresolved')
    listing=write_concat(paths,OUT/'concat.txt');narration=Path(read(EP/'narration.json')['path'])
    if float(probe(narration)['format']['duration'])>frames/FPS:raise ValueError('Narration would be cut off')
    staged=OUT/'export.rendering.mp4'
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-i',str(narration),'-map','0:v:0','-map','1:a:0','-c:v','copy','-af','apad','-c:a','aac','-b:a','192k','-ar','48000','-t',str(frames/FPS),'-movflags','+faststart',str(staged)])
    run(['ffmpeg','-v','error','-i',str(staged),'-f','null','-'],timeout=1200)
    from scripts import assemble_dreamx_full as qc
    qc.OUT=OUT;audio=qc.audio_export_check(staged,narration)
    meta=probe(staged);v=next(s for s in meta['streams'] if s['codec_type']=='video')
    checks={'1080p':(v['width'],v['height'])==(1920,1080),'h264':v['codec_name']=='h264','fps30':v['r_frame_rate']=='30/1','duration':420<=float(meta['format']['duration'])<=480,'one_audio':sum(s['codec_type']=='audio' for s in meta['streams'])==1,'no_subtitles':not any(s['codec_type']=='subtitle' for s in meta['streams']),'full_decode':True,'narration_only':audio['passed'],'source_repetition':True}
    if not all(checks.values()):raise RuntimeError(str(checks))
    staged.replace(FINAL)
    dump(OUT/'technical_qc.json',{'checks':checks,'duration':float(meta['format']['duration']),'sha256':sha(FINAL),'shots':len(rows),'publishing_enabled':False,'visual_review':'pending'})
    print(str(FINAL),flush=True)

def contacts():
    from PIL import Image,ImageDraw,ImageFont
    rows=read(EP/'edit_plan.json');folder=OUT/'review';folder.mkdir(exist_ok=True,parents=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    for page in range(math.ceil(len(rows)/12)):
        canvas=Image.new('RGB',(1440,1008),'#222222');draw=ImageDraw.Draw(canvas)
        for j,row in enumerate(rows[page*12:(page+1)*12]):
            dest=folder/(row['id']+'.jpg');t=(row['start_frame']+row['frames']*.55)/FPS
            run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',str(FINAL),'-frames:v','1','-vf','scale=480:270',str(dest)])
            x=(j%3)*480;y=(j//3)*252
            im=Image.open(dest);im.thumbnail((480,226));canvas.paste(im,(x,y));draw.text((x+10,y+227),f'{t:.1f}s {row["id"]}',font=font,fill='white')
        canvas.save(folder/f'contact_{page+1}.jpg')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['render','segments','contacts']);a=p.parse_args()
    if a.stage=='segments':render(segments_only=True)
    else:globals()[a.stage]()
