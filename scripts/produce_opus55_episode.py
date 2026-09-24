"""Ten-minute Opus 5.5 editorial pilot, using the established channel pipeline."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from scripts import produce_astra_episode as shared
from scripts import produce_qwen21_episode as base

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / 'data/episodes/episode_20260923_opus55'
PUBLIC_URLS = {
    'release': 'https://www.anthropic.com/claude-opus-5-5',
    'overview': 'https://platform.claude.com/docs/en/models/opus-5-5/overview',
    'whats_new': 'https://platform.claude.com/docs/en/models/opus-5-5/whats-new-opus-5-5',
    'migration': 'https://platform.claude.com/docs/en/models/opus-5-5/migration-guide',
    'product': 'https://www.anthropic.com/claude/opus',
    'github': 'https://github.blog/changelog/2026-09-22-claude-opus-5-5-is-now-available-in-github-copilot/',
    'cursor': 'https://prod.cursor.com/docs/models/claude-opus-5-5',
    'analysis': 'https://artificialanalysis.ai/articles/claude-opus-5-5',
}
DIRECTOR = '''Read only the transcript in the original Zubenelgenubi voice. One consistent young adult male, ordinary American English, calmly explaining useful technology to one curious friend. Aim for 172 to 178 words per minute. Connected phrases with brief natural pauses at changes of thought. Understated and lightly curious; not a salesman, trailer narrator, or performer. Complete every sentence with clear consonants. Keep the same timbre, volume and vocal placement throughout. No forced bass, whispering, breathy or muffled endings, exaggerated jokes, other voices, music or sound effects. Pronounce Claude Opus five point five naturally, GitHub as git hub, and A P I as individual letters. Transcript follows:\n'''


def configure():
    shared.EP = EP
    shared.DIRECTOR = DIRECTOR
    base.EP = EP
    base.DIRECTOR = DIRECTOR


def prepare():
    raw = (ROOT / 'research/episodes/opus55_script.md').read_text(encoding='utf-8')
    mapping = {
        '01_hook': ['release', 'overview'], '02_cost': ['overview', 'whats_new', 'product'],
        '03_coding': ['github'], '04_charts': ['analysis', 'release'],
        '05_work': ['release'], '06_communication': ['cursor'],
        '07_settings': ['overview', 'product', 'migration'],
        '08_migration': ['migration', 'whats_new'], '09_decision': ['release'],
    }
    chapters = []
    for block in raw.split('\n## ')[1:]:
        heading, body = block.split('\n', 1)
        ident, title = heading.split(' | ', 1)
        chapters.append({'id': ident, 'title': title, 'paragraphs': body.strip().split('\n\n'),
                         'sources': [PUBLIC_URLS[x] for x in mapping[ident]], 'evidence_ids': mapping[ident]})
    shared.dump(EP / 'script.json', {'title': 'Claude Opus 5.5: The Upgrade Hidden in the Bill',
        'chapters': chapters, 'word_count': len(re.findall(r'\S+', ' '.join(p for c in chapters for p in c['paragraphs']))),
        'target_duration_seconds': 600, 'publishing_enabled': False})
    shared.dump(EP / 'brief.json', {'topic': 'Claude Opus 5.5', 'format': 'source-led release explainer',
        'hook': 'Why 20% lower token prices can coexist with a 40% cheaper workload claim',
        'opening_candidates': ['price contradiction', 'benchmark trophy', 'migration surprise', 'workday before/after'],
        'selected_opening': 'price contradiction', 'proof_first': True,
        'voice': 'Zubenelgenubi', 'subtitles': False, 'width': 1920, 'height': 1080,
        'independent_model_test': False, 'rights_review_required': True, 'publishing_enabled': False})
    print('Spoken words:', shared.read(EP / 'script.json')['word_count'], flush=True)


def review():
    configure(); shared.review()


def narrate():
    configure(); base.narrate()


def fit_duration():
    """One uniform, pitch-preserving adjustment; never stretch an unsuitable script."""
    from pipeline.render_v2 import concat_audio, duration, make_silence
    configure()
    originals = [shared.read(EP / 'audio' / f'{c["id"]}_receipt.json')
                 for c in shared.read(EP / 'script.json')['chapters']]
    speech_target = 598.8 - .18 * (len(originals) - 1)
    total = sum(duration(Path(c['path'])) for c in originals)
    factor = total / speech_target
    if not .90 <= factor <= 1.12:
        raise RuntimeError(f'Natural narration requires script revision, not extreme retiming: {factor:.3f}')
    paths, chapters, cursor = [], [], 0.
    pause = make_silence(EP / 'audio/pause.wav', 180)
    for i, original in enumerate(originals):
        source = Path(original['path'])
        digest = hashlib.sha256(f'{shared.sha(source)}:{factor:.10f}'.encode()).hexdigest()[:12]
        dest = EP / 'audio' / f'{original["id"]}_{digest}_timed.wav'
        receipt = dest.with_suffix('.timing.json')
        valid = dest.exists() and receipt.exists() and shared.read(receipt).get('output_hash') == shared.sha(dest)
        if not valid:
            shared.run(['ffmpeg', '-y', '-v', 'error', '-i', str(source), '-af', f'atempo={factor:.10f}',
                        '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', str(dest)])
            shared.dump(receipt, {'input_hash': digest, 'output_hash': shared.sha(dest)})
        row = dict(original, path=str(dest), duration=duration(dest), start=cursor, hash=digest,
                   source_audio_hash=shared.sha(source), output_audio_hash=shared.sha(dest), tempo_factor=factor)
        chapters.append(row); paths.append(dest); cursor += row['duration']
        if i < len(originals)-1:
            paths.append(pause); cursor += .18
    master = concat_audio(paths, EP / 'narration_zubenelgenubi.wav')
    actual = duration(master)
    if abs(actual-598.8) > .25:
        raise RuntimeError(f'Unexpected tempo timing discrepancy: {actual:.3f}')
    shared.dump(EP / 'narration.json', {'chapters': chapters, 'path': str(master), 'duration': actual,
        'voice': 'Zubenelgenubi', 'model': 'gemini-3.1-flash-tts-preview', 'tempo_factor': factor})
    print('Narration:', round(actual, 3), 'seconds; uniform tempo:', round(factor, 4), flush=True)


def audio_qc():
    configure()
    narration=shared.read(EP/'narration.json')
    for row in narration['chapters']:
        if row['output_audio_hash'] != shared.sha(Path(row['path'])):
            raise RuntimeError('Timed audio bytes changed; rerun fit_duration: '+row['id'])
    base.audio_qc()
    seal_audio_review()


def seal_audio_review():
    """Bind the generated timing and recognition cache to exact reviewed bytes."""
    narration=shared.read(EP/'narration.json');qc=shared.read(EP/'audio_qc.json')
    if qc.get('audio_files') != audio_fingerprints():
        raise RuntimeError('Audio changed since its review')
    for row in narration['chapters']:
        if row['output_audio_hash'] != shared.sha(Path(row['path'])):
            raise RuntimeError('Retimed audio differs from its generation record')
    qc['paragraph_timing_hash']=shared.sha(EP/'paragraph_timing.json')
    shared.dump(EP/'audio_qc.json',qc)


def repair_audio():
    """Repair rejected sections without changing already aligned chapter timings."""
    from pipeline.render_v2 import concat_audio, duration, make_silence
    configure(); narration=shared.read(EP/'narration.json')
    for row in narration['chapters']:
        report=shared.read(EP/'audio'/f'{row["id"]}_qc.json')
        if report['passed']:continue
        receipt=shared.read(EP/'audio'/f'{row["id"]}_repair_ready.json')
        source=Path(receipt['path'])
        if row.get('repair_applied') == shared.sha(source):
            raise RuntimeError('This replacement was already applied and failed; generate another repair')
        target=row.get('repair_target_duration',row['duration']+({'08_migration':-3.,'09_decision':3.}.get(row['id'],0.)))
        factor=duration(source)/target
        if not .85<=factor<=1.15:raise RuntimeError('Repair pacing too different; revise before use')
        dest=source.with_name(source.stem+'_timed.wav')
        shared.run(['ffmpeg','-y','-v','error','-i',str(source),'-af',f'atempo={factor:.10f},apad',
                    '-t',str(target),'-ar','48000','-ac','1','-c:a','pcm_s16le',str(dest)])
        row.update(path=str(dest),duration=duration(dest),hash=shared.sha(dest)[:12],output_audio_hash=shared.sha(dest),
                   source_audio_hash=shared.sha(source),tempo_factor=factor,usage=receipt['usage'],
                   repair_applied=shared.sha(source),repair_target_duration=target)
        if abs(row['duration']-target)>.034:raise RuntimeError('Repair duration outside one frame tolerance')
    pause=make_silence(EP/'audio/pause.wav',180);paths=[]
    cursor=0.
    for i,row in enumerate(narration['chapters']):
        row['start']=cursor;cursor+=row['duration']
        paths.append(Path(row['path']))
        if i<len(narration['chapters'])-1:paths.append(pause);cursor+=.18
    master=concat_audio(paths,EP/'narration_zubenelgenubi.wav')
    narration['duration']=duration(master)
    if abs(narration['duration']-cursor)>.034:raise RuntimeError('Repaired master timing drift')
    shared.dump(EP/'narration.json',narration)


def prepare_repair():
    """Generate isolated replacements; never change the active narration in flight."""
    from pipeline.gemini_tts import GeminiTTSClient
    configure()
    narration={r['id']:r for r in shared.read(EP/'narration.json')['chapters']}
    for chapter in shared.read(EP/'script.json')['chapters']:
        report_path=EP/'audio'/f'{chapter["id"]}_qc.json'
        if not report_path.exists() or shared.read(report_path)['passed']:continue
        receipt_path=EP/'audio'/f'{chapter["id"]}_repair_ready.json'
        attempt=1
        if receipt_path.exists():
            previous=shared.read(receipt_path)
            if narration[chapter['id']].get('repair_applied') != previous['sha256']:continue
            attempt=previous.get('attempt',1)+1
            if attempt>2:raise RuntimeError('Two unsuccessful audio repair passes; human review required')
            shared.dump(receipt_path.with_name(receipt_path.stem+f'_attempt{attempt-1}.json'),previous)
        raw=EP/'audio'/f'{chapter["id"]}_repair{attempt}_raw.wav';dest=raw.with_name(raw.name.replace('_raw','_master'))
        director=DIRECTOR+f'\nConsistency take {attempt}: Steady neutral speaking register, natural conversational pitch. No change in vocal texture between clauses or paragraphs; finish with the same placement as the beginning.\n'
        result=GeminiTTSClient(shared.env().get('GEMINI_API_KEY'),model='gemini-3.1-flash-tts-preview',
            voice='Zubenelgenubi',timeout_seconds=240).synthesize('\n\n'.join(chapter['paragraphs']),raw,director_prompt=director,retries=2)
        shared.run(['ffmpeg','-y','-v','error','-i',str(raw),'-af','highpass=f=60,loudnorm=I=-17:TP=-1.5:LRA=6',
                    '-ar','48000','-ac','1','-c:a','pcm_s16le',str(dest)])
        shared.dump(receipt_path,{'path':str(dest),'sha256':shared.sha(dest),'usage':result.usage,'attempt':attempt})
        print('Replacement ready',chapter['id'],flush=True)


def audio_fingerprints():
    configure(); return base.audio_fingerprints()


def listening_review():
    from scripts import extend_astra_episode as audit
    audit.EP=EP;configure();(EP/'qa').mkdir(exist_ok=True)
    audit.listening_review()


def voice_outlier_review():
    from scripts import extend_astra_episode as audit
    audit.EP=EP;configure();(EP/'qa').mkdir(exist_ok=True)
    audit.voice_review()
    seal_audio_review()


def package():
    narration, script = shared.read(EP/'narration.json'), shared.read(EP/'script.json')
    chapters = [f'{int(a["start"])//60:02d}:{int(a["start"])%60:02d} {c["title"]}'
                for a, c in zip(narration['chapters'], script['chapters'])]
    description = ('Claude Opus 5.5 promises cheaper work. But a lower token price is only part of the story. '
        'We break down the release, coding reports, benchmark charts, and the settings worth checking before switching.\n\n'
        'This is analysis of published sources, not an independent hands-on benchmark. Prices and availability were checked September 23, 2026. '
        'Original synthetic narration; official launch excerpts are identified on screen.\n\n' + '\n'.join(chapters)
        + '\n\nSources\n' + '\n'.join(PUBLIC_URLS.values()))
    shared.dump(EP/'review_metadata.json', {'title': 'Claude Opus 5.5 Is Cheaper. Here’s What Actually Changed.',
        'description': description, 'chapters': chapters, 'channel': 'Diffusion Daily',
        'tags': ['Claude Opus 5.5', 'Anthropic', 'Claude Code', 'AI news', 'Claude pricing'],
        'publishing_enabled': False, 'rights_review_required': True, 'synthetic_narration': True})
    voice_receipts=sorted((EP/'audio').glob('*_receipt.json'))+sorted((EP/'audio').glob('*_repair_ready*.json'))
    spend=shared.read(EP/'provider_usage.json')
    shared.dump(EP/'production_usage.json',{'openrouter_usd':spend['openrouter_usd'],
        'openrouter_episode_cap_usd':spend['openrouter_cap_usd'],'magichour_credits':0,
        'gemini_tts':[{'receipt':p.name,'usage':shared.read(p).get('usage',{})} for p in voice_receipts],
        'gemini_audio_reviews':[{ 'receipt':name,'usage':shared.read(EP/name).get('usage',{})}
            for name in ['voice_outlier_review.json','audio_listening_review.json'] if (EP/name).exists()],
        'gemini_cost_usd':None,'cost_note':'Gemini usage recorded; provider did not return dollar charges.'})
    print('Local review package ready', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'review', 'narrate', 'fit_duration', 'audio_qc', 'seal_audio_review', 'prepare_repair', 'repair_audio', 'listening_review','voice_outlier_review','package'])
    globals()[parser.parse_args().stage]()
