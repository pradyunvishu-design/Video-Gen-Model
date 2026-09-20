"""Verified brand identity assets for editorial thumbnails.

Only exact local assets with an official provenance URL may be composited.  The
registry intentionally includes common companies whose files are not installed
yet: detecting one of those companies pauses thumbnail production instead of
drawing a lookalike logo or pretending a channel-owned avatar is official.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


DEFAULT_BRAND_ROOT = Path(__file__).resolve().parents[1] / "remotion" / "public" / "brands"


@dataclass(frozen=True)
class BrandIdentity:
    key: str
    display_name: str
    aliases: tuple[str, ...]
    domains: tuple[str, ...]
    asset_relpath: str | None
    identity_kind: str
    accent: str
    official_source_url: str
    terms_url: str = ""
    avatar_style: str = "none"
    avatar_status: str = "none"


BRAND_REGISTRY: dict[str, BrandIdentity] = {
    "openai": BrandIdentity(
        "openai", "OpenAI / ChatGPT / Codex", ("openai", "chatgpt", "codex", "gpt-5"),
        ("openai.com", "chatgpt.com"), "openai.svg", "logo", "#F2F1ED",
        "https://openai.com/brand/", avatar_style="geometric-rabbit",
        avatar_status="channel-owned-editorial-avatar",
    ),
    "claude": BrandIdentity(
        "claude", "Claude", ("claude", "claude code"), ("claude.ai",),
        "claude.svg", "product-logo", "#D97757", "https://www.anthropic.com/press-kit",
        avatar_style="geometric-rabbit", avatar_status="channel-owned-editorial-avatar",
    ),
    "anthropic": BrandIdentity(
        "anthropic", "Anthropic", ("anthropic",), ("anthropic.com",),
        "anthropic.svg", "logo", "#D97757", "https://www.anthropic.com/",
    ),
    "minimax": BrandIdentity(
        "minimax", "MiniMax", ("minimax", "hailuo", "h3"),
        ("minimax.io", "minimax.chat"), "minimax.svg", "logo", "#FF6673",
        "https://www.minimax.io/",
    ),
    "buzz": BrandIdentity(
        "buzz", "Buzz by Block", ("buzz", "block buzz", "buzz workspace"),
        ("buzz.xyz",), "buzz.svg", "product-logo", "#FFD84D",
        "https://github.com/block/buzz/blob/main/desktop/public/buzz.svg",
        "https://github.com/block/buzz/blob/main/LICENSE",
    ),
    "block": BrandIdentity(
        "block", "Block, Inc.", ("block", "block inc", "block, inc."),
        ("block.xyz",),
        "block-official/media-kit/block-logos_20250519/svg/block-lockup_black.svg",
        "logo", "#111111", "https://block.xyz/mediakit",
        "https://block.xyz/legal/copyright",
    ),
    "goose": BrandIdentity(
        "goose", "Goose by Block", ("goose", "block goose"),
        ("block.github.io", "github.com"), "goose.svg", "product-logo", "#111111",
        "https://cdn.agentclientprotocol.com/registry/v1/latest/goose.svg",
        "https://github.com/block/goose/blob/main/LICENSE",
    ),
    "github": BrandIdentity(
        "github", "GitHub / Copilot", ("github", "github copilot", "copilot"), ("github.com",),
        "github-brand/GitHub Logos/PNG/GitHub_Invertocat_Black.png",
        "official-mascot", "#F2F1ED", "https://github.com/logos",
        "https://docs.github.com/en/site-policy/github-terms/github-logo-policy",
    ),
    # Common news subjects below are detectable but deliberately unresolved.
    # Add an exact approved file and provenance before producing their thumbnail.
    "amd": BrandIdentity(
        "amd", "AMD", ("amd", "ryzen", "radeon", "instinct"), ("amd.com",),
        None, "logo", "#ED1C24", "https://www.amd.com/en/partner/browse-by-resource/marketing-materials.html",
        "https://www.amd.com/en/legal/terms-and-conditions/media-library.html",
    ),
    "gemini": BrandIdentity(
        "gemini", "Google Gemini", ("gemini", "google gemini", "deepmind"),
        ("gemini.google.com", "deepmind.google", "ai.google"), "gemini.svg", "product-logo", "#4E7CF4",
        "https://ai.google.dev/_static/googledevai/images/gemini-api-logo.svg",
    ),
    "google": BrandIdentity(
        "google", "Google", ("google",), ("google.com",), None, "logo", "#4285F4",
        "https://about.google/brand-resource-center/",
    ),
    "huggingface": BrandIdentity(
        "huggingface", "Hugging Face", ("hugging face", "huggingface"), ("huggingface.co",),
        None, "official-mascot", "#FFD21E", "https://huggingface.co/brand",
    ),
    "meta": BrandIdentity(
        "meta", "Meta", ("meta", "llama"), ("meta.com", "ai.meta.com"), None, "logo", "#0668E1",
        "https://about.meta.com/brand/resources/meta/company-brand/",
    ),
    "microsoft": BrandIdentity(
        "microsoft", "Microsoft", ("microsoft", "azure", "phi"), ("microsoft.com", "azure.com"),
        None, "logo", "#00A4EF", "https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks",
    ),
    "nvidia": BrandIdentity(
        "nvidia", "NVIDIA", ("nvidia", "cuda", "nemotron"), ("nvidia.com",), None, "logo", "#76B900",
        "https://www.nvidia.com/en-us/about-nvidia/legal-info/logo-brand-usage/",
    ),
    "stability": BrandIdentity(
        "stability", "Stability AI", ("stability ai", "stable diffusion"), ("stability.ai",),
        None, "logo", "#8B5CF6", "https://stability.ai/",
    ),
    "mistral": BrandIdentity(
        "mistral", "Mistral AI", ("mistral", "mistral ai"), ("mistral.ai",), None, "logo", "#FF7000",
        "https://mistral.ai/",
    ),
    "xai": BrandIdentity(
        "xai", "xAI / Grok", ("xai", "x.ai", "grok"), ("x.ai",), None, "logo", "#F2F1ED",
        "https://x.ai/",
    ),
    "perplexity": BrandIdentity(
        "perplexity", "Perplexity", ("perplexity",), ("perplexity.ai",), None, "logo", "#22B8B0",
        "https://www.perplexity.ai/",
    ),
    "magic-hour": BrandIdentity(
        "magic-hour", "Magic Hour", ("magic hour", "magichour"), ("magichour.ai",), None, "logo", "#B74DFF",
        "https://magichour.ai/",
    ),
    "comfyui": BrandIdentity(
        "comfyui", "ComfyUI", ("comfyui", "comfy ui"), ("comfy.org",), "comfyui.svg", "project-logo", "#5D92FF",
        "https://github.com/Comfy-Org/docs/blob/main/logo.svg",
    ),
}


def _contains_alias(text: str, alias: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(alias.casefold())}(?![A-Za-z0-9])", text))


def normalize_brand_key(value: str) -> str | None:
    normalized = re.sub(r"\s+", " ", value.strip().casefold())
    if normalized in BRAND_REGISTRY:
        return normalized
    for key, identity in BRAND_REGISTRY.items():
        if any(normalized == alias.casefold() for alias in identity.aliases):
            return key
    return None


def detect_brand_keys(
    entities: list[str] | tuple[str, ...] = (), *, context: str = "", source_urls: list[str] | tuple[str, ...] = (),
) -> list[str]:
    """Detect represented brands from entity language and official source domains."""
    text = " ".join([*entities, context]).casefold()
    hosts = [urlsplit(str(url)).netloc.casefold().removeprefix("www.") for url in source_urls]
    detected: list[str] = []
    for key, identity in BRAND_REGISTRY.items():
        alias_hit = any(_contains_alias(text, alias) for alias in identity.aliases)
        domain_hit = any(
            host == domain or host.endswith("." + domain)
            for host in hosts for domain in identity.domains
        )
        if alias_hit or domain_hit:
            detected.append(key)
    # Claude is the more useful product identity when both it and Anthropic are named.
    if "claude" in detected and "anthropic" in detected:
        detected.remove("anthropic")
    # Gemini is the useful product identity when a Google source is specifically about Gemini.
    if "gemini" in detected and "google" in detected:
        detected.remove("google")
    return detected[:4]


def resolve_brand_assets(
    requested: list[str] | tuple[str, ...], *, brand_root: Path | None = None,
    overrides: dict[str, Path] | None = None,
) -> list[dict[str, str]]:
    """Resolve exact local identity files or fail with an actionable missing-assets list."""
    root = brand_root or DEFAULT_BRAND_ROOT
    override_map = {key.casefold(): Path(path) for key, path in (overrides or {}).items()}
    records: list[dict[str, str]] = []
    failures: list[str] = []
    seen: set[str] = set()
    for raw in requested:
        key = normalize_brand_key(raw)
        if not key:
            failures.append(f"{raw}: no brand registry entry")
            continue
        if key in seen:
            continue
        seen.add(key)
        identity = BRAND_REGISTRY[key]
        path = override_map.get(key)
        if path is None and identity.asset_relpath:
            path = root / identity.asset_relpath
        if path is None or not path.is_file():
            failures.append(
                f"{identity.display_name}: approved {identity.identity_kind} file is missing "
                f"(official source: {identity.official_source_url})"
            )
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append({
            "key": key, "display_name": identity.display_name, "identity_kind": identity.identity_kind,
            "asset_path": str(path.resolve()), "asset_sha256": digest, "accent": identity.accent,
            "official_source_url": identity.official_source_url, "terms_url": identity.terms_url,
            "generated": "false",
            "avatar_style": identity.avatar_style,
            "avatar_status": identity.avatar_status,
        })
    if failures:
        raise ValueError("thumbnail brand identity gate failed: " + "; ".join(failures))
    return records


def motion_brand_theme(context: str) -> dict[str, str] | None:
    """Return localized motion styling without altering an official mark."""
    keys = detect_brand_keys(context=context)
    if not keys:
        return None
    identity = BRAND_REGISTRY[keys[0]]
    return {
        "key": identity.key,
        "displayName": identity.display_name,
        "accent": identity.accent,
        "markTreatment": "official-asset-unmodified",
        "avatarStyle": identity.avatar_style,
        "avatarStatus": identity.avatar_status,
        "officialSourceUrl": identity.official_source_url,
    }
