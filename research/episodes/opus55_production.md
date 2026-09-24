# Claude Opus 5.5 episode

Production adapter for a ten-minute, source-led Diffusion Daily explainer. This is published-source analysis, not a claimed hands-on model benchmark. No upload or publishing action is included.

## Reproducible stages

Run from the repository root with the existing Python environment:

```powershell
py -3.12 -m scripts.acquire_opus55_sources discover
py -3.12 -m scripts.acquire_opus55_sources acquire
py -3.12 -m scripts.acquire_opus55_sources text_sources
py -3.12 -m scripts.acquire_opus55_sources record_comparisons
py -3.12 -m scripts.capture_opus55_sources
py -3.12 -m scripts.produce_opus55_episode prepare
py -3.12 -m scripts.produce_opus55_episode review
py -3.12 -m scripts.produce_opus55_episode narrate
py -3.12 -m scripts.produce_opus55_episode fit_duration
py -3.12 -m scripts.produce_opus55_episode audio_qc
py -3.12 -m scripts.render_opus55_motion render
py -3.12 -m scripts.assemble_opus55_episode make_plan
py -3.12 -m scripts.assemble_opus55_episode render
py -3.12 -m scripts.assemble_opus55_episode contacts
py -3.12 -m scripts.assemble_opus55_episode delivery_checks
py -3.12 -m scripts.produce_opus55_episode package
```

Inspect each gate before proceeding. If narration fails, `prepare_repair` generates isolated replacement chapters, `repair_audio` applies them, and `audio_qc` must pass again. A failed replacement cannot simply be reused and marked approved. Source availability and public-page layouts can change; recheck the actual captures.

## Production contract

- Exactly 600 seconds; 1920x1080, H.264, 30 fps.
- One original Zubenelgenubi narrator; no source audio or subtitles.
- Eight original 12-second explanatory graphics, each used once.
- First-party launch quotation and stable public-page comparison recordings.
- Source excerpts at most twice; no still hold longer than twelve seconds.
- Exact measured underlines only when they support the current narration.
- Article capture hashes, source URLs, commentary basis, and pending publication review retained in episode ledgers.
- Paid factual review uses the existing OpenRouter key and a per-episode ceiling of $1. Gemini TTS uses the existing environment key; do not put credentials in this document or export.
- Retimed narration, aligned paragraph timing, edit plan, and final export are hash-bound to their reviews. The complete final export is decoded and checked against narration audio.

## Verification

Focused regression command:

```powershell
py -3.12 -m pytest tests/test_opus55_episode.py -q -p no:cacheprovider --basetemp "$env:TEMP/opus55-test-fresh"
```

Use a fresh dedicated test directory. The default repository pytest temporary directory can be locked on this Windows host.

Final artifacts and actual test results belong under `data/episodes/episode_20260923_opus55`; local rendered media and provider credentials are not GitHub source-code artifacts.

## Six official demo revision

The six user-selected Claude videos are identity-checked against official channel
`UCV03SRZXJEz-hchIAogeJOg`. This revision uses bounded, silent native-1080p excerpts,
not full source films. The original export and approved narration remain unchanged.

```powershell
py -3.12 -m scripts.acquire_opus55_six_demos discover
py -3.12 -m scripts.acquire_opus55_six_demos acquire
py -3.12 -m scripts.acquire_opus55_six_demos contacts
py -3.12 -m scripts.revise_opus55_six_demos plan
py -3.12 -m scripts.revise_opus55_six_demos render
py -3.12 -m scripts.revise_opus55_six_demos contacts
py -3.12 -m scripts.revise_opus55_six_demos delivery_checks
```

Inspect actual excerpts before rendering: daily-effort footage must begin at local
2.5 seconds to exclude the presenter; daily-review-diff starts at local 0.3 seconds
to exclude a one-frame presenter flash; GPS-interactive starts at local 4 seconds
to skip its title card. Versioned selections and placements live in `configs/opus55_six_demo_*.json`;
episode-local manifests can override them. Original episode assets are required.
Never infer download permission or publication clearance from discovery metadata.

Output: `data/episodes/episode_20260923_opus55_six_demos/Claude_Opus_55_Six_Demos_1080p.mp4`.
The reviewed plan replaces 22 shots and contains 178.7 seconds of real video,
325.3 seconds of article/source evidence, and 96 seconds of original diagrams.
Every requested source appears, with non-overlapping source time ranges. Illustrative
creative demos do not establish the independent benchmark or pricing claims; keep
the corresponding evidence pages and avoid presenting the source demos as our tests.
Publishing remains disabled and excerpt rights remain pending human review.
