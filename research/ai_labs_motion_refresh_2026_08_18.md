# AI LABS motion study refresh — 2026-08-18

This is a genre-level production study for an original channel package. It is not permission to trace frames, copy branded artwork, reuse footage, or reproduce distinctive layouts shot-for-shot.

## Material inspected

- AI LABS channel video index: <https://www.youtube.com/@AILABS-393/videos>
- “How To Use Claude Design To Build Beautiful Sites”: <https://www.youtube.com/watch?v=bBlY5YOsKN8>
- “Every Level Of Claude Code Loop Engineering”: <https://www.youtube.com/watch?v=PLyRe6Zk--8>

Representative states were inspected around 0:20–3:00. The useful pattern is consistent across the sampled videos:

1. The camera is usually locked. Motion happens inside the explanation.
2. Full-screen product UI and source pages are allowed to remain still long enough to read.
3. Cards enter by 8–18 pixels, settle, and stop. There is no ambient floating.
4. Paths draw only when explaining a workflow or loop.
5. Real source text gets one marker-style highlight, not a permanent animated underline.
6. Interface comparisons use two large equal panels, not many small dashboard cards.
7. Black space is functional. It isolates one relationship at a time.
8. Product footage and human/source clips interrupt diagrams so the episode does not become a motion-graphics slideshow.
9. Color is restrained: neutral black/gray dominates; product color and one warm accent identify the active state.
10. State changes happen every few seconds, but this does not mean the frame must constantly move.

## Implementation decisions

- Remove automatic `zoompan` from all stills.
- Keep source footage and screenshots at exactly 1.0× unless a narrated evidence crop requires at most 1.01×.
- Use a 56/22/22 target mix: official footage, source pages, deterministic motion graphics.
- Replace static three-card boards with six reusable motion patterns: ladder, workflow, metric, boundary, checklist, and title verdict.
- Restrict overlays to semantic moments and animate the overlay layer, never the underlying camera.
- Keep hard cuts as the default; use short opacity or directional blur only when the argument changes.
- Run blocked-page, popup, repetition, freeze, silence, and motion-stability checks before review.
