"""Generate high-depth, identity-free Nano Banana plates for three AI-news hooks."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline import magichour


ROOT = Path("output/thumbnails/viral_topics_aug_2026/nano_banana_remake")


PROMPTS = {
    "gpt56_speed": """
Create four original premium 16:9 visual backplate variations for a YouTube technology-news thumbnail.
BACKPLATE ONLY. The factual story is an AI model offered in an ultrafast mode, with a reported peak of fourteen times the standard speed. Turn that speed claim into one unmistakable physical visual sentence.

Show a practical studio-built speed test: a compact matte-black server module or precision compute object on the RIGHT half of a wind-tunnel test bench, caught in a violent but believable burst of acceleration. Use long-exposure white and electric-lime speed streaks, a bent analog gauge needle, flying paper test strips, and one clean blank circular metal badge on the front of the object for a verified logo to be added later. The object must remain crisp and tactile while the environment communicates extreme speed. Leave the LEFT 38 percent dark and low-detail for a large headline. Camera is close, slightly low, 35mm commercial product photograph; hard key light, controlled rim light, practical reflections, real brushed aluminum, matte polymer and paper. Charcoal, warm white and acid-yellow palette. Deliberately art-directed, punchy, high contrast, recognizable at phone size.

Do not create any words, letters, numbers, logos, brand marks, mascots, people, faces, UI, screens, charts, circuit-board wallpaper, holograms, neon fog, sci-fi rooms, random frames, podiums, watermarks or signatures. No glossy generic AI render. No duplicate objects. Preserve generous clean headline space.
""".strip(),
    "github_models_retired": """
Create four original premium 16:9 visual backplate variations for a YouTube technology-news thumbnail.
BACKPLATE ONLY. The factual story is that an online AI-model service has been fully retired. Communicate removal and finality in one physical scene, without destruction or misinformation.

On the RIGHT two-thirds, show a row of four distinct matte model tokens or small black product boxes being pulled behind a heavy closing archival shutter. One final token sits halfway across the threshold while a thick red power cable has been cleanly unplugged and rests in the foreground. Include one large blank circular black plaque with a thin white rim on the final token for an exact verified logo to be composited later. A red paper retirement strip crosses part of the shutter but contains absolutely no writing. Leave the LEFT 40 percent clean near-black for a giant headline. Real workshop photography, crisp cut-paper and powder-coated steel materials, believable contact shadows, subtle red practical light, strong silhouette, asymmetrical editorial composition. Serious but playful tech-news energy, immediately readable at phone size.

Do not create any words, letters, numbers, logos, brand marks, mascots, people, faces, UI, screens, fake error messages, explosions, fire, cracks through the blank plaque, neon fog, generic robots, random cards, watermarks or signatures. No glossy generic AI look. Preserve a clean headline zone.
""".strip(),
    "claude_tests_chips": """
Create four original premium 16:9 visual backplate variations for a YouTube technology-news thumbnail.
BACKPLATE ONLY. The factual story is that an AI coding system is being used to write and run tests for semiconductor and hardware validation. Make the semiconductor testing visually undeniable.

Build an extreme macro commercial photograph of a real semiconductor probe station on the RIGHT two-thirds: one large golden silicon die and part of a patterned 300mm wafer under precise robotic probe needles, with an amber scanning light passing across the die. Add a clean cream-colored blank circular enamel badge attached to the probe arm, large and front-facing, ready for an exact verified logo overlay. Show a few tiny physical green pass indicators as simple lights only, never interface text. Leave the LEFT 38 percent deep charcoal and low-detail for a large headline. Terracotta, copper, cream and charcoal palette with a restrained cyan edge light. Highly tactile laboratory metal, ceramic, glass and silicon; editorial product-photography polish; dramatic close focus; controlled depth of field; strong shape separation at phone size. The scene should feel built and photographed by a human art director, not imagined by an AI.

Do not create any words, letters, numbers, logos, brand marks, mascots, people, faces, hands, UI, monitors, circuit-board wallpaper, sci-fi laboratories, holograms, neon fog, liquid chrome, random frames, watermarks or signatures. No malformed machinery. Preserve the blank badge and generous headline space.
""".strip(),
}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    record_path = ROOT / "generation_record.json"
    if record_path.is_file():
        record = json.loads(record_path.read_text(encoding="utf-8"))
    else:
        record = {"schema_version": "viral-nano-banana-plates.v1", "topics": {}}

    pending: list[tuple[str, dict]] = []
    for key, prompt in PROMPTS.items():
        topic_dir = ROOT / key
        topic_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(topic_dir.glob("*.png")) + sorted(topic_dir.glob("*.jpg"))
        if len(existing) >= 4:
            record["topics"][key] = {
                **record["topics"].get(key, {}),
                "prompt": prompt,
                "paths": [str(path.resolve()) for path in existing[:4]],
                "cache_hit": True,
            }
            continue
        saved = record["topics"].get(key, {})
        if saved.get("project_id"):
            pending.append((key, {"id": saved["project_id"]}))
            continue
        submitted = magichour.image_generate(
            prompt,
            f"viral-thumbnail-{key}-reference-study-v1",
            aspect_ratio="16:9",
            resolution="2k",
            model="nano-banana-2",
            image_count=4,
        )
        record["topics"][key] = {
            "prompt": prompt,
            "project_id": str(submitted["id"]),
            "model": "nano-banana-2",
            "resolution": "2k",
            "cache_hit": False,
        }
        record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        pending.append((key, submitted))

    for key, submitted in pending:
        completed = magichour.wait_image(str(submitted["id"]))
        paths = magichour.download_all(completed, ROOT / key, "plate")
        entry = record["topics"][key]
        entry["paths"] = [str(path.resolve()) for path in paths]
        entry["credits_charged"] = int(
            completed.get("credits_charged", submitted.get("credits_charged", 0)) or 0
        )
        record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
