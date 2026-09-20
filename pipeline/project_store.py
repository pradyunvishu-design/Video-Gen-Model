"""Atomic, resumable storage for EpisodeProject documents."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .models import EpisodeProject


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def project_path(run_dir: Path) -> Path:
    return run_dir / "episode_project.json"


def load_project(run_dir: Path) -> EpisodeProject:
    return EpisodeProject.model_validate_json(project_path(run_dir).read_text(encoding="utf-8"))


def save_project(project: EpisodeProject, run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    target = project_path(run_dir)
    temp = target.with_suffix(".json.tmp")
    temp.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temp, target)
    return target


def stage_is_current(project: EpisodeProject, stage: str, inputs: Any) -> bool:
    return project.episode.get("stage_hashes", {}).get(stage) == canonical_hash(inputs)


def mark_stage(project: EpisodeProject, stage: str, inputs: Any) -> None:
    project.episode.setdefault("stage_hashes", {})[stage] = canonical_hash(inputs)
