import json
from pathlib import Path
import pytest
from PIL import Image
from scripts.audit_motion_reference_frames import build


def test_training_boards_exclude_sealed_records_and_report_actual_samples(tmp_path):
    run_dir = tmp_path / 'data/motion_expert_runs/ai_labs_motion_v1'
    run_dir.mkdir(parents=True)
    cache = tmp_path / 'data/fidelity_runs/_reference_cache/ai_labs'
    cache.mkdir(parents=True)
    frame = tmp_path / 'frame.jpg'
    Image.new('RGB', (960, 540)).save(frame)
    def record(video_id):
        return dict(video_id=video_id, title='Example', channel_id='UCelfWQr9sXVMTvBzviPGlFw',
                    visual_timecodes=list(range(8)), analysis_frame_strip=str(frame))
    (run_dir / 'reference_corpus.json').write_text(json.dumps({
        'channel': {}, 'training': [record('training')],
        'holdout': {'count': 1, 'sealed_manifest': 'never-read.json'}}))
    (run_dir / 'motion_expert_run.json').write_text(json.dumps({'holdout_ids': ['sealed']}))
    (cache / 'sealed.json').write_text(json.dumps(record('sealed')))
    output = tmp_path / 'boards'
    with pytest.raises(ValueError, match='Only 1'):
        build(tmp_path, output, count=2)
    build(tmp_path, output, count=1)
    result = json.loads((output / 'manifest.json').read_text())
    assert result['video_count'] == 1
    assert result['records'][0]['sampled_timecodes'] == [1, 3, 5]
    assert 'sealed' not in json.dumps(result['records'])


def test_practice_profile_is_not_a_certified_fidelity_claim():
    root = Path(__file__).resolve().parents[1]
    profile = json.loads((root / 'configs/motion_craft_profile.json').read_text())
    assert profile['status'] == 'practice_not_fidelity_certified'
    assert profile['canvas'] == {'width': 1920, 'height': 1080, 'fps': 30}
    assert profile['gates']['require_human_preview']
    assert not profile['gates']['sealed_holdout_access']
    html = (root / 'remotion/hyperframes/motion_craft_v2/index.html').read_text(encoding='utf-8')
    assert 'Math.random' not in html and 'setInterval' not in html
    assert "import {draw} from './framework/ui/draw.js'" in html
    assert 'data-duration="27"' in html
