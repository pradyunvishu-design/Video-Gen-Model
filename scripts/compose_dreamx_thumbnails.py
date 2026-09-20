"""Finish existing generated plates with exact official identity and typography."""
import hashlib, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

OUT=Path(__file__).resolve().parents[1]/'data/episodes/episode_20260907_dreamx_creator/thumbnails'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def font(n): return ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',n)
def main():
    logo_path=OUT/'dreamx_official_avatar.png'
    logo=Image.open(logo_path).convert('RGB').crop((38,90,423,355))
    words=[('IT MAKES','SOUND'),('VIDEO WITH','SOUND'),('VIDEO MEETS','AUDIO'),('ONE IMAGE.','BOTH.')]
    candidates=[]
    for i,lines in enumerate(words):
        canvas=ImageOps.fit(Image.open(OUT/f'plate_{i}.png').convert('RGB'),(1920,1080),method=Image.Resampling.LANCZOS)
        draw=ImageDraw.Draw(canvas)
        # The original avatar background is intentionally retained inside a brand badge.
        badge=ImageOps.contain(logo,(370,255),Image.Resampling.LANCZOS)
        canvas.paste(badge,(88,90))
        for n,line in enumerate(lines):
            size=135 if n==0 else 158
            while draw.textbbox((0,0),line,font=font(size))[2]>770: size-=1
            y=427+n*180
            if n==1:
                width=draw.textbbox((0,0),line,font=font(size))[2]
                draw.rectangle((78,y-10,110+width,y+size+20),fill='#a8c7bf')
            draw.text((95,y),line,font=font(size),fill='#f5f3ec' if n==0 else '#142823',stroke_width=0)
        path=OUT/f'dreamx_concept_{i+1}_1080p.jpg'
        canvas.save(path,quality=94,subsampling=0)
        canvas.resize((320,180),Image.Resampling.LANCZOS).save(OUT/f'dreamx_concept_{i+1}_mobile.png')
        ImageOps.grayscale(canvas).resize((320,180),Image.Resampling.LANCZOS).save(OUT/f'dreamx_concept_{i+1}_gray.png')
        candidates.append({'path':str(path),'headline':' '.join(lines),'sha256':sha(path),'brand_placements':[{'key':'dreamx','bounds':[88,90,370,255]}],'conceptual_art_not_model_output':True})
    manifest={'represented_companies':['dreamx'],'resolved_brand_assets':[{'key':'dreamx','asset_path':str(logo_path),'official_source_url':'https://github.com/AMAP-ML','download_url':'https://avatars.githubusercontent.com/u/202896035?v=4','sha256':sha(logo_path),'generated':False,'cutout_method':'none; intentional original-background identity badge'}],'candidates':candidates,'recommended':candidates[0]['path'],'evidence_ids':['E01','E02'],'provider':'Magic Hour direct API','model':'nano-banana-2','credits_charged':sum(json.loads((OUT/f'job_{i}.json').read_text()).get('credits_charged',0) for i in range(4)),'human_review_status':'awaiting user review','public_upload_blocker':'Source video excerpt reuse rights unverified'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    sheet=Image.new('RGB',(1280,720),'#111111')
    for i in range(4):
        im=Image.open(OUT/f'dreamx_concept_{i+1}_1080p.jpg').resize((640,360),Image.Resampling.LANCZOS)
        sheet.paste(im,((i%2)*640,(i//2)*360))
    sheet.save(OUT/'four_concepts.jpg',quality=94)
    print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()
