"""Thin wrapper around the ffmpeg binary: discovery, probing, encoder detection, progress parsing."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

from .paths import cache_dir

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _popen_kwargs() -> dict:
    kw: dict = {}
    if sys.platform == "win32":
        kw["creationflags"] = _CREATE_NO_WINDOW
    return kw


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    env = os.environ.get("TCE_FFMPEG")
    if env and Path(env).exists():
        return env
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError(
        "ffmpeg not found. Install the 'imageio-ffmpeg' package (pip install imageio-ffmpeg) "
        "or put ffmpeg on your PATH, or set TCE_FFMPEG to the executable."
    )


@lru_cache(maxsize=1)
def ffprobe_exe() -> Optional[str]:
    env = os.environ.get("TCE_FFPROBE")
    if env and Path(env).exists():
        return env
    sibling = Path(ffmpeg_exe()).with_name("ffprobe" + (".exe" if sys.platform == "win32" else ""))
    if sibling.exists():
        return str(sibling)
    return shutil.which("ffprobe")


@dataclass
class ProbeResult:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_RE = re.compile(r"Video:.*?\s(\d{2,5})x(\d{2,5})[,\s].*?(?:(\d+(?:\.\d+)?)\s*fps)?")
_AUDIO_RE = re.compile(r"Audio:")


def probe(path: str) -> ProbeResult:
    """Return duration/size/fps for a media file, using ffprobe when present and ffmpeg's banner otherwise."""
    fp = ffprobe_exe()
    if fp:
        try:
            out = subprocess.run(
                [fp, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
                capture_output=True,
                text=True,
                timeout=60,
                **_popen_kwargs(),
            ).stdout
            data = json.loads(out or "{}")
            fmt = data.get("format", {})
            duration = float(fmt.get("duration") or 0.0)
            width = height = 0
            fps = 0.0
            has_audio = False
            for s in data.get("streams", []):
                if s.get("codec_type") == "video" and not width:
                    width = int(s.get("width") or 0)
                    height = int(s.get("height") or 0)
                    fr = s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1"
                    num, _, den = fr.partition("/")
                    try:
                        fps = float(num) / float(den or 1)
                    except (ValueError, ZeroDivisionError):
                        fps = 0.0
                    if not duration and s.get("duration"):
                        duration = float(s["duration"])
                elif s.get("codec_type") == "audio":
                    has_audio = True
            if duration or width:
                return ProbeResult(duration, width, height, fps, has_audio)
        except Exception:
            pass

    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", path],
        capture_output=True,
        text=True,
        timeout=60,
        **_popen_kwargs(),
    )
    text = proc.stderr
    duration = 0.0
    m = _DURATION_RE.search(text)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    width = height = 0
    fps = 0.0
    m = _VIDEO_RE.search(text)
    if m:
        width, height = int(m.group(1)), int(m.group(2))
        if m.group(3):
            fps = float(m.group(3))
    return ProbeResult(duration, width, height, fps, bool(_AUDIO_RE.search(text)))


@lru_cache(maxsize=1)
def font_file() -> Optional[str]:
    """Locate a TrueType font for drawtext. Windows ships Arial; Linux usually has DejaVu."""
    env = os.environ.get("TCE_FONT")
    if env and Path(env).exists():
        return env
    candidates: list[str] = []
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        candidates += [
            os.path.join(windir, "Fonts", "segoeui.ttf"),
            os.path.join(windir, "Fonts", "arial.ttf"),
            os.path.join(windir, "Fonts", "consola.ttf"),
        ]
    elif sys.platform == "darwin":
        candidates += ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf"]
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def has_filter(name: str) -> bool:
    return name in available_filters()


@lru_cache(maxsize=1)
def available_filters() -> set[str]:
    out = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-filters"], capture_output=True, text=True, **_popen_kwargs()
    ).stdout
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "->" in parts[2]:
            names.add(parts[1])
    return names


HW_ENCODERS = ["h264_nvenc", "h264_amf", "h264_qsv", "h264_videotoolbox"]


def _encoder_cache_file() -> Path:
    return cache_dir() / "encoders.json"


def detect_encoders(force: bool = False) -> dict[str, bool]:
    """Test which H.264 encoders actually work on this machine (a listed encoder can still fail at runtime)."""
    cache = _encoder_cache_file()
    if not force and cache.exists():
        try:
            data = json.loads(cache.read_text())
            if data.get("ffmpeg") == ffmpeg_exe():
                return data["encoders"]
        except Exception:
            pass
    listed = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-encoders"], capture_output=True, text=True, **_popen_kwargs()
    ).stdout
    result: dict[str, bool] = {"libx264": "libx264" in listed}
    for enc in HW_ENCODERS:
        if enc not in listed:
            result[enc] = False
            continue
        proc = subprocess.run(
            [
                ffmpeg_exe(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=256x144:rate=30",
                "-frames:v",
                "5",
                "-c:v",
                enc,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            **_popen_kwargs(),
        )
        result[enc] = proc.returncode == 0
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"ffmpeg": ffmpeg_exe(), "encoders": result}))
    except Exception:
        pass
    return result


def pick_encoder(preference: str = "auto") -> str:
    encoders = detect_encoders()
    if preference != "auto":
        if encoders.get(preference):
            return preference
        return "libx264"
    for enc in HW_ENCODERS:
        if encoders.get(enc):
            return enc
    return "libx264"


def encoder_args(encoder: str, quality: str) -> list[str]:
    """Rate-control flags for the chosen encoder and quality preset."""
    q = {"draft": 0, "standard": 1, "high": 2}.get(quality, 1)
    if encoder == "libx264":
        crf = ["28", "22", "18"][q]
        preset = ["veryfast", "medium", "slow"][q]
        return ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p"]
    if encoder == "h264_nvenc":
        cq = ["30", "23", "19"][q]
        preset = ["p2", "p4", "p6"][q]
        return ["-c:v", "h264_nvenc", "-preset", preset, "-rc", "vbr", "-cq", cq, "-b:v", "0", "-pix_fmt", "yuv420p"]
    if encoder == "h264_amf":
        qp = ["30", "24", "20"][q]
        return ["-c:v", "h264_amf", "-rc", "cqp", "-qp_i", qp, "-qp_p", qp, "-quality", "quality", "-pix_fmt", "yuv420p"]
    if encoder == "h264_qsv":
        gq = ["30", "24", "20"][q]
        return ["-c:v", "h264_qsv", "-global_quality", gq, "-look_ahead", "0", "-pix_fmt", "nv12"]
    if encoder == "h264_videotoolbox":
        qv = ["45", "60", "75"][q]
        return ["-c:v", "h264_videotoolbox", "-q:v", qv, "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p"]


class FFmpegCancelled(Exception):
    pass


class FFmpegError(RuntimeError):
    pass


def run_ffmpeg(
    args: list[str],
    total_duration: Optional[float] = None,
    on_progress: Optional[Callable[[float], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> None:
    """Run ffmpeg with `-progress pipe:1`, reporting a 0..1 fraction through `on_progress`."""
    cmd = [ffmpeg_exe(), "-hide_banner", "-y", "-nostdin", "-loglevel", "error", "-progress", "pipe:1", *args]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **_popen_kwargs(),
    )
    stderr_chunks: list[str] = []

    def _drain_err() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_chunks.append(line)

    t = threading.Thread(target=_drain_err, daemon=True)
    t.start()
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            if cancel_event is not None and cancel_event.is_set():
                proc.kill()
                proc.wait()
                raise FFmpegCancelled()
            line = line.strip()
            if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                try:
                    us = int(line.split("=", 1)[1])
                except ValueError:
                    continue
                if total_duration and on_progress:
                    on_progress(max(0.0, min(1.0, us / 1_000_000 / total_duration)))
            elif line == "progress=end" and on_progress:
                on_progress(1.0)
    finally:
        proc.wait()
        t.join(timeout=5)
    if proc.returncode != 0:
        err = "".join(stderr_chunks).strip()
        raise FFmpegError(err[-4000:] if err else f"ffmpeg exited with code {proc.returncode}")


def run_ffmpeg_simple(args: list[str], timeout: Optional[float] = None) -> None:
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-y", "-nostdin", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        **_popen_kwargs(),
    )
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr.strip()[-4000:] or f"ffmpeg exited with code {proc.returncode}")
