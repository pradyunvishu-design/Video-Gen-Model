"""Fast source-only evidence motion. No fake clicks or unmeasured underlines.

API: render_source_shot(source_path, destination, duration_seconds, focus=None,
                       annotation=None, cursor=True, framing=None, zoom=1.028)
focus: normalized dict {x,y,width,height}, or pixel sequence [x,y,w,h].
annotation: complete capture manifest such as captures/source_focus.json.
framing: source pixel crop [x,y,w,h]; None selects known capture framing.
Return: receipt dict including path, checks, cache status and input hash.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / 'data/episodes/episode_20260907_dreamx_creator'
OUT = EP / 'source_motion'
W, H, FPS = 1920, 1080, 30

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(command, timeout=1200):
    r = subprocess.run([str(v) for v in command], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=timeout)
    if r.returncode:
        raise RuntimeError((r.stdout+r.stderr)[-6500:])
    return r

def probe(path):
    return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',path]).stdout)

def box(value):
    if isinstance(value, dict):
        vals = [float(value[k]) for k in ('x','y','width','height')]
        if value.get('units','normalized') != 'pixels':
            vals = [vals[0]*W,vals[1]*H,vals[2]*W,vals[3]*H]
    else:
        vals = list(map(float,value))
    if len(vals)!=4 or not all(math.isfinite(v) for v in vals):
        raise ValueError('Region must have four finite coordinates')
    x,y,w,h=vals
    if not (0<=x<x+w<=W and 0<=y<y+h<=H):
        raise ValueError(f'Region outside source viewport: {vals}')
    return vals

def default_framing(source):
    if source.name == 'repository_input_focus.png':
        return [60,90,1340,900]
    if source.parent.name == 'captures':
        if source.name.startswith(('generation_','refinement_','weights_')):
            return [500,0,1400,1080]
        if source.name.startswith('repository_'):
            return [60,0,1340,1080]
    return [0,0,W,H]

def pointer_asset():
    from PIL import Image, ImageDraw
    path=OUT/'pointer_micro.png'
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        im=Image.new('RGBA',(9,12),(0,0,0,0))
        draw=ImageDraw.Draw(im)
        draw.polygon([(0,0),(0,9),(3,6),(5,11),(7,10),(5,6),(8,6)],fill='white',outline='#17221D',width=1)
        im.save(path)
    return path

def validate_annotations(record, source_hash, crop, duration):
    if record is None:
        return [],[]
    rejected=[]
    if not isinstance(record,dict) or record.get('sha256')!=source_hash or record.get('viewport')!=[W,H]:
        return [],['Underline rejected: missing/mismatched capture hash or viewport']
    visible=record.get('visible_text','')
    if not isinstance(visible,str) or not isinstance(record.get('annotations'),list):
        return [],['Underline rejected: invalid captured text or annotations list']
    valid=[]
    for item in record.get('annotations',[]):
        if not isinstance(item,dict):
            rejected.append('Underline rejected: annotation is not an object')
            continue
        try:
            if item.get('measurement')!='exact single-line browser DOM Range' or not item.get('narration_cue'):
                raise ValueError('missing exact DOM Range or narration cue')
            if not item.get('phrase') or item['phrase'] not in visible:
                raise ValueError('phrase not in captured visible text')
            region=box(item['region']); x,y,w,h=region
            if h>110 or w<5:
                raise ValueError('not a plausible single text line')
            if not(crop[0]<=x<x+w<=crop[0]+crop[2] and crop[1]<=y<y+h+5<=crop[1]+crop[3]):
                raise ValueError('annotation excluded by framing')
            start,end=float(item['start']),float(item['end'])
            if not(0<=start<end<=duration):
                raise ValueError('annotation time outside shot')
            valid.append(dict(item,pixel_region=region,start=start,end=end))
        except (KeyError,TypeError,ValueError) as exc:
            rejected.append(f"Underline rejected for {item.get('phrase','unknown')}: {exc}")
    valid.sort(key=lambda a:a['start'])
    return valid,rejected

def render_source_shot(source_path, destination, duration_seconds, focus=None,
                       annotation=None, cursor=True, framing=None, zoom=1.028):
    source,dest=Path(source_path).resolve(),Path(destination).resolve()
    seconds=float(duration_seconds)
    if not source.is_file() or source==dest or dest.suffix.lower()!='.mp4':
        raise ValueError('Source must exist and destination must be a different MP4')
    if not math.isfinite(seconds) or not 0.2<=seconds<=120:
        raise ValueError('Shot duration must be between 0.2 and 120 seconds')
    if not math.isfinite(zoom) or not 1<zoom<=1.03:
        raise ValueError('Directed zoom must be greater than 1 and at most 1.03')
    meta=probe(source); video=next(s for s in meta['streams'] if s['codec_type']=='video')
    if (video['width'],video['height'])!=(W,H):
        raise ValueError('Source screenshot must be exactly 1920x1080')
    crop=box(framing if framing is not None else default_framing(source))
    source_hash=sha(source)
    anns,rejected=validate_annotations(annotation,source_hash,crop,seconds)
    region=box(focus) if focus is not None else (anns[0]['pixel_region'] if anns else crop)
    cx,cy=region[0]+region[2]/2,region[1]+region[3]/2
    if not(crop[0]<=cx<=crop[0]+crop[2] and crop[1]<=cy<=crop[1]+crop[3]):
        raise ValueError('Focus center is outside the selected framing')
    scale=min(W/crop[2],H/crop[3]); sw,sh=round(crop[2]*scale),round(crop[3]*scale)
    px,py=(W-sw)/2,(H-sh)/2
    transform=lambda x,y: ((x-crop[0])*scale+px,(y-crop[1])*scale+py)
    fx,fy=transform(cx,cy)
    frames=round(seconds*FPS); actual_seconds=frames/FPS
    spec={'source_hash':source_hash,'duration_frames':frames,'focus':region,'framing':crop,
          'cursor':bool(cursor),'zoom':zoom,'annotations':anns,'renderer_hash':sha(__file__)}
    digest=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
    receipt_path=dest.with_suffix('.motion.json')
    if dest.exists() and receipt_path.exists():
        prior=json.loads(receipt_path.read_text(encoding='utf-8'))
        if prior.get('input_hash')==digest and prior.get('output_sha256')==sha(dest):
            return dict(prior,cached=True)
    dest.parent.mkdir(parents=True,exist_ok=True)
    filters=[f"[0:v]crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]},scale={sw}:{sh}:flags=lanczos,pad={W}:{H}:{px}:{py}:color=0xF3F2ED,format=yuv444p[base]"]
    current='base'
    cursor_cues=[]
    for a in anns:
        x,y,w,h=a['pixel_region']; ax,ay=transform(x,y+h)
        width=w*scale; ay+=3
        start,end=a['start'],a['end']; draw_time=min(.85,(end-start)*.65)
        segments=[]
        for i in range(32):
            left=round(ax+width*i/32); right=round(ax+width*(i+1)/32)
            threshold=start+draw_time*(i/32)
            segments.append(f"drawbox=x={left}:y={round(ay)}:w={max(1,right-left)}:h=3:color=0xBA3D36:t=fill:enable='between(t,{threshold:.5f},{end:.5f})'")
        nxt=f"line{len(cursor_cues)}"
        filters.append(f"[{current}]"+','.join(segments)+f'[{nxt}]');current=nxt
        cursor_cues.append((ax,ay-1,width,start,end,draw_time))
    command=['ffmpeg','-y','-v','error','-filter_complex_threads','2','-loop','1','-framerate',FPS,'-i',source]
    if cursor:
        command+=['-loop','1','-framerate',FPS,'-i',pointer_asset()]
        if cursor_cues:
            x_expr,y_expr='-100','-100'
            for ax,ay,width,start,end,draw_time in reversed(cursor_cues):
                u=f'clip((t-{start})/{draw_time},0,1)'
                x_expr=f'if(between(t,{start},{end}),{ax}+{width}*{u},{x_expr})'
                y_expr=f'if(between(t,{start},{end}),{ay},{y_expr})'
        else:
            travel=min(1.5,seconds*.35);u=f'clip(t/{travel},0,1)';ease=f'(1-pow(1-{u},3))'
            x_expr=f'{fx}-75+75*{ease}';y_expr=f'{fy}+55-55*{ease}'
        filters.append(f"[{current}][1:v]overlay=x='{x_expr}':y='{y_expr}':eval=frame:shortest=1:format=yuv444[cursor]")
        current='cursor'
    # Per-frame floating-point affine transform avoids integer-crop zoom jitter.
    # No actual perspective/skew: every corner has the same scale about the focus.
    delta=f'({zoom-1:.8f}*on/{max(1,frames-1)})'
    filters.append(f"[{current}]perspective=x0='-{fx}*{delta}':y0='-{fy}*{delta}':x1='W+(W-{fx})*{delta}':y1='-{fy}*{delta}':x2='-{fx}*{delta}':y2='H+(H-{fy})*{delta}':x3='W+(W-{fx})*{delta}':y3='H+(H-{fy})*{delta}':sense=destination:eval=frame:interpolation=cubic,scale=out_color_matrix=bt709:out_range=tv,setsar=1,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709[out]")
    temporary=dest.with_name(dest.stem+'.rendering.mp4')
    command+=['-filter_complex',';'.join(filters),'-map','[out]','-an','-frames:v',frames,'-r',FPS,'-c:v','libx264','-preset','veryfast','-crf','18','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',temporary]
    started=time.monotonic();run(command)
    result=probe(temporary);v=next(s for s in result['streams'] if s['codec_type']=='video')
    run(['ffmpeg','-v','error','-i',temporary,'-f','null','-'])
    checks={'1080p':(v['width'],v['height'])==(W,H),'fps30':v['r_frame_rate']=='30/1',
            'h264':v['codec_name']=='h264','rec709':v.get('color_space')=='bt709','silent':len(result['streams'])==1,
            'duration':abs(float(result['format']['duration'])-actual_seconds)<.04,'decode':True}
    if not all(checks.values()):
        raise RuntimeError(f'Source motion QC failed: {checks}')
    temporary.replace(dest)
    receipt={'path':str(dest),'input_hash':digest,'output_sha256':sha(dest),'cached':False,'checks':checks,
             'duration_seconds':actual_seconds,'elapsed_seconds':round(time.monotonic()-started,3),
             'motion':'directed subpixel push-in around exact focus; measured underline/cursor when available',
             'validated_underlines':len(anns),'rejected_annotations':rejected,'spec':spec,'publishing_enabled':False}
    receipt_path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return receipt

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source');parser.add_argument('destination');parser.add_argument('--seconds',type=float,required=True)
    parser.add_argument('--focus',help='JSON region or pixel [x,y,w,h]')
    parser.add_argument('--framing',help='JSON pixel [x,y,w,h]')
    parser.add_argument('--annotation',help='Path to complete capture annotation JSON')
    parser.add_argument('--no-cursor',action='store_true');parser.add_argument('--zoom',type=float,default=1.028)
    args=parser.parse_args()
    result=render_source_shot(args.source,args.destination,args.seconds,
        focus=json.loads(args.focus) if args.focus else None,
        annotation=json.loads(Path(args.annotation).read_text(encoding='utf-8')) if args.annotation else None,
        cursor=not args.no_cursor,framing=json.loads(args.framing) if args.framing else None,zoom=args.zoom)
    print(json.dumps({k:result[k] for k in ('path','cached','checks','duration_seconds','validated_underlines','rejected_annotations')},indent=2))

if __name__=='__main__':
    main()
