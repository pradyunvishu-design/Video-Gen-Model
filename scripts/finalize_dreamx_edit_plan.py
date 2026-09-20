"""Freeze the reviewed shot plan with exact source cues and no filler flashes."""
from scripts.produce_dreamx_episode import EP, read, dump, sha
from collections import Counter


def finalize():
    base=read(EP/'full_edit_plan.json')
    rows=base['shots']
    by_id={r['id']:r for r in rows}
    ledger={r['id']:r for r in read(EP/'captures/ledger.json')}

    def source(shot,asset,reason):
        r=by_id[shot];item=ledger[asset];b=item['bounds']
        x=max(0,b['x']);y=max(0,b['y']);w=min(1920-x,b['width']);h=min(1080-y,b['height'])
        r.update(kind='source',source_path=item['path'],source_id=item['source_id'],
                 focus={'x':x/1920,'y':y/1080,'width':w/1920,'height':h/1080,'basis':'visible DOM bounds'},
                 relevance=reason,rationale=reason)

    def illustration(shot,concept,headline,labels,reason):
        r=by_id[shot]
        r.update(kind='editorial',source_path='ORIGINAL_ILLUSTRATION',source_id='editorial',
                 focus={'x':0,'y':0,'width':1,'height':1,'basis':'original full-frame illustration'},
                 concept=concept,headline=headline,labels=labels,
                 relevance=reason,rationale=reason,illustration_label='Illustration')

    # Put the measured source text under the actual introductory sentence.
    by_id['opening_1a']['duration']=6.0
    r=by_id['opening_1b'];r['start']=20.443;r['duration']=6.8
    r['source_path']='captures/repository_input_focus.png';r['focus']=None
    r['relevance']='First frame and native joint audio-video generation, measured exact text'
    r['rationale']='Verified DOM Range underlines at the same narration beat'
    by_id['opening_1c']['start']=27.243;by_id['opening_1c']['duration']=10.565
    illustration('opening_1c','image_prompt','Picture and sound, together',
                 ['Starting image','Describe the action','Video + sound'],
                 'Explain the joint-generation premise while the roadmap is narrated')
    illustration('listen_0b','cup_contact','The tap belongs to the contact',
                 ['Cup meets table','Sound begins'],
                 'Hypothetical cup example; no model output or score implied')
    illustration('listen_3c','separate_scores','One event. Three checks.',
                 ['Picture','Sound','Timing'],'Restates the exact single-event evaluation method')
    source('mechanism_0b','repository_03','The README describes the two coordinated streams')
    illustration('mechanism_2a','separate_scores','A mechanism is not a guarantee',
                 ['Look','Listen','Check the timing'],'Distinguish architectural capability from actual output quality')
    by_id['mechanism_1a']['labels']=['Two streams refer to the same event']
    by_id['mechanism_1a']['illustration_label']='Illustrative analogy'
    by_id['mechanism_2b']['labels']=['Visible action','Matching sound','Same moment']
    by_id['mechanism_3b']['labels']=['A key is pressed','Its note belongs here']
    illustration('resolution_1a','sharpness_not_sync','Sharper is not better timed',
                 ['Picture detail','Sound timing'],'Image resolution and synchronization are separate properties')
    source('resolution_1b','refinement_01','Refinement synthesizes video and retains the original audio by default')
    source('test_plan_1a','generation_05','Input, seed and inference options make attempts traceable')
    by_id['test_plan_0a']['illustration_label']='Proposed test — not run here'
    by_id['test_plan_0b']['labels']=['Repeated action','Matching rhythm']
    by_id['test_plan_0b']['illustration_label']='Proposed tests — not run here'
    by_id['test_plan_0b']['headline']='Test 2: repeated action'
    speech=dict(by_id['test_plan_0b'])
    speech.update(id='test_plan_0c',start=299.3,concept='speech_sync',
                  headline='Test 3: speech',labels=['Mouth movement','Voice at the same moment'],
                  relevance='The narration introduces speech and mouth/voice timing',
                  rationale='Original mouth symbol and waveform; not a model result or real person')
    rows.insert(rows.index(by_id['test_plan_0b'])+1,speech)
    by_id['test_plan_1b']['labels']=['Keep the input','Keep every attempt']
    by_id['test_plan_2b']['labels']=['One changed setting','Compare with the baseline']
    by_id['test_plan_3b']['labels']=['Describe the event','Name the specific error']
    by_id['resolution_2b']['headline']='One step does not mean one second'
    by_id['resolution_2b']['labels']=['Elapsed time','Generation','Refinement']
    # A 0.379 second page flash adds no information; retain the explanatory shot.
    by_id['access_2b']['duration']=10.379
    rows=[r for r in rows if r['id']!='access_2c']
    illustration('conclusion_0b','caveats','Look beyond the showcase',
                 ['Complex scenes under-represented','Inspect failures, not only highlights','No universal winner claimed'],
                 'Paper limitation paraphrase, not a misleading unrelated speed-settings screenshot')
    by_id['conclusion_0b']['illustration_label']='Source: DreamX-Creator technical report'
    by_id['conclusion_0a']['illustration_label']='Source: DreamX-Creator technical report'
    by_id['conclusion_1b']['labels']=['Movement and sound refer to the same event']
    illustration('conclusion_2b','final_question','When you listen, does it hold up?',
                 ['Watch the action. Listen for its sound.'],
                 'Close on the useful viewing question rather than replaying the same teaser a third time')
    by_id['conclusion_2a']['labels']=['Look, listen, then judge them together.']
    # Preserve paragraph boundaries, quantizing only at the final 30fps assembly.
    for left,right in zip(rows,rows[1:]):left['duration']=right['start']-left['start']
    rows[-1]['duration']=480-rows[-1]['start']
    for row in rows:
        if row.get('concept')=='cup_contact' and row['kind']=='editorial':
            row['visual_revision']='cup-contacts-table-v2'
    locked={'schema_version':3,'duration_seconds':480,'shots':rows,
        'source_draft_sha256':sha(EP/'full_edit_plan.json'),
        'rules':{'source_max_reuse':2,'motion_clip_max_reuse':1,
                 'source_treatment':'Directed subpixel push-in; cursor outside text; red underline only with exact DOM evidence',
                 'no_source_audio':True,'publishing_enabled':False},
        'source_focus_sha256':sha(EP/'captures/source_focus.json'),
        'shot_counts':dict(Counter(r['kind'] for r in rows))}
    dump(EP/'full_edit_plan_locked.json',locked)
    return locked


if __name__=='__main__':
    p=finalize()
    print('Locked',len(p['shots']),'shots',p['shot_counts'])
