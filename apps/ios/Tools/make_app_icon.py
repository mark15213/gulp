#!/usr/bin/env python3
"""Build the iOS app icon from the product logo.

The source is the repo's `icon.png` — a transparent, portrait, pop-art banana.
An iOS icon has to be square, opaque (the App Store rejects an alpha channel)
and safe under the superellipse mask iOS draws over it, so none of that
translates directly. This script does the translation, and it is checked in so
the icon can be rebuilt from the logo rather than being a binary somebody once
exported from somewhere.

    just ios-icon              # paper, the shipped one
    just ios-icon ink          # the alternative
    python3 apps/ios/Tools/make_app_icon.py --preview out.png

`paper` is the default because the icon, the launch screen and Today are then
the same surface: the app opens without ever changing colour underneath you.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "icon.png"
ICONSET = REPO / "apps/ios/Gulp/Assets.xcassets/AppIcon.appiconset"

SIZE = 1024
# iOS masks the icon with a superellipse, so art that runs to the edge loses its
# corners. 78% leaves the banana whole at every corner radius Apple has used.
CONTENT = 0.78

# The two design-system anchors, so the icon belongs to the same product as the
# app rather than to whatever the logo happened to be exported over.
BACKGROUNDS = {
    "paper": (250, 250, 247),
    "ink": (28, 27, 24),
}


def trimmed(image: Image.Image) -> Image.Image:
    """Drop the transparent margin, so `CONTENT` measures the art and not the
    empty space somebody happened to export around it."""
    box = image.getchannel("A").getbbox()
    return image.crop(box) if box else image


def build(background: tuple[int, int, int]) -> Image.Image:
    logo = trimmed(Image.open(SOURCE).convert("RGBA"))

    limit = int(SIZE * CONTENT)
    scale = min(limit / logo.width, limit / logo.height)
    logo = logo.resize(
        (max(1, round(logo.width * scale)), max(1, round(logo.height * scale))),
        Image.LANCZOS,
    )

    canvas = Image.new("RGB", (SIZE, SIZE), background)
    canvas.paste(logo, ((SIZE - logo.width) // 2, (SIZE - logo.height) // 2), logo)
    return canvas


def preview(path: Path) -> None:
    """Both variants, masked the way a home screen would, side by side."""
    tile = 360
    tiles = []
    for background in BACKGROUNDS.values():
        image = build(background).resize((tile, tile), Image.LANCZOS).convert("RGBA")
        mask = Image.new("L", (tile, tile), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, tile - 1, tile - 1], radius=int(tile * 0.225), fill=255
        )
        image.putalpha(mask)
        tiles.append(image)

    pad, gap = 40, 48
    sheet = Image.new("RGB", (pad * 2 + tile * 2 + gap, pad * 2 + tile), (128, 128, 128))
    for index, image in enumerate(tiles):
        sheet.paste(image, (pad + index * (tile + gap), pad), image)
    sheet.save(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("background", nargs="?", default="paper", choices=sorted(BACKGROUNDS))
    parser.add_argument("--preview", type=Path, help="write a side-by-side comparison here instead")
    args = parser.parse_args()

    if not SOURCE.exists():
        print(f"no logo at {SOURCE}", file=sys.stderr)
        return 1

    if args.preview:
        preview(args.preview)
        print(f"wrote {args.preview}")
        return 0

    ICONSET.mkdir(parents=True, exist_ok=True)
    out = ICONSET / "AppIcon.png"
    build(BACKGROUNDS[args.background]).save(out, "PNG")
    print(f"wrote {out.relative_to(REPO)} on {args.background}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
