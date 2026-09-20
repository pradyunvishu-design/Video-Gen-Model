"""Run the independent oral-edit gate for the MiniMax H3 episode."""
from __future__ import annotations

import json
from datetime import date

from pipeline.editorial import review_script_quality
from pipeline.models import Brief, Claim, EpisodeProject, Script, ScriptBeat, Source
from scripts.build_h3_10m_episode import BEATS, EPISODE_ID, RUN_DIR, SOURCES


PURPOSES = {
    "hook": "hook",
    "what_it_is": "context",
    "native_audio": "evidence",
    "open_release": "context",
    "comfyui": "evidence",
    "hardware": "limitation",
    "quality": "evidence",
    "resolution": "limitation",
    "not_fully_local": "limitation",
    "community": "implication",
    "workflow": "analysis",
    "who_for": "analysis",
    "why_now": "implication",
    "creator_test": "test_setup",
    "sample_limits": "limitation",
    "license": "context",
    "decision": "analysis",
    "verdict": "verdict",
}

VISUAL_PROOF = {
    "quality": "Play the official starship sample full-screen. Time subtle zoom callouts to the silver hair, red collar, dark uniform, and cool window light as each is named. Then cut to the official dinner-table sample and call out the foreground bowl, rising steam, and warm side light.",
    "resolution": "Show MiniMax's matched official 768p and 2K outputs with source labels; do not imply a pixel-for-pixel test beyond the published comparison.",
    "community": "Show the dated community source page and label both add-ons UNVERIFIED / NOT TESTED; do not show a fabricated interface.",
    "workflow": "Show the official ComfyUI graph, then animate a derived four-step overlay labeled RECOMMENDED FROM TEMPLATE STRUCTURE, NOT HANDS-ON TESTED.",
}


def build_project() -> EpisodeProject:
    sources = [
        Source(
            id=source_id,
            title=value["title"],
            url=value["url"],
            publisher=value["publisher"],
            source_type="community" if "reddit.com" in value["url"] else "primary",
            signal_role="community_signal" if "reddit.com" in value["url"] else "primary_evidence",
        )
        for source_id, value in SOURCES.items()
    ]
    claims: list[Claim] = []
    beats: list[ScriptBeat] = []
    for beat in BEATS:
        claim_ids = []
        for index, source_id in enumerate(beat["source_ids"], start=1):
            claim_id = f"claim_{beat['id']}_{index}"
            claim_ids.append(claim_id)
            claims.append(
                Claim(
                    id=claim_id,
                    text=f"Evidence supporting spoken beat {beat['id']}",
                    source_ids=[source_id],
                    kind="fact",
                )
            )
        beats.append(
            ScriptBeat(
                id=beat["id"],
                narration=beat["narration"],
                claim_ids=claim_ids,
                purpose=PURPOSES[beat["purpose"]],
                visual_direction=VISUAL_PROOF.get(
                    beat["purpose"],
                    f"Show official H3 media: {', '.join(beat['broll'])}; overlay only: {beat['overlay']}",
                ),
                source_ids=beat["source_ids"],
            )
        )
    script = Script(
        title="AI Video Just Escaped the Cloud",
        description="A practical, evidence-backed MiniMax H3 deep dive.",
        tags=["MiniMax H3", "AI video", "ComfyUI", "open source"],
        thumbnail_text="AI VIDEO WENT LOCAL",
        beats=beats,
    )
    brief = Brief(
        title=script.title,
        thesis="MiniMax H3 makes serious local AI-video experimentation possible, but its best workflow is still hybrid.",
        episode_format="deep_dive",
        source_ids=list(SOURCES),
        claim_ids=[claim.id for claim in claims],
        why_now="The open weights and day-zero ComfyUI workflows shipped this month.",
        visual_opportunities=["official H3 output samples", "official architecture graphic", "clean source captures"],
        approved=True,
    )
    return EpisodeProject(
        episode_id=EPISODE_ID,
        scheduled_date=date.today().isoformat(),
        brief=brief,
        sources=sources,
        claims=claims,
        editorial_plan={
            "thesis": brief.thesis,
            "visible_examples": ["starship sequence", "dinner-table sequence", "ComfyUI workflow"],
            "practical_rule": "Preview low, lock references, finish high.",
            "documented_test": False,
        },
        script=script,
    )


def main() -> None:
    project = build_project()
    review = review_script_quality(project)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    destination = RUN_DIR / "script_quality_review.json"
    destination.write_text(json.dumps(review, indent=2), encoding="utf-8")
    print(json.dumps(review, indent=2))
    if not review["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
