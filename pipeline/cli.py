"""Run the pipeline: python -m pipeline.cli all  (or a single stage with --run <dir>)."""
import argparse
import datetime as dt
from pathlib import Path

from . import assemble, assets, ingest, scriptgen, tts, tts_placeholder
from .config import OUTPUT_DIR

STAGES = {
    "ingest": ingest.run,
    "script": scriptgen.run,
    "voice": tts.run,
    "voice-placeholder": tts_placeholder.run,
    "assets": assets.run,
    "render": assemble.run,
}
ORDER = ["ingest", "script", "voice", "assets", "render"]


def main():
    ap = argparse.ArgumentParser(description="AI news video pipeline")
    ap.add_argument("stage", choices=list(STAGES) + ["all"])
    ap.add_argument("--run", help="existing run directory to resume (e.g. output/run_20260803)")
    args = ap.parse_args()

    if args.run:
        run_dir = Path(args.run)
    else:
        run_dir = OUTPUT_DIR / f"run_{dt.datetime.now():%Y%m%d_%H%M}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Run dir: {run_dir}")

    stages = ORDER if args.stage == "all" else [args.stage]
    for name in stages:
        print(f"\n=== {name} ===")
        STAGES[name](run_dir)


if __name__ == "__main__":
    main()
