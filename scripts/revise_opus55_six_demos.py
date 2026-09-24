"""Reversible, narration-preserving edit using six verified official demo sources."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
import shutil

from scripts import assemble_opus55_episode as edit

ORIGINAL=edit.EP
REVISION=ORIGINAL.with_name(ORIGINAL.name+'_six_demos')
EXPECTED={'daily','launch','gps','earthrise','daydreams','gravity'}
DEFAULT_PLACEMENTS=Path(__file__).resolve().parents[1]/'configs/opus55_six_demo_placements.json'


def replace_shot(old,clip,offset,rationale):
    seconds=old['frames']/30
    if (offset<0 or offset+seconds>clip['duration']+.02
            or clip['source_in']<0 or clip['source_out']-clip['source_in']<offset+seconds-.02):
        raise ValueError('Clip cannot cover narration without freezing or looping')
    if not clip.get('rights_basis') or not rationale.strip():
        raise ValueError('Missing rights record or visual rationale')
    row={k:v for k,v in deepcopy(old).items() if k not in {'annotation_path','framing','focus'}}
    row.update(kind='video',asset_id=clip['id'],path=clip['path'],offset=offset,
               source_url=clip['source_url'],source_id=clip['source_id'],
               source_in=clip['source_in']+offset,source_out=clip['source_in']+offset+seconds,
               source_asset_hash=clip['sha256'],rights_basis=clip['rights_basis'],
               publication_approval=clip.get('publication_approval','pending'),
               visual_rationale=rationale,source_audio_used=False)
    return row


def verify_demo_coverage(rows,expected=EXPECTED):
    used={r['source_id'] for r in rows if r.get('source_id')}
    if not expected<=used:raise ValueError('Missing requested official videos: '+str(expected-used))
    ranges=defaultdict(list)
    for row in rows:
        if row.get('source_id'):ranges[row['source_id']].append((row['source_in'],row['source_out']))
    for source,segments in ranges.items():
        ordered=sorted(segments)
        if any(a[1]>b[0]+.02 for a,b in zip(ordered,ordered[1:])):
            raise ValueError('Overlapping source footage: '+source)
    return used


def configure():
    edit.EP=REVISION;edit.OUT=REVISION/'edit'
    edit.FINAL=REVISION/'Claude_Opus_55_Six_Demos_1080p.mp4'


def plan():
    """An explicit reviewed placement manifest; never randomly distribute demo clips."""
    placement_path=ORIGINAL/'research/six_demos/placements.json'
    if not placement_path.exists():placement_path=DEFAULT_PLACEMENTS
    manifest=edit.read(placement_path)
    clips={r['id']:r for r in edit.read(ORIGINAL/'media/six_demos/ledger.json')}
    rows=edit.read(ORIGINAL/'edit_plan.json')
    original_rows=deepcopy(rows)
    index={r['id']:n for n,r in enumerate(rows)}
    touched=set()
    for placement in manifest:
        ident=placement['shot_id']
        if ident in touched:raise ValueError('Duplicate replacement: '+ident)
        touched.add(ident)
        clip=clips[placement['clip_id']]
        if edit.sha(Path(clip['path']))!=clip['sha256']:raise ValueError('Source hash changed')
        row=rows[index[ident]]
        if row['kind']=='motion':raise ValueError('Keep approved explanatory graphics')
        rows[index[ident]]=replace_shot(row,clip,placement.get('offset',0),placement['rationale'])
    verify_demo_coverage(rows);edit.validate(rows)
    REVISION.mkdir(parents=True,exist_ok=True)
    for name in ('script.json','narration.json','audio_qc.json','paragraph_timing.json','brief.json'):
        shutil.copy2(ORIGINAL/name,REVISION/name)
    edit.dump(REVISION/'edit_plan.json',rows)
    receipt=edit.read(ORIGINAL/'edit/plan_receipt.json')
    if receipt['plan_hash']!=edit.sha(ORIGINAL/'edit_plan.json'):
        raise ValueError('Original plan changed since its audio review')
    receipt['plan_hash']=edit.sha(REVISION/'edit_plan.json')
    edit.dump(REVISION/'edit/plan_receipt.json',receipt)
    # Unchanged segments retain their content-hash receipts and need no re-encode.
    for row in rows:
        if row['id'] in touched:continue
        for suffix in ('.mp4','.json'):
            src=ORIGINAL/'edit/segments'/(row['id']+suffix)
            dst=REVISION/'edit/segments'/src.name
            if src.exists() and not dst.exists():
                dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    usage={'source_ids':sorted(verify_demo_coverage(rows)),
           'seconds_by_kind':{k:sum(r['frames']/30 for r in rows if r['kind']==k) for k in ('video','article','motion')},
           'replacement_count':len(touched),'source_counts':dict(Counter(r.get('source_id') for r in rows if r.get('source_id'))),
           'original_export_preserved':True,'narration_changed':False,'publishing_enabled':False}
    edit.dump(REVISION/'edit/source_usage.json',usage)
    edit.dump(REVISION/'edit/placement_manifest.json',manifest)
    edit.dump(REVISION/'edit/revision_inputs.json',{
        'original_plan_hash':edit.sha(ORIGINAL/'edit_plan.json'),
        'placement_manifest_hash':edit.sha(placement_path),
        'source_ledger_hash':edit.sha(ORIGINAL/'media/six_demos/ledger.json'),
        'changed_shots':sorted(touched),
        'original_timings':[(r['id'],r['start_frame'],r['frames']) for r in original_rows]})
    print(usage,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['plan','render','contacts','delivery_checks'])
    args=parser.parse_args()
    if args.stage=='plan':plan()
    else:
        configure();getattr(edit,args.stage)()
