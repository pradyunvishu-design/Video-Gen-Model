"""Evidence-preserving review summary and delivery notes; never publishes."""
from pathlib import Path
from scripts.produce_astra_jobs_episode import EP, SOURCES
from scripts.produce_astra_episode import read, dump, sha


def audio_adjudication():
    raw = read(EP/'audio_qc.json')
    full = read(EP/'audio_listening_review.json')
    windows = read(EP/'voice_outlier_review.json')
    audio = Path(read(EP/'narration.json')['path'])
    digest = sha(audio)
    assert full['audio_sha256'] == windows['audio_sha256'] == digest
    assert windows['source_qc_sha256'] == sha(EP/'audio_qc.json')
    r = full['review']
    assert all(r[k] for k in ('same_speaker_throughout','intelligible_throughout','clean_signal'))
    assert r['distinct_speakers'] == 1 and not r['defects']
    reviewed = {windows['mapping'][item['label']]['chapter']:item for item in windows['review']['results']}
    flagged = []
    for chapter in raw['chapters']:
        if chapter['passed']:
            continue
        assert chapter['failures'] == ['narrator timbre changes too much between sections']
        m = chapter['metrics']
        assert m['voice_similarity'] >= .85 and m['voice_similarity_p10'] >= .55
        actual = reviewed[chapter['chapter']]
        assert actual['same_speaker'] and actual['clean_intelligible_audio'] and not actual['audible_defects']
        flagged.append({'chapter':chapter['chapter'],'raw_failures':chapter['failures'],
                        'adjudication':'No audible speaker change or defect in independent full-master and worst-window reviews; spectral flag retained as a non-blocking warning.'})
    dump(EP/'audio_qc_adjudicated.json', {
        'passed':True,'audio_sha256':digest,'source_qc_sha256':sha(EP/'audio_qc.json'),
        'full_master_review_sha256':sha(EP/'audio_listening_review.json'),
        'outlier_review_sha256':sha(EP/'voice_outlier_review.json'),
        'raw_qc_passed':raw['passed'],'warnings':flagged,'raw_qc_modified':False,
        'scope':'Automated ASR, waveform tests and independent audio-understanding review. Not a human listening certification.',
        'publishing_enabled':False})


def package():
    narration = read(EP/'narration.json')
    script = read(EP/'script.json')
    chapter_lines = []
    for audio, chapter in zip(narration['chapters'], script['chapters']):
        s = round(audio['start'])
        chapter_lines.append(f'{s//60:02}:{s%60:02} {chapter["title"]}')
    text = '\n'.join([
        '# Astra at Work — review package', '',
        '## Suggested title', '', 'Is Astra Coming for Our Jobs? Finance, Law & What Changes', '',
        '## Description', '',
        'Astra is moving beyond the chat window. OpenAI now has offerings for financial services and law—but what does that actually change about the work?', '',
        'We walk through the official demos, explain the benchmark numbers in plain English, and look at the tasks people might hand over versus the decisions they still need to check. There are also practical examples for financial models, legal research, software testing and everyday team workflows.', '',
        'This is an analysis of the announcements and company demonstrations, not an independent hands-on product test. Hypothetical examples are labeled. Benchmark gains are not evidence of job losses. Nothing here is financial or legal advice.', '',
        'Chapters', *chapter_lines, '', 'Primary sources', *[f'- {u}' for u in SOURCES.values()], '',
        'Production note: AI-generated narration and original explanatory graphics. Official demonstration footage is credited on screen. This channel project is developed in connection with Magic Hour; this episode is not sponsored or endorsed by OpenAI.', '',
        '## Review status', '',
        'Not uploaded or published. Public availability of source footage is not a verified reuse license. Review the media ledger and obtain any necessary permissions before publication.', '',
        'Final video: Astra_Jobs_Finance_Law_1080p.mp4',
        'Thumbnail: thumbnails/Astra_Our_Jobs_Next_1080p.jpg',
        'No burned-in subtitles. One approved Zubenelgenubi voice; source audio muted.',
        ''])
    (EP/'REVIEW_PACKAGE.md').write_text(text, encoding='utf-8')


def final_report():
    final = EP/'Astra_Jobs_Finance_Law_1080p.mp4'
    report_path = EP/'qa/final_visual_review.json'
    if not final.exists() or not report_path.exists():
        return
    technical = read(EP/'qa/delivery_verification.json')
    visual = read(report_path)
    digest = sha(final)
    assert technical['passed'] and visual['passed']
    assert technical['sha256'] == visual['video_sha256'] == digest
    assert read(EP/'script_review.json')['passed']
    dump(EP/'qa/episode_review_gate.json', {
        'status':'ready_for_private_human_review','passed':True,
        'video_sha256':digest,'duration_seconds':technical['duration_seconds'],
        'hard_delivery_defects':[],
        'review_layers':['Independent factual script check','Local ASR and waveform metrics',
                         'Independent full-master and flagged-window audio review',
                         'Final media decode, black-frame and repetition checks',
                         '94 exported-shot midpoints and11 full-resolution visual checks'],
        'anti_slop_repairs':['Matched chart baseline to exact narration beat',
                             'Reframed tiny financial UI details',
                             'Broke long diagram sequence with relevant official excerpts',
                             'Matched closing software footage to spoken software example',
                             'Rebuilt stale graphic reveal timing and tested actual short exports'],
        'remaining_soft_limits':visual['remaining_soft_limits'],
        'raw_audio_flags_preserved':True,
        'rights_status':'Public reuse permissions unverified; source ledger retained. Publication review required.',
        'publishing_enabled':False,
        'limitations':'Sampled visual and automated full-audio review, not a continuous human watch-through or a retention guarantee.'})


if __name__ == '__main__':
    audio_adjudication()
    package()
    final_report()
    print('Audio adjudication and review notes ready; no publishing action.')
