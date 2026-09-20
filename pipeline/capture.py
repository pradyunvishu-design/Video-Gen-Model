"""Safety-constrained Playwright screenshots and short public-page recordings."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .config import CAPTURE_PARALLELISM, FFMPEG_PRESET, FFMPEG_THREADS_PER_JOB
from .models import CaptureAction, CaptureArtifact, CapturePlan, CaptureRecord, Source

CapturePlanner = Callable[[Source, dict, list[str]], CapturePlan]
CAPTURE_CACHE_VERSION = 5
_QC_SAMPLE_WIDTH = 160
_QC_SAMPLE_HEIGHT = 90


class BlockedPageError(RuntimeError):
    """Raised when a capture target returns a bot challenge or access-denied page."""


class CaptureOverlayError(RuntimeError):
    """Raised when a capture would show a paywall or an intrusive modal.

    This is deliberately a rejection, not a mechanism for removing a
    subscription wall. The editorial pipeline must switch to another public
    source instead of recording content hidden behind access controls.
    """


_BLOCKED_PAGE_PATTERNS = (
    "you've been blocked by network security",
    "you have been blocked by network security",
    "access denied",
    "request blocked",
    "temporarily blocked",
    "verify you are human",
    "are you a robot",
    "unusual traffic from your computer network",
    "complete the security check",
    "captcha",
    "just a moment...",
)

_PAYWALL_PATTERNS = (
    "subscribe to continue", "subscribe to read", "continue reading with",
    "unlock unlimited", "start your trial", "start a trial", "already a subscriber",
    "subscription required", "become a subscriber", "subscribe for access",
    "sign in to continue", "log in to continue", "create an account to continue",
)


def _capture_overlay_report(page) -> list[dict]:
    """Report visible modal-like obstructions without trying to defeat them."""
    try:
        return page.evaluate("""(paywallPatterns) => {
          const selectors = [
            'dialog', '[role="dialog"]', '[aria-modal="true"]',
            '[class*="modal"]', '[id*="modal"]', '[class*="overlay"]', '[id*="overlay"]',
            '[class*="paywall"]', '[id*="paywall"]', '[class*="subscribe"]', '[id*="subscribe"]'
          ].join(',');
          const viewportArea = Math.max(1, innerWidth * innerHeight);
          const rows = [];
          for (const el of document.querySelectorAll(selectors)) {
            const style = getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || 1) < 0.05) continue;
            if (rect.width < 160 || rect.height < 72 || rect.bottom < 0 || rect.right < 0 || rect.top > innerHeight || rect.left > innerWidth) continue;
            const fixed = style.position === 'fixed' || style.position === 'sticky' || el.matches('dialog,[role="dialog"],[aria-modal="true"]');
            if (!fixed) continue;
            const area = (Math.min(innerWidth, rect.right) - Math.max(0, rect.left)) * (Math.min(innerHeight, rect.bottom) - Math.max(0, rect.top));
            const text = (el.innerText || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 360);
            const normalized = text.toLowerCase();
            const paywall = paywallPatterns.some(pattern => normalized.includes(pattern));
            // A compact sticky header or chat pill is not a visual obstruction.
            if (!paywall && area / viewportArea < 0.10) continue;
            rows.push({ text, paywall, coverage: Math.round(area / viewportArea * 1000) / 10 });
          }
          return rows.slice(0, 8);
        }""", list(_PAYWALL_PATTERNS)) or []
    except Exception:
        return []


def _assert_no_paywall_overlay(page, *, moment: str) -> None:
    overlays = _capture_overlay_report(page)
    paywall = next((row for row in overlays if row.get("paywall")), None)
    if paywall:
        raise CaptureOverlayError(
            f"paywall/subscription overlay at {moment}; source capture rejected ({paywall.get('text', '')[:120]})"
        )


def _assert_capture_is_clean(page, *, moment: str) -> None:
    overlays = _capture_overlay_report(page)
    paywall = next((row for row in overlays if row.get("paywall")), None)
    if paywall:
        raise CaptureOverlayError(
            f"paywall/subscription overlay at {moment}; source capture rejected ({paywall.get('text', '')[:120]})"
        )
    obstruction = next((row for row in overlays if float(row.get("coverage", 0)) >= 18), None)
    if obstruction:
        raise CaptureOverlayError(
            f"intrusive overlay at {moment}; source capture rejected ({obstruction.get('text', '')[:120]})"
        )


def _blocked_page_reason(page) -> str:
    """Return a stable reason for short challenge pages, otherwise an empty string."""
    try:
        title = (page.title() or "").casefold().strip()
    except Exception:
        title = ""
    try:
        body = (page.locator("body").inner_text(timeout=3000) or "").casefold().strip()
    except Exception:
        body = ""
    sample = f"{title}\n{body[:12000]}"
    # Avoid rejecting a normal article that merely discusses access errors.
    challenge_sized = len(body) < 12000
    for pattern in _BLOCKED_PAGE_PATTERNS:
        if pattern in sample and challenge_sized:
            return pattern
    if title in {"forbidden", "access denied", "blocked"}:
        return title
    return ""


def _capture_urls(url: str) -> list[str]:
    """Return conservative visual fallbacks without changing the cited source identity."""
    parsed = urlsplit(url)
    candidates = [url]
    host = (parsed.hostname or "").casefold()
    if host == "reddit.com" or host.endswith(".reddit.com"):
        old_reddit = parsed._replace(netloc="old.reddit.com").geturl()
        if old_reddit not in candidates:
            candidates.append(old_reddit)
    return candidates


@lru_cache(maxsize=512)
def _host_is_public(hostname: str) -> bool:
    host = hostname.casefold().rstrip(".")
    if not host or host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            }
        except (OSError, ValueError):
            return False
    return bool(addresses) and all(address.is_global for address in addresses)


def _safe_url(url: str) -> str:
    parsed = urlsplit(str(url))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or not _host_is_public(parsed.hostname):
        raise ValueError(f"capture URL is not a public HTTP(S) destination: {url}")
    if parsed.username or parsed.password:
        raise ValueError("capture URL must not contain credentials")
    return str(url)


def _slug(source: Source) -> str:
    title = re.sub(r"[^a-z0-9]+", "-", source.title.lower()).strip("-")[:48]
    return f"{source.id}-{title or hashlib.sha256(str(source.url).encode()).hexdigest()[:8]}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _route_public(route) -> None:
    parsed = urlsplit(route.request.url)
    if parsed.scheme in {"about", "blob", "data"}:
        route.continue_()
        return
    try:
        _safe_url(route.request.url)
    except ValueError:
        route.abort()
        return
    route.continue_()


def _load_page(page, url: str, *, freeze_motion: bool = True) -> None:
    page.route("**/*", _route_public)
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    _safe_url(page.url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeoutError:
        pass
    # Check before suppressing benign cookie/newsletter chrome. That avoids a
    # false "clean" result if a site happens to label a paid-access modal as a
    # newsletter prompt.
    _assert_no_paywall_overlay(page, moment="page load")
    # Public cookie-consent controls are safe to dismiss for a clean evidence
    # capture. Prefer rejection so the browser session does not opt into
    # optional tracking. This is deliberately narrow and never targets login,
    # subscription, paywall, or generic modal buttons.
    for label in ("Reject All", "Reject all", "Reject optional cookies", "Only necessary"):
        try:
            button = page.get_by_role("button", name=label, exact=True).first
            if button.is_visible(timeout=500):
                button.click(timeout=1500)
                page.wait_for_timeout(250)
                break
        except Exception:
            continue
    motion_css = """
        *, *::before, *::after {
          caret-color: transparent !important;
          animation-duration: 0s !important;
          animation-delay: 0s !important;
          transition-duration: 0s !important;
          scroll-behavior: auto !important;
        }
    """ if freeze_motion else """
        *, *::before, *::after { caret-color: transparent !important; }
        html, body { cursor: none !important; }
        video { object-fit: contain !important; }
    """
    # Consent and newsletter prompts obstruct a public page but do not control
    # access to its reporting. Never add paywall/subscription selectors here:
    # those are detected and rejected below rather than hidden.
    page.add_style_tag(content="""
        [class*='cookie'], [id*='cookie'], [class*='consent'], [id*='consent'],
        [class*='newsletter'], [id*='newsletter'], [data-testid*='cookie'] { display:none !important; }
        html { scroll-behavior: auto !important; }
        html, body { scrollbar-width: none !important; }
        body::-webkit-scrollbar { display: none !important; }
    """ + motion_css)
    try:
        page.evaluate("""async () => {
          if (document.fonts && document.fonts.ready) await document.fonts.ready;
          const images = [...document.images].filter(img => img.getBoundingClientRect().top < innerHeight * 3);
          const readiness = Promise.all(images.map(img => img.complete ? Promise.resolve() : new Promise(resolve => {
            img.addEventListener('load', resolve, {once:true}); img.addEventListener('error', resolve, {once:true});
          })));
          await Promise.race([readiness, new Promise(resolve => setTimeout(resolve, 5000))]);
        }""")
    except Exception:
        pass
    page.wait_for_timeout(700)
    reason = _blocked_page_reason(page)
    if reason:
        raise BlockedPageError(f"challenge page detected ({reason})")
    _assert_capture_is_clean(page, moment="page load")


def _observe_page(page) -> dict:
    candidates = page.evaluate("""
        () => {
          const selector = 'h1,h2,h3,main,article,section,figure,img,video,canvas,[role="main"],[role="img"],button,a';
          const output = [];
          for (const element of document.querySelectorAll(selector)) {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            if (style.display === 'none' || style.visibility === 'hidden' || rect.width < 120 || rect.height < 35) continue;
            const text = (element.innerText || element.getAttribute('alt') || element.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
            if (!text && !['IMG', 'VIDEO', 'CANVAS'].includes(element.tagName)) continue;
            const candidateId = `c${String(output.length + 1).padStart(3, '0')}`;
            element.setAttribute('data-ai-capture-id', candidateId);
            output.push({
              candidate_id: candidateId,
              tag: element.tagName.toLowerCase(),
              role: element.getAttribute('role') || '',
              aria_label: element.getAttribute('aria-label') || '',
              href: element.tagName === 'A' ? (element.getAttribute('href') || '') : '',
              controls: element.tagName === 'VIDEO' ? Boolean(element.controls) : false,
              text: text.slice(0, 240),
              width: Math.round(rect.width),
              height: Math.round(rect.height),
              y: Math.round(rect.top + window.scrollY)
            });
            if (output.length >= 80) break;
          }
          return output;
        }
    """)
    return {"page_title": page.title(), "final_url": page.url, "candidates": candidates}


def _artifact(
    kind: str, path: Path, label: str = "", *, source_url: str = "", capture_mode: str = "",
    quality: dict | None = None, candidate_id: str = "", visible_text: str = "",
) -> CaptureArtifact:
    return CaptureArtifact(
        kind=kind, path=str(path), label=label, sha256=_sha256(path), source_url=source_url,
        capture_mode=capture_mode, candidate_id=candidate_id, visible_text=visible_text,
        muted=True, quality=quality or {},
    )


def _exact_text_region(locator, phrase: str) -> dict | None:
    """Return a tight normalized DOM Range for one exact, single-line phrase.

    The locator is captured as its own image, so coordinates are normalized to
    the element rather than the full browser viewport.  Multi-line ranges fail
    closed because a single underline would otherwise point at the wrong line.
    """
    phrase = " ".join(phrase.split()).strip()
    if not phrase:
        return None
    return locator.evaluate(
        """
        (element, phrase) => {
          const wanted = phrase.toLocaleLowerCase();
          const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
          let node;
          while ((node = walker.nextNode())) {
            const raw = node.textContent || '';
            const start = raw.toLocaleLowerCase().indexOf(wanted);
            if (start < 0) continue;
            const range = document.createRange();
            range.setStart(node, start);
            range.setEnd(node, start + phrase.length);
            const rects = [...range.getClientRects()].filter(r => r.width > 1 && r.height > 1);
            if (rects.length !== 1) return null;
            const rect = rects[0];
            const host = element.getBoundingClientRect();
            if (host.width <= 0 || host.height <= 0) return null;
            return {
              x: Math.max(0, Math.min(1, (rect.left - host.left) / host.width)),
              y: Math.max(0, Math.min(1, (rect.top - host.top) / host.height)),
              width: Math.max(0.001, Math.min(1, rect.width / host.width)),
              height: Math.max(0.001, Math.min(1, rect.height / host.height))
            };
          }
          return null;
        }
        """,
        phrase,
    )


def _capture_stills(page, output_dir: Path, slug: str, plan: CapturePlan, errors: list[str]) -> list[CaptureArtifact]:
    artifacts: list[CaptureArtifact] = []
    reason = _blocked_page_reason(page)
    if reason:
        raise BlockedPageError(f"challenge page detected before screenshot ({reason})")
    _assert_capture_is_clean(page, moment="screenshot")
    viewport_path = output_dir / f"{slug}-viewport.png"
    full_path = output_dir / f"{slug}-full.png"
    page.screenshot(path=str(viewport_path), full_page=False, animations="disabled")
    page.screenshot(path=str(full_path), full_page=True, animations="disabled")
    artifacts.extend([
        _artifact("viewport", viewport_path, "Opening viewport", source_url=page.url, capture_mode="viewport"),
        _artifact("full_page", full_path, "Full-page source record", source_url=page.url, capture_mode="full_page"),
    ])
    targeted = [action for action in plan.actions if action.kind in {"element", "hover", "focus"}][:5]
    for index, action in enumerate(targeted, start=1):
        try:
            locator = page.locator(f'[data-ai-capture-id="{action.candidate_id}"]')
            if locator.count() != 1:
                raise ValueError("candidate is no longer unique")
            locator.scroll_into_view_if_needed(timeout=5000)
            if action.kind == "hover":
                locator.hover(timeout=5000)
                page.wait_for_timeout(500)
            visible_text = " ".join(locator.inner_text(timeout=5000).split()).strip()
            exact_region = _exact_text_region(locator, action.label)
            target = output_dir / f"{slug}-element-{index:02d}.png"
            locator.screenshot(path=str(target), animations="disabled", timeout=10000)
            quality = {
                "dom_text_verified": bool(
                    action.label and action.label.casefold() in visible_text.casefold()
                ),
            }
            if exact_region:
                quality["exact_text"] = action.label
                quality["exact_text_region"] = exact_region
            artifacts.append(_artifact(
                "element", target, action.label, source_url=page.url, capture_mode=action.kind,
                candidate_id=action.candidate_id, visible_text=visible_text, quality=quality,
            ))
        except Exception as exc:
            errors.append(f"{action.kind} {action.candidate_id}: {type(exc).__name__}: {exc}")
    return artifacts


def _motion_actions(plan: CapturePlan) -> list[CaptureAction]:
    actions = [
        action for action in plan.actions
        if action.kind in {"scroll", "hover", "focus", "click_reveal", "video_playback"}
    ][:3]
    return actions or [CaptureAction(
        kind="scroll", label="Controlled evidence scroll", start_ratio=0.05, end_ratio=0.85,
        duration_seconds=7,
    )]


def _perform_motion(page, action: CaptureAction) -> None:
    duration_ms = int(action.duration_seconds * 1000)
    _install_editorial_cursor(page)
    if action.kind in {"hover", "focus", "click_reveal", "video_playback"} and action.candidate_id:
        locator = page.locator(f'[data-ai-capture-id="{action.candidate_id}"]')
        if locator.count() == 1:
            locator.scroll_into_view_if_needed(timeout=5000)
            move_ms = min(650, max(250, duration_ms // 4))
            _move_editorial_cursor(page, locator, duration_ms=move_ms)
            pre_hold_ms = min(240, max(100, duration_ms // 12))
            page.wait_for_timeout(pre_hold_ms)
            if action.kind == "video_playback":
                locator.evaluate("video => { video.muted = true; video.volume = 0; video.loop = true; video.play(); }")
            elif action.kind == "click_reveal":
                locator.click(timeout=5000, no_wait_after=True)
            else:
                locator.hover(timeout=5000)
            settle_ms = round(action.settle_seconds * 1000)
            page.wait_for_timeout(settle_ms)
            remaining_ms = max(250, duration_ms - move_ms - pre_hold_ms - settle_ms)
            if action.kind == "focus":
                page.evaluate("""async ({durationMs}) => {
                  await new Promise(resolve => {
                    const start = performance.now();
                    const tick = now => now - start >= durationMs ? resolve() : requestAnimationFrame(tick);
                    requestAnimationFrame(tick);
                  });
                }""", {"durationMs": remaining_ms})
            else:
                page.wait_for_timeout(remaining_ms)
            return
    page.evaluate("document.getElementById('__ai_capture_cursor')?.style.setProperty('opacity','0.55')")
    page.evaluate("""async ({startRatio, endRatio, durationMs}) => {
      const maxScroll = Math.max(0, document.documentElement.scrollHeight - innerHeight);
      const requestedStart = maxScroll * startRatio;
      const requestedEnd = maxScroll * endRatio;
      const maxTravel = innerHeight * 1.35;
      const direction = requestedEnd >= requestedStart ? 1 : -1;
      const start = Math.max(0, Math.min(maxScroll, requestedStart));
      const end = Math.max(0, Math.min(maxScroll, start + direction * Math.min(Math.abs(requestedEnd - start), maxTravel)));
      const hold = Math.min(450, Math.max(250, durationMs * 0.08));
      const active = Math.max(500, durationMs - hold * 2);
      window.scrollTo(0, Math.round(start));
      await new Promise(resolve => setTimeout(resolve, hold));
      await new Promise(resolve => {
        const begin = performance.now();
        const frame = now => {
          const t = Math.min(1, (now - begin) / active);
          const eased = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
          // Pixel-aligned positions avoid sub-pixel shimmer in text and thin UI
          // rules when Chromium's recorder samples a scrolling page.
          window.scrollTo(0, Math.round(start + (end - start) * eased));
          if (t < 1) requestAnimationFrame(frame); else resolve();
        };
        requestAnimationFrame(frame);
      });
      await new Promise(resolve => setTimeout(resolve, hold));
    }""", {
        "startRatio": action.start_ratio, "endRatio": action.end_ratio, "durationMs": duration_ms,
    })


def _install_editorial_cursor(page) -> None:
    """Add a clean cursor to the captured DOM; Playwright video omits the OS pointer."""
    page.evaluate("""
      () => {
        if (document.getElementById('__ai_capture_cursor')) return;
        const cursor = document.createElement('div');
        cursor.id = '__ai_capture_cursor';
        cursor.setAttribute('aria-hidden', 'true');
        cursor.style.cssText = 'position:fixed;left:82%;top:78%;width:22px;height:31px;z-index:2147483647;pointer-events:none;transform:translate(-3px,-3px);filter:drop-shadow(0 1px 2px rgba(0,0,0,.38));opacity:.92';
        cursor.innerHTML = '<svg viewBox="0 0 20 28" width="22" height="31"><path d="M2 2L2 23L7 18L11 26L15 24L11 16L18 16Z" fill="white" stroke="#171C1A" stroke-width="1.5" stroke-linejoin="round"/></svg>';
        document.documentElement.appendChild(cursor);
      }
    """)


def _move_editorial_cursor(page, locator, *, duration_ms: int = 650) -> None:
    box = locator.bounding_box()
    if not box:
        return
    page.evaluate("""
      async ({x,y,duration}) => {
        const cursor = document.getElementById('__ai_capture_cursor');
        if (!cursor) return;
        const current = cursor.getBoundingClientRect();
        const sx = current.left + current.width / 2;
        const sy = current.top + current.height / 2;
        const cx = sx + (x - sx) * .42;
        const cy = sy - Math.min(90, Math.abs(x - sx) * .1);
        cursor.style.opacity = '.94';
        await new Promise(resolve => {
          const started = performance.now();
          const frame = now => {
            const progress = Math.min(1, (now - started) / duration);
            const eased = progress * progress * (3 - 2 * progress);
            const inverse = 1 - eased;
            cursor.style.left = (inverse * inverse * sx + 2 * inverse * eased * cx + eased * eased * x) + 'px';
            cursor.style.top = (inverse * inverse * sy + 2 * inverse * eased * cy + eased * eased * y) + 'px';
            if (progress < 1) requestAnimationFrame(frame); else resolve();
          };
          requestAnimationFrame(frame);
        });
      }
    """, {
        "x": box["x"] + box["width"] / 2,
        "y": box["y"] + box["height"] / 2,
        "duration": duration_ms,
    })


def _video_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _recording_quality(path: Path, *, expected_seconds: float) -> dict:
    """Perform deterministic acceptance checks before a capture reaches editing."""
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-of", "json", "-show_entries",
        "format=duration,size,bit_rate:stream=codec_type,width,height,avg_frame_rate",
        str(path),
    ], capture_output=True, text=True, check=True)
    payload = json.loads(probe.stdout or "{}")
    stream = next((item for item in payload.get("streams", []) if item.get("codec_type") == "video"), {})
    rate = str(stream.get("avg_frame_rate", "0/1"))
    numerator, denominator = (rate.split("/", 1) + ["1"])[:2] if "/" in rate else (rate, "1")
    fps = float(numerator) / max(1.0, float(denominator))
    fmt = payload.get("format", {})
    duration = float(fmt.get("duration") or 0)
    bitrate = int(float(fmt.get("bit_rate") or 0))
    report = {
        "status": "accepted",
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "fps": round(fps, 3),
        "duration_seconds": round(duration, 3),
        "bitrate_bps": bitrate,
        "checks": ["1080p", "30fps", "duration"],
        "readability_review_required": True,
    }
    failures: list[str] = []
    if (report["width"], report["height"]) != (1920, 1080):
        failures.append(f"expected 1920x1080, got {report['width']}x{report['height']}")
    if not 29.5 <= fps <= 30.5:
        failures.append(f"expected 30fps, got {fps:.2f}")
    if duration < max(0.1, expected_seconds * 0.95 - 1 / 30):
        failures.append(f"recording too short ({duration:.2f}s)")
    if path.is_file():
        sampled = subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(path), "-an", "-vf",
            f"fps=2,scale={_QC_SAMPLE_WIDTH}:{_QC_SAMPLE_HEIGHT}:flags=area,format=gray",
            "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
        ], capture_output=True, check=True)
        visual = _visual_frame_metrics(
            sampled.stdout, width=_QC_SAMPLE_WIDTH, height=_QC_SAMPLE_HEIGHT,
        )
        report["visual"] = {key: value for key, value in visual.items() if key != "failures"}
        report["checks"].extend(["non_black_pixels", "visible_motion", "edge_detail"])
        failures.extend(visual["failures"])
    # A mostly static text page can encode sharply at a very low bitrate.
    # Conversely, noisy unreadable frames can have a high bitrate. Keep this
    # metric informational; do not label an encode sharp without visual review.
    if failures:
        report["status"] = "rejected"
        report["failures"] = failures
        raise RuntimeError("recording QC rejected: " + "; ".join(failures))
    return report


def _visual_frame_metrics(raw: bytes, *, width: int, height: int) -> dict:
    """Measure real decoded pixels so a valid container cannot hide black/frozen footage."""
    frame_size = width * height
    if width < 2 or height < 2 or frame_size <= 0:
        raise ValueError("visual QC dimensions must be at least 2x2")
    frames = [raw[offset:offset + frame_size] for offset in range(0, len(raw), frame_size)]
    frames = [frame for frame in frames if len(frame) == frame_size]
    if not frames:
        return {
            "sampled_frames": 0, "black_frame_ratio": 1.0, "frozen_pair_ratio": 1.0,
            "motion_energy": 0.0, "edge_energy": 0.0,
            "failures": ["capture frame sampling failed"],
        }
    black_frames = sum(
        sum(pixel <= 8 for pixel in frame) / frame_size >= 0.985 for frame in frames
    )
    pair_energy = [
        sum(abs(left - right) for left, right in zip(before, after)) / frame_size
        for before, after in zip(frames, frames[1:])
    ]
    edge_energy = max(
        sum(
            abs(frame[row * width + column] - frame[row * width + column - 1])
            for row in range(height) for column in range(1, width)
        ) / (height * (width - 1))
        for frame in frames
    )
    frozen_pairs = sum(value < 0.18 for value in pair_energy)
    frozen_ratio = frozen_pairs / len(pair_energy) if pair_energy else 0.0
    failures: list[str] = []
    black_ratio = black_frames / len(frames)
    if black_ratio >= 0.75:
        failures.append("capture is black")
    if edge_energy < 1.0:
        failures.append("capture is visually empty or unreadable")
    if len(pair_energy) >= 2 and frozen_ratio >= 0.95:
        failures.append("capture has no visible movement")
    return {
        "sampled_frames": len(frames),
        "black_frame_ratio": round(black_ratio, 4),
        "frozen_pair_ratio": round(frozen_ratio, 4),
        "motion_energy": round(sum(pair_energy) / len(pair_energy), 4) if pair_energy else 0.0,
        "edge_energy": round(edge_energy, 4),
        "failures": failures,
    }


def _render_cinematic_scroll(
    full_page_path: Path, output_dir: Path, slug: str, action: CaptureAction, sequence: int, *, source_url: str,
) -> CaptureArtifact | None:
    """Create an exact, crisp article scroll from a clean full-page capture.

    Browser video is reserved for real interactions (hover/click/product demos).
    For reading a page, moving a lossless full-page capture avoids compositor
    jitter, keeps text legible, and makes an intentional editorial scroll.
    """
    with Image.open(full_page_path) as image:
        original_width, original_height = image.size
    scaled_height = round(original_height * 1920 / max(1, original_width))
    if scaled_height <= 1140:
        return None
    available = scaled_height - 1080
    start = round(available * action.start_ratio)
    requested_end = round(available * action.end_ratio)
    # Keep a deliberate evidence move short enough that text is never a blur.
    end = max(0, min(available, start + max(-round(1080 * 1.15), min(round(1080 * 1.15), requested_end - start))))
    travel = end - start
    if abs(travel) < 24:
        return None
    duration = max(3.0, min(8.0, action.duration_seconds))
    hold = min(0.45, max(0.25, duration * 0.08))
    active = max(0.5, duration - hold * 2)
    # A cosine ease gives a short motion-blur-like feeling at speed without
    # applying a real blur that would make product names and source text fuzzy.
    y_expr = (
        f"{start}+{travel}*pow(sin(PI*clip((t-{hold:.3f})/{active:.3f},0,1)/2),2)"
    )
    destination = output_dir / f"{slug}-recording-{sequence:02d}.mp4"
    video_filter = (
        "scale=1920:-2:flags=lanczos,"
        f"crop=1920:1080:0:y='{y_expr}',"
        "unsharp=5:5:0.18:5:5:0,format=yuv420p"
    )
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", str(full_page_path),
        "-t", f"{duration:.3f}", "-vf", video_filter, "-an", "-r", "30",
        "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", "14",
        "-threads", str(FFMPEG_THREADS_PER_JOB), "-pix_fmt", "yuv420p", str(destination),
    ], check=True, capture_output=True, text=True)
    quality = _recording_quality(destination, expected_seconds=duration)
    quality["checks"].append("clean_source_capture")
    quality["stabilization"] = "lossless full-page pan with pixel-aligned cosine easing"
    return _artifact(
        "screen_recording", destination, "Cinematic clean source scroll", source_url=source_url,
        capture_mode="cinematic_scroll", quality=quality,
    )


def _trim_recording(raw_path: Path, destination: Path, target_seconds: float) -> None:
    if not 0 < target_seconds < float("inf"):
        raise ValueError("target recording duration must be finite and positive")
    total = _video_duration(raw_path)
    length = min(target_seconds, total)
    start = max(0.0, total - length - 0.15)
    subprocess.run([
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(raw_path), "-t", f"{length:.3f}",
        "-an", "-vf", _recording_filter(),
        "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", "14", "-threads", str(FFMPEG_THREADS_PER_JOB),
        "-r", "30", "-pix_fmt", "yuv420p", str(destination),
    ], check=True, capture_output=True, text=True)


def _recording_filter() -> str:
    """Normalize browser captures without adding synthetic camera movement.

    Preserve real captured frames: optical flow can warp text and cursors and
    cannot recover frames dropped by the recorder. Normalize timestamps only.
    """
    return (
        "setpts=PTS-STARTPTS,"
        "scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,"
        "crop=1920:1080,"
        "fps=30,"
        "unsharp=5:5:0.18:5:5:0,format=yuv420p"
    )


def _capture_recording(
    browser, url: str, output_dir: Path, slug: str, action: CaptureAction, sequence: int,
) -> CaptureArtifact:
    video_dir = output_dir / "recordings"
    video_dir.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
        record_video_dir=str(video_dir), record_video_size={"width": 1920, "height": 1080},
    )
    page = context.new_page()
    video = page.video
    _load_page(page, url, freeze_motion=False)
    _observe_page(page)
    _perform_motion(page, action)
    _assert_capture_is_clean(page, moment=f"after {action.kind} motion")
    final_url = page.url
    context.close()
    raw_path = video_dir / f"{slug}-{sequence:02d}-raw.webm"
    original_path = Path(video.path())
    video.save_as(str(raw_path))
    if original_path != raw_path:
        original_path.unlink(missing_ok=True)
    destination = output_dir / f"{slug}-recording-{sequence:02d}.mp4"
    _trim_recording(raw_path, destination, action.duration_seconds)
    raw_path.unlink(missing_ok=True)
    quality = _recording_quality(destination, expected_seconds=action.duration_seconds)
    quality["checks"].extend(["clean_dom_before", "clean_dom_after"])
    quality["stabilization"] = "deterministic browser motion + real-frame cadence normalization"
    return _artifact(
        "screen_recording", destination, action.label, source_url=final_url, capture_mode=action.kind,
        quality=quality,
    )


def _recording_cache_valid(entries: list[dict], output_dir: Path) -> bool:
    """Cache hits must retain current QC and refer to unchanged local files."""
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        name = entry.get("name", "")
        if not isinstance(name, str) or not name or Path(name).name != name:
            return False
        target = output_dir / name
        quality = entry.get("quality", {})
        if (not isinstance(quality, dict) or quality.get("status") != "accepted"
                or quality.get("readability_review_required") is not True
                or not target.is_file() or target.is_symlink()):
            return False
        try:
            if _sha256(target) != entry.get("sha256"):
                return False
        except OSError:
            return False
    return True


def capture_source(
    source: Source, output_dir: Path, *, record: bool = False,
    planner: CapturePlanner | None = None, visual_directions: list[str] | None = None,
) -> dict:
    """Capture baseline and model-directed assets while retaining deterministic fallbacks."""
    from .browser_director import fallback_plan

    output_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug(source)
    url = _safe_url(str(source.url))
    # Capture files are content-addressed by the normalized source slug. Reuse a
    # complete baseline on restart instead of reopening and rerecording a page.
    cached_viewport = output_dir / f"{slug}-viewport.png"
    cached_full = output_dir / f"{slug}-full.png"
    cache_manifest = output_dir / f"{slug}-capture-qc-v{CAPTURE_CACHE_VERSION}.json"
    cache_data: dict = {}
    if cache_manifest.is_file():
        try:
            cache_data = json.loads(cache_manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache_data = {}
    cache_key = hashlib.sha256(json.dumps({
        "url": url, "record": record, "directions": visual_directions or [],
        "planner": getattr(planner, "__qualname__", "fallback"),
    }, sort_keys=True).encode()).hexdigest()
    if (isinstance(cache_data, dict)
            and cache_data.get("schema_version") == CAPTURE_CACHE_VERSION
            and cache_data.get("request_hash") == cache_key
            and cached_viewport.is_file() and cached_full.is_file()
            and (not record or bool(cache_data.get("recordings")))
            and _recording_cache_valid(cache_data.get("recordings", []), output_dir)):
        cached_artifacts = [
            _artifact("viewport", cached_viewport, "Opening viewport", source_url=url, capture_mode="viewport"),
            _artifact("full_page", cached_full, "Full-page source record", source_url=url, capture_mode="full_page"),
        ]
        element_entries = {
            entry.get("name", ""): entry for entry in cache_data.get("elements", [])
        }
        for target in sorted(output_dir.glob(f"{slug}-element-*.png")):
            entry = element_entries.get(target.name, {})
            cached_artifacts.append(_artifact(
                "element", target, entry.get("label", "Cached evidence detail"),
                source_url=url, capture_mode=entry.get("capture_mode", "element"),
                candidate_id=entry.get("candidate_id", ""),
                visible_text=entry.get("visible_text", ""),
                quality=entry.get("quality", {}),
            ))
        for entry in cache_data.get("recordings", []):
            target = output_dir / entry.get("name", "")
            if not target.is_file():
                continue
            cached_artifacts.append(_artifact(
                "screen_recording", target, "Cached controlled page motion",
                source_url=url, capture_mode=entry.get("capture_mode", "cinematic_scroll"),
                quality={**entry["quality"], "cache_hit": True},
            ))
        cached_plan = fallback_plan(source)
        cached_record = CaptureRecord(
            source_id=source.id,
            requested_url=url,
            final_url=url,
            page_title=source.title,
            captured_at=datetime.now(timezone.utc),
            plan=cached_plan,
            artifacts=cached_artifacts,
            errors=[],
        )
        editorial_stills = [item.path for item in cached_artifacts if item.kind in {"viewport", "element"}]
        provenance_stills = [item.path for item in cached_artifacts if item.kind == "full_page"]
        recordings = [item.path for item in cached_artifacts if item.kind == "screen_recording"]
        return {
            "source_id": source.id,
            "screenshots": editorial_stills,
            "editorial_stills": editorial_stills,
            "provenance_stills": provenance_stills,
            "recording": recordings[0] if recordings else None,
            "recordings": recordings,
            "errors": [],
            "record": cached_record,
        }
    errors: list[str] = []
    artifacts: list[CaptureArtifact] = []
    plan = fallback_plan(source)
    observation = {"page_title": "", "final_url": url, "candidates": []}
    try:
        with sync_playwright() as playwright:
            launch_options = {
                "headless": True,
                "args": ["--disable-dev-shm-usage", "--no-sandbox"],
            }
            bundled_browser = Path(playwright.chromium.executable_path)
            if not bundled_browser.is_file():
                # Local Windows installs frequently have Chrome available even
                # when Playwright's versioned headless shell was not downloaded.
                # The stable channel preserves the same clean, isolated context.
                launch_options["channel"] = "chrome"
            browser = playwright.chromium.launch(**launch_options)
            try:
                captured_url = ""
                for candidate_url in _capture_urls(url):
                    context = browser.new_context(
                        viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
                    )
                    page = context.new_page()
                    try:
                        _load_page(page, candidate_url)
                        observation = _observe_page(page)
                        if planner:
                            try:
                                plan = planner(source, observation, visual_directions or [])
                            except Exception as exc:
                                errors.append(f"capture planning fallback: {type(exc).__name__}: {exc}")
                        artifacts.extend(_capture_stills(page, output_dir, slug, plan, errors))
                        captured_url = page.url
                        break
                    except (BlockedPageError, CaptureOverlayError) as exc:
                        errors.append(f"rejected capture candidate {candidate_url}: {exc}")
                    finally:
                        context.close()
                if captured_url and record:
                    full_page = next((Path(item.path) for item in artifacts if item.kind == "full_page"), None)
                    for sequence, action in enumerate(_motion_actions(plan), start=1):
                        try:
                            if action.kind == "scroll" and full_page:
                                cinematic = _render_cinematic_scroll(
                                    full_page, output_dir, slug, action, sequence, source_url=captured_url,
                                )
                                if cinematic:
                                    artifacts.append(cinematic)
                                    continue
                            artifacts.append(_capture_recording(browser, captured_url, output_dir, slug, action, sequence))
                        except Exception as exc:
                            errors.append(
                                f"{action.kind} recording failed: {type(exc).__name__}: {exc}"
                            )
                elif not captured_url:
                    errors.append("all capture candidates were blocked or unavailable; editorial assets omitted")
            finally:
                browser.close()
    except Exception as exc:
        errors.append(f"capture failed: {type(exc).__name__}: {exc}")

    record_data = CaptureRecord(
        source_id=source.id,
        requested_url=url,
        final_url=observation.get("final_url", ""),
        page_title=observation.get("page_title", ""),
        captured_at=datetime.now(timezone.utc),
        plan=plan,
        artifacts=artifacts,
        errors=errors,
    )
    if artifacts and not errors:
        element_manifest = [
            {
                "name": Path(item.path).name,
                "label": item.label,
                "capture_mode": item.capture_mode,
                "candidate_id": item.candidate_id,
                "visible_text": item.visible_text,
                "quality": item.quality,
            }
            for item in artifacts if item.kind == "element"
        ]
        recordings_manifest = [
            {"name": Path(item.path).name, "capture_mode": item.capture_mode,
             "sha256": _sha256(Path(item.path)), "quality": item.quality}
            for item in artifacts if item.kind == "screen_recording"
        ]
        cache_manifest.write_text(json.dumps({
            "schema_version": CAPTURE_CACHE_VERSION,
            "request_hash": cache_key,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "elements": element_manifest,
            "recordings": recordings_manifest,
        }, indent=2), encoding="utf-8")
    editorial_stills = [item.path for item in artifacts if item.kind in {"viewport", "element"}]
    provenance_stills = [item.path for item in artifacts if item.kind == "full_page"]
    recordings = [item.path for item in artifacts if item.kind == "screen_recording"]
    recording = recordings[0] if recordings else None
    return {
        "source_id": source.id,
        "screenshots": editorial_stills,
        "editorial_stills": editorial_stills,
        "provenance_stills": provenance_stills,
        "recording": recording,
        "recordings": recordings,
        "errors": errors,
        "record": record_data,
    }


def capture_sources(
    sources: list[Source], output_dir: Path, max_recordings: int = 6,
    *, planner: CapturePlanner | None = None,
    visual_directions_by_source: dict[str, list[str]] | None = None,
) -> list[dict]:
    directions = visual_directions_by_source or {}
    def capture_indexed(item: tuple[int, Source]) -> dict:
        index, source = item
        return capture_source(
            source, output_dir, record=index < max_recordings, planner=planner,
            visual_directions=directions.get(source.id, []),
        )
    with ThreadPoolExecutor(max_workers=min(CAPTURE_PARALLELISM, max(1, len(sources)))) as executor:
        return list(executor.map(capture_indexed, enumerate(sources)))
