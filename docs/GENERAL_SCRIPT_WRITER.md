# General-channel scriptwriting v1

## Product direction

A channel is not a niche-specific prompt. Separate **subject**, **audience**,
**episode format**, and **spoken voice**. A science comparison should use the same
comparison reasoning as a photography comparison, but different evidence,
vocabulary, examples and viewer decisions. Keep narrator identity separate from
writing style. This release changes scriptwriting only, not discovery, visuals,
voices, uploading or publishing.

The design was brainstormed and independently reviewed with one Astra helper.
No model was fine-tuned. This is an explicit, testable writing workflow.

## Implemented writer's room

1. Validate an approved, episode-scoped brief with full source text and claim IDs.
2. Resolve one typed writing contract. Reject unknown formats and empty profiles.
3. Translate the evidence for the audience: familiar knowledge, necessary terms,
   examples, limitations and an achievable payoff.
4. Develop four source-supported openings using at least three mechanisms. Select
   for evidence fit and viewer benefit, not maximum shock.
5. Outline listener questions and payoffs. Budget words for the requested duration.
6. Draft each section within its assigned claim scope.
7. Unify the sections into one speaker; remove duplicate setup and conclusions.
8. Perform a fact-locked spoken edit without changing beat IDs or evidence mapping.
9. Independently review factual support and spoken quality using a different
   configured model. Review packets exclude the generator's outline and past scores.
10. Revise on specific feedback, with bounded retries. Hold high-risk topics for
    expert review rather than buying rewrites that cannot resolve that hold.

Successful responses are cached by contract, evidence, prompt, schema and model.
Changed source text, evidence classification, audience, format or voice invalidates
the plan. Failed semantic responses receive one corrective attempt and are not
cached as successful. Script-only runs checkpoint completed responses atomically.
A crash after a provider charges but before its response is checkpointed can still
require reconciliation; this is not a claim of exactly-once provider billing.

## Formats and quality targets

| Format | What earns the viewer's time | What to reject |
| --- | --- | --- |
| Explainer | Concrete puzzle → mechanism → example → mental model | Analogy presented as literal fact |
| Tutorial | Outcome → prerequisites → steps → checkpoints → recovery | Missing prerequisites or invented testing |
| Comparison | Decision → shared criteria → evidence → tradeoffs | Fabricated scores or unconditional winner |
| History | Question → chronology → turning points → interpretations | Invented dialogue, motives, or causal certainty |
| Science | Phenomenon → model → evidence → uncertainty | Correlation described as causation |
| Case study | Decision → incentives → actions → outcomes → alternative causes | Success mythology and invented metrics |
| Documentary | Documented stakes → sequence → turning point → resolution | Reconstruction presented as witnessed footage |
| News | Verified change → context → consequence → limits | Manufactured urgency or unverified reporting |

Clarity, natural speech, promise delivery and voice consistency require 9/10.
The other existing review dimensions require 8/10. Major findings block approval.
Legacy rhythm heuristics remain diagnostics, not universal genre laws. A single
contraction count cannot prove whether a history documentary sounds natural.

The factual reviewer checks original sources as well as claims. It can detect a
high-risk topic even if the caller labels it general. This is an additional gate,
not a substitute for qualified review. General v1 disallows personal testing and
experience claims; a `model_test` label is not proof that someone ran a test.

## Existing-pipeline integration

Add an optional top-level `script_profile` to an existing `EpisodeProject`:

```json
{
  "version": "1.0",
  "niche": "astronomy",
  "subject": "Why the Moon changes shape",
  "audience": "Curious adults without a physics background",
  "viewer_payoff": "Explain the phases using one simple spatial model",
  "format": "science",
  "knowledge_level": "beginner",
  "timeliness": "evergreen",
  "voice": "conversational",
  "humor": "light",
  "words_per_minute": 145,
  "risk_domain": "general"
}
```

This is a profile snippet, not a complete runnable source bundle. Supply the
approved brief, sources with full text, and claims. Keep the legacy
`brief.episode_format` (usually `deep_dive`) for existing production compatibility;
`script_profile.format` controls the new writer. No profile means the old news
behavior remains unchanged. The older `pipeline.cli` / `scriptgen.py` one-shot
writer is not generalized by this change.

The existing `editorial.build_editorial_plan`, `draft_researched_sections`,
`write_script`, `humanize_script`, `verify_script`, `review_script_quality` and
`write_verified_script` entrypoints route profile-enabled projects automatically.
The production script hash includes the complete writing input fingerprint.
Legacy manual approvals cannot silently bypass general-script review.

### Script-only operation

Validate and prepare a project without spending credits:

```powershell
py -3.12 -m pipeline.script_only approved_episode.json --output output/general_script_trial
```

Explicitly run the paid writer and reviewer:

```powershell
py -3.12 -m pipeline.script_only approved_episode.json --output output/general_script_trial --generate --max-revisions 1
```

Credentials stay in the existing environment. This uses `OPENROUTER_MODEL` and
`OPENROUTER_VERIFY_MODEL`; they must differ. Successful generation needs eight
logical requests before revisions, with at most one corrective attempt per
malformed/invalid stage. Existing transport retries still apply. Configure a
restricted provider key or the existing orchestration usage hook for a dollar
budget; this CLI does **not** enforce a new dollar ceiling itself. No paid test
was run for this implementation pass.

Output is `episode_project.json`, containing the script, contract, stage cache
and review report. `script_review_ready` means ready for human script review,
not a finished or publish-ready video. High-risk content returns
`script_expert_review_required`. Failed gates return a nonzero CLI exit status.
The script-only entrypoint never calls TTS, asset generation, rendering or upload.

## Evaluation plan

### Phase 1 — implemented contract and regression tests

Eight format/topic pairs exercise all eight stages with mocked providers: ecology,
architecture, cooking, photography, business, sports, astronomy and transport.
Additional cases cover legacy compatibility, unapproved briefs, malformed output,
claim scope, word budgets, source-role changes, cache reuse, bounded repair,
fact-locked editing, reviewer separation, high-risk holds and script-only isolation.
These tests establish routing and safety behavior, **not writing quality**.

### Phase 2 — real writing trials, next

Use fresh primary-source bundles for 60-90 second trials in science, history,
tutorial and comparison. Write two independently generated candidates per bundle.
Blind the author and version labels, then have a reviewer listen/read aloud and
score: immediate clarity, curiosity earned by evidence, concrete teaching,
sentence rhythm, format payoff, originality and factual restraint. Require no
unsupported claim and no major listener-confusion finding. Select the best
candidate, not the highest self-reported model score.

### Phase 3 — longer and unfamiliar subjects

Expand accepted trials to 8-12 minutes. Hold out topics and audiences not used
while adjusting prompts. Include a novice/expert pair and topics with conflicting
sources. Evaluate coherence across chapters, not just good opening paragraphs.
Record reasons for human edits. A professional review pass remains required.

### Phase 4 — generalize production separately

Only after script trials pass, adapt discovery, rights-aware visual acquisition,
storyboards and graphics by format. Measure actual audio duration and retention
on real episodes. No script system can guarantee virality or quality on every topic.

## Current boundaries

- English, evidence-backed nonfiction; fiction/comedy/sketches need separate contracts.
- 1-20 target minutes. Word estimates are planning aids, not verified runtime.
- No automatic broad-topic research or new topic discovery in this release.
- No automatic permission to reuse source footage or imitate a creator's identity.
- Existing news production remains compatible; arbitrary-niche full-video quality is unproven.

## Verification record — September 25, 2026

- 104 focused tests passed in the production workspace and again in the sanitized
  GitHub checkout. Existing worker, model, editorial, opening and style tests were included.
- Scoped coverage for the three new modules: **92%** (writer 89%, profile 95%, script-only entrypoint 98%).
- Python compilation passed for the three modules and the modified editorial,
  models and production modules.
- One Astra helper performed planning and independent static review. All four
  findings were repaired and given regression tests, including preserving a
  completed script and human edits when a dry-run is repeated.
- Two existing deprecation warnings remain (Starlette test client and Pillow).
- Full repository suite, paid provider trials, real script read-aloud evaluation,
  video generation and audience-retention validation were not run.

Focused test command (a fresh temporary directory avoids the existing locked
`.pytest_tmp` directory):

```powershell
$scriptTestTemp = Join-Path $env:TEMP ('general-script-final-' + [guid]::NewGuid().ToString('N'))
$env:COVERAGE_FILE = Join-Path $env:TEMP ('general-script-coverage-' + [guid]::NewGuid().ToString('N'))
py -3.12 -m pytest tests/test_general_scripting.py tests/test_editorial.py tests/test_models.py tests/test_opening_retention.py tests/test_editorial_style.py tests/test_worker_api.py -q -p no:cacheprovider --basetemp=$scriptTestTemp --cov=pipeline.general_scripting --cov=pipeline.script_profiles --cov=pipeline.script_only --cov-report=term-missing
py -3.12 -m compileall -q pipeline/general_scripting.py pipeline/script_profiles.py pipeline/script_only.py pipeline/editorial.py pipeline/models.py pipeline/production.py
```

Anti-slop review: implementation passes the scoped code gate after semantic
cache validation, source-role invalidation, expert-review holds and non-destructive
resume fixes. No unresolved hard blocker was found in that reviewed scope.
Naturalness and engagement of actual generated cross-niche scripts remain unscored;
mocked provider outputs are explicitly test fixtures, not portfolio samples.
