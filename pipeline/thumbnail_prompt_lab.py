"""Story-specific Nano Banana 2 prompts derived from measured thumbnail grammar.

Reference channels inform transferable hierarchy and material choices only.
Prompts never name a creator, request imitation, or ask the model to draw brand
identity, people, UI, or final headline text.
"""
from __future__ import annotations

from dataclasses import dataclass

from .creative_profile import ThumbnailConcept


@dataclass(frozen=True)
class PromptFamily:
    key: str
    composition: str
    set_design: str
    lighting: str
    palette: str
    empty_zones: str


PROMPT_FAMILIES: dict[str, PromptFamily] = {
    "commercial_collage": PromptFamily(
        "commercial_collage",
        "a precise asymmetric editorial flat-lay with a completely clean central field and quiet art-directed details confined to the far perimeter",
        "one continuous sheet of warm ivory uncoated paper, faint blue and orange registration lines, two small translucent acrylic color swatches at the extreme edges, exact folded-paper corners, subtle paper grain; no clips, frames, cards, pedestals, or containers",
        "large softbox from upper left, weak warm bounce from lower right, short physically plausible contact shadows, no atmospheric haze",
        "warm ivory, carbon black, restrained orange, one cobalt accent, one muted green detail",
        "an unobstructed central headline field covering 45 percent of the frame; an empty identity zone centered above it; keep all four corners visually quiet because real source captures will be composited there",
    ),
    "editorial_symbol": PromptFamily(
        "editorial_symbol",
        "an uninterrupted matte-black editorial field with one large sculptural folded bridge in the lower third and broad open space above it",
        "continuous charcoal screen-printed paper, one folded off-white paper bridge with a single muted slate cord passing through it, one narrow clay strip lying on the floor; no cards, frames, boards, panels, sockets, pins, labels, documents, or rectangles",
        "flat studio illumination with one narrow rim on the physical metaphor, crisp but not glossy, no bloom",
        "charcoal, off-white, muted slate, one moss detail, one restrained clay detail",
        "a broad unframed empty headline field across the upper half; one unframed identity area at lower left; keep the right third open for one real source capture",
    ),
    "cinematic_duel": PromptFamily(
        "cinematic_duel",
        "a symmetrical product-comparison stage with two equal empty plinths, a clean central tension gap, and shallow edge slots for evidence",
        "black painted wood, smoked acrylic, one cool blue glass plane on the left, one warm orange glass plane on the right, subtle brushed aluminum",
        "controlled product-photography lighting, blue edge light left, warm edge light right, neutral key light, deep clean blacks, no fog",
        "carbon black, cool cobalt, warm orange, neutral white highlights",
        "one empty identity mount per side; a broad empty headline field across the upper third; two empty screenshot slots at the lower corners",
    ),
    "bold_conflict": PromptFamily(
        "bold_conflict",
        "a bright architectural product-photography set with one large empty cylindrical plinth on the left and one much smaller empty cylindrical plinth on the right, leaving an uninterrupted path between them",
        "warm cream cyclorama wall and floor, matte architectural plaster plinths, one thin orange acrylic floor strip and one cobalt edge light; realistic construction with no drawn outlines, toy shapes, abstract glyphs, arrows, chevrons, pointers, or directional symbols",
        "large commercial softbox with controlled side fill, crisp physically grounded shadows, level horizon, high material clarity, no glow or painterly texture",
        "warm cream, carbon black, saturated red-orange, one cobalt accent",
        "a large uninterrupted headline zone across the top half; an empty logo-sized surface on each plinth; keep the center and far right clear for deterministic evidence and direction overlays; no labels on any object",
    ),
}


GLOBAL_EXCLUSIONS = (
    "people, human faces, hands, skin, portraits, presenters, influencers, crowds, characters",
    "words, letters, numbers, typography, logos, brand marks, mascots, signatures, watermarks, QR codes",
    "screens, product interfaces, fake screenshots, browser windows, app icons, charts with labels",
    "gears, circuit boards, circuit traces, microchips, sci-fi tunnels, concentric portals, glowing orbs, holograms, HUD graphics",
    "generic robots, android heads, cyberpunk rooms, neon fog, blue-purple AI glow, liquid chrome, random confetti",
    "impossible reflections, warped geometry, melted edges, floating objects without shadows, duplicated props, excessive depth of field",
)


def build_nano_banana_prompt(concept: ThumbnailConcept) -> str:
    family = PROMPT_FAMILIES[concept.style_mode]
    return (
        "Generate exactly one premium 16:9 BACKGROUND PLATE for a technology-news thumbnail at 2K. "
        "This is not a finished YouTube thumbnail. It is an art-directed physical set that will receive real screenshots, exact official logos, and typography later. "
        f"Narrative tension: {concept.angle}. Express that tension only through scale, spacing, and object placement; do not invent literal product imagery or claims. "
        f"Composition: {family.composition}. "
        f"Set design and materials: {family.set_design}. "
        f"Lighting: {family.lighting}. "
        f"Color discipline: {family.palette}. "
        f"Required negative space: {family.empty_zones}. "
        "Use a straight-on or very shallow three-quarter camera, 40mm product-photography perspective, level horizon, precise alignment, realistic material thickness, and deliberate human art direction. "
        "Make the scene look built and photographed by a professional design studio: specific, restrained, tactile, clean, and believable at phone size. "
        "Do not make it look futuristic, fantastical, generative, or like a generic AI technology illustration. "
        "STRICTLY EXCLUDE: " + "; ".join(GLOBAL_EXCLUSIONS) + "."
    )


def build_prompt_set(concepts: list[ThumbnailConcept]) -> list[dict[str, str]]:
    return [
        {
            "style_mode": concept.style_mode,
            "archetype": concept.archetype,
            "generation_mode": "local_deterministic" if concept.style_mode == "bold_conflict" else "nano-banana-2",
            "prompt": build_nano_banana_prompt(concept),
        }
        for concept in concepts
    ]


def review_prompt_set(prompt_set: list[dict[str, str]]) -> dict[str, object]:
    failures: list[str] = []
    for index, item in enumerate(prompt_set, start=1):
        prompt = item["prompt"].casefold()
        for required in ("background plate", "negative space", "exact official logos", "strictly exclude"):
            if required not in prompt:
                failures.append(f"prompt {index} misses required contract phrase: {required}")
        if len(prompt) < 900:
            failures.append(f"prompt {index} is underspecified")
        if any(name in prompt for name in ("ai labs", "dubibubi", "jack roberts")):
            failures.append(f"prompt {index} names a reference creator")
    return {"passed": not failures, "failures": failures, "count": len(prompt_set)}
