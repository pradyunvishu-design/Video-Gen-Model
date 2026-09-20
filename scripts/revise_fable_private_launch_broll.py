"""A scoped, unpublished review edit requested by the user, not a rights approval.

Does not modify the licensed-ingestion gate or any existing episode. Only four
video segments change; the previous episode's AAC narration is copied verbatim.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.render_v2 import write_concat

PARENT = ROOT / 'data/episodes/episode_20260902_fable_mythos_v3'
EP = ROOT / 'data/episodes/episode_20260902_fable_mythos_v4_private'
SOURCE = EP / 'broll/anthropic_launch.mp4'
URL = 'https://www.youtube.com/watch?v=ROF2Nv_KjOM'
FINAL = EP / 'Claude_Fable_51_and_Mythos_Private_Review_1080p.mp4'
PARENT_VIDEO = PARENT / 'Claude_Fable_51_and_Mythos_1080p.mp4'
# Timecodes are taken from inspected original footage, not invented demonstrations.
EDITS = {
    's000': (0.75, 'Official launch introduction while introducing Fable and Mythos.'),
    's007': (33.10, 'Publisher illustration of evaluating interconnected tasks; introduce examination of published evidence.'),
    's009': (13.65, 'Branching task illustration during explanation of model capability and surrounding systems.'),
    's049': (51.25, 'Research-document workflow animation while explaining an agent combining scientific ingredients.'),
}


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def dump(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def sha(p):
    with p.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result.stdout


def probe(p):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(p)]))


def assemble():
    source_info = probe(SOURCE)
    source_video = next(s for s in source_info['streams'] if s['codec_type'] == 'video')
    assert (source_video['width'], source_video['height']) == (1920, 1080)
    original_rows = read(PARENT / 'storyboard.json')
    rows = json.loads(json.dumps(original_rows))
    source_hash = sha(SOURCE)
    rights = {
        'source_url': URL, 'source_title': 'Introducing Claude Fable 5.1',
        'publisher': 'Anthropic', 'source_sha256': source_hash,
        'youtube_license': 'standard YouTube license',
        'basis': 'user_requested_private_review',
        'permission_to_publish': False, 'reuse_license_verified': False,
        'user_instruction': 'I aint gonna upload it so for now use the clips',
        'scope': 'This specific private draft only; not a company-wide rights exception.',
        'publication_blockers': ['Obtain and record an appropriate public-reuse basis before publication.'],
        'source_audio_used': False,
    }
    dump(EP / 'broll/private_use_record.json', rights)
    for row in rows:
        if row['id'] not in EDITS:
            continue
        start, purpose = EDITS[row['id']]
        assert start + row['duration'] < float(source_info['format']['duration'])
        row.update({
            'asset_key': 'anthropic_launch_' + row['id'], 'kind': 'official_source_excerpt',
            'source': str(SOURCE), 'source_in': start, 'source_reference_in': start,
            'asset_source_id': 'anthropic_launch_video', 'asset_source_url': URL,
            'source_credit': 'Anthropic', 'rights_basis': rights['basis'],
            'rights_ledger': str(EP / 'broll/private_use_record.json'),
            'edit_note': purpose + ' Original audio muted, no added camera movement.',
        })
        row.pop('editorial_filter', None)
    dump(EP / 'storyboard.json', rows)
    for name in ('script.json', 'script_review.json', 'voice_selection.json', 'narration.json', 'audio_qc.json'):
        shutil.copy2(PARENT / name, EP / name)
    (EP / 'thumbnails').mkdir(exist_ok=True)
    shutil.copy2(PARENT / 'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg', EP / 'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg')

    def segment(row):
        if row['id'] not in EDITS:
            path = PARENT / 'timeline_segments/fable-v1' / (row['id'] + '.mp4')
            assert path.is_file()
            return path
        path = EP / 'timeline_segments' / (row['id'] + '.mp4')
        receipt = path.with_suffix('.json')
        digest = hashlib.sha256((json.dumps(row, sort_keys=True) + source_hash).encode()).hexdigest()
        if path.exists() and receipt.exists() and read(receipt).get('hash') == digest and read(receipt).get('output_sha256') == sha(path):
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        vf = "setsar=1,format=yuv420p,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='Anthropic':fontcolor=white:fontsize=23:box=1:boxcolor=black@0.70:boxborderw=9:x=w-tw-40:y=34"
        run(['ffmpeg', '-y', '-v', 'error', '-ss', str(row['source_in']), '-i', str(SOURCE),
             '-an', '-vf', vf, '-t', str(row['duration']), '-r', '30', '-c:v', 'libx264',
             '-preset', 'fast', '-crf', '17', '-threads', '2', '-pix_fmt', 'yuv420p',
             '-video_track_timescale', '15360', str(path)])
        dump(receipt, {'hash': digest, 'output_sha256': sha(path)})
        print('Rendered replacement', row['id'], flush=True)
        return path

    with ThreadPoolExecutor(max_workers=3) as pool:
        paths = list(pool.map(segment, rows))
    listing = write_concat(paths, EP / 'timeline_segments/concat.txt')
    duration = sum(row['duration'] for row in rows)
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing),
         '-i', str(PARENT_VIDEO), '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy',
         '-t', str(duration), '-movflags', '+faststart', str(FINAL)])
    dump(EP / 'revision_manifest.json', {
        'parent': str(PARENT_VIDEO), 'parent_sha256': sha(PARENT_VIDEO),
        'final': str(FINAL), 'publishing_enabled': False, 'public_reuse_cleared': False,
        'unchanged_segments': [{'id': r['id'], 'path': str(p), 'sha256': sha(p)} for r, p in zip(rows, paths) if r['id'] not in EDITS],
        'changed_segments': [r for r in rows if r['id'] in EDITS],
        'narration': 'Parent AAC stream copied without re-encoding or changing voice.',
        'new_paid_generation_calls': 0,
    })
    ledger = read(PARENT / 'source_ledger.json')
    ledger['private_launch_revision'] = rights | {'placements': [r for r in rows if r['id'] in EDITS]}
    dump(EP / 'source_ledger.json', ledger)
    (EP / 'REVIEW_PACKAGE.md').write_text(
        '# Private review only\n\nPublishing disabled. Public reuse is not cleared.\n\n'
        'Four short, source-credited Anthropic launch excerpts replace existing shots. '
        'The complete narration audio, script, other visuals, and thumbnail are unchanged. '
        'The publisher footage is illustrative and does not imply a new hands-on test.\n\n'
        f'Source: {URL}\n\nSee revision_manifest.json for exact source and timeline timecodes.\n', encoding='utf-8')
    print(str(FINAL), flush=True)


def verify():
    from PIL import Image, ImageDraw, ImageFont
    rows = read(EP / 'storyboard.json')
    manifest = read(EP / 'revision_manifest.json')
    info = probe(FINAL)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    def audio_hash(p):
        return run(['ffmpeg', '-v', 'error', '-i', str(p), '-map', '0:a:0', '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-']).strip()
    checks = {
        'exact_1080p_h264': (video['width'], video['height'], video['codec_name']) == (1920, 1080, 'h264'),
        'runtime_unchanged': abs(float(info['format']['duration']) - float(probe(PARENT_VIDEO)['format']['duration'])) < .05,
        'narration_aac_bytes_unchanged': audio_hash(FINAL) == audio_hash(PARENT_VIDEO),
        'script_unchanged': sha(PARENT / 'script.json') == sha(EP / 'script.json'),
        'thumbnail_unchanged': sha(PARENT / 'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg') == sha(EP / 'thumbnails/Claude_Fable_Mythos_Thumbnail.jpg'),
        'no_subtitle_streams': not any(s['codec_type'] == 'subtitle' for s in info['streams']),
        'all_unchanged_segments_intact': all(sha(Path(r['path'])) == r['sha256'] for r in manifest['unchanged_segments']),
        'parent_final_intact': sha(PARENT_VIDEO) == manifest['parent_sha256'],
        'only_four_shots_changed': len(manifest['changed_segments']) == 4,
        'publishing_disabled': manifest['publishing_enabled'] is False,
    }
    decode = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(FINAL), '-f', 'null', '-'], capture_output=True, text=True, timeout=600)
    checks['full_decode_clean'] = decode.returncode == 0 and not decode.stderr.strip()
    black = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(FINAL), '-vf', 'blackdetect=d=0.12:pix_th=0.04:pic_th=0.98', '-an', '-f', 'null', '-'], capture_output=True, text=True, timeout=600)
    events = [s.strip() for s in black.stderr.splitlines() if 'black_start:' in s]
    checks['no_blackouts'] = black.returncode == 0 and not events
    qc = EP / 'qc'
    qc.mkdir(exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
    sheet = Image.new('RGB', (1440, 4 * 304), '#eae8e2')
    draw = ImageDraw.Draw(sheet)
    for i, row in enumerate(r for r in rows if r['id'] in EDITS):
        for j, offset in enumerate((.1, row['duration'] / 2, row['duration'] - .1)):
            frame = qc / f'{row["id"]}_{j}.jpg'
            run(['ffmpeg', '-y', '-v', 'error', '-ss', str(row['start'] + offset), '-i', str(FINAL), '-frames:v', '1', str(frame)])
            with Image.open(frame) as img:
                sheet.paste(img.resize((480, 270)), (j * 480, i * 304))
            draw.text((j * 480 + 7, i * 304 + 274), f'{row["id"]} episode {row["start"]+offset:.2f}s', fill='#222222', font=font)
    sheet.save(qc / 'replacement_review.jpg', quality=95)
    result = {'technical_passed': all(checks.values()), 'checks': checks, 'duration': info['format']['duration'],
              'bytes': FINAL.stat().st_size, 'sha256': sha(FINAL), 'black_events': events,
              'public_release_ready': False, 'visual_review': 'pending contact-sheet inspection',
              'rights': 'Private review requested by user; not a verified public-use license.'}
    dump(qc / 'private_edit_qc.json', result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['assemble', 'verify'])
    globals()[parser.parse_args().stage]()
