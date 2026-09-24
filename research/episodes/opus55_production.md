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
