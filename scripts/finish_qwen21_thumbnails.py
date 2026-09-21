"""Deterministic, private-review packaging; never calls an image provider."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT / 'data/episodes/episode_20260920_qwen_image21'
OUT = EP / 'thumbnails'
IVORY = '#f5f1e7'
INK = '#222521'
SAGE = '#adbaa2'
CLAY = '#bd7b60'
SIZE = (1920, 1080)
LOGO_PATH = EP / 'media/logo.png'
LOGO = Image.open(LOGO_PATH).convert('RGBA')
LOGO_BBOX = LOGO.getbbox()
LOGO = LOGO.crop(LOGO_BBOX)
FONT = 'C:/Windows/Fonts/impact.ttf'
BODY = 'C:/Windows/Fonts/arialbd.ttf'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text(im, value, xy, size, fill=INK, font=FONT):
    ImageDraw.Draw(im).text(xy, value, font=ImageFont.truetype(font, size), fill=fill, anchor='lt')


def brand(im, x, y, width):
    height = round(width * LOGO.height / LOGO.width)
    asset = LOGO.resize((width, height), Image.Resampling.LANCZOS)
    im.paste(asset, (x, y), asset)
    return [{'key': 'qwen', 'bounds': [x, y, width, height], 'asset_path': str(LOGO_PATH),
             'operation': 'trim transparent padding, uniform resize, alpha composite; original colors retained'}]


def proof(im, source, box, crop=None):
    asset = Image.open(EP / 'media' / source).convert('RGB')
    if crop:
        asset = asset.crop(crop)
    fitted = ImageOps.fit(asset, (box[2]-box[0], box[3]-box[1]), method=Image.Resampling.LANCZOS)
    im.paste(fitted, box[:2])


def save(im, name):
    path = OUT / f'qwen21_{name}_v01.png'
    staging = path.with_name(path.stem + '.rendering.png')
    im.save(staging, optimize=True)
    staging.replace(path)
    # Preserve the exact official logo raster layer without lossy palette reduction.
    im.resize((320, 180), Image.Resampling.LANCZOS).save(OUT / f'{path.stem}_320.png')
    ImageOps.grayscale(im).save(OUT / f'{path.stem}_gray.png', optimize=True)
    ImageOps.grayscale(im).resize((320, 180), Image.Resampling.LANCZOS).save(OUT / f'{path.stem}_gray_320.png')
    if path.stat().st_size > 2_000_000:
        # Retain the lossless master, with a high-quality upload-sized derivative.
        upload = path.with_suffix('.jpg')
        im.save(upload, quality=97, subsampling=0, optimize=True)
        return upload
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = json.loads((EP / 'media/ledger.json').read_text())
    used = [entry for entry in ledger if entry['id'] in {'logo', 'example-18', 'example-19', 'example-16'}]
    for asset in used:
        assert sha(asset['path']) == asset['sha256'], f"Source changed: {asset['id']}"
    candidates = []

    # Winner: retain supplied editorial concept, remove generated identity completely.
    im = Image.open(EP / 'thumbnail_concept.png').convert('RGB').resize(SIZE, Image.Resampling.LANCZOS)
    # Suppress subpixel resampling noise only; avoid palette banding in paper shadows.
    # The official brand is added afterward and is unaffected by this filtering.
    im = im.filter(ImageFilter.GaussianBlur(0.5))
    ImageDraw.Draw(im).rounded_rectangle((67, 160, 931, 321), radius=51, fill=IVORY)
    placements = brand(im, 100, 174, 795)
    p = save(im, 'cleanup_question')
    candidates.append({'path': str(p), 'headline': 'SKIP THE CLEANUP?', 'visual_sentence': 'A sticker peels from its rectangular background, making the cleanup question concrete.',
        'hook_mechanism': 'workflow consequence', 'style_mode': 'editorial_symbol', 'focal_subject': 'Illustrated sticker peeling from paper',
        'supporting_subjects': ['transparency checkerboard'], 'proof_asset_ids': [], 'evidence_ids': ['model_card', 'release'],
        'highlighted_word': None, 'brand_placements': placements,
        'generated_layer': {'path': str(EP / 'thumbnail_concept.png'), 'sha256': sha(EP / 'thumbnail_concept.png'),
            'role': 'supplied editorial illustration, NOT an unmodified Qwen output or official mascot',
            'modification': 'Illustration plate resampling noise softened at 0.5px; entire generated identity badge painted over; exact official logo composited afterward',
            'caveat': 'Question presents possible workflow benefit, not independently verified quality or performance.'},
        'scores': {'hook_fit': 5, 'evidence_fit': 4, 'identity_fit': 5, 'mobile_clarity': 5, 'originality': 4}})

    # Before/after: authentic annotated input and its corresponding official output.
    im = Image.new('RGB', SIZE, IVORY)
    d = ImageDraw.Draw(im)
    text(im, 'CHANGE', (65, 60), 132)
    d.rectangle((503, 47, 810, 205), fill=SAGE)
    text(im, 'ONLY', (525, 61), 132)
    text(im, 'THIS?', (845, 61), 132)
    placements = brand(im, 1180, 93, 675)
    for name, box in [('example-18.png', (115, 305, 845, 1014)), ('example-19.png', (1075, 305, 1805, 1014))]:
        proof(im, name, box)
    text(im, 'ANNOTATED INPUT', (115, 245), 34, font=BODY)
    text(im, 'OFFICIAL OUTPUT', (1075, 245), 34, font=BODY)
    d.line((885, 645, 1025, 645), fill=INK, width=14)
    d.polygon([(1025, 645), (985, 612), (985, 678)], fill=INK)
    p = save(im, 'edit_receipt')
    candidates.append({'path': str(p), 'headline': 'CHANGE ONLY THIS?', 'visual_sentence': 'The published annotated portrait directly faces its published edited result.',
        'hook_mechanism': 'authentic transformation', 'style_mode': 'source_before_after', 'focal_subject': 'Changed hair in official input/output pair',
        'supporting_subjects': ['original edit annotations'], 'proof_asset_ids': ['example-18', 'example-19'], 'evidence_ids': ['repository'],
        'highlighted_word': 'ONLY', 'brand_placements': placements,
        'scores': {'hook_fit': 5, 'evidence_fit': 5, 'identity_fit': 5, 'mobile_clarity': 4, 'originality': 4}})

    # A quoted license condition is the story, not a decorative browser screenshot.
    im = Image.new('RGB', SIZE, INK)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((65, 74, 860, 244), radius=30, fill=IVORY)
    placements = brand(im, 99, 96, 725)
    text(im, 'OPEN', (70, 348), 216, IVORY)
    text(im, 'HAS', (70, 571), 216, IVORY)
    d.rectangle((63, 790, 840, 1015), fill=CLAY)
    text(im, 'LIMITS', (91, 811), 216, INK)
    d.rectangle((964, 115, 1880, 986), fill='#10120f')
    d.rectangle((935, 86, 1851, 957), fill=IVORY)
    d.rectangle((935, 86, 1851, 106), fill=SAGE)
    text(im, 'RESEARCH LICENSE', (1002, 168), 51, font=BODY)
    text(im, 'SECTION 2(a)', (1002, 254), 30, font=BODY)
    d.line((1002, 323, 1780, 323), fill='#b8b9ae', width=3)
    quote = 'FOR NON-COMMERCIAL PURPOSES ONLY'
    assert quote in (EP / 'research/license.txt').read_text(encoding='utf-8')
    for idx, line in enumerate(['FOR', 'NON-COMMERCIAL', 'PURPOSES ONLY']):
        text(im, line, (1002, 395 + idx * 130), 84, INK)
    text(im, 'Exact excerpt from release terms', (1002, 835), 33, font=BODY)
    p = save(im, 'license_caveat')
    candidates.append({'path': str(p), 'headline': 'OPEN HAS LIMITS', 'visual_sentence': 'The promise of open access meets the actual non-commercial license condition.',
        'hook_mechanism': 'receipt collision', 'style_mode': 'bold_conflict', 'focal_subject': 'Exact license excerpt',
        'supporting_subjects': [], 'proof_asset_ids': ['license'], 'evidence_ids': ['license'], 'quote': quote,
        'highlighted_word': 'LIMITS', 'brand_placements': placements,
        'scores': {'hook_fit': 5, 'evidence_fit': 5, 'identity_fit': 5, 'mobile_clarity': 4, 'originality': 4}})

    # Mechanism handoff: preserve all five actual references and the published result.
    im = Image.new('RGB', SIZE, IVORY)
    d = ImageDraw.Draw(im)
    placements = brand(im, 65, 83, 670)
    text(im, 'MORE', (65, 310), 150)
    text(im, 'INPUTS.', (65, 470), 150)
    text(im, 'MORE', (65, 678), 130)
    d.rectangle((57, 821, 730, 994), fill=SAGE)
    text(im, 'CONTROL?', (77, 821), 136)
    source = Image.open(EP / 'media/example-16.png')
    # Published source is 1353x1453; all five input panels occupy its left 273px.
    assert source.size == (1353, 1453)
    refs = source.crop((0, 0, 273, 1453)).resize((177, 942), Image.Resampling.LANCZOS)
    im.paste(refs, (795, 80))
    proof(im, 'example-16.png', (1041, 80, 1860, 1022), crop=(273, 0, 1353, 1453))
    d.line((987, 547, 1027, 547), fill=INK, width=8)
    d.polygon([(1030, 547), (1012, 529), (1012, 565)], fill=INK)
    text(im, '5 REFERENCES', (791, 34), 24, font=BODY)
    text(im, 'PUBLISHED RESULT', (1041, 34), 24, font=BODY)
    p = save(im, 'reference_handoff')
    candidates.append({'path': str(p), 'headline': 'MORE INPUTS. MORE CONTROL?', 'visual_sentence': 'Five original reference panels feed one authentic published composite.',
        'hook_mechanism': 'mechanism handoff', 'style_mode': 'source_editorial_collage', 'focal_subject': 'Official outfit composition result',
        'supporting_subjects': ['five actual reference images'], 'proof_asset_ids': ['example-16'], 'evidence_ids': ['repository'],
        'highlighted_word': 'CONTROL', 'brand_placements': placements,
        'scores': {'hook_fit': 4, 'evidence_fit': 5, 'identity_fit': 5, 'mobile_clarity': 4, 'originality': 5}})

    hooks = ['SKIP THE CLEANUP?', 'CHANGE ONLY THIS?', 'OPEN HAS LIMITS', 'MORE INPUTS. MORE CONTROL?',
             'CHECK THE EDGES', 'BEYOND THE PRETTY PICTURE', 'KEEP THE REST?', 'READY FOR REAL WORK?']
    for candidate in candidates:
        candidate.update({'represented_companies': ['qwen'], 'safe_margins_px': 60,
            'palette': ['warm ivory', 'charcoal', 'muted sage', 'clay', 'official logo colors'],
            'forbidden_implications': ['Our own Qwen test', 'Guaranteed clean edges', 'Commercial clearance', 'Official endorsement'],
            'file_sha256': sha(candidate['path']), 'human_review_status': 'pending',
            'visual_review_status': 'pending full size, grayscale and mobile inspection'})
    manifest = {'schema': 'qwen-thumbnail-package.v1', 'canvas': [1920, 1080], 'publishing_enabled': False,
        'usage': 'Private research/evaluation only. Commercial publication not cleared.',
        'recommended': candidates[0]['path'], 'represented_companies': ['qwen'],
        'strongest_supported_promise': 'Potentially less cleanup after generation; published examples, not our own tests.',
        'unresolved_question': 'Do usable edges and controlled edits survive real workflows?',
        'hook_angles': [{'headline': h, 'specificity': 4 if i > 3 else 5, 'payoff': 5, 'selected': i < 4} for i, h in enumerate(hooks)],
        'resolved_brand_assets': [{'key': 'qwen', 'label': 'Qwen-Image-2.1', 'identity_kind': 'product logo',
            'asset_path': str(LOGO_PATH), 'official_source_url': used[0]['url'],
            'terms_url': 'https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE',
            'sha256': sha(LOGO_PATH), 'generated': False, 'original_mode': 'RGBA', 'trim_bbox': list(LOGO_BBOX),
            'cutout_method': 'none; official original already transparent', 'original_colors_preserved': True}],
        'media_source_ledger': used + [{'id': 'license', 'path': str(EP / 'research/license.txt'),
            'sha256': sha(EP / 'research/license.txt'), 'url': 'https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE'}],
        'candidates': candidates, 'external_requests': 0}
    manifest_path = OUT / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    if Path(candidates[0]['path']).suffix.lower()=='.jpg':
        shutil.copyfile(candidates[0]['path'], EP / 'thumbnail.jpg')
    else:
        Image.open(candidates[0]['path']).save(EP / 'thumbnail.jpg', quality=97, subsampling=0, optimize=True)
    shutil.copyfile(OUT / 'qwen21_cleanup_question_v01.png', EP / 'thumbnail.png')
    contact = Image.new('RGB', (1280, 720), IVORY)
    for i, candidate in enumerate(candidates):
        thumb = Image.open(candidate['path']).resize((640, 360), Image.Resampling.LANCZOS)
        contact.paste(thumb, ((i % 2) * 640, (i // 2) * 360))
    contact.save(OUT / 'contact_sheet.png')
    validator = Path('C:/Users/kanag/.codex/skills/generate-tech-news-thumbnails/scripts/validate_thumbnail.py')
    results = []
    for candidate in candidates:
        # YouTube's byte-size check is reported separately from 1920x1080 visual delivery.
        completed = subprocess.run([sys.executable, str(validator), candidate['path'], '--manifest', str(manifest_path), '--require-brand'], capture_output=True, text=True)
        results.append(json.loads(completed.stdout))
    (OUT / 'validation.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps({'candidates': len(candidates), 'recommended': str(EP / 'thumbnail.jpg'),
                      'validator_passed': [x['passed'] for x in results], 'bytes': [x['bytes'] for x in results]}, indent=2))


if __name__ == '__main__':
    main()
