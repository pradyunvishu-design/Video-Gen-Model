---
name: write-human-ai-news-scripts
description: Write, revise, and review evidence-backed AI and technology YouTube narration that sounds natural, useful, consistent, and genuinely spoken. Use for episode promises, outlines, section drafts, script humanization, hooks, transitions, humor, read-aloud editing, and script quality review.
---

# Human AI-News Script Writing

Use a staged writer's room. Do not ask one model to research, outline, write, humanize, and fact-check in a single prompt.

## Project route

1. Require an approved brief, source bundle, and claim records.
2. Load `configs/editorial_voice_profile.json`. Keep one audience relationship and vocabulary range across the episode without turning them into catchphrases.
3. Load `configs/conversational_script_profile.json`, then run `pipeline.editorial.build_editorial_plan`. The plan generates four evidence-backed opening candidates across at least three mechanisms and selects one before outlining.
4. Run `pipeline.editorial.draft_researched_sections`. Each chapter may use only its assigned claim IDs.
5. Run `pipeline.editorial.write_script` to unify the section drafts into one speaker and one continuous argument.
6. Run `pipeline.editorial.humanize_script` as a fact-locked read-aloud edit. It may change narration and delivery, never evidence mappings or beat order.
7. Run `pipeline.editorial.verify_script` and `pipeline.editorial.review_script_quality` independently. Revise only from specific failed claims, beats, or rubric items.
8. Do not generate narration until fact, promise, voice, clarity, and oral-quality gates pass or a human records an explicit override.

## Writing contract

- Make one answerable promise in the opening. Target visible proof within five seconds, product and practical benefit by twelve, and a truthful scope/bridge by thirty. These are adjustable local production targets, not universal retention laws. Resolve the promise at the end.
- Use `pipeline.opening_retention.build_opening_contract` to adapt the entry to the episode format and available evidence. Verify the actual spoken/visual timing with `evaluate_opening` before describing an opening as verified. An untimed script remains `awaiting_actual_timeline`; textual quality is not measured retention. See `research/first_30_seconds_hook_system.md` for research, limits, and cohort-based follow-up.
- Rotate evidence-appropriate opening mechanisms—verdict, demonstration, relatable friction, context reversal, or ranked roundup—rather than reusing one viral-hook shell.
- Build chapters around a listener question. Supply proof that changes the answer, translate the consequence, state the important limit, and leave through a causal bridge.
- Write for the ear. Prefer concrete nouns, active verbs, explicit referents, natural contractions, and varied sentence lengths.
- Put examples before abstractions. Delay jargon until the problem is understood, then define it once in plain language.
- Earn retention with proof, a useful example, a comparison, a failure, or a changed conclusion. Never manufacture suspense.
- Humor is optional. Keep only short observations that arise from documented product friction, contradiction, limitation, or recognizable behavior.
- Use a clean cut when no spoken transition is needed. Never insert a transition merely to prove that a transition exists.
- Treat Reddit and X as leads or attributed reaction unless another source verifies the factual claim.

## Automatic rejection

Reject and rewrite scripts with:

- stock AI phrases, press-release language, fake excitement, generic summaries, or copied creator mannerisms;
- repeated rhetorical questions, repeated beat openings, metronomic sentence lengths, or formal essay connectors;
- announced structure such as "next question," "observation," or "the key takeaway";
- unexplained technical terms, ambiguous pronouns, or conclusions that arrive before proof;
- first-person testing language without a captured test ledger;
- factual beats without claim IDs, unsupported numbers or names, or a promise the ending does not answer.

## Method boundaries

Adapt workflow patterns, not prompt wording or persona. The research sources support staged blueprinting, payoff alignment, format routing, independent criticism, and read-aloud revision. They do not authorize imitation of a creator or copying repository prose into narration.

Read [references/human-script-rubric.md](references/human-script-rubric.md) for the scoring contract. Read [references/conversational-opening-study.md](references/conversational-opening-study.md) when choosing or reviewing an opening. Read [references/method-sources.md](references/method-sources.md) for provenance and adaptation limits.
