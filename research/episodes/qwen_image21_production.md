# Qwen-Image 2.1 private evaluation episode

Topic: whether native transparency, constrained edits, and multiple references
could reduce the work after generating an image. This is a source-led explainer,
not a model benchmark or claimed independent generation test.

## Production entrypoints

Use Python 3.12 from the repository root. Runtime files stay under
`data/episodes/episode_20260920_qwen_image21`; credentials stay in the existing
environment and are never part of an export.

1. `py -3.12 -m scripts.produce_qwen21_episode acquire`
2. `py -3.12 -m scripts.produce_qwen21_episode prepare`
3. `py -3.12 -m scripts.produce_qwen21_episode review`
4. `py -3.12 -m scripts.produce_qwen21_episode narrate`
5. `py -3.12 -m scripts.produce_qwen21_episode audio_qc`
6. `py -3.12 scripts/capture_qwen21_sources.py`
7. `py -3.12 -m scripts.produce_qwen21_episode graphics`
8. `py -3.12 -m scripts.assemble_qwen21_episode make_plan`
9. `py -3.12 -m scripts.assemble_qwen21_episode render`
10. `py -3.12 -m scripts.assemble_qwen21_episode delivery_checks`
11. `py -3.12 -m scripts.produce_qwen21_episode package`

Narration uses the existing Gemini TTS Zubenelgenubi voice. Only rejected chapter
inputs are changed by `repair_audio`; run `audio_qc` again afterward. There is a
maximum of two repair attempts per rejected chapter. Review uses the existing
OpenRouter helper with a one-dollar episode cap. Gemini billing is not returned
by the API; token receipts are retained instead of asserting a dollar charge.
No Magic Hour calls are needed for this source-led episode.

Graphics extend the existing deterministic Remotion source-explainer path, using
simple original SVG/React diagrams at 1920x1080. Existing FFmpeg source-motion
rendering performs measured DOM-range highlights and small stable reframing.
This is not an implementation of a new general-purpose authoring framework.

## Review boundaries

- Publishing is disabled. No upload endpoint is called.
- Qwen materials have a research/non-commercial license; do not infer commercial
  clearance from available model weights or the existence of this private draft.
- Keep the downloaded license, source ledger and NOTICE beside the local video.
- Official showcase images illustrate model capabilities. They are not our own
  model outputs or independent measurements.
- The selected thumbnail's illustrated backplate is not an authentic model
  output. Its official logo is composited afterward from the untouched source.
- Thumbnail masters and source media are deliberately not checked into Git.
  `finish_qwen21_thumbnails` requires the local `thumbnail_concept.png` plate.
- No subtitles, borrowed source audio, or uncleared background music are added.
- Deterministic audio checks do not constitute a human listening certification.
- A final human review still determines publication suitability and viewer appeal.

## Verification

Focused tests: `py -3.12 -m pytest tests/test_qwen21_episode.py tests/test_audio_qc.py -q`.
Use a fresh, explicitly named `--basetemp` if the legacy default temporary folder
has Windows permission problems. Captures can be checked without the network
using `py -3.12 scripts/capture_qwen21_sources.py --verify-only`.

Inspect both sides of every cut in `edit/boundaries`, inspect the finished MP4,
and retain `technical_qc.json`, `audio_export_qc.json`, `delivery_checks.json`,
source-image repetition counts, and thumbnail validation alongside the draft.
