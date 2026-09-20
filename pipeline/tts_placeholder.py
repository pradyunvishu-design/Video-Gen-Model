"""Offline stand-in for the voice stage, using the Windows built-in speech engine.

Costs nothing and needs no voice sample, so you can exercise the render stage
end-to-end. The output sounds robotic — it is for timing and layout only, never
for publishing. Use `pipeline.tts` (Magic Hour voice cloner) for real narration.
"""
import json
import subprocess
import tempfile
from pathlib import Path

PS_SCRIPT = """
Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText('{txt}', [System.Text.Encoding]::UTF8)
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = 1
$s.SetOutputToWaveFile('{wav}')
$s.Speak($text)
$s.Dispose()
"""


def _speak(text: str, wav: Path):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
        txt = f.name
    try:
        script = PS_SCRIPT.format(txt=txt.replace("\\", "\\\\"), wav=str(wav).replace("\\", "\\\\"))
        subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       check=True, capture_output=True)
    finally:
        Path(txt).unlink(missing_ok=True)


def run(run_dir: Path) -> Path:
    script = json.loads((run_dir / "script.json").read_text(encoding="utf-8"))
    audio_dir = run_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    for scene in script["scenes"]:
        sid = scene["id"]
        mp3 = audio_dir / f"scene_{sid:02d}_0.mp3"
        if not mp3.exists():
            wav = audio_dir / f"scene_{sid:02d}_0.wav"
            _speak(scene["narration"], wav)
            subprocess.run(["ffmpeg", "-y", "-i", str(wav), "-c:a", "libmp3lame",
                            "-q:a", "2", str(mp3)], check=True, capture_output=True)
            wav.unlink()
        scene["audio_files"] = [mp3.name]
        print(f"  scene {sid} placeholder audio")

    (run_dir / "script.json").write_text(json.dumps(script, indent=2), encoding="utf-8")
    print(f"Placeholder audio -> {audio_dir}  (robotic on purpose; not for publishing)")
    return audio_dir
