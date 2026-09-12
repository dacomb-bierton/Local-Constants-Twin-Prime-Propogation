import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("TCE_DATA_DIR", str(Path(__file__).parent / ".tce_test_data"))

from teslacam_editor import ffmpeg_tools as ff  # noqa: E402

CAMS = ["front", "back", "left_repeater", "right_repeater", "left_pillar", "right_pillar"]
SEG_SECONDS = 3


def _make_clip(path: Path, seconds: float, hue: int, size: str = "320x240") -> None:
    # Distinct colours per camera so tiles can be told apart in the rendered output.
    src = f"color=c=0x{hue:06x}:s={size}:r=30,drawbox=x=10:y=10:w=60:h=40:c=white:t=fill"
    subprocess.run(
        [ff.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-t", f"{seconds}",
         "-i", src, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )


def make_event(folder: Path, stamps: list[str], cams: list[str], reason: str | None, trigger: str | None,
               missing: set[tuple[str, str]] = frozenset()) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for ts in stamps:
        for i, cam in enumerate(cams):
            if (ts, cam) in missing:
                continue
            _make_clip(folder / f"{ts}-{cam}.mp4", SEG_SECONDS, [0x3060C0, 0xC03030, 0x30A030, 0xC0A030, 0x8030C0, 0x30A0A0][i])
    if reason:
        meta = {
            "timestamp": trigger,
            "city": "Testville",
            "est_lat": "37.3861",
            "est_lon": "-122.0839",
            "reason": reason,
            "camera": "3",
        }
        (folder / "event.json").write_text(json.dumps(meta))


@pytest.fixture(scope="session")
def teslacam_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("usb") / "TeslaCam"
    saved = root / "SavedClips" / "2024-05-01_12-00-00"
    make_event(
        saved,
        ["2024-05-01_11-58-00", "2024-05-01_11-59-00", "2024-05-01_12-00-00"],
        CAMS,
        "user_interaction_honk",
        "2024-05-01T12:00:00",
    )
    sentry = root / "SentryClips" / "2024-05-02_20-30-10"
    make_event(
        sentry,
        ["2024-05-02_20-29-00", "2024-05-02_20-30-00"],
        CAMS[:4],
        "sentry_aware_object_detection",
        "2024-05-02T20:30:10",
        missing={("2024-05-02_20-30-00", "back")},
    )
    recent = root / "RecentClips"
    make_event(recent, ["2024-05-03_08-00-00", "2024-05-03_08-01-00"], CAMS[:4], None, None)
    make_event(recent, ["2024-05-03_09-30-00"], CAMS[:4], None, None)
    return root
