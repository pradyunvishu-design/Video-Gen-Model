"""Scoped picture-only Astra revision. Keep the approved AAC narration bit-for-bit."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import base64
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.produce_astra_episode import ROOT, read, dump, sha, run, probe
from pipeline.render_v2 import duration, write_concat
from PIL import Image, ImageDraw, ImageChops, ImageStat

BASE = ROOT / 'data/episodes/episode_20260905_gpt6_astra_extended'
EP = ROOT / 'data/episodes/episode_20260905_gpt6_astra_capture_polish'
FINAL = EP / 'GPT6_Astra_Clean_Captures_1080p.mp4'
INPUT = BASE / 'GPT6_Astra_Extended_1080p.mp4'
CAPTURE = ROOT / 'output/playwright/astra-polish'
SOURCE = 'https://openai.com/index/gpt-6-astra/'
EXPECTED_INPUT = '47302f2883940773bf2a777bdca4939400d2069586b0ed7024d5949508d178b3'


def init():
    for sub in ['media', 'qa', 'render/segments']:
        (EP / sub).mkdir(parents=True, exist_ok=True)
    if sha(INPUT) != EXPECTED_INPUT:
        raise RuntimeError('The approved source master changed; inspect before editing.')


def captures():
    init()
    ledger = []
    for name, count, y0, y1 in [('launch_scroll', 265, 0, 660), ('source_scroll', 266, 1660, 1810)]:
        frames = sorted((CAPTURE / name).glob('*.jpg'))
        assert len(frames) == count, (name, len(frames))
        assert all(Image.open(p).size == (1920,1080) for p in frames)
        sig = hashlib.sha256(''.join(sha(p) for p in frames).encode()).hexdigest()
        dest = EP / 'media' / f'{name}.mp4'
        receipt = dest.with_suffix('.json')
        if not dest.exists() or not receipt.exists() or read(receipt).get('input_hash') != sig:
            run(['ffmpeg','-y','-v','error','-framerate','30','-i',str(CAPTURE/name/'%04d.jpg'),
                 '-frames:v',str(count),'-an','-c:v','libx264','-preset','fast','-crf','17',
                 '-threads','3','-pix_fmt','yuv420p',str(dest)])
        entry = {'id':name,'path':str(dest),'source_url':SOURCE,'publisher':'OpenAI',
                 'capture_method':'Real browser, deterministic scroll positions, one screenshot per output frame',
                 'css_viewport':[1280,720],'device_scale_factor':1.5,'output':[1920,1080],
                 'scroll_css_pixels':[y0,y1],'fps':30,'frames':count,'camera_zoom':False,
                 'capture_audio':False,'input_hash':sig,'sha256':sha(dest),
                 'rights_basis':'Limited source-page excerpt for direct commentary; publication review pending',
                 'page_content_rewritten':False,'publishing_enabled':False}
        dump(receipt,entry); ledger.append(entry)
    dump(EP/'media/ledger.json',ledger)


def assemble():
    init()
    timeline = copy.deepcopy(read(BASE/'timeline.json'))
    original_segments = [Path(line[6:-1]) for line in (BASE/'render/concat.txt').read_text().splitlines() if line.startswith("file '")]
    assert len(original_segments) == len(timeline['shots'])
    replacements = {
        1: ('video','launch_scroll',EP/'media/launch_scroll.mp4',0,'Full-screen eased scroll replaces the small static launch card.'),
        2: ('photo','house_room_detail',EP/'media/house_room_detail.jpg',0,'Room question shows the actual room, not unrelated launch-film lecture footage.'),
        3: ('photo','qa',BASE/'qa/qa.jpg',0,'Website-check question shows the official QA interface, not apartment listings.'),
        4: ('card','osworld',BASE/'cards/osworld.png',0,'Mention of making sense of charts previews the actual chart, not another house still.'),
        5: ('video','source_scroll',EP/'media/source_scroll.mp4',0,'Source disclaimer shows readable first-party source text instead of repeating the hero.'),
    }
    # A different, real camera position for the room question; no generated imagery.
    detail = EP/'media/house_room_detail.jpg'
    if not detail.exists():
        run(['ffmpeg','-y','-v','error','-ss','11.5','-i',str(BASE/'media/house.mp4'),'-frames:v','1',str(detail)])
    changed = []
    for index,(kind,asset,path,offset,why) in replacements.items():
        shot=timeline['shots'][index]
        changed.append({'index':index,'start':shot['start_frame']/30,'end':(shot['start_frame']+shot['frames'])/30,'before':shot['asset'],'after':asset,'reason':why})
        shot.update(kind=kind,asset=asset,path=str(path),source_offset=offset)
        if asset=='osworld':shot['evidence_ids']=sorted(set(shot['evidence_ids']+['launch']))
    # Preserve exact speech boundaries. Only affected picture segments are rebuilt.
    def encode(index):
        shot=timeline['shots'][index]
        signature=hashlib.sha256((json.dumps(shot,sort_keys=True)+sha(Path(shot['path']))+'capture-polish-v1').encode()).hexdigest()[:16]
        dest=EP/'render/segments'/f'{index:03d}_{signature}.mp4'
        if dest.exists():
            try:
                if abs(duration(dest)-shot['duration'])<.04:return index,dest
            except (subprocess.CalledProcessError,ValueError,KeyError):pass
        still=shot['kind'] in ['photo','card']
        args=['ffmpeg','-y','-v','error']+(['-loop','1','-framerate','30'] if still else [])+['-i',shot['path']]
        filters=['scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos','pad=1920:1080:(ow-iw)/2:(oh-ih)/2','setsar=1','fps=30']
        if shot['kind']!='card':
            filters += ['drawbox=x=40:y=1010:w=150:h=44:color=black@0.65:t=fill',"drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='OpenAI':x=57:y=1020:fontsize=23:fontcolor=white"]
        run(args+['-vf',','.join(filters),'-frames:v',str(shot['frames']),'-an','-c:v','libx264','-preset','fast','-crf','17','-threads','2','-pix_fmt','yuv420p','-video_track_timescale','15360',str(dest)])
        return index,dest
    with ThreadPoolExecutor(max_workers=3) as pool:
        for index,dest in pool.map(encode,replacements):original_segments[index]=dest
    timeline['source_video_uses']={}
    for shot in timeline['shots']:
        if shot['kind']=='video':timeline['source_video_uses'][shot['asset']]=timeline['source_video_uses'].get(shot['asset'],0)+1
    timeline['base_episode']=str(BASE)
    timeline['audio_preservation']='AAC stream copied directly from the approved 11:57 master.'
    dump(EP/'timeline.json',timeline)
    dump(EP/'edit_decisions.json',{'changes':changed,'unchanged_picture_segments':len(original_segments)-len(replacements),'narration_changed':False,'publishing_enabled':False})
    listing=write_concat(original_segments,EP/'render/concat.txt')
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(EP/'render/picture.mp4')])
    # One delivery normalization prevents mixed JPEG/video color metadata resets.
    run(['ffmpeg','-y','-v','error','-i',str(EP/'render/picture.mp4'),'-i',str(INPUT),
         '-map','0:v:0','-map','1:a:0','-vf','scale=out_color_matrix=bt709:out_range=tv,setsar=1,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709',
         '-c:v','libx264','-preset','fast','-crf','17','-threads','6',
         '-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709',
         '-c:a','copy','-t',str(timeline['duration']),'-movflags','+faststart',str(FINAL)],1200)
    print('Master ready',FINAL,flush=True)


def audit():
    """Three time samples per actual source-video shot, not only a poster-frame review."""
    init()
    timeline=read(EP/'timeline.json') if (EP/'timeline.json').exists() else read(BASE/'timeline.json')
    rows=[]
    for shot in timeline['shots']:
        if shot['kind']!='video':continue
        strip=Image.new('RGB',(1440,300),'#111111'); draw=ImageDraw.Draw(strip)
        for col,frac in enumerate([.08,.5,.92]):
            dest=EP/'qa'/f"clip_{shot['index']:02d}_{shot['asset']}_{col}.jpg"
            offset=shot['source_offset']+shot['duration']*frac
            if not dest.exists():run(['ffmpeg','-y','-v','error','-ss',str(offset),'-i',shot['path'],'-frames:v','1','-vf','scale=480:270',str(dest)])
            strip.paste(Image.open(dest),(col*480,30));draw.text((col*480+8,7),f"{shot['start_frame']/30+shot['duration']*frac:.2f}s | {shot['asset']}",fill='white')
        dest=EP/'qa'/f"strip_{shot['index']:02d}.jpg";strip.save(dest,quality=95)
        rows.append({'index':shot['index'],'start':shot['start_frame']/30,'asset':shot['asset'],'frames':str(dest),'narration':shot['narration']})
    for start in range(0,len(rows),5):
        sheet=Image.new('RGB',(1440,300*len(rows[start:start+5])),'black')
        for i,row in enumerate(rows[start:start+5]):sheet.paste(Image.open(row['frames']),(0,i*300))
        sheet.save(EP/'qa'/f'clip_audit_{start//5}.jpg',quality=95)
    dump(EP/'qa/clip_audit.json',rows)
    print('Source-shot review strips ready',len(rows),flush=True)


def verify():
    meta=probe(FINAL);timeline=read(EP/'timeline.json');v=next(s for s in meta['streams'] if s['codec_type']=='video')
    decoded=subprocess.run(['ffmpeg','-v','error','-i',str(FINAL),'-f','null','-'],capture_output=True,text=True,timeout=600)
    def audio_hash(path):
        return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-c','copy','-f','hash','-hash','sha256','-'],text=True).strip()
    gates={'1080p':(v['width'],v['height'])==(1920,1080),'h264':v['codec_name']=='h264',
           '30fps':v['r_frame_rate']=='30/1','decode':decoded.returncode==0 and not decoded.stderr.strip(),
           'duration_unchanged':abs(float(meta['format']['duration'])-717.233333)<.05,
           'audio_bitstream_identical':audio_hash(INPUT)==audio_hash(FINAL),
           'original_master_preserved':sha(INPUT)==EXPECTED_INPUT,'no_subtitle_stream':not any(s['codec_type']=='subtitle' for s in meta['streams']),
           'publishing_disabled':timeline['publishing_enabled'] is False}
    run(['ffmpeg','-y','-v','error','-threads','2','-i',str(FINAL),'-vf','fps=1/2,scale=480:270,tile=4x6:nb_frames=24','-frames:v','1',str(EP/'qa/opening_review_fixed.jpg')])
    assert (EP/'qa/opening_review_fixed.jpg').exists(), 'Opening review image was not emitted'
    dump(EP/'qc.json',{'gates':gates,'automated_passed':all(gates.values()),'video_sha256':sha(FINAL),'duration':float(meta['format']['duration']),'source_audio':False,'narrator':'Zubenelgenubi','limitations':['Source demonstrations include native 720p and 900p excerpts; 1080p delivery does not invent source detail.','Semantic/temporal review uses actual timecoded frame strips; it is not a claim of full human playback review.'],'publishing_enabled':False})
    print(json.dumps(gates,indent=2),flush=True)
    assert all(gates.values())


def motion_qc():
    import numpy as np
    checks=[]
    for name in ['launch_scroll','source_scroll']:
        frames=sorted((CAPTURE/name).glob('*.jpg'))
        header=None;deltas=[];centers=[]
        for p in frames:
            with Image.open(p) as im:
                current=im.crop((0,20,1800,75)).convert('L')
                # Track the fixed white OpenAI wordmark, not the page's native
                # transparent-to-black navigation background at initial scroll.
                mark=np.asarray(im.crop((40,25,160,70)).convert('L'))>200
                yy,xx=np.where(mark)
                assert len(xx)>50, 'Navigation wordmark missing'
                centers.append((float(xx.mean()),float(yy.mean())))
            if header is not None:deltas.append(ImageStat.Stat(ImageChops.difference(current,header)).mean[0])
            header=current
        maximum=max(deltas)
        anchor_shift=max(float(np.linalg.norm(np.array(b)-np.array(a))) for a,b in zip(centers,centers[1:]))
        checks.append({'capture':name,'frames':len(frames),'largest_change_frame':deltas.index(maximum)+1,'max_consecutive_header_pixel_difference_0_255':maximum,
                       'raw_luminance_test_pass':maximum<2,'max_fixed_wordmark_centroid_shift_pixels':anchor_shift,
                       'fixed_navigation_stability_pass':anchor_shift<.5,
                       'raw_flag_explanation':'Launch frame 21-to-22 changes the native navigation backdrop to black; inspected both source frames. Wordmark geometry separately tested.',
                       'scope':'Fixed navigation wordmark position, not background luminance; does not certify motion inside provider demos.'})
    dump(EP/'qa/capture_motion_qc.json',{'checks':checks,'passed':all(c['fixed_navigation_stability_pass'] for c in checks)})
    print(json.dumps(checks,indent=2),flush=True)


def review():
    """Fresh independent visual review; does not pretend sampled frames are playback."""
    from scripts.produce_astra_episode import env
    import pipeline.editorial as editorial
    from pipeline.editorial import call_openrouter, capture_openrouter_usage
    receipt=EP/'qa/independent_clip_review.json'
    images=sorted((EP/'qa').glob('clip_audit_*.jpg'))+[EP/'qa/opening_review_fixed.jpg']+sorted((EP/'qa').glob('fullsize_*.jpg'))
    assert all(path.exists() for path in images), 'Rendered review packet incomplete'
    packet_hash=hashlib.sha256(''.join(sha(p) for p in images).encode()).hexdigest()
    if receipt.exists() and read(receipt).get('packet_hash')==packet_hash:
        print(json.dumps(read(receipt),indent=2));return
    if receipt.exists():dump(EP/'qa/review_history'/f"{read(receipt).get('packet_hash','source_only')}.json",read(receipt))
    editorial.OPENROUTER_API_KEY=env().get('OPENROUTER_API_KEY','')
    packet=[{'type':'text','text':'Independently review this narrated technology-news edit using timecoded strips. Judge whether each visual matches the attached narration, whether source UI looks obstructed/unreadable, and whether opening pacing is purposeful. A filmstrip is not full playback; do not certify audio or smoothness from these samples. The video is commentary on published official demonstrations, not our hands-on test. Some demos are natively sped up. List concrete major defects with timestamps; distinguish authored errors from ordinary demo content. Score 1-10. The unmodified source strips can show baked subtitles that the final editor crops away for playco_demo; see the final opening contact sheet for actual framing. No extra subtitles are added.'},
            {'type':'text','text':json.dumps(read(EP/'qa/clip_audit.json'))},
            {'type':'text','text':'Viewing contract: the filmstrips and grid are reduced-size timing overviews, NOT the delivery resolution. Evaluate readability using the fullsize_<seconds>.jpg frames from the exported 1920x1080 movie. Judge main communication rather than requiring every incidental UI cell to be readable. The opening contact sheet spans 0-48 seconds with 24 cells. Do not infer any unshown frames or audio.'}]
    for path in images:
        if path.exists():packet += [{'type':'text','text':path.name},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(path.read_bytes()).decode()}}]
    spendpath=BASE/'provider_usage.json';spend=read(spendpath)
    def usage(event):
        if event['phase']=='before':
            if spend['openrouter_usd']+spend.get('reserved_usd',0)+.25>spend['openrouter_cap_usd']:raise RuntimeError('Review budget cap')
            spend['reserved_usd']=.25;dump(spendpath,spend);return {'max_tokens':1800}
        cost=event.get('usage',{}).get('cost')
        if cost is None:raise RuntimeError('Missing review cost receipt')
        spend['openrouter_usd']+=float(cost);spend['reserved_usd']=0;spend['calls'].append(event);dump(spendpath,spend)
    props={'passed':{'type':'boolean'},'major_issues':{'type':'array','items':{'type':'string'}},'soft_notes':{'type':'array','items':{'type':'string'}},'clip_relevance_score':{'type':'number'},'opening_flow_score':{'type':'number'}}
    schema={'type':'json_schema','json_schema':{'name':'ClipReview','strict':True,'schema':{'type':'object','additionalProperties':False,'properties':props,'required':list(props)}}}
    with capture_openrouter_usage(usage):
        result=call_openrouter('openai/gpt-5.4','Review the rendered evidence independently. No access to creator reasoning. Be precise and do not claim observations beyond the supplied material.',packet,schema,temperature=.1)
    result.update(scope='Three time samples per source shot, narration mapping, and opening contact sheet; not full temporal/audio inspection',model='openai/gpt-5.4',packet_hash=packet_hash,packet_images=[str(p) for p in images])
    dump(receipt,result);print(json.dumps(result,indent=2),flush=True)


def package():
    qc=read(EP/'qc.json')
    assert qc['automated_passed']
    original=read(BASE/'package.json')
    original.update(video=str(FINAL),quality_report=str(EP/'qc.json'),edit_decisions=str(EP/'edit_decisions.json'),source_capture_ledger=str(EP/'media/ledger.json'),capture_stability_report=str(EP/'qa/capture_motion_qc.json'))
    dump(EP/'package.json',original)
    dump(EP/'source_provenance.json',{'base_ledger':str(BASE/'media/ledger.json'),'base_card_ledger':str(BASE/'cards/ledger.json'),'new_capture_ledger':str(EP/'media/ledger.json'),'house_room_detail':{'source':str(BASE/'media/house.mp4'),'source_time_local':11.5,'source_time_original':13.5,'source_url':SOURCE,'sha256':sha(EP/'media/house_room_detail.jpg')},'publishing_enabled':False})
    review_result=read(EP/'qa/independent_clip_review.json') if (EP/'qa/independent_clip_review.json').exists() else None
    dump(EP/'anti_slop_review.json',{'artifact':str(FINAL),'scope':'Picture-only polish; preserved approved narration and graphics','status':'pass_with_notes' if review_result and review_result['passed'] else 'review_required','hard_defects':review_result.get('major_issues',[]) if review_result else ['Independent review missing'],'soft_signals':review_result.get('soft_notes',[]) if review_result else [],'verification':qc['gates'],'capture_stability':read(EP/'qa/capture_motion_qc.json'),'limitations':qc['limitations'],'changes':read(EP/'edit_decisions.json')['changes'],'publishing_enabled':False})


if __name__=='__main__':
    {'captures':captures,'assemble':assemble,'audit':audit,'verify':verify,'review':review,'package':package,'motion_qc':motion_qc}[sys.argv[1]]()
