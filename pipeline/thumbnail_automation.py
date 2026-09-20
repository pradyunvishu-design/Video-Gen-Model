"""Reusable strategy and provider-neutral prompt packs for tech thumbnails.

The automation separates generated scene art from deterministic identity and
typography.  An image model may create a high-quality backplate, but it is
never asked to draw company marks, product UI, mascots, or headline copy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from PIL import Image, ImageDraw

from .creative_profile import ThumbnailConcept
from .thumbnail_prompt_lab import build_prompt_set, review_prompt_set


@dataclass(frozen=True)
class StyleMode:
    key: str
    visual_goal: str
    composition: str
    material: str
    palette: tuple[str, ...]
    exclusions: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["palette"] = list(self.palette)
        data["exclusions"] = list(self.exclusions)
        return data


STYLE_MODES: dict[str, StyleMode] = {
    "cinematic_duel": StyleMode(
        "cinematic_duel",
        "Two opposing subjects resolve into one instantly readable comparison.",
        "Symmetrical confrontation, strong left/right color split, one shared task, large central tension.",
        "Realistic studio photography, tactile desk or device surfaces, controlled rim light.",
        ("#111318", "#315CFF", "#FF6A24", "#F7F4EA"),
        ("logo-headed people", "neon fog", "fake UI", "extra text", "watermarks"),
    ),
    "bold_conflict": StyleMode(
        "bold_conflict",
        "An exaggerated scale or emotional contrast makes the consequence obvious.",
        "Bright field, one oversized subject, one smaller counter-subject, huge outlined type, one alert block.",
        "Clean channel-owned 3D objects or crisp editorial cutouts with hard studio shadows.",
        ("#F3E59C", "#111111", "#FFFFFF", "#FF3D21", "#315CFF"),
        ("fake official mascot", "synthetic company logo", "extra limbs", "extra text", "watermarks"),
    ),
    "editorial_symbol": StyleMode(
        "editorial_symbol",
        "One physical metaphor and modular typography explain an era shift or hidden mechanism.",
        "Near-black field, cut-paper headline blocks, centered symbol, one crisp split or handoff outside logo pixels.",
        "Printed paper, ink, matte cutout, small offset shadows; no glossy render haze.",
        ("#1B1C20", "#F7F4EA", "#ECEA16", "#C96F54"),
        ("damaged logo", "random cracks", "glow", "extra text", "watermarks"),
    ),
    "commercial_collage": StyleMode(
        "commercial_collage",
        "One product identity anchors a polished collage of real outputs and capabilities.",
        "High-key center, three to five edge crops at varied scale and angle, dominant two-level headline.",
        "Editorial magazine layout, premium product-ad lighting, crisp paper and glass layers.",
        ("#F5F2EA", "#161616", "#FF6A24", "#315CFF", "#5B9468"),
        ("tiny unreadable UI", "random decoration", "generated logos", "extra text", "watermarks"),
    ),
}


def score_hook(headline: str, *, context: str = "") -> dict[str, Any]:
    """Score headline copy before spending image-generation credits."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", headline)
    value = " ".join(words).upper()
    context_tokens = {
        token.casefold() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", context)
        if len(token) > 3
    }
    specific_tokens = [word for word in words if word.casefold() in context_tokens]
    concrete = [
        word for word in words
        if len(word) >= 5 and word.upper() not in {"THIS", "CHANGES", "EVERYTHING", "THING", "FUTURE"}
    ]
    specificity = 5 if specific_tokens else (4 if any(char.isdigit() for char in value) or concrete else 3)
    curiosity = 5 if any(term in value for term in ("VS", "CATCH", "REAL", "STOP", "NOT", "WHY", "ERA")) else 4
    visualizability = 5 if 2 <= len(words) <= 5 else 2
    payoff = 5 if value and value not in {
        "THIS CHANGES EVERYTHING", "GAME CHANGER", "INSANE AI", "BIG AI NEWS",
    } else 1
    score = specificity + curiosity + visualizability + payoff
    return {
        "headline": value,
        "score": score,
        "max_score": 20,
        "specificity": specificity,
        "curiosity_gap": curiosity,
        "visualizability": visualizability,
        "script_payoff": payoff,
        "passed": specificity >= 4 and payoff >= 4 and 2 <= len(words) <= 5,
    }


def build_prompt_pack(
    concept: ThumbnailConcept,
    *,
    brand_labels: list[str],
    channel_id: str = "ai-news-weekly",
) -> dict[str, Any]:
    """Build provider-neutral draft/final prompts with an identity-safe contract."""
    style = STYLE_MODES[concept.style_mode]
    seed = "|".join((channel_id, concept.topic_class, concept.archetype, concept.headline))
    session_id = "thumb-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    brands = ", ".join(brand_labels) if brand_labels else "the documented product subject"
    base_prompt = (
        "Create a premium 16:9 YouTube thumbnail BACKPLATE ONLY at 1280x720. "
        f"Story: {concept.visual_sentence} Focal subject: {concept.focal_subject}. "
        f"Represented subjects, for composition only: {brands}. "
        f"Visual goal: {style.visual_goal} Composition: {style.composition} "
        f"Material and lighting: {style.material} Palette: {', '.join(style.palette)}. "
        "Reserve a clean, low-detail area covering at least 35 percent of the frame for a later headline. "
        "Create no words, letters, numbers, logos, brand marks, mascots, product UI, signatures, or watermarks. "
        "Do not imitate any existing thumbnail composition. Keep one focal cluster and strong phone-size silhouettes."
    )
    negative = ", ".join((*style.exclusions, "misspelled text", "malformed hands", "duplicate subjects", "busy background"))
    return {
        "session_id": session_id,
        "style": style.as_dict(),
        "draft": {
            "mode": "eco",
            "purpose": "composition proof only",
            "prompt": base_prompt + " Use fast draft detail while preserving the final composition.",
        },
        "final": {
            "mode": "max",
            "purpose": "selected high-quality backplate",
            "prompt": base_prompt + " Use maximum detail, clean edges, realistic materials, and controlled cinematic lighting.",
            "negative_prompt": negative,
        },
        "provider_options": {
            "magic_hour": {
                "text_to_image": ["nano-banana-2", "nano-banana"],
                "resolution": "2k",
                "aspect_ratio": "16:9",
                "image_count": 4,
                "credential": "MAGIC_HOUR_API_KEY",
                "identity_policy": "backplate-only; exact official logos are composited locally",
            },
            "eachlabs": {
                "text_to_image": ["gpt-image-v2-text-to-image", "flux-2-max-text-to-image"],
                "edit": ["gpt-image-v2-edit", "flux-2-max-edit"],
                "background_remove": "rembg-enhance",
                "upscale": "topaz-upscale-image",
                "credential": "EACHLABS_API_KEY",
            },
            "local_source_only": {
                "enabled": True,
                "description": "Use accepted source captures and deterministic Pillow composition with no image API.",
            },
        },
        "deterministic_overlay": {
            "headline": concept.headline,
            "highlighted_keyword": concept.highlighted_keyword,
            "required_logos": list(concept.required_logos),
            "rule": "Apply exact official local assets and headline typography after backplate generation.",
        },
    }


def build_automation_plan(
    concepts: list[ThumbnailConcept],
    *,
    brand_labels: list[str],
    channel_id: str = "ai-news-weekly",
) -> dict[str, Any]:
    """Return the auditable plan used by n8n, the worker, and review UI."""
    hook = score_hook(concepts[0].headline, context=" ".join(item.visual_sentence for item in concepts))
    return {
        "schema_version": "thumbnail-automation.v2",
        "channel_id": channel_id,
        "hook_review": hook,
        "candidate_count": len(concepts),
        "style_modes": [concept.style_mode for concept in concepts],
        "stages": [
            "brief", "identity_gate", "draft_backplates", "select", "max_backplate",
            "deterministic_composite", "mobile_qc", "human_review",
        ],
        "candidates": [build_prompt_pack(concept, brand_labels=brand_labels, channel_id=channel_id) for concept in concepts],
    }


def commercial_collage_backplate_prompt(concepts: list[ThumbnailConcept]) -> str:
    """Compatibility helper returning the preferred commercial prompt."""
    prompt_set = build_prompt_set(concepts)
    return prompt_set[0]["prompt"] if prompt_set else ""


def _local_bold_conflict_backplate(directory: Path) -> Path:
    """Create a clean non-AI plate where image generation adds no quality."""
    path = directory / "local_bold_conflict_v1.png"
    if path.is_file():
        return path
    width, height = 2048, 1152
    image = Image.new("RGB", (width, height), "#F5E6B2")
    pixels = image.load()
    left = (248, 235, 190)
    right = (242, 221, 169)
    for x in range(width):
        ratio = x / (width - 1)
        color = tuple(round(a + (b - a) * ratio) for a, b in zip(left, right))
        for y in range(height):
            pixels[x, y] = color
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, 26, height), fill=(49, 92, 255, 160))
    draw.rectangle((width - 34, 0, width, height), fill=(255, 76, 41, 175))
    draw.line((0, height - 72, width, height - 72), fill=(18, 18, 18, 35), width=3)
    image.save(path)
    return path


def generate_magic_hour_backplates(
    concepts: list[ThumbnailConcept],
    output_dir: Path,
    *,
    model: str = "nano-banana-2",
    fallback_model: str = "nano-banana",
    resolution: str = "2k",
    quality_review: bool = True,
    max_replacements_per_prompt: int = 2,
    prompt_set_override: list[dict[str, str]] | None = None,
) -> tuple[list[Path], dict[str, Any]]:
    """Generate or resume four Nano Banana collage plates through Magic Hour."""
    from . import magichour

    directory = output_dir / "generated-backplates"
    directory.mkdir(parents=True, exist_ok=True)
    prompt_set = prompt_set_override or build_prompt_set(concepts)
    prompt_review = review_prompt_set(prompt_set)
    if not prompt_review["passed"]:
        raise ValueError("Nano Banana prompt contract failed: " + "; ".join(prompt_review["failures"]))
    fingerprint = hashlib.sha256(json.dumps({
        "prompt_set": prompt_set,
        "model": model,
        "fallback_model": fallback_model,
        "resolution": resolution,
        "image_count": 1,
        "quality_review": quality_review,
        "quality_review_version": 1,
        "max_replacements_per_prompt": max_replacements_per_prompt,
    }, sort_keys=True).encode("utf-8")).hexdigest()
    record_path = directory / "magic_hour_backplates.json"
    if record_path.is_file():
        record = json.loads(record_path.read_text(encoding="utf-8"))
        cached = [Path(value) for value in record.get("paths") or []]
        if record.get("input_sha256") == fingerprint and len(cached) >= 4 and all(path.is_file() for path in cached):
            record["cache_hit"] = True
            return cached[:4], record

    from . import visual_qc

    progress_path = directory / "magic_hour_backplates.progress.json"
    progress = (
        json.loads(progress_path.read_text(encoding="utf-8"))
        if progress_path.is_file() else {"schema_version": "thumbnail-backplate-progress.v1", "entries": {}}
    )
    progress_entries = progress.setdefault("entries", {})
    prompt_fingerprints = [
        hashlib.sha256(json.dumps({
            "prompt": item["prompt"], "generation_mode": item.get("generation_mode"),
            "model": model, "fallback_model": fallback_model,
            "resolution": resolution, "quality_review": quality_review,
            "quality_review_version": 1, "max_replacements_per_prompt": max_replacements_per_prompt,
        }, sort_keys=True).encode("utf-8")).hexdigest()
        for item in prompt_set
    ]
    paths: list[Path | None] = [None] * 4
    quality_reviews: list[dict[str, Any] | None] = [None] * 4
    cached_count = 0
    pending_indices: list[int] = []
    for index, item_sha in enumerate(prompt_fingerprints):
        entry = progress_entries.get(str(index)) or {}
        cached_path = Path(str(entry.get("path") or ""))
        review = entry.get("quality_review") or {}
        if entry.get("input_sha256") == item_sha and cached_path.is_file() and review.get("passed"):
            paths[index] = cached_path
            quality_reviews[index] = review
            cached_count += 1
        else:
            pending_indices.append(index)

    api_pending_indices: list[int] = []
    for index in pending_indices:
        if prompt_set[index].get("generation_mode") != "local_deterministic":
            api_pending_indices.append(index)
            continue
        local_path = _local_bold_conflict_backplate(directory)
        local_review = {
            "passed": True, "unwanted_text": False, "logos_or_ui": False,
            "people_or_faces": False, "generic_ai_aesthetic": False,
            "severe_distortion": False, "usable_negative_space": True,
            "professional_art_direction": True,
            "notes": ["Deterministic non-AI background; generative imagery intentionally skipped for this style."],
            "style_mode": prompt_set[index]["style_mode"], "replacement_count": 0,
            "accepted_path": str(local_path.resolve()),
        }
        paths[index] = local_path
        quality_reviews[index] = local_review
        progress_entries[str(index)] = {
            "input_sha256": prompt_fingerprints[index], "style_mode": prompt_set[index]["style_mode"],
            "path": str(local_path.resolve()), "quality_review": local_review,
            "project_ids": [], "credits_charged": 0, "model": "local-deterministic", "resolution": "2k",
        }
        progress_path.write_text(json.dumps(progress, indent=2), encoding="utf-8")

    selected_model = model
    selected_resolution = resolution
    submissions_by_index: list[tuple[int, dict[str, Any]]] = []
    try:
        for index in api_pending_indices:
            item = prompt_set[index]
            submissions_by_index.append((index, magichour.image_generate(
                item["prompt"], f"thumbnail-{item['style_mode']}-prompt-lab-v2-{index + 1}",
                aspect_ratio="16:9", resolution=selected_resolution,
                model=selected_model, image_count=1,
            )))
    except Exception:
        if submissions_by_index or not fallback_model or fallback_model == selected_model:
            raise
        selected_model = fallback_model
        selected_resolution = "1k" if fallback_model == "nano-banana" else resolution
        submissions_by_index = [
            (index, magichour.image_generate(
                prompt_set[index]["prompt"],
                f"thumbnail-{prompt_set[index]['style_mode']}-prompt-lab-v2-fallback-{index + 1}",
                aspect_ratio="16:9", resolution=selected_resolution,
                model=selected_model, image_count=1,
            ))
            for index in api_pending_indices
        ]

    failed_reviews: list[str] = []
    for index, submitted in submissions_by_index:
        entry_project_ids = [str(submitted["id"])]
        entry_credits = 0
        complete = magichour.wait_image(str(submitted["id"]))
        entry_credits += int(complete.get("credits_charged", submitted.get("credits_charged", 0)) or 0)
        downloaded = magichour.download_all(complete, directory, f"prompt_lab_{index + 1}")
        if not downloaded:
            raise RuntimeError(f"Magic Hour returned no backplate for prompt {index + 1}")
        accepted_path = downloaded[0]
        identity_arena = str(prompt_set[index].get("archetype") or "") == "identity_arena"
        inspector = (
            visual_qc.inspect_identity_arena_backplate
            if identity_arena else visual_qc.inspect_thumbnail_backplate
        )
        expected_layout = (
            f"{prompt_set[index]['style_mode']} identity arena with the requested mascot count, "
            "blank logo panels, and clean deterministic-overlay zones"
            if identity_arena
            else f"{prompt_set[index]['style_mode']} with clean deterministic-overlay zones"
        )
        review = (
            inspector(accepted_path, expected_layout)
            if quality_review else {"passed": True, "notes": ["quality review disabled"]}
        )
        replacement_count = 0
        while not review["passed"] and replacement_count < max_replacements_per_prompt:
            replacement_count += 1
            repair_notes = "; ".join(str(value) for value in review.get("notes") or [])[:600]
            repair_prompt = (
                prompt_set[index]["prompt"]
                + " REPAIR DIRECTIVE: A previous result was rejected by visual QC. "
                + (repair_notes or "It violated the clean backplate contract.")
                + " Remove the failure completely. Create no placeholder labels, guide text, annotations, symbols, or pseudo-writing."
            )
            replacement = magichour.image_generate(
                repair_prompt, f"thumbnail-{prompt_set[index]['style_mode']}-prompt-lab-v2-repair-{replacement_count}",
                aspect_ratio="16:9", resolution=selected_resolution,
                model=selected_model, image_count=1,
            )
            entry_project_ids.append(str(replacement["id"]))
            replacement_complete = magichour.wait_image(str(replacement["id"]))
            entry_credits += int(
                replacement_complete.get("credits_charged", replacement.get("credits_charged", 0)) or 0
            )
            replacement_download = magichour.download_all(
                replacement_complete, directory, f"prompt_lab_{index + 1}_repair_{replacement_count}",
            )
            if not replacement_download:
                raise RuntimeError(f"Magic Hour returned no replacement for prompt {index + 1}")
            accepted_path = replacement_download[0]
            review = inspector(accepted_path, expected_layout)
        review["style_mode"] = prompt_set[index]["style_mode"]
        review["replacement_count"] = replacement_count
        review["accepted_path"] = str(accepted_path.resolve())
        progress_entries[str(index)] = {
            "input_sha256": prompt_fingerprints[index],
            "style_mode": prompt_set[index]["style_mode"],
            "path": str(accepted_path.resolve()),
            "quality_review": review,
            "project_ids": entry_project_ids,
            "credits_charged": entry_credits,
            "model": selected_model,
            "resolution": selected_resolution,
        }
        progress_path.write_text(json.dumps(progress, indent=2), encoding="utf-8")
        if not review["passed"]:
            quality_reviews[index] = review
            failed_reviews.append(
                f"Nano Banana backplate {index + 1} failed quality review after {replacement_count} replacements: "
                + "; ".join(str(value) for value in review.get("notes") or [])
            )
            continue
        paths[index] = accepted_path
        quality_reviews[index] = review
    if failed_reviews:
        raise RuntimeError(" | ".join(failed_reviews))
    if len(paths) != 4 or any(path is None for path in paths):
        raise RuntimeError("Magic Hour did not produce four accepted thumbnail backplates")
    final_entries = [progress_entries[str(index)] for index in range(4)]
    record = {
        "input_sha256": fingerprint,
        "project_ids": [project_id for entry in final_entries for project_id in entry["project_ids"]],
        "model": model,
        "resolution": resolution,
        "image_count": 4,
        "credits_charged": sum(int(entry["credits_charged"]) for entry in final_entries),
        "paths": [str(path.resolve()) for path in paths if path is not None],
        "prompt_set": prompt_set,
        "prompt_review": prompt_review,
        "quality_reviews": quality_reviews,
        "replacement_jobs": sum(int(entry["quality_review"].get("replacement_count", 0)) for entry in final_entries),
        "partial_cache_hits": cached_count,
        "cache_hit": cached_count == 4,
    }
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return [path for path in paths if path is not None], record


def run_brief(brief_path: Path, output_dir: Path) -> list[Path]:
    """Run a JSON brief through the existing deterministic thumbnail renderer."""
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    required = {"headline", "evidence_ids"}
    missing = sorted(required - set(brief))
    if missing:
        raise ValueError("thumbnail brief is missing required fields: " + ", ".join(missing))
    auto_route = str(brief.get("hero_template") or "").casefold() in {"auto", "universal"}
    auto_route = auto_route or str(brief.get("schema_version") or "") == "thumbnail-request.v1"
    if auto_route:
        from .thumbnail_formula import build_universal_thumbnail_brief
        brief = build_universal_thumbnail_brief(brief)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "planned_thumbnail_brief.json").write_text(json.dumps(brief, indent=2), encoding="utf-8")
    if str(brief.get("hero_template") or "") == "identity_arena":
        from .identity_arena_thumbnail import generate_identity_arena_package
        return generate_identity_arena_package(brief, output_dir)
    if not brief.get("source_images"):
        raise ValueError("source-first thumbnail briefs require at least one source image")
    from .thumbnail import generate_variants

    return generate_variants(
        [Path(value) for value in brief["source_images"]],
        str(brief["headline"]),
        output_dir,
        topic_context=str(brief.get("topic_context") or ""),
        episode_format=str(brief.get("episode_format") or ""),
        topic_class=str(brief.get("topic_class") or ""),
        evidence_ids=[str(value) for value in brief["evidence_ids"]],
        asset_ids=[str(value) for value in brief.get("asset_ids") or []] or None,
        focal_subject=str(brief.get("focal_subject") or "PRIMARY SOURCE"),
        supporting_subjects=[str(value) for value in brief.get("supporting_subjects") or []],
        represented_companies=[str(value) for value in brief.get("represented_companies") or []],
        must_not_imply=[str(value) for value in brief.get("must_not_imply") or []],
        generate_backplates=bool(brief.get("generate_backplates", False)),
        backplate_model=str(brief.get("backplate_model") or "nano-banana-2"),
        backplate_fallback_model=str(brief.get("backplate_fallback_model") or "nano-banana"),
        backplate_resolution=str(brief.get("backplate_resolution") or "2k"),
        require_brand_identity=bool(brief.get("require_brand_identity", False)),
    )
