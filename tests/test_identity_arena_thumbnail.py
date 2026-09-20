from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from pipeline.identity_arena_thumbnail import (
    CANVAS,
    _logo_on_blank_panel,
    build_identity_arena_prompts,
    snap_panel_anchors,
)


def test_identity_arena_prompt_contract() -> None:
    prompts = build_identity_arena_prompts()
    assert len(prompts) == 4
    assert {item["style_mode"] for item in prompts} == {
        "agent_hq", "agent_showdown", "agent_orbit", "agent_home",
    }
    for item in prompts:
        prompt = item["prompt"]
        assert "BACKGROUND PLATE" in prompt
        assert "negative space" in prompt
        assert "exact official logos" in prompt
        assert "STRICTLY EXCLUDE" in prompt
        assert "YouTube" not in prompt.replace("YouTube thumbnail", "")


def test_exact_logo_overlay_preserves_transparency() -> None:
    base = Image.new("RGBA", CANVAS, (12, 14, 18, 255))
    logo = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(25, 75):
        for y in range(25, 75):
            logo.putpixel((x, y), (255, 100, 20, 255))
    record = {"key": "test", "display_name": "Test", "asset_sha256": "abc"}
    placement = _logo_on_blank_panel(base, record, logo, (640, 360), 120)
    assert placement["panel_center"] == [640, 360]
    assert placement["asset_sha256"] == "abc"
    assert base.getpixel((640, 360))[:3] == (255, 100, 20)
    assert base.getpixel((590, 310))[:3] == (12, 14, 18)


def test_visual_anchor_detection_snaps_black_and_white_blank_panels() -> None:
    image = Image.new("RGB", CANVAS, (14, 15, 18))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((130, 205, 385, 405), radius=28, fill=(230, 176, 35))
    draw.rounded_rectangle((150, 225, 365, 385), radius=22, fill=(16, 16, 17))
    draw.rounded_rectangle((870, 195, 1120, 420), radius=28, fill=(25, 90, 220))
    draw.rounded_rectangle((895, 220, 1095, 395), radius=20, fill=(246, 245, 240))
    spec = {
        "claude": {"x": 350, "y": 410, "size": 175, "panel_tone": "black"},
        "openai": {"x": 930, "y": 410, "size": 175, "panel_tone": "white"},
        "headline": {"left": 48, "top": 35, "width": 760, "lines": ["CLAUDE", "VS CODEX"]},
    }
    snapped = snap_panel_anchors(image, spec)
    assert snapped["claude"]["anchor_detection"] == "visual-snap"
    assert snapped["openai"]["anchor_detection"] == "visual-snap"
    assert abs(snapped["claude"]["x"] - 258) <= 8
    assert abs(snapped["openai"]["x"] - 995) <= 8
    assert spec["claude"]["x"] == 350


def test_buzz_brief_uses_curated_full_frame_plates() -> None:
    root = Path(__file__).resolve().parents[1]
    brief = json.loads((root / "config" / "thumbnail_brief.buzz_workspace.json").read_text(encoding="utf-8"))
    assert brief["background_mode"] == "curated_identity_plates"
    assert len(brief["identity_plates"]) == 4
    for item in brief["identity_plates"]:
        assert (root / item["path"]).exists()
        assert {"buzz", "block", "openai", "claude", "goose"}.issubset(item)
    assert brief["hero_template"] == "identity_arena"
    assert brief["identity_keys"] == ["buzz", "block", "openai", "claude", "goose"]
