"""Build compact contact sheets for a private thumbnail reference study."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def build_sheet(source: Path, output: Path) -> None:
    images = [
        p for p in sorted((*source.glob("*.jpg"), *source.glob("*.jpeg"), *source.glob("*.png")))
        if not p.stem.startswith("UC")
    ][:8]
    if not images:
        raise FileNotFoundError(f"No thumbnail images found in {source}")

    cell_width, cell_height = 384, 216
    gap, header = 16, 62
    canvas = Image.new("RGB", (cell_width * 4 + gap * 5, header + cell_height * 2 + gap * 3), "#111318")
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 15), source.name.replace("_", " ").upper(), fill="white", font=_font(30))

    for index, path in enumerate(images):
        image = Image.open(path).convert("RGB")
        image.thumbnail((cell_width, cell_height), Image.Resampling.LANCZOS)
        x = gap + (index % 4) * (cell_width + gap)
        y = header + gap + (index // 4) * (cell_height + gap)
        canvas.paste(image, (x + (cell_width - image.width) // 2, y + (cell_height - image.height) // 2))

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=92)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build_sheet(args.source, args.output)


if __name__ == "__main__":
    main()
