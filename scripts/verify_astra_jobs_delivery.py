"""Final-file checks; reports defects without silently repairing the edit."""
from collections import Counter
from pathlib import Path
import re
import subprocess
from scripts.produce_astra_jobs_episode import EP
from scripts.produce_astra_episode import read, dump, sha, probe


def main():
    video = EP/'Astra_Jobs_Finance_Law_1080p.mp4'
    rows = read(EP/'edit_plan.json')
    narration = read(EP/'narration.json')
    audio = read(EP/'audio_qc_adjudicated.json')
    info = probe(video)
    streams = info['streams']
    v = next(s for s in streams if s['codec_type']=='video')
    count = Counter(r['asset_id'] for r in rows)
    filters = subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(video),
        '-an','-vf','blackdetect=d=0.35:pix_th=0.07','-f','null','-'],capture_output=True,text=True,timeout=1200)
    assert filters.returncode == 0, filters.stderr[-1500:]
    black = [{'start':float(a),'end':float(b),'duration':float(c)} for a,b,c in re.findall(
        r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)',filters.stderr)]
    checks = {
        '1080p_h264_30fps':v['width']==1920 and v['height']==1080 and v['codec_name']=='h264' and v['r_frame_rate']=='30/1',
        'about_15_minutes':895 <= float(info['format']['duration']) <= 905,
        'one_audio_track':sum(s['codec_type']=='audio' for s in streams)==1,
        'no_subtitle_track':not any(s['codec_type']=='subtitle' for s in streams),
        'complete_narration':float(info['format']['duration'])>=narration['duration'],
        'audio_review_matches_master':audio['passed'] and audio['audio_sha256']==sha(Path(narration['path'])),
        'raw_audio_review_retained':audio['source_qc_sha256']==sha(EP/'audio_qc.json'),
        'provenance_complete':all(r.get('source_url') and r.get('relevance') for r in rows),
        'broll_at_most_twice':all(count[r['asset_id']]<=2 for r in rows if r['kind']=='video'),
        'each_motion_once':all(count[r['asset_id']]<=1 for r in rows if r['kind']=='motion'),
        'no_long_black_sections':not black,
        'full_video_decode':True,
    }
    totals = Counter()
    for r in rows:totals[r['kind']]+=r['frames']/30
    dump(EP/'qa/delivery_verification.json',{
        'passed':all(checks.values()),'checks':checks,'duration_seconds':float(info['format']['duration']),
        'sha256':sha(video),'shot_count':len(rows),'kind_duration_seconds':dict(totals),
        'black_sections':black,'publishing_enabled':False,
        'limits':'Automated checks do not establish a reuse license or guarantee watchability. Visual semantic review and source rights ledger remain separate.'})
    print(checks,flush=True)
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
