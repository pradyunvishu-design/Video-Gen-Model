"""Artifact checks and a non-publishing review package for the Fable episode."""
from __future__ import annotations
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import statistics
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / 'data/episodes/episode_20260902_fable_mythos'


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def main():
    video = EP / 'Claude_Fable_51_and_Mythos_1080p.mp4'
    narration = json.loads((EP / 'narration.json').read_text())
    shots = json.loads((EP / 'storyboard.json').read_text())
    script = json.loads((EP / 'script.json').read_text(encoding='utf-8'))
    probe = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(video)]).stdout)
    visual = next(x for x in probe['streams'] if x['codec_type'] == 'video')
    audio = next(x for x in probe['streams'] if x['codec_type'] == 'audio')
    duration = float(probe['format']['duration'])
    decoded = run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'])
    black = run(['ffmpeg', '-hide_banner', '-i', str(video), '-an', '-vf', 'blackdetect=d=0.25:pix_th=0.05:pic_th=0.995', '-f', 'null', '-'])
    black_intervals = [dict(zip(('start', 'end', 'duration'), map(float, values))) for values in re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)', black.stderr)]
    repeats = collections.Counter(x['asset_key'] for x in shots)
    audio_qc = json.loads((EP / 'audio_qc.json').read_text())
    script_qc = json.loads((EP / 'script_review.json').read_text())
    checks = {
        'exact_1920x1080': (visual['width'], visual['height']) == (1920, 1080),
        'h264_yuv420p': visual['codec_name'] == 'h264' and visual['pix_fmt'] == 'yuv420p',
        'aac_audio': audio['codec_name'] == 'aac',
        'no_subtitle_stream': not any(x['codec_type'] == 'subtitle' for x in probe['streams']),
        'eight_to_twelve_minutes': 480 <= duration <= 720,
        'protected_narration_tail': duration >= narration['duration'] + .8,
        'no_decode_errors': not decoded.stderr.strip(),
        'no_empty_black_intervals': not black_intervals,
        'no_visual_reused_more_than_twice': max(repeats.values()) <= 2,
        'motion_graphics_used_once': all(n <= 1 for name, n in repeats.items() if name.startswith('@')),
        'no_visual_held_over_twelve_seconds': max(x['duration'] for x in shots) <= 12,
        'continuous_timeline': all(abs(a['start'] + a['duration'] - b['start']) < .04 for a, b in zip(shots, shots[1:])),
        'audio_automated_qc': audio_qc['passed'],
        'current_script_independently_reviewed': script_qc['passed'] and script_qc['script_hash'] == hashlib.sha256((EP / 'script.json').read_bytes()).hexdigest(),
        'all_assets_have_source_urls': all(x.get('asset_source_url', '').startswith('https://') for x in shots),
    }
    youtube_shots = [s for s in shots if s.get('rights_ledger')]
    if youtube_shots:
        clip_repeats = collections.Counter(s['source'] for s in youtube_shots)
        checks['youtube_excerpts_used_at_most_twice'] = max(clip_repeats.values()) <= 2
        checks['youtube_licenses_and_bytes_verified'] = all(
            (lambda ledger, shot: ledger['rights']['basis'] == 'creative_commons'
             and ledger['quality']['status'] == 'accepted'
             and ledger['output_sha256'] == hashlib.sha256(Path(shot['source']).read_bytes()).hexdigest()
             and shot['source_in'] + shot['duration'] <= ledger['end_seconds'] - ledger['start_seconds'] + .04)
            (json.loads(Path(s['rights_ledger']).read_text(encoding='utf-8')), s)
            for s in youtube_shots
        )
    qcdir = EP / 'qc'
    qcdir.mkdir(exist_ok=True)
    samples = sorted(set([.05, 2, 8, duration - 1] + [x['start'] + min(3.5, x['duration'] / 2) for x in shots if x['kind'] == 'motion_graphic'] + [x['start'] + 9 for x in narration['chapters']]))
    sheet = Image.new('RGB', (1280, ((len(samples)+2)//3)*264), '#f3f0e9')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    for i, second in enumerate(samples):
        path = qcdir / f'frame_{i:02d}.png'
        run(['ffmpeg', '-y', '-v', 'error', '-ss', str(second), '-i', str(video), '-frames:v', '1', str(path)])
        with Image.open(path) as frame:
            tile = ImageOps.contain(frame.convert('RGB'), (420, 236))
        x, y = (i % 3) * 426, (i // 3) * 264
        sheet.paste(tile, (x, y))
        draw.text((x+8, y+239), f'{int(second)//60:02}:{int(second)%60:02}', fill='#202820', font=font)
    sheet.save(qcdir / 'contact_sheet.jpg', quality=92)

    validator = Path('C:/Users/kanag/.codex/skills/generate-tech-news-thumbnails/scripts/validate_thumbnail.py')
    spec = importlib.util.spec_from_file_location('thumb_validator', validator)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    thumbs = [p for p in (EP/'thumbnails').glob('*.png') if not any(t in p.stem for t in ('_preview', '_grayscale','_master'))]
    brand = EP/'media/brand/Claude Spark - Clay.png'
    manifest = {'represented_companies':['anthropic'], 'resolved_brand_assets':[{'key':'anthropic','asset_path':str(brand),'official_source_url':'https://www.anthropic.com/press-kit','generated':False}], 'candidates':[{'path':str(p),'brand_placements':[{'key':'anthropic'}]} for p in thumbs]}
    save(EP/'thumbnails/brand_manifest.json', manifest)
    thumb_qc = []
    for path in thumbs:
        result = mod.validate(path, 2_000_000)
        result['brand'] = mod.validate_brand_manifest(path, EP/'thumbnails/brand_manifest.json', require_brand=True)
        result['passed'] = result['passed'] and all(result['brand']['checks'].values())
        thumb_qc.append(result)
    generated_thumb = EP/'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg'
    generated_result = mod.validate(generated_thumb, 2_000_000)
    generated_result['brand_note'] = 'Generated sculptural interpretation of the official reference, not an unmodified brand asset; no claim of official endorsement.'
    generated_result['manual_review'] = 'Text, metaphor, brand recognition and phone-size hierarchy checked visually.'
    thumb_qc.append(generated_result)
    save(EP/'thumbnails/qc.json', thumb_qc)
    checks['thumbnails_technical_qc'] = all(x['passed'] for x in thumb_qc)
    mix = {kind:round(sum(s['duration'] for s in shots if s['kind']==kind)/duration*100,2) for kind in {s['kind'] for s in shots}}
    report = {'render_checks_passed':all(checks.values()),'checks':checks,'duration_seconds':duration,'video_bytes':video.stat().st_size,'sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'shot_count':len(shots),'unique_asset_count':len(repeats),'median_shot_seconds':statistics.median(s['duration'] for s in shots),'visual_mix_percent':mix,'black_intervals':black_intervals,'contact_sheet':str(qcdir/'contact_sheet.jpg'),'publishing_enabled':False,'publication_ready':False,'remaining_gates':['Human editorial and voice listening approval','Final rights sign-off for limited article/figure excerpts'],'scope_notes':['Source-focused explainer rather than a hands-on test','Official NASA footage is historical context, not a new Claude-generated render','Standard-license Anthropic YouTube clips were not downloaded or included without clearance','Automated audio checks are not a human listening certification','No claim of 99% channel fidelity']}
    save(EP/'QC_REPORT.json',report)
    project_path = EP/'episode_project.json'
    project = json.loads(project_path.read_text(encoding='utf-8'))
    project['artifacts']['thumbnail'] = str(generated_thumb)
    project['artifacts']['qc_report'] = str(EP/'QC_REPORT.json')
    for shot, row in zip(project['shots'], shots):
        shot['source_in_seconds'] = row.get('source_reference_in', row['source_in'])
        shot['semantic_target'] = row['semantic_text']
    project['qc']['delivery'] = report
    save(project_path, project)
    timestamps = []
    for chapter, aud in zip(script['chapters'], narration['chapters']):
        second = int(aud['start'])
        timestamps.append(f'{second//60:02}:{second%60:02} {chapter["title"]}')
    sources = '\n'.join(f'- {url}' for url in dict.fromkeys(s['asset_source_url'] for s in shots))
    description = f"{script['title']}\n\nFable 5.1 and Mythos 5.1: what the release says about capabilities, safeguards, access, scientific examples, and pricing. We examine Anthropic's published evidence rather than claiming to reproduce its experiments.\n\n" + '\n'.join(timestamps) + '\n\nSources:\n' + sources + '\n\nCredits: NASA/Goddard Space Flight Center Scientific Visualization Studio; cloud data courtesy NASA/JPL-Caltech. Historical Magellan visualization, 2010. Claude identity assets: Anthropic media kit.\n\nDisclosure: Produced by a Magic Hour-affiliated channel using synthetic Gemini narration (Zubenelgenubi) and original explanatory graphics. This episode is not sponsored by Anthropic.\n'
    if any(s.get('asset_source_id') == 'youtube_duncan_fable' for s in shots):
        description += '\nYouTube excerpt attribution: "Claude Fable 5.1 + Claude Design = INSANE Instagram Carousels!" by Duncan Rogoff | Learn Claude Code, https://www.youtube.com/watch?v=-E2emAQOX1E . Licensed under the YouTube Creative Commons Attribution license, https://creativecommons.org/licenses/by/3.0/ . Changes: selected excerpts, muted original audio, normalized to 1080p, added source credit and original narration. Creator does not endorse this episode. Exact source timestamps and license metadata are retained in the episode rights ledger.\n'
    (EP/'upload_description.txt').write_text(description,encoding='utf-8')
    (EP/'script.md').write_text('# '+script['title']+'\n\n'+'\n\n'.join('## '+c['title']+'\n\n'+'\n\n'.join(c['paragraphs']) for c in script['chapters']),encoding='utf-8')
    (EP/'REVIEW_PACKAGE.md').write_text(f'# Fable / Mythos review package\n\nVideo: `{video.name}` ({duration/60:.2f} minutes), 1920x1080, one Zubenelgenubi narrator, no burned-in subtitles.\n\nRecommended thumbnail: `thumbnails/Claude_Fable_Mythos_Thumbnail.jpg`. Four alternate deterministic concepts are in the same folder. The recommended cover is a conceptual image generated with the built-in image tool; its prompt and reference are recorded in `thumbnails/generated_thumbnail_record.json`.\n\n`upload_description.txt` contains chapters, credits, sources, and synthetic-narration disclosure. `script.md`, `storyboard.json`, `source_ledger.json`, and `episode_project.json` retain the editorial and provenance records. `QC_REPORT.json` records automated checks and limitations.\n\nPublishing remains disabled. This is a completed review cut, not a rights-cleared publishing authorization. Confirm article/figure excerpt rights and listen to the full episode before posting.\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
