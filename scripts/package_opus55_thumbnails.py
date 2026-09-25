"""Package four original thumbnail concepts for private episode review."""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / 'data/episodes/episode_20260923_opus55_six_demos'
OUT = EP / 'thumbnails'
BRAND = ROOT / 'data/episodes/episode_20260902_fable_mythos/media/brand/Claude Spark - Clay.png'
PLATE = OUT / 'receipt_plate_v02.png'
INK, CREAM, CLAY, SAGE = '#191c1b', '#f3efe6', '#d97757', '#adbbb1'
FONT = 'C:/Windows/Fonts/arialbd.ttf'
HEAVY = 'C:/Windows/Fonts/impact.ttf'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def text(im, words, xy, size, color=CREAM, font=HEAVY):
    ImageDraw.Draw(im).text(xy, words, font=ImageFont.truetype(font, size), fill=color, anchor='lt')

def brand(im, xy=(80,75), size=170, color=CREAM):
    logo=Image.open(BRAND).convert('RGBA')
    logo=logo.crop(logo.getbbox())
    logo.thumbnail((size,size),Image.Resampling.LANCZOS)
    im.paste(logo,xy,logo)
    text(im,'CLAUDE', (xy[0]+size+27,xy[1]+20),51,color,FONT)
    text(im,'OPUS 5.5',(xy[0]+size+27,xy[1]+86),68,color,FONT)
    return {'key':'claude','bounds':[xy[0],xy[1],size,size]}

def save(im, key, headline, mechanism, placements, evidence):
    path=OUT/f'opus55_{key}_v01.jpg'
    im.save(path,quality=96,subsampling=0,optimize=True)
    im.save(path.with_suffix('.png'),optimize=True)
    im.resize((320,180),Image.Resampling.LANCZOS).save(OUT/f'{key}_mobile.png')
    ImageOps.grayscale(im).resize((320,180),Image.Resampling.LANCZOS).save(OUT/f'{key}_gray.png')
    return {'path':str(path),'headline':headline,'mechanism':mechanism,'brand_placements':placements,'evidence_ids':evidence,'sha256':sha(path),'review':'pending'}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    candidates=[]
    im=Image.open(PLATE).convert('RGB').resize((1920,1080),Image.Resampling.LANCZOS)
    p=brand(im)
    text(im,'CHEAPER.',(75,368),169)
    text(im,'BUT',(77,566),138)
    ImageDraw.Draw(im).rectangle((71,741,711,956),fill=CLAY)
    text(im,'HOW?',(101,750),193,INK)
    # Editorial typography, not a fabricated invoice or user result.
    text(im,'TOKEN PRICE',(1080,300),35,INK,FONT)
    text(im,'20%',(1080,415),158,INK)
    text(im,'LESS',(1139,615),48,INK,FONT)
    text(im,'TASK COST',(1526,414),34,INK,FONT)
    text(im,'40%',(1518,510),145,INK)
    text(im,'LESS',(1580,677),45,INK,FONT)
    text(im,'TYPICAL WORKLOADS',(1518,774),25,INK,FONT)
    text(im,'Anthropic reports reductions vs Opus 5',(1010,987),27,CREAM,FONT)
    candidates.append(save(im,'receipt','CHEAPER. BUT HOW?','Two different price metrics create a question the opening resolves.',[p],['release','overview']))

    im=Image.new('RGB',(1920,1080),CREAM);d=ImageDraw.Draw(im)
    p=brand(im,(80,63),150,INK)
    text(im,'WHY TWO NUMBERS?',(80,300),132,INK)
    d.rectangle((75,513,925,969),fill=INK);d.rectangle((950,513,1845,969),fill=SAGE)
    text(im,'20%',(155,544),256,CREAM)
    text(im,'40%',(1035,544),256,INK)
    text(im,'TOKEN PRICE',(148,865),46,CREAM,FONT)
    text(im,'TYPICAL TASK COST',(1020,865),46,INK,FONT)
    text(im,'Anthropic-reported reductions vs Opus 5',(82,1011),27,INK,FONT)
    candidates.append(save(im,'two_numbers','WHY TWO NUMBERS?','Evidence contrast: different denominators, not a contradiction.',[p],['release','overview']))

    im=Image.new('RGB',(1920,1080),INK)
    p=brand(im,(80,75),174)
    text(im,'CLAUDE',(80,390),157)
    text(im,'BUILT',(80,570),157)
    ImageDraw.Draw(im).rectangle((73,769,750,975),fill=SAGE)
    text(im,'THIS?',(94,782),181,INK)
    proof=Image.open(EP/'edit/05_work_3_01-end.jpg').convert('RGB')
    # Preserve the complete official frame without inventing UI or retouching output.
    proof.thumbnail((1000,770),Image.Resampling.LANCZOS)
    im.paste(proof,(865,320))
    text(im,'OFFICIAL EARTHRISE DEMO',(885,927),34,CREAM,FONT)
    candidates.append(save(im,'real_demo','CLAUDE BUILT THIS?','Authentic release output is the payoff, not invented generated proof.',[p],['earthrise']))

    im=Image.new('RGB',(1920,1080),CREAM);d=ImageDraw.Draw(im)
    p=brand(im,(82,70),160,INK)
    text(im,'LESS',(80,415),182,INK)
    text(im,'BACK-AND-',(80,620),130,INK)
    d.rectangle((74,780,795,978),fill=SAGE)
    text(im,'FORTH?',(92,794),166,INK)
    # A qualitative workflow sketch, deliberately not a measured performance chart.
    for i in range(5):
        x=995+(i%2)*490;y=345+i*110
        d.rounded_rectangle((x,y,x+315,y+62),radius=8,fill='#d5d3cc')
        if i<4:d.line((x+155,y+63,1300, y+90),fill='#8d958e',width=8)
    d.rounded_rectangle((1060,903,1775,1000),radius=16,fill=INK)
    text(im,'FINISHED WORK',(1090,923),55,CREAM,FONT)
    candidates.append(save(im,'workflow','LESS BACK-AND-FORTH?','Qualitative illustration of fewer retries, not a fixed step count claim.',[p],['github','release']))

    manifest={'schema':'opus55-thumbnail-package.v1','dimensions':[1920,1080],
      'represented_companies':['claude'],'resolved_brand_assets':[{'key':'claude','asset_path':str(BRAND),'official_source_url':'https://www.anthropic.com/press-kit','generated':False,'sha256':sha(BRAND),'cutout':'existing transparent PNG; no background removal; uniform resize only'}],
      'candidates':candidates,'recommended':candidates[0]['path'],
      'hook_angles':['CHEAPER. BUT HOW?','WHY TWO NUMBERS?','CLAUDE BUILT THIS?','LESS BACK-AND-FORTH?','FOLLOW THE BILL','THE REAL UPGRADE','WHAT ACTUALLY CHANGED?','LOOK PAST THE SCORE'],
      'sources':['https://www.anthropic.com/claude-opus-5-5','https://platform.claude.com/docs/en/models/opus-5-5/overview'],
      'generated_plate':{'path':str(PLATE),'sha256':sha(PLATE),'provider':'built-in image_gen','purpose':'editorial paper metaphor, not actual model output'},
      'forbidden_implications':['guaranteed 40 percent saving for every user','our independent model test','official endorsement'],
      'publishing_enabled':False}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(candidates[0]['path'])

if __name__=='__main__':main()
