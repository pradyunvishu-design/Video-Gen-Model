"""Original pictorial editorial inserts, rendered quickly with Pillow and FFmpeg.

render_editorial(row, destination) accepts concept, headline, labels, duration.
Native 1920x1080 phases reveal the cause, connection, consequence and takeaway;
short crossfades are semantic entrances, never decorative camera drift.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import textwrap
import time
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
PAPER='#F3F2ED';INK='#24312E';MOSS='#647E6A';SLATE='#667780';PALE='#D6DDD5'
CONCEPTS={'cup_contact','keyboard_rhythm','review_modes','separate_scores','shared_timeline','image_prompt','piano','sharpness_not_sync','stopwatch_scope','retain_attempts','one_change','error_notes','memory_offload','creator_vs_researcher','caveats','final_question','speech_sync'}

def run(cmd):
    r=subprocess.run([str(v) for v in cmd],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1200)
    if r.returncode:raise RuntimeError((r.stdout+r.stderr)[-5000:])
    return r.stdout

def font(size,bold=False):return ImageFont.truetype('C:/Windows/Fonts/seguisb.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',size)

def text(d,xy,value,size=38,width=500,bold=False,color=INK):
    value=str(value)
    words=value.split();lines=[];line=''
    for word in words:
        candidate=(line+' '+word).strip()
        if d.textlength(candidate,font=font(size,bold))>width and line:lines.append(line);line=word
        else:line=candidate
    if line:lines.append(line)
    if len(lines)>2 and size>28:return text(d,xy,value,size-4,width,bold,color)
    if len(lines)>3:raise ValueError('Editorial text exceeds safe three-line area')
    for i,line in enumerate(lines):d.text((xy[0],xy[1]+i*(size+8)),line,font=font(size,bold),fill=color)

def line(d,points,color=SLATE,width=5):d.line(points,fill=color,width=width,joint='curve')
def arrow(d,a,b,color=SLATE):
    line(d,[a,b],color);angle=math.atan2(b[1]-a[1],b[0]-a[0]);r=19
    line(d,[(b[0]-r*math.cos(angle-.55),b[1]-r*math.sin(angle-.55)),b,(b[0]-r*math.cos(angle+.55),b[1]-r*math.sin(angle+.55))],color)
def film(d,x,y,w=320,h=205):
    d.rounded_rectangle((x,y,x+w,y+h),8,outline=INK,width=5)
    for i in range(7):
        sx=x+16+i*(w-38)/7
        d.rectangle((sx,y+13,sx+w/20,y+24),fill=PALE)
        d.rectangle((sx,y+h-24,sx+w/20,y+h-13),fill=PALE)
    d.polygon([(x+w*.1,y+h*.77),(x+w*.39,y+h*.38),(x+w*.58,y+h*.65),(x+w*.75,y+h*.48),(x+w*.9,y+h*.77)],fill=PALE)
    d.ellipse((x+w*.71-h*.07,y+h*.28-h*.07,x+w*.71+h*.07,y+h*.28+h*.07),fill=MOSS)
def wave(d,x,y,w=460,h=100):
    line(d,[(x,y),(x+w,y)],PALE,2)
    for i in range(35):
        a=h*(.1+.9*math.exp(-((i-18)/5)**2))*abs(math.sin(i*1.9))
        line(d,[(x+i*w/34,y-a),(x+i*w/34,y+a)],MOSS,max(3,int(w/90)))
def document(d,x,y,w=220,h=260):
    d.polygon([(x,y),(x+w-45,y),(x+w,y+45),(x+w,y+h),(x,y+h)],fill=PAPER,outline=INK,width=4)
    line(d,[(x+w-45,y),(x+w-45,y+45),(x+w,y+45)],SLATE,3)
    for i in range(4):line(d,[(x+30,y+85+i*35),(x+w-30-(i%2)*25,y+85+i*35)],PALE,7)
def clock(d,x,y,r=100):
    d.ellipse((x-r,y-r,x+r,y+r),outline=INK,width=5);line(d,[(x,y-r*.65),(x,y),(x+r*.47,y)],INK,5)
    line(d,[(x-22,y-r-26),(x+22,y-r-26)],INK,5);line(d,[(x,y-r-26),(x,y-r)],INK,5)
def folder(d,x,y,w=360,h=190):
    for i in range(2,-1,-1):document(d,x+35+i*17,y-85-i*21,w*.68,190)
    d.polygon([(x,y),(x+w*.32,y),(x+w*.4,y+27),(x+w,y+27),(x+w*.9,y+h),(x+22,y+h)],fill=PALE,outline=INK,width=4)
def magnifier(d,x,y,r=76):
    d.ellipse((x-r,y-r,x+r,y+r),outline=MOSS,width=8);line(d,[(x+r*.7,y+r*.7),(x+r*1.5,y+r*1.5)],MOSS,12)
def keyboard(d,x,y,w=600,h=205,piano=False,active=False):
    d.rounded_rectangle((x,y,x+w,y+h),8,outline=INK,width=5)
    if piano:
        for i in range(10):
            if active and i in [2,6]:d.rectangle((x+i*w/10+3,y+3,x+(i+1)*w/10-3,y+h-3),fill=PALE)
            line(d,[(x+i*w/10,y),(x+i*w/10,y+h)],INK,2)
        for i in [0,1,3,4,5,7,8]:d.rectangle((x+(i+.7)*w/10,y,x+(i+1.3)*w/10,y+h*.62),fill=INK)
    else:
        for row in range(3):
            for col in range(10):
                px=x+17+col*(w-27)/10;py=y+18+row*49
                d.rounded_rectangle((px,py,px+43,py+34),3,fill=MOSS if active and (row,col) in [(1,3),(0,6)] else PALE)
        d.rectangle((x+w*.26,y+h-38,x+w*.76,y+h-18),fill=PALE)
def eye(d,x,y):
    d.arc((x-115,y-76,x+115,y+100),195,345,fill=INK,width=6);d.arc((x-115,y-100,x+115,y+76),15,165,fill=INK,width=6)
    d.ellipse((x-35,y-35,x+35,y+35),fill=MOSS)
def speaker(d,x,y):
    d.polygon([(x-80,y-35),(x-35,y-35),(x+15,y-80),(x+15,y+80),(x-35,y+35),(x-80,y+35)],fill=PALE,outline=INK,width=4)
    d.arc((x-40,y-100,x+130,y+100),300,60,fill=MOSS,width=6)
def chip(d,x,y):
    d.rectangle((x,y,x+255,y+170),outline=INK,width=5);d.rectangle((x+48,y+35,x+207,y+135),fill=PALE)
    for i in range(7):
        for yy in [y-24,y+170]:line(d,[(x+27+i*33,yy),(x+27+i*33,yy+24)],MOSS,5)
def disk(d,x,y):
    d.rectangle((x,y,x+270,y+150),fill=PAPER);d.ellipse((x,y-35,x+270,y+35),fill=PALE,outline=INK,width=4)
    line(d,[(x,y),(x,y+150)],INK,4);line(d,[(x+270,y),(x+270,y+150)],INK,4)
    d.arc((x,y+115,x+270,y+185),0,180,fill=INK,width=4)
def warning(d,x,y):
    d.polygon([(x,y-115),(x-125,y+95),(x+125,y+95)],outline=INK,width=6)
    line(d,[(x,y-44),(x,y+25)],MOSS,11);d.ellipse((x-6,y+50,x+6,y+62),fill=MOSS)

def phase_image(row,phase):
    im=Image.new('RGB',(1920,1080),PAPER);d=ImageDraw.Draw(im);c=row['concept']
    text(d,(110,99),row.get('headline',c.replace('_',' ')),76,1700,True)
    labels=row.get('labels',[]);labels=list(labels.values()) if isinstance(labels,dict) else labels
    def label(i,x,y,width=500):
        if phase>=3 and i<len(labels):text(d,(x,y),labels[i],37,width,color=MOSS if i==2 else INK)
    if c in ['cup_contact','keyboard_rhythm','piano']:
        if c=='cup_contact':
            d.rounded_rectangle((355,370,565,620),26,outline=INK,width=6);d.arc((505,409,645,557),270,90,fill=INK,width=7);line(d,[(287,620),(687,620)],INK,5)
            if phase>=1:line(d,[(445,668),(475,668)],MOSS,7)
        else:keyboard(d,190,418,640,240,c=='piano',phase>=2)
        if phase>=1:arrow(d,(865,543),(1050,543))
        if phase>=2:wave(d,1140,543,540,115)
        label(0,220,738,650);label(1,1130,738,600)
    elif c=='review_modes':
        eye(d,365,497)
        if phase>=1:speaker(d,936,497)
        if phase>=2:clock(d,1495,497,94)
        label(0,175,695,420);label(1,755,695,430);label(2,1320,695,410)
    elif c=='separate_scores':
        film(d,205,348,245,155)
        if phase>=1:wave(d,222,623,220,60)
        if phase>=2:clock(d,325,814,61)
        for i in range(min(3,phase+1)):
            yy=[419,623,814][i]
            line(d,[(525,yy),(716,yy)],PALE,4)
            text(d,(772,yy-31),labels[i] if i<len(labels) else ['Picture','Sound','Timing'][i],44,730)
            d.rectangle((1630,yy-29,1685,yy+26),outline=SLATE,width=4)
    elif c=='shared_timeline':
        film(d,160,336,230,145)
        if phase>=1:wave(d,180,691,200,62)
        line(d,[(483,428),(1730,428)],PALE,4)
        if phase>=1:line(d,[(483,691),(1730,691)],PALE,4)
        if phase>=2:
            line(d,[(1185,348),(1185,776)],MOSS,5);d.rectangle((1162,398,1208,458),fill=MOSS);wave(d,1040,691,290,77)
        label(0,525,815,1150)
    elif c=='image_prompt':
        film(d,140,355,350,228)
        if phase>=1:document(d,691,354,260,266);text(d,(541,437),'+',84,100)
        if phase>=2:arrow(d,(1025,490),(1230,490));film(d,1320,355,370,228);wave(d,1325,660,360,60)
        label(0,158,744,490);label(1,697,744,420);label(2,1320,744,480)
    elif c=='sharpness_not_sync':
        film(d,235,372,440,270)
        if phase>=1:magnifier(d,681,605,72)
        if phase>=2:wave(d,1120,518,460,100);clock(d,1665,620,60)
        label(0,240,769,620);label(1,1090,769,620)
    elif c=='stopwatch_scope':
        clock(d,330,530,145)
        if phase>=1:film(d,771,348,270,175);wave(d,787,619,244,62)
        if phase>=2:arrow(d,(1120,487),(1320,487));film(d,1410,348,280,175)
        label(0,177,782,490);label(1,735,782,490);label(2,1330,782,440)
    elif c=='retain_attempts':
        document(d,240,361,270,327)
        if phase>=1:arrow(d,(593,535),(796,535))
        if phase>=2:folder(d,970,489,570,220)
        label(0,215,808,580);label(1,960,808,710)
    elif c=='one_change':
        for i in range(3):
            yy=390+i*113;line(d,[(210,yy),(770,yy)],PALE,7)
            pos=[365,620 if phase>=1 else 455,555][i];d.ellipse((pos-22,yy-22,pos+22,yy+22),fill=MOSS if i==1 and phase>=1 else SLATE)
        if phase>=2:arrow(d,(860,515),(1080,515));document(d,1250,358,310,320)
        label(0,205,789,690);label(1,1190,789,560)
    elif c=='error_notes':
        document(d,220,335,400,397)
        if phase>=1:magnifier(d,672,617,88)
        if phase>=2:arrow(d,(879,516),(1080,516));document(d,1280,353,290,340);line(d,[(1312,602),(1507,602)],MOSS,7)
        label(0,207,808,730);label(1,1197,808,570)
    elif c=='memory_offload':
        chip(d,280,416)
        if phase>=1:arrow(d,(660,501),(1110,501))
        if phase>=2:disk(d,1260,414);clock(d,1592,659,68)
        label(0,194,761,650);label(1,1200,761,580)
    elif c=='creator_vs_researcher':
        d.polygon([(300,595),(478,347),(525,384),(347,632)],fill=PALE,outline=INK,width=5);d.polygon([(300,595),(277,689),(347,632)],fill=MOSS)
        if phase>=1:
            line(d,[(1280,343),(1390,343)],INK,6);line(d,[(1300,345),(1300,470),(1180,649),(1500,649),(1370,470),(1370,345)],INK,6)
            d.polygon([(1260,549),(1430,549),(1479,627),(1200,627)],fill=PALE)
        if phase>=2:line(d,[(946,355),(946,706)],PALE,3)
        label(0,200,783,640);label(1,1110,783,650)
    elif c=='caveats':
        warning(d,355,507)
        for i in range(min(3,phase+1)):
            yy=346+i*164;d.rectangle((795,yy+13,810,yy+28),fill=MOSS)
            text(d,(860,yy),labels[i] if i<len(labels) else ['Check access','Check requirements','Verify the result'][i],44,860)
    elif c=='speech_sync':
        # Original mouth symbol, not a person's likeness or generated talking face.
        d.polygon([(253,480),(390,413),(466,441),(541,413),(683,480),(541,561),(390,561)],fill=PALE,outline=INK,width=5)
        line(d,[(253,480),(390,493),(541,493),(683,480)],INK,5)
        if phase>=1:wave(d,1080,484,570,113)
        if phase>=2:
            line(d,[(466,620),(466,709),(1370,709),(1370,620)],MOSS,4)
            line(d,[(924,681),(924,743)],INK,6)
        label(0,220,797,665);label(1,1080,797,665)
    elif c=='final_question':
        film(d,205,344,410,264)
        if phase>=1:wave(d,233,711,352,78)
        if phase>=2:
            magnifier(d,1220,507,144)
            text(d,(1168,384),'?',176,190,True)
        label(0,821,813,940)
    credit=row.get('illustration_label','Illustration')
    if credit:text(d,(110,985),credit,22,1600,color=SLATE)
    return im

def render_editorial(row,destination):
    row=dict(row);concept=row.get('concept')
    if concept not in CONCEPTS:raise ValueError(f'Unknown editorial concept: {concept}')
    seconds=float(row.get('duration',row.get('duration_seconds',row.get('seconds',10))))
    if not math.isfinite(seconds) or not .5<=seconds<=90:raise ValueError('Invalid editorial duration')
    frames=round(seconds*30);seconds=frames/30;dest=Path(destination).resolve();dest.parent.mkdir(parents=True,exist_ok=True)
    spec={'row':row,'frames':frames,'renderer_hash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    digest=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest();receipt_path=dest.with_suffix('.editorial.json')
    if dest.exists() and receipt_path.exists():
        old=json.loads(receipt_path.read_text())
        if old.get('input_hash')==digest and old.get('output_sha256')==hashlib.sha256(dest.read_bytes()).hexdigest():return dict(old,cached=True)
    assets=dest.parent/'editorial_frames'/digest[:12];assets.mkdir(parents=True,exist_ok=True)
    for phase in range(4):phase_image(row,phase).save(assets/f'{phase}.png')
    command=['ffmpeg','-y','-v','error','-filter_complex_threads','2']
    for phase in range(4):command+=['-loop','1','-framerate','30','-i',assets/f'{phase}.png']
    offsets=[seconds*.2,seconds*.4,seconds*.64];fade=min(.23,seconds*.06)
    filters=[f'[{i}:v]format=yuv444p,settb=1/30,setpts=PTS-STARTPTS[p{i}]' for i in range(4)]
    filters += [f'[p0][p1]xfade=transition=fade:duration={fade}:offset={offsets[0]}[a]',f'[a][p2]xfade=transition=fade:duration={fade}:offset={offsets[1]}[b]',f'[b][p3]xfade=transition=fade:duration={fade}:offset={offsets[2]},scale=out_color_matrix=bt709:out_range=tv,setsar=1,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709[out]']
    tmp=dest.with_name(dest.stem+'.rendering.mp4');started=time.monotonic()
    command+=['-filter_complex',';'.join(filters),'-map','[out]','-an','-frames:v',frames,'-r','30','-c:v','libx264','-preset','veryfast','-crf','18','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',tmp]
    run(command)
    meta=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',tmp]));v=meta['streams'][0]
    checks={'1080p':(v['width'],v['height'])==(1920,1080),'fps30':v['r_frame_rate']=='30/1','h264':v['codec_name']=='h264','silent':len(meta['streams'])==1,'rec709':v.get('color_space')=='bt709','duration':abs(float(meta['format']['duration'])-seconds)<.04}
    run(['ffmpeg','-v','error','-i',tmp,'-f','null','-']);checks['decode']=True
    if not all(checks.values()):raise RuntimeError(f'Editorial QC failed: {checks}')
    tmp.replace(dest)
    receipt={'path':str(dest),'input_hash':digest,'output_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'duration_seconds':seconds,'cached':False,'checks':checks,'elapsed_seconds':round(time.monotonic()-started,2),'concept':concept,'original_illustration':True,'phase_preview':str(assets/'3.png'),'motion':'Four semantic reveals with short fades; locked framing','publishing_enabled':False}
    receipt_path.write_text(json.dumps(receipt,indent=2),encoding='utf-8');return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('row_json');parser.add_argument('destination');args=parser.parse_args()
    print(json.dumps(render_editorial(json.loads(Path(args.row_json).read_text(encoding='utf-8')),args.destination),indent=2))
