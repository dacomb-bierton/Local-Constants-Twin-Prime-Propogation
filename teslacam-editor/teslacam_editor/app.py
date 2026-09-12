"""HTTP API + static UI.  Everything runs on localhost; the browser is only the front end."""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import export as exporter
from . import ffmpeg_tools as ff
from . import scanner
from .layouts import LAYOUTS, layout_payload
from .models import (
    ASPECT_PRESETS,
    CAMERA_LABELS,
    CAMERAS,
    EventDetail,
    EventInfo,
    ExportRequest,
    JobStatus,
    Project,
    StillRequest,
)
from .paths import default_export_dir, projects_dir, settings_file, thumbs_dir, uploads_dir

STATIC_DIR = Path(__file__).parent / "static"


class Library:
    def __init__(self) -> None:
        self.root: Optional[str] = None
        self.events: dict[str, EventDetail] = {}
        self.order: list[str] = []
        self.resolved: set[str] = set()
        self.lock = threading.RLock()

    def scan(self, root: str) -> list[EventDetail]:
        events = scanner.scan(root)
        with self.lock:
            self.root = str(scanner.normalize_root(root))
            self.events = {e.id: e for e in events}
            self.order = [e.id for e in events]
            self.resolved = set()
        return events

    def infos(self) -> list[EventInfo]:
        with self.lock:
            return [EventInfo(**self.events[i].model_dump(exclude={"segments"})) for i in self.order]

    def get(self, event_id: str) -> EventDetail:
        with self.lock:
            ev = self.events.get(event_id)
        if ev is None:
            raise HTTPException(404, "Unknown event (rescan the library)")
        if event_id not in self.resolved:
            scanner.resolve_durations(ev)
            with self.lock:
                self.resolved.add(event_id)
        return ev

    def remove(self, event_id: str) -> None:
        with self.lock:
            self.events.pop(event_id, None)
            if event_id in self.order:
                self.order.remove(event_id)
            self.resolved.discard(event_id)


class Jobs:
    def __init__(self) -> None:
        self.jobs: dict[str, JobStatus] = {}
        self.cancels: dict[str, threading.Event] = {}
        self.lock = threading.Lock()

    def create(self, kind: str) -> JobStatus:
        job = JobStatus(id=uuid.uuid4().hex[:12], kind=kind, state="queued")
        with self.lock:
            self.jobs[job.id] = job
            self.cancels[job.id] = threading.Event()
        return job

    def update(self, job_id: str, **fields) -> None:
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                for k, v in fields.items():
                    setattr(job, k, v)

    def get(self, job_id: str) -> JobStatus:
        with self.lock:
            job = self.jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Unknown job")
        return job

    def cancel(self, job_id: str) -> None:
        with self.lock:
            ev = self.cancels.get(job_id)
        if ev:
            ev.set()


library = Library()
jobs = Jobs()
outputs: set[str] = set()


def load_settings() -> dict:
    try:
        return json.loads(settings_file().read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data: dict) -> None:
    current = load_settings()
    current.update(data)
    settings_file().write_text(json.dumps(current, indent=2), encoding="utf-8")


app = FastAPI(title="TeslaCam Editor", docs_url=None, redoc_url=None)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/config")
def config() -> dict:
    settings = load_settings()
    return {
        "cameras": CAMERAS,
        "camera_labels": CAMERA_LABELS,
        "layouts": LAYOUTS,
        "aspects": list(ASPECT_PRESETS.keys()),
        "detected_roots": scanner.find_teslacam_roots(),
        "last_root": settings.get("last_root"),
        "recent_roots": settings.get("recent_roots", []),
        "output_dir": settings.get("output_dir") or str(default_export_dir()),
        "ffmpeg": ff.ffmpeg_exe(),
        "platform": sys.platform,
        "library_root": library.root,
    }


@app.get("/api/encoders")
def encoders(force: bool = False) -> dict:
    enc = ff.detect_encoders(force=force)
    return {"encoders": enc, "auto": ff.pick_encoder("auto")}


@app.get("/api/browse")
def browse(path: Optional[str] = None) -> dict:
    try:
        return scanner.list_directory(path)
    except FileNotFoundError:
        raise HTTPException(404, "Folder not found")
    except PermissionError:
        raise HTTPException(403, "Permission denied")


class ScanRequest(BaseModel):
    root: str


@app.post("/api/library/scan")
def scan_library(req: ScanRequest) -> dict:
    try:
        library.scan(req.root)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    settings = load_settings()
    recent = [r for r in settings.get("recent_roots", []) if r != library.root]
    save_settings({"last_root": library.root, "recent_roots": [library.root, *recent][:8]})
    return {"root": library.root, "events": [e.model_dump() for e in library.infos()]}


@app.get("/api/library")
def get_library() -> dict:
    return {"root": library.root, "events": [e.model_dump() for e in library.infos()]}


@app.get("/api/events/{event_id}")
def get_event(event_id: str) -> EventDetail:
    return library.get(event_id)


@app.delete("/api/events/{event_id}")
def delete_event(event_id: str) -> dict:
    ev = library.get(event_id)
    folder = Path(ev.folder)
    removed = 0
    if ev.kind == "RecentClips":
        for seg in ev.segments:
            for f in seg.files.values():
                try:
                    os.remove(f)
                    removed += 1
                except OSError:
                    pass
    else:
        try:
            shutil.rmtree(folder)
            removed = ev.segment_count
        except OSError as e:
            raise HTTPException(500, f"Could not delete: {e}")
    library.remove(event_id)
    return {"ok": True, "removed": removed}


@app.get("/api/events/{event_id}/thumb")
def event_thumb(event_id: str, t: Optional[float] = None, camera: str = "front") -> Response:
    ev = library.get(event_id)
    if t is None:
        native = Path(ev.folder) / "thumb.png"
        if ev.kind != "RecentClips" and native.is_file():
            return FileResponse(native, headers={"Cache-Control": "max-age=86400"})
        t = ev.trigger_offset if ev.trigger_offset is not None else min(1.0, ev.duration / 2)
    cam = camera if camera in ev.cameras else ev.cameras[0]
    key = f"{event_id}_{cam}_{int(t * 10)}.jpg"
    out = thumbs_dir() / key
    if not out.exists():
        res = exporter.frame_at(ev, cam, float(t), out)
        if res is None:
            raise HTTPException(404, "No frame")
    return FileResponse(out, headers={"Cache-Control": "max-age=86400"})


def _range_response(path: Path, request: Request) -> Response:
    size = path.stat().st_size
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    range_header = request.headers.get("range")
    start, end = 0, size - 1
    status = 200
    if range_header and range_header.startswith("bytes="):
        spec = range_header[6:].split(",")[0].strip()
        a, _, b = spec.partition("-")
        try:
            if a:
                start = int(a)
                if b:
                    end = min(size - 1, int(b))
            elif b:
                start = max(0, size - int(b))
        except ValueError:
            raise HTTPException(416, "Bad range")
        if start > end or start >= size:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        status = 206
    length = end - start + 1

    def iterator(chunk: int = 1024 * 512):
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                data = fh.read(min(chunk, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Length": str(length),
        "Accept-Ranges": "bytes",
        "Content-Type": ctype,
        "Cache-Control": "max-age=3600",
    }
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(iterator(), status_code=status, headers=headers, media_type=ctype)


@app.get("/api/media/{event_id}/{index}/{camera}")
def media(event_id: str, index: int, camera: str, request: Request) -> Response:
    ev = library.get(event_id)
    if index < 0 or index >= len(ev.segments):
        raise HTTPException(404, "No such segment")
    path = ev.segments[index].files.get(camera)
    if not path or not Path(path).is_file():
        raise HTTPException(404, "Camera file missing")
    return _range_response(Path(path), request)


@app.get("/api/layout")
def get_layout(
    layout: str = "single",
    cameras: str = "front",
    main: str = "front",
    aspect: str = "16:9",
) -> dict:
    cams = [c for c in cameras.split(",") if c in CAMERAS]
    return layout_payload(layout, cams, main, aspect)


@app.post("/api/export")
def start_export(req: ExportRequest) -> dict:
    project = req.project
    events = {item.event_id: library.get(item.event_id) for item in project.items}
    try:
        exporter.expand_items(project, events)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not project.items:
        raise HTTPException(400, "Add at least one clip to the sequence")
    if project.export.output_dir:
        save_settings({"output_dir": project.export.output_dir})
    job = jobs.create("export")
    cancel = jobs.cancels[job.id]

    def progress(frac: float, msg: str) -> None:
        jobs.update(job.id, progress=frac, message=msg)

    def run() -> None:
        jobs.update(job.id, state="running", message="Starting")
        try:
            out = exporter.export_project(project, events, progress, cancel)
            outputs.add(out)
            jobs.update(job.id, state="done", progress=1.0, message="Done", output=out)
        except ff.FFmpegCancelled:
            jobs.update(job.id, state="cancelled", message="Cancelled")
        except Exception as e:  # surface ffmpeg errors to the UI
            jobs.update(job.id, state="error", error=str(e), message="Failed")

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job.id}


@app.post("/api/still")
def still(req: StillRequest) -> dict:
    ev = library.get(req.event_id)
    try:
        out = exporter.render_still(req, ev)
    except ff.FFmpegError as e:
        raise HTTPException(500, str(e))
    outputs.add(out)
    return {"output": out}


@app.get("/api/jobs")
def list_jobs() -> list[JobStatus]:
    with jobs.lock:
        return list(jobs.jobs.values())


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> JobStatus:
    return jobs.get(job_id)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    jobs.get(job_id)
    jobs.cancel(job_id)
    return {"ok": True}


@app.get("/api/output")
def get_output(path: str, request: Request) -> Response:
    if path not in outputs or not Path(path).is_file():
        raise HTTPException(404, "Not an export of this session")
    return _range_response(Path(path), request)


@app.post("/api/upload/{kind}")
async def upload(kind: str, file: UploadFile = File(...)) -> dict:
    if kind not in ("music", "watermark"):
        raise HTTPException(400, "kind must be music or watermark")
    name = Path(file.filename or "upload").name
    dest = uploads_dir() / f"{uuid.uuid4().hex[:8]}_{name}"
    with open(dest, "wb") as fh:
        while chunk := await file.read(1024 * 1024):
            fh.write(chunk)
    info: dict = {"path": str(dest), "name": name, "url": f"/api/uploads/{dest.name}"}
    if kind == "music":
        try:
            info["duration"] = ff.probe(str(dest)).duration
        except Exception:
            info["duration"] = 0
    return info


@app.get("/api/uploads/{name}")
def get_upload(name: str, request: Request) -> Response:
    path = uploads_dir() / Path(name).name
    if not path.is_file():
        raise HTTPException(404)
    return _range_response(path, request)


class LocalFile(BaseModel):
    path: str


@app.post("/api/localfile")
def register_local_file(req: LocalFile) -> dict:
    """Use an audio/image file already on disk (typed path) without uploading it."""
    p = Path(req.path).expanduser()
    if not p.is_file():
        raise HTTPException(404, "File not found")
    outputs.add(str(p))
    info: dict = {"path": str(p), "name": p.name, "url": f"/api/output?path={p}"}
    try:
        info["duration"] = ff.probe(str(p)).duration
    except Exception:
        info["duration"] = 0
    return info


@app.get("/api/projects")
def list_projects() -> list[dict]:
    items = []
    for f in sorted(projects_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        items.append({"name": f.stem, "modified": f.stat().st_mtime})
    return items


def _project_file(name: str) -> Path:
    safe = exporter._safe_filename(name)
    if not safe:
        raise HTTPException(400, "Invalid name")
    return projects_dir() / f"{safe}.json"


@app.get("/api/projects/{name}")
def get_project(name: str) -> Project:
    f = _project_file(name)
    if not f.is_file():
        raise HTTPException(404, "No such project")
    return Project.model_validate_json(f.read_text(encoding="utf-8"))


@app.put("/api/projects/{name}")
def save_project(name: str, project: Project) -> dict:
    f = _project_file(name)
    project.name = name
    f.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    return {"ok": True, "name": name}


@app.delete("/api/projects/{name}")
def delete_project(name: str) -> dict:
    f = _project_file(name)
    if f.is_file():
        f.unlink()
    return {"ok": True}


class OpenRequest(BaseModel):
    path: str


@app.post("/api/reveal")
def reveal(req: OpenRequest) -> dict:
    """Open the containing folder in the OS file manager."""
    p = Path(req.path)
    target = p if p.is_dir() else p.parent
    if not target.is_dir():
        raise HTTPException(404, "Folder not found")
    try:
        if sys.platform == "win32":
            if p.is_file():
                subprocess.Popen(["explorer", "/select,", str(p)])
            else:
                os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"ok": True}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})
