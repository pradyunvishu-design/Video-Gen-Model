# First 30 seconds: evidence-first, topic-adaptive hooks

Research and implementation: 2026-09-21. Goal: improve the Qwen-Image 2.1 opening and the existing script workflow, not promise virality.

## Findings and confidence

1. **Pay off the click early.** YouTube defines intro retention as the fraction still watching after 30 seconds, suggests aligning that opening with the title/thumbnail, and recommends moving compelling later moments earlier. Strong platform guidance; not an experiment establishing one universal hook. [YouTube retention help](https://support.google.com/youtube/answer/9314415?hl=en)
2. **Show the useful thing before channel ceremony.** YouTube's Creator Playbook recommends an immediate compelling statement or visual, early subject clarity and branding after content. Its tutorial example presents the finished result early. Foundational guidance from 2011, still consistent with current help; not a new 2026 controlled study. [Creator Playbook](https://blog.youtube/creator-and-artist-stories/youtube-creator-playbook-tips-first-15/)
3. **Diagnose the mismatch, not just the cut rate.** YouTube advises testing introductions and storytelling against retention, and separating traffic sources rather than treating aggregate performance as causal evidence. High clicks with poor retention can indicate a packaging mismatch. [YouTube metrics guide, 2025](https://blog.youtube/creator-and-artist-stories/master-these-4-metrics/)
4. **Use one focused question the evidence can answer.** Information-gap theory distinguishes a specific missing piece of knowledge from general interest. Applying that to video openings is an editorial inference, not a proven retention multiplier. Show enough context to make the gap intelligible; do not manufacture a secret. [Loewenstein, 1994](https://www.cmu.edu/dietrich/sds/docs/loewenstein/PsychofCuriosity.pdf) · [Golman and Loewenstein, 2014](https://www.cmu.edu/dietrich/sds/docs/golman/golman_loewenstein_curiosity.pdf)
5. **Synchronize words with the relevant visual.** Multimedia-learning work supports removing irrelevant material and presenting corresponding narration and pictures together. Publisher abstracts were available, not the full paywalled chapters; classroom learning findings do not establish YouTube retention uplift. [Mayer, 1999](https://www.benjamins.com/catalog/dd.1.1.02may) · [Fiorella and Mayer, 2021](https://doi.org/10.1017/9781108894333.019)
6. **Framing and focus matter more than random movement.** Google's ad guidance recommends getting into the story quickly, tight framing, simple messaging and avoiding competing audio/text. These are advertising findings; we adapt clarity principles, not ad conversion claims or early CTAs. [Google Ads ABCDs](https://support.google.com/google-ads/answer/14783551?hl=en) · [Google creative research](https://business.google.com/in/think/future-of-marketing/production-guide-youtube-ad-tips/)
7. **Do not confuse completion percentage with usefulness.** Wistia reports length/type-specific behavior across hosted business video. It is context, not a benchmark for an organic AI-news channel or a reason to shorten all episodes. [Wistia 2026 research recap](https://wistia.com/blog/state-of-video-webinar-recap)

## Existing project evidence reused

The project's 18-video AI Search opening study already identifies demonstration, bounded verdict, relatable friction, context reversal and ranked roundup formats. We reused transformed observations rather than copying transcripts or creator mannerisms. Files: `.agents/skills/write-human-ai-news-scripts/references/conversational-opening-study.md`, `configs/conversational_script_profile.json` and `configs/editorial_voice_profile.json`.

The existing opening lab generated four candidates but largely judged text and claim IDs. It allowed proof as late as 45 seconds and did not require an actual timed proof asset for the opening. This revision adds a separate first-30-second contract rather than rewriting the whole editorial system.

## Algorithm

1. Start with the **actual viewer promise** in the title/thumbnail, verified claims, available proof assets and episode format. Refuse a demo-first hook without a real available output/capture. Published examples must be attributed; a model test requires a genuine test ledger.
2. Generate four substantially different candidates spanning at least three suitable mechanisms. Explain the visual for each, the viewer consequence and where its promise is resolved. Never use a fixed reusable opening sentence.
3. Select on evidence fit, clear stakes, readability, speakability and novelty against recent openings. A quality assessment is not a forecast of views or retention.
4. Pair narration with an actual timed opening. Local adjustable targets: relevant proof visible by 5 seconds; product and practical benefit by 12; one question/promise, truthful scope/limit and an easy bridge into the body by about 30. These timings are production hypotheses, **not scientifically optimal universal deadlines**. No greeting, subscription request or logo-only opener.
5. Verify the completed audio timing, not character count. Inspect the opening without sound, then with narration. The first frame must already be meaningful, and each reveal must clarify the current clause. No jitter, arbitrary zoom, fake UI or unrelated spectacle.
6. Independently verify facts and wording; reject unsupported tests, unfulfilled promises and false visual evidence. Record script, audio, asset and render hashes. Repair only the opening if the body still matches its promise.
7. After authorized publication, compare observed 30-second retention and drop-off locations with similar-duration/format channel videos, separating traffic and viewer cohorts. Record sample size and date. Do not claim A/B causality from different uploads or infer retention from views alone. No analytics connection or publication is added by this task.

## Format routes, not universal wording

| Episode | Preferred entry if evidence permits | Necessary constraint |
|---|---|---|
| Image/video-model release | Visible output or controlled edit, then what changed | Attribute official showcases; distinguish from our own tests |
| Product test | Captured result/failure, then the exact test question | Comparable inputs and a test record |
| Comparison | Same input, meaningful output difference | No universal winner from unrelated tasks |
| Technical explainer | Familiar failure or useful consequence | Define jargon after the viewer understands the problem |
| Industry news | Verified consequence, then event/context | No fabricated urgency or employment prediction |
| Weekly roundup | Strongest consequence first, two concise previews | No flat long headline list |

## Qwen implementation

Old opening: about 48 seconds. A general problem statement precedes the specific transparent-image showcase (~29.6 seconds). It is clear but delays the thumbnail's cleanup proposition.

Candidate mechanisms considered:
- Demonstration: the real transparent PNG on contrasting backgrounds. Selected: directly pays off the thumbnail, understandable without jargon, available evidence on frame one.
- Friction: cleaning an edge after image generation. Rejected for this revision: repeats the old abstract setup and implies an unrecorded editing session unless illustrated explicitly.
- Context reversal: image quality versus post-generation work. Useful thesis, but too abstract before a visible example.
- Bounded verdict: native transparency is the most practically interesting capability. Rejected as opening: weaker than letting the viewer see it first.

New copy begins: **That background isn't white. It's gone.** The actual source PNG appears immediately; its background changes to demonstrate its existing alpha channel. A tightly framed repository excerpt then identifies the local-edit control without replaying the body section's before/after photographs a third time. The question is **can you actually skip the cleanup?** The episode examines examples, remaining checks and the license caveat, without claiming an independent model test.

Visual concept choice: direct alpha compositing wins over a mock editing application or a bullet-only roadmap. Camera stays locked; official logo remains unchanged; source artwork is not repurposed as a mascot. Short normal speech and a clause-timed before/after reveal replace the long introduction.

## Research scope and limitations

Four sub-questions: early payoff, honest curiosity, audiovisual clarity and measurement. Twelve query formulations searched general/platform sources and research literature; key official guidance was read beyond snippets. We screened broader search results but did not rely on growth blogs' unsupported promises. The list above records ten primary publications/pages, with access limits noted; the existing 18-video study was reused, not newly replayed. Firecrawl/Exa were unavailable; web search/open tools substituted under the deep-research skill. No audience experiment, model fine-tuning, public-channel retention measurement or guaranteed 'best algorithm' is claimed.
