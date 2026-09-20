# Source package and setup boundaries

This repository contains the project's first-party Python pipeline, worker API,
n8n workflow templates, Remotion scenes, thumbnail tooling, scripts, tests,
configuration profiles, and project-local editorial/art-direction skills.
It is a source snapshot, not a pretrained model or a bundle of finished episodes.

## What is deliberately not published

- API keys, live environment files, private Google Sheets IDs, saved credential
  bindings, browser profiles, cookies, and live tunnel addresses.
- Narrator recordings, consent records, company/source media, downloaded footage,
  completed episodes, captions, transcripts, run databases, or logs.
- `node_modules`, local Python packages, browser binaries, caches, or third-party
  checkouts. Their upstream sources and pinned revisions remain in
  `configs/video_production_sources.json`.
- Machine-specific progress notes and personal workspace/agent instructions.

The original working project and all private production artifacts stay on the
owner's computer. This separate checkout preserves the destination repository's
history and contains only the reviewed export.

## Local setup

1. Use Python 3.12+ and Node.js. Install FFmpeg and make `ffmpeg`/`ffprobe` available.
2. Create a virtual environment and install `requirements-dev.txt`.
3. Install the Playwright Chromium browser with `python -m playwright install chromium`.
4. In `remotion`, run `npm ci` to install its pinned dependencies.
5. Copy `.env.example` to `.env` and enter your own keys. Never commit that file.
   Use `.env.worker.example` for worker deployment settings. Start with a private
   local worker and a long random `WORKER_API_TOKEN`; do not expose it unprotected.
6. Configure your own approved narrator and licensed assets. Public brand logos
   and demo footage are not bundled. Recreate local source folders as needed.
7. Import the JSON workflows from `n8n/`. They are disabled templates: bind your own
   n8n credentials, replace `https://video-worker.example.com`, and set your own
   spreadsheet ID. Spreadsheet tab names are retained, not private numeric IDs.
8. Read the main README for individual stages and worker endpoints. Start with
   local tests and one short private canary; inspect cost/rights/quality gates
   before any full episode or schedule. No upload/publication automation is enabled.

## Portability and dependency limitations

The reusable application lives in `pipeline/`. Some historical one-off scripts in
`scripts/` and `tools/` still refer to the original Windows workspace, installed
tools, local fonts, or missing episode assets. They are included as source, not
promised to run unchanged on another machine. The source export does not refactor
these scripts or recreate private input data.

Runtime data under `data/` and assets under `remotion/public/` are omitted on
purpose. Render and corpus-dependent integration tests may need those inputs.
Model names in templates reflect the existing project and must be checked for
availability with your own provider account before paid runs.

External references retain their own license requirements. In particular,
`recreate-video` remains a private-evaluation integration pending license review;
its implementation is not copied into this public repository. Do not infer reuse
permission from a catalog entry. Remotion company-use terms and every media asset's
rights require their own review. No blanket license is assigned to third-party work.

## Verification and export record

`SOURCE_EXPORT_MANIFEST.json` records exported paths, hashes, exclusions, and n8n
sanitization. The export checks provider-key patterns and exact known local secret
values without printing them. This is a focused safety check, not a guarantee that
every possible sensitive identifier is detectable.

The export does not make paid provider calls, execute episode production, upload
media, or alter the production project's credential files/workflows.
