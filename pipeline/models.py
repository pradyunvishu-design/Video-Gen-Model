"""Versioned contracts shared by the CLI, worker API, and n8n workflows."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator
from .script_profiles import ScriptProfile


class Source(BaseModel):
    id: str
    title: str
    url: HttpUrl
    publisher: str = ""
    author: str = ""
    published_at: datetime | None = None
    source_type: Literal["primary", "secondary", "community", "unknown"] = "unknown"
    text: str = ""
    summary: str = ""
    cluster_id: str = ""
    entities: list[str] = Field(default_factory=list)
    media_urls: list[HttpUrl] = Field(default_factory=list)
    capture_status: Literal["pending", "complete", "failed", "skipped"] = "pending"
    trend_score: float = 0
    signal_role: Literal[
        "primary_evidence", "independent_reporting", "newsletter_lead", "community_signal", "unknown"
    ] = "unknown"
    category: str = ""
    importance_score: float = 0


class Claim(BaseModel):
    id: str
    text: str
    source_ids: list[str]
    disputed: bool = False
    kind: Literal["fact", "number", "quote", "commentary"] = "fact"


class Brief(BaseModel):
    title: str
    thesis: str
    episode_format: Literal[
        "roundup", "weekly_roundup", "deep_dive", "tool_test", "open_source_spotlight", "trend_explainer"
    ]
    source_ids: list[str]
    claim_ids: list[str]
    why_now: str
    visual_opportunities: list[str] = Field(default_factory=list)
    approved: bool = False
    review_notes: str = ""


class DeliveryDirection(BaseModel):
    pace: Literal["slow", "normal", "quick"] = "normal"
    energy: Literal["restrained", "normal", "emphatic"] = "normal"
    pause_before_ms: int = Field(default=0, ge=0, le=2500)
    pause_after_ms: int = Field(default=350, ge=0, le=2500)
    emphasis_words: list[str] = Field(default_factory=list, max_length=5)


class Pronunciation(BaseModel):
    term: str
    spoken_as: str


class ScriptBeat(BaseModel):
    id: str
    narration: str
    claim_ids: list[str] = Field(default_factory=list)
    purpose: Literal[
        "hook", "show_intro", "headlines", "story_intro", "context", "test_setup", "model_test", "observation", "evidence",
        "analysis", "limitation", "comparison", "transition", "implication", "verdict",
        "weekly_recap", "disclosure", "outro",
    ]
    visual_direction: str
    source_ids: list[str] = Field(default_factory=list)
    delivery: DeliveryDirection = Field(default_factory=DeliveryDirection)
    pronunciations: list[Pronunciation] = Field(default_factory=list)


class Script(BaseModel):
    title: str
    description: str
    tags: list[str]
    thumbnail_text: str
    beats: list[ScriptBeat]
    disclosure: str = "Produced with AI-assisted research and a consistent synthetic narrator; sources are linked for review."

    @field_validator("thumbnail_text")
    @classmethod
    def thumbnail_copy_is_readable(cls, value: str) -> str:
        count = len(value.split())
        if not 3 <= count <= 5:
            raise ValueError("thumbnail text must contain 3-5 words")
        return value

    @property
    def narration(self) -> str:
        return "\n\n".join(beat.narration for beat in self.beats)

    @property
    def word_count(self) -> int:
        return len(self.narration.split())


class VisualAnnotation(BaseModel):
    """A normalized, evidence-preserving emphasis region on a captured source image."""

    style: Literal["zoom", "underline", "outline", "spotlight", "callout", "arrow", "cursor"]
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    label: str = Field(default="", max_length=160)
    # Exact text copied from the captured DOM when the cue targets words.  This
    # is deliberately separate from editorial copy so a renderer cannot draw a
    # plausible-looking underline beneath text that was never on the page.
    target_text: str = Field(default="", max_length=240)
    verification_method: Literal["", "dom-range", "vision-verified", "element-boundary", "ocr-words"] = ""
    start_seconds: float = Field(default=0.25, ge=0)
    end_seconds: float | None = Field(default=None, gt=0)
    color: str = "#65D6FF"
    rationale: str = ""

    @model_validator(mode="after")
    def region_stays_inside_frame(self) -> "VisualAnnotation":
        if self.x + self.width > 1.0001 or self.y + self.height > 1.0001:
            raise ValueError("annotation region must stay inside the normalized source image")
        return self


class Shot(BaseModel):
    id: str
    beat_id: str
    asset_type: Literal[
        "screenshot", "screen_recording", "official_demo", "generated_image",
        "generated_video", "concept_animation", "motion_graphic", "chapter_card", "chart"
    ]
    source_id: str | None = None
    prompt: str = ""
    # Sentence-level visual contract used by deterministic alignment QC.
    semantic_target: str = ""
    alignment_terms: list[str] = Field(default_factory=list, max_length=24)
    alignment_score: float | None = Field(default=None, ge=0, le=100)
    asset_fingerprint: str = ""
    reuse_group: str = ""
    asset_path: str = ""
    start_seconds: float = 0
    duration_seconds: float = Field(default=6, gt=0, le=30)
    source_in_seconds: float = Field(default=0, ge=0)
    focus_x: float = Field(default=0.5, ge=0, le=1)
    focus_y: float = Field(default=0.5, ge=0, le=1)
    motion_style: Literal[
        "locked", "push_in", "pull_out", "pan_left", "pan_right", "float"
    ] = "push_in"
    easing: Literal["linear", "ease_in_out", "ease_out"] = "ease_in_out"
    transition: Literal["cut", "dissolve", "dip"] = "cut"
    presentation: Literal["full_bleed", "editorial_card"] = "full_bleed"
    motion_template: Literal[
        "auto", "ui_stage", "orbit_map", "step_flow", "comparison",
        "stat_reveal", "evidence_focus", "chapter_title", "news_intro",
        "list_reveal", "timeline", "prompt_anatomy", "news_workflow",
        "seedance_editorial",
    ] = "auto"
    annotations: list[VisualAnnotation] = Field(default_factory=list, max_length=2)
    rights_note: str = ""
    visual_category: Literal[
        "auto", "youtube_broll", "article_evidence", "motion_graphics", "miscellaneous"
    ] = "auto"
    fallback_reason: Literal[
        "", "no_relevant_rights_cleared_footage", "chapter_transition",
        "explanatory_data_visualization",
    ] = ""


class MediaAsset(BaseModel):
    id: str
    kind: str
    path: str
    source_id: str | None = None
    magic_hour_project_id: str | None = None
    credits: int = 0
    sha256: str = ""
    qc_status: Literal["pending", "passed", "failed", "rejected"] = "pending"
    qc_notes: list[str] = Field(default_factory=list)


class CaptureAction(BaseModel):
    kind: Literal[
        "viewport", "element", "scroll", "hover", "focus", "click_reveal", "video_playback"
    ]
    candidate_id: str = ""
    label: str = ""
    start_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    end_ratio: float = Field(default=0.85, ge=0.0, le=1.0)
    duration_seconds: float = Field(default=6.0, ge=1.0, le=8.0)
    settle_seconds: float = Field(default=0.6, ge=0.2, le=2.0)


class CapturePlan(BaseModel):
    source_id: str
    rationale: str = ""
    actions: list[CaptureAction] = Field(default_factory=list, max_length=8)


class CaptureArtifact(BaseModel):
    kind: Literal["viewport", "full_page", "element", "screen_recording"]
    path: str
    label: str = ""
    sha256: str = ""
    source_url: str = ""
    capture_mode: str = ""
    candidate_id: str = ""
    # Text actually visible inside the captured DOM element.  Narration and
    # source titles must never be substituted for this field.
    visible_text: str = ""
    muted: bool = True
    # Kept with the asset, rather than only in a log, so a reviewer can see
    # why a browser recording was accepted and whether it was re-used.
    quality: dict[str, Any] = Field(default_factory=dict)


class CaptureRecord(BaseModel):
    source_id: str
    requested_url: str
    final_url: str = ""
    page_title: str = ""
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    plan: CapturePlan | None = None
    artifacts: list[CaptureArtifact] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ReviewState(BaseModel):
    slate_status: Literal["pending", "approved", "revision_requested", "skipped"] = "pending"
    final_status: Literal["pending", "approved", "revision_requested"] = "pending"
    notes: list[str] = Field(default_factory=list)


class EpisodeProject(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal["2.0"] = "2.0"
    episode_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_date: str
    status: str = "draft"
    episode: dict[str, Any] = Field(default_factory=dict)
    brief: Brief | None = None
    sources: list[Source] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    editorial_plan: dict[str, Any] = Field(default_factory=dict)
    script_profile: ScriptProfile | None = None
    script: Script | None = None
    shots: list[Shot] = Field(default_factory=list)
    media: list[MediaAsset] = Field(default_factory=list)
    captures: list[CaptureRecord] = Field(default_factory=list)
    narration: dict[str, Any] = Field(default_factory=dict)
    timeline: dict[str, Any] = Field(default_factory=dict)
    rights: list[dict[str, Any]] = Field(default_factory=list)
    costs: dict[str, int | float] = Field(default_factory=lambda: {"magic_hour_credits": 0})
    qc: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    review: ReviewState = Field(default_factory=ReviewState)

    @model_validator(mode="after")
    def validate_references(self) -> "EpisodeProject":
        source_ids = {source.id for source in self.sources}
        for claim in self.claims:
            missing = set(claim.source_ids) - source_ids
            if missing:
                raise ValueError(f"claim {claim.id} references unknown sources: {sorted(missing)}")
        claim_ids = {claim.id for claim in self.claims}
        if self.script:
            for beat in self.script.beats:
                missing_claims = set(beat.claim_ids) - claim_ids
                missing_sources = set(beat.source_ids) - source_ids
                if missing_claims or missing_sources:
                    raise ValueError(
                        f"beat {beat.id} has invalid references: claims={sorted(missing_claims)}, "
                        f"sources={sorted(missing_sources)}"
                    )
        return self
