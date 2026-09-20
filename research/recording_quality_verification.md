# Recording and narration verification — 2026-09-19

## Checked scope

This pass improves the existing pipeline and documents the proposed local Mac
recorder. It does not claim a finished Tauri desktop app, a cloud deployment,
or a rendered new episode. No paid provider requests were made.

Focused suite: **60 passed**, including real FFmpeg 1080p encode and decode.
Python compilation passed for the four changed pipeline modules.
Three local Chrome recordings exercised a real click, a changed result, timed focus,
and a readable result hold, using only a labeled synthetic fixture. The second
preview removes the oversized cursor dot and stale focus rectangle identified
in the first poster inspection. The final preview includes eased cursor movement
and returns to full view after the click, with the updated cache/QC code.
The independent review identified cache invalidation and stale post-click focus;
both were repaired with regression tests. Poster-frame inspection found readable
text and no stale outline. Frame snapshots do not prove subjective motion quality.

## Exact successful commands

Working directory: `C:\Youtube Automation for Magic hour`.

```powershell
& 'C:\Users\kanag\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/test_screen_framing.py tests/test_product_demo.py tests/test_browser_director.py tests/test_browser_director_exact_text.py tests/test_gemini_tts.py tests/test_source_export.py tests/test_tts.py tests/test_audio_qc.py -q -o addopts= -p no:cacheprovider --basetemp 'C:\Users\kanag\AppData\Local\Temp\video_quality_check_20260919d'

& 'C:\Users\kanag\AppData\Local\Programs\Python\Python312\python.exe' -m compileall -q pipeline/screen_framing.py pipeline/product_demo.py pipeline/capture.py pipeline/gemini_tts.py scripts/preview_screen_framing.py

& 'C:\Users\kanag\AppData\Local\Programs\Python\Python312\python.exe' -m scripts.preview_screen_framing --output 'output/screen_framing_preview_20260919_final'

ffmpeg -hide_banner -i 'output/screen_framing_preview_20260919_final/screen_framing_preview_1080p.mp4' -vf 'blackdetect=d=0.1:pix_th=0.10' -an -f null -
```

The first default pytest run failed to initialize temporary folders because the
pre-existing `.pytest_tmp` directory denies access. No production files or that
directory were deleted to work around it. Isolated temporary folders and disabled
pytest caching allowed the suite to run successfully.

## Quality review

- No fake API footage: the canary labels itself LOCAL RECORDING TEST.
- No API keys, real accounts, third-party media, narration generation, or upload.
- Export remains 1920x1080 at 30 fps; duration is checked against recorded actions.
- Focus filtering prevents incidental hover/short-click camera bounces and
  conflicting overlapping moves; no continuous camera animation is added.
- Fixed-size output and one encode replace resizing/reencoding intermediate video.
- Bitrate is informational, not proof of readable text. Readability still needs
  inspection, and poor raw capture cannot be repaired by declaring 1080p output.
- Source audio remains muted in product B-roll to prevent competing voices.
- Gemini tests validate input-aware cache invalidation, multipart PCM preservation,
  malformed/truncated response rejection, and non-retryable errors.

## Remaining verification

- A listening A/B audition of current versus revised delivery with the same
  approved voice. Prompt changes alone do not prove more human speech.
- Real-site browser review for layout changes, overlays, text size, missing frames,
  and narration-to-visual alignment. The local fixture is not that test.
- An integrated episode: older one-off scripts can supply custom director prompts
  or use their own caches. They were not silently overridden.
- Mac ScreenCaptureKit permissions, mic synchronization, tray Stop, local editor,
  WebM export, transcription, backup/restore and app E2E remain future app work.
- No measured whole-episode speedup or guaranteed 30-minute production time is claimed.
