"""Bounded editorial focus moves shared by recorded product demonstrations.

The camera follows an intentional action, never a raw stream of mouse positions.
This module does not capture a desktop or synthesize missing source frames.
"""
from __future__ import annotations

import math


def focus_events(events: list[dict]) -> list[dict]:
    """Validate, coalesce nearby actions, and prevent overlapping camera moves."""
    cleaned = []
    for event in events:
        if event.get("kind") not in {"click", "fill", "focus"}:
            continue
        values = {key: float(event[key]) for key in ("start_seconds", "end_seconds", "x", "y")}
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("focus coordinates and times must be finite")
        start, end = values["start_seconds"], values["end_seconds"]
        if start < 0 or end <= start or not all(0 <= values[key] <= 1 for key in ("x", "y")):
            raise ValueError("focus event lies outside the recording or viewport")
        if end - start < 1.2:
            continue  # A short click is better without a camera bounce.
        cleaned.append(values)
    result: list[dict] = []
    for event in sorted(cleaned, key=lambda item: item["start_seconds"]):
        if result:
            previous = result[-1]
            gap = event["start_seconds"] - previous["end_seconds"]
            distance = math.hypot(event["x"] - previous["x"], event["y"] - previous["y"])
            if gap <= 0.5 and distance < 0.08:
                previous["end_seconds"] = max(previous["end_seconds"], event["end_seconds"])
                continue
            if gap < 0.5:
                continue  # Do not jump between targets while still zoomed in.
        result.append(event)
    return result


def framing_filter(events: list[dict]) -> str:
    """Fixed-size 1080p output with smoothstep entrances/exits and still holds.

    4:4:4 sampling before the crop avoids even-pixel chroma snapping. A fixed
    zoompan output avoids reconfiguring a scale/crop pair on every frame.
    No optical-flow interpolation is applied to text or mouse pointers.
    """
    events = focus_events(events)
    base = "setpts=PTS-STARTPTS,fps=30,scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
    if not events:
        return base + ",format=yuv420p"

    zoom, x, y = "1", "0.5", "0.5"
    for event in reversed(events):
        start, end = event["start_seconds"], event["end_seconds"]
        ramp = min(0.65, (end - start) / 3)
        enter = f"clip((on/30-{start:.4f})/{ramp:.4f},0,1)"
        leave = f"clip(({end:.4f}-on/30)/{ramp:.4f},0,1)"

        def ease(value: str) -> str:
            return f"(({value})*({value})*(3-2*({value})))"

        active = f"between(on/30,{start:.4f},{end:.4f})"
        zoom = f"if({active},1+0.12*{ease(enter)}*{ease(leave)},{zoom})"
        x = f"if({active},{event['x']:.4f},{x})"
        y = f"if({active},{event['y']:.4f},{y})"
    return (
        base + ",format=yuv444p,"
        f"zoompan=z='{zoom}':x='(iw-iw/zoom)*({x})':y='(ih-ih/zoom)*({y})':"
        "d=1:s=1920x1080:fps=30,format=yuv420p"
    )
