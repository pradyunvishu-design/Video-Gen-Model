"""No-network contract tests for the scoped Astra picture repair."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import repair_astra_motion as r

class RepairTests(unittest.TestCase):
    def test_source_allocations_never_overlap_within_pass(self):
        t=r.read(r.EP/'timeline.json')
        groups={}
        for s in t['shots']:
            if 'source_pass' not in s:continue
            self.assertIn(s['source_pass'],[1,2]);self.assertGreaterEqual(s['speed'],.38)
            groups.setdefault((s['asset'],s['source_pass']),[]).append((s['source_offset'],s['source_end']))
        for entries in groups.values():
            entries.sort()
            for a,b in zip(entries,entries[1:]):self.assertLessEqual(a[1],b[0]+1e-6)

    def test_timing_narration_evidence_unchanged(self):
        before=r.read(r.SOURCE/'timeline.json')['shots'];after=r.read(r.EP/'timeline.json')['shots']
        self.assertEqual(len(before),len(after))
        for a,b in zip(before,after):
            for key in ['start_frame','frames','duration','narration','evidence_ids']:
                self.assertEqual(a[key],b[key])

    def test_all_photos_replaced(self):
        t=r.read(r.EP/'timeline.json')
        self.assertFalse(any(s['kind']=='photo' for s in t['shots']))
        self.assertEqual(t['shots'][2]['kind'],'video')
        self.assertEqual(t['shots'][2]['asset'],'house')
        self.assertFalse(t['publishing_enabled'])

    def test_insufficient_footage_fails_instead_of_looping(self):
        with self.assertRaises(ValueError):
            r.allocate_ranges([{'index':0,'asset':'house','duration':120}],{'house':1})

    def test_source_signature_present(self):
        t=r.read(r.EP/'timeline.json');self.assertEqual(len(t['source_master_hash']),64)

    def test_quote_detail_keeps_exact_source_credit_pixels(self):
        from PIL import Image
        shot=next(s for s in r.read(r.EP/'timeline.json')['shots'] if s['asset']=='playco_fixes')
        detail=Image.open(r.detail_image(shot)).convert('RGB')
        original=Image.open(shot['path']).convert('RGB')
        self.assertEqual(detail.crop((0,980,1920,1080)).tobytes(),original.crop((0,880,1920,980)).tobytes())

    def test_exact_expected_frame_count(self):
        self.assertEqual(sum(s['frames'] for s in r.read(r.EP/'timeline.json')['shots']),21517)

    def test_frozen_or_missing_moving_sample_blocks_qc(self):
        self.assertFalse(r.moving_samples_pass([{'index':2,'exact_freeze_across_samples':True}],{2}))
        self.assertFalse(r.moving_samples_pass([],{2}))
        self.assertTrue(r.moving_samples_pass([{'index':2,'exact_freeze_across_samples':False}],{2}))

    def test_large_temporal_packet_expression_parses(self):
        expr=r.selection_expression(range(200))
        r.run(['ffmpeg','-v','error','-f','lavfi','-i','color=black:s=32x32:r=30:d=0.1','-vf','select='+expr,'-frames:v','1','-f','null','-'])

if __name__=='__main__':unittest.main()
