"""Build analysis-only boards from cached training frames, never sealed holdouts."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def build(root: Path, output: Path, count: int = 50):
    corpus = json.loads((root / 'data/motion_expert_runs/ai_labs_motion_v1/reference_corpus.json').read_text())
    run = json.loads((root / 'data/motion_expert_runs/ai_labs_motion_v1/motion_expert_run.json').read_text())
    heldout = set(run['holdout_ids'])
    records = list(corpus['training'])
    known = {v['video_id'] for v in records}
    for path in sorted((root / 'data/fidelity_runs/_reference_cache/ai_labs').glob('*.json')):
        record = json.loads(path.read_text())
        if record['video_id'] not in known | heldout and record.get('analysis_frame_strip'):
            records.append(record)
            known.add(record['video_id'])
    eligible = [r for r in records if r['video_id'] not in heldout
                and r.get('channel_id') == 'UCelfWQr9sXVMTvBzviPGlFw'
                and Path(r.get('analysis_frame_strip', '')).is_file()][:count]
    if len(eligible) < count:
        raise ValueError(f'Only {len(eligible)} non-holdout records have cached visual evidence')
    output.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 22)
    boards = []
    for offset in range(0, len(eligible), 6):
        board = Image.new('RGB', (1920, 1740), '#eeeeea')
        pen = ImageDraw.Draw(board)
        for i, record in enumerate(eligible[offset:offset+6]):
            x, y = (i % 2)*960, (i//2)*580
            pen.text((x+14, y+7), f"{offset+i+1:02d} | {record['video_id']} | {record['title'][:53]}", fill='#111111', font=font)
            with Image.open(record['analysis_frame_strip']) as strip:
                board.paste(strip.convert('RGB').resize((960, 540)), (x, y+40))
        destination = output / f'board_{offset//6+1:02d}.jpg'
        board.save(destination, quality=94)
        boards.append(str(destination))
    manifest = {'channel': corpus['channel'], 'video_count': len(eligible), 'heldout_excluded': True,
                'method': 'Cached sampled-frame inspection; not full-video viewing or measured temporal choreography',
                'boards': boards, 'records': [
        {k: r.get(k) for k in ('video_id', 'title', 'url', 'analysis_frame_strip', 'motion_trace_path')}
        | {'sampled_timecodes': r.get('visual_timecodes', [])[1:7:2]}
        | {'frame_sha256': hashlib.sha256(Path(r['analysis_frame_strip']).read_bytes()).hexdigest()}
        for r in eligible]}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return {'video_count': len(eligible), 'boards': boards}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.root, args.output)))
