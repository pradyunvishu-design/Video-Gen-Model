# Video Composer: Magic Hour integration preview

## Product direction

Offer **Video Composer** as a selectable creation option inside Magic Hour. This
is an editorial/composition workflow, not a newly trained diffusion model. It
writes a source-backed script, searches for matching existing footage, plans
original explanatory motion, and hands approved shots to the existing video
pipeline. Do not market it as a new Kling/Seedance-style foundation model.

The customer's latest choice is **system searches for clips**. Search is the
default, not an uploads-only workflow. Provided-only and hybrid modes remain
available. Search does not grant reuse rights or prove that the visible action
matches the narration. No automatic YouTube download is part of discovery.

## Intended customer experience

1. Select explainer, tutorial, comparison, documentary, or news; alternatively
   give a custom brief using the supported nonfiction formats.
2. Describe the topic, audience, intended takeaway, tone, and duration. Attach
   research or let a future research adapter build an evidence bundle.
3. Review the proposed brief and source-backed script before production.
4. The system searches YouTube per narration beat and presents up to three
   candidates with source links. Review the actual range and reuse permission.
5. Mix approved existing/generated footage with purposeful comparison, timeline,
   process, or list graphics. Missing footage remains an explicit gap.
6. Align the chosen narrator, review the edit, render, and export. No publishing.

The first four operations and a Shot-contract compiler are implemented here.
The full customer-facing flow is a product roadmap, not a claim of deployment.

## Implemented contract

Model ID: `editorial-composer-v1`; status: `integration_preview`.
1920x1080 only; request duration 60–1200 seconds. The current discovery adapter
supports up to 70 script beats; longer scripts need batching before that limit
is lifted. One consistent approved narrator remains the downstream requirement.

All routes use the existing worker bearer authorization. The trusted Magic Hour
backend assigns `X-Customer-ID` from its authenticated session. Never accept this
header directly from an untrusted browser, put the worker token in frontend code,
or expose generic worker routes through the customer gateway.

| Route | Purpose |
| --- | --- |
| `GET /video-models` | Model descriptor and available presets |
| `POST /composition-projects` | Create scoped brief and evidence records |
| `GET /composition-projects/{id}` | State, required next action, hashes, edit plan |
| `GET /composition-projects/{id}/script` | Script and linked claims/sources for review |
| `GET /composition-projects/{id}/clips` | Candidate links/metadata without internal paths |
| `POST /composition-projects/{id}/approvals` | Approve exact brief, script, or plan hash |
| `POST /composition-projects/{id}/asset-alignments` | Bind a reviewed range and claims to registered asset bytes |
| `POST /composition-projects/{id}/jobs` | Enqueue one operation in the existing SQLite queue |
| `GET /composition-projects/{id}/jobs/{job_id}` | Owner-scoped, redacted progress |
| `POST /composition-projects/{id}/jobs/{job_id}/cancel` | Cooperative cancellation |

Example project body (replace example research with real supporting material):

```json
{
  "model": "editorial-composer-v1",
  "mode": "preset",
  "preset": "explainer",
  "topic": "How telescopes collect light",
  "instructions": "Explain the mechanism with demonstrations and one useful comparison.",
  "niche": "astronomy",
  "audience": "curious beginners",
  "viewer_payoff": "Understand what a telescope changes and what it cannot change",
  "target_seconds": 120,
  "footage_mode": "search",
  "sources": [{
    "title": "Customer-supplied research",
    "url": "https://example.org/research",
    "text": "Replace this example with the actual source text supporting the proposed claims.",
    "facts": ["Replace this with a claim supported by that text."]
  }]
}
```

Sources may be omitted at creation, but production then stops at `add_sources`.
There is no automatic factual research acquisition or evidence-edit endpoint in
this preview; the trusted host must populate/recreate the brief. Customer source
text is untrusted evidence, never prompt instructions or automatically verified
official material.

Approve using `{"stage":"brief","expected_hash":"<returned hash>"}`.
Enqueue using `{"stage":"discover_clips","idempotency_key":"search-v1"}`.
Supported operations are `write_script`, `discover_clips`, `plan_edit`, and
`compile_edit`. Script writing additionally requires
`"paid_generation_approved": true` and current brief approval. Script approval
requires an independent passing fact review bound to the actual script hash.

### What automatic search does

Reuses `youtube_broll.py` and the configured YouTube Data API key. Queries now
support general demonstrations/documentary footage rather than appending AI
launch/keynote language to every topic. Evergreen projects omit the date filter;
current projects use 90 days. Existing relevance, reputable/viral, and duplicate
candidate filters remain active. Metadata ranking is candidate triage, not visual
verification. Small authoritative channels can still require manual sourcing.

The composer disables the additional paid query-planning LLM and caption fetches.
Unknown timestamps remain unknown, not fabricated. YouTube quota still applies.
An interrupted search may repeat quota-consuming requests; per-scene durable
search caching is not implemented. Completed worker jobs return their stored
status on retries with the same key.

### Reviewed edit and renderer handoff

Use the existing approved licensed-clip ingestion path to register local media,
content hashes, QC status, attribution, and reuse rights. An alignment submission
does not grant rights. The host must validate license terms/permission evidence;
this adapter consumes that ledger rather than performing legal clearance.

Only reviewed claim-matched video assets can fill footage slots. The same media
hash can appear at most twice, including aliases with different asset IDs.
Motion is explanation-triggered, capped by the configured time fraction, and
does not silently replace every missing clip. Cameras stay locked and edits use
cuts. Source audio is intended to be muted by the downstream renderer.

The trusted narration adapter must supply contiguous `narration.beat_timings`
with `beat_id`, `start_seconds`, and `end_seconds`. Without alignment, timing is
explicitly estimated and compilation is blocked. These records must come from
the actual audio; this preview does not itself generate/verify that alignment.

`compile_edit` checks asset containment and SHA-256, then emits existing `Shot`
objects using motion-template names supported by the renderer. It does **not**
produce an MP4, authorize a new generation service, or publish. Downstream media
probing must still verify source duration, dimensions, decodability, audio
identity, motion payload readability, and final render quality. The current
preview does not validate clip end times against decoded media duration.

## Reliability and deployment boundaries

- Semantic operation hashes exclude status, response caches, and output fields,
  allowing checkpoints to survive retries without accepting changed inputs.
- Writing reuses the existing durable validated-response cache. A crash after a
  provider accepts a request but before a response is saved can still incur an
  uncertain charge; this is not a guarantee of exactly-once billing.
- After a single-worker restart, retry the same job request/key to schedule a
  recovered queued job. There is no automatic startup queue drain in this change.
- Cancellation is checked before writing calls and between search scenes;
  in-flight HTTP calls are not forcibly aborted.
- Mutations use a process-local lock. Run this preview with **one server process**;
  it is not distributed locking or a production multi-tenant scheduler.
- The internal worker retains administrative endpoints. A real product gateway
  must allowlist only scoped customer routes, enforce sessions, quotas, paid-spend
  caps, request-size limits, retention, and artifact access. An approval boolean
  alone is not billing authorization for a public SaaS product.
- No live Magic Hour UI integration, hosting, customer upload adapter, automatic
  license acquisition, final rendering operation, or tenant billing is shipped.
- No new paid calls or external downloads are needed to run the tests.

## Next integration milestones

1. Connect the real Magic Hour application session, model picker, brief form, and
   review screens; add per-customer spending caps and source editing.
2. Add licensed-footage providers and/or an existing entitlement catalog for
   genuinely unattended sourcing; retain YouTube as a research candidate source.
3. Connect approved ingestion and narration alignment to a strict render job,
   including media-probe checks and deterministic motion payload validation.
4. Exercise astronomy, cooking, history, software tutorials, and product
   comparisons with held-out scripts and human watchability reviews. Do not
   claim universal niche quality from structural tests.
5. Validate one real end-to-end customer render, then load-test concurrency,
   worker recovery, budgets, and tenant isolation before release.

## Verification

Focused contracts, API isolation, search routing, approvals, stale asset detection,
repetition limits, cancellation, checkpoint hashes, and queue recovery are tested
in `tests/test_video_composer.py`. These tests mock providers and use fixture
media bytes; they prove neither visual quality nor a rendered video.

Run from the repository root on Windows with the installed Python 3.12 runtime:

```powershell
$composerTemp = Join-Path $env:TEMP ('composer-tests-' + [guid]::NewGuid().ToString('N'))
py -3.12 -m pytest tests/test_video_composer.py tests/test_youtube_broll.py tests/test_worker_api.py tests/test_general_scripting.py -q -p no:cacheprovider --basetemp=$composerTemp
```
