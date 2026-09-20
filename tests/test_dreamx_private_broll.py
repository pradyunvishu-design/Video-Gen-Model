import unittest
from scripts.revise_dreamx_private_broll import INSERTS, pieces, validate_inserts, revision_inserts, remove_short_card_flashes


class PrivateBrollTests(unittest.TestCase):
    def test_insert_bounds_and_unique_ids(self):
        validate_inserts()
        self.assertEqual(len(INSERTS),8)

    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):
            validate_inserts([(0,0,90,'a','reason'),(60,90,30,'b','reason')])

    def test_split_across_original_shots_preserves_every_frame(self):
        rows=[{'id':'a','start_frame':0,'end_frame':100},
              {'id':'b','start_frame':100,'end_frame':14400}]
        parts=pieces(rows,[(90,100,20,'clip','reason')])
        self.assertEqual(sum(p['end']-p['start'] for p in parts),14400)
        self.assertEqual([p['offset'] for p in parts if p['kind']=='broll'],[100,110])
        self.assertEqual(sum(p['end']-p['start'] for p in parts if p['kind']=='broll'),20)

    def test_no_change_retains_original_shots(self):
        rows=[{'id':'a','start_frame':0,'end_frame':14400}]
        parts=pieces(rows,[])
        self.assertEqual(len(parts),1)
        self.assertTrue(parts[0]['full'])

    def test_expanded_revision_preserves_original_inserts(self):
        expanded=revision_inserts(True)
        validate_inserts(expanded)
        self.assertEqual(len(expanded),12)
        self.assertTrue(all(item in expanded for item in INSERTS))
        self.assertEqual(sum(item[2] for item in expanded),1023)

    def test_third_source_replay_rejected(self):
        with self.assertRaises(ValueError):
            validate_inserts([(0,0,30,'a','reason'),(30,0,30,'b','reason'),(60,0,30,'c','reason')])

    def test_natural_playout_avoids_third_replay_and_joins_detail(self):
        expanded=revision_inserts(natural_playout=True)
        validate_inserts(expanded)
        by_name={r[3]:r for r in expanded}
        self.assertNotIn('wave_callback',by_name)
        self.assertGreaterEqual(by_name['wave'][2],300)
        self.assertGreaterEqual(by_name['fire'][2],180)
        self.assertEqual(by_name['ice'][0]+by_name['ice'][2],by_name['detail'][0])

    def test_short_card_absorbed_without_touching_broll_or_audio_timing(self):
        raw=[{'kind':'broll','start':0,'end':300},
             {'kind':'base','row_id':'flash','start':300,'end':330,'full':False},
             {'kind':'base','row_id':'explanation','start':330,'end':510,'full':True,'offset':0}]
        result=remove_short_card_flashes(raw)
        self.assertEqual(len(result),2)
        self.assertEqual(result[0],raw[0])
        self.assertEqual((result[1]['start'],result[1]['end']),(300,510))
        self.assertEqual(result[1]['retime_input_frames'],180)


if __name__=='__main__':
    unittest.main()
