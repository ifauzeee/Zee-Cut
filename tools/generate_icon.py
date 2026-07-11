"""Generate assets/icon.ico for Zee-Cut (run once, output is committed).

Uses only Pillow so it works cross-platform without design tooling.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _rounded_rect(draw: ImageDraw.ImageDraw, box, radius: int, fill) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def build_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background gradient (approximated with two stacked rounded rects).
    _rounded_rect(draw, [0, 0, size, size], size // 6, (11, 15, 25, 255))
    _rounded_rect(
        draw,
        [size * 0.06, size * 0.06, size * 0.94, size * 0.94],
        size // 7,
        (17, 24, 39, 255),
    )

    # Accent bar (brand blue #3b82f6).
    bar_h = max(2, int(size * 0.10))
    draw.rectangle(
        [size * 0.18, size * 0.78, size * 0.82, size * 0.78 + bar_h],
        fill=(59, 130, 246, 255),
    )

    # "ZC" monogram.
    try:
        font = ImageFont.truetype("segoeui.ttf", int(size * 0.46))
    except Exception:
        font = ImageFont.load_default()

    text = "ZC"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
        text,
        font=font,
        fill=(248, 250, 252, 255),
    )
    return img


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    out.parent.mkdir(parents=True, exist_ok=True)

    base = build_icon(256)
    base.save(out, sizes=[(s, s) for s in (256, 128, 64, 48, 32, 16)])
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
