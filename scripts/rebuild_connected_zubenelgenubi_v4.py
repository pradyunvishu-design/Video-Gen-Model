"""Rebuild episode 03 with the approved connected Zubenelgenubi delivery."""
from __future__ import annotations

from pathlib import Path

import scripts.rebuild_original_nerdy_host_v3 as profile
from scripts.refine_measured_tech_host_delivery import DIRECTOR


build = profile.build
EPISODE = build.EPISODE
REVISION_DIR = EPISODE / "connected_zubenelgenubi_v4"

build.PROJECT_BACKUP = EPISODE / "episode_project.pre_connected_zubenelgenubi_v4.json"
build.REVISION_DIR = REVISION_DIR
build.AUDIO_DIR = REVISION_DIR / "audio"
# The user requested an audio-only revision. Reuse the accepted v3 motion and
# normalized visual segments, then retime them to the new word timestamps.
build.MOTION_DIR = EPISODE / "manager_feedback_v3" / "motion"
build.SOURCE_SEGMENTS = EPISODE / "timeline_segments" / "manager-feedback-v3"
build.SEGMENT_DIR = EPISODE / "timeline_segments" / "connected-zubenelgenubi-v4"
build.FINAL_NARRATION = EPISODE / "narration_gemini_31_zubenelgenubi_connected_v4.wav"
build.FINAL_TIMELINE = EPISODE / "timeline_connected_zubenelgenubi_v4.mp4"
build.FINAL_VIDEO = EPISODE / "final_connected_zubenelgenubi_v4_1080p.mp4"
build.VOICE = "Zubenelgenubi"
build.DIRECTOR = DIRECTOR
build.PAUSE_MS = 220
build.GROUP_RANGES = (
    (0, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 29),
)
build.REVISION_VERSION = "connected-zubenelgenubi-v4"
build.VOICE_PROFILE_ID = "gemini_31_zubenelgenubi_original_connected_tech_host_v4"
build.QC_PREFIX = "connected_zubenelgenubi_v4"
build.REVIEW_NOTE = (
    "Audio-only revision: one original Gemini Zubenelgenubi preset throughout, "
    "using the approved connected, understated technology-host delivery. No voice cloning."
)


if __name__ == "__main__":
    build.main()
