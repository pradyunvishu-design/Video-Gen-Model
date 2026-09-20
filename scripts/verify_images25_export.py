"""Final publication-disabled artifact and source-integrity verification."""
import json,re,statistics,hashlib,subprocess
from collections import Counter
from pathlib import Path
from scripts.produce_images25_episode import EP,read,dump,sha,run,probe

def main():
    final=EP/'ChatGPT_Images_25_1080p.mp4';technical=read(EP/'edit/technical_qc.json');rows=read(EP/'edit_plan.json')
    if sha(final)!=technical['sha256']:raise RuntimeError('QC not bound to final artifact')
    scan=subprocess.run(['ffmpeg','-hide_banner','-i',str(final),'-an','-vf','scale=320:180,blackdetect=d=0.3:pix_th=0.02:pic_th=0.98','-f','null','-'],capture_output=True,text=True,encoding='utf-8',errors='replace',check=True,timeout=1200)
    noise=scan.stderr
    (EP/'qa/blackdetect.log').write_text(noise,encoding='utf-8')
    black=[{'start':float(a),'end':float(b),'duration':float(c)} for a,b,c in re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)',noise)]
    uses=Counter(r['asset_id'] for r in rows);durations=[r['frames']/30 for r in rows]
    audio=read(EP/'audio_qc.json');thumb=read(EP/'thumbnails/review.json')
    checks={'technical':all(technical['checks'].values()),'audio_qc':audio['passed'],'thumbnail_review':thumb['passed'],'no_unexplained_black_intervals':not black,'all_motion_once':all(n==1 for k,n in uses.items() if k.startswith('motion_')),'source_max_two':max(uses.values())<=2,'no_identical_adjacent_source':all(a['asset_id']!=b['asset_id'] for a,b in zip(rows,rows[1:])),'no_holds_over_12_seconds':max(durations)<=12,'contiguous_frames':all(a['start_frame']+a['frames']==b['start_frame'] for a,b in zip(rows,rows[1:])),'every_shot_source_linked':all(r['source_url'] and r['relevance'] for r in rows)}
    usage=[]
    for receipt in sorted((EP/'audio').glob('*_receipt.json')):
        c=read(receipt);usage.append({'stage':'narration','chapter':c['id'],'provider':'Gemini','usage':c.get('usage',{})})
    usage.append({'stage':'audio_outlier_review','provider':'Gemini','usage':read(EP/'voice_outlier_review.json').get('usage',{})})
    dump(EP/'provider_usage.json',{'openrouter_usd':0,'magichour_credits':0,'gemini_calls_recorded':len(usage),'gemini_billed_cost_usd':None,'billing_note':'Actual currency charges not returned; do not report unavailable billing as zero.','calls':usage,'thumbnail_method':'authentic source partial blur with exact brand and typography; no new generated image'})
    report={'passed':all(checks.values()),'checks':checks,'artifact':str(final),'sha256':sha(final),'runtime_seconds':technical['duration'],'shots':len(rows),'median_shot_seconds':statistics.median(durations),'black_intervals':black,'voice':'Zubenelgenubi','subtitles':False,'source_capture_limitation':'Clean live-browser screenshots unavailable; use explicitly sourced retypeset launch summaries and authentic official gallery/demos. Unstyled saved-page renders rejected.','audio_method':audio['method'],'voice_review_limitation':'Automated waveform/recognition checks plus independent audio-capable review of flagged samples; not a full human listening certificate.','publishing_enabled':False,'public_rights_review':'pending','visual_review':'pending'}
    dump(EP/'final_qc.json',report);print(json.dumps(report,indent=2))
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
