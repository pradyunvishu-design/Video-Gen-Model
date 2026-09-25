"""Generate/review a script without importing production, narration or publishing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import editorial
from .general_scripting import checkpoints, preflight
from .models import EpisodeProject
from .project_store import canonical_hash, load_project, save_project
from .script_profiles import script_input_hash


def run_script_only(project: EpisodeProject, output_dir: Path, *, generate: bool = False,
                    max_revisions: int = 1, should_cancel=None) -> EpisodeProject:
    if not 0 <= max_revisions <= 2:
        raise ValueError("max_revisions must be 0-2")
    preflight(project)
    output_dir = Path(output_dir)
    if (output_dir / "episode_project.json").exists():
        existing = load_project(output_dir)
        if existing.episode_id != project.episode_id:
            raise ValueError("output directory belongs to a different episode")
        if existing.script_profile and script_input_hash(existing) == script_input_hash(project):
            project = existing
            if not generate:
                return project
        elif not generate:
            raise ValueError("output has different writing inputs; choose a new output directory for validation")
    project.episode["publishing_enabled"] = False
    project.status = "script_ready_to_generate"
    save_project(project, output_dir)
    if not generate:
        return project
    def checkpoint(current):
        save_project(current, output_dir)
        if should_cancel and should_cancel():
            raise InterruptedError("script generation canceled")
    with checkpoints(checkpoint):
        try:
            checkpoint(project)
            project.script, report, revisions = editorial.write_verified_script(project, max_revisions=max_revisions)
            project.qc["fact_check"] = {**report, "automatic_revisions": revisions,
                "reviewed_script_hash": canonical_hash(project.script.model_dump(mode="json"))}
            project.status = ("script_expert_review_required" if report.get("human_expert_review_required") else
                              "script_review_ready" if report["passed"] else "script_revision_required")
        except InterruptedError:
            project.status = "script_canceled"
            raise
        except Exception:
            project.status = "script_stage_failed"
            raise
        finally:
            save_project(project, output_dir)
    return project


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Approved EpisodeProject JSON with source text and script_profile")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generate", action="store_true", help="Explicitly authorize paid writing/review calls")
    parser.add_argument("--max-revisions", type=int, default=1, choices=range(3))
    args = parser.parse_args(argv)
    project = EpisodeProject.model_validate_json(args.project.read_text(encoding="utf-8-sig"))
    result = run_script_only(project, args.output, generate=args.generate, max_revisions=args.max_revisions)
    print(json.dumps({"status": result.status, "project": str((args.output / "episode_project.json").resolve()),
                      "publishing_enabled": False}))
    return 0 if result.status in {"script_ready_to_generate", "script_review_ready"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
