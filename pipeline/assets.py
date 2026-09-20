"""Retired legacy image stage; standalone AI stills are forbidden."""
from pathlib import Path


def run(run_dir: Path) -> Path:
    raise RuntimeError(
        "The legacy assets stage is disabled: it created standalone AI-generated stills. "
        "Run the EpisodeProject worker pipeline for real captures and exact motion graphics."
    )
