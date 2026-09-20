from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output" / "claude_chips_5m_recreate"
AUDIO = OUT / "audio_news_v3" / "narration_news_v3_master.m4a"
REFERENCE = OUT / "audio_news_v3" / "approved_narrator_reference.wav"
SCRIPT = OUT / "script_news_v3.json"
REPORT = OUT / "audio_news_v3" / "audio_qc_news_v3.json"
FFMPEG_BIN = Path(r"C:\Users\kanag\Desktop\Hermes-Workspace\Youtube Automation for Magic hour\tools\ffmpeg\bin")


def main() -> None:
    os.environ["PATH"] = str(FFMPEG_BIN) + os.pathsep + os.environ.get("PATH", "")
    from pipeline.audio_qc import review_narration

    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    approved = " ".join(section["narration"] for section in script["sections"])
    report = review_narration(
        AUDIO,
        approved,
        REFERENCE,
        enforce_pacing=True,
        max_unmatched_words=12,
        min_intelligibility=0.88,
    )
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
