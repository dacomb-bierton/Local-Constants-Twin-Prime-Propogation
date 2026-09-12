"""Discover TeslaCam footage on disk and turn it into events made of synchronized multi-camera segments.

TeslaCam layout on the USB drive:

    TeslaCam/
      RecentClips/   <timestamp>-<camera>.mp4 ...           (flat rolling buffer)
      SavedClips/    <timestamp>/ event.json thumb.png <timestamp>-<camera>.mp4 ...
      SentryClips/   <timestamp>/ event.json thumb.png <timestamp>-<camera>.mp4 ...

Every segment is ~60 s and there is one file per camera: front, back, left_repeater, right_repeater and on
newer cars left_pillar / right_pillar.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import string
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from .models import CAMERAS, EventDetail, EventInfo, Segment
from .paths import cache_dir

FILE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})-(?P<cam>front|back|left_repeater|right_repeater|left_pillar|right_pillar)\.mp4$",
    re.IGNORECASE,
)
KINDS = ("SavedClips", "SentryClips", "RecentClips")

EVENT_CAMERA_CODES = {
    "0": "front",
    "1": "front",
    "2": "front",
    "3": "left_repeater",
    "4": "right_repeater",
    "5": "left_pillar",
    "6": "right_pillar",
    "7": "back",
}

REASON_LABELS = [
    ("user_interaction_honk", "Honk"),
    ("user_interaction_dashcam_icon_tapped", "Dashcam icon tapped"),
    ("user_interaction_dashcam_panel_save", "Saved from dashcam panel"),
    ("user_interaction_dashcam_launcher_action_tapped", "Saved from launcher"),
    ("user_interaction", "Manual save"),
    ("sentry_aware_object_detection", "Sentry: object detected"),
    ("sentry_aware_accel", "Sentry: impact / acceleration"),
    ("sentry_aware", "Sentry event"),
    ("sentry", "Sentry event"),
    ("collision", "Collision detected"),
]


def reason_label(reason: Optional[str]) -> Optional[str]:
    if not reason:
        return None
    for prefix, label in REASON_LABELS:
        if reason.startswith(prefix):
            return label
    return reason.replace("_", " ").capitalize()


def parse_ts(ts: str) -> float:
    """Filename timestamps are the car's local time; interpret them as local time on this machine."""
    dt = datetime.strptime(ts, "%Y-%m-%d_%H-%M-%S")
    return time.mktime(dt.timetuple())


def parse_event_ts(ts: str) -> Optional[float]:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d_%H-%M-%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return time.mktime(datetime.strptime(ts[:26], fmt).timetuple())
        except ValueError:
            continue
    return None


def _event_id(*parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode("utf-8", "replace")).hexdigest()
    return h[:16]


class DurationCache:
    """Persistent cache of probed segment durations keyed by path + size + mtime."""

    def __init__(self) -> None:
        self._file = cache_dir() / "durations.json"
        self._lock = threading.Lock()
        self._data: dict[str, float] = {}
        self._dirty = False
        try:
            self._data = json.loads(self._file.read_text())
        except Exception:
            self._data = {}

    @staticmethod
    def _key(path: str) -> str:
        try:
            st = os.stat(path)
            return f"{path}|{st.st_size}|{int(st.st_mtime)}"
        except OSError:
            return path

    def get(self, path: str) -> Optional[float]:
        with self._lock:
            return self._data.get(self._key(path))

    def set(self, path: str, duration: float) -> None:
        with self._lock:
            self._data[self._key(path)] = duration
            self._dirty = True

    def save(self) -> None:
        with self._lock:
            if not self._dirty:
                return
            try:
                self._file.write_text(json.dumps(self._data))
                self._dirty = False
            except Exception:
                pass


_durations = DurationCache()


def segment_duration(seg: Segment) -> float:
    """Probe (and cache) the real duration of a segment using its first available camera file."""
    from . import ffmpeg_tools

    for cam in CAMERAS:
        path = seg.files.get(cam)
        if not path:
            continue
        cached = _durations.get(path)
        if cached is not None:
            return cached
        try:
            d = ffmpeg_tools.probe(path).duration
        except Exception:
            d = 0.0
        if d <= 0:
            continue
        _durations.set(path, d)
        _durations.save()
        return d
    return 60.0


def normalize_root(root: str) -> Path:
    p = Path(root).expanduser()
    if (p / "TeslaCam").is_dir():
        return p / "TeslaCam"
    return p


def _group_files(folder: Path) -> dict[str, dict[str, str]]:
    """timestamp -> camera -> path for all TeslaCam mp4 files directly inside `folder`."""
    groups: dict[str, dict[str, str]] = {}
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return groups
    for entry in entries:
        if not entry.is_file():
            continue
        m = FILE_RE.match(entry.name)
        if not m:
            continue
        ts = m.group("ts")
        cam = m.group("cam").lower()
        groups.setdefault(ts, {})[cam] = entry.path
    return groups


def _segments_from_groups(groups: dict[str, dict[str, str]]) -> list[Segment]:
    segs = []
    for ts in sorted(groups):
        try:
            epoch = parse_ts(ts)
        except ValueError:
            continue
        segs.append(Segment(start=ts, start_epoch=epoch, files=groups[ts]))
    return segs


def _read_event_json(folder: Path) -> dict:
    f = folder / "event.json"
    if not f.is_file():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _folder_size(files: Iterable[str]) -> int:
    total = 0
    for f in files:
        try:
            total += os.path.getsize(f)
        except OSError:
            pass
    return total


def _build_event(kind: str, folder: Path, segments: list[Segment], meta: dict, root: Path, title: Optional[str] = None) -> EventDetail:
    if not segments:
        raise ValueError("event without segments")
    cameras = [c for c in CAMERAS if any(c in s.files for s in segments)]
    first = segments[0]
    total = 0.0
    for s in segments:
        s.duration = s.duration or 60.0
        total += s.duration
    trigger_epoch = parse_event_ts(str(meta.get("timestamp"))) if meta.get("timestamp") else None
    trigger_offset = None
    if trigger_epoch is not None:
        trigger_offset = max(0.0, min(total, trigger_epoch - first.start_epoch))

    def _float(v) -> Optional[float]:
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    start_dt = datetime.fromtimestamp(first.start_epoch)
    if title is None:
        title = start_dt.strftime("%a %d %b %Y, %H:%M:%S")
    all_files = [p for s in segments for p in s.files.values()]
    return EventDetail(
        id=_event_id(str(root), kind, str(folder), first.start),
        kind=kind,  # type: ignore[arg-type]
        folder=str(folder),
        title=title,
        start=first.start,
        start_epoch=first.start_epoch,
        duration=total,
        cameras=cameras,
        segment_count=len(segments),
        reason=meta.get("reason"),
        reason_label=reason_label(meta.get("reason")),
        city=meta.get("city") or None,
        lat=_float(meta.get("est_lat")),
        lon=_float(meta.get("est_lon")),
        trigger_epoch=trigger_epoch,
        trigger_offset=trigger_offset,
        trigger_camera=EVENT_CAMERA_CODES.get(str(meta.get("camera"))) if meta.get("camera") is not None else None,
        has_thumb=(folder / "thumb.png").is_file(),
        size_bytes=_folder_size(all_files),
        segments=segments,
    )


def _scan_event_folders(kind: str, parent: Path, root: Path) -> list[EventDetail]:
    events = []
    try:
        subdirs = [d for d in os.scandir(parent) if d.is_dir()]
    except OSError:
        return events
    for d in subdirs:
        groups = _group_files(Path(d.path))
        segs = _segments_from_groups(groups)
        if not segs:
            continue
        meta = _read_event_json(Path(d.path))
        try:
            events.append(_build_event(kind, Path(d.path), segs, meta, root))
        except ValueError:
            continue
    return events


def _scan_flat(kind: str, folder: Path, root: Path, max_gap: float = 120.0) -> list[EventDetail]:
    """RecentClips is a flat folder; group consecutive segments into drives."""
    segs = _segments_from_groups(_group_files(folder))
    events: list[EventDetail] = []
    if not segs:
        return events
    current: list[Segment] = [segs[0]]
    for s in segs[1:]:
        if s.start_epoch - current[-1].start_epoch > max_gap:
            events.append(_flat_event(kind, folder, current, root))
            current = [s]
        else:
            current.append(s)
    events.append(_flat_event(kind, folder, current, root))
    return events


def _flat_event(kind: str, folder: Path, segs: list[Segment], root: Path) -> EventDetail:
    first = datetime.fromtimestamp(segs[0].start_epoch)
    last = datetime.fromtimestamp(segs[-1].start_epoch + 60)
    title = f"Drive {first.strftime('%a %d %b %Y, %H:%M')}–{last.strftime('%H:%M')}"
    return _build_event(kind, folder, segs, {}, root, title=title)


def scan(root: str) -> list[EventDetail]:
    """Scan a TeslaCam folder (or drive root, or a single clips folder) and return all events, newest first."""
    base = normalize_root(root)
    if not base.is_dir():
        raise FileNotFoundError(f"Folder not found: {root}")
    events: list[EventDetail] = []
    found_kind_folder = False
    for kind in KINDS:
        sub = base / kind
        if sub.is_dir():
            found_kind_folder = True
            if kind == "RecentClips":
                events += _scan_flat(kind, sub, base)
            else:
                events += _scan_event_folders(kind, sub, base)
    if not found_kind_folder:
        name = base.name
        if name in KINDS:
            kind = name
            if kind == "RecentClips":
                events += _scan_flat(kind, base, base.parent)
            else:
                events += _scan_event_folders(kind, base, base.parent)
        else:
            direct = _segments_from_groups(_group_files(base))
            if direct:
                # A single event folder (or an arbitrary folder of clips).
                meta = _read_event_json(base)
                kind = "SentryClips" if str(meta.get("reason", "")).startswith("sentry") else "SavedClips"
                events.append(_build_event(kind, base, direct, meta, base.parent))
            else:
                events += _scan_event_folders("SavedClips", base, base)
    events.sort(key=lambda e: e.start_epoch, reverse=True)
    return events


def resolve_durations(event: EventDetail) -> EventDetail:
    """Replace the 60 s placeholder durations with probed values and recompute the derived fields."""
    total = 0.0
    for seg in event.segments:
        seg.duration = segment_duration(seg)
        total += seg.duration
    event.duration = total
    if event.trigger_epoch is not None:
        event.trigger_offset = max(0.0, min(total, event.trigger_epoch - event.start_epoch))
    return event


def event_time_to_segment(event: EventDetail, t: float) -> tuple[Segment, float]:
    """Map a time on the event timeline to (segment, offset inside that segment)."""
    acc = 0.0
    for seg in event.segments:
        if t < acc + seg.duration or seg is event.segments[-1]:
            return seg, max(0.0, min(seg.duration, t - acc))
        acc += seg.duration
    seg = event.segments[-1]
    return seg, seg.duration


def find_teslacam_roots() -> list[str]:
    """Best-effort auto-detection of plugged-in TeslaCam drives."""
    found: list[str] = []
    candidates: list[Path] = []
    if sys.platform == "win32":
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:\\")
            if drive.exists():
                candidates.append(drive)
    else:
        for base in ("/media", "/mnt", "/Volumes", "/run/media"):
            b = Path(base)
            if not b.is_dir():
                continue
            try:
                for d in b.iterdir():
                    candidates.append(d)
                    if d.is_dir():
                        try:
                            candidates += [x for x in d.iterdir() if x.is_dir()]
                        except OSError:
                            pass
            except OSError:
                pass
    for c in candidates:
        try:
            if (c / "TeslaCam").is_dir():
                found.append(str(c / "TeslaCam"))
        except OSError:
            continue
    return found


def list_directory(path: Optional[str]) -> dict:
    """Server-side folder browser used by the UI (browsers cannot reveal absolute paths of picked folders)."""
    if not path:
        roots: list[dict] = []
        if sys.platform == "win32":
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if Path(drive).exists():
                    roots.append({"name": drive, "path": drive})
        else:
            roots.append({"name": "/", "path": "/"})
            home = str(Path.home())
            roots.append({"name": "Home", "path": home})
            for base in ("/media", "/mnt", "/Volumes"):
                if Path(base).is_dir():
                    roots.append({"name": base, "path": base})
        return {"path": None, "parent": None, "dirs": roots, "is_teslacam": False}
    p = Path(path).expanduser()
    if not p.is_dir():
        raise FileNotFoundError(path)
    dirs = []
    try:
        for entry in sorted(os.scandir(p), key=lambda e: e.name.lower()):
            if entry.is_dir(follow_symlinks=False) and not entry.name.startswith((".", "$")):
                dirs.append({"name": entry.name, "path": entry.path})
    except OSError:
        pass
    parent = str(p.parent) if p.parent != p else None
    is_tc = any((p / k).is_dir() for k in KINDS) or (p / "TeslaCam").is_dir() or p.name in KINDS
    return {"path": str(p), "parent": parent, "dirs": dirs, "is_teslacam": is_tc}
