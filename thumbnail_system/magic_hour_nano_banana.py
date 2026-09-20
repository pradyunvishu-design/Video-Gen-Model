#!/usr/bin/env python3
"""Generate reference-conditioned thumbnail plates with Magic Hour Nano Banana 2."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


API_ROOT = "https://api.magichour.ai/v1"
TERMINAL_STATUSES = {"complete", "error", "canceled"}


class MagicHourError(RuntimeError):
    pass


def request_json(url: str, token: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise MagicHourError(f"Magic Hour HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise MagicHourError(f"Magic Hour connection failed: {exc.reason}") from exc


def upload_references(paths: list[Path], token: str) -> list[str]:
    if len(paths) > 9:
        raise MagicHourError("Nano Banana 2 image editing accepts at most nine reference images")
    items = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        items.append({"type": "image", "extension": path.suffix.lower().lstrip(".")})

    response = request_json(f"{API_ROOT}/files/upload-urls", token, method="POST", body={"items": items})
    upload_items = response.get("items") or []
    if len(upload_items) != len(paths):
        raise MagicHourError("Magic Hour returned an unexpected number of upload URLs")

    file_paths: list[str] = []
    for path, item in zip(paths, upload_items):
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        request = urllib.request.Request(
            item["upload_url"],
            data=path.read_bytes(),
            headers={"Content-Type": content_type},
            method="PUT",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                if response.status not in {200, 201, 204}:
                    raise MagicHourError(f"Reference upload failed with status {response.status}")
        except urllib.error.URLError as exc:
            raise MagicHourError(f"Reference upload failed for {path.name}: {exc}") from exc
        file_paths.append(item["file_path"])
    return file_paths


def create_project(
    token: str,
    prompt: str,
    *,
    name: str,
    resolution: str,
    references: list[Path],
) -> dict[str, Any]:
    common: dict[str, Any] = {
        "name": name,
        "image_count": 1,
        "model": "nano-banana-2",
        "aspect_ratio": "16:9",
        "resolution": resolution,
        "style": {"prompt": prompt},
    }
    if references:
        common["assets"] = {"image_file_paths": upload_references(references, token)}
        endpoint = "ai-image-editor"
    else:
        endpoint = "ai-image-generator"
    return request_json(f"{API_ROOT}/{endpoint}", token, method="POST", body=common)


def wait_for_project(project_id: str, token: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status = None
    while time.monotonic() < deadline:
        project = request_json(f"{API_ROOT}/image-projects/{project_id}", token)
        status = project.get("status")
        if status != last_status:
            print(json.dumps({"project_id": project_id, "status": status, "credits_charged": project.get("credits_charged")}))
            last_status = status
        if status in TERMINAL_STATUSES:
            if status != "complete":
                raise MagicHourError(f"Project ended with status={status}: {project.get('error')}")
            return project
        time.sleep(3)
    raise MagicHourError(f"Timed out waiting for project {project_id}")


def download_outputs(project: dict[str, Any], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    downloads = project.get("downloads") or []
    if not downloads:
        raise MagicHourError("Completed project did not include download URLs")
    paths: list[Path] = []
    for index, item in enumerate(downloads, start=1):
        target = output_dir / f"nano-banana-2_{project['id']}_{index:02d}.png"
        try:
            with urllib.request.urlopen(item["url"], timeout=120) as response:
                target.write_bytes(response.read())
        except urllib.error.URLError as exc:
            raise MagicHourError(f"Could not download output {index}: {exc}") from exc
        paths.append(target)
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--reference", type=Path, action="append", default=[])
    parser.add_argument("--name", default="thumbnail-plate-nb2")
    parser.add_argument("--resolution", choices=("640px", "1k", "2k", "4k"), default="2k")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prompt = args.prompt_file.read_text(encoding="utf-8").strip()
    if not prompt:
        raise MagicHourError("Prompt file is empty")
    request_summary = {
        "endpoint": "ai-image-editor" if args.reference else "ai-image-generator",
        "model": "nano-banana-2",
        "aspect_ratio": "16:9",
        "resolution": args.resolution,
        "reference_count": len(args.reference),
        "prompt_file": str(args.prompt_file.resolve()),
    }
    if args.dry_run:
        print(json.dumps(request_summary, indent=2))
        return 0

    token = os.getenv("MAGIC_HOUR_API_KEY") or os.getenv("API_TOKEN")
    if not token:
        raise MagicHourError("Set MAGIC_HOUR_API_KEY in the environment; never place the key in prompts or exported JSON")

    created = create_project(
        token,
        prompt,
        name=args.name,
        resolution=args.resolution,
        references=args.reference,
    )
    project = wait_for_project(created["id"], token, args.timeout)
    paths = download_outputs(project, args.output_dir)
    record = {
        **request_summary,
        "project_id": project["id"],
        "credits_charged": project.get("credits_charged"),
        "outputs": [str(path.resolve()) for path in paths],
    }
    (args.output_dir / f"{project['id']}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
