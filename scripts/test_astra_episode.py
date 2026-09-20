"""Artifact-contract checks for the locally produced Astra episode."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.produce_astra_episode import EP,read,probe
from PIL import Image

class AstraEpisodeTests(unittest.TestCase):
    def test_evidence_links_resolve(self):
        evidence=read(EP/'evidence.json')
        for chapter in read(EP/'script.json')['chapters']:
            for source in chapter['sources']:self.assertIn(source,evidence)

    def test_frame_coverage_and_repetition(self):
        timeline=read(EP/'timeline.json');cursor=0;previous_still=None;held_frames=0
        for shot in timeline['shots']:
            self.assertEqual(shot['start_frame'],cursor);cursor+=shot['frames']
            self.assertGreater(shot['frames'],0)
            if shot['kind']=='card':self.assertLessEqual(shot['frames'],360)
            if shot['kind'] in ['card','photo']:
                held_frames=held_frames+shot['frames'] if previous_still==shot['path'] else shot['frames']
                previous_still=shot['path']
                self.assertLessEqual(held_frames,360,'Adjacent cuts must not disguise a long identical still hold')
            else:
                previous_still=None;held_frames=0
        self.assertAlmostEqual(cursor/30,timeline['duration'],places=5)
        self.assertLessEqual(max(timeline['source_video_uses'].values()),2)

    def test_one_voice_and_final_tail(self):
        narration=read(EP/'narration.json')
        self.assertEqual({x['voice'] for x in narration['chapters']},{'Zubenelgenubi'})
        self.assertTrue(read(EP/'audio_qc.json')['passed'])
        self.assertGreaterEqual(read(EP/'timeline.json')['duration']-narration['duration'],1.15)

    def test_bounded_muted_first_party_excerpts(self):
        for rec in read(EP/'media/ledger.json'):
            self.assertFalse(rec['source_audio_used'])
            self.assertLess(rec['source_out']-rec['source_in'],rec['full_source_duration'])
            self.assertIn('OpenAI',rec['publisher'])
            self.assertTrue(rec['rights_basis'])
            self.assertFalse(any(s['codec_type']=='audio' for s in probe(rec['path'])['streams']))

    def test_dimensions_and_thumbnails(self):
        for image in (EP/'cards').glob('*.png'):
            with Image.open(image) as im:self.assertEqual(im.size,(1920,1080))
        for check in read(EP/'thumbnails/qc.json'):self.assertTrue(check['passed'])

    def test_spend_and_no_publishing(self):
        spend=read(EP/'provider_usage.json')
        self.assertLessEqual(spend['openrouter_usd'],spend['openrouter_cap_usd'])
        self.assertFalse(read(EP/'package.json')['publishing_enabled'])
        self.assertFalse(read(EP/'package.json')['captions'])

if __name__=='__main__':unittest.main()
