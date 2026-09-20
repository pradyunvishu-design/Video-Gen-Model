"""Restore the attached narrator profile and retain live demos without face-cams."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import produce_fable_mythos_episode as base
ORIGINAL=ROOT/'data/episodes/episode_20260902_fable_mythos'
PARENT=ROOT/'data/episodes/episode_20260902_fable_mythos_v2'
EP=ROOT/'data/episodes/episode_20260902_fable_mythos_v3'
ATTACHED=Path('C:/Users/kanag/Downloads/zubenelgenubi_connected_master (1).wav')
REFERENCE=ROOT/'output/voice_canary/measured_original_tech_host_v4_round2/zubenelgenubi_connected_master.wav'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8'))

def prepare():
    if sha(ATTACHED)!=sha(REFERENCE): raise RuntimeError('Attachment no longer matches the approved profile')
    EP.mkdir(exist_ok=True)
    for folder in ('research','cards','thumbnails','motion','media/brand'):
        (EP/folder).mkdir(parents=True,exist_ok=True)
        for source in (PARENT/folder).glob('*'):
            if source.is_file() and not (EP/folder/source.name).exists(): shutil.copy2(source,EP/folder/source.name)
    shutil.copy2(PARENT/'media/nasa_venus_topography.mp4',EP/'media/nasa_venus_topography.mp4')
    (EP/'audio').mkdir(exist_ok=True)
    for source in (ORIGINAL/'audio').glob('*'):
        if source.is_file() and not source.name.startswith('intro') and not (EP/'audio'/source.name).exists():
            shutil.copy2(source,EP/'audio'/source.name)
    for name in ('provider_usage.json','source_ledger.json'):
        if not (EP/name).exists(): shutil.copy2(PARENT/name,EP/name)
    script=read(PARENT/'script.json')
    script.pop('delivery_direction',None)
    script['version']='3.0'
    base.dump(EP/'script.json',script)
    reviewed=read(PARENT/'script_review.json')
    assert reviewed['passed'] and reviewed['script_hash']==sha(PARENT/'script.json')
    assert script['chapters']==read(PARENT/'script.json')['chapters']
    reviewed['inherited_spoken_text_review']={'source':str(PARENT/'script_review.json'),'reason':'All spoken paragraphs, source IDs and title unchanged. Only non-spoken version and narrator direction metadata changed.','original_script_hash':reviewed['script_hash']}
    reviewed['script_hash']=sha(EP/'script.json')
    base.dump(EP/'script_review.json',reviewed)
    base.dump(EP/'voice_selection.json',{'attachment':str(ATTACHED),'sha256':sha(ATTACHED),'exact_match':str(REFERENCE),'voice':'Zubenelgenubi','model':'gemini-3.1-flash-tts-preview','method':'Restore saved original preset and connected delivery; reuse identical reviewed body narration. Generate only the revised introduction. Reference is not looped and no new voice clone is claimed.'})
    clips=read(PARENT/'broll/approved_clips.json')
    for cid,clip in clips.items():
        if cid=='duncan_model_select':
            clip['editorial_filter']='crop=1408:792:512:288'
            clip['visible_range']=[2,8.8]
        elif cid=='duncan_prompt':
            clip['editorial_filter']="drawbox=x=0:y=800:w=488:h=280:color=0x141414:t=fill:enable='between(t+{source_in},4,8)',crop=1408:792:0:288"
            clip['visible_range']=[0,18]
        elif cid=='duncan_effort':
            # The face-cam sits in the otherwise blank lower-left page margin.
            # Do not invent the data obscured by the original presenter overlay.
            clip['editorial_filter']='drawbox=x=0:y=800:w=488:h=280:color=0xFAF9F6:t=fill'
            clip['visible_range']=[5,15.8]
        else:
            clip['editorial_filter']='crop=1408:792:512:0'
            clip['visible_range']=[0,12.5] if cid=='duncan_limitations' else [0,18]
        clip['edit_note']='Locked editorial crop or page-tone face-cam cover. Retain original moving cursor and product interactions, mute original audio, retain attribution. No generated fill.'
    base.dump(EP/'broll/approved_clips.json',clips)
    edits=read(PARENT/'edit_plan_overrides.json')
    edits['benchmarks_2']=['!duncan_effort:5','launch_04_detail','launch_05_detail']
    edits['benchmarks_3']=['docs_00_detail','!duncan_effort:8','launch_03_detail']
    edits['cost_verdict_4']=['!duncan_review:7','!duncan_limitations:0','@verdict']
    base.dump(EP/'edit_plan_overrides.json',edits)
    print('Prepared presenter-free revision; attached voice profile matched exactly',flush=True)

def preview():
    from pipeline.render_v2 import run_command
    from PIL import Image,ImageDraw,ImageFont
    clips=read(EP/'broll/approved_clips.json')
    folder=EP/'qc/face_free_previews'
    folder.mkdir(parents=True,exist_ok=True)
    sheet=Image.new('RGB',(1440,len(clips)*296),'#f3f0e9')
    draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    for i,(cid,c) in enumerate(clips.items()):
        a,b=c['visible_range']
        for j,t in enumerate((a+.1,(a+b)/2,b-.15)):
            path=folder/f'{cid}_{j}.jpg'
            vf=c['editorial_filter'].replace('{source_in}',str(t))+',scale=1920:1080:flags=lanczos,setsar=1'
            run_command(['ffmpeg','-y','-v','error','-ss',str(t),'-i',c['path'],'-vf',vf,'-frames:v','1',str(path)])
            with Image.open(path) as im: sheet.paste(im.resize((480,270)),(480*j,296*i))
            draw.text((480*j+8,296*i+272),f'{cid} +{t:.2f}s',font=font,fill='#202820')
    sheet.save(folder/'contact_sheet.jpg',quality=94)
    print(str(folder/'contact_sheet.jpg'),flush=True)

def verify():
    from scripts import verify_fable_mythos_delivery as checks
    checks.EP=EP
    checks.main()
    rows=read(EP/'storyboard.json')
    ledger=read(EP/'source_ledger.json')
    ledger['presenter_removal']=[{'shot':r['id'],'source':r['asset_source_url'],'start_seconds':r['source_reference_in'],'duration_seconds':r['duration'],'transform':r['editorial_filter'],'note':r['edit_note']} for r in rows if r.get('editorial_filter')]
    base.dump(EP/'source_ledger.json',ledger)
    with (EP/'upload_description.txt').open('a',encoding='utf-8') as handle:
        handle.write('\nAdditional excerpt edits: face-camera insets were removed using fixed editorial crops or a flat page-matched cover. Product interactions and cursor movement remain from the original source; no missing UI or chart data was generated.\n')
    from pipeline.render_v2 import run_command
    from PIL import Image,ImageDraw,ImageFont
    folder=EP/'qc/edited_clip_review'
    folder.mkdir(exist_ok=True)
    edited=[r for r in rows if r.get('editorial_filter')]
    video=EP/'Claude_Fable_51_and_Mythos_1080p.mp4'
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    for page in range((len(edited)+4)//5):
        batch=edited[page*5:(page+1)*5]
        sheet=Image.new('RGB',(1440,len(batch)*296),'#f3f0e9')
        draw=ImageDraw.Draw(sheet)
        for i,row in enumerate(batch):
            for j,offset in enumerate((.04,row['duration']/2,row['duration']-.08)):
                path=folder/f'{row["id"]}_{j}.jpg'
                run_command(['ffmpeg','-y','-v','error','-ss',str(row['start']+offset),'-i',str(video),'-frames:v','1',str(path)])
                with Image.open(path) as im: sheet.paste(im.resize((480,270)),(480*j,296*i))
                draw.text((480*j+6,296*i+272),f'{row["id"]} {row["start"]+offset:.2f}s',font=font,fill='#202820')
        sheet.save(folder/f'page_{page+1}.jpg',quality=94)
    base.dump(EP/'qc/voice_cache_proof.json',{'attachment_matches_saved_profile':sha(ATTACHED)==sha(REFERENCE),'reference_sha256':sha(ATTACHED),'body_audio_unchanged_from_matching_profile':all(sha(Path(c['path']))==sha(Path(c0['path'])) for c,c0 in zip(read(EP/'narration.json')['chapters'][1:],read(ORIGINAL/'narration.json')['chapters'][1:])),'new_intro_uses_same_model_and_voice':read(EP/'narration.json')['voice']=='Zubenelgenubi','new_intro_qc':read(EP/'audio/intro_qc.json')['passed'],'full_audio_qc':read(EP/'audio_qc.json')['passed'],'publishing_enabled':False})

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['prepare','narrate','audio_review','preview','assemble','verify'])
    args=parser.parse_args()
    if args.stage in ('narrate','audio_review','assemble'):
        base.EP=EP
        getattr(base,args.stage)()
    else: globals()[args.stage]()
