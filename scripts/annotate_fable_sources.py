"""Ground editorial pointers in the actual captured article pixels."""
from pathlib import Path
import argparse
import json
import asyncio
import hashlib
import sys
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'data/episodes/episode_20260902_fable_mythos_v5_faster'
EP=ROOT/'data/episodes/episode_20260902_fable_mythos_v6_pointers'
sys.path.insert(0,str(ROOT))
from pipeline.editorial_pointer import exact_word_box, write_pointer_ass, ass_filter
from pipeline.render_v2 import write_concat
FINAL=EP/'Claude_Fable_Mythos_Article_Pointers_Private_1080p.mp4'
PARENT_VIDEO=PARENT/'Claude_Fable_51_and_Mythos_Faster_Private_Review_1080p.mp4'

# Shot-local timing checked against the actual, faster narration. No cue is a real browser click.
# Tuple: kind, OCR line, exact visible phrase, entrance, exit, narrative reason.
EDITS={
 's002': [('underline',6,'same model',.1,1.65,'Same underlying model'),
          ('cursor',7,'levels of safeguards',1.85,5.15,'Different safeguards and access in this paragraph')],
 's003': [('cursor',11,'Agentic coding',2.0,3.9,'Introduction names stronger coding results')],
 's005': [('underline',21,'$0.25',.1,3.1,'Cached-input rate just introduced')],
 's016': [('cursor',11,'safeguards for vetted individuals',2.8,6.4,'More permissive safeguards still apply to vetted users')],
 's024': [('underline',0,'24.7%',.12,4.8,'Comparison specifically names the prior Fable 5 score')],
 's027': [('cursor',9,'60.9%',.1,3.7,'Narration names the Mythos result then explains the score gap')],
 's030': [('underline',13,'log scale',.1,5.1,'Explain that equal spacing is not equal dollars')],
 's034': [('cursor',13,'or Medium effort',.15,4.6,'Configuration comparison; point to effort setting paragraph')],
 's053': [('cursor',16,'for multiple protein targets',2.0,5.65,'Definition of a minibinder continues on this source line')],
 's055': [('underline',6,'the first step',.15,5.7,'Binder design is only an early step, not a finished drug')],
 's056': [('underline',11,'Aug 18, 2026',.25,3.0,'Distinguish the earlier research publication from this launch')],
 's058': [('cursor',12,'independently produced and tested',1.0,5.4,'Narration contrasts a prediction with physical lab evidence')],
 's060': [('underline',15,'nearly 50% across 12',.1,5.8,'Keep this 12-target launch result separate from the earlier study')],
 's066': [('cursor',9,'independently produced and tested',.15,5.4,'Ask whether the designs were physically tested')],
 's069': [('cursor',26,'Claude models',.2,5.1,'Point to the explanation of long sessions re-reading a cached prefix')],
 's072': [('underline',43,'$10',2.4,4.05,'Base input rate, not cache-read pricing'),
          ('underline',51,'$50',4.15,5.42,'Separate output rate named by the narrator')],
 's073': [('underline',15,'$0.25',1.35,4.25,'Do not apply the cheapest cache-read number to the entire bill')],
 's074': [('underline',7,'estimated 25% less',1.0,6.5,'Savings are explicitly an estimate')],
 's077': [('underline',37,'30-day data retention',1.6,2.9,'Standard retention interval'),
          ('cursor',38,'unless expressly authorized by Anthropic',3.05,5.35,'Exception must be expressly authorized')],
 's079': [('underline',5,'eligible customers',.1,4.75,'Only eligible customers receive these terms')],
}

def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')

def prepare():
    selected={}
    for row in read(PARENT/'storyboard.json'):
        if row['kind']=='screenshot' and row['asset_key'].startswith(('launch_','docs_','protein_research_','efs_','table_')):
            selected[row['asset_key']]={'id':row['asset_key'],'path':row['source']}
    dump(EP/'annotations/ocr_input.json',list(selected.values()))
    print(len(selected),'source images selected; B-roll and original graphics excluded',flush=True)

async def ocr_async():
    from winrt.windows.storage import StorageFile, FileAccessMode
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.globalization import Language
    engine=OcrEngine.try_create_from_language(Language('en-US'))
    if engine is None: raise RuntimeError('English Windows OCR is unavailable')
    destination=EP/'annotations/ocr_results.json'
    results=read(destination) if destination.exists() else {}
    for item in read(EP/'annotations/ocr_input.json'):
        digest=hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()
        if results.get(item['id'],{}).get('sha256')==digest: continue
        file=await StorageFile.get_file_from_path_async(item['path'])
        stream=await file.open_async(FileAccessMode.READ)
        decoder=await BitmapDecoder.create_async(stream)
        bitmap=await decoder.get_software_bitmap_async()
        result=await engine.recognize_async(bitmap)
        lines=[]
        for line in result.lines:
            words=[]
            for word in line.words:
                b=word.bounding_rect
                words.append({'text':word.text,'box':[b.x,b.y,b.width,b.height]})
            lines.append({'text':line.text,'words':words})
        results[item['id']]={**item,'sha256':digest,'lines':lines}
        bitmap.close(); stream.close()
        dump(destination,results)
        print(item['id'],len(lines),'lines',flush=True)

def ocr(): asyncio.run(ocr_async())

def sha(path):
    with path.open('rb') as handle: return hashlib.file_digest(handle,'sha256').hexdigest()

def run(args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=600)
    if result.returncode: raise RuntimeError(result.stderr[-3000:])
    return result.stdout

def plan():
    ocrs=read(EP/'annotations/ocr_results.json')
    rows=read(PARENT/'storyboard.json')
    words=read(PARENT/'audio/full_212be1685bcb_words.json')
    plans={}
    for row in rows:
        if row['id'] not in EDITS: continue
        source=ocrs[row['asset_key']]
        assert sha(Path(row['source']))==source['sha256']
        cues=[]
        for kind,line_no,quote,start,end,why in EDITS[row['id']]:
            if row['id']=='s024':
                # Source table OCR order is non-spatial: identify the exact value, not an assumed row index.
                indices=[i for i,l in enumerate(source['lines']) if l['text']=='24.7%']
                assert len(indices)==1
                line_no=indices[0]
            line=source['lines'][line_no]
            box=exact_word_box(line,quote)
            cue={'kind':kind,'box':box,'quote':quote,'start':start,'end':min(end,row['duration']-.06),
                 'rationale':why,'ocr_line':line_no,'source_line':line['text'],
                 'verification_method':'ocr-words','source_sha256':source['sha256']}
            cues.append(cue)
        ass=write_pointer_ass(cues,row['duration'],EP/'annotations'/f'{row["id"]}.ass')
        plans[row['id']]={'cues':cues,'ass':str(ass),'source':row['source'],
                         'source_url':row.get('asset_source_url'),
                         'spoken_here':' '.join(w['text'] for w in words if row['start']<=w['start']<row['start']+row['duration'])}
    dump(EP/'annotations/plan.json',plans)
    dump(EP/'annotations/omitted.json',[{'id':r['id'],'asset':r['asset_key'],
        'reason':'No exact current-sentence target visible, or additional emphasis would be redundant.'}
        for r in rows if r['kind']=='screenshot' and r['id'] not in plans])
    print(len(plans),'shots with grounded annotations',flush=True)

def render():
    plans=read(EP/'annotations/plan.json'); rows=read(PARENT/'storyboard.json')
    destination=EP/'timeline_segments';destination.mkdir(exist_ok=True)
    def segment(row):
        source=PARENT/'timeline_segments'/f'{row["id"]}.mp4'
        if row['id'] not in plans: return source
        out=destination/source.name;receipt=out.with_suffix('.json')
        p=plans[row['id']];ass=Path(p['ass'])
        key=hashlib.sha256((sha(source)+sha(ass)).encode()).hexdigest()
        if out.exists() and receipt.exists() and read(receipt).get('hash')==key and read(receipt).get('sha256')==sha(out): return out
        run(['ffmpeg','-y','-v','error','-i',str(source),'-an','-vf',ass_filter(ass),
             '-c:v','libx264','-preset','fast','-crf','17','-threads','2','-pix_fmt','yuv420p',
             '-video_track_timescale','15360',str(out)])
        dump(receipt,{'hash':key,'sha256':sha(out),'source':str(source),'source_sha256':sha(source)})
        print('Annotated',row['id'],flush=True)
        return out
    with ThreadPoolExecutor(max_workers=3) as pool: paths=list(pool.map(segment,rows))
    listing=write_concat(paths,destination/'concat.txt')
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-i',str(PARENT_VIDEO),
         '-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',str(FINAL)])
    for row in rows:
        if row['id'] in plans: row['editorial_annotations']=plans[row['id']]['cues']
    dump(EP/'storyboard.json',rows)
    for name in ['script.json','delivery_edit_plan.json','parent_source_ledger.json']:
        shutil.copy2(PARENT/name,EP/name)
    (EP/'thumbnails').mkdir(exist_ok=True)
    shutil.copy2(PARENT/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg',EP/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg')
    dump(EP/'revision_manifest.json',{'parent':str(PARENT_VIDEO),'parent_sha256':sha(PARENT_VIDEO),
         'final':str(FINAL),'changed_shots':list(plans),'new_paid_generation_calls':0,
         'publishing_enabled':False,'public_reuse_cleared':False,
         'audio':'AAC stream copied verbatim from faster approved-profile parent',
         'segments':[{'id':r['id'],'path':str(p),'sha256':sha(p),'changed':r['id'] in plans} for r,p in zip(rows,paths)]})
    print(FINAL,flush=True)

def verify():
    from PIL import Image,ImageDraw,ImageFont
    qc=EP/'qc';qc.mkdir(exist_ok=True)
    manifest=read(EP/'revision_manifest.json');plans=read(EP/'annotations/plan.json')
    rows=read(EP/'storyboard.json');by_id={r['id']:r for r in rows}
    def probe(p):return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
    info=probe(FINAL);parent_info=probe(PARENT_VIDEO)
    stream=next(s for s in info['streams'] if s['codec_type']=='video')
    def ahash(p):return run(['ffmpeg','-v','error','-i',str(p),'-map','0:a:0','-c','copy','-f','hash','-hash','sha256','-']).strip()
    checks={'1080p_h264':(stream['width'],stream['height'],stream['codec_name'])==(1920,1080,'h264'),
        'runtime_unchanged':abs(float(info['format']['duration'])-float(parent_info['format']['duration']))<.05,
        'audio_stream_identical':ahash(FINAL)==ahash(PARENT_VIDEO),
        'no_subtitle_track':not any(s['codec_type']=='subtitle' for s in info['streams']),
        'only_article_table_changes':all(by_id[k]['kind']=='screenshot' for k in plans),
        'unaltered_shots_intact':all(sha(Path(r['path']))==r['sha256'] for r in manifest['segments'] if not r['changed']),
        'script_unchanged':sha(EP/'script.json')==sha(PARENT/'script.json'),
        'thumbnail_unchanged':sha(EP/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg')==sha(PARENT/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg'),
        'source_image_hashes_match':all(sha(Path(p['source']))==c['source_sha256'] for p in plans.values() for c in p['cues']),
        'publishing_disabled':manifest['publishing_enabled'] is False}
    jobs=[]
    for shot,p in plans.items():
        for index,c in enumerate(p['cues']):
            offset=min(c['start']+1.0,(c['start']+c['end'])/2)
            jobs.append((shot,index,offset,c))
    def frame(job):
        shot,index,offset,c=job
        destination=qc/f'{shot}_{index}.jpg'
        run(['ffmpeg','-y','-v','error','-ss',str(by_id[shot]['start']+offset),'-i',str(FINAL),'-frames:v','1','-q:v','2',str(destination)])
        return destination
    with ThreadPoolExecutor(max_workers=3) as pool:paths=list(pool.map(frame,jobs))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
    for batch in range(0,len(jobs),6):
        sheet=Image.new('RGB',(1920,3*580),'#ebe9e3');draw=ImageDraw.Draw(sheet)
        for i,(job,path) in enumerate(zip(jobs[batch:batch+6],paths[batch:batch+6])):
            x,y=(i%2)*960,(i//2)*580
            with Image.open(path) as im:sheet.paste(im.resize((960,540)),(x,y))
            draw.text((x+10,y+545),f'{job[0]} {job[3]["kind"]} | {job[3]["quote"]}',fill='#171918',font=font)
        sheet.save(qc/f'annotations_{batch//6+1}.jpg',quality=94)
    # Decode and black-frame scan in one pass.
    proc=subprocess.run(['ffmpeg','-hide_banner','-i',str(FINAL),'-vf','blackdetect=d=0.12:pix_th=0.04:pic_th=0.98','-f','null','-'],capture_output=True,text=True,timeout=600)
    black=[line for line in proc.stderr.splitlines() if 'black_start:' in line]
    errors=[line for line in proc.stderr.splitlines() if 'Error' in line or 'Invalid' in line or 'corrupt' in line.lower()]
    checks['full_decode_clean']=proc.returncode==0 and not errors
    checks['no_blackouts']=not black
    result={'checks':checks,'technical_passed':all(checks.values()),'duration':info['format']['duration'],
            'changed_shots':len(plans),'cues':len(jobs),'sha256':sha(FINAL),'black_events':black,'decode_errors':errors,
            'visual_review':'pending inspection','public_release_ready':False,
            'audio_note':'Unchanged parent audio; inherited subjective tone review remains inconclusive.'}
    dump(qc/'annotation_qc.json',result);print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('stage',choices=['prepare','ocr','plan','render','verify'])
    globals()[parser.parse_args().stage]()
