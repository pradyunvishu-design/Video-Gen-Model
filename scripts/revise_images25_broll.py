"""Revision-only edit: complete official demo beats, unchanged approved narration."""
from __future__ import annotations
import argparse
import json
import math
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from scripts import assemble_images25_episode as assembler
from scripts.produce_images25_episode import EP, read, dump, sha, probe, run

REV = EP / 'revision_v2'
FINAL = EP / 'ChatGPT_Images_25_More_Broll_1080p.mp4'


def validate_reviewed_sources(rows):
    """Never promote pending, changed, or failed source clips into an export."""
    ledger = {item['id']: item for item in read(REV/'media/ledger.json')}
    for row in rows:
        if row['kind'] != 'video' or not row['asset_id'].startswith('v2_'):
            continue
        item = ledger[row['asset_id']]
        if item.get('endpoint_qa_status') != 'pass':
            raise ValueError('Source endpoint review not passed: '+row['asset_id'])
        if sha(Path(row['path'])) != item['sha256']:
            raise ValueError('Source changed after endpoint review: '+row['asset_id'])


def plan():
    original = read(EP / 'edit_plan.json')
    assets = {r['asset_id']: dict(r) for r in original}
    ledger = read(EP / 'media/ledger.json') + read(REV / 'media/ledger.json')
    for item in ledger:
        assets[item['id']] = {
            'asset_id': item['id'], 'path': item['path'], 'kind': 'video',
            'source_url': item['source_url'], 'relevance': item['caption'],
            'available_frames': int(probe(Path(item['path']))['streams'][0]['nb_frames']),
        }
    # 'full' always consumes the entire endpoint-reviewed action/result excerpt.
    # A still absorbs remaining speech; video is never shortened to fill a slot.
    specs = {
        'opening_0': [('v2_fullbody_early','full'), ('picture_mid-century-modern-posters',None)],
        'opening_1': [('v2_aquarium_comments','full'), ('v2_hair_preview','full'), ('picture_sci-fi-surrealism',None)],
        'opening_2': [('v2_tattoo','full'), ('picture_retrofuturism',None)],
        'precision_0': [('v2_aquarium_comments','full'), ('card_precision',None)],
        'precision_1': [('picture_mid-century-modern-posters',6.033333333), ('motion_edit',10), ('picture_stickers',None)],
        'precision_2': [('ticket_cities','full'), ('v2_template_logo','full'), ('picture_wedding-invitation',None)],
        'precision_3': [('v2_template_merch','full'), ('picture_stickers',None)],
        'consistency_0': [('card_multiturn',None), ('cube_turn','full'), ('candles_candles','full'), ('v2_fullbody_late','full')],
        'consistency_1': [('motion_continuity',10), ('v2_template_merch','full'), ('picture_wedding-invitation',None)],
        'consistency_2': [('ticket_cities','full'), ('v2_template_motorcycle','full'), ('picture_vintage-national-park-stamps',None)],
        'consistency_3': [('v2_fullbody_late','full'), ('cube_turn','full'), ('card_multiturn',None)],
        'speed_0+speed_1': [('card_latency',10.233333333), ('motion_latency',10), ('card_latency',None)],
        'speed_2': [('v2_template_logo','full'), ('picture_impressionist-cityscape',None)],
        'speed_3': [('v2_fullbody_early','full'), ('card_flare',None)],
        'sketch_0': [('v2_sketch_frog','full'), ('v2_template_motorcycle','full'), ('card_sharing',None)],
        'sketch_1': [('card_sketch',None), ('motion_sketch',10), ('v2_sketch_garden','full')],
        'sketch_2': [('v2_sketch_fashion','full'), ('v2_sketch_horse','full'), ('picture_retrofuturism',None)],
        'sketch_3': [('v2_sketch_crab','full'), ('v2_sketch_garden','full'), ('picture_presentation-image',None)],
        'models_0': [('card_flare',9.1), ('card_sunburst',None)],
        'models_1': [('motion_tradeoff',10), ('v2_sketch_fashion','full'), ('picture_cyberpunk',None)],
        'models_2': [('motion_check',10), ('v2_candleholder','full'), ('picture_vintage-national-park-stamps',None)],
        'conclusion_0': [('v2_flowers','full'), ('picture_cyberpunk',None)],
        'conclusion_1': [('picture_presentation-image',6.9), ('card_safety',None)],
        'conclusion_2': [('candles_candles','full'), ('v2_hair_preview','full'), ('v2_sketch_crab','full'), ('picture_sci-fi-surrealism',None)],
        'conclusion_3': [('v2_tattoo','full'), ('v2_sketch_horse','full'), ('picture_impressionist-cityscape',None)],
    }
    timings = {t['id']: t for t in read(EP / 'paragraph_timing.json')}
    rows = []
    cursor = 0
    for key, beats in specs.items():
        ids = key.split('+')
        start = round(timings[ids[0]]['start'] * 30)
        end = (math.ceil if key == 'conclusion_3' else round)(timings[ids[-1]]['end'] * 30)
        assert start == cursor
        counts = [assets[a]['available_frames'] if d == 'full' else None if d is None else round(d*30) for a,d in beats]
        remainder = end-start-sum(n or 0 for n in counts)
        assert counts.count(None) == 1
        counts[counts.index(None)] = remainder
        for (ident, duration), count in zip(beats, counts):
            assert 60 <= count <= 360, (key,ident,count)
            asset = assets[ident]
            previous = next((r for r in original if r['asset_id']==ident and r['start_frame']==cursor and r['frames']==count), None)
            if previous:
                row = dict(previous)
            else:
                row = {k:v for k,v in asset.items() if k not in {'id','start_frame','frames','paragraph_ids','narration','available_frames'}}
                row.update(id=f'v2_{len(rows)+1:03d}_{key.replace("+","_")}_{ident}',start_frame=cursor,frames=count,paragraph_ids=ids,narration=' '.join(timings[i]['text'] for i in ids))
            rows.append(row)
            cursor += count
    assembler.validate(rows)
    validate_reviewed_sources(rows)
    assert not any('travel_text' in r['asset_id'] or 'travel_text' in r['path'] for r in rows)
    uses = Counter(r['asset_id'] for r in rows)
    assert max(uses.values()) <= 2
    assert all(a['asset_id'] != b['asset_id'] for a,b in zip(rows,rows[1:]))
    for r in rows:
        if r['kind']=='video':
            assert r['frames']==assets[r['asset_id']]['available_frames'], r['id']
    before = sum(r['frames']/30 for r in original if r['kind']=='video')
    after = sum(r['frames']/30 for r in rows if r['kind']=='video')
    assert after > before + 20, (before,after)
    chart = next(r for r in rows if r['asset_id']=='motion_latency')
    assert chart['start_frame']==5905 and chart['frames']==300
    active = [r for r in ledger if uses[r['id']]]
    # Enforce repetition on actual source time, not renamed excerpt IDs.
    source_frames = Counter()
    for item in active:
        for frame in range(round(item['source_in']*30), round(item['source_out']*30)):
            source_frames[(item['source_url'],frame)] += uses[item['id']]
    assert max(source_frames.values())<=2, 'Overlapping sources repeat a frame more than twice'
    dump(REV/'edit_plan.json',rows)
    dump(REV/'active_source_ledger.json',active)
    report = {'old_video_seconds':before,'new_video_seconds':after,'added_video_seconds':after-before,'runtime_seconds':cursor/30,'shots':len(rows),'rejected_assets':['travel_text'],'complete_source_beats':True,'unchanged_narration_hash':sha(Path(read(EP/'narration.json')['path'])),'source_time_max_uses':max(source_frames.values()),'publishing_enabled':False}
    dump(REV/'changes.json',report)
    print(json.dumps(report,indent=2))


def configure():
    # Reuse the established encoder/QC without changing the original episode.
    original_read = assembler.read
    def read_revision(path):
        return original_read(REV/'edit_plan.json' if Path(path)==EP/'edit_plan.json' else path)
    assembler.read = read_revision
    assembler.OUT = REV/'edit'
    assembler.FINAL = FINAL


def render():
    validate_reviewed_sources(read(REV/'edit_plan.json'))
    configure()
    dest = assembler.OUT/'segments'
    dest.mkdir(parents=True,exist_ok=True)
    for r in read(REV/'edit_plan.json'):
        for suffix in ['.mp4','.json']:
            source = EP/'edit/segments'/(r['id']+suffix)
            target = dest/(r['id']+suffix)
            if source.exists() and not target.exists():
                shutil.copy2(source,target)
    assembler.render()


def review():
    from PIL import Image, ImageDraw, ImageFont
    configure()
    assembler.contacts()
    rows = read(REV/'edit_plan.json')
    folder = REV/'edit/boundaries'
    folder.mkdir(parents=True,exist_ok=True)
    def capture(job):
        i,r = job
        result=[]
        for side,t in [('in',(r['start_frame']+2)/30),('out',(r['start_frame']+r['frames']-3)/30)]:
            path=folder/f'{i:03d}_{side}.jpg'
            run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',str(FINAL),'-frames:v','1','-vf','scale=480:270',str(path)])
            result.append(path)
        return result
    with ThreadPoolExecutor(max_workers=3) as pool:
        pairs=list(pool.map(capture,enumerate(rows)))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    for start in range(0,len(rows),8):
        group=rows[start:start+8]
        sheet=Image.new('RGB',(1920,1200),'#171717');draw=ImageDraw.Draw(sheet)
        for n,r in enumerate(group):
            x=(n%2)*960;y=(n//2)*300
            for j,path in enumerate(pairs[start+n]):sheet.paste(Image.open(path),(x+480*j,y+26))
            draw.text((x+8,y+4),f"{r['start_frame']/30:.2f}s {r['asset_id']} | in / out",font=font,fill='white')
        sheet.save(folder/f'boundary_{start//8+1}.jpg')


def verify():
    rows=read(REV/'edit_plan.json');technical=read(REV/'edit/technical_qc.json')
    validate_reviewed_sources(rows)
    assert sha(EP/'ChatGPT_Images_25_1080p.mp4') == read(EP/'final_qc.json')['sha256'], 'Original export changed'
    selected={r['asset_id'] for r in rows if r['kind']=='video'}
    current_ledger=read(EP/'media/ledger.json')+read(REV/'media/ledger.json')
    dump(REV/'active_source_ledger.json',[item for item in current_ledger if item['id'] in selected])
    assert sha(FINAL)==technical['sha256']
    scan=subprocess.run(['ffmpeg','-hide_banner','-i',str(FINAL),'-an','-vf','scale=320:180,blackdetect=d=0.3:pix_th=0.02:pic_th=0.98','-f','null','-'],capture_output=True,text=True,encoding='utf-8',check=True,timeout=1200)
    dump(REV/'blackdetect.json',{'intervals':re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)',scan.stderr)})
    assert not read(REV/'blackdetect.json')['intervals']
    assert all(technical['checks'].values())
    changes=read(REV/'changes.json')
    assert changes['unchanged_narration_hash']==sha(Path(read(EP/'narration.json')['path']))
    dump(REV/'qc.json',{'technical_passed':True,'artifact':str(FINAL),'sha256':sha(FINAL),'changes':changes,'source_audio_used':False,'no_black_intervals':True,'source_endpoint_reviews_passed':True,'source_review':'media/qa/endpoint_review.json','visual_review':'pending','publication_rights_review':'pending','publishing_enabled':False})
    print(json.dumps(read(REV/'qc.json'),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['plan','render','review','verify']);a=p.parse_args()
    globals()[a.stage]()
