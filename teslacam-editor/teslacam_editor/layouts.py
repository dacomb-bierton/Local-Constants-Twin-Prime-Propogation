"""Camera layouts.

A layout turns (camera subset, main camera, canvas size) into a list of tiles.  The same tile geometry drives
the browser preview (via /api/layout, in normalised coordinates) and the ffmpeg export (in pixels), so what
you see is what gets rendered.  Every layout works for any canvas aspect ratio; portrait canvases rearrange
tiles vertically where that makes sense.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .models import ASPECT_PRESETS, CAMERAS

SOURCE_ASPECT = 4 / 3  # Tesla cameras record 4:3 (1280x960 on HW3; HW4 is close enough)

LAYOUTS = {
    "single": "Single camera",
    "grid": "Grid",
    "pip": "Picture in picture",
    "side": "Main + side strip",
    "cinematic": "Cinematic (main + bottom strip)",
    "three_wide": "Strip (side by side)",
}

GRID_ORDER_6 = ["left_pillar", "front", "right_pillar", "left_repeater", "back", "right_repeater"]


@dataclass
class Tile:
    camera: str
    x: int
    y: int
    w: int
    h: int

    def normalized(self, canvas_w: int, canvas_h: int) -> dict:
        return {
            "camera": self.camera,
            "x": self.x / canvas_w,
            "y": self.y / canvas_h,
            "w": self.w / canvas_w,
            "h": self.h / canvas_h,
        }


def parse_aspect(aspect: str) -> tuple[int, int]:
    if aspect in ASPECT_PRESETS:
        return ASPECT_PRESETS[aspect]
    try:
        a, b = aspect.replace("/", ":").split(":")
        return max(1, int(a)), max(1, int(b))
    except ValueError:
        return ASPECT_PRESETS["16:9"]


def canvas_size(aspect: str, short_side: int) -> tuple[int, int]:
    """Canvas in pixels where the *shorter* side equals `short_side` (1080 -> 1920x1080, 1080x1920, 1080x1080...)."""
    a, b = parse_aspect(aspect)
    short_side = max(120, int(short_side))
    if a >= b:
        h = short_side
        w = short_side * a / b
    else:
        w = short_side
        h = short_side * b / a
    return _even(w), _even(h)


def _even(v: float) -> int:
    n = int(round(v))
    return n if n % 2 == 0 else n - 1 if n > 2 else 2


def order_cameras(cameras: list[str], main: str) -> list[str]:
    cams = [c for c in CAMERAS if c in cameras]
    if main in cams:
        cams.remove(main)
        cams.insert(0, main)
    return cams


def compute_tiles(layout: str, cameras: list[str], main: str, canvas_w: int, canvas_h: int) -> list[Tile]:
    cams = order_cameras(cameras, main)
    if not cams:
        return []
    if main not in cams:
        main = cams[0]
    if len(cams) == 1 or layout == "single":
        return [Tile(main, 0, 0, canvas_w, canvas_h)]
    fn = {
        "grid": _grid,
        "pip": _pip,
        "side": _side,
        "cinematic": _cinematic,
        "three_wide": _strip,
    }.get(layout, _grid)
    tiles = fn(cams, main, canvas_w, canvas_h)
    return [_snap(t, canvas_w, canvas_h) for t in tiles]


def _snap(t: Tile, cw: int, ch: int) -> Tile:
    x = max(0, _even(t.x))
    y = max(0, _even(t.y))
    w = max(2, _even(t.w))
    h = max(2, _even(t.h))
    if x + w > cw:
        w = _even(cw - x)
    if y + h > ch:
        h = _even(ch - y)
    return Tile(t.camera, x, y, w, h)


def _grid(cams: list[str], main: str, cw: int, ch: int) -> list[Tile]:
    n = len(cams)
    if n == 6 and set(cams) == set(GRID_ORDER_6):
        cams = list(GRID_ORDER_6)
    best = None
    for cols in range(1, n + 1):
        rows = math.ceil(n / cols)
        tile_aspect = (cw / cols) / (ch / rows)
        waste = cols * rows - n
        score = abs(math.log(tile_aspect / SOURCE_ASPECT)) + 0.35 * waste
        if best is None or score < best[0]:
            best = (score, cols, rows)
    assert best is not None
    _, cols, rows = best
    tw = cw / cols
    th = ch / rows
    tiles = []
    for i, cam in enumerate(cams):
        r, c = divmod(i, cols)
        in_row = min(cols, n - r * cols)
        offset = (cols - in_row) * tw / 2  # centre a partial last row
        tiles.append(Tile(cam, int(offset + c * tw), int(r * th), int(tw), int(th)))
    return tiles


def _pip(cams: list[str], main: str, cw: int, ch: int) -> list[Tile]:
    others = [c for c in cams if c != main]
    k = len(others)
    margin = max(4, int(min(cw, ch) * 0.015))
    th = ch * (0.22 if cw >= ch else 0.16)
    tw = th * SOURCE_ASPECT
    max_tw = (cw - (k + 1) * margin) / k
    if tw > max_tw:
        tw = max_tw
        th = tw / SOURCE_ASPECT
    total = k * tw + (k - 1) * margin
    x0 = (cw - total) / 2
    y0 = ch - th - margin
    tiles = [Tile(main, 0, 0, cw, ch)]
    for i, cam in enumerate(others):
        tiles.append(Tile(cam, int(x0 + i * (tw + margin)), int(y0), int(tw), int(th)))
    return tiles


def _side(cams: list[str], main: str, cw: int, ch: int) -> list[Tile]:
    others = [c for c in cams if c != main]
    k = len(others)
    if cw >= ch:
        # Main on the left, a column of the others on the right.
        th = ch / k
        tw = min(th * SOURCE_ASPECT, cw * 0.38)
        th = tw / SOURCE_ASPECT
        col_h = th * k
        y0 = (ch - col_h) / 2
        main_w = cw - tw
        tiles = [Tile(main, 0, 0, int(main_w), ch)]
        for i, cam in enumerate(others):
            tiles.append(Tile(cam, int(main_w), int(y0 + i * th), int(tw), int(th)))
        return tiles
    # Portrait: others split between a top row and a bottom row, main in the middle.
    top = others[: math.ceil(k / 2)]
    bottom = others[math.ceil(k / 2) :]
    tiles = []
    y_top_h = 0.0
    if top:
        tw = cw / len(top)
        y_top_h = tw / SOURCE_ASPECT
        for i, cam in enumerate(top):
            tiles.append(Tile(cam, int(i * tw), 0, int(tw), int(y_top_h)))
    y_bot_h = 0.0
    if bottom:
        tw = cw / len(bottom)
        y_bot_h = tw / SOURCE_ASPECT
        for i, cam in enumerate(bottom):
            tiles.append(Tile(cam, int(i * tw), int(ch - y_bot_h), int(tw), int(y_bot_h)))
    tiles.insert(0, Tile(main, 0, int(y_top_h), cw, int(ch - y_top_h - y_bot_h)))
    return tiles


def _cinematic(cams: list[str], main: str, cw: int, ch: int) -> list[Tile]:
    """Main camera on top, the rest in a strip along the bottom."""
    others = [c for c in cams if c != main]
    k = len(others)
    tw = cw / k
    strip_h = min(tw / SOURCE_ASPECT, ch * (0.3 if cw >= ch else 0.25))
    tw_fit = strip_h * SOURCE_ASPECT
    if tw_fit * k < cw:
        tw = tw_fit
    total = tw * k
    x0 = (cw - total) / 2
    tiles = [Tile(main, 0, 0, cw, int(ch - strip_h))]
    for i, cam in enumerate(others):
        tiles.append(Tile(cam, int(x0 + i * tw), int(ch - strip_h), int(tw), int(strip_h)))
    return tiles


def _strip(cams: list[str], main: str, cw: int, ch: int) -> list[Tile]:
    """All cameras side by side (landscape) or stacked (portrait) with the main camera in the middle."""
    others = [c for c in cams if c != main]
    left_side = [c for c in others if c.startswith("left")]
    right_side = [c for c in others if c.startswith("right")]
    rest = [c for c in others if c not in left_side and c not in right_side]
    ordered = left_side + rest[: len(rest) // 2] + [main] + rest[len(rest) // 2 :] + right_side
    n = len(ordered)
    tiles = []
    if cw >= ch:
        tw = cw / n
        for i, cam in enumerate(ordered):
            tiles.append(Tile(cam, int(i * tw), 0, int(tw), ch))
    else:
        th = ch / n
        for i, cam in enumerate(ordered):
            tiles.append(Tile(cam, 0, int(i * th), cw, int(th)))
    return tiles


def layout_payload(layout: str, cameras: list[str], main: str, aspect: str, short_side: int = 720) -> dict:
    cw, ch = canvas_size(aspect, short_side)
    tiles = compute_tiles(layout, cameras, main, cw, ch)
    return {
        "layout": layout,
        "aspect": aspect,
        "canvas": {"w": cw, "h": ch},
        "tiles": [t.normalized(cw, ch) for t in tiles],
        "tiles_px": [asdict(t) for t in tiles],
    }
