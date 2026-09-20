"""Diagnostic source/candidate comparison after an independent voice-change flag."""
import base64
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import requests
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.retime_fable_connected_delivery import EP, SOURCE_AUDIO, map_time, read, dump, run, sha
from scripts.analyze_reference_delivery_sampled import estimate_pitch


def inverse_time(t,plan):
    a,b=0.0,plan['source_seconds']
    for _ in range(50):
        m=(a+b)/2
        if map_time(m,plan)<t: a=m
        else: b=m
    return (a+b)/2


def main():
    plan=read(EP/'delivery_edit_plan.json')
    folder=EP/'audio/paired_diagnostic'; folder.mkdir(exist_ok=True)
    destination=folder/'review.json'
    if destination.exists(): print(destination.read_text()); return
    parts=[{'text':'Compare each paired audio excerpt on its own audible evidence. The two versions in each pair contain the same passage. Do not infer identity, gender or production method. For each pair report: whether A changes speaker/timbre within itself, whether B does, whether A and B sound like the same narrator at different speeds, whether either sounds pitch-shifted or distorted, and specific audible evidence. Return JSON with pairs [{pair, same_narrator_across_versions, A_internal_voice_change, B_internal_voice_change, distorted_version_or_none, evidence}], and conclusion. Do not transcribe the passages.'}]
    measurements=[]
    for i,t in enumerate((34.5,60,117,204,283,374,420)):
        new_a,new_b=t-4,t+5
        old_a,old_b=inverse_time(new_a,plan),inverse_time(new_b,plan)
        entries=[('source',SOURCE_AUDIO,old_a,old_b),('candidate',EP/'narration_zubenelgenubi.wav',new_a,new_b)]
        if i%2: entries.reverse()
        pitches={}; labels={}
        for label,(kind,source,start,end) in zip(('A','B'),entries):
            path=folder/f'{i+1}_{label}.mp3'
            run(['ffmpeg','-y','-v','error','-ss',str(start),'-i',str(source),'-t',str(end-start),'-c:a','libmp3lame','-b:a','192k',str(path)])
            raw=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True,check=True).stdout
            pitch=estimate_pitch(np.frombuffer(raw,dtype=np.float32))
            pitches[kind]=float(np.median(pitch)) if pitch else None
            labels[label]=kind
            parts.extend([{'text':f'Pair {i+1}, version {label}'},{'inlineData':{'mimeType':'audio/mp3','data':base64.b64encode(path.read_bytes()).decode()}}])
        measurements.append({'pair':i+1,'candidate_time':t,'labels':labels,'median_pitch_hz':pitches,
                             'pitch_delta_semitones':12*math.log2(pitches['candidate']/pitches['source']) if all(pitches.values()) else None})
    dump(folder/'measurement_and_blinding_key.json',{'pairs':measurements,'candidate_sha256':sha(EP/'narration_zubenelgenubi.wav')})
    env=dotenv_values(r'C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker')
    response=requests.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent',
        headers={'x-goog-api-key':env['GEMINI_API_KEY']},json={'contents':[{'role':'user','parts':parts}],
        'generationConfig':{'responseMimeType':'application/json','temperature':.1,'maxOutputTokens':6000}},timeout=240)
    if not response.ok: raise RuntimeError(f'Paired diagnostic HTTP {response.status_code}; no automatic retry')
    payload=response.json(); result=json.loads(''.join(x.get('text','') for x in payload['candidates'][0]['content']['parts']))
    dump(destination,{'method':'Paired source/candidate diagnostic of the actual flagged passages. Randomized A/B labels. Reviewer did not receive prior results or the blinding key.',
                      'review':result,'usage':payload.get('usageMetadata',{}),'reported_cost_usd':None})
    print(json.dumps({'review':result,'measurements':measurements},indent=2),flush=True)


if __name__=='__main__': main()
