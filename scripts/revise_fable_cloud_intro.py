"""Replace only the first 5.5 seconds with the user-selected cached launch scene."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pipeline.render_v2 import write_concat

PARENT=ROOT/'data/episodes/episode_20260902_fable_mythos_v6_pointers'
EP=ROOT/'data/episodes/episode_20260902_fable_mythos_v7_cloud_intro'
SOURCE=ROOT/'data/episodes/episode_20260902_fable_mythos_v4_private/broll/anthropic_launch.mp4'
PARENT_VIDEO=PARENT/'Claude_Fable_Mythos_Article_Pointers_Private_1080p.mp4'
FINAL=EP/'Claude_Fable_Mythos_Cloud_Intro_Private_1080p.mp4'
SOURCE_IN=80.55
SOURCE_LENGTH=4.70

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
def sha(p):
    with p.open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()
def run(args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=600)
    if result.returncode:raise RuntimeError(result.stderr[-4000:])
    return result.stdout
def probe(p):return json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)]))
def ahash(p):return run(['ffmpeg','-v','error','-i',str(p),'-map','0:a:0','-c','copy','-f','hash','-hash','sha256','-']).strip()

def main():
    parent=read(PARENT/'revision_manifest.json');rows=read(PARENT/'storyboard.json')
    rights=read(SOURCE.parent/'private_use_record.json')
    assert sha(SOURCE)==rights['source_sha256']
    assert rows[0]['id']=='s000' and rows[0]['duration']==5.5
    assert SOURCE_IN+SOURCE_LENGTH < float(probe(SOURCE)['format']['duration'])
    segment=EP/'timeline_segments/s000.mp4';segment.parent.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(f'{sha(SOURCE)}:{SOURCE_IN}:{SOURCE_LENGTH}:165:v1'.encode()).hexdigest()
    receipt=segment.with_suffix('.json')
    if not(segment.exists() and receipt.exists() and read(receipt).get('input_hash')==digest and read(receipt).get('sha256')==sha(segment)):
        # Keep the original source motion at 1x; hold its last clean frame for 0.8s to preserve all downstream timing.
        vf=(f'trim=duration={SOURCE_LENGTH},setpts=PTS-STARTPTS,setsar=1,'
            'fps=30,tpad=stop_mode=clone:stop_duration=0.85,format=yuv420p')
        run(['ffmpeg','-y','-v','error','-ss',str(SOURCE_IN),'-i',str(SOURCE),'-an','-vf',vf,
             '-frames:v','165','-c:v','libx264','-preset','fast','-crf','17','-threads','2',
             '-pix_fmt','yuv420p','-video_track_timescale','15360',str(segment)])
        dump(receipt,{'input_hash':digest,'sha256':sha(segment),'source_in':SOURCE_IN,
                      'source_out':SOURCE_IN+SOURCE_LENGTH,'last_frame_hold_seconds':.8})
    paths=[segment if item['id']=='s000' else Path(item['path']) for item in parent['segments']]
    assert all(p.is_file() for p in paths)
    concat=write_concat(paths,segment.parent/'concat.txt')
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(concat),'-i',str(PARENT_VIDEO),
         '-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',str(FINAL)])
    rows[0].update(source_in=SOURCE_IN,source_reference_in=SOURCE_IN,asset_key='anthropic_cloud_logo',
                   edit_note='User-selected cloud-and-moon title animation; original source audio muted. Natural source motion, no extra zoom or transition.',
                   last_frame_hold_seconds=.8)
    dump(EP/'storyboard.json',rows)
    for name in ['script.json','parent_source_ledger.json']:
        shutil.copy2(PARENT/name,EP/name)
    (EP/'thumbnails').mkdir(exist_ok=True)
    shutil.copy2(PARENT/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg',EP/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg')
    manifest={'parent':str(PARENT_VIDEO),'parent_sha256':sha(PARENT_VIDEO),'final':str(FINAL),
              'changed_shots':['s000'],'publishing_enabled':False,'public_reuse_cleared':False,
              'source_url':rights['source_url'],'source_sha256':sha(SOURCE),
              'rights_basis':rights['basis'],'rights_record':str(SOURCE.parent/'private_use_record.json'),
              'user_reference':'C:/Users/kanag/AppData/Local/Temp/codex-clipboard-41641d46-0cdb-4db9-a357-8b17bbf6cc79.png',
              'new_paid_generation_calls':0,'narration':'Unchanged parent AAC stream, copied without re-encoding',
              'segments':[{'id':r['id'],'path':str(p),'sha256':sha(p),'changed':r['id']=='s000'} for r,p in zip(rows,paths)]}
    dump(EP/'revision_manifest.json',manifest)
    info=probe(FINAL);old_info=probe(PARENT_VIDEO);v=next(s for s in info['streams'] if s['codec_type']=='video')
    checks={'1920x1080_h264':(v['width'],v['height'],v['codec_name'])==(1920,1080,'h264'),
            'runtime_unchanged':abs(float(info['format']['duration'])-float(old_info['format']['duration']))<.01,
            'audio_bytes_identical':ahash(FINAL)==ahash(PARENT_VIDEO),
            '82_other_segments_unchanged':all(sha(Path(s['path']))==s['sha256'] for s in parent['segments'][1:]),
            'no_subtitle_stream':not any(s['codec_type']=='subtitle' for s in info['streams']),
            'script_identical':sha(EP/'script.json')==sha(PARENT/'script.json'),
            'thumbnail_identical':sha(EP/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg')==sha(PARENT/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg')}
    qc=EP/'qc';qc.mkdir(exist_ok=True)
    for time in [0,1.8,4.9,5.4667,5.5333,465.1]:
        run(['ffmpeg','-y','-v','error','-ss',str(time),'-i',str(FINAL),'-frames:v','1','-q:v','2',str(qc/f'frame_{time:.3f}.jpg')])
    # Direct comparison verifies the unchanged video packets, not just inputs to concatenation.
    tail=[]
    for p in [PARENT_VIDEO,FINAL]:
        tail.append(run(['ffmpeg','-v','error','-ss','5.5','-i',str(p),'-an','-c:v','copy','-f','hash','-hash','sha256','-']).strip())
    checks['remaining_video_packets_identical']=tail[0]==tail[1]
    decode=subprocess.run(['ffmpeg','-hide_banner','-i',str(FINAL),'-vf','blackdetect=d=0.12:pix_th=0.04:pic_th=0.98','-f','null','-'],capture_output=True,text=True,timeout=600)
    black=[l for l in decode.stderr.splitlines() if 'black_start:' in l]
    errors=[l for l in decode.stderr.splitlines() if 'Error' in l or 'Invalid' in l or 'corrupt' in l.lower()]
    checks['decode_clean']=decode.returncode==0 and not errors
    checks['no_blackouts']=not black
    report={'checks':checks,'technical_passed':all(checks.values()),'duration':info['format']['duration'],
            'sha256':sha(FINAL),'bytes':FINAL.stat().st_size,'public_release_ready':False,
            'visual_review':'pending first frame and transition inspection','black_events':black,'decode_errors':errors}
    dump(qc/'intro_qc.json',report)
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
