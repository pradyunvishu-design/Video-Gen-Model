"""Scoped revision: remove graphic annotations; preserve v2 edit and narration."""
from __future__ import annotations
import argparse
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path
from scripts import assemble_images25_episode as assembler
from scripts import revise_images25_broll as previous
from scripts.produce_images25_episode import EP, read, dump, sha, run

REV = EP/'revision_v3'
BASE = EP/'revision_v2'
FINAL = EP/'ChatGPT_Images_25_Clean_Graphics_1080p.mp4'
CHANGED = {'motion_edit', 'motion_tradeoff', 'motion_check'}


def plan():
    original = read(BASE/'edit_plan.json')
    rows = copy.deepcopy(original)
    previous.validate_reviewed_sources(rows)
    for row in rows:
        if row['asset_id'] in CHANGED:
            row['path'] = str(REV/'motion'/(row['asset_id'].removeprefix('motion_')+'.mp4'))
    assert assembler.validate(rows) == assembler.validate(original)
    for old, new in zip(original, rows):
        assert {k:v for k,v in old.items() if k != 'path'} == {k:v for k,v in new.items() if k != 'path'}
        if old['asset_id'] not in CHANGED:
            assert old == new
    dump(REV/'edit_plan.json', rows)
    dump(REV/'changes.json', {
        'base_video':str(previous.FINAL), 'base_video_sha256':sha(previous.FINAL),
        'base_plan_sha256':sha(BASE/'edit_plan.json'),
        'changed_assets':sorted(CHANGED),
        'removed':'Red date-selection box and leader; poster leader; comparison bracket; red inspection box and leader',
        'preserved':'Chart axes, diagram geometry, article highlights, source citations, B-roll, shot timing, narrator',
        'narration_sha256':sha(Path(read(EP/'narration.json')['path'])),
        'frames':sum(r['frames'] for r in rows), 'publishing_enabled':False,
    })


def configure():
    assembler.OUT = REV/'edit'
    assembler.FINAL = FINAL
    assembler.read = lambda path: read(REV/'edit_plan.json') if Path(path) == EP/'edit_plan.json' else read(path)


def render():
    rows=read(REV/'edit_plan.json')
    previous.validate_reviewed_sources(rows)
    configure()
    dest=assembler.OUT/'segments'
    dest.mkdir(parents=True,exist_ok=True)
    for row in rows:
        for suffix in ('.mp4','.json'):
            source=BASE/'edit/segments'/(row['id']+suffix)
            target=dest/(row['id']+suffix)
            if source.is_file() and not target.exists():shutil.copy2(source,target)
    assembler.render()


def verify():
    changes=read(REV/'changes.json')
    technical=read(REV/'edit/technical_qc.json')
    assert sha(previous.FINAL)==changes['base_video_sha256']
    assert sha(BASE/'edit_plan.json')==changes['base_plan_sha256']
    assert sha(Path(read(EP/'narration.json')['path']))==changes['narration_sha256']
    assert sha(FINAL)==technical['sha256'] and all(technical['checks'].values())
    rows=read(REV/'edit_plan.json')
    previous.validate_reviewed_sources(rows)
    unchanged=0
    for row in rows:
        if row['asset_id'] not in CHANGED:
            name=row['id']+'.mp4'
            assert sha(BASE/'edit/segments'/name)==sha(REV/'edit/segments'/name)
            unchanged+=1
    result=subprocess.run(['ffmpeg','-hide_banner','-i',str(FINAL),'-an','-vf','scale=320:180,blackdetect=d=0.3:pix_th=0.02:pic_th=0.98','-f','null','-'],capture_output=True,text=True,encoding='utf-8',check=True,timeout=1200)
    black=re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)',result.stderr)
    assert not black
    folder=REV/'review';folder.mkdir(exist_ok=True)
    for row in rows:
        if row['asset_id'] not in CHANGED:continue
        for label,offset in [('entry',.08),('developing',2),('settled',6.8),('exit',9.9)]:
            run(['ffmpeg','-y','-v','error','-ss',str(row['start_frame']/30+offset),'-i',str(FINAL),'-frames:v','1',str(folder/(row['asset_id']+'_'+label+'.png'))])
    shutil.copy2(BASE/'active_source_ledger.json',REV/'active_source_ledger.json')
    dump(REV/'qc.json',{'artifact':str(FINAL),'sha256':sha(FINAL),'technical':technical['checks'],
        'black_intervals':black,'unchanged_segments_verified_by_hash':unchanged,
        'duration':technical['duration'],'narration_sha256':changes['narration_sha256'],
        'visual_review':'pending','source_audio_used':False,'publishing_enabled':False})
    print(json.dumps(read(REV/'qc.json'),indent=2))


def thumbnail_report():
    from PIL import Image
    folder=EP/'thumbnails'
    artifact=folder/'images25_galaxy_v02.jpg'
    with Image.open(artifact) as image:assert image.size == (1920,1080)
    original=read(folder/'manifest.json')
    dump(folder/'images25_galaxy_v02_manifest.json',{
        'artifact':str(artifact),'sha256':sha(artifact),'dimensions':[1920,1080],
        'headline':'IT CAN DO WHAT?','topic':'ChatGPT Images 2.5',
        'method':'Built-in image tool, reference-assisted image edit; Lanczos export normalization',
        'image_calls':1,'prompt_path':str(folder/'images25_galaxy_v02_prompt.md'),
        'reference_proof':original['proof'],'brand_reference':original['logo'],
        'proof_treatment':'Entire right-hand proof region obscured edge to edge; not an unmodified product screenshot',
        'logo_treatment':'Reference-assisted raster reproduction, not a byte-identical SVG composite',
        'visual_reference':['output/thumbnails/astra-particles/ChatGPT_Astra_Particles_1080p.jpg','output/thumbnails/astra-space/ChatGPT_Astra_Meet_Astra_1080p.jpg'],
        'review':{'status':'pass','hard_blockers':[],'soft_signal_categories':[],
            'evidence':['Full frame checked: near-black galaxy, ice-blue/white headline, single straight arrow.',
                'Entire proof region is blurred, including all four edges; logo, arrow and type remain crisp.',
                '320x180 color and grayscale previews checked: main hook readable and image separated from background.'],
            'limitations':['Does not guarantee click-through performance or establish public reuse rights.']},
        'publishing_enabled':False,
    })


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['plan','render','verify','thumbnail_report'])
    globals()[parser.parse_args().stage]()
