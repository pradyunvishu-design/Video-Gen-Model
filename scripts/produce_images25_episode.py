"""Resume the Images 2.5 episode with the existing channel voice and QC tools."""
import argparse, hashlib, json, math
from pathlib import Path
from scripts import produce_astra_episode as shared
from scripts import produce_fable_mythos_episode as audio_tools
from pipeline.render_v2 import concat_audio, make_silence, duration

EP=Path(__file__).resolve().parents[1]/'data/episodes/episode_20260908_chatgpt_images25'
read,dump,sha,run,probe=shared.read,shared.dump,shared.sha,shared.run,shared.probe
DIRECTOR='''Read only the transcript below in the original Zubenelgenubi voice. One consistent young adult male technology host, ordinary clear American English, talking naturally to one curious friend. Aim for 153 to 160 words per minute. Connected conversational phrases, brief natural pauses where the thought changes. Understate the delivery. No presenter performance, forced bass, breathy endings, vocal fry, whispers, sing-song inflection, exaggerated punchlines, background voices, music or sound effects. Keep stable full resonance and finish every sentence. Pronounce ChatGPT as Chat G P T, API as A P I. No extra words. Transcript follows:\n'''

def narrate():
    shared.EP=EP;shared.DIRECTOR=DIRECTOR
    shared.narrate()
    source=read(EP/'narration.json')
    dump(EP/'narration_original.json',source)
    total=source['duration']
    # Preserve comfortable natural cadence; never pad with a repeated visual.
    target=min(465,max(430,total))
    factor=(total-.18*(len(source['chapters'])-1))/(target-.18*(len(source['chapters'])-1))
    if not .90<=factor<=1.10:
        raise RuntimeError(f'Narration {total:.1f}s requires script/delivery revision, not extreme retiming')
    if abs(factor-1)<.002:
        return
    rows=[];paths=[];cursor=0
    pause=make_silence(EP/'audio/pause.wav',180)
    for c in source['chapters']:
        h=hashlib.sha256((sha(Path(c['path']))+f':atempo:{factor:.9f}').encode()).hexdigest()[:12]
        dest=EP/'audio'/f"{c['id']}_{h}_timed.wav"
        if not dest.exists():
            run(['ffmpeg','-y','-v','error','-i',c['path'],'-af',f'atempo={factor:.9f}','-ar','48000','-ac','1','-c:a','pcm_s16le',str(dest)])
        row={**c,'source_path':c['path'],'path':str(dest),'duration':duration(dest),'start':cursor,'hash':h,'tempo_factor':factor}
        rows.append(row);paths.append(dest);cursor+=row['duration']
        if len(rows)<len(source['chapters']):paths.append(pause);cursor+=.18
    master=concat_audio(paths,EP/'narration_zubenelgenubi_timed.wav')
    dump(EP/'narration.json',{**source,'chapters':rows,'path':str(master),'duration':duration(master),'timing_adjustment':factor})
    print('Narration runtime',duration(master),flush=True)

def audio_qc():
    audio_tools.EP=EP
    audio_tools.audio_review()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['narrate','audio_qc']);a=p.parse_args();globals()[a.stage]()
