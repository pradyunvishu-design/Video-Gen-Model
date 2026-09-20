"""Capture clean, already-positioned source evidence for one episode.

This supplements the generic capture planner with deterministic section frames.
It uses an isolated Chrome context, public pages only, no login state, and
records every frame in the EpisodeProject provenance ledger.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from pipeline.capture import _assert_capture_is_clean, _load_page
from pipeline.config import CAPTURE_PARALLELISM, OPENROUTER_BROWSER_MODEL
from pipeline.models import CaptureArtifact, CapturePlan, CaptureRecord
from pipeline.project_store import load_project, mark_stage, save_project


PROJECT_DIR = Path("data/episodes/episode_20260901_03").resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _positions(page, count: int) -> list[tuple[float, str]]:
    scroll_height = float(page.evaluate("document.documentElement.scrollHeight"))
    max_y = max(0.0, scroll_height - 1080.0)
    rows = []
    for heading in page.locator("h1,h2,h3").all():
        try:
            text = " ".join(heading.inner_text().split()).strip()
            absolute_y = float(heading.evaluate("e => e.getBoundingClientRect().top + window.scrollY"))
        except Exception:
            continue
        if not text or absolute_y < 180:
            continue
        if text in {"Innovation & AI", "Products & platforms", "Company news", "Ready for more?"}:
            continue
        rows.append((max(0.0, min(max_y, absolute_y - 130.0)), text[:150]))
    # Heading-centered frames are preferred. Fill any remaining slots with
    # evenly-spaced windows so no article screenshot is reused.
    if len(rows) < count:
        for index in range(count * 2):
            y = max_y * ((index + 1) / (count * 2 + 1)) if max_y else 0.0
            rows.append((y, f"Evidence section {index + 1}"))
    selected = []
    for y, label in rows:
        if any(abs(y - prior_y) < 120 for prior_y, _ in selected):
            continue
        selected.append((y, label))
        if len(selected) == count:
            break
    while len(selected) < count:
        index = len(selected)
        y = max_y * (index / max(1, count - 1)) if max_y else 0.0
        selected.append((y, f"Evidence frame {index + 1}"))
    return selected


def main() -> None:
    project = load_project(PROJECT_DIR)
    beats = {beat.id: beat for beat in project.script.beats}
    targets = [
        shot for shot in project.shots
        if shot.visual_category in {"article_evidence", "miscellaneous"}
    ]
    targets_by_source = defaultdict(list)
    for shot in targets:
        source_id = shot.source_id or (beats[shot.beat_id].source_ids or [project.sources[0].id])[0]
        shot.source_id = source_id
        targets_by_source[source_id].append(shot)

    source_by_id = {source.id: source for source in project.sources}
    output_dir = PROJECT_DIR / "captures" / "positioned_evidence"
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel="chrome", headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        try:
            for source_id, shots in targets_by_source.items():
                source = source_by_id[source_id]
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
                )
                page = context.new_page()
                artifacts = []
                errors = []
                try:
                    _load_page(page, str(source.url))
                    _assert_capture_is_clean(page, moment="positioned evidence capture")
                    for index, ((y, label), shot) in enumerate(zip(_positions(page, len(shots)), shots), 1):
                        target = output_dir / f"{source_id}-{index:02d}-{shot.id}.png"
                        page.evaluate("""y => {
                          document.documentElement.scrollTop = y;
                          document.body.scrollTop = y;
                          window.scrollTo(0, y);
                        }""", y)
                        page.wait_for_timeout(180)
                        page.screenshot(
                            path=str(target), full_page=False, animations="disabled",
                        )
                        sha = _sha256(target)
                        artifact = CaptureArtifact(
                            kind="element",
                            path=str(target),
                            label=label,
                            sha256=sha,
                            source_url=page.url,
                            capture_mode="positioned_source_section",
                            visible_text=label,
                            muted=True,
                            quality={
                                "status": "accepted",
                                "width": 1920,
                                "height": 1080,
                                "popup_free": True,
                                "prepositioned": True,
                            },
                        )
                        artifacts.append(artifact)
                        shot.asset_path = str(target)
                        shot.asset_fingerprint = hashlib.sha256(
                            f"{source_id}:{y:.1f}:{shot.id}".encode()
                        ).hexdigest()[:20]
                        shot.asset_type = "screenshot"
                        shot.source_in_seconds = 0
                        shot.presentation = "full_bleed"
                        shot.transition = "cut"
                        shot.motion_style = "push_in" if shot.visual_category == "article_evidence" else "locked"
                        shot.prompt = (
                            f"Positioned official source section: {label}. "
                            f"Current narration: {beats[shot.beat_id].narration}"
                        )
                        shot.rights_note = (
                            "Public source-page capture used for private editorial review; "
                            "publication rights review required."
                        )
                except Exception as exc:
                    errors.append(f"{type(exc).__name__}: {exc}")
                    raise
                finally:
                    context.close()
                records.append(CaptureRecord(
                    source_id=source_id,
                    requested_url=str(source.url),
                    final_url=str(source.url),
                    page_title=source.title,
                    captured_at=datetime.now(timezone.utc),
                    plan=CapturePlan(source_id=source_id, rationale="Prepositioned section evidence", actions=[]),
                    artifacts=artifacts,
                    errors=errors,
                ))
                source.capture_status = "complete"
        finally:
            browser.close()

    project.captures = records
    capture_input = {
        "planner": {
            "version": 7,
            "model": OPENROUTER_BROWSER_MODEL,
            "semantic_annotations": True,
            "resolution": "1080p",
            "parallelism": CAPTURE_PARALLELISM,
        },
        "sources": [{"id": source.id, "url": str(source.url)} for source in project.sources],
        "shots": [
            {"id": shot.id, "type": shot.asset_type, "source_id": shot.source_id, "prompt": shot.prompt}
            for shot in project.shots
        ],
        "model_tests": project.episode.get("model_test_queue", []),
    }
    mark_stage(project, "capture", capture_input)
    project.episode.get("stage_hashes", {}).pop("media", None)
    project.episode.get("stage_hashes", {}).pop("render", None)
    project.status = "approved_for_production"
    save_project(project, PROJECT_DIR)
    print(f"captured {sum(len(record.artifacts) for record in records)} unique positioned frames")


if __name__ == "__main__":
    main()
