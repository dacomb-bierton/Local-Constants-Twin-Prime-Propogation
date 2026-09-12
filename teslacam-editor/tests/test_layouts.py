import itertools

import pytest

from teslacam_editor.layouts import LAYOUTS, canvas_size, compute_tiles, layout_payload
from teslacam_editor.models import ASPECT_PRESETS, CAMERAS


@pytest.mark.parametrize("aspect,short,expected", [
    ("16:9", 1080, (1920, 1080)),
    ("9:16", 1080, (1080, 1920)),
    ("1:1", 1080, (1080, 1080)),
    ("4:3", 720, (960, 720)),
    ("21:9", 1080, (2520, 1080)),
    ("4:5", 1080, (1080, 1350)),
])
def test_canvas_size(aspect, short, expected):
    assert canvas_size(aspect, short) == expected


def _subsets():
    for n in range(1, len(CAMERAS) + 1):
        for combo in itertools.combinations(CAMERAS, n):
            yield list(combo)


@pytest.mark.parametrize("layout", list(LAYOUTS))
@pytest.mark.parametrize("aspect", list(ASPECT_PRESETS))
def test_tiles_within_canvas_for_every_camera_subset(layout, aspect):
    cw, ch = canvas_size(aspect, 720)
    for cams in _subsets():
        for main in cams:
            tiles = compute_tiles(layout, cams, main, cw, ch)
            if layout == "single":
                assert [t.camera for t in tiles] == [main]
            else:
                assert set(t.camera for t in tiles) == set(cams) and len(tiles) == len(cams)
            for t in tiles:
                assert t.w >= 2 and t.h >= 2
                assert t.w % 2 == 0 and t.h % 2 == 0 and t.x % 2 == 0 and t.y % 2 == 0
                assert 0 <= t.x and t.x + t.w <= cw
                assert 0 <= t.y and t.y + t.h <= ch


def test_single_layout_fills_canvas():
    tiles = compute_tiles("single", ["front", "back"], "back", 1920, 1080)
    assert len(tiles) == 1 and tiles[0].camera == "back"
    assert (tiles[0].w, tiles[0].h) == (1920, 1080)


def test_grid_picks_sensible_shape():
    tiles = compute_tiles("grid", ["front", "back", "left_repeater", "right_repeater"], "front", 1920, 1080)
    xs = sorted({t.x for t in tiles})
    ys = sorted({t.y for t in tiles})
    assert len(xs) == 2 and len(ys) == 2  # 2x2 on a landscape canvas
    # portrait: a 4-row stack keeps the 4:3 sources closer to their aspect than a 2x2 of tall tiles
    tiles = compute_tiles("grid", ["front", "back", "left_repeater", "right_repeater"], "front", 1080, 1920)
    assert len({t.x for t in tiles}) == 1 and len({t.y for t in tiles}) == 4
    six = compute_tiles("grid", CAMERAS, "front", 1920, 1080)
    assert len({t.x for t in six}) == 3 and len({t.y for t in six}) == 2


def test_pip_main_first_and_others_small():
    tiles = compute_tiles("pip", ["front", "back", "left_repeater"], "front", 1920, 1080)
    assert tiles[0].camera == "front" and tiles[0].w == 1920
    assert all(t.h < 1080 * 0.3 for t in tiles[1:])


def test_payload_normalised():
    p = layout_payload("side", ["front", "back", "left_repeater"], "front", "9:16")
    assert p["canvas"]["w"] < p["canvas"]["h"]
    for t in p["tiles"]:
        assert 0 <= t["x"] <= 1 and 0 <= t["y"] <= 1 and t["x"] + t["w"] <= 1.0001 and t["y"] + t["h"] <= 1.0001
