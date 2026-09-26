# Reusable motion graphics

The composer can now use nine original, structured SVG/HyperFrames layouts:
process, timeline, comparison, bars, layers, hub-and-spoke, checklist, quote,
and single metric. Three theme presets (charcoal, paper, slate) separate color
choices from content. These are nine layouts, not 27 different designs.

This extends the existing composer, Shot contract and production renderer. It
does not replace existing Remotion compositions, generate facts, copy a channel's
artwork, or claim measured AI LABS fidelity. It is not a newly trained model.

## Reproduce a graphic

From the repository root, with project Python dependencies and Node installed:

```powershell
python -m scripts.build_motion_library
$env:HYPERFRAMES_NO_TELEMETRY='1'
npx --yes hyperframes@0.8.77 preview data/motion_expert_runs/library_v1/gallery --background --port 3020
```

This builds an 88-second, nine-scene multi-topic gallery for review, not an MP4.
For custom content use `--input path/to/specs.json --output path/to/package`.
Input is one JSON object or an array of up to 40 objects. See
`configs/motion_library_examples.json` for museum, cooking, education and data
examples. The downloaded GSAP runtime is version- and SHA-256-pinned. Compiled
episode packages stage the same local runtime; raw `write_package()` callers
must call `stage_runtime()` before browser preview.

```json
{
  "kind": "comparison",
  "title": "Two ways to explain the idea",
  "theme": "paper",
  "duration_seconds": 10,
  "source_label": "Customer research",
  "evidence_ids": ["claim_1_1"],
  "items": [
    {"label": "Demonstration", "detail": "Show the action and its result."},
    {"label": "Diagram", "detail": "Show the relationship behind the action."}
  ]
}
```

Reuse means changing content, theme and duration without rewriting animation.
Same input and library version produce the same HTML and content hash. System
fonts can differ between operating systems; byte-identical cross-platform video
is not claimed. Output is fixed at 1920 x 1080.

## Composer integration

Existing worker authentication applies. `X-Customer-ID` is a scope supplied by a
trusted authenticated server, not a public client login mechanism.

1. `GET /motion-styles` returns the catalog and input schema.
2. Approve the evidence-checked script using the existing composer review flow.
3. `POST /composition-projects/{id}/motion-specs` with `beat_id`,
   `expected_script_hash`, and `spec`. Evidence IDs must belong to that beat.
   Even an illustrative episode graphic requires claim binding and a source.
4. Run `plan_edit`, review the plan, then run `compile_edit` through existing
   jobs. Standalone examples can use `illustrative: true`; they remain visibly
   marked as illustrative, never benchmark results.
5. Preview the generated local `motion_graphics/{scene_id}` package in
   HyperFrames Studio. `GET .../motion-previews` supplies IDs and review hashes,
   not public file URLs. A hosted customer preview UI is not included here.
6. After human visual review, `POST .../motion-previews/{scene_id}/approve` with
   `expected_hash`. The existing production motion renderer checks current plan
   and preview approvals before calling HyperFrames. Compilation is not video
   generation; rendering remains a separate existing production stage.

The planner suggests a style from narrative intent. New styles require supplied
structured content rather than invented numbers or labels. Automatic free-text
extraction into every graphic type is not implemented. Strong footage and legacy
motion routes remain available. Explicit assignments may reuse a family with new
content, subject to the episode's motion-share and reading-time limits. An
assignment that cannot fit becomes a visible review gap, not a silent substitution.

## Guardrails and limitations

- Four to twenty seconds per graphic, bounded text/items and minimum reading time.
- Numeric graphics require supplied nonnegative values. Evidence binding is a
  provenance check, not proof that a claim or number is true.
- Unsupported fields and layouts are rejected rather than silently ignored.
- Locked framing, short staggered reveals, no random movement or decorative zoom.
- Package HTML changes invalidate approval; changed plans require recompilation.
- Source text is escaped. No user-provided HTML or executable scene code.
- Large lists must be split. Negative/log scales, maps, custom logos, arbitrary
  aspect ratios and bespoke 3D scenes are outside this library's current schema.
- Preview approval is required before final rendering. Publishing stays disabled.

## Checks

```powershell
python -m pytest tests/test_motion_library.py tests/test_video_composer.py -q -p no:cacheprovider --basetemp .test_tmp/motion-library-check
npx --yes hyperframes@0.8.77 check data/motion_expert_runs/library_v1/gallery --snapshots --json
```

Coverage includes nine styles across three themes, invalid inputs, content hashes,
source binding, ownership, stale approvals, runtime integrity, compilation into
the existing Shot model and refusing unapproved rendering. Browser snapshots and
seeked motion checks supplement unit tests. They do not establish channel-fidelity
scores or acceptance of every possible customer brief.
