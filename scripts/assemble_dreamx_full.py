"""Resume the approved DreamX edit without new narration or provider spending."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.produce_dreamx_episode import EP, read, dump, sha, run as _run, probe
from scripts.render_dreamx_source_motion import render_source_shot
from pipeline.render_v2 import write_concat

OUT = EP / 'full_edit'
FINAL = EP / 'DreamX_Creator_8min_1080p.mp4'
FPS = 30


def run(command, timeout=600):
    return _run([str(value) for value in command], timeout=timeout)


def promote_export(staged, destination):
    # Windows preview/QA readers may hold the current MP4 open. An identical
    # verified export needs no replacement; retain the staged file for recovery.
    if destination.exists() and sha(staged)==sha(destination):
        return False
    staged.replace(destination)
    return True


def validate_audio_binding(binding, hashes, seconds):
    for key,value in hashes.items():
        if binding.get(key)!=value:
            raise ValueError('Audio review is stale: '+key)
    if abs(seconds-binding['duration_seconds'])>.03 or not 478<=seconds<480:
        raise ValueError('Narration is incomplete, too long, or no longer the reviewed duration')


def audio_gate():
    narration=EP/'narration_zubenelgenubi_8min.wav'
    hashes={'narration_sha256':sha(narration),'script_sha256':sha(EP/'script.json'),
            'audio_qc_sha256':sha(EP/'audio_qc.json'),
            'voice_review_sha256':sha(EP/'voice_outlier_review.json')}
    validate_audio_binding(read(EP/'audio_review_binding.json'),hashes,float(probe(narration)['format']['duration']))
    if not read(EP/'audio_qc.json').get('passed'):
        raise RuntimeError('Narration gate not cleared')


def audio_export_check(video, narration):
    import numpy as np
    def decode(path):
        p=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-vn','-ac','1','-ar','8000',
                          '-f','f32le','pipe:1'],capture_output=True,check=True)
        return np.frombuffer(p.stdout,dtype='<f4')
    reference,exported=decode(narration),decode(video)
    if len(exported)<len(reference):raise RuntimeError('Export truncates the approved narration')
    correlations=[]
    for start in range(0,len(reference),40000):
        a=reference[start:start+40000];b=exported[start:start+len(a)]
        if len(a)<100 or np.sqrt(np.mean(a*a))<.0003:continue
        a=a-a.mean();b=b-b.mean()
        correlations.append(float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-12)))
    result={'passed':bool(correlations) and min(correlations)>.97,
            'windows':len(correlations),'minimum_waveform_correlation':min(correlations) if correlations else None,
            'method':'Five-second waveform windows compare the entire decoded AAC export with approved narration; only ending padding is excluded'}
    if not result['passed']:raise RuntimeError('Export audio differs from the approved full narration')
    dump(OUT/'audio_export_qc.json',result)
    return result


def prepare_plan(document):
    rows = document if isinstance(document, list) else document['shots']
    rows = [dict(row) for row in rows]
    if not rows:
        raise ValueError('No approved shots')
    end = 0.0
    end_frame = 0
    seen = Counter()
    ids = set()
    for row in rows:
        if row['id'] in ids:
            raise ValueError('Duplicate shot ID')
        ids.add(row['id'])
        start, duration = float(row['start']), float(row['duration'])
        if abs(start-end) > .06 or duration <= 0 or duration > 12.05:
            raise ValueError(f"Timeline gap/overlong shot: {row['id']} {start} {end} {duration}")
        row['start_frame'] = round(start*FPS)
        row['end_frame'] = round((start+duration)*FPS)
        if row['start_frame'] != end_frame:
            raise ValueError(f"Frame-level timeline gap: {row['id']}")
        end_frame = row['end_frame']
        row['duration_frames'] = row['end_frame']-row['start_frame']
        row['duration'] = row['duration_frames']/FPS
        end = start+duration
        if not row.get('relevance') or not row.get('rationale'):
            raise ValueError(f"Shot has no semantic rationale: {row['id']}")
        if row['kind'] not in {'source','motion','teaser','editorial'}:
            raise ValueError(f"Unfilled visual gap: {row['id']}")
        if row['kind'] != 'editorial':
            source = Path(row['source_path'])
            if not source.is_absolute():
                source = EP/source
            row['source_path'] = str(source)
            if not source.is_file():
                raise ValueError(f"Missing shot source: {row['id']}")
            seen[str(source.resolve())] += 1
            limit = 1 if row['kind']=='motion' else 2
            if seen[str(source.resolve())] > limit:
                raise ValueError(f"Repeated source exceeds limit: {row['id']}")
        elif not row.get('concept'):
            raise ValueError(f"Editorial gap has no concept: {row['id']}")
    if abs(end-480) > .15:
        raise ValueError(f'Full episode must end at 480 seconds, got {end}')
    rows[-1]['end_frame'] = 480*FPS
    rows[-1]['duration_frames'] = rows[-1]['end_frame']-rows[-1]['start_frame']
    rows[-1]['duration'] = rows[-1]['duration_frames']/FPS
    return rows


def normalized_clip(row, dest):
    source=Path(row['source_path'])
    spec={'row':row,'source_hash':sha(source),'version':1}
    digest=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
    receipt_path=dest.with_suffix('.render.json')
    if dest.exists() and receipt_path.exists():
        receipt=read(receipt_path)
        if receipt.get('input_hash')==digest and receipt.get('output_sha256')==sha(dest):
            return dict(receipt,cached=True)
    if row['kind']=='teaser':
        # Author-owned repository montage is illustrative, not a generated sample.
        still=OUT/(row['id']+'.png')
        run(['ffmpeg','-y','-v','error','-i',source,'-vf',
             'scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xF3F2ED',
             '-frames:v','1',still])
        return render_source_shot(still,dest,row['duration'],cursor=False,zoom=1.022)
    actual=float(probe(source)['format']['duration'])
    if row['duration'] > actual+.05:
        raise ValueError('Do not freeze/loop an explanatory graphic to fill missing footage')
    run(['ffmpeg','-y','-v','error','-i',source,'-an','-frames:v',row['duration_frames'],
         '-vf','fps=30,setsar=1,format=yuv420p','-c:v','libx264','-preset','veryfast',
         '-crf','18','-threads','2','-color_range','tv','-colorspace','bt709',
         '-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',dest])
    receipt={'path':str(dest),'input_hash':digest,'output_sha256':sha(dest),'cached':False}
    dump(receipt_path,receipt)
    return receipt


def render_row(row):
    dest=OUT/'segments'/(row['id']+'.mp4')
    dest.parent.mkdir(parents=True,exist_ok=True)
    if row['kind']=='source':
        annotation=None
        if Path(row['source_path']).name=='repository_input_focus.png':
            annotation=read(EP/'captures/source_focus.json')
        result=render_source_shot(row['source_path'],dest,row['duration'],
            focus=row.get('focus'),annotation=annotation,cursor=True,
            framing=row.get('framing'),zoom=1.028)
    elif row['kind']=='editorial':
        from scripts.render_dreamx_editorial import render_editorial
        result=render_editorial(row,dest)
    else:
        result=normalized_clip(row,dest)
    print(('Cached ' if result.get('cached') else 'Rendered ')+row['id'],flush=True)
    return str(dest)


def render(kind=None):
    audio_gate()
    rows=prepare_plan(read(EP/'full_edit_plan_locked.json'))
    OUT.mkdir(exist_ok=True)
    dump(OUT/'timeline.json',rows)
    selected=[row for row in rows if kind is None or row['kind']==kind]
    errors=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(render_row,row):row['id'] for row in selected}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as error:
                errors.append({'shot':futures[future],'error':str(error)[-1200:]})
                print('Failed '+futures[future]+': '+str(error)[-300:],flush=True)
    if errors:
        dump(OUT/'render_errors.json',errors)
        raise RuntimeError(f'{len(errors)} shot(s) failed; completed segments remain cached')
    if kind:
        return
    paths=[OUT/'segments'/(row['id']+'.mp4') for row in rows]
    source_receipts=[read((OUT/'segments'/(row['id']+'.mp4')).with_suffix('.motion.json')) for row in rows if row['kind']=='source']
    measured_underlines=sum(r['validated_underlines'] for r in source_receipts)
    listing=write_concat(paths,OUT/'concat.txt')
    narration=EP/'narration_zubenelgenubi_8min.wav'
    temp=OUT/'DreamX_Creator_8min_1080p.rendering.mp4'
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',listing,
         '-i',narration,'-map','0:v:0','-map','1:a:0','-c:v','copy',
         '-af','apad','-c:a','aac','-b:a','192k','-ar','48000','-t','480',
         '-movflags','+faststart',temp])
    meta=probe(temp)
    v=next(s for s in meta['streams'] if s['codec_type']=='video')
    a=next(s for s in meta['streams'] if s['codec_type']=='audio')
    run(['ffmpeg','-v','error','-i',temp,'-f','null','-'],timeout=1200)
    audio_check=audio_export_check(temp,narration)
    checks={'1080p':(v['width'],v['height'])==(1920,1080),
            'eight_minutes':abs(float(meta['format']['duration'])-480)<.1,
            'h264':v['codec_name']=='h264','fps30':v['r_frame_rate']=='30/1',
            'aac':a['codec_name']=='aac','exactly_one_audio_track':sum(s['codec_type']=='audio' for s in meta['streams'])==1,
            'no_subtitles':not any(s['codec_type']=='subtitle' for s in meta['streams']),
            'full_decode':True,'audio_qc':True,'narration_not_truncated':audio_check['passed'],
            'every_source_has_directed_motion':all(1<r['spec']['zoom']<=1.03 for r in source_receipts),
            'measured_intro_underlines':measured_underlines==2,
            'timeline_contiguous':all(a['end_frame']==b['start_frame'] for a,b in zip(rows,rows[1:]))}
    if not all(checks.values()):
        raise RuntimeError(f'Final technical QC failed: {checks}')
    promote_export(temp,FINAL)
    dump(OUT/'technical_qc.json',{'checks':checks,'artifact':str(FINAL),'sha256':sha(FINAL),
         'duration':float(meta['format']['duration']),'shot_count':len(rows),
         'narration_sha256':sha(narration),'visual_review':'pending','publishing_enabled':False})
    print('Assembled '+str(FINAL),flush=True)


def contact_sheets():
    from PIL import Image, ImageDraw, ImageFont
    rows=read(OUT/'timeline.json')
    review=OUT/'review'
    review.mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    for page in range((len(rows)+11)//12):
        sheet=Image.new('RGB',(1280,636),'#F3F2ED')
        d=ImageDraw.Draw(sheet)
        for cell,row in enumerate(rows[page*12:(page+1)*12]):
            timestamp=row['start_frame']/FPS+row['duration']*.56
            path=review/(row['id']+'.jpg')
            run(['ffmpeg','-y','-v','error','-ss',timestamp,'-i',FINAL,
                 '-frames:v','1','-vf','scale=320:180:flags=lanczos',path])
            x,y=(cell%4)*320,(cell//4)*212
            with Image.open(path) as im:sheet.paste(im,(x,y))
            d.text((x+5,y+184),f'{timestamp:.1f}s {row["id"]}',font=font,fill='#24312E')
        sheet.save(review/f'contact_{page+1:02d}.jpg',quality=95)
    print('Review sheets: '+str(review),flush=True)


def motion_check():
    import numpy as np
    rows=read(OUT/'timeline.json')
    results=[]
    for row in rows:
        if row['kind']!='source':continue
        clip=OUT/'segments'/(row['id']+'.mp4')
        p=subprocess.run(['ffmpeg','-v','error','-i',str(clip),'-vf','fps=2,scale=320:180',
                          '-pix_fmt','gray','-f','rawvideo','pipe:1'],capture_output=True,check=True)
        frames=np.frombuffer(p.stdout,np.uint8).reshape((-1,180,320)).astype(np.float32)
        changes=np.abs(np.diff(frames,axis=0)).mean(axis=(1,2))
        results.append({'shot':row['id'],'samples':len(frames),
                        'min_half_second_pixel_change':float(changes.min()),
                        'all_intervals_move':bool(np.all(changes>.03))})
    report={'passed':bool(results) and all(r['all_intervals_move'] for r in results),
            'scope':'Every source shot sampled twice per second; verifies motion, not a substitute for visual readability review',
            'shots':results}
    dump(OUT/'source_motion_qc.json',report)
    print('Source motion samples passed:',report['passed'],len(results))


def cut_sheets():
    from PIL import Image, ImageDraw, ImageFont
    rows=read(OUT/'timeline.json')
    frames=[f for row in rows[1:] for f in (row['start_frame']-1,row['start_frame'])]
    review=OUT/'cut_review';review.mkdir(exist_ok=True)
    selection='+'.join(f"between(n,{row['start_frame']-1},{row['start_frame']})" for row in rows[1:])
    run(['ffmpeg','-y','-v','error','-i',FINAL,'-vf',f"select='{selection}',scale=240:135",
         '-fps_mode','vfr','-frames:v',len(frames),review/'frame_%03d.jpg'],timeout=1200)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    for page in range((len(frames)+23)//24):
        sheet=Image.new('RGB',(960,966),'#F3F2ED');draw=ImageDraw.Draw(sheet)
        for cell,frame in enumerate(frames[page*24:(page+1)*24]):
            i=page*24+cell+1;x=(cell%4)*240;y=(cell//4)*161
            with Image.open(review/f'frame_{i:03d}.jpg') as im:sheet.paste(im,(x,y))
            draw.text((x+4,y+138),f'{frame/FPS:.3f}s',font=font,fill='#24312E')
        sheet.save(review/f'cuts_{page+1:02d}.jpg',quality=95)
    print('Every cut boundary extracted:',len(frames)//2)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--kind',choices=['source','motion','teaser','editorial'])
    parser.add_argument('--contacts',action='store_true')
    parser.add_argument('--motion-check',action='store_true')
    parser.add_argument('--cuts',action='store_true')
    args=parser.parse_args()
    if args.cuts:cut_sheets()
    elif args.motion_check:motion_check()
    elif args.contacts:contact_sheets()
    else:render(args.kind)
