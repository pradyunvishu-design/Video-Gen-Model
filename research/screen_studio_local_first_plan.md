# Local recording studio: design proposal and pipeline improvements

Status: **planning for the desktop application; targeted existing-pipeline fixes implemented.**
No Tauri app, Mac capture backend, cloud worker, or hosted service has been built in this pass.

## What makes the channel better

Reuse the project's 18-video AI Search opening study rather than buying another
analysis of the same material. The transferable lesson is a specific promise,
visible proof, plain explanation, practical consequence, and an honest limitation.
The goal is an original useful channel, not another presenter's voice or scripts.
The public reference is [AI Search, @theAIsearch](https://www.youtube.com/@theAIsearch).
Its public page was checked, but no fresh video/audio analysis is claimed here.

For a demo, give each clip one viewer question and a visible answer. Plan the
click and its result before recording. Keep the result on screen long enough to
read. Cut setup and waiting, not the meaningful outcome. Do not use camera motion
to conceal a static, irrelevant, or failed capture.

| Spoken beat | Screen treatment | Avoid |
| --- | --- | --- |
| Here is the feature | Full interface, then one click | Zooming at every hover |
| This setting changes the output | Brief target focus, then show the result | Moving away before the result appears |
| The announcement makes this claim | Pre-positioned exact evidence line; restrained annotation | Scrolling a whole article to fill time |
| Compare two outputs | Locked side-by-side view with readable labels | Moving both examples while explaining |
| Three steps or a mechanism | Original explanatory graphic with timed reveals | Decorative diagrams without a teaching purpose |

## Implemented in the existing Python pipeline

- Browser normalization now preserves real frames rather than applying optical
  flow to text and cursors. This removes an expensive processing stage, but does
  not manufacture missing capture frames or guarantee a particular speedup.
- Fixed-output 1920x1080 framing replaces per-frame scale-size reconfiguration.
  Focus moves ease in/out, hold briefly, skip incidental hovers, merge nearby
  actions, and reject conflicting overlapping moves. Maximum zoom is 12%.
- Scroll actions start from the current position rather than snapping to a
  requested start. Focus events use measured action time rather than fixed delays.
- Product recordings finish the current action and hold the result, then trim
  away navigation and encode once. The requested duration is a soft action budget,
  not permission to cut an interaction in half. Recorded time is retained in metadata.
- Clip-duration QC now rejects material truncation. Resolution/rate checks remain.
- Narration caching validates text, delivery prompt, model, voice, and audio hash.
  Invalid audio formats, truncated responses, and permanent request errors no
  longer silently produce/reuse plausible-looking WAV files.
- Default delivery asks for connected thought groups, sparse meaningful emphasis,
  complete sentence endings, and no background sound. Explicit caller-selected
  voices and custom episode prompts are preserved.

These fixes affect new runs that use the relevant modules. They do not rewrite
existing finished videos. Historical one-off scripts may bypass the shared client
or skip existing files; migrate those explicitly before re-producing an episode.
Speech still requires a listening audition; valid PCM is not proof of naturalness.
The current Playwright action clock is aligned from measured duration, not native
frame timestamps. Do not describe it as frame-accurate cursor tracking.

## Proposed desktop app: requested stack only

Keep this as a small new app in an empty directory, not a rewrite of the working
Python production system. Use **Tauri 2, React, TypeScript, FFmpeg, and SQLite**.
The app exports a local media bundle that the existing pipeline can ingest.

- React/TypeScript: source selection, recording status, editor timeline, preview,
  crop handles, focus markers, text callouts, export progress, and recovery states.
- Tauri/Rust: narrowly scoped filesystem/database commands, recorder lifecycle,
  tray Stop action, OS permissions, and FFmpeg subprocess supervision.
- macOS capture adapter: ScreenCaptureKit through a native bridge; preserve raw
  screen/video and optional microphone tracks separately. Tauri's webview is not
  itself a complete screen/window/region recorder. Verify the microphone backend
  against the chosen minimum macOS version on a real Mac.
- SQLite: projects, source metadata, edit revisions, export jobs, errors, and hashes.
  Do not store video blobs in SQLite.
- FFmpeg: deterministic framing, crop, trim, annotation composition, audio mix,
  poster extraction, H.264 MP4 and VP9/Opus WebM exports.
- Local transcription: reuse the existing local transcription capability through
  a bounded worker interface. No paid service or account required. Record model
  availability and offer a recoverable missing-model state, never fake a transcript.

Primary documentation: [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/),
[Tauri tray API](https://v2.tauri.app/learn/system-tray/),
[Apple ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit).
Implementation must verify supported APIs and minimum OS versions before pinning.

## Recording and non-destructive edit contract

1. Select screen, window, or bounded region. Preview what is included. Mic is
   opt-in; system audio is off by default to prevent background voices.
2. Check screen/microphone permissions, disk space, encoder availability, and
   selected source existence. Never start a timer if capture failed to start.
3. Show an always-visible timer with Pause/Stop and a tray Stop action. Exclude the
   recording HUD from capture. Explain permission denial and provide a retry path.
4. Save immutable source media plus cursor/click events against the same monotonic
   media clock. Account for display scaling, capture origin, pauses, and region bounds.
5. Store trim in/out, crop rectangle, padding, focus moves, cursor highlighting,
   and text callouts as versioned edit decisions. Undo edits without recapturing.
6. Automatically focus intentional click clusters; use dead zones, smooth easing,
   reading-time holds, and a return to overview. A cursor moving randomly is not
   a camera target. Do not zoom where the source cannot support readable text.
7. Export locally with resumable jobs. Preserve the original on cancel/failure.
   Verify decoding, duration, audio endpoints, resolution, and missing frames.
8. Place `video.mp4` or `video.webm`, `poster.jpg`, `transcript.vtt`, `summary.md`,
   and `project.json` beside each other. Summary is transcript-grounded; a silent
   recording gets an explicit no-speech note, not invented narration.
9. Offer Copy file path and Reveal in folder. There is no mandatory upload.

## Local storage, security, and backup

Use the OS app-data directory for SQLite and project indexes, with a user-selected
local recordings directory. Resolve file paths server-side; restrict commands to
owned projects. Use UUID project IDs and sanitized display-name slugs; never pass
user text through a shell. Validate timestamps, geometry, output presets, and
callout lengths. Write exports to temporary siblings, then atomically finalize.

Local operation should need no secrets. Optional integrations read `.env`; commit
only `.env.example`. Keep credentials out of UI state, logs, project bundles, and
transcripts. No accounts, telemetry, analytics, billing, enterprise workspaces,
SSO, viewer tracking, or hosted control plane.

Backup: stop capture/exports, use SQLite backup or checkpoint/close WAL safely,
then copy database plus project directories. Restore into an empty data location
and validate source hashes. Do not copy only the database and lose the media.

## Build order and acceptance

1. Capture spine on a real Mac: screen/window/region, optional mic, timer/tray Stop,
   interruptions and permission denial. No editor polish before reliable recording.
2. Non-destructive editor and deterministic transform tests: validate boundaries,
   crop limits, cursor mapping, easing continuity, and complete audio endpoints.
3. Local export queue, poster/transcript/summary, copy/reveal, cancel/resume.
4. One real Mac E2E: launch, select test window, click/scroll, stop, trim, export,
   reopen output and verify picture/audio/sidecars. Mocked APIs cannot pass this gate.
5. Human review at native 1080p: readable UI, no popup/private content, no jerky
   zoom, understandable action, complete narration, restrained typography.

Target first-run command after documented platform prerequisites: `npm run dev`.
The future bootstrap must check Rust/Xcode/FFmpeg, install locked frontend
dependencies if absent, and give an actionable missing-prerequisite message.
This command is a design requirement, **not a working command in this repository yet**.
Cloud deployment is deferred. Desktop recording requires an interactive OS
session; it must not be treated as an ordinary headless container job.

## Verification in this pass

The core transformation has focused unit tests and a real local FFmpeg encode /
decode happy path. This is **not** the future Mac recorder E2E test. No cloud,
capture permissions, tray, Mac UI, or live Gemini voice audition was tested here.
Exact commands and final outcomes are recorded in `research/recording_quality_verification.md`.
