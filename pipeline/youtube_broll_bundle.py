"""Validate a locally supplied, rights-cleared YouTube B-roll bundle.

The YouTube Data API can discover and verify Creative Commons metadata, but it
does not return video media.  This module deliberately keeps media acquisition
outside the renderer: an approved service or a human supplies local clips plus
their source records, and the renderer refuses incomplete or unlicensed input.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ALLOWED_RIGHTS_BASES = {
    "creative_commons",
    "creator_permission",
    "owned",
    "public_domain",
}
ALLOWED_RIGHTS_STATUSES = {"approved", "cleared"}


class BrollBundleError(ValueError):
    """Raised when a B-roll bundle cannot safely enter a render."""


def _resolve_media_path(value: str, manifest_path: Path) -> Path:
    source = Path(value)
    if not source.is_absolute():
        source = manifest_path.parent / source
    return source.resolve()


def load_approved_youtube_broll_bundle(
    manifest_path: Path,
    *,
    expected_slots: set[int],
    episode_id: str,
) -> dict[int, dict[str, Any]]:
    """Return one validated media record per expected six-second slot."""
    if not manifest_path.is_file():
        raise BrollBundleError(
            f"approved YouTube B-roll manifest is missing: {manifest_path}"
        )
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if raw.get("episode_id") != episode_id:
        raise BrollBundleError(
            f"bundle episode_id must be {episode_id!r}, got {raw.get('episode_id')!r}"
        )
    records = raw.get("clips")
    if not isinstance(records, list):
        raise BrollBundleError("bundle clips must be a list")

    by_slot: dict[int, dict[str, Any]] = {}
    seen_media_ranges: set[tuple[str, float, float]] = set()
    errors: list[str] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"clips[{index}] is not an object")
            continue
        try:
            slot = int(record["slot"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"clips[{index}] has no valid integer slot")
            continue
        if slot not in expected_slots:
            errors.append(f"slot {slot} is not assigned to YouTube B-roll")
            continue
        if slot in by_slot:
            errors.append(f"slot {slot} appears more than once")
            continue

        source_url = str(record.get("source_url") or "")
        if not source_url.startswith(("https://www.youtube.com/", "https://youtu.be/")):
            errors.append(f"slot {slot} has no YouTube source URL")
        rights_basis = str(record.get("rights_basis") or "").casefold()
        rights_status = str(record.get("rights_status") or "").casefold()
        if rights_basis not in ALLOWED_RIGHTS_BASES:
            errors.append(f"slot {slot} has unsupported rights_basis {rights_basis!r}")
        if rights_status not in ALLOWED_RIGHTS_STATUSES:
            errors.append(f"slot {slot} is not rights-approved")
        if str(record.get("qc_status") or "").casefold() != "passed":
            errors.append(f"slot {slot} has not passed visual QC")
        if not record.get("title") or not record.get("channel"):
            errors.append(f"slot {slot} is missing title/channel attribution")

        media_value = str(record.get("media_file") or "")
        if not media_value:
            errors.append(f"slot {slot} is missing media_file")
            continue
        media_path = _resolve_media_path(media_value, manifest_path)
        if not media_path.is_file() or media_path.stat().st_size < 100_000:
            errors.append(f"slot {slot} media is missing or too small: {media_path}")
            continue
        start = float(record.get("source_start_seconds") or 0.0)
        end = float(record.get("source_end_seconds") or (start + 6.0))
        if start < 0 or end - start < 5.9:
            errors.append(f"slot {slot} must provide at least 5.9 seconds of source media")
        media_range = (str(media_path).casefold(), round(start, 3), round(end, 3))
        if media_range in seen_media_ranges:
            errors.append(f"slot {slot} repeats an already-used source range")
        seen_media_ranges.add(media_range)

        by_slot[slot] = {
            **record,
            "slot": slot,
            "media_file": str(media_path),
            "source_start_seconds": start,
            "source_end_seconds": end,
        }

    missing = sorted(expected_slots - set(by_slot))
    extras = sorted(set(by_slot) - expected_slots)
    if missing:
        errors.append(f"missing YouTube B-roll slots: {missing}")
    if extras:
        errors.append(f"unexpected YouTube B-roll slots: {extras}")
    if errors:
        raise BrollBundleError("; ".join(errors))
    return by_slot
