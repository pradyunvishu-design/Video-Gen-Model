"""Episode-specific private commentary cut. Never grants or clears media rights.

The user explicitly requested temporary inclusion after being told that the
official demo's reuse terms were unverified. This is NOT a publishing path.
Keep the accepted export, script, narrator, and ordinary rights gates unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import assemble_dreamx_full as original

EP = original.EP
OUT = EP / 'broll_private'
REEL = 'https://github.com/user-attachments/assets/e49fc64d-5b31-4c16-be1d-737dc3aef04b'
FPS = 30
VERSION = 1

# Frame-exact short excerpts, chosen from the source contact sheets. No loops.
# target frame, source frame, length frames, ID, narrative reason
INSERTS = [
    (433, 642, 114, 'shore', 'Release introduction: a moving example from the official showcase, not our own test.'),
    (1830, 1002, 102, 'conversation', 'Lip movement: people visibly speaking and reacting around a table.'),
    (2912, 432, 93, 'wave', 'Watch a launch clip muted: an obvious moving wave to follow visually.'),
    (4952, 786, 102, 'fire', 'Does sound fit what is visible: a clear fire example, without claiming that its audio was tested.'),
    (6839, 1359, 45, 'detail', 'Compare results: the source reel itself shows a side-by-side landscape; no invented benchmark or before/after label.'),
    (8979, 6, 135, 'speech', 'The final proposed test is speech: close-up of a speaking person from the showcase.'),
    (9516, 1434, 60, 'wildlife', 'A showcase demonstrates possibilities, not success rate: a distinct animal example.'),
    (13546, 909, 66, 'road', 'Conclusion: a moving scene from the release, credited as a showcase rather than our model test.'),
]

# A modest second pass: three unused source scenes and one closing callback.
EXTRA_INSERTS = [
    (2080, 309, 90, 'dialogue', 'Which visible event the sound belongs to: a speaking person gesturing in a conversation.'),
    (6620, 1260, 54, 'ice', 'A sharper picture and correct sound timing are different: a dynamic ice scene, not a fabricated before/after.'),
    (13215, 543, 72, 'storm', 'Narration discusses highly dynamic scenes: a distinct storm example from the showcase, not evidence that the limitation is solved.'),
    (14002, 432, 90, 'wave_callback', 'Closing question about whether the scene holds together: briefly revisit the wave shown six minutes earlier.'),
]


def revision_inserts(more_broll=False, natural_playout=False):
    base = sorted(INSERTS + (EXTRA_INSERTS if more_broll or natural_playout else []))
    if not natural_playout:
        return base
    # Source-paced sequences. In particular, do not cut away halfway through
    # the wave/storm/shore sequence or between the fire and road demonstrations.
    # Adjacent ice/detail excerpts remove the source's black interstitial rather
    # than interrupting them with a sub-two-second explanatory-card flash.
    windows = {
        'shore': (433, 642, 114),
        'conversation': (1830, 1002, 105),
        'dialogue': (2080, 294, 116),
        'wave': (2912, 426, 330),
        'fire': (4952, 786, 203),
        'ice': (6620, 1260, 70),
        'detail': (6690, 1348, 62),
        'speech': (8979, 0, 144),
        'wildlife': (9516, 1422, 78),
        'storm': (13215, 542, 82),
        'road': (13546, 909, 80),
    }
    return sorted((*windows[name], name, reason) for _,_,_,name,reason in base if name in windows)


def validate_inserts(inserts=INSERTS):
    last = 0
    ids = set()
    for target, source, frames, name, reason in inserts:
        if target < last or frames <= 0 or target + frames > 14400:
            raise ValueError('Overlapping or out-of-range replacement')
        if source < 0 or source + frames > 1713:
            raise ValueError('Source excerpt exceeds official reel')
        if name in ids or not reason:
            raise ValueError('Repeated excerpt or missing rationale')
        ids.add(name)
        last = target + frames
    # Count source-frame exposure rather than filenames so alternate IDs cannot
    # accidentally disguise a third replay of the same material.
    source_uses = [0] * 1713
    for _, source, frames, _, _ in inserts:
        for index in range(source, source+frames):
            source_uses[index] += 1
            if source_uses[index] > 2:
                raise ValueError('Source footage used more than twice')


def pieces(rows, inserts=INSERTS):
    """Split existing cached shots only at replacement edges; retain exact timing."""
    validate_inserts(inserts)
    result = []
    for row in rows:
        left, right = row['start_frame'], row['end_frame']
        cursor = left
        for target, source, frames, name, reason in inserts:
            end = target + frames
            if end <= left or target >= right:
                continue
            a, b = max(left, target), min(right, end)
            if cursor < a:
                result.append({'kind': 'base', 'row_id': row['id'], 'start': cursor,
                               'end': a, 'offset': cursor-left, 'full': cursor==left and a==right})
            result.append({'kind': 'broll', 'id': name, 'start': a, 'end': b,
                           'offset': source+a-target, 'reason': reason})
            cursor = b
        if cursor < right:
            result.append({'kind': 'base', 'row_id': row['id'], 'start': cursor,
                           'end': right, 'offset': cursor-left, 'full': cursor==left})
    if not result or result[0]['start'] != 0 or result[-1]['end'] != 14400:
        raise ValueError('Incomplete episode')
    if any(a['end'] != b['start'] for a,b in zip(result,result[1:])):
        raise ValueError('Timeline gap')
    return result


def remove_short_card_flashes(parts):
    """Absorb a sub-1.5s leftover card into the following editorial shot.

    Only the neighbouring original graphic is gently retimed; B-roll plays at
    source speed, and the audio timeline is never touched.
    """
    result=[]
    i=0
    while i<len(parts):
        current=parts[i]
        if (result and result[-1]['kind']=='broll' and current['kind']=='base'
                and current['end']-current['start']<45 and i+1<len(parts)
                and parts[i+1]['kind']=='base' and parts[i+1]['full']):
            following=dict(parts[i+1])
            following['retime_input_frames']=following['end']-following['start']
            following['start']=current['start']
            following['full']=False
            following['card_flash_removed']=current['row_id']
            result.append(following)
            i+=2
        else:
            result.append(current)
            i+=1
    return result


def encode(part):
    frames = part['end']-part['start']
    if part['kind']=='base':
        source = EP/'full_edit/segments'/(part['row_id']+'.mp4')
        if not source.is_file():
            raise FileNotFoundError(source)
        if part['full']:
            return source
        fingerprint = original.sha(source)
        vf = 'fps=30,setsar=1,format=yuv420p'
        if part.get('retime_input_frames'):
            ratio=frames/part['retime_input_frames']
            vf=f'setpts={ratio:.12f}*(PTS-STARTPTS),'+vf
    else:
        source = REEL
        fingerprint = REEL
        # Source captions sit at the bottom. Crop their narrow strip, not faces;
        # scale once with no fake camera motion. Only a small source credit added.
        crop_height = 620 if part['id'] in {'speech','dialogue'} else 660
        vf = (
            f'crop=1280:{crop_height}:0:0,scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,'
            'crop=1920:1080,setsar=1,fps=30,format=yuv420p,'
            "drawtext=font='Arial':text='Source  DreamX Team / AMAP-ML':fontsize=23:"
            'fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=9:x=36:y=h-53'
        )
    spec = {'part':part, 'source':fingerprint, 'filter':vf, 'version':VERSION}
    digest = hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
    dest = OUT/'segments'/f"{part['start']:05}_{part['end']:05}.mp4"
    receipt = dest.with_suffix('.json')
    if dest.exists() and receipt.exists():
        old = original.read(receipt)
        if old.get('input_hash')==digest and old.get('sha256')==original.sha(dest):
            return dest
    dest.parent.mkdir(parents=True,exist_ok=True)
    original.run(['ffmpeg','-y','-v','error','-ss',part['offset']/FPS,'-i',source,
                  '-map','0:v:0','-an','-vf',vf,'-frames:v',frames,
                  '-c:v','libx264','-preset','veryfast','-crf','18','-threads','2',
                  '-video_track_timescale','15360','-color_range','tv','-colorspace','bt709',
                  '-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',dest])
    meta = original.probe(dest)
    video = next(s for s in meta['streams'] if s['codec_type']=='video')
    if int(video.get('nb_frames',0)) != frames:
        raise ValueError('Wrong excerpt frame count')
    original.dump(receipt, {'input_hash':digest,'sha256':original.sha(dest),'spec':spec,
                           'source_audio_present':False,'rights_cleared':False if part['kind']=='broll' else None})
    print('Prepared '+dest.name,flush=True)
    return dest


def render_private(more_broll=False, natural_playout=False):
    original.audio_gate()
    OUT.mkdir(exist_ok=True)
    original_export = EP/'DreamX_Creator_8min_1080p.mp4'
    before = original.sha(original_export)
    rows = original.read(EP/'full_edit/timeline.json')
    inserts = revision_inserts(more_broll,natural_playout)
    suffix = '_v3' if natural_playout else ('_v2' if more_broll else '')
    timeline = pieces(rows,inserts)
    if natural_playout:
        timeline=remove_short_card_flashes(timeline)
    original.dump(OUT/f'private_review_manifest{suffix}.json', {
        'purpose':'Private editorial review requested by user; not approved for distribution',
        'user_direction':('some of the b-roll footage gets cut abruptly; let it play out' if natural_playout else ('try to include a little more b-roll footage' if more_broll else 'just inlcude in the video for now i\'ll tell u why later')),
        'edit_treatment':('Longer source-paced sequences; adjacent detail shots; no loop, slowdown, or ending wave replay' if natural_playout else 'Short editorial excerpts'),
        'rights_status':'unverified', 'publishing_enabled':False,
        'review_readiness':'blocked_for_publication_pending_media_rights',
        'source_url':'https://github.com/AMAP-ML/DreamX-Creator', 'media_url':REEL,
        'source_resolution':[1280,720], 'output_resolution':[1920,1080],
        'source_audio':'removed', 'synthetic_media':True,
        'original_export_sha256':before,
        'placements':[{'episode_start':a/FPS,'episode_end':(a+n)/FPS,'source_in':s/FPS,
                       'source_out':(s+n)/FPS,'id':i,'reason':r} for a,s,n,i,r in inserts],
        'narration_sha256':original.sha(EP/'narration_zubenelgenubi_8min.wav')})
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        paths = list(pool.map(encode,timeline))
    original.dump(OUT/f'timeline{suffix}.json',timeline)
    listing = original.write_concat(paths,OUT/f'concat{suffix}.txt')
    staged = OUT/f'DreamX_Private_Broll{suffix}.rendering.mp4'
    # Copy the *existing* approved AAC stream: byte-identical narration, no clip audio.
    original.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',listing,
                  '-i',original_export,'-map','0:v:0','-map','1:a:0','-c','copy',
                  '-t','480','-movflags','+faststart',staged])
    meta = original.probe(staged)
    v = next(s for s in meta['streams'] if s['codec_type']=='video')
    checks = {
        '1920x1080':(v['width'],v['height'])==(1920,1080),
        '480_seconds':abs(float(meta['format']['duration'])-480)<.05,
        '14400_frames':int(v.get('nb_frames',0))==14400,
        'h264':v['codec_name']=='h264', 'fps30':v['r_frame_rate']=='30/1',
        'one_audio_track':sum(s['codec_type']=='audio' for s in meta['streams'])==1,
        'no_subtitle_track':not any(s['codec_type']=='subtitle' for s in meta['streams']),
        'original_export_unchanged':before==original.sha(original_export),
    }
    def audio_hash(path):
        p=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0',
                          '-c:a','copy','-f','hash','-hash','sha256','-'],capture_output=True,check=True)
        return p.stdout.decode().strip()
    checks['audio_bitstream_identical']=audio_hash(staged)==audio_hash(original_export)
    original.run(['ffmpeg','-v','error','-i',staged,'-f','null','-'],timeout=1200)
    checks['full_decode']=True
    if not all(checks.values()):
        raise RuntimeError(str(checks))
    final = EP/f'DreamX_Creator_8min_Broll_Private{suffix}_1080p.mp4'
    original.promote_export(staged,final)
    original.dump(OUT/f'technical_qc{suffix}.json',{'checks':checks,'artifact':str(final),
                  'sha256':original.sha(final),'broll_inserts':len(inserts),
                  'broll_seconds':sum(x[2] for x in inserts)/FPS,
                  'visual_review':'pending','rights_status':'unverified','publishing_enabled':False})
    print('Private review export: '+str(final),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--private-review-authorized',action='store_true',required=True)
    parser.add_argument('--more-broll',action='store_true')
    parser.add_argument('--natural-playout',action='store_true')
    args=parser.parse_args()
    render_private(more_broll=args.more_broll,natural_playout=args.natural_playout)
