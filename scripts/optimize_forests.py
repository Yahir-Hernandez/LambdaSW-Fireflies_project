#!/usr/bin/env python3
"""Convert and resize the forest images used by the site.

By default this script reads JPG/PNG files from:
    sistema_app/static/img/forests

It writes WebP files next to the originals, keeping the same stem:
    forest_1.jpg -> forest_1.webp

Examples:
    python scripts/optimize_forests.py
    python scripts/optimize_forests.py --width 1200 --quality 78
    python scripts/optimize_forests.py --input-dir /path/to/forests --output-dir /tmp/forests-webp
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

SOURCE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
DEFAULT_WIDTH = 1200
DEFAULT_QUALITY = 78
DEFAULT_INPUT_DIR = Path("sistema_app/static/img/forests")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resize forest images and export them as WebP."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory with the source images.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory where WebP files will be written. Defaults to the input directory.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help="Maximum width in pixels for the exported images.",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=DEFAULT_QUALITY,
        help="WebP quality from 0 to 100.",
    )
    parser.add_argument(
        "--delete-originals",
        action="store_true",
        help="Remove the original files after successful conversion.",
    )
    return parser.parse_args()


def iter_source_images(input_dir: Path) -> Iterable[Path]:
    for path in sorted(input_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS:
            yield path


def convert_image(source: Path, output_dir: Path, max_width: int, quality: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source.stem}.webp"

    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "RGBA"):
            if "A" in img.getbands():
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")

        if img.width > max_width:
            new_height = round((max_width / img.width) * img.height)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        save_kwargs = {
            "format": "WEBP",
            "quality": quality,
            "method": 6,
            "lossless": False,
        }
        if img.mode == "RGBA":
            save_kwargs["exact"] = True

        img.save(output_path, **save_kwargs)

    return output_path


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir or input_dir

    if not input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {input_dir}")

    sources = list(iter_source_images(input_dir))
    if not sources:
        raise SystemExit(f"No source images found in {input_dir}")

    converted = []
    for source in sources:
        output_path = convert_image(source, output_dir, args.width, args.quality)
        converted.append((source, output_path))
        print(f"{source.name} -> {output_path.name}")
        print(f"  saved from {source.stat().st_size / 1024:.1f} KB")
        print(f"  to {output_path.stat().st_size / 1024:.1f} KB")

    if args.delete_originals:
        for source, _ in converted:
            source.unlink()
            print(f"deleted {source.name}")

    print(f"Done. Converted {len(converted)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
