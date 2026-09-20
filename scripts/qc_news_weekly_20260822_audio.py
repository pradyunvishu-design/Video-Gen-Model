from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import audio_qc

audio_qc.FFMPEG = str(Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\tools\ffmpeg\bin\ffmpeg.exe"))


OUT = ROOT / "output" / "news_weekly_20260822"
script = json.loads((OUT / "script.json").read_text(encoding="utf-8"))
approved = " ".join(section["narration"] for section in script["sections"])
result = audio_qc.review_narration(
    OUT / "audio" / "narration_master.m4a",
    approved,
    ROOT / "output" / "claude_chips_5m_recreate" / "audio_news_v3" / "approved_narrator_reference.wav",
    max_unmatched_words=18,
    min_intelligibility=0.86,
)
(OUT / "audio_qc.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
