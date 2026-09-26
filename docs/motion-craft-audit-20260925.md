# Motion craft audit and private practice preview

## What was actually inspected

The public channel listing confirmed **AI LABS / @AILABS-393**, channel ID
`UCelfWQr9sXVMTvBzviPGlFw`, on 2026-09-25. The local analysis boards contain
**50 distinct training/reference videos**, normally three sampled frames each.
Forty-nine were reused from the existing training corpus; `bBMp5tLxShQ` was
added through public playback frame extraction. No complete source video was
saved. Seven sealed holdouts were excluded and were not viewed for authoring.

This is a sampled-frame design study, **not 50 complete video viewings**, a
trained model, a comprehensive motion-family census, or a 99% fidelity result.
The cached short motion traces do not establish every entrance, easing curve,
or narrative placement. Their existence must not be confused with full review.

Local evidence: `data/research/ailabs_craft_20260925/manifest.json` records IDs,
URLs, sampled timecodes, image hashes and the nine analysis boards. Temporary
analysis frames are research material, not footage cleared for production.

## Reusable observations

| Relationship / observation | Training evidence (seconds) | Application and limit |
| --- | --- | --- |
| A small workflow advances between tasks; most of the frame stays quiet | [bBMp5tLxShQ](https://www.youtube.com/watch?v=bBMp5tLxShQ&t=127), 127.286 / 381.857 | Stage the active step; don't fill every corner. Still frames do not prove the animation speed. |
| Task rows and execution artifacts carry the explanation | [WJgxX0Eib6k](https://www.youtube.com/watch?v=WJgxX0Eib6k&t=102), 102 / 306 / 510 | Show concrete states rather than decorative brand cards. |
| Relationships are expressed through branches and connection paths | [AD-EmZ3v6-g](https://www.youtube.com/watch?v=AD-EmZ3v6-g&t=129), 129 / 387 / 645 | Use branching only when the narration describes it; do not trace the reference geometry. |
| File/graph structure and text hierarchy explain system boundaries | [H7t3uUp3HVw](https://www.youtube.com/watch?v=H7t3uUp3HVw&t=121), 121 / 363 / 605 | One active hierarchy, less emphasis on surrounding detail. |
| Input, processing and output can be an actual relationship rather than three generic title cards | [aMBQB_IJ0dQ](https://www.youtube.com/watch?v=aMBQB_IJ0dQ&t=132), 132 / 396 / 660 | Draw the connective logic before adding decorative surfaces. |
| Capacity/context is represented spatially | [O1XLCh-uA_E](https://www.youtube.com/watch?v=O1XLCh-uA_E&t=111), 111.143 / 333.429 / 555.714 | Only use quantities and proportions supported by evidence. |
| Focused real code/document text is more informative than recreated pseudo-code | [fMY5Sdj2DMk](https://www.youtube.com/watch?v=fMY5Sdj2DMk&t=117), 117.143 / 351.429 / 585.714 | Crop and emphasize the exact relevant passage. Preserve provenance. |

Some references use purple/blue surrounds or yellow accents. We deliberately
retain the user's neutral/moss/clay palette instead. This alone makes claims
of exact replication inappropriate. Company marks must keep their real colors.

## Problems found in the old evaluator

1. `build_motion_pattern_catalog` assigns references to hardcoded families by
   index arithmetic. Those links do not demonstrate that a family was observed
   at that timecode. Treat the legacy catalog as heuristics, not measured truth.
2. Post-repair reviews retained old ratings on untouched axes and segments,
   even when a fresh reviewer reported regressions. This could manufacture a
   cumulative pass. Fixed: use every fresh rating, validate completeness and
   reject any individual regression or hard failure.
3. Legacy accepted reviews could be reused without re-evaluation. Fixed: a
   `fresh_matrix_v2` policy is now required for accepted-review reuse. Historical
   files remain intact; their old `perfect_fidelity` status is not new evidence.
4. Global image brightness/edge statistics are not a complete measure of
   typography, motion timing or placement. The old numeric result is not a
   defensible 99% quality claim, even after fixing score aggregation.

## Art direction / concept choice

Three distinct concepts were considered:

- **Narration-to-candidate selection:** connect a concrete action in a sentence
  to its best visual example. Chosen for the first beat because the change of
  emphasis itself teaches semantic footage matching.
- **Evidence convergence:** separate source, excerpt and permission requirements
  converge on one usable artifact. Chosen for the second beat because a gate is
  clearer than a scrolling checklist.
- **Edit timeline:** repeat identity stays visible and a third use is replaced.
  Chosen for the third beat because temporal arrangement is the actual point.

These are three scenes within one original 27-second practice composition,
not three recolored versions of the same card. Their proof object is the
existing `pipeline/video_composer.py` selection logic: reviewed claim matches,
recorded rights, defined excerpts and a two-use limit by asset hash. Clip icons
are explicitly illustrative; they are not invented screenshots or benchmarks.

Frame contract: 1920×1080, 128px safe inset, neutral background, restrained
moss emphasis, sentence-case heading, no logo-as-entire-idea, locked camera,
short 18px entrances, drawn connectors and hard cuts. Authored timing is a
hypothesis to review, not a measurement attributed to AI LABS.

## Reproduce

```powershell
python -m scripts.audit_motion_reference_frames --output data/research/ailabs_craft_20260925
python -m scripts.build_motion_craft_preview
cd data/motion_expert_runs/craft_v2/preview
npx hyperframes@0.8.77 check --json
npx hyperframes@0.8.77 snapshot --at 5.8,15.5,25 --output frames --json
npx hyperframes@0.8.77 preview --background --port 3019
```

Use the project's Python environment with Pillow, requests and the pipeline
dependencies. The preview builder is Windows-local (junction creation). It
links the pinned `recreate-video` dependency without copying its implementation.
That dependency remains **private-evaluation-only pending license verification**.
GSAP 3.14.2 is downloaded once and cached locally. No Magic Hour/OpenRouter
generation, voice change, publication or production-episode replacement occurs.

## Verification on this pass

- `tests/test_ai_labs_motion_expert.py` plus `tests/test_motion_craft_preview.py`:
  **38 passed**, using Python 3.12 and a fresh task-specific pytest base directory.
- Independent code review was repeated after fixing its findings; no blocking
  issues remained in the reviewed changes. The reviewer found no hard readability
  defects in the three settled full-HD frames. This was not heldout fidelity scoring.
- HyperFrames 0.8.77 check: zero errors, 47/47 text contrast checks passed, no
  runtime errors. Three scene-structure recommendations remain, plus a connector
  heuristic that associates a scene-two line with the hidden scene-one `#spoken`
  node. The actual scene-two source and result were visually verified on stage.
- Twelve timestamped proof frames show the entrance, connector reveal, scene
  cuts, replacement and held final state. The keyframe inspector could not trace
  the imported `draw()` helper; its failed diagnostic is not claimed as a pass.
  Pixel snapshots at 2.45 / 2.75 / 3.1 seconds establish the connector reveal.
- Preview server responded HTTP 200 on port 3019. It is a silent graphics test,
  not a narrated episode. No final MP4 was rendered or published.
- New provider usage: **$0 OpenRouter, 0 Magic Hour credits**.

Exact successful targeted test command (from project root):

```powershell
& 'C:/Users/kanag/AppData/Local/Programs/Python/Python312/python.exe' -m pytest tests/test_ai_labs_motion_expert.py tests/test_motion_craft_preview.py -q -p no:cacheprovider --basetemp .test_tmp/motion_craft_20260925_final
```

Use a new `--basetemp` per run; the repository's shared `.pytest_tmp` was not
writable during the first attempt. The default `python` on this machine points
at an unrelated Hermes environment without Playwright.

## Still required before claiming completion

- Observe full motion intervals and narration boundaries, not just snapshots.
- Replace index-assigned pattern evidence with confirmed family/timecode labels.
- Validate on independent, sealed reference material without feeding it into
  authoring. Do not equate structural tests with a fidelity score.
- Get approval on this preview before final MP4 rendering (HyperFrames gate).
- Promote approved scenes into the general compositor with real episode data;
  this practice package is deliberately not a silently enabled production default.
