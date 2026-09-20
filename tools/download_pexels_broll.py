"""Download a fixed, rights-reviewed set of Pexels b-roll clips.

The source pages are recorded beside each file. Only 1920x1080-or-smaller
public MP4 variants are accepted; the script never downloads 4K media.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

RUNTIME_VENDOR = Path(__file__).resolve().parent / "runtime_vendor"
if RUNTIME_VENDOR.exists():
    sys.path.insert(0, str(RUNTIME_VENDOR))

try:
    from curl_cffi import requests
    CURL_CFFI = True
except ModuleNotFoundError:
    import requests
    CURL_CFFI = False


SOURCES = {
    "electronics-workstation": "https://www.pexels.com/video/6754817/",
    "circuit-board-repair": "https://www.pexels.com/video/7423951/",
    "office-walk-documents": "https://www.pexels.com/video/7652109/",
    "team-walking-discussion": "https://www.pexels.com/video/8102826/",
    "software-engineer-office": "https://www.pexels.com/video/5483084/",
    "circuit-board-macro": "https://www.pexels.com/video/2376984/",
    "office-corridor-team": "https://www.pexels.com/video/7147176/",
    "tablet-collaboration": "https://www.pexels.com/video/7653220/",
}


def candidates(page_text: str) -> list[str]:
    decoded = html.unescape(page_text.replace("\\u002F", "/").replace("\\/", "/"))
    urls = re.findall(r"https://videos\.pexels\.com/video-files/[^\"'<> ]+?\.mp4", decoded)
    return list(dict.fromkeys(urls))


def score(url: str) -> tuple[int, int]:
    name = urlparse(url).path.lower()
    dimensions = re.search(r"_(\d{3,4})_(\d{3,4})_", name)
    if dimensions:
        width, height = map(int, dimensions.groups())
        if width <= 1920 and height <= 1080:
            return (2 if (width, height) == (1920, 1080) else 1, width * height)
        return (-1, -(width * height))
    return (0, 0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    ledger = []
    session = requests.Session(impersonate="chrome") if CURL_CFFI else requests.Session()
    for slug, page_url in SOURCES.items():
        response = session.get(page_url, timeout=45)
        response.raise_for_status()
        found = sorted(candidates(response.text), key=score, reverse=True)
        usable = [url for url in found if score(url)[0] >= 0]
        if not usable:
            raise RuntimeError(f"No <=1080p MP4 found for {page_url}")
        media_url = usable[0]
        target = args.output / f"pexels_{slug}.mp4"
        if not target.exists() or target.stat().st_size < 1_000_000:
            with session.get(media_url, stream=True, timeout=120) as media:
                media.raise_for_status()
                with target.open("wb") as handle:
                    for chunk in media.iter_content(chunk_size=1 << 20):
                        if chunk:
                            handle.write(chunk)
        ledger.append({
            "asset_id": f"pexels:{slug}",
            "path": str(target),
            "source_url": page_url,
            "download_url": media_url,
            "rights_status": "pexels-free-to-use",
            "usage": "private editorial review b-roll; source audio muted",
            "bytes": target.stat().st_size,
        })
        print(f"downloaded {slug}: {target.stat().st_size / 1_000_000:.1f} MB", flush=True)
    (args.output / "pexels_rights_ledger.json").write_text(
        json.dumps(ledger, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
