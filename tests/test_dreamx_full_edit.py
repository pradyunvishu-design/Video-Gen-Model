"""The final assembly must not hide missing footage or narration truncation."""
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from scripts.assemble_dreamx_full import prepare_plan, run, validate_audio_binding, promote_export


def plan():
    return [{'id':f's{i}','kind':'editorial','concept':'cup_contact',
             'start':i*10,'duration':10,'relevance':'cup touching a surface',
             'rationale':'original illustrative timing example'} for i in range(48)]


class FullEditTests(unittest.TestCase):
    def test_identical_export_does_not_replace_open_file(self):
        with TemporaryDirectory() as directory:
            staged=Path(directory)/'staged.mp4';dest=Path(directory)/'final.mp4'
            staged.write_bytes(b'checked video');dest.write_bytes(b'checked video')
            with patch.object(Path,'replace',side_effect=PermissionError('reader lock')):
                self.assertFalse(promote_export(staged,dest))

    def test_short_padded_narration_cannot_pass(self):
        with self.assertRaises(ValueError):
            validate_audio_binding({'duration_seconds':120,'narration_sha256':'x'},{'narration_sha256':'x'},120)

    def test_stale_audio_review_cannot_pass(self):
        with self.assertRaises(ValueError):
            validate_audio_binding({'duration_seconds':478.67,'narration_sha256':'x'},{'narration_sha256':'changed'},478.67)

    def test_ffmpeg_arguments_normalized(self):
        with patch('scripts.assemble_dreamx_full._run') as child:
            run(['ffmpeg','-frames:v',300,Path('clip.mp4')])
            child.assert_called_once_with(['ffmpeg','-frames:v','300','clip.mp4'],timeout=600)

    def test_frame_contiguity_and_exact_duration(self):
        rows=prepare_plan(plan())
        self.assertEqual(rows[-1]['end_frame'],14400)
        self.assertTrue(all(a['end_frame']==b['start_frame'] for a,b in zip(rows,rows[1:])))

    def test_unfilled_visual_gap_rejected(self):
        rows=plan();rows[8]['kind']='gap'
        with self.assertRaises(ValueError):prepare_plan(rows)

    def test_missing_rationale_rejected(self):
        rows=plan();rows[3]['rationale']=''
        with self.assertRaises(ValueError):prepare_plan(rows)

    def test_long_filler_hold_rejected(self):
        rows=plan();rows[3]['duration']=20
        with self.assertRaises(ValueError):prepare_plan(rows)

    def test_gap_rejected(self):
        rows=plan();rows[3]['start']+=1
        with self.assertRaises(ValueError):prepare_plan(rows)

    def test_single_frame_gap_rejected(self):
        rows=plan();rows[3]['start']+=1/30
        with self.assertRaises(ValueError):prepare_plan(rows)


if __name__=='__main__':unittest.main()
