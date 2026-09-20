# Video-Gen-Model

Source snapshot of the Diffusion Daily / News Weekly video pipeline. Start with [SOURCE_PACKAGE.md](SOURCE_PACKAGE.md) for export scope, private configuration, and portability notes.

Quality-first automation for one entertaining, evidence-backed 8-12 minute technology and AI news show each week.
The system researches and verifies claims, captures source pages with Playwright, writes
evidence-linked scripts through OpenRouter, creates a single consistent narrator through
Magic Hour voice cloning, and renders with FFmpeg/Remotion. The local configuration auto-approves
private drafts; it does **not** upload to YouTube.

## Recording quality and local studio roadmap

Browser demos now use a single 1080p encode with restrained, action-led focus
moves; narration caching validates the script, voice, and returned audio.
The [local recording studio plan](research/screen_studio_local_first_plan.md)
describes the proposed Tauri 2 / React / TypeScript / FFmpeg / SQLite app. That Mac
desktop app is not implemented yet; cloud hosting is deliberately deferred.

For a no-key, local browser capture preview (requires Chrome and FFmpeg):

```powershell
python -m scripts.preview_screen_framing --output output/my_screen_preview
```

Use a fresh output directory. This records a clearly labeled test page, not a
real product. See [verification and exact test commands](research/recording_quality_verification.md)
for what was checked and what still requires listening or native-platform review.

## Current editorial profile

- New drafts use the `hermes-proof-first-v1` creative profile: authentic proof first, one
  information change every roughly five seconds, restrained motion, a narrow verdict, one
  continuous narrator, and word-timed captions. A 20-45 second proof cannot pass as silent,
  cannot hold a scene longer than 6.5 seconds, and must contain source evidence plus a
  verification or verdict state.
- Thumbnail planning is topic-aware. Launches, comparisons, workflows, failures, research,
  policy/business stories, and weekly roundups route to four materially different concept
  contracts. Every concept records evidence IDs, accepted source assets, the focal subject,
  forbidden implications, a 320x180 preview, and QC results. Algorithm v4 additionally detects
  represented companies and fails closed until every one resolves to an exact local official
  logo or documented mascot with provenance, hash, and visible placement. Blank and
  network-block pages are rejected before rendering.
- The flagship format is **NEWS WEEKLY**: a consequence-first cold open, a short branded intro,
  five to seven ranked stories, zero to two approved hands-on model tests, and a concise watch list.
- Cover consequential technology and AI news across commercial models, open source, creator tools,
  research, chips, business, policy, and security. Discovery includes r/StableDiffusion, r/comfyui,
  related communities, company/repository feeds, independent reporting, and newsletter feeds.
- Reddit and X posts are leads, not proof. Names, dates, numbers, benchmarks, and causal claims
  must link back to a primary source or an independently corroborated evidence record.
- Use real webpages, real product recordings, official demos, repositories, charts, and local
  deterministic graphics. Standalone AI-generated stills remain forbidden. Inside the fixed 15%
  motion allocation, half of eligible explanatory beats may use silent, text-free 1080p Seedance
  inserts (`MAGIC_HOUR_SEEDANCE_MOTION_SHARE=0.50`); exact type, logos, data, and citations stay local.
- Magic Hour is used for the configured cloned narrator and the bounded motion route above. Adjacent script beats are combined into
  longer performance blocks so the voice does not restart its cadence every few sentences. The narrator is mastered locally
  and must pass transcription, noise, clipping, silence, pacing, and voice-consistency checks
  before the pipeline can render or spend credits on later stages.
- Pacing and clarity may be informed by successful commentary channels, but scripts remain
  original and do not imitate another creator's wording, catchphrases, or identity.

## Architecture

```text
n8n schedules + approval forms
        |
        | authenticated JSON jobs only
        v
video-worker (FastAPI + SQLite)
  research -> evidence -> script -> source capture -> cloned voice -> captions -> Remotion/FFmpeg -> QC
        |
        v
durable /data/episodes artifacts and protected preview endpoints
```

The original `python -m pipeline.cli all` prototype remains available for inspecting old
runs. New production work should go through `pipeline.worker` and the workflows in
`n8n/`.

## News Weekly research and show flow

The source pool is refreshed throughout the week, but the Sunday show plan uses only the strongest
five to seven corroborated clusters:

1. **Primary evidence:** company announcements, repositories, changelogs, papers, and official demos.
2. **Independent reporting:** confirms consequences, disputes, business context, and outside reaction.
3. **Newsletters:** The Batch, Import AI, Latent Space, One Useful Thing, and Interconnects surface context and leads.
4. **Community signals:** Reddit and Hacker News indicate attention, friction, and reproducible workflows.

Recency, publisher breadth, primary evidence, independent confirmation, engagement, impact language,
and visual demonstrability contribute to a 0-100 cluster score. Newsletter/community-only clusters are
capped and cannot become confirmed narration. The planner also prevents one company or release category
from swallowing the entire episode.

Run a local weekly plan with:

```powershell
.\.venv\Scripts\python.exe -m scripts.create_news_weekly
```

Newsletter emails can be exported by n8n/Gmail into `data/newsletters/inbox/*.json`. Each item accepts
`title`, `url`, `publisher`, `published_at`, `body`, `author`, and `category`. Mailbox credentials never
enter the worker.

If the weekly plan selects a hands-on test, it creates a disabled `model_test_queue` entry. Bind an official
product URL and explicitly allow generation before capturing it:

```powershell
.\.venv\Scripts\python.exe -m scripts.configure_weekly_model_test `
  episode_YYYYMMDD_news_weekly story_id https://official-product.example/app `
  --prompt "A harmless prompt chosen for this comparison" --allow-generation
```

The worker stages `configure_model_test` and `run_model_tests` provide the same flow to n8n. Completed
1080p browser recordings are automatically assigned to the matching `model_test` beats; an unconfigured
test can never be narrated as a completed first-person result.

## What changed

- Open-source quality upgrades now include Trafilatura article extraction, Promptfoo script-prompt
  regression tests, caption alignment diagnostics, single-pass FFmpeg perceptual QC, and a
  C2PA-ready provenance sidecar. See `research/OPEN_SOURCE_UPGRADE_AUDIT.md` for adopted and deferred
  projects, integration locations, and measured follow-up experiments.
- Full source enrichment and 30-day rolling research instead of RSS snippets alone.
- Seven non-overlapping briefs with a curated mix of roundups, deep dives, tool tests,
  open-source spotlights, and trend explainers.
- OpenRouter JSON Schema responses using Claude Opus 4.7 for writing and GPT-5.4 as an
  independent evidence and visual verifier.
- A versioned `EpisodeProject` contract with source, claim, shot, rights, cost, QC, and
  artifact records.
- Duration-weighted 70-110 shot timelines with a fixed house mix: 55% matched,
  rights-cleared YouTube b-roll, 20% article/source evidence, 15% motion graphics,
  and 10% miscellaneous editorial utility. Motion is a declared fallback or
  chapter transition, never the automatic filler when footage is missing.
- OpenRouter-directed Chromium capture that selects observed headlines, product UI,
  charts, figures, hover states, and controlled scrolling shots. Navigation is limited
  to public HTTP(S) sources; private networks, logins, forms, and downloads are blocked.
- Remotion renders exact UI, text, comparisons, charts, annotations, and chapter cards as native
  1920x1080/30 fps masters with restrained surfaces and frame-deterministic easing. Magic Hour
  image-to-video is restricted to silent, text-free motion plates at 1080p; standalone generated
  stills remain forbidden in timelines and thumbnails.
- Speech-first scripting with an audience translation, 7-11 chapter proof outline,
  structured pauses, pronunciation guidance, oral-edit validation, fact checking, and an
  independent clarity/originality/visual-proof review before narration spend.
- Exact-script karaoke captions aligned to faster-whisper word timings.
- Background-music ducking, thumbnails, technical QC, a configurable credit safety gate, and
  recoverable targeted revisions.

## Local verification

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\playwright.exe install chromium
.\.venv\Scripts\python.exe -m pytest -q
cd remotion
npm install
npm run lint
```

Tests never call OpenRouter or Magic Hour and therefore spend no credits. Run
`scripts/run_voice_canary.py` separately when intentionally validating a new narrator.

## Browser-sourced visuals

The video worker—not OpenRouter itself—runs its own isolated Chromium browser. After a
source page loads, the worker exposes a bounded list of visible headings, figures,
product UI regions, media, and controls to the OpenRouter browser-director model. The
model may select only those observed candidate IDs and may request:

- clean viewport screenshots plus full-page provenance records;
- targeted element or hover-state screenshots; and
- up to three muted 1-8 second recordings per selected source: cinematic clean-page pan, hover,
  stable focus, safe tab/accordion reveal, or playback of an observed public HTML video.

The worker stores the final URL, page title, capture plan, timestamp, hashes, errors,
and asset paths in `EpisodeProject.captures`. Full-page images never enter the editorial
shot pool. Editorial screenshots are captured at native 1920x1080 resolution. Recordings use display-rate
cubic easing, bounded travel, settled fonts and images, hidden cursors, muted media, 30 fps
normalization, CRF 14 encoding, and stable framing without blur-producing frame blending. Article
scrolls are rendered from the clean full-page capture rather than a live compositor recording, so they
remain sharp and do not jitter. The worker rejects paywall/subscription modals and other large visual
obstructions instead of suppressing access controls; that source is omitted from the editorial asset
pool. Each accepted recording is checked for 1920x1080, 30 fps, adequate bitrate, duration, and a
clean DOM before and after motion. Challenge
pages such as Reddit's "blocked by network security" screen are detected before capture. The worker
tries a conservative old.reddit.com fallback and omits the source from the editorial pool if every
candidate is blocked. The planner cannot click
links, login/signup, forms, purchases, downloads, uploads, installs, publishing, deletion, or
consent controls. A deterministic scroll plan remains available if model planning fails. `MAX_CAPTURE_RECORDINGS`
defaults to six per episode. This uses the existing OpenRouter key through
`OPENROUTER_BROWSER_MODEL`; no additional browser API key is required.

## 30-minute draft profile

The default local profile targets a 10-minute review draft in 30 minutes without lowering the 1080p,
30 fps, source-capture, narration, or caption requirements. Remote Magic Hour motion jobs are submitted
first and polled/downloaded three at a time; independent local Remotion cards render in a two-job pool;
and generated-motion review runs three independent visual inspections at once. Tune only the bounded
`MAGIC_HOUR_MOTION_PARALLELISM`, `LOCAL_MOTION_RENDER_PARALLELISM`, and `VISUAL_QC_PARALLELISM` values
to the machine/API capacity. All work remains stage-hashed: a rejected clip reruns only that clip, not
the voice, captures, captions, thumbnail, or complete final render.

## Clean review gate

Before a draft can be reviewed, the package now includes one `review_readiness` result. It combines the
fact check, human-speech review, narration listenability, captions, thumbnail readability, source-rights
ledger, capture QC, and final delivery check. A failure names only the stage that needs revision, so a
weak line, clip, or thumbnail cannot trigger an unnecessary full regeneration.

At most six high-value screenshots per full episode receive one semantic emphasis target, and only
when the narration explicitly points to a visible fact, result, number, label, or control.
The browser model inspects the captured image and chooses an underline, outline, spotlight,
or compact callout around evidence that supports the current narration. Coordinates are
stored in `Shot.annotations`, and the renderer places the source in a branded evidence card
before easing the camera toward that region. If visual planning fails, the worker may frame a tight
element capture but leaves broad page screenshots unmarked instead of guessing at a target.
Short text targets use a 5-pixel red underline that draws from left to right. Small arrows are
reserved for precise controls or details that would otherwise be missed; they are not used on
headlines, paragraphs, large images, or obvious central subjects.

## Editorial and visual quality algorithm

1. Translate the evidence into what changed, why the viewer should care, terms needing
   plain-English definitions, concrete examples, limitations, and unknowns.
2. Build a 7-11 chapter argument where each section answers a listener question and earns
   a payoff with proof. A source, demo, test, or example appears at least every 90 seconds.
3. Draft each researched chapter independently from its allowed claim IDs, then stitch the chapter
   drafts into 1,250-1,800 conversational words in 24-30 spoken segments with one consistent voice.
   The hidden story logic is state, explain, concrete example, implication; those labels never appear
   in narration. Hooks use truthful result-first, relatable-friction, or earned-curiosity openings.
   Humor is optional and must grow from documented friction instead of being inserted by a comedy
   prompt. Observation and interpretation stay separate; first-hand testing is never implied without evidence.
4. Store emphasis, pronunciation, pacing, and 250-2,500 ms pauses as delivery metadata.
   Silence is inserted into narration audio, not printed into captions.
5. GPT-5.4 independently checks factual support, clarity, natural speech, density,
   continuity, originality, and visual proof. A major written-not-spoken issue fails the
   script; short episodes receive no relaxed threshold. Failing scripts are rewritten before TTS.
   Before that review, a separate fact-locked spoken edit rewrites narration and delivery while
   preserving every beat ID, claim link, source link, name, number, and factual boundary.
6. Source recordings and screenshots carry the factual load. Native 1080p Remotion graphics
   handle exact UI/text, evidence underlines, arrows, comparisons, metrics, and transitions.
   Seedance is used only for selected mechanism, transformation, comparison-metaphor, and timeline
   beats, with generated text/audio disabled and automated temporal/artifact QC before acceptance.
7. Narration is mastered to -16 LUFS with a -1.5 dB true-peak ceiling, then back-transcribed.
   The job fails closed for low intelligibility, clipping, static-like high-frequency noise,
   long unexplained silence, implausible speaking rate, or narrator-reference mismatch.
8. Four thumbnails use real source captures or accepted motion frames with local 3-5 word
   overlays. Official identity assets are composited as story subjects rather than tiny badges;
   missing, generated, or unplaced company marks fail the stage. QC rejects generic-hype copy,
   low contrast, near-duplicates, and unreadable compositions, with an 86/100 quality floor.

## Fast 1080p production profile

Every active video path has one exact delivery contract: 1920x1080 at 30 fps. Magic Hour
routes are forced to 1080p even if a stale environment value requests 4K, Chromium captures
at native 1080p, Remotion rasterizes at native 1080p, and FFmpeg never builds an oversized
intermediate. This removes 75% of the pixels previously rendered in a 4K frame without
downscaling the final output.

Independent work is bounded rather than serialized: research enrichment uses eight workers,
browser capture uses two, and timeline shots use three. FFmpeg gives each concurrent job two
threads and uses the `fast` x264 preset at CRF 18 for intermediates and CRF 17 for the final,
so speed comes from less unnecessary computation and safe parallelism rather than reduced
resolution. Frame blending is disabled to keep text and browser footage crisp. Stage hashes
include this render profile, so old 4K caches are ignored while completed 1080p assets remain
resumable.

The researched format playbooks, capture policy, motion vocabulary, and source links are in
[`CHANNEL_RESEARCH_AND_MOTION_SYSTEM.md`](CHANNEL_RESEARCH_AND_MOTION_SYSTEM.md).

## One-time production setup

1. Copy `.env.worker.example` to `.env.worker` and fill in the OpenRouter key, Magic Hour
   key, a randomly generated worker token of at least 32 characters, and the HTTPS
   `WORKER_PUBLIC_BASE_URL` used by reviewers. Reverse-proxy only the worker's artifact
   route publicly; job, slate, and package metadata routes remain bearer-protected.
2. Put the approved voice sample in `assets/voices/` and set `VOICE_SAMPLE` plus a stable
   `VOICE_PROFILE_ID` in `.env.worker`. The current profile uses
   `assets/voices/channel_narrator_approved_english_clean.wav`. This is the uninterrupted
   center speech isolated from the user-approved narrator WAV. Music-like lead-in and
   transition audio are excluded; every generated chunk must match its English script.
3. When permission has been granted but the form will be filed later, set
   `VOICE_CONSENT_ATTESTED=true`. The worker records the sample SHA-256 and marks the
   documentation pending. A completed `assets/voice_consent.txt` supersedes the attestation.
4. Add several pre-cleared music files to `assets/music/`. The render remains valid but
   intentionally music-free when this directory is empty.
5. Confirm the Docker network used by n8n. `docker-compose.worker.yml` expects
   `n8n_default`; change the external network name if the Hostinger stack uses another.
6. Build and start the isolated worker:

   ```bash
   docker compose -f docker-compose.worker.yml up -d --build
   docker compose -f docker-compose.worker.yml ps
   curl http://127.0.0.1:8080/health
   ```

## Authenticated product demos

Authenticated model testing is isolated from the public source crawler. The automation never types,
receives, or stores a Google password or 2FA code. Create one local Chrome profile and sign in manually:

```powershell
.\.venv\Scripts\python.exe -m scripts.setup_google_demo_profile --profile google_manual
```

Chrome opens visibly. Complete sign-in yourself and press Enter in the terminal. The resulting cookies
remain under `data/browser_profiles/google_manual/` and must never be uploaded or exposed through n8n. The sign-in window is ordinary Chrome—not a Playwright-controlled login—so Google credentials and 2FA never pass through the automation. Close Chrome completely before continuing so the authenticated session is saved.

Copy `configs/demo_specs/google_ai_studio.example.json`, adjust the harmless test prompt and goal, then run:

```powershell
.\.venv\Scripts\python.exe -m scripts.generate_product_demo configs\demo_specs\google_ai_studio.example.json
```

The AI sees only bounded visible controls and creates a clean action plan before recording. The final
pass replays that plan with a visible Bezier cursor, one precise focus ring at the active control, settled
holds, smooth bounded scrolling, 1920x1080 capture, action screenshots, and an action ledger. It then
creates a separate editorial master with a restrained 8.5% push-in only while a recorded control or result
is being discussed; there is no permanent zoom, fake cursor movement, or decorative arrow spam. Both the
normalized and editorial masters must pass 1080p/30fps/bitrate QC, and any access/subscription modal causes
the capture to be rejected. A Generate/Create/Run click is accepted
only when that job sets `allow_generation=true`; it may spend credits on the tested product. Password
fields, 2FA, billing, purchases, account/security changes, permissions, publishing, uploads, downloads,
deletion, and external navigation are always rejected. n8n can submit the same spec through worker stage
`generate_browser_demo` after the profile is ready.

## Licensed YouTube excerpts

The worker can ingest a precise YouTube section only through the `ingest_licensed_clip` stage. It uses
yt-dlp's timestamped-section support, then performs a frame-accurate FFmpeg normalization to 1080p/30fps.
Source audio is removed by default. Copy `configs/licensed_clip.example.json`, select one or more existing
shot IDs, and submit that JSON as the job payload.

The stage accepts only channel-owned, written-permission, verified Creative Commons, or documented
public-domain material. Written proof files must live under `assets/rights/`. Standard YouTube-licensed
videos are rejected, as are clips longer than 45 seconds. Every accepted output retains the source URL,
timestamps, uploader, license, attribution, proof hash, output hash, and final QC in a rights ledger.
Publication still requires human rights review.

### Podcast and release-video clip format

After ingesting an approved excerpt, submit worker stage `build_clip_segment` with
`configs/clip_segment.example.json`. It builds an original 36–60 second sequence: hook, full-screen
source excerpt, plain-English context, claim-versus-evidence check, a second source detail, and a concise
takeaway. Source footage is muted under the episode narration, remains visibly attributed, and cannot be
used unless its asset hash, rights ledger, and media QC all match. Set `render` to `false` to review the
JSON motion plan before rendering, or `true` for a 1080p preview.

## n8n setup

Import these files in order:

1. `n8n/news_weekly_research.json` - Sunday source refresh and ranked News Weekly plan.
2. `n8n/ai_news_script_generator.json` - legacy six-hour research refresh and seven-episode slate.
3. `n8n/weekly_slate_approval.json` - legacy weekly batch approval form.
4. `n8n/daily_production.json` - production and polling.
5. `n8n/review_and_revision.json` - final approval or targeted revision form.
6. `n8n/credit_approval.json` - explicit approval when an episode pauses above its
   configured credit ceiling (50,000 in the local setup).
7. `n8n/google_sheets_sync.json` - 15-minute metadata sync to the Google Sheets
   operations ledger.
8. `n8n/broll_review_and_insert.json` - human rights/timestamp approval for one
   discovered YouTube candidate, followed by a cached episode rerender.

### Automated scene-level b-roll

Full episode production now reserves 55% of runtime for individual footage slots
immediately after the storyboard is created. OpenAI turns each slot's active
narration beat into a concise visual search query, and the YouTube Data API returns
three high-definition candidates for that exact slot. The worker saves both
`broll_candidates.json` and a
review-friendly `broll_review.csv`. Every candidate retains its source URL,
thumbnail, target scene and shot IDs, channel, license metadata, ranking reason,
and suggested timestamps when public captions are available.

Discovery is deliberately metadata-only: it does not download video. Import
`n8n/broll_review_and_insert.json` to choose the exact candidate and timestamp
range, record the rights basis, mute the source audio, insert the normalized
1080p excerpt into its assigned shots, and rerender from cached stages. The
existing rights gate accepts only owned, permissioned, verified Creative Commons,
or documented public-domain footage. Publishing remains disabled.

Production stops at `broll_review_required` until every reserved footage slot has
an approved timestamped excerpt, at least a 45/100 sentence-to-picture alignment
score, muted source audio, and a unique asset fingerprint. It does not replace an
unfilled slot with a motion graphic or an article recording. Final QC measures
screen time rather than shot count and rejects a mix outside two percentage points
of 55/20/15/10.

For a standalone discovery job, submit worker stage `discover_broll` with
`configs/discover_broll.example.json`. Put `OPENAI_API_KEY` and
`YOUTUBE_API_KEY` in the private `.env.worker` file; never place either key in an
n8n export.

Create a Header Auth credential named **Video Worker API**:

- Header: `Authorization`
- Value: `Bearer <the same WORKER_API_TOKEN from .env.worker>`

Because the current n8n instance runs on Hostinger while the worker runs on the laptop,
replace `https://WORKER_BASE_URL_REQUIRED.invalid` in all HTTP Request nodes with one
stable HTTPS tunnel or reverse-proxy URL that reaches local port 8080. `localhost` and
`127.0.0.1` do not work from the Hostinger n8n container. This installation does not
include paid n8n Variables, so the URL is deliberately explicit in the exported nodes.

Open each HTTP Request node and select that credential. In the Google Sheets sync,
select a Google Sheets OAuth2 credential on all six `Sync ...` nodes. The target is
[AI Media Channel Operations Ledger](https://docs.google.com/spreadsheets/d/REPLACE_WITH_YOUR_SPREADSHEET_ID/edit).
Publish the two form workflows, test everything manually, then activate the schedules.
The exported JSON contains no API keys.

## Where data is stored

- `/data/episodes` on the video worker is the durable source of truth for complete
  `EpisodeProject` documents, downloaded source media, narration, generated assets,
  captions, thumbnails, manifests, QC reports, and rendered videos.
- `/data/jobs.sqlite3` stores resumable job state, hashes, progress, errors, and credit
  accounting. n8n separately retains its normal execution history.
- Google Sheets is a searchable metadata mirror. It stores the activity log, episode
  status, weekly slate, approvals/revisions, source and rights links, job status, costs,
  QC results, and protected review URLs. It deliberately does not store binary media.
- The worker's authenticated `GET /ledger` endpoint normalizes these records; the sync
  workflow upserts them every 15 minutes, so retries do not create duplicate rows.

## Safe live rollout

Do not activate the daily schedule first.

1. Run `Refresh Source Pool` manually.
2. Run `Create Seven-Episode Slate`, open the weekly form with its returned slate ID,
   and inspect all seven briefs on the second form page.
3. Submit the weekly approval form for one episode only.
4. Start a 60-second canary against that episode:

   ```bash
   curl -X POST http://127.0.0.1:8080/jobs \
     -H "Authorization: Bearer $WORKER_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"stage":"produce_canary","payload":{"episode_id":"episode_YYYYMMDD_01"}}'
   ```

5. Poll `GET /jobs/{job_id}`. Review voice, screenshots, local motion graphics, captions,
   music, thumbnail, and QC output.
6. Produce one complete episode and approve it before activating the seven-day schedule.

## Worker API

- `POST /jobs` starts `refresh_sources`, `research_slate`, `review_slate`,
  `produce_episode`, `produce_next`, `produce_canary`, `review_final`, or
  `approve_credits`. It can also start isolated `generate_browser_demo` jobs with a
  validated `DemoSpec` after the named local Chrome profile is ready.
- `GET /jobs/{job_id}` returns status, progress, result, cost, and error information.
- `POST /jobs` with stage `run_fidelity_loop` snapshots provider budgets before any
  research or paid call, then builds or resumes the 30+30 channel reference corpus,
  scores the private pilot, and repairs only
  its lowest fidelity dimension. Supply the dashboard-confirmed
  `magic_hour_starting_balance_credits`; supply `openrouter_starting_balance_usd` only
  when the current OpenRouter key cannot report its remaining limit.
- `POST /jobs` with stage `build_fidelity_reference_profile` performs only the free,
  read-only 30+30 public-channel corpus and pattern-library stages. It never creates a
  provider budget or calls OpenRouter/Magic Hour, so research can finish while paid
  generation remains fail-closed.
- `GET /fidelity-runs/{run_id}` returns the current 12-dimension score matrix, exact
  provider usage, milestones, remaining gaps, finishing estimate, and artifact paths.
- `POST /jobs/{job_id}/cancel` requests safe cancellation.
- `GET /slates/{slate_id}` returns the seven-brief review payload.
- `GET /packages/{episode_id}` returns QC, costs, and fresh review URLs.
- `GET /ledger` returns the normalized metadata snapshot used by Google Sheets.
- `GET /artifacts/{episode_id}/{name}` returns a single-file artifact with bearer auth
  or a 24-hour HMAC-signed review link. The MP4, four thumbnails, captions, and complete
  `EpisodeProject` preview manifest are each addressable.
- `GET /health` is intentionally unauthenticated for container health checks.

All non-artifact production endpoints require the worker bearer token. Job creation is
idempotent, and jobs that were running when the service restarted are safely re-queued.
Canceled jobs stop at the next paid-stage boundary. Credit-limit breaches enter a
distinct `paused` state and require the credit approval form before a resumable rerun.

The fidelity loop never publishes. It stores detailed checkpoints under
`data/fidelity_runs/<run_id>` and writes only four durable headings to `progress.md`:
pattern library, first scored script, first scored storyboard, and first verified episode.
Reference transcript metrics and analysis-only timecoded frame strips are cached by video ID
and content hash; complete reference videos are never retained. Integrated review uses those
real reference strips and a sampled candidate strip in hash-randomized anonymous packets.

## Review and publishing policy

- Magic Hour affiliation is disclosed when relevant, but it receives no automatic favorable
  editorial treatment and is covered only when independently newsworthy.
- Every sourced visual carries provenance and a rights note; a human must still confirm
  rights before publication.
- The local configuration accepts the user's permission attestation and records the exact
  voice-sample hash. Written documentation can be added later without blocking private drafts.
- Private drafts may be auto-approved when `AUTO_APPROVE_PRIVATE_DRAFTS=true`; publishing
  remains disabled and is not performed by this system.
- Realistic generated media must be disclosed when eventually uploading.
- Final approval changes project status only. There is deliberately no YouTube upload
  node in this release.
