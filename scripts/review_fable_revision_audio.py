"""Independent audio-input review; retain waveform checks and cache by audio hash."""
from pathlib import Path
import base64
import hashlib
import json
import subprocess
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT/'data/episodes/episode_20260902_fable_mythos_v2'

def main():
    source = EP/'narration_zubenelgenubi.wav'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    target = EP/'audio'/f'independent_listening_{digest[:12]}.json'
    if target.exists():
        print(target.read_text(encoding='utf-8'))
        return
    compressed = EP/'audio'/f'listening_{digest[:12]}.mp3'
    if not compressed.exists():
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(source),'-c:a','libmp3lame','-b:a','128k',str(compressed)],check=True)
    prompt = '''Listen to the complete attached English narration as an independent audio quality reviewer. You have no information about its creator or production method. Evaluate what is actually audible, not whether the story is true. Check the whole recording, especially whether the speaker changes or develops a sustained muffled/gravelly tone, static/buzz, clipping, unintelligible words, truncated sentences, or unnatural theatrical delivery. Distinguish ordinary vowel/consonant variation and emphasis from a sustained speaker change. Do not infer a speaker's identity or exact age. Return JSON with: duration_reviewed_seconds (number), distinct_speakers (integer), same_speaker_throughout (boolean), intelligible_throughout (boolean), natural_delivery_1_to_5 (number), clean_signal (boolean), defects (array of objects with start_seconds, end_seconds, severity [minor, major], audible_evidence), tone_description (string), conclusion (string). Be critical and timestamp every actual audible problem. Do not produce a transcript.'''
    env = dotenv_values(r'C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\.env.worker')
    key = env.get('GEMINI_API_KEY')
    if not key: raise RuntimeError('Configured Gemini credential is missing')
    model = 'gemini-3.1-pro-preview'
    response = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',headers={'x-goog-api-key':key},json={'contents':[{'role':'user','parts':[{'text':prompt},{'inlineData':{'mimeType':'audio/mp3','data':base64.b64encode(compressed.read_bytes()).decode()}}]}],'generationConfig':{'responseMimeType':'application/json','temperature':0.15,'maxOutputTokens':6000}},timeout=240)
    if not response.ok: raise RuntimeError(f'Independent audio review HTTP {response.status_code}; no automatic retry')
    payload=response.json()
    raw=''.join(p.get('text','') for p in payload['candidates'][0]['content']['parts'])
    result={'audio_sha256':digest,'model':model,'method':'Full audio supplied to a separate audio-understanding model without generation prompt, script or earlier scores. Automated review, not human listening.','review':json.loads(raw),'usage':payload.get('usageMetadata',{}),'reported_cost_usd':None}
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__': main()
