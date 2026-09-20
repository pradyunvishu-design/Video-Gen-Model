"""Cached Magic Hour thumbnail backplates; exact branding is composed separately."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from pipeline import magichour

OUT = Path(__file__).resolve().parents[1] / 'data/episodes/episode_20260907_dreamx_creator/thumbnails'

def create(i, prompt):
    record = OUT / f'job_{i}.json'
    if record.exists():
        job = json.loads(record.read_text())
    else:
        job = magichour.image_generate(prompt, f'DreamX editorial concept {i}', model='nano-banana-2', resolution='2k')
        record.write_text(json.dumps(job, indent=2))
    print(json.dumps({'concept': i, 'id': job['id'], 'credits_charged': job.get('credits_charged')}), flush=True)
    dest = OUT / f'plate_{i}.png'
    if not dest.exists():
        result = magichour.wait_image(job['id'])
        magichour.download(result, dest)
        record.write_text(json.dumps({k:v for k,v in result.items() if k != 'downloads'}, indent=2))
    return str(dest)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        OUT = args.output.resolve()
    brief = json.loads((OUT/'creative_brief.json').read_text())
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(lambda pair: create(*pair), enumerate(brief['prompts'])):
            print(result, flush=True)
