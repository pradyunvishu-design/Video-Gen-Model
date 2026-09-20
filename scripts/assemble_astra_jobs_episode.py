"""Narration-only, frame-exact Astra jobs edit using the existing source renderer."""
from __future__ import annotations
import argparse
import math
import io
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from scripts import assemble_images25_episode as renderer
from scripts.produce_images25_episode import read, dump, sha, run, probe
from pipeline.render_v2 import write_concat

EP = Path(__file__).resolve().parents[1]/'data/episodes/episode_20260919_astra_jobs'
OUT = EP/'edit'
FINAL = EP/'Astra_Jobs_Finance_Law_1080p.mp4'
FPS = 30

def configure():
    renderer.EP=EP
    renderer.OUT=OUT
    renderer.FINAL=FINAL

def validate(rows):
    cursor=0; used=Counter(); ids=set()
    for row in rows:
        assert row['id'] not in ids, 'Duplicate shot'
        ids.add(row['id'])
        limit=420 if row.get('purposeful_complete_demo') else 360
        assert row['start_frame']==cursor and 1 <= row['frames'] <= limit, row
        assert Path(row['path']).is_file() and row['source_url'] and row['relevance'], row
        used[row['asset_id']]+=1
        assert used[row['asset_id']] <= (1 if row['kind']=='motion' or row.get('original_editorial') else 2), row['asset_id']
        if row['kind']=='video':
            info=probe(Path(row['path']))
            video=next(s for s in info['streams'] if s['codec_type']=='video')
            assert row['frames']+round(row.get('offset',0)*FPS)<=int(video['nb_frames']), row['id']
        cursor+=row['frames']
    narration=Path(read(EP/'narration.json')['path'])
    expected=math.ceil(read(EP/'paragraph_timing.json')[-1]['end']*FPS)
    assert cursor==expected, (cursor, expected)
    return cursor

def render(segments_only=False):
    configure(); rows=read(EP/'edit_plan.json');frames=validate(rows)
    OUT.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        paths=list(pool.map(renderer.shot,rows))
    reveal_checks=supplemental_reveal_check(rows)
    if segments_only:return
    narration=Path(read(EP/'narration.json')['path'])
    adjudication=EP/'audio_qc_adjudicated.json'
    approved=read(adjudication) if adjudication.exists() else {}
    if not (approved.get('passed') and approved.get('audio_sha256')==sha(narration)
            and approved.get('source_qc_sha256')==sha(EP/'audio_qc.json')):
        raise RuntimeError('Current, hash-matched narration QC adjudication is required before final export')
    listing=write_concat(paths,OUT/'concat.txt')
    staged=OUT/'export.rendering.mp4'
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-i',str(narration),'-map','0:v:0','-map','1:a:0','-c:v','copy','-af','apad','-c:a','aac','-b:a','192k','-ar','48000','-t',str(frames/FPS),'-movflags','+faststart',str(staged)])
    run(['ffmpeg','-v','error','-i',str(staged),'-f','null','-'],timeout=1200)
    from scripts import assemble_dreamx_full as audio_qc
    audio_qc.OUT=OUT
    audio=audio_qc.audio_export_check(staged,narration)
    meta=probe(staged);v=next(s for s in meta['streams'] if s['codec_type']=='video')
    checks={'1080p':(v['width'],v['height'])==(1920,1080),'h264':v['codec_name']=='h264','fps30':v['r_frame_rate']=='30/1','exact_frames':int(v['nb_frames'])==frames,'narration_complete':float(meta['format']['duration'])>=float(probe(narration)['format']['duration']),'one_audio':sum(s['codec_type']=='audio' for s in meta['streams'])==1,'no_subtitles':not any(s['codec_type']=='subtitle' for s in meta['streams']),'full_decode':True,'narration_only':audio['passed'],'source_repetition':True,'supplemental_final_state_visible':reveal_checks['passed']}
    if not all(checks.values()):raise RuntimeError(str(checks))
    staged.replace(FINAL)
    dump(OUT/'technical_qc.json',{'checks':checks,'duration':float(meta['format']['duration']),'sha256':sha(FINAL),'shots':len(rows),'publishing_enabled':False,'visual_review':'pending actual exported-frame review','audio_identity_basis':'One approved narration master only; no source audio or music mapped'})
    print(str(FINAL),flush=True)

def supplemental_reveal_check(rows):
    """Regression gate for stale reveal timing in shorter editorial inserts."""
    import numpy as np
    from PIL import Image
    checks=[]
    for row in rows:
        if not row.get('original_editorial'):continue
        source=Path(row['path']);state=source.with_name(source.stem+'_2.png')
        assert row['frames']/FPS >= 3.9, 'Not enough time for the final editorial state'
        sample=3.7
        segment=OUT/'segments'/(row['id']+'.mp4')
        data=subprocess.run(['ffmpeg','-v','error','-ss',str(sample),'-i',str(segment),'-frames:v','1','-f','image2pipe','-vcodec','png','pipe:1'],capture_output=True,check=True).stdout
        decoded=np.asarray(Image.open(io.BytesIO(data)).convert('RGB'),dtype=np.float32)
        expected=np.asarray(Image.open(state).convert('RGB'),dtype=np.float32)
        previous=np.asarray(Image.open(source.with_name(source.stem+'_1.png')).convert('RGB'),dtype=np.float32)
        changed=np.max(np.abs(expected-previous),axis=2)>20
        assert np.count_nonzero(changed)>100, 'Final state has no meaningful reveal'
        error=float(np.mean(np.abs(decoded-expected)))
        reveal_error=float(np.mean(np.abs(decoded[changed]-expected[changed])))
        stale_error=float(np.mean(np.abs(previous[changed]-expected[changed])))
        checks.append({'shot':row['id'],'asset':row['asset_id'],'actual_shot_seconds':row['frames']/FPS,'sample_seconds':sample,'mean_pixel_error':error,'final_reveal_pixel_error':reveal_error,'stale_state_negative_control_error':stale_error,'reveal_pixels':int(np.count_nonzero(changed)),'expected_final_state_sha256':sha(state),'segment_sha256':sha(segment),'passed':error<3.0 and reveal_error<18 and stale_error>=18})
    result={'passed':bool(checks) and all(c['passed'] for c in checks),'method':'Decoded actual rendered segment at3.7s compared with its authored final state, specifically masking the pixels introduced by the last reveal. A stale previous state is checked as negative control. Threshold18/255 on changed pixels tolerates H264/chroma conversion but rejects missing objects.','checks':checks}
    dump(OUT/'supplemental_reveal_qc.json',result)
    if not result['passed']:raise RuntimeError('An editorial shot ends before its final visual state appears')
    return result

def contacts():
    configure();renderer.contacts()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['render','segments','contacts','validate']);arg=parser.parse_args()
    if arg.stage=='segments':render(True)
    elif arg.stage=='validate':print(validate(read(EP/'edit_plan.json')))
    else:globals()[arg.stage]()
