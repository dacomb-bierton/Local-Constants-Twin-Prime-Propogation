"""Render a project (sequence of multi-camera clips + music) to a single video with ffmpeg.

Pipeline:
  1. Every sequence item is expanded into *render units*.  Camera cycling splits an item into consecutive
     units whose main camera rotates.
  2. Each unit is rendered to an intermediate MP4: per camera the covering segment files are trimmed,
     scaled/cropped to their tile, mirrored/labelled, joined with the concat filter, then all cameras are
     overlaid on a solid canvas.  Timestamps are drawn per source segment so the clock is exact even when the
     playback speed is changed.  Blur regions and a watermark are applied on the finished canvas.
  3. The intermediates are concatenated with stream copy (identical codec parameters), then music is mixed in
     (loop, offset, volume, fades) or the result is converted to GIF.
"""

from __future__ import annotations

import math
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from . import ffmpeg_tools as ff
from . import overlays
from .layouts import Tile, canvas_size, compute_tiles
from .models import CAMERA_LABELS, EventDetail, ExportSettings, MusicTrack, Project, SequenceItem, StillRequest
from .paths import cache_dir, default_export_dir

ProgressFn = Callable[[float, str], None]


@dataclass
class RenderUnit:
    event: EventDetail
    t0: float
    t1: float
    cameras: list[str]
    layout: str
    main: str
    fit: str
    speed: float
    mirror_rear: bool
    show_timestamp: bool
    show_labels: bool
    show_location: bool
    blur_regions: list = field(default_factory=list)

    @property
    def source_duration(self) -> float:
        return max(0.0, self.t1 - self.t0)

    @property
    def output_duration(self) -> float:
        return self.source_duration / max(0.05, self.speed)


@dataclass
class _Cover:
    file: Optional[str]
    ss: float
    dur: float
    epoch: float  # wall-clock epoch of the first rendered frame of this piece


def covering_segments(event: EventDetail, t0: float, t1: float, camera: str) -> list[_Cover]:
    """Segment pieces of `camera` that cover [t0, t1) on the event timeline (None file => black filler)."""
    pieces: list[_Cover] = []
    acc = 0.0
    for seg in event.segments:
        s0, s1 = acc, acc + seg.duration
        if s1 > t0 and s0 < t1:
            ss = max(0.0, t0 - s0)
            te = min(seg.duration, t1 - s0)
            if te - ss > 0.001:
                pieces.append(_Cover(seg.files.get(camera), ss, te - ss, seg.start_epoch + ss))
        acc = s1
    if not pieces:
        pieces.append(_Cover(None, 0.0, max(0.04, t1 - t0), event.start_epoch + t0))
    return pieces


def expand_items(project: Project, events: dict[str, EventDetail]) -> list[RenderUnit]:
    units: list[RenderUnit] = []
    for item in project.items:
        ev = events.get(item.event_id)
        if ev is None:
            raise ValueError(f"Event {item.event_id} is not in the library any more")
        t0 = max(0.0, min(item.in_point, ev.duration))
        t1 = max(t0, min(item.out_point, ev.duration))
        if t1 - t0 < 0.04:
            continue
        cams = [c for c in item.cameras if c in ev.cameras] or ev.cameras[:1]
        main = item.main_camera if item.main_camera in cams else cams[0]
        common = dict(
            event=ev,
            cameras=cams,
            layout=item.layout,
            fit=item.fit,
            speed=item.speed,
            mirror_rear=item.mirror_rear,
            show_timestamp=item.show_timestamp,
            show_labels=item.show_labels,
            show_location=item.show_location,
            blur_regions=list(item.blur_regions),
        )
        if item.cycle_enabled and len(cams) > 1 and item.cycle_interval > 0.1:
            cycle = [c for c in (item.cycle_cameras or cams) if c in cams] or cams
            # Start the rotation at the chosen main camera when it is part of the cycle.
            if main in cycle:
                idx = cycle.index(main)
                cycle = cycle[idx:] + cycle[:idx]
            t = t0
            k = 0
            while t < t1 - 0.001:
                end = min(t1, t + item.cycle_interval)
                units.append(RenderUnit(t0=t, t1=end, main=cycle[k % len(cycle)], **common))
                t = end
                k += 1
        else:
            units.append(RenderUnit(t0=t0, t1=t1, main=main, **common))
    return units


def epoch_at(event: EventDetail, t: float) -> float:
    """Wall-clock time of position t on the event timeline, using each segment's own start time."""
    acc = 0.0
    for seg in event.segments:
        if t < acc + seg.duration:
            return seg.start_epoch + (t - acc)
        acc += seg.duration
    last = event.segments[-1]
    return last.start_epoch + last.duration + (t - acc)


def _hex_color(c: str) -> str:
    c = (c or "#000000").strip()
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", c):
        return "0x" + c.lstrip("#")
    return c or "black"


def _intersects(x: int, y: int, w: int, h: int, tile: Tile) -> bool:
    return x < tile.x + tile.w and x + w > tile.x and y < tile.y + tile.h and y + h > tile.y


def _fit_filter(fit: str, w: int, h: int, bg: str) -> str:
    if fit == "contain":
        return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={bg}"
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"


class UnitGraph:
    """Builds the ffmpeg argument list for one render unit."""

    def __init__(
        self,
        unit: RenderUnit,
        settings: ExportSettings,
        canvas: tuple[int, int],
        assets_dir: Path,
        single_frame: bool = False,
    ):
        self.unit = unit
        self.settings = settings
        self.cw, self.ch = canvas
        self.fps = max(1, settings.fps)
        self.bg = _hex_color(settings.background)
        self.single_frame = single_frame
        self.assets_dir = assets_dir
        self.inputs: list[str] = []
        self.filters: list[str] = []
        self.n_inputs = 0
        self._asset_n = 0

    def _add_input(self, args: list[str]) -> int:
        self.inputs += args
        idx = self.n_inputs
        self.n_inputs += 1
        return idx

    def _asset(self, name: str) -> Path:
        self._asset_n += 1
        return self.assets_dir / f"{name}_{self._asset_n}.png"

    def _camera_stream(self, tile: Tile, tag: str) -> str:
        u = self.unit
        pieces = covering_segments(u.event, u.t0, u.t1, tile.camera)
        labels = []
        mirror = u.mirror_rear and tile.camera != "front"
        for j, piece in enumerate(pieces):
            if piece.file:
                args = []
                if piece.ss > 0.0005:
                    args += ["-ss", f"{piece.ss:.3f}"]
                args += ["-t", f"{piece.dur:.3f}", "-i", piece.file]
            else:
                args = ["-f", "lavfi", "-t", f"{piece.dur:.3f}", "-i", f"color=c=black:s=64x48:r={self.fps}"]
            idx = self._add_input(args)
            chain = [f"fps={self.fps}", _fit_filter(u.fit, tile.w, tile.h, self.bg)]
            if mirror:
                chain.append("hflip")
            chain.append("setsar=1")
            out = f"[{tag}_{j}]"
            self.filters.append(f"[{idx}:v]" + ",".join(chain) + out)
            labels.append(out)
        if len(labels) == 1:
            joined = labels[0]
        else:
            joined = f"[{tag}_cat]"
            self.filters.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0" + joined)
        if abs(u.speed - 1.0) > 1e-3:
            out = f"[{tag}_spd]"
            self.filters.append(f"{joined}setpts=PTS/{u.speed:.4f},fps={self.fps}{out}")
            joined = out
        return joined

    def _image_input(self, path: Path, duration: float) -> int:
        return self._add_input(["-loop", "1", "-framerate", str(self.fps), "-t", f"{duration:.3f}", "-i", str(path)])

    def _text_overlays(self, current: str, tiles: list[Tile], out_dur: float) -> str:
        """Timestamp / location on the main tile and camera labels on every tile."""
        u = self.unit
        main_tile = next((t for t in tiles if t.camera == u.main), tiles[0])
        n = 0
        if u.show_timestamp:
            fs = max(14, int(main_tile.h * 0.045))
            m = max(6, int(main_tile.h * 0.02))
            first_epoch = epoch_at(u.event, u.t0)
            rows = int(math.ceil(u.source_duration)) + 2
            sprite = self._asset("clock")
            w, h, rows = overlays.render_clock_sprite(first_epoch, rows, fs, sprite)
            idx = self._image_input(sprite, out_dur + 0.5)
            frac = first_epoch - int(first_epoch)
            row_expr = f"min({rows - 1}\\,floor({frac:.3f}+t*{u.speed:.4f}))"
            self.filters.append(f"[{idx}:v]crop={w}:{h}:0:{h}*{row_expr}[clock]")
            self.filters.append(f"{current}[clock]overlay=x={main_tile.x + m}:y={main_tile.y + m}:eof_action=repeat[tx{n}]")
            current = f"[tx{n}]"
            n += 1
            if u.show_location:
                parts = [p for p in (u.event.city, u.event.reason_label) if p]
                if parts:
                    png = self._asset("loc")
                    lw, lh = overlays.render_text_png(" · ".join(parts), int(fs * 0.85), png)
                    idx = self._image_input(png, out_dur + 0.5)
                    self.filters.append(f"{current}[{idx}:v]overlay=x={main_tile.x + m}:y={main_tile.y + m + h + 4}:eof_action=repeat[tx{n}]")
                    current = f"[tx{n}]"
                    n += 1
        if u.show_labels:
            for tile in tiles:
                fs = max(12, int(tile.h * 0.05))
                m = max(6, int(tile.h * 0.02))
                png = self._asset("label")
                lw, lh = overlays.render_text_png(CAMERA_LABELS.get(tile.camera, tile.camera), fs, png)
                idx = self._image_input(png, out_dur + 0.5)
                x = tile.x + tile.w - lw - m
                y = tile.y + tile.h - lh - m
                others = [t for t in tiles if t is not tile]
                if any(_intersects(x, y, lw, lh, t) for t in others):
                    y = tile.y + m  # bottom-right is covered by a PiP thumbnail; use the top-right corner
                self.filters.append(f"{current}[{idx}:v]overlay=x={x}:y={y}:eof_action=repeat[tx{n}]")
                current = f"[tx{n}]"
                n += 1
        return current

    def build(self, output: str) -> list[str]:
        u = self.unit
        tiles = compute_tiles(u.layout, u.cameras, u.main, self.cw, self.ch)
        out_dur = 0.2 if self.single_frame else u.output_duration
        base_idx = self._add_input(
            ["-f", "lavfi", "-t", f"{out_dur + 0.5:.3f}", "-i", f"color=c={self.bg}:s={self.cw}x{self.ch}:r={self.fps}"]
        )
        current = f"[{base_idx}:v]"
        for i, tile in enumerate(tiles):
            stream = self._camera_stream(tile, f"c{i}")
            out = f"[ov{i}]"
            self.filters.append(f"{current}{stream}overlay=x={tile.x}:y={tile.y}:eof_action=repeat{out}")
            current = out
        current = self._text_overlays(current, tiles, out_dur)
        for i, region in enumerate(u.blur_regions):
            rw, rh = max(2, int(region.w * self.cw)), max(2, int(region.h * self.ch))
            rx, ry = int(region.x * self.cw), int(region.y * self.ch)
            rx, ry = max(0, min(self.cw - rw, rx)), max(0, min(self.ch - rh, ry))
            radius = max(2, min(rw, rh) // 8)
            self.filters.append(f"{current}split[bsrc{i}][bcpy{i}]")
            self.filters.append(f"[bcpy{i}]crop={rw}:{rh}:{rx}:{ry},boxblur={radius}:2[blur{i}]")
            self.filters.append(f"[bsrc{i}][blur{i}]overlay=x={rx}:y={ry}[bl{i}]")
            current = f"[bl{i}]"
        wm = self.settings.watermark_path
        if wm and Path(wm).is_file():
            idx = self._add_input(["-loop", "1", "-t", f"{out_dur + 0.5:.3f}", "-i", wm])
            ww = max(16, int(self.cw * max(0.02, min(0.6, self.settings.watermark_scale))))
            op = max(0.0, min(1.0, self.settings.watermark_opacity))
            m = max(8, int(self.ch * 0.02))
            pos = {
                "tl": f"x={m}:y={m}",
                "tr": f"x=W-w-{m}:y={m}",
                "bl": f"x={m}:y=H-h-{m}",
                "br": f"x=W-w-{m}:y=H-h-{m}",
            }[self.settings.watermark_position]
            self.filters.append(f"[{idx}:v]scale={ww}:-1,format=rgba,colorchannelmixer=aa={op:.3f}[wm]")
            self.filters.append(f"{current}[wm]overlay={pos}:shortest=0[wmv]")
            current = "[wmv]"
        self.filters.append(f"{current}format=yuv420p[vout]")
        args = [*self.inputs, "-filter_complex", ";".join(self.filters), "-map", "[vout]", "-an"]
        if self.single_frame:
            args += ["-frames:v", "1", "-q:v", "2", "-update", "1", output]
        else:
            enc = ff.pick_encoder(self.settings.encoder)
            args += ["-t", f"{out_dur:.3f}", "-r", str(self.fps), "-fps_mode", "cfr", *ff.encoder_args(enc, self.settings.quality)]
            args += ["-movflags", "+faststart", output]
        return args


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^\w\-. ()]+", "_", name).strip(" .")
    return name or "export"


def output_path(project: Project, events: dict[str, EventDetail]) -> Path:
    s = project.export
    out_dir = Path(s.output_dir) if s.output_dir else default_export_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    if s.filename:
        stem = _safe_filename(Path(s.filename).stem)
    else:
        first = events.get(project.items[0].event_id) if project.items else None
        if project.name and project.name != "Untitled":
            base = project.name
        elif first is not None:
            base = f"TeslaCam {first.kind.replace('Clips', '')} {first.start}"
        else:
            base = "TeslaCam export"
        stem = _safe_filename(f"{base} {s.aspect.replace(':', 'x')} {datetime.now():%Y%m%d-%H%M%S}")
    ext = ".gif" if s.format == "gif" else ".mp4"
    path = out_dir / (stem + ext)
    n = 1
    while path.exists():
        path = out_dir / f"{stem} ({n}){ext}"
        n += 1
    return path


def _workdir() -> Path:
    base = cache_dir() / "work"
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="tce_", dir=base))


def _music_args(music: MusicTrack, total: float) -> tuple[list[str], str]:
    """Extra input + audio filter chain for the music track."""
    args: list[str] = []
    if music.loop:
        args += ["-stream_loop", "-1"]
    if music.offset > 0:
        args += ["-ss", f"{music.offset:.3f}"]
    args += ["-i", music.path]
    chain = [f"volume={max(0.0, music.volume):.3f}"]
    if music.video_offset > 0:
        ms = int(music.video_offset * 1000)
        chain.append(f"adelay=delays={ms}:all=1")
    if music.fade_in > 0:
        chain.append(f"afade=t=in:st={music.video_offset:.3f}:d={music.fade_in:.3f}")
    if music.fade_out > 0 and total > music.fade_out:
        chain.append(f"afade=t=out:st={total - music.fade_out:.3f}:d={music.fade_out:.3f}")
    chain.append(f"atrim=0:{total:.3f}")
    chain.append("asetpts=PTS-STARTPTS")
    return args, ",".join(chain)


def export_project(
    project: Project,
    events: dict[str, EventDetail],
    progress: Optional[ProgressFn] = None,
    cancel: Optional[threading.Event] = None,
) -> str:
    def report(frac: float, msg: str) -> None:
        if progress:
            progress(max(0.0, min(1.0, frac)), msg)

    units = expand_items(project, events)
    if not units:
        raise ValueError("Nothing to export: add at least one clip to the sequence")
    settings = project.export
    canvas = canvas_size(settings.aspect, settings.resolution)
    total = sum(u.output_duration for u in units)
    work = _workdir()
    final = output_path(project, events)
    try:
        parts: list[Path] = []
        done = 0.0
        for i, unit in enumerate(units):
            if cancel and cancel.is_set():
                raise ff.FFmpegCancelled()
            part = work / f"part_{i:04d}.mp4"
            args = UnitGraph(unit, settings, canvas, work).build(str(part))
            label = f"Rendering clip {i + 1}/{len(units)}"
            report(done / total * 0.9, label)
            weight = unit.output_duration
            ff.run_ffmpeg(
                args,
                total_duration=weight,
                on_progress=lambda f, d=done, w=weight: report((d + f * w) / total * 0.9, label),
                cancel_event=cancel,
            )
            done += weight
            parts.append(part)

        if len(parts) == 1:
            joined = parts[0]
        else:
            report(0.9, "Joining clips")
            lst = work / "concat.txt"
            lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
            joined = work / "joined.mp4"
            ff.run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(joined)], cancel_event=cancel)

        if settings.format == "gif":
            report(0.93, "Converting to GIF")
            gif_fps = min(20, settings.fps)
            vf = f"fps={gif_fps},split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle"
            ff.run_ffmpeg(["-i", str(joined), "-filter_complex", vf, "-loop", "0", str(final)], total_duration=total, on_progress=lambda f: report(0.93 + f * 0.07, "Converting to GIF"), cancel_event=cancel)
        elif project.music and Path(project.music.path).is_file():
            report(0.95, "Mixing music")
            m_args, a_chain = _music_args(project.music, total)
            args = ["-i", str(joined), *m_args, "-filter_complex", f"[1:a]{a_chain}[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(final)]
            ff.run_ffmpeg(args, total_duration=total, on_progress=lambda f: report(0.95 + f * 0.05, "Mixing music"), cancel_event=cancel)
        else:
            shutil.move(str(joined), str(final))
        report(1.0, "Done")
        return str(final)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_still(req: StillRequest, event: EventDetail) -> str:
    cams = [c for c in req.cameras if c in event.cameras] or event.cameras[:1]
    main = req.main_camera if req.main_camera in cams else cams[0]
    t = max(0.0, min(event.duration - 0.05, req.time))
    unit = RenderUnit(
        event=event,
        t0=t,
        t1=t + 0.2,
        cameras=cams,
        layout=req.layout,
        main=main,
        fit=req.fit,
        speed=1.0,
        mirror_rear=req.mirror_rear,
        show_timestamp=req.show_timestamp,
        show_labels=False,
        show_location=False,
    )
    settings = ExportSettings(aspect=req.aspect, resolution=req.resolution)
    out_dir = Path(req.output_dir) if req.output_dir else default_export_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_filename(f"TeslaCam {event.start} +{t:.1f}s {req.aspect.replace(':', 'x')}")
    out = out_dir / f"{stem}.jpg"
    n = 1
    while out.exists():
        out = out_dir / f"{stem} ({n}).jpg"
        n += 1
    work = _workdir()
    try:
        args = UnitGraph(unit, settings, canvas_size(req.aspect, req.resolution), work, single_frame=True).build(str(out))
        ff.run_ffmpeg_simple(args, timeout=120)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return str(out)


def frame_at(event: EventDetail, camera: str, t: float, out: Path, width: int = 480) -> Optional[Path]:
    """Quick single-camera thumbnail at event time t."""
    from .scanner import event_time_to_segment

    t = max(0.0, min(t, event.duration - 0.5))
    seg, off = event_time_to_segment(event, t)
    off = max(0.0, min(off, seg.duration - 0.5))
    path = seg.files.get(camera) or next(iter(seg.files.values()), None)
    if not path:
        return None
    args = ["-ss", f"{off:.3f}", "-i", path, "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", "-update", "1", str(out)]
    try:
        ff.run_ffmpeg_simple(args, timeout=60)
    except ff.FFmpegError:
        return None
    return out if out.exists() else None


def export_raw(event: EventDetail, cameras: list[str], output_dir: Optional[str] = None) -> list[str]:
    """Join the original segment files of each camera with stream copy (no re-encoding, no quality loss)."""
    out_dir = Path(output_dir) if output_dir else default_export_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    work = _workdir()
    outputs: list[str] = []
    try:
        for cam in cameras:
            files = [seg.files[cam] for seg in event.segments if cam in seg.files]
            if not files:
                continue
            stem = _safe_filename(f"TeslaCam {event.start} {cam}")
            out = out_dir / f"{stem}.mp4"
            n = 1
            while out.exists():
                out = out_dir / f"{stem} ({n}).mp4"
                n += 1
            if len(files) == 1:
                shutil.copy2(files[0], out)
            else:
                lst = work / f"{cam}.txt"
                lst.write_text("".join(f"file '{Path(f).as_posix()}'\n" for f in files), encoding="utf-8")
                ff.run_ffmpeg_simple(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)])
            outputs.append(str(out))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return outputs


def cleanup_stale_workdirs(max_age_hours: float = 24) -> None:
    base = cache_dir() / "work"
    if not base.is_dir():
        return
    cutoff = time.time() - max_age_hours * 3600
    for d in base.iterdir():
        try:
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass
