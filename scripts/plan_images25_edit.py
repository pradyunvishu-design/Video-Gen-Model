"""Frame-exact paragraph-led editorial plan; never loop or extend source clips."""
from pathlib import Path
import json, math, hashlib, subprocess
from collections import Counter
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
EP=ROOT/'data/episodes/episode_20260908_chatgpt_images25'
URL='https://openai.com/index/introducing-chatgpt-images-2-5/'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    assets={}
    for x in read(EP/'media/ledger.json'):
        assets[x['id']]={'asset_id':x['id'],'path':x['path'],'kind':'video','source_url':x['source_url'],'relevance':x['caption'],'available_frames':round(x['verified_duration']*30)}
    for x in read(EP/'captures/ledger.json'):
        assets['card_'+x['id']]={'asset_id':'card_'+x['id'],'path':x['path'],'kind':'article','source_url':x['source_url'],'relevance':x['visible_text'].split('\n')[0],'focus':x['normalized_region'],'framing':[0,0,1920,1080]}
    gallery=[]
    for x in read(EP/'media/gallery_proofs.json'):
        name=x['id'].replace('.png','').replace('.webp','')
        dest=EP/'cards/gallery_normalized'/f'{name}.png';dest.parent.mkdir(parents=True,exist_ok=True)
        raw=Image.open(x['path']).convert('RGB');raw.thumbnail((1880,1006),Image.Resampling.LANCZOS)
        im=Image.new('RGB',(1920,1080),'#f4f3ef');im.paste(raw,((1920-raw.width)//2,(1022-raw.height)//2))
        draw=ImageDraw.Draw(im);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
        draw.text((52,1025),'Source — OpenAI',font=font,fill='#41413c');im.save(dest)
        row={'asset_id':'picture_'+name,'path':str(dest),'kind':'picture','source_url':x['source_url'],'relevance':x['caption'],'framing':[0,0,1920,1080],'normalization':'Full original image fitted without crop; neutral matte and quiet source credit','source_hash':x['sha256'],'sha256':sha(dest)}
        assets[row['asset_id']]=row;gallery.append(row)
    dump(EP/'cards/gallery_normalized/ledger.json',gallery)
    for name in ['edit','continuity','latency','sketch','tradeoff','check']:
        assets['motion_'+name]={'asset_id':'motion_'+name,'path':str(EP/'motion'/f'{name}.mp4'),'kind':'motion','source_url':URL,'relevance':'Editorial explanatory diagram: '+name+'; not an independent model benchmark','available_frames':300}

    # None marks a still that absorbs the paragraph's remaining frames. Every
    # explicit source-video duration uses a real bounded excerpt, never a loop.
    plans={
      'opening_0':[('fullbody_cardigan',5),('picture_mid-century-modern-posters',5),('card_precision',None)],
      'opening_1':[('launch_x_tattoo_prompt',7),('fullbody_background',5),('picture_sci-fi-surrealism',None)],
      'opening_2':[('launch_x_tattoo_result',6),('picture_retrofuturism',None)],
      'precision_0':[('launch_x_tattoo_prompt',7),('card_precision',None)],
      'precision_1':[('picture_mid-century-modern-posters',6.033333333),('motion_edit',10),('picture_stickers',None)],
      'precision_2':[('ticket_cities',5.3),('travel_text',5.3),('picture_wedding-invitation',None)],
      'precision_3':[('picture_stickers',None),('templates_formats',6.5)],
      'consistency_0':[('card_multiturn',None),('cube_turn',2.7),('candles_candles',4.5),('fullbody_lighting',6)],
      'consistency_1':[('motion_continuity',10),('picture_wedding-invitation',None)],
      'consistency_2':[('templates_merch',7),('picture_vintage-national-park-stamps',None)],
      'consistency_3':[('fullbody_background',5),('fullbody_lighting',6),('card_multiturn',None)],
      # The ten-second chart crosses the paragraph boundary, matching both the
      # word 'chart' and the immediately following 100-to-50 explanation.
      'speed_0+speed_1':[('card_latency',10.233333333),('motion_latency',10),('card_latency',None)],
      'speed_2':[('templates_logo',7),('picture_impressionist-cityscape',None)],
      'speed_3':[('fullbody_cardigan',5),('card_flare',None)],
      'sketch_0':[('sketch_draw',6.5),('templates_formats',4.5),('card_sharing',None)],
      'sketch_1':[('card_sketch',None),('motion_sketch',10),('sketch_horse',7)],
      'sketch_2':[('sketch_fashion',8),('picture_retrofuturism',None)],
      'sketch_3':[('sketch_crab',7),('picture_presentation-image',None)],
      'models_0':[('card_flare',9.1),('card_sunburst',None)],
      'models_1':[('motion_tradeoff',10),('picture_cyberpunk',None)],
      'models_2':[('motion_check',10),('ticket_cities',5.3),('picture_vintage-national-park-stamps',None)],
      'conclusion_0':[('launch_x_candleholder',6.966666667),('sketch_fashion',6.966666667)],
      'conclusion_1':[('picture_presentation-image',6.9),('card_safety',None)],
      'conclusion_2':[('candles_candles',4.5),('sketch_crab',7),('picture_sci-fi-surrealism',None)],
      'conclusion_3':[('sketch_draw',6.5),('picture_impressionist-cityscape',None)],
    }
    timings=read(EP/'paragraph_timing.json');by_id={x['id']:x for x in timings}
    sequence=[];used=Counter();cursor=0;review=[]
    for key,beats in plans.items():
        ids=key.split('+');start=round(by_id[ids[0]]['start']*30);end=math.ceil(by_id[ids[-1]]['end']*30) if key=='conclusion_3' else round(by_id[ids[-1]]['end']*30)
        assert start==cursor,(key,start,cursor)
        count=end-start;frames=[None if duration is None else round(duration*30) for _,duration in beats]
        remainder=count-sum(n or 0 for n in frames)
        if None in frames:frames[frames.index(None)]=remainder
        elif remainder:
            # At most a frame of quantization enters a video shot if still below
            # its genuinely available frames; otherwise shortening prior cut.
            frames[-1]+=remainder
        current=[]
        for (asset,_),n in zip(beats,frames):
            a=assets[asset];assert 1<=n<=360,(key,asset,n)
            assert n<=a.get('available_frames',360),(asset,n,a.get('available_frames'))
            used[asset]+=1;assert used[asset]<=(1 if a['kind']=='motion' else 2),(asset,used[asset])
            assert not sequence or sequence[-1]['asset_id']!=asset,asset
            row={k:v for k,v in a.items() if k not in ['available_frames','sha256','source_hash','normalization']}
            row.update(id=f'{len(sequence)+1:03d}_{key.replace("+","_")}_{asset}',start_frame=cursor,frames=n,paragraph_ids=ids,narration=' '.join(by_id[i]['text'] for i in ids))
            row['relevance']=a['relevance']+' | '+semantic_reason(key,asset)
            sequence.append(row);current.append({'asset':asset,'seconds':n/30});cursor+=n
        review.append({'paragraphs':ids,'start':start/30,'end':end/30,'shots':current})
    assert cursor==math.ceil(timings[-1]['end']*30)
    chart=next(r for r in sequence if r['asset_id']=='motion_latency')
    assert 196<=chart['start_frame']/30<=198 and chart['frames']==300
    dump(EP/'edit_plan.json',sequence)
    durations=Counter()
    for row in sequence:durations[row['kind']]+=row['frames']/30
    missing=[x['path'] for x in sequence if not Path(x['path']).exists()]
    dump(EP/'cards/gallery_normalized/edit_plan_semantic_review.json',{'status':'ready' if not missing else 'awaiting_named_motion_assets','shots':len(sequence),'duration':cursor/30,'kind_seconds':dict(durations),'uses':dict(used),'chart_start':chart['start_frame']/30,'chart_end':(chart['start_frame']+chart['frames'])/30,'paragraph_review':review,'missing_assets':missing,'decisions':['Thumbnail surreal city fully revealed in opening launch examples','No hair/salon/dinner footage under product-layout narration','All source excerpts limited to two appearances, motion once, no adjacent asset duplication','No source clip extended past verified duration; paragraph remainders assigned to source summaries or specific output examples','Gallery examples illustrate the launch output range; do not claim independently verified performance or model-to-model outcomes'],'publishing_enabled':False})
    print(json.dumps({'shots':len(sequence),'duration':cursor/30,'kind_seconds':dict(durations),'chart_start':chart['start_frame']/30,'missing_assets':missing},indent=2))

def semantic_reason(key,asset):
    if asset=='picture_sci-fi-surrealism' and key=='opening_1':return 'Reveal the actual upside-down-city launch output teased in the thumbnail.'
    if asset=='motion_edit':return 'Illustrative poster date correction during the Friday-to-Saturday instruction; not claimed as model test.'
    if asset=='motion_latency':return 'Normalized 100-to-50 chart appears when narration introduces and explains this comparison.'
    if asset=='picture_presentation-image':return 'Actual information-rich launch output provides something concrete to inspect for layout and factual accuracy, without endorsing its correctness.'
    if key.startswith('precision'):return 'Inspect stable typography/layout and focused revisions during change-versus-preserve guidance.'
    if key.startswith('consistency'):return 'Show iterative edits or inspect concrete fine-detail output while discussing preservation.'
    if key.startswith('speed'):return 'Discuss controlled iteration and the qualified launch speed claim, not a fabricated stopwatch result.'
    if key.startswith('sketch'):return 'Contrast rough spatial guidance, style treatment, and a finished launch example.'
    if key.startswith('models'):return 'Support workflow selection and separate output criteria; the displayed example is not assigned to an unverified model.'
    if key.startswith('conclusion'):return 'Return to concrete targeted creation examples and the limits of selected launch demonstrations.'
    return 'Source-led launch example aligned with the opening editing-control question.'

if __name__=='__main__':main()
