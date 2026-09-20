---
name: "Premium Source-First AI News"
version: "2.0"
style_prompt_short: "Source-first technology journalism with asymmetric editorial hierarchy, one specific proof object, restrained neutral editorial accents, and motion that explains rather than decorates."
style_prompt_full: "Design an original 1920x1080 editorial motion frame for technology news. Begin with one verified claim, compare three structurally different concepts, and select one dominant relationship. Use a neutral near-black or paper canvas, IBM Plex Serif for editorial display, IBM Plex Sans for body copy, and a small professional palette of slate, moss, clay, paper, and charcoal. Yellow and purple are forbidden as editorial accents, cards, captions, source markers, or glows; a native color may remain only inside an unmodified verified company logo. Make real source evidence, official product UI, charts, or a verified mechanism occupy most of the stage. Prefer intentional asymmetry and product-specific detail over centered logo objects and reusable card templates. Use a quiet newsroom source credit with a thin neutral rule—never a colored status dot or pill. Reveal information in reading order with short enter/connect/emphasize motions, strong ease-out entrances, and faster exits. Keep the camera locked, use hard cuts or a four-to-eight-frame fade, and change meaningful information every two to three seconds. Reject invented mascots, stacked all-caps headlines, perfect symmetry, plastic 3D icons, floating glass cards, neon accents, colorful gradients, random glows, decorative underlines, equal card grids, constant zooms, and invented UI. An underline is permitted only for an exact single-line DOM Range stored with the capture; otherwise use no underline or a restrained element boundary."
colors:
  primary:
    - name: "Canvas"
      hex: "#121513"
      role: "neutral background"
    - name: "Paper"
      hex: "#F0F2F0"
      role: "primary type and proof surfaces"
    - name: "Muted"
      hex: "#C8CEC9"
      role: "secondary text"
    - name: "Line"
      hex: "#4A4F4B"
      role: "structural dividers"
    - name: "Slate"
      hex: "#83938C"
      role: "single neutral editorial emphasis"
    - name: "Clay"
      hex: "#B56F55"
      role: "warm company-adjacent emphasis when semantically justified"
typography:
  display: "IBM Plex Serif 600"
  body: "IBM Plex Sans 400"
  mono: "IBM Plex Mono 500"
layout:
  frame: "1920x1080"
  safe_inset_px: 96
  rule: "one dominant relationship, intentional asymmetry, no more than three focal groups"
motion:
  intents: ["micro", "enter", "connect", "emphasize"]
  transitions: ["hard cut", "4-8 frame fade"]
  camera: "locked by default"
---
