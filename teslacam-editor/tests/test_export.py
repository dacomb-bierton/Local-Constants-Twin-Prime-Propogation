import subprocess
from pathlib import Path

import pytest

from teslacam_editor import export as exporter
from teslacam_editor import ffmpeg_tools as ff
from teslacam_editor import scanner
from teslacam_editor.models import BlurRegion, ExportSettings, MusicTrack, Project, SequenceItem, StillRequest


@pytest.fixture(scope="module")
def library(teslacam_root):
    events = scanner.scan(str(teslacam_root))
    for e in events:
        scanner.resolve_durations(e)
    return {e.id: e for e in events}


def _by_kind(library, kind):
    return next(e for e in library.values() if e.kind == kind)


def _make_music(path: Path, seconds: float = 4.0) -> Path:
    subprocess.run(
        [ff.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-t", str(seconds),
         "-i", "sine=frequency=440:sample_rate=44100", "-c:a", "aac", str(path)],
        check=True,
    )
    return path


def test_expand_items_cycles_cameras(library):
    saved = _by_kind(library, "SavedClips")
    item = SequenceItem(id="a", event_id=saved.id, in_point=0, out_point=6, cameras=["front", "back", "left_repeater"],
                        layout="pip", main_camera="back", cycle_enabled=True, cycle_interval=2.0)
    units = exporter.expand_items(Project(items=[item]), library)
    assert [u.main for u in units] == ["back", "left_repeater", "front"]
    assert [round(u.t0) for u in units] == [0, 2, 4]


def test_covering_segments_handles_missing_camera(library):
    sentry = _by_kind(library, "SentryClips")
    pieces = exporter.covering_segments(sentry, 1.0, sentry.duration, "back")
    assert len(pieces) == 2
    assert pieces[0].file and pieces[0].file.endswith("back.mp4")
    assert pieces[1].file is None  # black filler for the missing file
    assert abs(pieces[0].ss - 1.0) < 0.01


@pytest.mark.parametrize("aspect,short,expected", [
    ("16:9", 360, (640, 360)),
    ("9:16", 360, (360, 640)),
    ("1:1", 360, (360, 360)),
])
def test_export_multi_clip_all_features(library, tmp_path, aspect, short, expected):
    saved = _by_kind(library, "SavedClips")
    sentry = _by_kind(library, "SentryClips")
    music = _make_music(tmp_path / "music.m4a")
    project = Project(
        name="Test",
        items=[
            SequenceItem(id="1", event_id=saved.id, in_point=1.0, out_point=5.0, cameras=saved.cameras, layout="grid",
                         main_camera="front", show_timestamp=True, show_labels=True, show_location=True,
                         blur_regions=[BlurRegion(x=0.1, y=0.1, w=0.2, h=0.2)]),
            SequenceItem(id="2", event_id=sentry.id, in_point=0.0, out_point=4.0, cameras=sentry.cameras, layout="pip",
                         main_camera="front", cycle_enabled=True, cycle_interval=1.5, mirror_rear=True, speed=2.0),
            SequenceItem(id="3", event_id=saved.id, in_point=2.0, out_point=3.0, cameras=["left_repeater", "front", "right_repeater"],
                         layout="three_wide", main_camera="front", speed=0.5, fit="contain"),
        ],
        music=MusicTrack(path=str(music), volume=0.6, fade_in=0.5, fade_out=1.0, loop=True, offset=0.5),
        export=ExportSettings(aspect=aspect, resolution=short, fps=24, quality="draft", output_dir=str(tmp_path)),
    )
    progress = []
    out = exporter.export_project(project, library, lambda f, m: progress.append((f, m)))
    assert Path(out).is_file() and Path(out).suffix == ".mp4"
    info = ff.probe(out)
    assert (info.width, info.height) == expected
    # 4 s + 4 s / 2 + 1 s / 0.5 = 8 s
    assert abs(info.duration - 8.0) < 0.6
    assert info.has_audio
    assert progress and progress[-1][0] == 1.0


def test_export_gif_and_watermark(library, tmp_path):
    saved = _by_kind(library, "SavedClips")
    wm = tmp_path / "wm.png"
    subprocess.run([ff.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=red:s=64x32", "-frames:v", "1", str(wm)], check=True)
    project = Project(
        items=[SequenceItem(id="1", event_id=saved.id, in_point=0.0, out_point=2.0, cameras=["front", "back"], layout="side")],
        export=ExportSettings(aspect="4:3", resolution=240, fps=12, format="gif", output_dir=str(tmp_path),
                              watermark_path=str(wm), filename="clip"),
    )
    out = exporter.export_project(project, library)
    assert Path(out).name == "clip.gif"
    info = ff.probe(out)
    assert (info.width, info.height) == (320, 240)


def test_render_still(library, tmp_path):
    saved = _by_kind(library, "SavedClips")
    req = StillRequest(event_id=saved.id, time=4.0, cameras=saved.cameras, layout="cinematic", main_camera="front",
                       aspect="16:9", resolution=360, output_dir=str(tmp_path))
    out = exporter.render_still(req, saved)
    info = ff.probe(out)
    assert (info.width, info.height) == (640, 360)


def _frame(video: str, t: float, out: Path):
    from PIL import Image

    subprocess.run([ff.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", video,
                    "-frames:v", "1", "-update", "1", str(out)], check=True)
    return Image.open(out).convert("RGB")


def test_timestamp_overlay_is_drawn_and_advances(library, tmp_path):
    saved = _by_kind(library, "SavedClips")
    project = Project(
        items=[SequenceItem(id="1", event_id=saved.id, in_point=0.0, out_point=3.0, cameras=["front"], layout="single",
                            show_timestamp=True)],
        export=ExportSettings(aspect="16:9", resolution=360, fps=10, quality="draft", output_dir=str(tmp_path)),
    )
    out = exporter.export_project(project, library)
    f0 = _frame(out, 0.2, tmp_path / "f0.png")
    f2 = _frame(out, 2.7, tmp_path / "f2.png")
    # The timestamp box sits in the top-left of the main tile; the synthetic footage is a flat colour there.
    region = (8, 8, 220, 36)
    assert len(set(f0.crop(region).tobytes())) > 20, "timestamp text not rendered"
    assert f0.crop(region).tobytes() != f2.crop(region).tobytes(), "clock did not advance"


def test_export_raw_joins_segments_without_reencoding(library, tmp_path):
    saved = _by_kind(library, "SavedClips")
    outs = exporter.export_raw(saved, ["front", "back"], str(tmp_path))
    assert len(outs) == 2 and all(Path(o).is_file() for o in outs)
    info = ff.probe(outs[0])
    assert abs(info.duration - saved.duration) < 0.5
    assert (info.width, info.height) == (320, 240)  # untouched source resolution


def test_export_rejects_empty(library):
    with pytest.raises(ValueError):
        exporter.export_project(Project(), library)
