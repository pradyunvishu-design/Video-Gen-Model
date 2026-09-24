"""Centered, readable official Opus 5.5 evidence with DOM-derived annotations."""
from __future__ import annotations
import argparse, copy, hashlib, json, sys
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image,ImageDraw
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.capture import _load_page,_assert_capture_is_clean
from scripts.capture_qwen21_sources import FIND_TARGET,EXACT_RANGE,VISIBLE_TEXT
from scripts.acquire_opus55_sources import EP,URLS,dump

# Literal source phrases and chosen display zoom. No synthetic source headlines.
SPECS=[
 ('launch_intro','launch','We’re introducing Claude Opus 5.5','40% less',1.45),
 ('launch_migration_story','launch','One tester completed a 680,000-line','680,000-line',1.5),
 ('launch_load_times','launch','cut load times across every page','39 of 40',1.5),
 ('launch_cost_speed','launch','Cost and speed.','30% faster',1.5),
 ('launch_usage_limits','launch','five-hour usage limits','five-hour usage limits',1.6),
 ('launch_pricing','launch','Prices per 1M tokens','Cache reads',1.35),
 ('launch_fast_mode','launch','Fast mode for Opus 5.5','2.5x speed',1.6),
 ('launch_benchmark_table','launch','Agentic coding','Terminal-Bench 4.0',1.05),
 ('launch_benchmark_caveat','launch','benchmark margins have become','less reliable',1.55),
 ('launch_benchmark_safeguards','launch','production safeguards enabled','production safeguards enabled',1.4),
 ('launch_coding_audit','launch','Opus 5.5 is particularly good','200,000-line',1.5),
 ('launch_haproxy','launch','Both rewrites passed nearly','9.5 hours',1.6),
 ('launch_terminal_chart','launch','Terminal-Bench 4.0 Accuracy vs Cost','40% of the cost',1.0),
 ('launch_frontier_chart','launch','FrontierCode v1.1, main set Accuracy vs Cost','54.6%',1.0),
 ('launch_cursor_chart','launch','CursorBench 4.0 Accuracy vs Cost','52.5%',1.0),
 ('launch_security','launch','The most secure coding agent','screens every action',1.45),
 ('launch_reports','launch','Opus 5.5 is a reliable and adept researcher','16 out of 18',1.5),
 ('launch_merger','launch','two fictional HR software companies','63 minutes',1.5),
 ('launch_gdp_chart','launch','GDPval-AA v2.1 Elo vs Cost','44 occupations',1.0),
 ('launch_automation_chart','launch','AutomationBench Accuracy vs Cost','business workflows',1.0),
 ('launch_wandr_chart','launch','WANDR Accuracy vs Cost','large data collection tasks',1.0),
 ('launch_communication','launch','We’ve made major improvements to the way','puts the most important information up front',1.45),
 ('launch_bug_example','launch','The extra drop is a bug in the billing refactor','stops counting usage',1.5),
 ('launch_safeguards','launch','most cybersecurity tasks','Opus 4.8',1.5),
 ('launch_availability','launch','Opus 5.5 is available','Opus 5.5 is available',1.45),
 ('docs_context','docs','For long-running agentic coding and knowledge work','1M',1.15),
 ('docs_breaking_changes','docs','Four breaking changes','Four breaking changes',1.25),
 ('docs_pricing','docs','5m cache write','Cache read',1.35),
 ('docs_capabilities','docs','Reliable knowledge cutoff','medium',1.35),
 ('docs_thinking','docs','Adaptive thinking is always on','effort parameter',1.35),
 ('migration_thinking','migration',"Thinking can't be disabled",'always enabled',1.3),
 ('migration_forced_tools','migration','Forced tool use is not supported','Forced tool use',1.3),
 ('migration_progress','migration','Text between tool calls is returned in thinking blocks','thinking blocks',1.3),
 ('migration_fallback','migration','Safety classifiers and fallback','fallback',1.3),
 ('github_copilot','github','Claude Opus 5.5 is now available in GitHub Copilot','Claude Opus 5.5',1.35),
 ('analysis_intelligence','analysis','Claude Opus 5.5','Intelligence Index',1.2),
 ('cursor_overview','cursor','Claude Opus 5.5','Claude Opus 5.5',1.3),
 ('analysis_terminal','analysis','On Terminal-Bench 4.0 it scores 59.6%','59.6%',1.5),
 ('analysis_score','analysis','At max effort it scores 58','scores 58',1.5),
 ('analysis_effort','analysis','Level with Opus 5 on cost per task','1.6x',1.5),
 ('analysis_frontier','analysis','Four of five effort levels','Four of five effort levels',1.4),
 ('github_steps','github','using significantly fewer steps and tokens','fewer steps and tokens',1.5),
 ('github_access','github','Availability in GitHub Copilot','Pro+, Max, Business, and Enterprise',1.45),
 ('cursor_communication','cursor','Clearer communication than earlier Opus models','without over-elaborating',1.5),
 ('cursor_effort','cursor','We recommend the high thinking variant','high thinking variant',1.5),
 ('docs_cache','docs','Cache read','$0.20',1.5),
 ('docs_fast_mode','launch','It costs $8 per million input tokens','40 per million output tokens',1.65),
 ('github_recovery','github','It also quickly recovered from errors','recovered from errors',1.65),
 ('launch_report_threshold','launch','any invented figure or quote would have failed','invented figure or quote',1.65),
 ('launch_research_sources','launch','using only the information it could find','earnings release was hard to locate',1.65),
 ('launch_bug_check','launch','every event after','2026-08-31T00:00:00Z',1.5),
 ('migration_checklist','migration','Migration checklist by starting model','Every starting model',1.2),
 ('migration_computer','migration','The computer_20251124 computer use tool is not supported','computer_20251124',1.3),
 ('migration_context','migration','Thinking blocks are tied to the model and the conversation','model and the conversation',1.3),
]
CHARTS={'launch_terminal_chart':('Agentic terminal coding','Terminal-Bench 4.0'), 'launch_frontier_chart':('Agentic coding: FrontierCode','FrontierCode v1.1'), 'launch_cursor_chart':('Agentic coding: CursorBench','CursorBench 4.0'), 'launch_gdp_chart':('GDPval-AA v2.1','GDPval-AA v2.1'), 'launch_automation_chart':('AutomationBench','AutomationBench'), 'launch_wandr_chart':('WANDR','WANDR')}
# Generic targets for these IDs previously reached a newsletter, animated blank
# tail, and docs footer. Pin the actual visually approved source frames instead.
VERIFIED_REPAIRS={
 'analysis_intelligence':('analysis_score','690091525f082f086513bb4ff7a3a8079e0fbb82453c197a0a20a60534b44d15',(240,140,1440,810),'At max effort it scores 58','Centered article body excluding floating navigation; fixed 16:9 crop'),
 'docs_thinking':('docs_capabilities','9ce2b809671f01062bec6423b5cc5b1c1596734a6dc0fa2b13328c6d7ff24ccc',(1035,80,880,495),'Official default effort: medium','Inspected source capabilities panel showing Default effort and medium'),
 'launch_bug_check':('launch_bug_example','b9e280b8596998a373e2b3853aceb3244a020298a08ac86940535cdfcc1466ff',(900,510,960,540),'Published billing example: date interval and condition excluding the last day','Inspected published billing example: What changed, interval code, and excluded date'),
}

def repair_verified_sources(records,out,selected=None,*,write=True):
    """Prevalidate all sources, then replace only approved aliases.

    A recaptured source with different pixels requires visual review. DOM text
    alone cannot prove that an animated paragraph has actually finished drawing.
    write=False checks the frozen assets without modifying them.
    """
    by_id={r['id']:r for r in records};pending=[]
    for ident,(source,approved_hash,box,subject,measurement) in VERIFIED_REPAIRS.items():
        if selected is not None and ident not in selected:continue
        if source not in by_id:raise ValueError(f'{ident}: missing verified source {source}')
        row=copy.deepcopy(by_id[source]);payload=Path(row['path']).read_bytes()
        digest=hashlib.sha256(payload).hexdigest()
        if digest!=approved_hash:raise ValueError(f'{ident}: {source} changed; inspect its full frame and final crop before approval')
        with Image.open(row['path']) as im:
            if im.size!=(1920,1080):raise ValueError(f'{ident}: expected 1920x1080 source')
        x,y,w,h=box
        if x<0 or y<0 or x+w>1920 or y+h>1080 or w*9!=h*16:raise ValueError(f'{ident}: invalid source crop')
        row.update(id=ident,path=str(out/f'{ident}.png'),sha256=digest,source_capture_id=source,subject=subject)
        row['framing']=dict(x=x,y=y,width=w,height=h,units='pixels',measurement=measurement)
        if ident=='launch_bug_check':row['annotations']=[]
        if ident=='docs_thinking':
            for annotation in row.get('annotations',[]):annotation['narration_cue']='Default effort is medium'
        pending.append((ident,row,payload))
    repaired={ident:row for ident,row,_ in pending}
    if write:
        for ident,row,payload in pending:Path(row['path']).write_bytes(payload)
    result=[repaired.get(row['id'],row) for row in records]
    result.extend(row for ident,row,_ in pending if ident not in by_id)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only',default='')
    parser.add_argument('--repair-verified-only',action='store_true',help='Reuse three inspected frames without browsing or recapturing other assets')
    parser.add_argument('--check-repairs',action='store_true',help='Read-only validation of frozen repair inputs')
    args=parser.parse_args()
    out=EP/'captures';out.mkdir(parents=True,exist_ok=True)
    if args.repair_verified_only or args.check_repairs:
        existing=json.loads((out/'ledger.json').read_text(encoding='utf-8'))
        result=repair_verified_sources(existing,out,write=not args.check_repairs)
        if not args.check_repairs:dump(out/'ledger.json',result)
        print('Verified three reviewed source repairs; '+('no files changed' if args.check_repairs else 'only repaired IDs updated'))
        return
    records=[];failures=[]
    if args.only and (out/'ledger.json').exists():records=[r for r in json.loads((out/'ledger.json').read_text(encoding='utf-8')) if r['id'] not in args.only.split(',')]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        for source,url in URLS.items():
            specs=[s for s in SPECS if s[1]==source and s[0] not in VERIFIED_REPAIRS and (not args.only or s[0] in args.only.split(','))]
            if not specs:continue
            context=browser.new_context(viewport={'width':1920,'height':1080},device_scale_factor=1,color_scheme='light');page=context.new_page()
            try:
                _load_page(page,url)
                if source=='analysis':
                    # Remove floating site navigation only; preserve the article.
                    page.add_style_tag(content='header,nav{visibility:hidden!important;}')
                text=page.locator('body').inner_text();(EP/'research'/f'{source}.txt').write_text(text,encoding='utf-8')
                for ident,_,target,phrase,zoom in specs:
                    try:
                        page.evaluate('z=>{document.body.style.zoom=z;window.scrollTo(0,0)}',zoom)
                        if ident in CHARTS:
                            tab,title=CHARTS[ident]
                            page.get_by_role('tab',name=tab,exact=True).click()
                            chart=page.locator('figcaption').filter(has_text=title).filter(has_text='vs Cost').filter(visible=True).first
                            chart.evaluate("e=>{document.documentElement.style.scrollBehavior='auto';const r=e.getBoundingClientRect();window.scrollTo({top:window.scrollY+r.top-180,behavior:'instant'})}")
                        else:page.evaluate(FIND_TARGET,{'phrase':target,'position':260})
                        page.wait_for_timeout(600)
                        page.evaluate('async()=>{await document.fonts.ready;}')
                        if ident not in CHARTS:page.evaluate(FIND_TARGET,{'phrase':target,'position':260})
                        else:
                            chart.evaluate("e=>{const r=e.getBoundingClientRect();window.scrollTo({top:window.scrollY+r.top-180,behavior:'instant'})}")
                            assert chart.bounding_box()['height'] < 100, 'Wrong source chart caption'
                            print('CHART_RECT',ident,chart.bounding_box(),flush=True)
                        page.wait_for_timeout(150)
                        _assert_capture_is_clean(page,moment=ident)
                        visible=page.evaluate(VISIBLE_TEXT)
                        if ident not in CHARTS and target not in visible:raise ValueError('Source target not readable in viewport')
                        annotation=page.evaluate(EXACT_RANGE,phrase)
                        path=out/f'{ident}.png';page.screenshot(path=str(path),animations='disabled')
                        row={'id':ident,'path':str(path),'url':page.url,'source_url':page.url,'page_title':page.title(),'subject':target,'visible_text':visible,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'viewport':[1920,1080],'framing':{'x':0,'y':0,'width':1920,'height':1080,'units':'pixels','measurement':'Full 1080p public page with target centered vertically; locked framing'},'captured_at':datetime.now(timezone.utc).isoformat(),'capture_plan':{'target_phrase':target,'target_y':260,'browser_zoom':zoom},'rights_note':'Limited public first-party source-page quotation for direct explanatory news commentary; no general reuse or publication permission asserted.','annotations':[]}
                        if ident in CHARTS:row['framing']={'x':240,'y':90,'width':1440,'height':810,'units':'pixels','measurement':'Measured complete source chart and caption, fixed 16:9 crop'}
                        elif source=='analysis':row['framing']={'x':240,'y':140,'width':1440,'height':810,'units':'pixels','measurement':'Centered article body excluding floating navigation; fixed 16:9 crop'}
                        if annotation:row['annotations']=[{'measurement':'exact single-line browser DOM Range','phrase':phrase,'narration_cue':target,'region':annotation,'start':.8,'end':6}]
                        records.append(row);print('CAPTURED',ident,'underline',bool(annotation),flush=True)
                    except Exception as exc:failures.append({'id':ident,'error':str(exc)});print('FAILED',ident,str(exc),flush=True)
            except Exception as exc:failures.append({'source':source,'error':str(exc)})
            finally:context.close()
        browser.close()
    for row in records:
        if row['id'] in CHARTS:row['framing']={'x':240,'y':90,'width':1440,'height':810,'units':'pixels','measurement':'Measured complete source chart and caption, fixed 16:9 crop'}
    records=repair_verified_sources(records,out,set(args.only.split(',')) if args.only else None)
    dump(out/'ledger.json',records);dump(out/'failures.json',failures)
    canvas=Image.new('RGB',(1920,296*((len(records)+3)//4)),'#eeeeee');draw=ImageDraw.Draw(canvas)
    for i,row in enumerate(records):
        im=Image.open(row['path']);assert im.size==(1920,1080);im.thumbnail((480,270));x=i%4*480;y=i//4*296;canvas.paste(im,(x,y));draw.text((x+8,y+274),row['id'],fill='black')
    canvas.save(out/'contact_sheet.jpg',quality=92)
    print('Captured',len(records),'failures',len(failures),flush=True)
if __name__=='__main__':main()
