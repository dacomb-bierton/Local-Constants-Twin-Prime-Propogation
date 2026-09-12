"""Text overlays rendered with Pillow.

ffmpeg's drawtext filter is missing from several common ffmpeg builds (including the one shipped by
imageio-ffmpeg), so labels and timestamps are rasterised here and composited with the `overlay` filter.
The running clock is a sprite sheet with one row per second; ffmpeg's `crop` filter selects the row for the
current frame with a time expression, which keeps the whole export a single ffmpeg pass.
"""

from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import ffmpeg_tools as ff

PAD_X = 10
PAD_Y = 6


@lru_cache(maxsize=32)
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = ff.font_file()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1 ships a scalable fallback font
    except TypeError:  # pragma: no cover - very old Pillow
        return ImageFont.load_default()


def _measure(font, text: str) -> tuple[int, int]:
    dummy = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(dummy)
    left, top, right, bottom = d.textbbox((0, 0), text, font=font, stroke_width=max(1, font.size // 12) if hasattr(font, "size") else 1)
    return right - left, bottom - top


def _draw_line(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, stroke: int) -> None:
    draw.text(xy, text, font=font, fill=(255, 255, 255, 255), stroke_width=stroke, stroke_fill=(0, 0, 0, 200))


def render_text_png(text: str, fontsize: int, out: Path) -> tuple[int, int]:
    """Single label with a translucent box; returns (width, height)."""
    font = _font(fontsize)
    stroke = max(1, fontsize // 12)
    tw, th = _measure(font, text)
    w, h = tw + 2 * PAD_X, th + 2 * PAD_Y
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=max(3, fontsize // 4), fill=(0, 0, 0, 110))
    _draw_line(d, (PAD_X, PAD_Y - 1), text, font, stroke)
    img.save(out)
    return w, h


def format_epoch(epoch: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))


def render_clock_sprite(first_epoch: float, seconds: int, fontsize: int, out: Path) -> tuple[int, int, int]:
    """Sprite sheet with one timestamp row per wall-clock second starting at floor(first_epoch).

    Returns (row_width, row_height, rows).
    """
    rows = max(1, seconds)
    base = int(first_epoch)
    font = _font(fontsize)
    stroke = max(1, fontsize // 12)
    tw, th = _measure(font, "0000-00-00 00:00:00")
    w, h = tw + 2 * PAD_X, th + 2 * PAD_Y
    if h % 2:
        h += 1
    if w % 2:
        w += 1
    img = Image.new("RGBA", (w, h * rows), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for r in range(rows):
        y = r * h
        d.rounded_rectangle((0, y, w - 1, y + h - 1), radius=max(3, fontsize // 4), fill=(0, 0, 0, 110))
        _draw_line(d, (PAD_X, y + PAD_Y - 1), format_epoch(base + r), font, stroke)
    img.save(out)
    return w, h, rows
