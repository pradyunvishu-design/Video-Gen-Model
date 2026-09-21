"""Speech-aligned Qwen source edit using the existing verified episode assembler."""
from __future__ import annotations
import argparse
import math
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from scripts import assemble_images25_episode as assembler
from scripts.produce_qwen21_episode import EP, PUBLIC_URLS, shared, audio_fingerprints

FINAL=EP/'Qwen_Image_21_Beyond_Generate_1080p.mp4'

# Each beat maps to the specific words in one approved paragraph. Motion is
# restricted to explanatory passages; source views are never random filler.
BEATS={
 '01_hook_0':['img:example-31','img:example-32','cap:repo_local_editing_example'],
 '01_hook_1':['cap:repo_unified_creation','cap:model_card_overview','img:example-04'],
 '01_hook_2':['cap:repo_native_transparency_examples','cap:model_license_notice'],
 '02_alpha_0':['motion:opaque','cap:repo_native_rgba'],
 '02_alpha_1':['motion:alpha_channel','cap:repo_rgba_prompt'],
 '02_alpha_2':['img:example-04:light','img:example-05:light'],
 '02_alpha_3':['motion:alpha','img:example-05:dark'],
 '03_edit_0':['img:example-32:detail','cap:repo_single_edit_code'],
 '03_edit_1':['cap:repo_local_masks','motion:edit'],
 '03_edit_2':['img:example-18','img:example-19'],
 '03_edit_3':['cap:repo_local_editing_example','cap:repo_single_edit_code'],
 '04_references_0':['img:example-15','img:example-16'],
 '04_references_1':['img:example-16:detail','cap:repo_multireference_code'],
 '04_references_2':['motion:references','cap:repo_ten_references'],
 '04_references_3':['img:example-31:detail','cap:repo_product_fidelity'],
 '05_size_0':['cap:repo_architecture_7b','motion:components'],
 '05_size_1':['cap:repo_resolution_settings','cap:repo_architecture_encoder'],
 '05_size_2':['cap:repo_memory_offload','cap:comfy_native_support'],
 '05_size_3':['motion:workflow','cap:model_cpu_offload'],
 '06_license_0':['cap:license_noncommercial_grant','motion:permission'],
 '06_license_1':['cap:license_commercial_permission','cap:license_research_definition'],
 '06_license_2':['cap:license_commercial_permission','cap:model_license_notice'],
 '06_license_3':['cap:license_research_definition','cap:model_card_overview'],
 '07_decision_0':['motion:checks','cap:repo_native_rgba'],
 '07_decision_1':['img:example-26','img:example-44'],
 '07_decision_2':['img:example-15:detail','img:example-42'],
 '07_decision_3':['img:example-06','img:example-42:detail'],
 '07_decision_4':['img:example-38','cap:repo_unified_creation','motion:outro'],
}

def picture(asset,variant='full'):
    """Native source imagery, not synthesized B-roll; flatten actual PNG alpha."""
    source=Path(asset['path']);dest=EP/'edit/stills'/f'{asset["id"]}_{variant}.png'
    dest.parent.mkdir(parents=True,exist_ok=True)
    receipt=dest.with_suffix('.source.json')
    if dest.exists() and receipt.exists():
        previous=shared.read(receipt)
        if previous.get('source_hash')==shared.sha(source) and previous.get('output_hash')==shared.sha(dest) and previous.get('variant')==variant:
            return dest
    im=Image.open(source).convert('RGBA')
    if variant=='detail':
        # Deliberate, documented detail crops rather than simulated mouse motion.
        crops={'example-31':(.18,.22,.9,.89),'example-32':(.2,.39,.66,.92),
               'example-16':(.03,.02,.43,.98),'example-15':(.02,.01,.34,.99),
               'example-42':(.48,0,1,1)}
        crop=crops[asset['id']]
        im=im.crop(tuple(round(v*(im.width if i%2==0 else im.height)) for i,v in enumerate(crop)))
    bg='#17221F' if variant=='dark' else '#F2F0E9'
    out=Image.new('RGBA',(1920,1080),bg)
    ratio=min(1680/im.width,890/im.height,2.5)
    im=im.resize((round(im.width*ratio),round(im.height*ratio)),Image.Resampling.LANCZOS)
    out.alpha_composite(im,((1920-im.width)//2,(995-im.height)//2))
    draw=ImageDraw.Draw(out);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',25)
    credit='Source: Qwen — official model showcase'
    if variant in {'light','dark'}:credit+=' · background added to inspect transparency'
    if variant=='detail':credit+=' · detail crop'
    if asset['id']=='example-44':credit+=' · generated lettering, not a factual diagram'
    draw.text((58,1020),credit,fill='#F2F0E9' if variant=='dark' else '#4E5E55',font=font)
    out.convert('RGB').save(dest)
    shared.dump(dest.with_suffix('.source.json'),{'source_url':asset['source_url'],'asset_url':asset['url'],
        'source_hash':shared.sha(source),'output_hash':shared.sha(dest),'variant':variant,'rights_basis':asset['rights_basis']})
    return dest


def allocate_frames(length,count):
    if length<=0 or count<=0:raise ValueError('Positive duration and shot count required')
    chunks=[round(length*(i+1)/count)-round(length*i/count) for i in range(count)]
    if any(not 60<=n<=360 for n in chunks):raise ValueError('Shots must last 2-12 seconds')
    return chunks


def require_audio_bytes(approved,current):
    if not isinstance(approved,dict) or not approved.get('master') or not approved.get('chapters') or approved!=current:
        raise RuntimeError('Narration WAV bytes differ from the approved audio review')


def make_plan():
    qc=shared.read(EP/'audio_qc.json')
    if not qc['passed'] or qc.get('narration_hash')!=shared.sha(EP/'narration.json') or qc.get('script_hash')!=shared.sha(EP/'script.json'):
        raise RuntimeError('Current narration/script audio review is not yet passed')
    require_audio_bytes(qc.get('audio_files'),audio_fingerprints())
    paragraphs=shared.read(EP/'paragraph_timing.json')
    assets={r['id']:r for r in shared.read(EP/'media/ledger.json')}
    captures={r['id']:r for r in shared.read(EP/'captures/ledger.json')}
    rows=[];cursor=0
    for para in paragraphs:
        choices=BEATS[para['id']]
        end=round(para['end']*30);length=end-cursor
        lengths=allocate_frames(length,len(choices))
        for i,item in enumerate(choices):
            kind,key,*variants=item.split(':');frames=lengths[i]
            row={'id':f'{para["id"]}_{i:02d}','start_frame':cursor,'frames':frames,'asset_id':key,
                'relevance':para['text'],'paragraph_id':para['id'],'source_url':PUBLIC_URLS['repository']}
            if kind=='img':
                row.update(kind='picture',path=str(picture(assets[key],variants[0] if variants else 'full')))
            elif kind=='cap':
                if key not in captures:raise ValueError('Missing clean capture: '+key)
                cap=captures[key];ann=EP/'edit/annotations'/f'{key}.json';shared.dump(ann,cap)
                row.update(kind='article',path=cap['path'],source_url=cap['url'],framing=cap.get('framing'),
                           annotation_path=str(ann) if cap.get('annotations') else None)
            else:
                row.update(kind='motion',path=str(EP/'motion'/f'{key}.mp4'),source_url='Original editorial explanation; '+PUBLIC_URLS['repository'])
            rows.append(row);cursor+=frames
    # In addition to timeline identities, count embedded official pictures.
    usage=Counter(r['asset_id'] for r in rows if r['kind']=='picture')
    for key in ['example-06','example-18','example-19']:usage[key]+=1
    if max(usage.values())>2:raise ValueError('Official source image reused over twice: '+str(usage))
    configure();assembler.validate(rows)
    shared.dump(EP/'edit_plan.json',rows)
    shared.dump(EP/'edit/plan_receipt.json',{'script_hash':shared.sha(EP/'script.json'),
        'narration_hash':shared.sha(EP/'narration.json'),'audio_qc_hash':shared.sha(EP/'audio_qc.json'),
        'plan_hash':shared.sha(EP/'edit_plan.json'),'audio_files':audio_fingerprints()})
    shared.dump(EP/'edit/source_usage.json',{'image_counts':dict(usage),'shots':len(rows),'frames':cursor,
        'duration':cursor/30,'motion_seconds':sum(r['frames']/30 for r in rows if r['kind']=='motion'),
        'caption_mode':'none','source_audio':'never included','publishing_enabled':False})
    print('Planned',len(rows),'shots',round(cursor/30,2),'seconds',flush=True)


def configure():
    assembler.EP=EP;assembler.OUT=EP/'edit';assembler.FINAL=FINAL


def render():
    receipt=shared.read(EP/'edit/plan_receipt.json')
    for field,filename in [('script_hash','script.json'),('narration_hash','narration.json'),('audio_qc_hash','audio_qc.json'),('plan_hash','edit_plan.json')]:
        if receipt[field]!=shared.sha(EP/filename):raise RuntimeError('Stale edit inputs: '+filename)
    require_audio_bytes(receipt.get('audio_files'),audio_fingerprints())
    configure();assembler.render()
    require_audio_bytes(receipt['audio_files'],audio_fingerprints())
    technical=shared.read(EP/'edit/technical_qc.json');technical['audio_files']=receipt['audio_files']
    shared.dump(EP/'edit/technical_qc.json',technical)


def contacts():
    configure();assembler.contacts()


def frame_selection_expression(indices):
    """Balance additions to avoid FFmpeg's parser-depth limit on long edits."""
    terms=[f'eq(n\\,{n})' for n in indices]
    if not terms:raise ValueError('At least one frame is required')
    while len(terms)>1:
        terms=[f'({terms[i]}+{terms[i+1]})' if i+1<len(terms) else terms[i]
               for i in range(0,len(terms),2)]
    return terms[0]


def delivery_checks():
    """Inspect real export timing and sample both sides of every edit boundary."""
    import json
    import subprocess
    configure()
    technical=shared.read(EP/'edit/technical_qc.json')
    if technical['sha256']!=shared.sha(FINAL):raise RuntimeError('Export changed since decode/audio QC')
    require_audio_bytes(technical.get('audio_files'),audio_fingerprints())
    rows=shared.read(EP/'edit_plan.json');folder=EP/'edit/boundaries';folder.mkdir(parents=True,exist_ok=True)
    indices=sorted({n for r in rows for n in [r['start_frame'],r['start_frame']+r['frames']-1]})
    expression=frame_selection_expression(indices)
    shared.run(['ffmpeg','-y','-v','error','-i',str(FINAL),'-an','-vf',f'select={expression},scale=640:360',
                '-fps_mode','vfr',str(folder/'frame_%03d.jpg')],timeout=1200)
    pictures=sorted(folder.glob('frame_*.jpg'))
    if len(pictures)!=len(indices):raise RuntimeError('Incomplete boundary samples')
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
    for page in range(math.ceil(len(pictures)/12)):
        canvas=Image.new('RGB',(1280,1188),'#eeeeea');draw=ImageDraw.Draw(canvas)
        for j,path in enumerate(pictures[page*12:(page+1)*12]):
            # Four rows of three proofs; raw samples are retained for closer inspection.
            image=Image.open(path);image.thumbnail((426,240));x=j%3*426;y=j//3*297
            canvas.paste(image,(x,y));draw.text((x+8,y+248),f'{indices[page*12+j]/30:.2f}s',fill='#17221f',font=font)
        canvas.save(folder/f'sheet_{page+1:02d}.jpg')
    black=subprocess.run(['ffmpeg','-hide_banner','-i',str(FINAL),'-an','-vf','blackdetect=d=0.10:pix_th=0.10','-f','null','-'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1200)
    if black.returncode:raise RuntimeError('Black-frame analysis failed')
    events=[line for line in black.stderr.splitlines() if 'black_start:' in line]
    result={'technical_export_hash':technical['sha256'],'boundaries_sampled':len(indices),
        'black_intervals':events,'no_detected_black_intervals':not events,
        'narration_tail_seconds':technical['duration']-shared.read(EP/'narration.json')['duration'],
        'manual_boundary_review':'pending','publishing_enabled':False}
    shared.dump(EP/'edit/delivery_checks.json',result)
    if events:raise RuntimeError('Black interval requires visual inspection')
    print('Sampled',len(indices),'boundary frames; no black intervals',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['make_plan','render','contacts','delivery_checks']);a=p.parse_args();globals()[a.stage]()
