from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import build_news_weekly_20260822_video as build


def rerender(slot: int) -> int:
    section = build.SLOT_SECTIONS[slot]
    destination = build.SEGMENTS / f"{slot:03d}_{section}.mp4"
    if slot in build.ENGAGING_BROLL_SLOTS:
        build.render_broll_with_context(section, slot, build.OPEN_BROLL_BY_SLOT[slot], destination)
    else:
        source = build.curated_source(slot)
        if source is None:
            raise FileNotFoundError(f"missing source for slot {slot}")
        build.render_source_sequence(section, slot, source, destination)
    return slot


def main() -> None:
    build.OPEN_BROLL_BY_SLOT = build.load_open_broll_bundle(build.OPEN_BROLL_MANIFEST)
    slots = sorted(build.ENGAGING_BROLL_SLOTS | build.ENGAGING_ARTICLE_SLOTS)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(rerender, slot) for slot in slots]
        for future in as_completed(futures):
            future.result()
    print(f"rerendered {len(slots)} moving evidence shots")


if __name__ == "__main__":
    main()
