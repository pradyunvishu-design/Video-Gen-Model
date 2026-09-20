"""Original silent DreamX diagrams; cached local Remotion frame-sequence render."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/episodes/episode_20260907_dreamx_creator/motion'
SPECS = {name: {'kind': name, 'seconds': 10} for name in ('together','stages','timing','protocol','runtime')}
RENDER_FRAMES = 180

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')

def run(cmd, timeout=1200, cwd=None):
    result = subprocess.run([str(x) for x in cmd], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', cwd=cwd, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stdout + result.stderr)[-6000:])
    return result.stdout

def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]))

def render(name, stills_only=False, preview=False):
    props = SPECS[name]
    source = ROOT / 'remotion/src/dreamx-entry.tsx'
    sig = hashlib.sha256(source.read_bytes() + json.dumps(props, sort_keys=True).encode()).hexdigest()
    frame_dir = OUT / 'frames' / f'{name}_{sig[:10]}'
    frame_dir.mkdir(parents=True, exist_ok=True)
    pp = OUT / f'{name}.props.json'
    dump(pp, props)
    dest = OUT / f'{name}.mp4'
    receipt = OUT / f'{name}.render.json'
    cmd = [ROOT / 'remotion/node_modules/.bin/remotion.cmd']
    browser = '--browser-executable=C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
    base = ['src/dreamx-entry.tsx', 'DreamXGraphic']
    if stills_only or preview:
        checkpoints = [('settled',179)] if preview else [('opening',0), ('developing',65), ('settled',179), ('exit',props['seconds']*30-1)]
        for label, frame in checkpoints:
            target = OUT / f'{name}_{label}.png'
            run(cmd + ['still'] + base + [target, f'--props={pp}', browser, f'--frame={frame}', '--image-format=png'], cwd=ROOT/'remotion')
        return
    if dest.exists() and receipt.exists() and json.loads(receipt.read_text()).get('input_hash') == sig and json.loads(receipt.read_text()).get('video_profile') == 'bt709-limited-v1':
        print('Cached', name, flush=True)
        return
    started = time.monotonic()
    frames = sorted(frame_dir.glob('*.jpeg'))
    if len(frames) != RENDER_FRAMES:
        result = subprocess.run([str(x) for x in cmd + ['render'] + base + [frame_dir, f'--props={pp}', browser, '--sequence', '--image-format=jpeg', '--jpeg-quality=96', '--concurrency=3', f'--frames=0-{RENDER_FRAMES-1}', '--muted']], cwd=ROOT/'remotion', capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800)
        (OUT / f'{name}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError((result.stdout+result.stderr)[-5000:])
    frames = sorted(frame_dir.glob('*.jpeg'))
    if len(frames) != RENDER_FRAMES:
        raise RuntimeError(f'Incomplete frame sequence: {name} {len(frames)}')
    listing = frame_dir/'sequence.txt'
    listing.write_text(''.join("file '"+x.as_posix()+"'\nduration 0.033333333333\n" for x in frames), encoding='utf-8')
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',listing,'-an','-vf',f"tpad=stop_mode=clone:stop_duration={props['seconds']},scale=out_color_matrix=bt709:out_range=tv,setsar=1,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709",'-r','30','-t',props['seconds'],'-c:v','libx264','-preset','fast','-crf','18','-threads','2','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',dest])
    meta=probe(dest)
    v=next(x for x in meta['streams'] if x['codec_type']=='video')
    run(['ffmpeg','-v','error','-i',dest,'-f','null','-'])
    checks={'1080p':v['width']==1920 and v['height']==1080,'fps30':v['r_frame_rate']=='30/1','h264':v['codec_name']=='h264','bt709_yuv420p':v['pix_fmt']=='yuv420p' and v.get('color_space')=='bt709','silent':not any(x['codec_type']=='audio' for x in meta['streams']),'duration':abs(float(meta['format']['duration'])-props['seconds'])<.05,'decode':True}
    if not all(checks.values()):
        raise RuntimeError(f'QC failed: {checks}')
    dump(receipt,{'input_hash':sig,'video_profile':'bt709-limited-v1','path':str(dest),'elapsed_seconds':round(time.monotonic()-started,2),'checks':checks,'original_editorial_diagram':True,'source_ids':['paper','refinement'] if name in ['stages','runtime'] else ['paper'] if name=='together' else [],'illustration':name in ['timing','protocol','runtime'],'publishing_enabled':False})
    for label, timestamp in [('opening',0),('developing',2.17),('settled',5.97),('exit',props['seconds']-.1)]:
        run(['ffmpeg','-y','-v','error','-ss',timestamp,'-i',dest,'-frames:v','1',OUT/f'{name}_{label}.png'])
    run(['ffmpeg','-y','-v','error','-i',dest,'-vf','fps=1,scale=384:216,tile=5x2','-frames:v','1',OUT/f'{name}_contact.png'])
    run(['ffmpeg','-y','-v','error','-i',OUT/f'{name}_settled.png','-vf','scale=480:270','-frames:v','1',OUT/f'{name}_mobile.png'])
    print('Ready',name,checks,flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--stills',action='store_true')
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--name',choices=list(SPECS))
    args=parser.parse_args()
    dump(OUT/'art_direction.json',{'version':2,'alternatives':['Source-paper crop with a single evidence callout','Open pictorial relationships with one semantic transformation','Sequential text ledger with progressive disclosure'],'selected':'Open pictorial relationships: joint clock, split route, impact alignment, test archive and end-to-end wait. These explain the mechanism without implying hands-on output.','selection_reason':'Paper crops are evidence elsewhere in the episode; another text ledger would repeat source shots and hide causal relationships. Original pictorial diagrams make timing, bypass and evaluation separations visible.','proof':'Technical report native joint generation and video-only refiner; timing, protocol and runtime scenes explicitly state their illustrative/editorial status.','frame_contract':{'canvas':'ivory','palette':['moss','slate','ink'],'safe_inset':110,'max_focal_groups':3,'headline_px':76,'body_min_px':29,'camera':'locked','reading_order':'headline, dominant object, meaningful relationship, resolved state','source_label':'quiet lower-left credit, no badge'},'motion_intents':{'together':'connect: exchanged information resolves onto one playhead crossing aligned picture/sound marks','stages':'connect: larger final-picture symbol, restrained waveform, full audio bypass path','timing':'emphasize: concrete ball impact replaces generic star; early sound shifts to contact','protocol':'connect: same input enters an archive of every output, then branches into three separate assessment criteria','runtime':'enter/connect: generation precedes refinement; a bracket collects both as the full workflow, without numerical time scale'},'motion_patterns':{'together':'graph-request-response','stages':'graph-dependency-chain','timing':'timeline-causality-chain','protocol':'activity-verification-pass','runtime':'stack-workflow-stages'},'animation_settles_by_frame':166,'specs':SPECS,'bounded_polish_passes':1,'no_third_party_media':True,'publishing_enabled':False})
    for name in ([args.name] if args.name else SPECS):
        render(name,args.stills,args.preview)

if __name__=='__main__':
    main()
