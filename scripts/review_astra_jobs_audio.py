"""Independent audio-input review of the final timed Astra jobs narration.

Never mutates narration or the main waveform/Whisper QC report. Calls are cached
by audio and prompt hashes; an uncertain request is never automatically retried.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import random
import subprocess
from pathlib import Path
import requests
from scripts import produce_astra_episode as shared

ROOT=Path(__file__).resolve().parents[1]
EP=ROOT/'data/episodes/episode_20260919_astra_jobs'
QA=EP/'qa'
MODEL='gemini-3.1-pro-preview'

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,o):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,ensure_ascii=False),encoding='utf-8')
def ffmpeg(args):
 r=subprocess.run(['ffmpeg','-y','-v','error']+[str(a) for a in args],capture_output=True,text=True,timeout=180)
 if r.returncode:raise RuntimeError(r.stderr[-1500:])
def audio_part(p):return {'inlineData':{'mimeType':'audio/mpeg','data':base64.b64encode(p.read_bytes()).decode('ascii')}}
def call_once(name,parts,signature,metadata):
 receipt=QA/f'audio-review_{name}_{signature[:16]}.json'
 journal=QA/f'audio-review_{name}_{signature[:16]}.request.json'
 if receipt.exists():return read(receipt)
 if journal.exists():raise RuntimeError('Prior request not safely completed; no automatic retry: '+str(journal))
 key=shared.env().get('GEMINI_API_KEY')
 if not key:raise RuntimeError('Configured Gemini credential missing')
 dump(journal,{'status':'submitted','input_hash':signature,'model':MODEL,**metadata})
 try:
  r=requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent',headers={'x-goog-api-key':key},json={'contents':[{'role':'user','parts':parts}],'generationConfig':{'responseMimeType':'application/json','temperature':.1,'maxOutputTokens':7000}},timeout=360)
  if not r.ok:
   dump(journal,{'status':'http_error','http_status':r.status_code,'input_hash':signature,'model':MODEL,**metadata})
   raise RuntimeError(f'Independent audio reviewer HTTP {r.status_code}; no automatic retry')
  response=r.json()
  raw=''.join(p.get('text','') for p in response['candidates'][0]['content']['parts'])
  result={'input_hash':signature,'model':MODEL,'review':json.loads(raw),'usage':response.get('usageMetadata',{}),'reported_cost_usd':None,**metadata}
  dump(receipt,result);dump(journal,{'status':'completed','receipt':str(receipt),'input_hash':signature,'model':MODEL})
  return result
 except requests.RequestException as e:
  dump(journal,{'status':'transport_uncertain','error_type':type(e).__name__,'input_hash':signature,'model':MODEL,**metadata})
  raise RuntimeError('Audio review transport uncertain; no automatic retry') from None

def full_review():
 narration=read(EP/'narration.json');source=Path(narration['path']);digest=sha(source)
 compressed=QA/f'audio-review_full_{digest[:16]}.mp3'
 if not compressed.exists():ffmpeg(['-i',source,'-vn','-ac','1','-ar','24000','-c:a','libmp3lame','-b:a','96k',compressed])
 prompt='''Listen critically to the entire attached English narration, from the first word to the last. You are an independent audio quality reviewer with no information about its creation. Judge only the audible recording, not factual truth. Check whether one consistent speaker is maintained, whether the sound develops sustained muffling or gravelly distortion, any static/buzz/background speech/clipping/unintelligible words, abrupt edits or cut-off sentence endings, distracting pauses, or delivery that becomes overly performed or monotonous. Normal differences in vowels, breaths and emphasis do not establish another speaker. Do not identify a person or estimate exact age; do not infer human versus synthetic origin. Timestamp every actual defect in seconds relative to the complete file, with concrete audible evidence. Return JSON with duration_reviewed_seconds (number), distinct_speakers (integer), same_speaker_throughout (boolean), intelligible_throughout (boolean), natural_delivery_1_to_5 (number), restrained_delivery_1_to_5 (number), clean_signal (boolean), defects (array of {start_seconds,end_seconds,severity:minor|major,audible_evidence}), tone_description (string), conclusion (string). Do not produce a transcript and do not invent issues if none are audible.'''
 sig=hashlib.sha256((digest+MODEL+prompt).encode()).hexdigest()
 result=call_once('full',[{'text':prompt},audio_part(compressed)],sig,{'audio_path':str(source),'audio_sha256':digest,'submitted_duration_seconds':narration['duration'],'method':'Complete final timed narration supplied to a fresh audio-understanding model. No script, generation prompt, production labels or earlier scores included. Automated listening review, not human listening.'})
 result['review_scope_validation']={'reported_duration_within_5_seconds':abs(float(result['review'].get('duration_reviewed_seconds',0))-narration['duration'])<=5,'audio_hash_still_matches':sha(source)==digest}
 dump(EP/'audio_listening_review.json',result)
 print(json.dumps(result,indent=2),flush=True)

def outliers():
 import numpy as np
 from pipeline.audio_qc import _decode,_spectrum_features
 qcpath=EP/'audio_qc.json'
 if not qcpath.exists():raise RuntimeError('Waveform/Whisper QC not completed yet; no review request sent')
 qc=read(qcpath);narration=read(EP/'narration.json');master=Path(narration['path']);digest=sha(master)
 flagged=[r for r in qc['chapters'] if not r['passed']]
 if not flagged:
  dump(EP/'voice_outlier_review.json',{'status':'not_needed','audio_sha256':digest,'source_qc_sha256':sha(qcpath),'reason':'No flagged chapters in completed automated QC','main_qc_modified':False});return
 reference=ROOT/'output/voice_canary/measured_original_tech_host_v4_round2/zubenelgenubi_connected_master.wav'
 ref=_decode(reference,24000);_,_,signature=_spectrum_features(ref,24000)
 candidates=[]
 for report in flagged:
  aud=next(c for c in narration['chapters'] if c['id']==report['chapter']);samples=_decode(Path(aud['path']),24000);scores=[]
  for t in range(0,max(1,int(aud['duration'])-2),2):
   chunk=samples[t*24000:(t+3)*24000]
   if np.sqrt(np.mean(chunk*chunk)+1e-12)<.004:continue
   _,_,sig=_spectrum_features(chunk,24000);scores.append((float(np.dot(signature,sig)),t))
  if not scores:raise RuntimeError('No speech windows found in flagged chapter')
  low,t=min(scores);start=max(0,t-4);global_start=aud['start']+start
  dest=QA/f'audio-review_outlier_{digest[:12]}_{aud["id"]}.mp3'
  ffmpeg(['-ss',global_start,'-i',master,'-t','15','-ac','1','-ar','24000','-b:a','96k',dest])
  candidates.append((dest,{'chapter':aud['id'],'global_start_seconds':global_start,'duration_seconds':15,'lowest_spectral_window_local_seconds':t,'lowest_spectral_similarity':low,'raw_flags':report['failures'],'clip_sha256':sha(dest)}))
 baseline=QA/f'audio-review_reference_{sha(reference)[:12]}.mp3'
 if not baseline.exists():ffmpeg(['-ss','5','-i',reference,'-t','15','-ac','1','-ar','24000','-b:a','96k',baseline])
 prompt='''Independently listen to the reference sample and every labeled candidate audio sample. Compare narrator consistency, sustained muffling, buzz/static, background speech, garbled words, clipped speech and conversational delivery. Do not assume any candidate is defective; ordinary vowel, breath, pitch and emphasis changes are normal. Do not identify the person or infer human/synthetic origin. Return JSON with results (one object per exact candidate label: label, same_speaker, clean_intelligible_audio, audible_defects array of {start_seconds,end_seconds,severity:minor|major,audible_evidence}, natural_delivery_1_to_5, audible_evidence), and conclusion. Times are relative to each candidate clip, not the full episode. Base judgments on sound, not topic. No transcript required.'''
 random.Random(918319).shuffle(candidates);mapping={};parts=[{'text':prompt},{'text':'Reference sample'},audio_part(baseline)]
 for i,(dest,data) in enumerate(candidates):
  label=f'Sample {i+1}';mapping[label]=data;parts.extend([{'text':label},audio_part(dest)])
 sig=hashlib.sha256((digest+sha(reference)+sha(qcpath)+prompt+MODEL+json.dumps(mapping,sort_keys=True)).encode()).hexdigest()
 result=call_once('outliers',parts,sig,{'audio_sha256':digest,'source_qc_sha256':sha(qcpath),'mapping':mapping,'method':'Actual lowest-spectral-similarity windows, with surrounding speech, extracted from final timed master. Reviewer receives only reference and anonymized audio, no flag labels, scores, script or generation instructions. Main QC is not modified.'})
 if isinstance(result['review'],list):
  raw_review=result['review']
  if not all(isinstance(v,dict) and ('label' in v or set(v)=={'conclusion'}) for v in raw_review):raise RuntimeError('Unexpected reviewer array shape; raw receipt retained')
  result={**result,'review':{'results':[v for v in raw_review if 'label' in v],'conclusion':' '.join(v['conclusion'] for v in raw_review if 'conclusion' in v)},'response_normalization':'Cached response was a JSON array of labeled results followed by conclusion. Rewrapped locally without changing content or making another request.'}
 labels=[v.get('label') for v in result['review'].get('results',[])]
 if len(labels)!=len(mapping) or set(labels)!=set(mapping):raise RuntimeError('Reviewer label set invalid; cached output retained, no retry')
 result['main_qc_modified']=False;dump(EP/'voice_outlier_review.json',result);print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['full','outliers']);args=parser.parse_args()
 QA.mkdir(parents=True,exist_ok=True)
 (full_review if args.action=='full' else outliers)()
