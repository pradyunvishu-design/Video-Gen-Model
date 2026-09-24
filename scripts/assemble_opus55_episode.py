"""Frame-exact, speech-aligned Opus 5.5 source edit; no publishing capability."""
from __future__ import annotations
import argparse, hashlib, json, math, subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from scripts.produce_opus55_episode import EP, shared, audio_fingerprints, PUBLIC_URLS
from scripts.assemble_qwen21_episode import require_audio_bytes, allocate_frames
read, dump, sha, run, probe = shared.read, shared.dump, shared.sha, shared.run, shared.probe
from scripts.render_dreamx_source_motion import render_source_shot
from pipeline.render_v2 import write_concat

OUT=EP/'edit'
FINAL=EP/'Claude_Opus_55_Explained_1080p.mp4'
FPS=30

# Ordered, paragraph-specific evidence choices. No random source substitution.
BEATS={
 '01_hook_0':['cap:launch_intro','cap:launch_pricing'],
 '01_hook_1':['video:launch_open','cap:launch_cost_speed'],
 '02_cost_0':['motion:token_price','cap:docs_pricing'],
 '02_cost_1':['cap:launch_pricing','cap:docs_pricing'],
 '02_cost_2':['motion:cost_layers','cap:launch_cost_speed'],
 '02_cost_3':['motion:cache_price','cap:docs_cache'],
 '03_coding_0':['cap:github_steps','cap:github_copilot'],
 '03_coding_1':['cap:launch_coding_audit','cap:launch_haproxy'],
 '03_coding_2':['cap:launch_haproxy','cap:github_recovery'],
 '03_coding_3':['cap:github_access','cap:github_copilot'],
 '04_charts_0':['motion:benchmark_axes','cap:launch_terminal_chart','cap:launch_gdp_chart'],
 '04_charts_1':['cap:analysis_intelligence','cap:analysis_terminal'],
 '04_charts_2':['cap:analysis_terminal','cap:launch_terminal_chart'],
 '04_charts_3':['cap:analysis_effort','cap:launch_benchmark_safeguards'],
 '05_work_0':['cap:launch_reports','cap:launch_report_threshold'],
 '05_work_1':['cap:launch_research_sources','cap:launch_reports'],
 '05_work_2':['motion:verification_loop','cap:launch_research_sources'],
 '05_work_3':['cap:launch_merger','cap:launch_report_threshold'],
 '06_communication_0':['cap:cursor_communication','cap:cursor_effort'],
 '06_communication_1':['cap:launch_communication','cap:launch_bug_example'],
 '06_communication_2':['video:site_design_comparison','cap:launch_bug_example','cap:launch_bug_check'],
 '06_communication_3':['cap:cursor_communication','video:site_bug_comparison','cap:launch_communication'],
 '07_settings_0':['motion:effort_tradeoff','cap:docs_thinking'],
 '07_settings_1':['cap:cursor_effort','cap:analysis_effort'],
 '07_settings_2':['cap:launch_fast_mode','cap:docs_fast_mode'],
 '07_settings_3':['cap:launch_fast_mode','cap:docs_context'],
 '08_migration_0':['cap:docs_breaking_changes','cap:migration_checklist'],
 '08_migration_1':['cap:migration_thinking','cap:migration_forced_tools','cap:migration_computer'],
 '08_migration_2':['cap:migration_context','cap:migration_progress'],
 '08_migration_3':['motion:migration','cap:migration_checklist'],
 '09_decision_0':['cap:launch_intro','cap:docs_context'],
 '09_decision_1':['motion:decision','cap:github_steps'],
 '09_decision_2':['cap:launch_availability','cap:cursor_overview'],
}


def distribute(length, choices):
    """Keep complete 12s diagrams and 5s quotations; split only source holds."""
    clip_frames={'video:site_bug_comparison':198,'video:site_design_comparison':143}
    fixed={i:(360 if k.startswith('motion:') else clip_frames.get(k,150)) for i,k in enumerate(choices) if not k.startswith('cap:')}
    remaining=length-sum(fixed.values())
    flexible=[i for i in range(len(choices)) if i not in fixed]
    if not flexible:
        if remaining:raise ValueError('No source shot for remaining speech')
        return [fixed[i] for i in range(len(choices))]
    lengths=allocate_frames(remaining,len(flexible))
    mapping={**fixed,**dict(zip(flexible,lengths))}
    return [mapping[i] for i in range(len(choices))]


def make_plan():
    qc=read(EP/'audio_qc.json')
    if not qc['passed'] or qc.get('narration_hash')!=sha(EP/'narration.json') or qc.get('script_hash')!=sha(EP/'script.json'):
        raise RuntimeError('Current audio review must pass before editing')
    require_audio_bytes(qc.get('audio_files'),audio_fingerprints())
    if qc.get('paragraph_timing_hash') != sha(EP/'paragraph_timing.json'):
        raise RuntimeError('Paragraph timing differs from the approved speech alignment')
    caps={r['id']:r for r in read(EP/'captures/ledger.json')}
    media={r['id']:r for r in read(EP/'media/ledger.json')}
    paragraphs=read(EP/'paragraph_timing.json');rows=[];cursor=0
    for n,para in enumerate(paragraphs):
        end=18000 if n==len(paragraphs)-1 else round(para['end']*FPS)
        choices=BEATS[para['id']];lengths=distribute(end-cursor,choices)
        for i,(choice,frames) in enumerate(zip(choices,lengths)):
            kind,key=choice.split(':')
            row={'id':f'{para["id"]}_{i:02d}','start_frame':cursor,'frames':frames,'asset_id':key,
                 'relevance':para['text'],'paragraph_id':para['id'],'source_url':PUBLIC_URLS['release']}
            if kind=='cap':
                cap=caps[key];ann=OUT/'annotations'/f'{key}.json';dump(ann,cap)
                no_annotation=para['id'] in {'03_coding_1','03_coding_2','05_work_1','05_work_2','05_work_3',
                    '06_communication_1','06_communication_3','07_settings_1','07_settings_3','09_decision_1','09_decision_2'}
                framing=cap.get('framing')
                # Remove wasted browser margins, but retain every measured line.
                crop={'x':240,'y':120,'width':1440,'height':810,'units':'pixels'}
                anns=cap.get('annotations',[]) if not no_annotation else []
                fits=all(240<=a['region']['x'] and a['region']['x']+a['region']['width']<=1680
                         and 120<=a['region']['y'] and a['region']['y']+a['region']['height']+5<=930 for a in anns)
                if framing and framing.get('width')==1920 and fits:framing=crop
                row.update(kind='article',path=cap['path'],source_url=cap['url'],framing=framing,
                           annotation_path=str(ann) if cap.get('annotations') and not no_annotation else None)
            elif kind=='video':
                row.update(kind='video',path=media[key]['path'],source_url=media[key]['source_url'],
                           offset=3.2 if key=='site_design_comparison' else 0)
            else:
                row.update(kind='motion',path=str(EP/'motion'/f'{key}.mp4'),source_url='Original editorial diagram; '+PUBLIC_URLS['release'])
            rows.append(row);cursor+=frames
    validate(rows);dump(EP/'edit_plan.json',rows)
    dump(OUT/'plan_receipt.json',{'script_hash':sha(EP/'script.json'),'narration_hash':sha(EP/'narration.json'),
        'audio_qc_hash':sha(EP/'audio_qc.json'),'plan_hash':sha(EP/'edit_plan.json'),'audio_files':audio_fingerprints(),
        'paragraph_timing_hash':sha(EP/'paragraph_timing.json')})
    dump(OUT/'source_usage.json',{'counts':dict(Counter(r['asset_id'] for r in rows)),
        'seconds_by_kind':{k:sum(r['frames']/FPS for r in rows if r['kind']==k) for k in ['article','motion','video']},
        'shots':len(rows),'seconds':600,'subtitles':False,'publishing_enabled':False})
    print('Planned',len(rows),'shots',flush=True)

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
    if cursor != 18000:raise ValueError('Video must be exactly ten minutes')
    return cursor

def shot(row):
    dest=OUT/'segments'/(row['id']+'.mp4');dest.parent.mkdir(parents=True,exist_ok=True)
    seconds=row['frames']/FPS
    digest=hashlib.sha256(json.dumps({'row':row,'hash':sha(Path(row['path'])),'renderer':sha(Path(__file__)), 'annotation_hash':sha(Path(row['annotation_path'])) if row.get('annotation_path') else None},sort_keys=True).encode()).hexdigest()
    receipt=dest.with_suffix('.json')
    if dest.exists() and receipt.exists() and read(receipt).get('input_hash')==digest and read(receipt).get('output_hash')==sha(dest):return dest
    if row['kind'] in {'article','picture'}:
        annotation=read(Path(row['annotation_path'])) if row.get('annotation_path') else None
        if annotation:
            annotation=json.loads(json.dumps(annotation))
            for a in annotation.get('annotations',[]):
                a['start']=min(.8,seconds*.15);a['end']=seconds-.15
        base=dest.with_name(dest.stem+'_base.mp4')
        result=render_source_shot(row['path'],base,seconds,annotation=annotation,cursor=False,framing=row.get('framing'),focus=row.get('focus'),zoom=1.0)
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
        filters.append("drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='Source — Anthropic':fontsize=23:fontcolor=white:shadowcolor=black:shadowx=1:shadowy=1:box=1:boxcolor=black@0.45:boxborderw=8:x=52:y=h-55")
    elif row['kind']=='article':
        from urllib.parse import urlparse
        host=urlparse(row['source_url']).hostname
        credit={'www.anthropic.com':'Anthropic','platform.claude.com':'Claude documentation',
                'github.blog':'GitHub','prod.cursor.com':'Cursor','artificialanalysis.ai':'Artificial Analysis'}.get(host)
        if not credit:raise ValueError('Unrecognized source credit')
        filters.append(f"drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='Source — {credit}':fontsize=22:fontcolor=0x17221F:box=1:boxcolor=0xF2F0E9@0.94:boxborderw=8:x=40:y=h-44")
    command+=['-an','-frames:v',str(row['frames']),'-vf',','.join(filters),'-c:v','libx264','-preset','veryfast','-crf','18','-threads','2','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',str(dest)]
    run(command)
    exported=probe(dest);stream=next(s for s in exported['streams'] if s['codec_type']=='video')
    if int(stream.get('nb_frames',0))!=row['frames']:
        raise ValueError('Rendered frame count does not cover planned speech: '+row['id'])
    dump(receipt,{'input_hash':digest,'output_hash':sha(dest),'path':str(dest)})
    print('Rendered',row['id'],flush=True);return dest

def render(segments_only=False):
    receipt=read(EP/'edit/plan_receipt.json')
    for field, filename in [('script_hash','script.json'), ('narration_hash','narration.json'), ('audio_qc_hash','audio_qc.json'), ('plan_hash','edit_plan.json'), ('paragraph_timing_hash','paragraph_timing.json')]:
        if receipt[field] != sha(EP/filename):raise RuntimeError('Stale edit input: '+filename)
    require_audio_bytes(receipt['audio_files'], audio_fingerprints())
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
    checks={'1080p':(v['width'],v['height'])==(1920,1080),'h264':v['codec_name']=='h264','fps30':v['r_frame_rate']=='30/1','duration':abs(float(meta['format']['duration'])-600)<.05,'one_audio':sum(s['codec_type']=='audio' for s in meta['streams'])==1,'no_subtitles':not any(s['codec_type']=='subtitle' for s in meta['streams']),'full_decode':True,'narration_only':audio['passed'],'source_repetition':True}
    if not all(checks.values()):raise RuntimeError(str(checks))
    staged.replace(FINAL)
    require_audio_bytes(receipt['audio_files'], audio_fingerprints())
    dump(OUT/'technical_qc.json',{'checks':checks,'duration':float(meta['format']['duration']),'sha256':sha(FINAL),'shots':len(rows),'publishing_enabled':False,'visual_review':'pending','audio_files':receipt['audio_files']})
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

def delivery_checks():
    from scripts import assemble_qwen21_episode as checks
    checks.EP=EP;checks.FINAL=FINAL;checks.audio_fingerprints=audio_fingerprints
    checks.configure=lambda:None
    checks.delivery_checks()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['make_plan','render','segments','contacts','delivery_checks']);a=p.parse_args()
    if a.stage=='segments':render(segments_only=True)
    else:globals()[a.stage]()
