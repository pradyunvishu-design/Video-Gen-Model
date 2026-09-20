"""Validation and rendering bridge for the JSON-driven editorial Remotion system."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .creative_profile import HERMES_PROOF_FIRST, review_proof_first_spec
from .brand_assets import motion_brand_theme
from .editorial_style import PAPER, SLATE, is_forbidden_editorial_color, safe_editorial_accent
from .art_direction import direct_scene
from .models import EpisodeProject, ScriptBeat, Shot
from .training_loop import lint_visual_spec
from .visual_style_profile import (
    DEFAULT_VISUAL_STYLE_PROFILE,
    composition_family,
    load_visual_style_profile,
    pattern_family,
    route_pattern,
    semantic_intent,
)


ALLOWED_SCENES = {"title", "chat", "graph", "source", "activity", "compare", "timeline", "terminal", "stack"}
ALLOWED_ANCHORS = {"left", "center", "right"}
MOTION_PATTERNS_BY_SCENE = {
    "title": ("title-cold-open", "title-number-hook", "title-quote-reveal", "title-chapter-reset", "title-logo-verdict", "title-final-takeaway", "title-brand-verdict-lockup", "title-keynote-stage"),
    "chat": ("chat-peer-debate", "chat-agent-handoff", "chat-correction-thread", "chat-async-status", "chat-approval-gate", "chat-decision-log", "chat-brand-review-relay", "chat-studio-podcast"),
    "graph": ("graph-hub-spoke", "graph-dependency-chain", "graph-agent-network", "graph-request-response", "graph-loop-cycle", "graph-branching-plan", "graph-brand-capability-ring"),
    "source": ("source-browser-proof", "source-paper-callout", "source-repo-metrics", "source-ui-feature", "source-demo-crop", "source-before-after-ui", "source-ui-focus-corridor"),
    "activity": ("activity-task-queue", "activity-checklist-progress", "activity-status-ladder", "activity-error-recovery", "activity-verification-pass", "activity-benchmark-run", "activity-ui-plan-to-progress"),
    "compare": ("compare-claim-proof", "compare-old-new", "compare-side-by-side", "compare-tradeoff-grid", "compare-promise-reality", "compare-scorecard", "compare-brand-prompt-fork"),
    "timeline": ("timeline-launch-sequence", "timeline-causality-chain", "timeline-iteration-history", "timeline-rollback-path", "timeline-week-recap", "timeline-checkpoint-run", "timeline-ui-agent-handoff"),
    "terminal": ("terminal-command-run", "terminal-streaming-output", "terminal-diff-apply", "terminal-test-suite", "terminal-tool-call", "terminal-file-tree", "terminal-ui-command-to-diff"),
    "stack": ("stack-context-layers", "stack-architecture", "stack-source-rank", "stack-model-ladder", "stack-workflow-stages", "stack-cost-layers", "stack-ui-proof-stack"),
}
MOTION_PATTERN_IDS = {pattern for patterns in MOTION_PATTERNS_BY_SCENE.values() for pattern in patterns}


@dataclass
class EditorialSpecReport:
    passed: bool
    duration_seconds: float
    scene_count: int
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    motion_score: int = 0
    training_lint: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "duration_seconds": self.duration_seconds,
            "scene_count": self.scene_count,
            "warnings": self.warnings,
            "errors": self.errors,
            "motion_score": self.motion_score,
            "training_lint": self.training_lint,
        }


def _run_length(values: list[str]) -> int:
    longest = current = 0
    previous = None
    for value in values:
        current = current + 1 if value == previous else 1
        longest = max(longest, current)
        previous = value
    return longest


def validate_editorial_spec(spec: dict[str, Any], public_dir: Path) -> EditorialSpecReport:
    scenes = spec.get("scenes") or []
    errors: list[str] = []
    warnings: list[str] = []
    if not spec.get("episodeId"):
        errors.append("episodeId is required")
    if not scenes:
        errors.append("at least one scene is required")
    ids = [str(scene.get("id", "")) for scene in scenes]
    if len(ids) != len(set(ids)):
        errors.append("scene ids must be unique")
    for index, scene in enumerate(scenes):
        label = scene.get("id") or f"scene[{index}]"
        if scene.get("kind") not in ALLOWED_SCENES:
            errors.append(f"{label}: unsupported scene kind")
        motion_pattern = scene.get("motionPattern")
        if motion_pattern and motion_pattern not in MOTION_PATTERN_IDS:
            errors.append(f"{label}: unsupported motion pattern {motion_pattern}")
        if motion_pattern and motion_pattern not in MOTION_PATTERNS_BY_SCENE.get(str(scene.get("kind")), ()):
            errors.append(f"{label}: motion pattern does not match scene kind")
        if scene.get("anchor") not in ALLOWED_ANCHORS:
            errors.append(f"{label}: anchor must be left, center, or right")
        if float(scene.get("durationSeconds", 0)) < 2:
            errors.append(f"{label}: scenes shorter than two seconds are not readable")
        if scene.get("kind") in {"timeline", "terminal", "stack"} and len(scene.get("items") or []) < 3:
            errors.append(f"{label}: {scene.get('kind')} scenes require at least three items")
        if scene.get("kind") == "graph":
            for node in scene.get("nodes") or []:
                if float(node.get("y", 0.5)) > 0.8:
                    errors.append(f"{label}: graph node {node.get('id', '')} is below the safe zone")
        if scene.get("kind") == "compare":
            if not str(scene.get("claim", "")).strip() or not str(scene.get("evidence", "")).strip():
                errors.append(f"{label}: compare scenes require both claim and evidence")
            if len(str(scene.get("title", "")).split()) > 10:
                warnings.append(f"{label}: comparison verdict is too long for the verdict band")
        if scene.get("kind") == "chat" and len(scene.get("messages") or []) < 2:
            warnings.append(f"{label}: chat scene has fewer than two verified messages; route to activity instead")
        if scene.get("kind") == "source":
            asset = str(scene.get("sourceAsset", ""))
            if not asset:
                errors.append(f"{label}: source scenes require sourceAsset")
            elif not asset.startswith(("http://", "https://")) and not (public_dir / asset).is_file():
                errors.append(f"{label}: missing source asset {asset}")
            if not scene.get("sourceLabel"):
                errors.append(f"{label}: source scenes require provenance label")
            if not str(scene.get("sourceUrl", "")).startswith(("http://", "https://")):
                errors.append(f"{label}: source scenes require an http(s) provenance URL")
            if not any(str(evidence_id).strip() for evidence_id in scene.get("evidenceIds") or []):
                errors.append(f"{label}: source scenes require at least one evidence ID")
            focus = scene.get("sourceFocus")
            if focus:
                x = float(focus.get("x", 0))
                y = float(focus.get("y", 0))
                width = float(focus.get("width", 0))
                height = float(focus.get("height", 0))
                if x + width > 1 or y + height > 1:
                    errors.append(f"{label}: source focus extends outside the captured frame")
                if not str(focus.get("label", "")).strip():
                    errors.append(f"{label}: source focus requires a narrated evidence label")
        for logo in scene.get("logos") or []:
            asset = str(logo.get("src", ""))
            if asset and not asset.startswith(("http://", "https://")) and not (public_dir / asset).is_file():
                errors.append(f"{label}: missing logo asset {asset}")
        for message in scene.get("messages") or []:
            asset = str(message.get("logo", ""))
            if asset and not asset.startswith(("http://", "https://")) and not (public_dir / asset).is_file():
                errors.append(f"{label}: missing message logo {asset}")
        brand_theme = scene.get("brandTheme") or {}
        if is_forbidden_editorial_color(scene.get("accent")):
            errors.append(f"{label}: decorative yellow and purple accents are forbidden by the premium palette")
        if is_forbidden_editorial_color(brand_theme.get("accent")):
            errors.append(f"{label}: brand color may remain in the official mark but not in editorial chrome")
        avatar_status = str(brand_theme.get("avatarStatus") or "")
        if avatar_status == "official-mascot" and not str(brand_theme.get("officialSourceUrl") or "").startswith(("http://", "https://")):
            errors.append(f"{label}: official mascot claims require an authoritative source URL")
        if avatar_status == "channel-owned-editorial-avatar" and brand_theme.get("markTreatment") != "official-asset-unmodified":
            errors.append(f"{label}: editorial avatars must preserve the official mark")
    if _run_length([str(scene.get("motionPattern") or scene.get("kind")) for scene in scenes]) > 2:
        warnings.append("more than two consecutive scenes use the same visual grammar")
    if _run_length([str(scene.get("anchor")) for scene in scenes]) > 2:
        warnings.append("more than two consecutive scenes use the same anchor")
    profile_review = review_proof_first_spec(spec, public_dir)
    errors.extend(profile_review["failures"])
    warnings.extend(profile_review["warnings"])
    training_lint = lint_visual_spec(spec)
    errors.extend(training_lint["failures"])
    warnings.extend(training_lint["warnings"])
    transition_seconds = {"hard-cut": 0.0, "fade": 0.2, "handoff": 8 / 30}
    duration = sum(float(scene.get("durationSeconds", 0)) for scene in scenes) - sum(
        transition_seconds.get(str(scene.get("transitionAfter", "fade")), 0.2)
        for scene in scenes[:-1]
    )
    kind_diversity = min(1.0, len({str(scene.get("kind")) for scene in scenes}) / max(1, min(6, len(scenes))))
    pattern_diversity = min(1.0, len({str(scene.get("motionPattern") or scene.get("kind")) for scene in scenes}) / max(1, min(10, len(scenes))))
    anchor_diversity = min(1.0, len({str(scene.get("anchor")) for scene in scenes}) / 3)
    repetition_penalty = .15 * len(warnings)
    source_bonus = .08 if any(scene.get("kind") == "source" for scene in scenes) else 0
    score = round(max(0, min(1, .42 * kind_diversity + .28 * pattern_diversity + .22 * anchor_diversity + source_bonus - repetition_penalty)) * 100)
    if spec.get("creativeProfile") == HERMES_PROOF_FIRST:
        score = min(score, int(profile_review["score"]))
    return EditorialSpecReport(
        not errors, round(duration, 3), len(scenes), warnings, errors, score, training_lint,
    )


def _stage_asset(path_value: str, public_dir: Path) -> str:
    if not path_value:
        return ""
    source = Path(path_value)
    if not source.is_file():
        return path_value if path_value.startswith(("http://", "https://")) else ""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    destination = public_dir / "runtime" / "editorial" / f"{digest}{source.suffix.lower()}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or destination.stat().st_size != source.stat().st_size:
        shutil.copy2(source, destination)
    return destination.relative_to(public_dir).as_posix()


def _scene_kind(beat: ScriptBeat, shot: Shot) -> str:
    direction = f"{beat.visual_direction} {shot.prompt}".lower()
    if shot.asset_type in {"screenshot", "screen_recording", "official_demo"} and shot.asset_path:
        return "source"
    if any(term in direction for term in ("timeline", "chronology", "release sequence", "history", "dated")):
        return "timeline"
    if any(term in direction for term in ("terminal", "command", "console", "run output", "code block")):
        return "terminal"
    if any(term in direction for term in ("stack", "layers", "hierarchy", "ranked", "architecture")):
        return "stack"
    if any(term in direction for term in ("chat", "conversation", "message thread", "agent discussion")):
        return "chat"
    if beat.purpose == "comparison":
        return "compare"
    if beat.purpose in {"evidence", "test_setup", "observation", "model_test"}:
        return "activity"
    if beat.purpose in {"analysis", "implication", "limitation"}:
        return "graph"
    return "title"


def _accent(text: str, kind: str) -> str:
    theme = motion_brand_theme(text)
    if theme:
        return safe_editorial_accent(theme["accent"])
    lowered = text.lower()
    if "minimax" in lowered:
        return "#FF6673"
    if "claude" in lowered or "anthropic" in lowered:
        return "#D97757"
    if "gemini" in lowered or "google" in lowered:
        return "#6F78D8"
    if kind in {"activity", "compare"}:
        return "#FFFFFF"
    return PAPER


def _motion_pattern(kind: str, context: str) -> str:
    """Choose a deterministic information pattern, not a decorative animation preset."""
    lowered = context.lower()
    keyword_routes = {
        "terminal": (("command to diff", "command becomes", "changed-files proof"), "terminal-ui-command-to-diff", ("diff", "patch", "changed file"), "terminal-diff-apply", ("test", "pytest", "benchmark"), "terminal-test-suite", ("tool call", "function call", "mcp"), "terminal-tool-call", ("tree", "files", "repository"), "terminal-file-tree", ("stream", "log", "progress"), "terminal-streaming-output"),
        "source": (("focus corridor", "reading corridor", "exact interface"), "source-ui-focus-corridor", ("paper", "study", "arxiv"), "source-paper-callout", ("github", "repository", "stars"), "source-repo-metrics", ("before", "after"), "source-before-after-ui", ("demo", "generation"), "source-demo-crop"),
        "chat": (("builder", "reviewer", "cross-review", "review relay"), "chat-brand-review-relay", ("handoff", "delegate"), "chat-agent-handoff", ("correct", "wrong"), "chat-correction-thread", ("approve", "review"), "chat-approval-gate", ("status", "parallel"), "chat-async-status"),
        "graph": (("capability ring", "product ecosystem", "verified capabilities"), "graph-brand-capability-ring", ("loop", "iterate"), "graph-loop-cycle", ("agent", "fleet"), "graph-agent-network", ("dependency", "chain"), "graph-dependency-chain", ("branch", "decision"), "graph-branching-plan"),
        "compare": (("shared prompt", "same task", "head-to-head"), "compare-brand-prompt-fork", ("old", "new"), "compare-old-new", ("promise", "reality"), "compare-promise-reality", ("score", "rank"), "compare-scorecard", ("versus", " vs "), "compare-side-by-side"),
        "timeline": (("task packet", "passes between", "agent handoff"), "timeline-ui-agent-handoff", ("week", "recap"), "timeline-week-recap", ("rollback", "failure"), "timeline-rollback-path", ("cause", "effect"), "timeline-causality-chain", ("version", "iteration"), "timeline-iteration-history"),
        "activity": (("plan item", "plan to progress", "progress row"), "activity-ui-plan-to-progress", ("error", "recover"), "activity-error-recovery", ("verify", "check"), "activity-verification-pass", ("benchmark", "measure"), "activity-benchmark-run", ("queue", "task"), "activity-task-queue"),
        "stack": (("official claim", "tested output", "independent check"), "stack-ui-proof-stack", ("source", "evidence"), "stack-source-rank", ("model", "capability"), "stack-model-ladder", ("cost", "credit"), "stack-cost-layers", ("architecture", "layer"), "stack-architecture"),
        "title": (("criterion-specific verdict", "brand verdict", "product verdict"), "title-brand-verdict-lockup", ("chapter", "next"), "title-chapter-reset", ("verdict", "winner"), "title-logo-verdict", ("quote", "said"), "title-quote-reveal", ("final", "takeaway"), "title-final-takeaway"),
    }
    routes = keyword_routes.get(kind, ())
    for index in range(0, len(routes), 2):
        terms, pattern = routes[index], routes[index + 1]
        if any(term in lowered for term in terms):
            return pattern
    choices = MOTION_PATTERNS_BY_SCENE[kind]
    digest = int(hashlib.sha256(context.encode("utf-8")).hexdigest()[:8], 16)
    return choices[digest % len(choices)]


def _items(text: str) -> list[str]:
    parts = [part.strip(" .") for part in re.split(r"[,;]|\bthen\b|\bversus\b", text, flags=re.I) if part.strip()]
    return (parts + ["Primary source", "Independent check", "Editorial conclusion"])[:4]


def build_editorial_spec(project: EpisodeProject, public_dir: Path) -> dict[str, Any]:
    """Convert a verified EpisodeProject into deterministic full-episode Remotion props."""
    if not project.script:
        raise ValueError("EpisodeProject requires a script before editorial motion planning")
    sources = {source.id: source for source in project.sources}
    claims = {claim.id: claim for claim in project.claims}
    shots_by_beat: dict[str, list[Shot]] = {}
    for shot in project.shots:
        shots_by_beat.setdefault(shot.beat_id, []).append(shot)
    scenes: list[dict[str, Any]] = []
    profile_version = str(project.episode.get("visual_style_profile") or DEFAULT_VISUAL_STYLE_PROFILE)
    visual_profile = load_visual_style_profile(profile_version)
    fidelity_overrides = project.editorial_plan.get("fidelity_visual_overrides") or {}
    prior_patterns: list[str] = []
    prior_compositions: list[str] = []
    prior_concepts: list[str] = []
    anchors = ["left", "right", "center", "left", "center", "right"]
    for beat in project.script.beats:
        beat_shots = shots_by_beat.get(beat.id) or [Shot(
            id=f"{beat.id}-editorial", beat_id=beat.id, asset_type="motion_graphic",
            prompt=beat.visual_direction, duration_seconds=max(3, min(8, len(beat.narration.split()) / 2.6)),
        )]
        for shot_index, shot in enumerate(beat_shots):
            kind = _scene_kind(beat, shot)
            source_id = shot.source_id or (beat.source_ids[0] if beat.source_ids else "")
            source = sources.get(source_id)
            annotation = shot.annotations[0] if shot.annotations else None
            claim_texts = [claims[claim_id].text for claim_id in beat.claim_ids if claim_id in claims]
            context = " ".join([beat.narration, beat.visual_direction, source.title if source else ""])
            intent = semantic_intent(beat.purpose, beat.narration)
            pattern = _motion_pattern(kind, context)
            if visual_profile:
                routed = route_pattern(
                    intent,
                    available_kinds={kind},
                    prior_patterns=prior_patterns,
                    prior_compositions=prior_compositions,
                    profile=visual_profile,
                )
                if pattern_family(routed) == kind:
                    pattern = routed
            composition = composition_family(pattern)
            evidence_ids = list(dict.fromkeys(
                evidence_id for evidence_id in [source_id, *beat.claim_ids] if evidence_id
            ))
            scene = {
                "id": f"{beat.id}-{shot_index + 1}",
                "kind": kind,
                "motionPattern": pattern,
                "durationSeconds": round(max(2, min(20, shot.duration_seconds)), 3),
                "chapter": beat.purpose.replace("_", " ").upper()[:42],
                "title": (shot.prompt or beat.visual_direction or beat.purpose).strip()[:120],
                "subtitle": beat.narration.strip()[:220],
                "anchor": anchors[len(scenes) % len(anchors)],
                "accent": _accent(context, kind),
                "logos": [], "messages": [], "nodes": [], "edges": [],
                "items": _items(beat.visual_direction),
                "sourceAsset": _stage_asset(shot.asset_path, public_dir),
                "sourceLabel": ((source.publisher if source else "") or "PRIMARY SOURCE")[:60],
                "sourceUrl": (str(source.url) if source else "")[:180],
                "evidenceIds": evidence_ids,
                "sourceStartSeconds": round(max(0, shot.source_in_seconds), 3),
                "sourceObjectPosition": "50% 50%" if fidelity_overrides else "50% 16%",
                "sourceFocus": ({
                    "x": annotation.x, "y": annotation.y, "width": annotation.width,
                    "height": annotation.height, "label": annotation.label,
                } if annotation else None),
                "claim": (claim_texts[0] if claim_texts else beat.narration)[:120],
                "evidence": (" ".join(claim_texts[1:]) or beat.narration)[:160],
            }
            art_direction = direct_scene(
                scene_id=scene["id"], kind=kind, intent=intent, context=context,
                accent=scene["accent"], prior_concepts=prior_concepts,
            )
            scene["artDirection"] = art_direction
            theme = motion_brand_theme(context)
            if theme:
                safe_theme = dict(theme)
                safe_theme["officialMarkAccent"] = safe_theme.get("accent")
                safe_theme["accent"] = safe_editorial_accent(str(safe_theme.get("accent") or SLATE))
                safe_theme["accentScope"] = "official-mark-only"
                scene["brandTheme"] = safe_theme
            if visual_profile:
                body_px = int(visual_profile["typography"]["minimumBodyPx"])
                label_px = int(visual_profile["typography"]["minimumLabelPx"])
                if fidelity_overrides.get("typography_profile") == "large_editorial":
                    body_px = max(body_px, 30)
                    label_px = max(label_px, 20)
                maximum_items = max(1, int(fidelity_overrides.get("max_information_items", 4)))
                scene["items"] = scene["items"][:maximum_items]
                scene.update({
                    "semanticIntent": intent,
                    "compositionFamily": composition,
                    "proofDominance": float(visual_profile["dominance"][kind]),
                    "bodyTextPx": body_px,
                    "labelTextPx": label_px,
                    "visualStates": ["context", "proof", "editorial-consequence"],
                    "meaningfulStateChangeSeconds": float(
                        fidelity_overrides.get("meaningful_state_change_seconds", 2.5)
                    ),
                    "annotationPurpose": annotation.label if annotation else "",
                    "transitionReason": "argument changes to the next verified beat",
                    "transitionAfter": "hard-cut",
                    "furnitureIds": [],
                })
            if kind == "graph":
                labels = _items(beat.visual_direction)[:3]
                scene["nodes"] = [
                    {"id": "idea", "label": "CORE IDEA", "color": scene["accent"], "x": .2, "y": .5},
                    *[
                        {"id": f"point-{i}", "label": label[:36].upper(), "color": "#F2F1ED", "x": .78, "y": .25 + i * .25}
                        for i, label in enumerate(labels)
                    ],
                ]
                scene["edges"] = [["idea", f"point-{i}"] for i in range(len(labels))]
            scenes.append(scene)
            prior_patterns.append(pattern)
            prior_compositions.append(composition)
            prior_concepts.append(art_direction["conceptFamily"])
    narration_path = str(project.narration.get("master_path") or project.narration.get("path") or "")
    result = {
        "episodeId": project.episode_id,
        "creativeProfile": str(project.episode.get("creative_profile") or "default"),
        "seriesName": str(project.episode.get("series_name") or "AI NEWS / FIELD NOTES")[:42],
        "footer": "SOURCE FIRST · EXPLANATION SECOND",
        "audioSrc": _stage_asset(narration_path, public_dir),
        "audioProfile": {
            "narrationGainDb": -1,
            "musicSrc": str(project.episode.get("music_src") or ""),
            "musicGainDb": -28,
        },
        "captions": project.timeline.get("captions") or [],
        "scenes": scenes,
    }
    if visual_profile:
        result["visualStyleProfileVersion"] = profile_version
        result["visualStyleProfile"] = visual_profile
    if fidelity_overrides:
        result["fidelityVisualOverrides"] = fidelity_overrides
    return result


def write_editorial_spec(project: EpisodeProject, destination: Path, public_dir: Path) -> Path:
    spec = build_editorial_spec(project, public_dir)
    report = validate_editorial_spec(spec, public_dir)
    if not report.passed:
        raise ValueError("Generated editorial spec failed validation:\n" + "\n".join(report.errors))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination


def render_editorial_spec(spec_path: Path, output_path: Path, project_dir: Path) -> Path:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    report = validate_editorial_spec(spec, project_dir / "public")
    if not report.passed:
        raise ValueError("Invalid editorial spec:\n" + "\n".join(report.errors))
    executable = project_dir / "node_modules" / ".bin" / ("remotion.cmd" if os.name == "nt" else "remotion")
    if not executable.is_file():
        raise FileNotFoundError(f"Remotion executable not found: {executable}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    composition = (
        "ProofFirstNarratedShort1080"
        if spec.get("creativeProfile") == HERMES_PROOF_FIRST and report.duration_seconds <= 45
        else "EditorialEpisode1080"
    )
    rate_control = ["--video-bitrate=4M"] if composition == "ProofFirstNarratedShort1080" else ["--crf=18"]
    command = [
        str(executable), "render", "src/index.ts", composition, str(output_path.resolve()),
        f"--props={spec_path.resolve()}", "--codec=h264", *rate_control, "--scale=0.5",
        "--pixel-format=yuv420p", "--color-space=bt709", "--image-format=png", "--concurrency=8",
    ]
    browser = shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("chromium")
    if browser:
        command.append(f"--browser-executable={browser}")
    process = subprocess.run(command, cwd=project_dir, capture_output=True, text=True, timeout=3600)
    if process.returncode:
        tail = "\n".join((process.stdout + "\n" + process.stderr).splitlines()[-40:])
        raise RuntimeError(f"Editorial Remotion render failed:\n{tail}")
    if not output_path.is_file() or output_path.stat().st_size < 1024:
        raise RuntimeError("Remotion returned no usable video")
    return output_path
