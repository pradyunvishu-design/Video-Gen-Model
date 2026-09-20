import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.produce_dreamx_episode import EP, capture_checkpoint, duration_fit_factor, read, sha, underline_filters


class DreamXEpisodeTests(unittest.TestCase):
    def test_underlines_require_evidence_and_valid_time(self):
        sample={'measurement':'exact single-line browser DOM Range','region':{'x':.4,'y':.45,'width':.1,'height':.03},'start':.5,'end':3}
        result=underline_filters([sample],6)
        self.assertEqual(result.count('drawbox='),24)
        self.assertIn('h=3:color=0xBA3D36',result)
        with self.assertRaises(ValueError):
            underline_filters([{**sample,'measurement':'guessed'}],6)
        with self.assertRaises(ValueError):
            underline_filters([{**sample,'end':9}],6)
        with self.assertRaises(ValueError):
            underline_filters([{**sample,'region':{**sample['region'],'x':.99}}],6)

    def test_partial_capture_refresh_preserves_old_receipts(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'ledger.json'
            capture_checkpoint(path,{'a':{'id':'a','v':1},'b':{'id':'b','v':1}},[{'id':'a','v':2}])
            self.assertEqual({x['id']:x['v'] for x in read(path)},{'a':2,'b':1})
            self.assertFalse(path.with_suffix('.pending.json').exists())

    def test_near_target_keeps_natural_pace(self):
        self.assertAlmostEqual(duration_fit_factor(477.72, 7), 1)
        self.assertTrue(.94 <= duration_fit_factor(470, 7) <= 1.06)

    def test_large_mismatch_fails_instead_of_padding_or_cutting(self):
        for seconds in [0, 300, 600]:
            with self.assertRaises(ValueError):
                duration_fit_factor(seconds, 7)
        with self.assertRaises(ValueError):
            duration_fit_factor(480, 0)

    def test_script_is_reviewed_and_evidence_mapped(self):
        script=read(EP/'script.json')
        review=read(EP/'script_review.json')
        evidence=read(EP/'evidence.json')
        valid={x['id'] for x in evidence['claims']} | set(evidence['editorial_tags'])
        self.assertTrue(review['passed'])
        self.assertEqual(review['script_hash'],sha(EP/'script.json'))
        words=0
        for chapter in script['chapters']:
            self.assertEqual(len(chapter['paragraphs']),len(chapter['paragraph_evidence']))
            self.assertTrue(chapter['sources'])
            for paragraph,ids in zip(chapter['paragraphs'],chapter['paragraph_evidence']):
                self.assertTrue(ids)
                self.assertTrue(set(ids)<=valid)
                words+=len(paragraph.split())
        self.assertTrue(1200<=words<=1350)
        self.assertFalse(script['independent_model_test'])


if __name__=='__main__':
    unittest.main()
