"""User-directed partial-blur reveal from an authentic launch example."""
from pathlib import Path
import json,hashlib
from PIL import Image,ImageOps,ImageFilter,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
EP=ROOT/'data/episodes/episode_20260908_chatgpt_images25'
OUT=EP/'thumbnails';OUT.mkdir(exist_ok=True)

def main():
    from playwright.sync_api import sync_playwright
    logo=ROOT/'remotion/public/brands/openai.svg'
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=b.new_page(viewport={'width':300,'height':304},device_scale_factor=2)
        page.set_content('<style>body{margin:0;background:#f4f3ef}svg{width:300px;height:304px}</style>'+logo.read_text())
        page.screenshot(path=str(OUT/'official_logo.png'));b.close()
    proof=next(x for x in json.loads((EP/'media/thumbnail_proofs.json').read_text(encoding='utf-8')) if x['id']=='sci-fi-surrealism.png')
    source=Image.open(proof['path']).convert('RGB')
    canvas=Image.new('RGB',(1920,1080),'#f4f3ef');draw=ImageDraw.Draw(canvas)
    # A crisp fragment preserves the real output's visual premise; only the
    # central reveal is blurred. This is not a fabricated generation result.
    photo=ImageOps.fit(source,(1020,980),Image.Resampling.LANCZOS,centering=(.57,.5))
    mask=Image.new('L',photo.size,0);md=ImageDraw.Draw(mask)
    md.rectangle((45,180,980,740),fill=255);mask=mask.filter(ImageFilter.GaussianBlur(14))
    photo=Image.composite(photo.filter(ImageFilter.GaussianBlur(25)),photo,mask)
    draw.rectangle((863,45,1890,1042),fill='#151918');canvas.paste(photo,(870,52))
    logoim=Image.open(OUT/'official_logo.png').convert('RGB');logoim.thumbnail((190,194),Image.Resampling.LANCZOS);canvas.paste(logoim,(70,70))
    draw=ImageDraw.Draw(canvas)
    font=lambda size:ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',size)
    draw.text((77,314),'IT CAN DO',font=font(116),fill='#171b19')
    draw.text((65,436),'WHAT?',font=font(200),fill='#171b19')
    draw.text((81,695),'ChatGPT Images 2.5',font=font(46),fill='#45504c')
    # A single editorial arrow points into the real obscured result.
    points=[(605,767),(760,818),(992,720),(1110,585)]
    draw.line(points,fill='#f4f3ef',width=20,joint='curve')
    draw.line(points,fill='#171b19',width=10,joint='curve')
    draw.polygon([(1118,575),(1070,596),(1103,623)],fill='#171b19',outline='#f4f3ef',width=3)
    path=OUT/'images25_it_can_do_what_v01.png';canvas.save(path)
    canvas.save(OUT/'images25_it_can_do_what_v01.jpg',quality=96,subsampling=0)
    canvas.resize((320,180),Image.Resampling.LANCZOS).save(OUT/'images25_mobile.png')
    ImageOps.grayscale(canvas).resize((320,180),Image.Resampling.LANCZOS).save(OUT/'images25_gray.png')
    manifest={'headline':'IT CAN DO WHAT?','user_selected_hook':True,'kind':'authentic partial-blur reveal','proof':proof,'logo':{'path':str(logo),'url':'https://openai.com/brand/','sha256':hashlib.sha256(logo.read_bytes()).hexdigest()},'blur':'Editorial blur on a real OpenAI launch output; never represented as unmodified source','generated_backplate':False,'new_image_api_calls':0,'no_performance_guarantee':True,'review_status':'pending','dimensions':[1920,1080]}
    manifest.update(represented_companies=['openai'],resolved_brand_assets=[{'key':'openai','asset_path':str(logo),'official_source_url':'https://openai.com/brand/','generated':False}],candidates=[{'path':str(OUT/'images25_it_can_do_what_v01.jpg'),'brand_placements':[{'key':'openai','bounds':[70,70,190,194]}]}])
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(path)

if __name__=='__main__':main()
