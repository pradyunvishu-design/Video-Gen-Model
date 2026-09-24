"""Render eight original, silent, source-cited Opus 5.5 explanatory inserts."""
from __future__ import annotations
import argparse,hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/episodes/episode_20260923_opus55/motion'
KINDS=['cost_layers','token_price','cache_price','benchmark_axes','verification_loop','effort_tradeoff','migration','decision']
DESIGNS={
 'cost_layers':{'message':'Token rates and tokens consumed jointly affect the bill.','proof':'Anthropic typical-workload cost statement.','concepts':['Unquantified multiplication relationship','Pie-chart attribution of savings','A single giant 40% label'],'selected':0,'reason':'Shows the two levers without inventing a quantified split.'},
 'token_price':{'message':'Both posted input and output token rates decrease by 20%.','proof':'Published USD-per-million rates for both generations.','concepts':['Two normalized paired bars','A decorative price tag','A dense complete price table'],'selected':0,'reason':'Pairwise geometry exposes the reduction; normalization is explicitly labeled.'},
 'cache_price':{'message':'Cache-read rate decreases from 50 cents to 20 cents.','proof':'Published cache read rate.','concepts':['A two-value change with one directional connector','Coin animation','Dollar-sign background'],'selected':0,'reason':'Makes the actual rate change legible without decorative money metaphors.'},
 'benchmark_axes':{'message':'Look for stronger performance at lower cost.','proof':'Narrated explanation of the launch cost-versus-score chart axes.','concepts':['Explicitly illustrative chart axes','Copied scatterplot layout','Unverified synthesized score points'],'selected':0,'reason':'Teaches reading direction while refusing invented measurements.'},
 'verification_loop':{'message':'Agent outputs still need tests and human judgment.','proof':'Editorial application of the launch agent workflow.','concepts':['Task-tool-check-review with retry connector','Four unrelated cards','Futuristic agent avatar'],'selected':0,'reason':'A retry path explains the role of verification.'},
 'effort_tradeoff':{'message':'Start at medium effort and increase for demanding tasks.','proof':'Migration guidance for default medium effort.','concepts':['Qualitative effort range','Unmeasured latency bars','Animated robot thinking'],'selected':0,'reason':'Shows the decision without making unsupported performance promises.'},
 'migration':{'message':'Changing a production model deserves workflow tests.','proof':'Current migration guide and supported options.','concepts':['Sequential change checklist','Fake terminal configuration','Cloud architecture illustration'],'selected':0,'reason':'Direct practical checks, no invented API output.'},
 'decision':{'message':'Evaluate the new model on one real repeated task.','proof':'Editorial recommendation; no claimed test results.','concepts':['One task branching into three measurements','Victory podium','Brand logo showdown'],'selected':0,'reason':'Connects the viewer action to concrete measurements.'}
}
ENTRY=ROOT/'remotion/src/opus55-entry.tsx'
CHROME=Path('C:/Program Files/Google/Chrome/Application/chrome.exe')

def dump(path,obj):path.write_text(json.dumps(obj,indent=2),encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(args,log):
    p=subprocess.run([str(x) for x in args],cwd=ROOT/'remotion',capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1200)
    log.write_text(p.stdout+p.stderr,encoding='utf-8')
    if p.returncode:raise RuntimeError((p.stdout+p.stderr)[-1800:])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['preview','render','qc']);parser.add_argument('--kind',choices=KINDS);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    empty_public=OUT/'empty_public';empty_public.mkdir(exist_ok=True)
    dump(OUT/'scene_designs.json',DESIGNS)
    dump(OUT/'design_contract.json',{'dimensions':[1920,1080],'fps':30,'seconds':12,'camera':'locked','palette':{'paper':'#F2F0E9','ink':'#17221F','clay':'#B56F55','sage':'#809689'},'concepts_compared':['Decorative model-centered cover: rejected, no explanatory relationship','Full comparison-card grid: rejected, repetitive and harder to read','Original diagrams with one narrated relationship each: selected, preserves evidence and visual variety'],'selected':'relationship-specific editorial diagrams','font':'Inter Variable','maximum_focal_groups':3,'minimum_body_px':28,'sources':['https://www.anthropic.com/claude-opus-5-5'],'originality':'Original layouts and SVG primitives; no source graphic traced. No official logo available at authoring, so no invented mark.','limitations':['Benchmark chart teaches axes with no fabricated scores.','Effort guide is qualitative; no implied speed measurement.','Migration is a checklist, not an asserted API compatibility guarantee.'],'motion_intents':['enter','connect','emphasize'],'kinds':KINDS})
    for kind in ([args.kind] if args.kind else KINDS):
        props=OUT/f'{kind}.props.json';dump(props,{'kind':kind})
        common=[ROOT/'remotion/node_modules/.bin/remotion.cmd','src/opus55-entry.tsx','Opus55Graphic']
        if args.stage=='qc':
            dest=OUT/f'{kind}.mp4'
            subprocess.run(['ffmpeg','-v','error','-i',str(dest),'-f','null','-'],check=True,capture_output=True)
            for frame in [0,126,252,359]:
                subprocess.run(['ffmpeg','-y','-v','error','-i',str(dest),'-vf',f'select=eq(n\\,{frame})','-frames:v','1',str(OUT/f'{kind}_render_{frame:03}.png')],check=True,capture_output=True)
            subprocess.run(['ffmpeg','-y','-v','error','-i',str(dest),'-vf','select=eq(n\\,0)+eq(n\\,126)+eq(n\\,252)+eq(n\\,359),scale=960:540,tile=2x2','-frames:v','1',str(OUT/f'{kind}_contact.png')],check=True,capture_output=True)
            dump(OUT/f'{kind}.decode_qc.json',{'file_hash':sha(dest),'full_decode_passed':True,'sample_frames':[0,126,252,359],'sample_hashes':[sha(OUT/f'{kind}_render_{i:03}.png') for i in [0,126,252,359]],'visual_review':'pending separate human/model inspection'})
            continue
        if args.stage=='preview':
            for frame in [0,126,252,359]:
                run([common[0],'still',*common[1:],OUT/f'{kind}_{frame:03}.png',f'--frame={frame}',f'--props={props}',f'--browser-executable={CHROME}',f'--public-dir={empty_public}'],OUT/f'{kind}_still.log')
        else:
            dest=OUT/f'{kind}.mp4';receipt=OUT/f'{kind}.receipt.json';sig=hashlib.sha256((sha(ENTRY)+sha(props)).encode()).hexdigest()
            if dest.exists() and receipt.exists():
                old=json.loads(receipt.read_text());
                if old.get('input_hash')==sig and old.get('output_hash')==sha(dest):continue
            run([common[0],'render',*common[1:],dest,f'--props={props}',f'--browser-executable={CHROME}',f'--public-dir={empty_public}','--concurrency=2','--codec=h264','--crf=18','--pixel-format=yuv420p','--muted'],OUT/f'{kind}_render.log')
            probe=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(dest)],capture_output=True,text=True,check=True)
            info=json.loads(probe.stdout);video=[v for v in info['streams'] if v['codec_type']=='video'];assert len(video)==1 and video[0]['width']==1920 and video[0]['height']==1080
            assert not any(v['codec_type']=='audio' for v in info['streams'])
            assert abs(float(info['format']['duration'])-12)<.05
            for frame in [0,126,252,359]:
                subprocess.run(['ffmpeg','-y','-v','error','-i',str(dest),'-vf',f'select=eq(n\\,{frame})','-frames:v','1',str(OUT/f'{kind}_render_{frame:03}.png')],check=True,capture_output=True)
            dump(receipt,{'input_hash':sig,'output_hash':sha(dest),'file':str(dest),'duration':info['format']['duration'],'width':1920,'height':1080,'fps':video[0]['r_frame_rate'],'codec':video[0]['codec_name'],'audio':False,'passed':True})
            print(dest,flush=True)
if __name__=='__main__':main()
