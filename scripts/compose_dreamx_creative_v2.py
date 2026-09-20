"""Original conceptual DreamX covers, preserving exact official logo pixels."""
import json, hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/episodes/episode_20260907_dreamx_creator/thumbnails_v2'
LOGO=OUT.parent/'thumbnails/dreamx_official_avatar.png'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def font(s): return ImageFont.truetype('C:/Windows/Fonts/impact.ttf',s)

def main():
    brief=json.loads((OUT/'creative_brief.json').read_text())
    manifest={'represented_companies':['dreamx'],'resolved_brand_assets':[{'key':'dreamx','asset_path':str(LOGO),'official_source_url':'https://github.com/AMAP-ML','generated':False,'sha256':sha(LOGO),'treatment':'Original avatar inside circular crop; no logo recoloring or background removal'}],'candidates':[],'credits_charged':600,'provider':'Magic Hour direct API','model':'nano-banana-2'}
    for i,c in enumerate(brief['concepts']):
        canvas=ImageOps.fit(Image.open(OUT/f'plate_{i}.png').convert('RGB'),(1920,1080),method=Image.Resampling.LANCZOS)
        d=ImageDraw.Draw(canvas)
        # Clean reserved header; does not replace or alter the conceptual hero.
        if i in (1,2): d.rectangle((0,0,1920,355),fill='#f3f0e7')
        brand=Image.open(LOGO).convert('RGB').resize((290,290),Image.Resampling.LANCZOS)
        mask=Image.new('L',(290,290)); ImageDraw.Draw(mask).ellipse((0,0,289,289),fill=255)
        canvas.paste(brand,(55,44),mask)
        for j,line in enumerate(c['headline']):
            size=155
            while d.textbbox((0,0),line,font=font(size))[2]>1450: size-=1
            x=405; y=45+j*153
            # Emphasize the final word, not a generic colored slab behind all copy.
            if j==1:
                prefix,word=line.rsplit(' ',1) if ' ' in line else ('',line)
                prefix=(prefix+' ') if prefix else ''
                pw=d.textlength(prefix,font=font(size))
                wb=d.textbbox((0,0),word,font=font(size))
                d.rectangle((x+pw-6,y+24,x+pw+wb[2]+9,y+size+15),fill='#13596a')
                d.text((x,y),prefix,font=font(size),fill='#12262b')
                d.text((x+pw,y),word,font=font(size),fill='#ffffff')
            else: d.text((x,y),line,font=font(size),fill='#12262b')
        path=OUT/f'dreamx_creative_{i+1}_1080p.jpg'
        canvas.save(path,quality=95,subsampling=0)
        canvas.resize((320,180),Image.Resampling.LANCZOS).save(OUT/f'dreamx_creative_{i+1}_mobile.png')
        ImageOps.grayscale(canvas).resize((320,180),Image.Resampling.LANCZOS).save(OUT/f'dreamx_creative_{i+1}_gray.png')
        manifest['candidates'].append({'path':str(path),'headline':' '.join(c['headline']),'visual_mechanism':c['mechanism'],'conceptual_art_not_model_output':True,'sha256':sha(path),'brand_placements':[{'key':'dreamx','bounds':[55,44,290,290]}]})
    manifest['recommended']=manifest['candidates'][0]['path']
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    sheet=Image.new('RGB',(1280,720))
    for i in range(4): sheet.paste(Image.open(OUT/f'dreamx_creative_{i+1}_1080p.jpg').resize((640,360),Image.Resampling.LANCZOS),((i%2)*640,(i//2)*360))
    sheet.save(OUT/'four_concepts.jpg',quality=94)
    print(manifest['recommended'])
if __name__=='__main__': main()
