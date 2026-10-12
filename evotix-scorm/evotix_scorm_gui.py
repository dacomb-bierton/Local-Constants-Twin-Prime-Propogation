#!/usr/bin/env python3
"""Evotix SCORM Studio.

The first step for every PowerPoint, PDF, Word, or Excel file is to flatten
each whole page to one PNG. The course shows those pictures. It does not pull
the pictures out of the file and build the page again.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import html
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape as xml_escape

try:
    import pymupdf
except ImportError:  # pragma: no cover - optional accelerator
    pymupdf = None

HOST = "127.0.0.1"
PORT_START = 8765
LO_LOCK = threading.Lock()
STATE_LOCK = threading.Lock()
SESSIONS: set[str] = set()
ASSETS: dict[str, dict] = {}

# PBKDF2-HMAC-SHA256 of the initial studio password. The password itself is
# not stored in this file.
DEFAULT_PASSWORD_RECORD = (
    "pbkdf2_sha256$200000$c0ffee5c0a11a5c0111e5a11ed00c0de$"
    "10156ddac3af9ce4e619e303957bc4e7a12ce1c6f64cb2fb443d89c52e3b85e9"
)

SLIDE_EXT = {".pptx", ".ppt", ".ppsx", ".pps", ".odp", ".odg"}
DOCUMENT_EXT = {".docx", ".doc", ".odt", ".rtf", ".xlsx", ".xls", ".ods", ".csv", ".pdf"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg"}
FLATTEN_EXT = SLIDE_EXT | DOCUMENT_EXT

COLLINS = {
    "primary": "#FE5000",
    "accent": "#006242",
    "text": "#1A1A1A",
    "page": "#E4E5E6",
    "card": "#FFFFFF",
    "buttonText": "#FFFFFF",
}

DEFAULT_SETTINGS = {
    "title": "Training course",
    "author": "",
    "primary": COLLINS["primary"],
    "accent": COLLINS["accent"],
    "text": COLLINS["text"],
    "page": COLLINS["page"],
    "card": COLLINS["card"],
    "buttonText": COLLINS["buttonText"],
    "radius": 12,
    "transition": 0.35,
    "transitionType": "fade",
    "passPercent": 1,
    "font": "Galano Grotesque",
    "slideSize": 100,
    "showPageNumbers": True,
    "completion": "Module complete",
    "nextLabel": "Next",
    "prevLabel": "Back",
    "autoAdvance": 0,
}


class FlattenError(RuntimeError):
    """The file could not be turned into whole-slide images."""


def app_dir() -> Path:
    return Path(__file__).resolve().parent


def password_record_path() -> Path:
    return app_dir() / "studio-password.hash"


def active_password_record() -> str:
    path = password_record_path()
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        if text.startswith("pbkdf2_sha256$") and text.count("$") == 3:
            return text
    return DEFAULT_PASSWORD_RECORD


def _split_record(record: str) -> tuple[int, bytes, bytes]:
    _algo, rounds, salt, digest = record.split("$")
    return int(rounds), bytes.fromhex(salt), bytes.fromhex(digest)


def password_matches(password: str) -> bool:
    try:
        rounds, salt, expected = _split_record(active_password_record())
    except (ValueError, TypeError):
        return False
    got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(got, expected)


def write_password(password: str) -> None:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    record = f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"
    password_record_path().write_text(record + "\n", encoding="utf-8")


def reset_runtime() -> None:
    with STATE_LOCK:
        SESSIONS.clear()
        ASSETS.clear()


def hex_colour(value: object, default: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", text):
        return text.upper()
    return default


def clean_font(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9 \-]", "", str(value or ""))[:40].strip()
    return text or "Galano Grotesque"


def clamp_int(value: object, low: int, high: int, default: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def clamp_float(value: object, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def clean_settings(raw: dict | None) -> dict:
    raw = raw or {}
    transition = str(raw.get("transitionType") or "fade")
    if transition not in {"none", "fade", "slide"}:
        transition = "fade"
    title = str(raw.get("title") or DEFAULT_SETTINGS["title"]).strip()[:120] or "Training course"
    return {
        "title": title,
        "author": str(raw.get("author") or "").strip()[:80],
        "primary": hex_colour(raw.get("primary"), COLLINS["primary"]),
        "accent": hex_colour(raw.get("accent"), COLLINS["accent"]),
        "text": hex_colour(raw.get("text"), COLLINS["text"]),
        "page": hex_colour(raw.get("page"), COLLINS["page"]),
        "card": hex_colour(raw.get("card"), COLLINS["card"]),
        "buttonText": hex_colour(raw.get("buttonText"), COLLINS["buttonText"]),
        "radius": clamp_int(raw.get("radius"), 0, 40, 12),
        "transition": clamp_float(raw.get("transition"), 0, 1.5, 0.35),
        "transitionType": transition,
        "passPercent": clamp_int(raw.get("passPercent"), 0, 100, 1),
        "font": clean_font(raw.get("font")),
        "slideSize": clamp_int(raw.get("slideSize"), 40, 100, 100),
        "showPageNumbers": bool(raw.get("showPageNumbers", True)),
        "completion": str(raw.get("completion") or "Module complete").strip()[:160] or "Module complete",
        "nextLabel": str(raw.get("nextLabel") or "Next").strip()[:24] or "Next",
        "prevLabel": str(raw.get("prevLabel") or "Back").strip()[:24] or "Back",
        "autoAdvance": clamp_int(raw.get("autoAdvance"), 0, 120, 0),
    }


def default_questions(name: str) -> list[dict]:
    label = name or "this module"
    return [
        {
            "prompt": f"Have you viewed every page of {label}?",
            "choices": ["Yes", "No"],
            "answer": 0,
        },
        {
            "prompt": "Before you finish this module you should:",
            "choices": ["Skip the remaining pages", "View each page", "Close the course"],
            "answer": 1,
        },
    ]


def clean_questions(raw: object, module_name: str) -> list[dict]:
    if not isinstance(raw, list):
        return default_questions(module_name)
    cleaned = []
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt") or "").strip()[:240]
        choices = [str(choice).strip()[:120] for choice in (item.get("choices") or []) if str(choice).strip()][:6]
        if not prompt or len(choices) < 2:
            continue
        answer = clamp_int(item.get("answer"), 0, len(choices) - 1, 0)
        cleaned.append({"prompt": prompt, "choices": choices, "answer": answer})
    return cleaned or default_questions(module_name)


def png_size(path: Path) -> tuple[int, int] | None:
    try:
        header = path.read_bytes()[:24]
    except OSError:
        return None
    if header[:8] != b"\x89PNG\r\n\x1a\n" or len(header) < 24:
        return None
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    if width <= 0 or height <= 0:
        return None
    return width, height


def image_size(path: Path) -> tuple[int, int] | None:
    size = png_size(path)
    if size:
        return size
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    while index + 8 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in {0xC0, 0xC1, 0xC2}:
            height = int.from_bytes(data[index + 5 : index + 7], "big")
            width = int.from_bytes(data[index + 7 : index + 9], "big")
            if width > 0 and height > 0:
                return width, height
            return None
        if marker == 0xD8 or marker == 0xD9:
            index += 2
            continue
        length = int.from_bytes(data[index + 2 : index + 4], "big")
        if length < 2:
            return None
        index += 2 + length
    return None


def find_soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    here = app_dir()
    candidates = [
        here / "LibreOffice" / "program" / "soffice.exe",
        here / "LibreOffice" / "program" / "soffice",
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def libreoffice_to_pdf(src: Path) -> Path | None:
    program = find_soffice()
    if not program:
        return None
    with LO_LOCK:
        work = Path(tempfile.mkdtemp(prefix="lo_flat_"))
        try:
            profile = work / "profile"
            outdir = work / "out"
            profile.mkdir()
            outdir.mkdir()
            proc = subprocess.run(
                [
                    program,
                    "--headless",
                    "--norestore",
                    "--nolockcheck",
                    "--nologo",
                    "--nofirststartwizard",
                    f"-env:UserInstallation={profile.resolve().as_uri()}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(outdir),
                    str(src.resolve()),
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
            pdfs = sorted(outdir.glob("*.pdf"))
            if proc.returncode != 0 or not pdfs:
                return None
            kept = Path(tempfile.mkdtemp(prefix="flat_pdf_")) / f"{src.stem}.pdf"
            shutil.copy(pdfs[0], kept)
            return kept
        except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            return None
        finally:
            shutil.rmtree(work, ignore_errors=True)


def pdf_to_pngs(pdf: Path, dest_dir: Path, mid: int) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if pymupdf is not None:
        document = pymupdf.open(pdf)
        written: list[Path] = []
        try:
            if document.page_count <= 0:
                return []
            for index, page in enumerate(document):
                long_side = max(page.rect.width, page.rect.height) or 1
                zoom = 1920 / long_side
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                out = dest_dir / f"page_{mid:02d}_{index:03d}.png"
                pixmap.save(out)
                size = png_size(out)
                if not size or max(size) < 320:
                    raise FlattenError(
                        f"Page {index + 1} rendered at {size}, which is too small to be a whole slide."
                    )
                written.append(out)
            return written
        finally:
            document.close()

    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise FlattenError(
            "Install PyMuPDF (pip install pymupdf) or poppler (pdftoppm) so each PDF page can become an image."
        )
    prefix = dest_dir / f"ppm_{mid:02d}"
    proc = subprocess.run(
        [pdftoppm, "-png", "-r", "144", str(pdf), str(prefix)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise FlattenError((proc.stderr or "pdftoppm failed").strip()[:400])
    found = sorted(dest_dir.glob(f"ppm_{mid:02d}-*.png"))
    written = []
    for index, source in enumerate(found):
        out = dest_dir / f"page_{mid:02d}_{index:03d}.png"
        source.replace(out)
        size = png_size(out)
        if not size or max(size) < 320:
            raise FlattenError(f"Page {index + 1} is {size}, not a whole slide.")
        written.append(out)
    return written


def powerpoint_flatten(src: Path, dest_dir: Path, mid: int, notes: list[str]) -> list[Path]:
    """Flatten with PowerPoint itself when this is a Windows PC."""
    if sys.platform != "win32":
        return []
    dest_dir.mkdir(parents=True, exist_ok=True)
    script = r"""
param($src, $outDir, $mid)
$ErrorActionPreference = "Stop"
$ppt = $null
$pres = $null
$started = $false
function Copy-FlatPngs($folder) {
  $found = @(Get-ChildItem -LiteralPath $folder -Recurse -Filter *.png | Sort-Object Name)
  $i = 0
  foreach ($file in $found) {
    $dest = Join-Path $outDir ("page_{0}_{1:D3}.png" -f $mid, $i)
    Copy-Item -LiteralPath $file.FullName -Destination $dest -Force
    $i++
  }
  return $i
}
try {
  $ppt = New-Object -ComObject PowerPoint.Application
  $started = $true
  $ppt.Visible = -1
  $pres = $ppt.Presentations.Open($src, -1, 0, -1)
  $pxW = [int][math]::Round($pres.PageSetup.SlideWidth * 2)
  $pxH = [int][math]::Round($pres.PageSetup.SlideHeight * 2)
  if ($pxW -lt 640) { $pxW = 1920 }
  if ($pxH -lt 360) { $pxH = 1080 }
  $expected = @($pres.Slides).Count
  $i = 0
  foreach ($slide in $pres.Slides) {
    $dest = Join-Path $outDir ("page_{0}_{1:D3}.png" -f $mid, $i)
    $slide.Export($dest, "PNG", $pxW, $pxH) | Out-Null
    $i++
  }
  if ($i -lt $expected) { throw "PowerPoint exported $i of $expected slides" }
} catch {
  if ($pres) {
    $flat = Join-Path $outDir ("flat_" + $mid)
    New-Item -ItemType Directory -Force -Path $flat | Out-Null
    $pres.SaveAs((Join-Path $flat "slide"), 18) | Out-Null
    $copied = Copy-FlatPngs $flat
    if ($copied -lt 1) { throw }
  } else {
    throw
  }
} finally {
  if ($pres) { try { $pres.Close() } catch {} }
  if ($started -and $ppt) {
    try { if ($ppt.Presentations.Count -eq 0) { $ppt.Quit() } } catch {}
  }
  [GC]::Collect()
}
"""
    script_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
            handle.write(script)
            script_path = handle.name
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
                "-src",
                str(src.resolve()),
                "-outDir",
                str(dest_dir.resolve()),
                "-mid",
                f"{mid:02d}",
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "PowerPoint flatten failed").strip()
            notes.append(detail[-400:])
            return []
        written = sorted(dest_dir.glob(f"page_{mid:02d}_*.png"))
        for path in written:
            size = png_size(path)
            if not size or max(size) < 320:
                for item in written:
                    item.unlink(missing_ok=True)
                notes.append("PowerPoint did not write full-slide images.")
                return []
        return written
    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError) as exc:
        notes.append(f"PowerPoint flatten failed: {exc}")
        return []
    finally:
        if script_path:
            try:
                os.remove(script_path)
            except OSError:
                pass


def flatten_to_pngs(src: str | Path, dest_dir: str | Path, mid: int = 0) -> list[Path]:
    """Turn every whole page into one PNG. This is the first step. Nothing else runs first."""
    source = Path(src)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    ext = source.suffix.lower()
    if ext not in FLATTEN_EXT:
        raise FlattenError(f"{source.name} is not a document or presentation.")
    notes: list[str] = []
    if ext in SLIDE_EXT:
        slides = powerpoint_flatten(source, dest, mid, notes)
        if slides:
            return slides
    owned_pdf: Path | None = None
    try:
        if ext == ".pdf":
            pdf = source
        else:
            pdf = libreoffice_to_pdf(source)
            owned_pdf = pdf
            if pdf is None:
                notes.append("LibreOffice could not flatten the file. Install LibreOffice, or PowerPoint on Windows.")
                pdf = None
        if pdf is not None:
            return pdf_to_pngs(pdf, dest, mid)
    finally:
        if owned_pdf is not None:
            shutil.rmtree(owned_pdf.parent, ignore_errors=True)
    raise FlattenError(
        "The slides were not flattened, so they were not rebuilt from the separate pictures. "
        + " ".join(notes)
    )


def classify(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in FLATTEN_EXT:
        return "flatten"
    return "unknown"


def store_asset(path: Path, kind: str, name: str) -> dict:
    asset_id = secrets.token_hex(8)
    size = image_size(path) if kind == "image" else None
    record = {
        "id": asset_id,
        "kind": kind,
        "path": str(path),
        "name": name,
        "w": size[0] if size else None,
        "h": size[1] if size else None,
    }
    with STATE_LOCK:
        ASSETS[asset_id] = record
    return public_asset(record)


def public_asset(record: dict) -> dict:
    return {
        "id": record["id"],
        "kind": record["kind"],
        "name": record["name"],
        "url": f"/api/asset/{record['id']}",
        "w": record.get("w"),
        "h": record.get("h"),
    }


def ingest_file(src: Path, work: Path, mid: int) -> dict:
    kind = classify(src)
    if kind == "unknown":
        raise FlattenError(f"{src.name} is not a supported file.")
    if kind == "flatten":
        images = flatten_to_pngs(src, work, mid)
        pages = [store_asset(image, "image", image.name) for image in images]
        note = f"Flattened {len(pages)} whole page{'s' if len(pages) != 1 else ''} of {src.name} to images."
    else:
        held = work / f"{mid:02d}_{src.name}"
        shutil.copy(src, held)
        pages = [store_asset(held, kind, src.name)]
        note = f"Added {src.name}."
    return {
        "name": src.name,
        "note": note,
        "pages": pages,
        "questions": default_questions(src.name),
    }


def font_files() -> list[Path]:
    folder = app_dir() / "fonts"
    if not folder.is_dir():
        return []
    found = []
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() in {".woff2", ".woff", ".ttf", ".otf"} and path.is_file():
            found.append(path)
    return found


def font_css(copied: list[str]) -> str:
    faces = []
    for href in copied:
        ext = Path(href).suffix.lower()
        fmt = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}.get(ext, "truetype")
        faces.append(
            "@font-face {"
            " font-family: 'Galano Grotesque';"
            f" src: url('{href}') format('{fmt}');"
            " font-weight: 100 900; font-display: swap; }"
        )
    return "\n".join(faces)


def build_player(settings: dict, modules: list[dict], font_block: str) -> str:
    payload = json.dumps({"settings": settings, "modules": modules}, ensure_ascii=False).replace("<", "\\u003c")
    title = html.escape(settings["title"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{font_block}
:root {{
  color-scheme: light;
  --primary: {settings["primary"]};
  --accent: {settings["accent"]};
  --text: {settings["text"]};
  --page: {settings["page"]};
  --card: {settings["card"]};
  --button-text: {settings["buttonText"]};
  --radius: {settings["radius"]}px;
  --speed: {settings["transition"]}s;
  --slide-size: {settings["slideSize"]};
  --font: "{settings["font"]}", "Galano Grotesque", "Galano Grotesque Alt", system-ui, sans-serif;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--page); color: var(--text);
  font-family: var(--font); min-height: 100vh;
}}
header, main {{ width: min(1100px, calc(100% - 24px)); margin: 0 auto; }}
header {{ display: flex; justify-content: space-between; gap: 16px; align-items: end; padding: 18px 0 10px; }}
h1 {{ font-size: 1.35rem; margin: 0; font-weight: 650; }}
.meta {{ margin: 4px 0 0; color: var(--text); opacity: .75; font-size: .92rem; }}
.stage {{
  background: var(--card); border-radius: var(--radius); min-height: 42vh;
  display: flex; align-items: center; justify-content: center; padding: 12px;
  touch-action: pan-y; overflow: hidden;
}}
img.slide {{
  display: block; width: auto; height: auto;
  max-width: calc(var(--slide-size) * 1%); max-height: 78vh;
  margin: 0 auto; background: transparent; object-fit: contain;
  user-select: none; -webkit-user-drag: none;
}}
video.slide, audio.slide {{ width: min(960px, 100%); max-height: 78vh; background: transparent; }}
.quiz {{ width: min(680px, 100%); padding: 12px 8px 20px; }}
.quiz h2 {{ margin: 0 0 8px; font-size: 1.15rem; }}
.choice {{
  display: block; width: 100%; text-align: left; margin: 8px 0; padding: 12px 14px;
  border-radius: var(--radius); border: 1px solid rgba(26, 26, 26, .18);
  background: var(--card); color: var(--text); font: inherit; cursor: pointer;
}}
.choice.selected {{ border-color: var(--primary); outline: 2px solid var(--primary); }}
.bar {{
  display: flex; justify-content: space-between; gap: 12px; align-items: center;
  padding: 12px 0 22px; flex-wrap: wrap;
}}
button.nav {{
  background: var(--primary); color: var(--button-text); border: 0; border-radius: var(--radius);
  padding: 12px 18px; font: inherit; font-weight: 650; cursor: pointer;
  transition: transform var(--speed) ease, opacity var(--speed) ease;
}}
button.nav.secondary {{ background: var(--card); color: var(--text); border: 1px solid rgba(26, 26, 26, .2); }}
button.nav:active {{ transform: translateY(1px); }}
.done {{ background: var(--card); border-radius: var(--radius); padding: 28px 22px; }}
.time {{ font-variant-numeric: tabular-nums; }}
@keyframes fadein {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
@keyframes slidein {{ from {{ transform: translateX(28px); opacity: .55; }} to {{ transform: none; opacity: 1; }} }}
</style>
</head>
<body>
<header>
  <div>
    <h1 id="course-title"></h1>
    <p class="meta" id="module-meta"></p>
  </div>
  <p class="meta time" id="time-meta"></p>
</header>
<main>
  <div class="stage" id="stage"></div>
  <div class="bar">
    <button class="nav secondary" id="prev" type="button"></button>
    <button class="nav" id="next" type="button"></button>
  </div>
</main>
<script id="course-data" type="application/json">{payload}</script>
<script>
const COURSE = JSON.parse(document.getElementById("course-data").textContent);
const CFG = COURSE.settings;
const rootStyle = document.documentElement.style;
rootStyle.setProperty("--primary", CFG.primary);
rootStyle.setProperty("--accent", CFG.accent);
rootStyle.setProperty("--text", CFG.text);
rootStyle.setProperty("--page", CFG.page);
rootStyle.setProperty("--card", CFG.card);
rootStyle.setProperty("--button-text", CFG.buttonText);
rootStyle.setProperty("--radius", CFG.radius + "px");
rootStyle.setProperty("--speed", CFG.transition + "s");
rootStyle.setProperty("--slide-size", CFG.slideSize);
rootStyle.setProperty("--font", '"' + CFG.font + '", "Galano Grotesque", "Galano Grotesque Alt", system-ui, sans-serif');
document.getElementById("course-title").textContent = CFG.title;
document.getElementById("next").textContent = CFG.nextLabel;
document.getElementById("prev").textContent = CFG.prevLabel;

const modules = COURSE.modules;
let mi = 0, pi = 0, phase = "slide", qi = 0;
const viewed = {{}};
const times = {{}};
const answers = {{}};
let pageStamp = Date.now();
const courseStart = Date.now();
let autoTimer = null;
let selected = null;

function findAPI(win) {{
  let hops = 0;
  try {{
    while (win && hops < 12) {{
      if (win.API) return win.API;
      if (!win.parent || win.parent === win) break;
      win = win.parent;
      hops += 1;
    }}
  }} catch (error) {{}}
  try {{ if (window.opener && window.opener.API) return window.opener.API; }} catch (error) {{}}
  return null;
}}
const API = findAPI(window);
function scorm(call) {{
  if (!API) return "";
  try {{ return call(); }} catch (error) {{ return ""; }}
}}
scorm(() => API.LMSInitialize(""));
function pageKey() {{ return mi + ":" + pi; }}
function flushTime() {{
  if (phase !== "slide") {{ pageStamp = Date.now(); return; }}
  const key = pageKey();
  times[key] = (times[key] || 0) + (Date.now() - pageStamp) / 1000;
  pageStamp = Date.now();
}}
function clock(total) {{
  const seconds = Math.max(0, Math.floor(total));
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m + ":" + String(s).padStart(2, "0");
}}
function scormTime(total) {{
  const seconds = Math.max(0, Math.floor(total));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return String(h).padStart(4, "0") + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0") + ".00";
}}
function snapshot() {{
  return JSON.stringify({{ mi, pi, phase, qi, viewed, times, answers }});
}}
function commit(status) {{
  let data = snapshot();
  if (data.length > 3500) data = JSON.stringify({{ mi, pi, phase, qi, viewed, answers }});
  scorm(() => API.LMSSetValue("cmi.core.lesson_location", mi + ":" + pi + ":" + phase));
  scorm(() => API.LMSSetValue("cmi.suspend_data", data.slice(0, 4096)));
  scorm(() => API.LMSSetValue("cmi.core.session_time", scormTime((Date.now() - courseStart) / 1000)));
  if (status) scorm(() => API.LMSSetValue("cmi.core.lesson_status", status));
  scorm(() => API.LMSCommit(""));
}}
function allPages() {{
  const keys = [];
  modules.forEach((mod, moduleIndex) => mod.pages.forEach((_, pageIndex) => keys.push(moduleIndex + ":" + pageIndex)));
  return keys;
}}
function score() {{
  let correct = 0, total = 0;
  modules.forEach((mod, moduleIndex) => {{
    (mod.questions || []).forEach((question, questionIndex) => {{
      total += 1;
      const given = (answers[moduleIndex] || [])[questionIndex];
      if (given === question.answer) correct += 1;
    }});
  }});
  if (!total) return 100;
  return Math.round((correct / total) * 100);
}}
function everyPageViewed() {{
  return allPages().every((key) => viewed[key]);
}}
function restore() {{
  const saved = scorm(() => API.LMSGetValue("cmi.suspend_data")) || "";
  if (!saved) return;
  try {{
    const data = JSON.parse(saved);
    mi = data.mi || 0; pi = data.pi || 0; phase = data.phase || "slide"; qi = data.qi || 0;
    Object.assign(viewed, data.viewed || {{}});
    Object.assign(times, data.times || {{}});
    Object.assign(answers, data.answers || {{}});
  }} catch (error) {{}}
}}

function clearNode(node) {{ while (node.firstChild) node.removeChild(node.firstChild); }}
function showSlide(mod) {{
  const stage = document.getElementById("stage");
  clearNode(stage);
  const page = mod.pages[pi];
  viewed[pageKey()] = true;
  if (!page) {{ stage.textContent = "This module has no pages."; return; }}
  if (page.kind === "video") {{
    const video = document.createElement("video");
    video.className = "slide"; video.controls = true; video.playsInline = true; video.src = page.src;
    stage.appendChild(video);
  }} else if (page.kind === "audio") {{
    const audio = document.createElement("audio");
    audio.className = "slide"; audio.controls = true; audio.src = page.src;
    stage.appendChild(audio);
  }} else {{
    const image = document.createElement("img");
    image.className = "slide"; image.alt = mod.name + " page " + (pi + 1); image.src = page.src;
    image.draggable = false;
    stage.appendChild(image);
  }}
  const meta = [mod.name];
  if (CFG.showPageNumbers) meta.push("Page " + (pi + 1) + " of " + mod.pages.length);
  document.getElementById("module-meta").textContent = meta.join(" · ");
}}
function showQuiz(mod) {{
  const stage = document.getElementById("stage");
  clearNode(stage);
  const wrap = document.createElement("div");
  wrap.className = "quiz";
  const questions = mod.questions || [];
  const question = questions[qi];
  const title = document.createElement("h2");
  title.textContent = "Question " + (qi + 1) + " of " + questions.length;
  const prompt = document.createElement("p");
  prompt.textContent = question ? question.prompt : "";
  wrap.appendChild(title); wrap.appendChild(prompt);
  selected = ((answers[mi] || [])[qi]);
  (question ? question.choices : []).forEach((choice, index) => {{
    const button = document.createElement("button");
    button.type = "button"; button.className = "choice" + (selected === index ? " selected" : "");
    button.textContent = choice;
    button.onclick = () => {{
      if (!answers[mi]) answers[mi] = [];
      answers[mi][qi] = index;
      showQuiz(mod);
    }};
    wrap.appendChild(button);
  }});
  stage.appendChild(wrap);
  document.getElementById("module-meta").textContent = mod.name + " · questions";
}}
function showDone() {{
  flushTime();
  if (autoTimer) clearInterval(autoTimer);
  const stage = document.getElementById("stage");
  clearNode(stage);
  const result = score();
  const passed = everyPageViewed() && result >= CFG.passPercent;
  const box = document.createElement("div");
  box.className = "done";
  const heading = document.createElement("h2");
  heading.textContent = passed ? CFG.completion : "Not completed yet";
  const detail = document.createElement("p");
  const viewedCount = allPages().filter((key) => viewed[key]).length;
  detail.textContent = "Score " + result + "%. Pages viewed " + viewedCount + " of " + allPages().length + ". Time in course " + clock((Date.now() - courseStart) / 1000) + ".";
  box.appendChild(heading); box.appendChild(detail);
  const list = document.createElement("ul");
  allPages().forEach((key) => {{
    const item = document.createElement("li");
    item.textContent = "Page " + key + " viewed " + clock(times[key] || 0);
    list.appendChild(item);
  }});
  box.appendChild(list);
  stage.appendChild(box);
  document.getElementById("module-meta").textContent = CFG.author || "";
  scorm(() => API.LMSSetValue("cmi.core.score.raw", String(result)));
  scorm(() => API.LMSSetValue("cmi.core.score.min", "0"));
  scorm(() => API.LMSSetValue("cmi.core.score.max", "100"));
  commit(passed ? "completed" : "incomplete");
  phase = "done";
}}
function render() {{
  const mod = modules[mi];
  const stage = document.getElementById("stage");
  if (!mod) {{ showDone(); return; }}
  if (phase === "slide") showSlide(mod);
  else if (phase === "quiz") showQuiz(mod);
  else showDone();
  stage.style.animation = "none";
  void stage.offsetWidth;
  if (CFG.transitionType === "fade") stage.style.animation = "fadein var(--speed) ease";
  if (CFG.transitionType === "slide") stage.style.animation = "slidein var(--speed) ease";
  paintTime();
  if (phase !== "done") commit("");
  if (autoTimer) clearInterval(autoTimer);
  if (CFG.autoAdvance > 0 && phase === "slide" && mod.pages.length > 1) {{
    autoTimer = setInterval(() => go(1), CFG.autoAdvance * 1000);
  }}
}}
function paintTime() {{
  const soFar = phase === "slide" ? (times[pageKey()] || 0) + (Date.now() - pageStamp) / 1000 : (times[pageKey()] || 0);
  document.getElementById("time-meta").textContent = "This page " + clock(soFar);
}}
function go(direction) {{
  const mod = modules[mi];
  if (!mod || phase === "done") return;
  flushTime();
  if (direction > 0) {{
    if (phase === "slide") {{
      if (pi < mod.pages.length - 1) pi += 1;
      else if ((mod.questions || []).length) {{ phase = "quiz"; qi = 0; }}
      else if (mi < modules.length - 1) {{ mi += 1; pi = 0; }}
      else {{ showDone(); return; }}
    }} else if (phase === "quiz") {{
      const given = (answers[mi] || [])[qi];
      if (given === undefined) return;
      if (qi < mod.questions.length - 1) qi += 1;
      else if (mi < modules.length - 1) {{ mi += 1; pi = 0; phase = "slide"; }}
      else {{ showDone(); return; }}
    }}
  }} else if (phase === "quiz" && qi > 0) qi -= 1;
  else if (phase === "quiz") phase = "slide";
  else if (pi > 0) pi -= 1;
  else if (mi > 0) {{
    mi -= 1;
    const previous = modules[mi];
    if ((previous.questions || []).length) {{ phase = "quiz"; qi = previous.questions.length - 1; }}
    else {{ phase = "slide"; pi = Math.max(0, previous.pages.length - 1); }}
  }}
  render();
}}
document.getElementById("next").onclick = () => go(1);
document.getElementById("prev").onclick = () => go(-1);
document.addEventListener("keydown", (event) => {{
  if (event.key === "ArrowRight") go(1);
  if (event.key === "ArrowLeft") go(-1);
}});
function bindSwipe(node) {{
  let x0 = 0, y0 = 0, active = false;
  node.addEventListener("pointerdown", (event) => {{
    if (event.target.closest("button, a, input, video, audio, textarea, select, label")) return;
    active = true; x0 = event.clientX; y0 = event.clientY;
    if (event.cancelable) event.preventDefault();
    try {{ node.setPointerCapture(event.pointerId); }} catch (error) {{}}
  }});
  node.addEventListener("pointerup", (event) => {{
    if (!active) return;
    active = false;
    const dx = event.clientX - x0;
    const dy = event.clientY - y0;
    if (Math.abs(dx) < 48 || Math.abs(dx) < Math.abs(dy) * 1.2) return;
    if (dx < 0) go(1); else go(-1);
  }});
  node.addEventListener("pointercancel", () => {{ active = false; }});
}}
bindSwipe(document.getElementById("stage"));
setInterval(paintTime, 250);
window.addEventListener("pagehide", () => {{ flushTime(); commit(everyPageViewed() && score() >= CFG.passPercent ? "completed" : "incomplete"); scorm(() => API.LMSFinish("")); }});
restore();
if (!modules.length) showDone(); else render();
</script>
</body>
</html>
"""


def build_manifest(settings: dict, files: list[str]) -> str:
    identifier = "EVOTIX-" + hashlib.sha1(settings["title"].encode("utf-8")).hexdigest()[:12].upper()
    title = xml_escape(settings["title"])
    file_nodes = "\n".join(f'      <file href="{xml_escape(name)}"/>' for name in files)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{identifier}" version="1.2"
  xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
  xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="ORG-1">
    <organization identifier="ORG-1">
      <title>{title}</title>
      <item identifier="ITEM-1" identifierref="RES-1" isvisible="true">
        <title>{title}</title>
        <adlcp:masteryscore>{int(settings["passPercent"])}</adlcp:masteryscore>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="RES-1" type="webcontent" adlcp:scormtype="sco" href="index.html">
{file_nodes}
    </resource>
  </resources>
</manifest>
"""


def build_zip(modules: list[dict], settings: dict, out_path: str | Path) -> Path:
    settings = clean_settings(settings)
    packaged_modules = []
    blobs: list[tuple[str, bytes]] = []
    page_index = 0
    for module in modules:
        name = str(module.get("name") or "Module").strip()[:120] or "Module"
        pages = []
        for page in module.get("pages") or []:
            kind = page.get("kind")
            source = Path(page["path"])
            ext = source.suffix.lower()
            if kind == "image" and ext not in IMAGE_EXT:
                raise FlattenError(f"{source.name} is not a flattened slide image.")
            if kind == "video" and ext not in VIDEO_EXT:
                raise FlattenError(f"{source.name} is not a video.")
            if kind == "audio" and ext not in AUDIO_EXT:
                raise FlattenError(f"{source.name} is not audio.")
            if kind not in {"image", "video", "audio"}:
                raise FlattenError("A course page has to be an image, video, or audio file.")
            arc = f"assets/page_{page_index:03d}{ext}"
            blobs.append((arc, source.read_bytes()))
            pages.append({"kind": kind, "src": arc})
            page_index += 1
        if not pages:
            raise FlattenError(f"{name} has no pages.")
        packaged_modules.append(
            {"name": name, "pages": pages, "questions": clean_questions(module.get("questions"), name)}
        )
    fonts = []
    for font in font_files():
        arc = f"fonts/{font.name}"
        blobs.append((arc, font.read_bytes()))
        fonts.append(arc)
    player = build_player(settings, packaged_modules, font_css(fonts)).encode("utf-8")
    file_names = ["index.html"] + [name for name, _data in blobs]
    manifest = build_manifest(settings, file_names).encode("utf-8")
    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("imsmanifest.xml", manifest)
        archive.writestr("index.html", player)
        for name, data in blobs:
            archive.writestr(name, data)
    return destination


def prepare_modules(paths: list[Path], work: Path) -> list[dict]:
    modules = []
    for index, path in enumerate(paths):
        ingested = ingest_file(path, work, index)
        resolved = []
        for page in ingested["pages"]:
            record = ASSETS[page["id"]]
            resolved.append({"kind": record["kind"], "path": record["path"]})
        modules.append({"name": ingested["name"], "pages": resolved, "questions": ingested["questions"]})
    return modules


STUDIO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Evotix SCORM Studio</title>
<style>
:root {
  color-scheme: light;
  --primary: #FE5000; --accent: #006242; --text: #1A1A1A; --page: #E4E5E6; --card: #FFFFFF;
  --font: "Galano Grotesque", "Galano Grotesque Alt", system-ui, sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--text); font-family: var(--font); }
main { width: min(1180px, calc(100% - 28px)); margin: 0 auto; padding: 22px 0 48px; }
h1 { margin: 0 0 6px; font-size: 1.7rem; }
.lede { margin: 0 0 18px; max-width: 70ch; }
.card { background: var(--card); border-radius: 16px; padding: 16px; margin: 12px 0; }
.drop {
  border: 2px dashed #c5c7c8; border-radius: 16px; padding: 28px; text-align: center; background: #fafafa;
}
.drop.hot { border-color: var(--primary); background: #fff4ec; }
button, .file-btn {
  background: var(--primary); color: white; border: 0; border-radius: 999px; padding: 10px 16px;
  font: inherit; font-weight: 650; cursor: pointer;
}
button.secondary { background: white; color: var(--text); border: 1px solid #c5c7c8; }
button.good { background: var(--accent); }
button:disabled { opacity: .45; cursor: not-allowed; }
.row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
label { display: block; font-size: .85rem; margin-bottom: 4px; }
input[type="text"], input[type="number"], select, textarea {
  width: 100%; border: 1px solid #c5c7c8; border-radius: 10px; padding: 8px 10px; font: inherit; background: white;
}
textarea { min-height: 64px; }
.color { display: flex; gap: 8px; align-items: center; }
input[type="color"] { width: 48px; height: 36px; border: 0; background: transparent; padding: 0; }
.themes { display: flex; flex-wrap: wrap; gap: 6px; }
.themes button { background: white; color: var(--text); border: 1px solid #c5c7c8; padding: 6px 10px; }
.themes button.on { background: var(--primary); color: white; border-color: var(--primary); }
.pages { display: flex; gap: 10px; overflow-x: auto; padding-bottom: 6px; }
.page { width: 180px; flex: 0 0 auto; }
.page img { width: 180px; height: 102px; object-fit: contain; background: white; border: 1px solid #e4e5e6; border-radius: 8px; }
.page .tools { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.page .tools button, .page .tools label { font-size: .75rem; padding: 4px 8px; border-radius: 8px; }
.status { min-height: 1.3em; font-weight: 650; }
.status.bad { color: #9f1239; }
.gate {
  position: fixed; inset: 0; background: rgba(26,26,26,.45); display: flex; align-items: center; justify-content: center;
}
.gate[hidden] { display: none; }
.gate form { background: white; padding: 22px; border-radius: 16px; width: min(420px, calc(100% - 32px)); }
</style>
</head>
<body>
<div class="gate" id="gate">
  <form id="login-form">
    <h2>Studio password</h2>
    <p>The password is checked against a stored hash.</p>
    <input type="password" id="password" autocomplete="current-password" required>
    <p class="status bad" id="login-status"></p>
    <button type="submit">Open studio</button>
  </form>
</div>
<main>
  <h1>Evotix SCORM Studio</h1>
  <p class="lede">Step 1 flattens every whole slide to an image. The course uses those images, with the slide's own pictures, text, and colours. It does not build the slide again.</p>
  <section class="card">
    <div class="drop" id="drop">Drop PowerPoint, PDF, Word, Excel, images, or video here</div>
    <div class="row" style="margin-top:12px">
      <label class="file-btn">Add files<input id="picker" type="file" multiple hidden></label>
      <button id="clear" class="secondary" type="button">Clear</button>
      <button id="flatten" type="button" disabled>Flatten slides to images</button>
    </div>
    <ul id="file-list"></ul>
    <p class="status" id="status"></p>
  </section>
  <section class="card" id="editor" hidden>
    <h2>Pages</h2>
    <p>These are the flattened slides. Replace a page, drop in a video, or change the order before you generate.</p>
    <div id="modules"></div>
  </section>
  <section class="card">
    <h2>Colours</h2>
    <div class="themes" id="themes"></div>
    <div class="grid" style="margin-top:12px">
      <div class="color"><input type="color" id="primary" value="#FE5000"><label for="primary">Buttons · Collins orange 021 C</label></div>
      <div class="color"><input type="color" id="accent" value="#006242"><label for="accent">Success · Collins green 3425 C</label></div>
      <div class="color"><input type="color" id="text" value="#1A1A1A"><label for="text">Text · rich black</label></div>
      <div class="color"><input type="color" id="page" value="#E4E5E6"><label for="page">Page · silver 877</label></div>
      <div class="color"><input type="color" id="card" value="#FFFFFF"><label for="card">Cards and slides</label></div>
      <div class="color"><input type="color" id="buttonText" value="#FFFFFF"><label for="buttonText">Button text</label></div>
    </div>
  </section>
  <section class="card">
    <h2>Course</h2>
    <div class="grid">
      <div><label for="title">Title</label><input id="title" type="text" value="Training course"></div>
      <div><label for="author">Author</label><input id="author" type="text" value=""></div>
      <div><label for="font">Font</label><select id="font">
        <option>Galano Grotesque</option><option>Galano Grotesque Alt</option><option>system-ui</option>
        <option>Segoe UI</option><option>Arial</option><option>Georgia</option><option>Verdana</option>
      </select></div>
      <div><label for="transitionType">Transition</label><select id="transitionType"><option>fade</option><option>slide</option><option>none</option></select></div>
      <div><label for="nextLabel">Next button</label><input id="nextLabel" type="text" value="Next"></div>
      <div><label for="prevLabel">Back button</label><input id="prevLabel" type="text" value="Back"></div>
      <div><label for="completion">Completion message</label><input id="completion" type="text" value="Module complete"></div>
      <div><label for="radius">Button roundness <span id="radius-out">12</span></label><input id="radius" type="range" min="0" max="40" value="12"></div>
      <div><label for="transition">Transition seconds <span id="transition-out">0.35</span></label><input id="transition" type="range" min="0" max="1.5" step="0.05" value="0.35"></div>
      <div><label for="slideSize">Slide size <span id="slideSize-out">100</span>%</label><input id="slideSize" type="range" min="40" max="100" value="100"></div>
      <div><label for="passPercent">Pass mark <span id="passPercent-out">1</span>% (1 keeps the pass rate near 99%)</label><input id="passPercent" type="range" min="0" max="100" value="1"></div>
      <div><label for="autoAdvance">Auto-advance seconds <span id="autoAdvance-out">0</span></label><input id="autoAdvance" type="range" min="0" max="30" value="0"></div>
    </div>
    <p class="row"><label><input id="showPageNumbers" type="checkbox" checked> Show page numbers</label></p>
  </section>
  <p class="row"><button id="generate" class="good" type="button" disabled>Generate SCORM ZIP</button></p>
</main>
<script>
const PRESETS = {
  Collins: {primary:"#FE5000", accent:"#006242", text:"#1A1A1A", page:"#E4E5E6", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Evotix: {primary:"#0B6E4F", accent:"#14B8A6", text:"#E7F6F1", page:"#071510", card:"#10241C", buttonText:"#FFFFFF"},
  Dark: {primary:"#38BDF8", accent:"#22C55E", text:"#E2E8F0", page:"#0F172A", card:"#111827", buttonText:"#082F49"},
  Light: {primary:"#0369A1", accent:"#15803D", text:"#1A1A1A", page:"#F8FAFC", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Corporate: {primary:"#1D4ED8", accent:"#0F766E", text:"#0F172A", page:"#E2E8F0", card:"#FFFFFF", buttonText:"#FFFFFF"},
  "High Contrast": {primary:"#FFD000", accent:"#00E5FF", text:"#FFFFFF", page:"#000000", card:"#111111", buttonText:"#000000"},
  Ocean: {primary:"#0077B6", accent:"#00B4D8", text:"#023047", page:"#E0F2FE", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Forest: {primary:"#166534", accent:"#65A30D", text:"#14532D", page:"#ECFCCB", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Sunset: {primary:"#EA580C", accent:"#BE123C", text:"#431407", page:"#FFEDD5", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Slate: {primary:"#334155", accent:"#0EA5E9", text:"#0F172A", page:"#E2E8F0", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Plum: {primary:"#7E22CE", accent:"#DB2777", text:"#3B0764", page:"#FAE8FF", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Sand: {primary:"#C2410C", accent:"#A16207", text:"#44403C", page:"#FAF5F0", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Navy: {primary:"#1E3A8A", accent:"#F59E0B", text:"#E0E7FF", page:"#0B1220", card:"#172554", buttonText:"#FFFFFF"},
  Rose: {primary:"#E11D48", accent:"#FB7185", text:"#4C0519", page:"#FFF1F2", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Amber: {primary:"#D97706", accent:"#065F46", text:"#1C1917", page:"#FFFBEB", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Glacier: {primary:"#0891B2", accent:"#6366F1", text:"#164E63", page:"#ECFEFF", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Ink: {primary:"#111827", accent:"#FE5000", text:"#111827", page:"#F3F4F6", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Paper: {primary:"#44403C", accent:"#006242", text:"#1C1917", page:"#F5F5F4", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Safety: {primary:"#FACC15", accent:"#DC2626", text:"#171717", page:"#F5F5F5", card:"#FFFFFF", buttonText:"#171717"},
  Night: {primary:"#A78BFA", accent:"#34D399", text:"#EDE9FE", page:"#1E1B4B", card:"#312E81", buttonText:"#1E1B4B"},
  Mint: {primary:"#059669", accent:"#0284C7", text:"#064E3B", page:"#ECFDF5", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Copper: {primary:"#B45309", accent:"#7C2D12", text:"#431407", page:"#FEF3C7", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Stone: {primary:"#57534E", accent:"#006242", text:"#1C1917", page:"#E7E5E4", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Wine: {primary:"#9F1239", accent:"#FE5000", text:"#4C0519", page:"#FDF2F8", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Arctic: {primary:"#0369A1", accent:"#22C55E", text:"#082F49", page:"#F0F9FF", card:"#FFFFFF", buttonText:"#FFFFFF"},
  Graphite: {primary:"#52525B", accent:"#FE5000", text:"#18181B", page:"#E4E4E7", card:"#FFFFFF", buttonText:"#FFFFFF"}
};
const files = [];
let modules = [];
const list = document.getElementById("file-list");
const status = document.getElementById("status");
const drop = document.getElementById("drop");
function setStatus(text, bad) {
  status.textContent = text || "";
  status.className = "status" + (bad ? " bad" : "");
}
function paintFiles() {
  list.innerHTML = "";
  files.forEach((file) => {
    const item = document.createElement("li");
    item.textContent = file.name;
    list.appendChild(item);
  });
  document.getElementById("flatten").disabled = files.length === 0;
}
function addFiles(listLike) {
  for (const file of listLike) files.push(file);
  paintFiles();
}
drop.ondragover = (event) => { event.preventDefault(); drop.classList.add("hot"); };
drop.ondragleave = () => drop.classList.remove("hot");
drop.ondrop = (event) => { event.preventDefault(); drop.classList.remove("hot"); addFiles(event.dataTransfer.files); };
document.getElementById("picker").onchange = (event) => { addFiles(event.target.files); event.target.value = ""; };
document.getElementById("clear").onclick = () => { files.splice(0, files.length); modules = []; paintFiles(); document.getElementById("editor").hidden = true; document.getElementById("generate").disabled = true; setStatus(""); };
function field(id) { return document.getElementById(id); }
["radius", "transition", "slideSize", "passPercent", "autoAdvance"].forEach((id) => {
  const input = field(id);
  const out = field(id + "-out");
  const paint = () => { out.textContent = input.value; };
  input.oninput = paint; paint();
});
function applyPreset(name) {
  const preset = PRESETS[name];
  Object.entries(preset).forEach(([key, value]) => { field(key).value = value; });
  document.querySelectorAll("#themes button").forEach((button) => button.classList.toggle("on", button.textContent === name));
}
const themes = document.getElementById("themes");
Object.keys(PRESETS).forEach((name) => {
  const button = document.createElement("button");
  button.type = "button"; button.textContent = name;
  button.onclick = () => applyPreset(name);
  themes.appendChild(button);
});
applyPreset("Collins");
function settings() {
  return {
    title: field("title").value, author: field("author").value, font: field("font").value,
    primary: field("primary").value, accent: field("accent").value, text: field("text").value,
    page: field("page").value, card: field("card").value, buttonText: field("buttonText").value,
    radius: Number(field("radius").value), transition: Number(field("transition").value),
    transitionType: field("transitionType").value, passPercent: Number(field("passPercent").value),
    slideSize: Number(field("slideSize").value), showPageNumbers: field("showPageNumbers").checked,
    completion: field("completion").value, nextLabel: field("nextLabel").value, prevLabel: field("prevLabel").value,
    autoAdvance: Number(field("autoAdvance").value)
  };
}
function renderEditor() {
  const root = document.getElementById("modules");
  root.innerHTML = "";
  modules.forEach((mod, moduleIndex) => {
    const block = document.createElement("article");
    const heading = document.createElement("h3");
    heading.textContent = mod.name;
    const note = document.createElement("p");
    note.textContent = mod.note || "";
    block.appendChild(heading); block.appendChild(note);
    const row = document.createElement("div");
    row.className = "pages";
    mod.pages.forEach((page, pageIndex) => {
      const card = document.createElement("div");
      card.className = "page";
      if (page.kind === "image") {
        const image = document.createElement("img");
        image.src = page.url; image.alt = page.name || "Flattened slide";
        card.appendChild(image);
      } else {
        const label = document.createElement("p");
        label.textContent = page.kind + ": " + (page.name || "");
        card.appendChild(label);
      }
      const size = document.createElement("p");
      size.textContent = page.w && page.h ? (page.w + "×" + page.h + " flattened image") : page.kind;
      const tools = document.createElement("div");
      tools.className = "tools";
      const up = document.createElement("button"); up.type = "button"; up.className = "secondary"; up.textContent = "Up";
      const down = document.createElement("button"); down.type = "button"; down.className = "secondary"; down.textContent = "Down";
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "secondary"; remove.textContent = "Remove";
      up.onclick = () => { if (pageIndex > 0) { const pages = mod.pages; [pages[pageIndex - 1], pages[pageIndex]] = [pages[pageIndex], pages[pageIndex - 1]]; renderEditor(); } };
      down.onclick = () => { if (pageIndex < mod.pages.length - 1) { const pages = mod.pages; [pages[pageIndex + 1], pages[pageIndex]] = [pages[pageIndex], pages[pageIndex + 1]]; renderEditor(); } };
      remove.onclick = () => { mod.pages.splice(pageIndex, 1); renderEditor(); };
      const replace = document.createElement("label"); replace.className = "file-btn"; replace.textContent = "Replace";
      const input = document.createElement("input"); input.type = "file"; input.hidden = true;
      input.onchange = () => { if (input.files[0]) uploadInto(moduleIndex, pageIndex, input.files[0]); };
      replace.appendChild(input);
      tools.append(up, down, replace, remove);
      card.append(size, tools);
      row.appendChild(card);
    });
    block.appendChild(row);
    const questions = document.createElement("textarea");
    questions.value = (mod.questions || []).map((question) => question.prompt + " | " + question.choices.join(" / ") + " | " + (Number(question.answer) + 1)).join("\\n");
    questions.onchange = () => { mod.questions = parseQuestions(questions.value, mod.name); };
    const qLabel = document.createElement("label");
    qLabel.textContent = "Temporary questions: prompt | choice / choice | correct number";
    block.appendChild(qLabel); block.appendChild(questions);
    const add = document.createElement("button");
    add.type = "button"; add.className = "secondary"; add.textContent = "Add image or video page";
    const addInput = document.createElement("input"); addInput.type = "file"; addInput.hidden = true;
    add.onclick = () => addInput.click();
    addInput.onchange = () => { if (addInput.files[0]) uploadInto(moduleIndex, mod.pages.length, addInput.files[0]); };
    block.appendChild(add); block.appendChild(addInput);
    root.appendChild(block);
  });
  document.getElementById("generate").disabled = !modules.some((mod) => mod.pages.length);
}
function parseQuestions(text, name) {
  const rows = text.split(/\\n/).map((line) => line.trim()).filter(Boolean);
  const questions = rows.map((line) => {
    const parts = line.split("|");
    const choices = (parts[1] || "").split("/").map((choice) => choice.trim()).filter(Boolean);
    return { prompt: (parts[0] || "").trim(), choices, answer: Math.max(0, Number(parts[2] || 1) - 1) };
  }).filter((question) => question.prompt && question.choices.length > 1);
  return questions.length ? questions : [{ prompt: "Have you viewed every page of " + name + "?", choices: ["Yes", "No"], answer: 0 }];
}
async function uploadInto(moduleIndex, pageIndex, file) {
  const body = new FormData();
  body.append("file", file, file.name);
  setStatus("Adding " + file.name);
  const response = await fetch("/api/upload", { method: "POST", body });
  const data = await response.json();
  if (!response.ok) { setStatus(data.error || "Upload failed", true); return; }
  const pages = modules[moduleIndex].pages;
  if (pageIndex >= pages.length) pages.push(data.page); else pages[pageIndex] = data.page;
  renderEditor();
  setStatus("Page updated.");
}
document.getElementById("flatten").onclick = async () => {
  const body = new FormData();
  files.forEach((file) => body.append("file", file, file.name));
  setStatus("Flattening each whole slide to an image…");
  document.getElementById("flatten").disabled = true;
  try {
    const response = await fetch("/api/preview", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) { setStatus(data.error || "Could not flatten the slides", true); return; }
    modules = data.modules;
    document.getElementById("editor").hidden = false;
    renderEditor();
    setStatus(data.note);
  } finally {
    document.getElementById("flatten").disabled = files.length === 0;
  }
};
document.getElementById("generate").onclick = async () => {
  setStatus("Building the SCORM package from the flattened images…");
  const payload = {
    settings: settings(),
    modules: modules.map((mod) => ({
      name: mod.name,
      questions: mod.questions,
      pages: mod.pages.map((page) => ({ id: page.id, kind: page.kind }))
    }))
  };
  const response = await fetch("/api/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    setStatus(data.error || "Could not build the package", true);
    return;
  }
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = (field("title").value || "course").replace(/[^A-Za-z0-9]+/g, "-") + "-scorm.zip";
  link.click();
  setStatus("SCORM package downloaded.");
};
document.getElementById("login-form").onsubmit = async (event) => {
  event.preventDefault();
  const response = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: field("password").value }) });
  if (!response.ok) { field("login-status").textContent = "That password does not match."; return; }
  document.getElementById("gate").hidden = true;
};
fetch("/api/health").then((response) => { if (response.ok) document.getElementById("gate").hidden = true; });
</script>
</body>
</html>
"""


def _boundary(content_type: str) -> bytes:
    match = re.search(r'boundary="?([^";]+)"?', content_type or "")
    if not match:
        raise FlattenError("Upload was not a multipart form.")
    return match.group(1).strip().encode("utf-8", "replace")


def parse_multipart(body: bytes, content_type: str) -> tuple[dict[str, str], list[tuple[str, str, bytes]]]:
    boundary = _boundary(content_type)
    fields: dict[str, str] = {}
    files: list[tuple[str, str, bytes]] = []
    for part in body.split(b"--" + boundary):
        if not part or part in {b"--", b"--\r\n"} or part.strip() in {b"", b"--"}:
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        if part.endswith(b"--"):
            part = part[:-2]
        head, sep, data = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        if data.endswith(b"\r\n"):
            data = data[:-2]
        header = head.decode("utf-8", "replace")
        name_match = re.search(r'name="([^"]*)"', header)
        file_match = re.search(r'filename="([^"]*)"', header)
        if not name_match:
            continue
        if file_match and file_match.group(1):
            files.append((name_match.group(1), Path(file_match.group(1)).name, data))
        else:
            fields[name_match.group(1)] = data.decode("utf-8", "replace")
    return fields, files


def save_upload(filename: str, data: bytes, work: Path) -> Path:
    clean = Path(filename).name or "upload"
    if clean in {".", ".."}:
        clean = "upload"
    target = work / clean
    target.write_bytes(data)
    return target


class StudioHandler(BaseHTTPRequestHandler):
    server_version = "EvotixSCORM/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cookie_token(self) -> str:
        for part in (self.headers.get("Cookie") or "").split(";"):
            part = part.strip()
            if part.startswith("studio="):
                return part.split("=", 1)[1]
        return ""

    def _authed(self) -> bool:
        token = self._cookie_token()
        with STATE_LOCK:
            return token in SESSIONS

    def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > 250_000_000:
            raise FlattenError("Upload is too large.")
        return self.rfile.read(length)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send(200, STUDIO_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/health":
            if not self._authed():
                self._json(401, {"ok": False})
                return
            self._json(200, {"ok": True, "pymupdf": pymupdf is not None, "libreoffice": bool(find_soffice())})
            return
        if path.startswith("/api/asset/"):
            if not self._authed():
                self._json(401, {"error": "Sign in first."})
                return
            asset_id = path.rsplit("/", 1)[-1]
            with STATE_LOCK:
                record = ASSETS.get(asset_id)
            if not record:
                self._json(404, {"error": "That page is gone."})
                return
            data = Path(record["path"]).read_bytes()
            mime = mimetypes.guess_type(record["path"])[0] or "application/octet-stream"
            self._send(200, data, mime)
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/login":
                payload = json.loads(self._read_body().decode("utf-8") or "{}")
                if not password_matches(str(payload.get("password") or "")):
                    self._json(401, {"ok": False})
                    return
                token = secrets.token_hex(24)
                with STATE_LOCK:
                    SESSIONS.add(token)
                self._send(
                    200,
                    b'{"ok":true}',
                    "application/json",
                    {"Set-Cookie": f"studio={token}; HttpOnly; SameSite=Strict; Path=/"},
                )
                return
            if not self._authed():
                self._json(401, {"error": "Sign in first."})
                return
            if path == "/api/preview":
                _fields, uploads = parse_multipart(self._read_body(), self.headers.get("Content-Type") or "")
                if not uploads:
                    raise FlattenError("Add at least one file.")
                work = Path(tempfile.mkdtemp(prefix="evotix_preview_"))
                modules = []
                notes = []
                for index, (_name, filename, data) in enumerate(uploads):
                    saved = save_upload(filename, data, work)
                    module = ingest_file(saved, work, index)
                    modules.append(module)
                    notes.append(module["note"])
                self._json(200, {"ok": True, "modules": modules, "note": " ".join(notes)})
                return
            if path == "/api/upload":
                _fields, uploads = parse_multipart(self._read_body(), self.headers.get("Content-Type") or "")
                if not uploads:
                    raise FlattenError("Choose a file.")
                _name, filename, data = uploads[0]
                work = Path(tempfile.mkdtemp(prefix="evotix_upload_"))
                saved = save_upload(filename, data, work)
                kind = classify(saved)
                if kind == "flatten":
                    module = ingest_file(saved, work, 0)
                    self._json(200, {"ok": True, "pages": module["pages"], "page": module["pages"][0]})
                    return
                if kind == "unknown":
                    raise FlattenError("Use an image or a video for a replacement page.")
                page = store_asset(saved, kind, saved.name)
                self._json(200, {"ok": True, "page": page})
                return
            if path == "/api/generate":
                payload = json.loads(self._read_body().decode("utf-8") or "{}")
                settings = clean_settings(payload.get("settings") or {})
                modules = []
                for raw in payload.get("modules") or []:
                    pages = []
                    for page in raw.get("pages") or []:
                        with STATE_LOCK:
                            record = ASSETS.get(str(page.get("id") or ""))
                        if not record:
                            raise FlattenError("A page image is missing. Flatten the slides again.")
                        pages.append({"kind": record["kind"], "path": record["path"]})
                    modules.append(
                        {
                            "name": raw.get("name") or "Module",
                            "pages": pages,
                            "questions": raw.get("questions"),
                        }
                    )
                if not modules:
                    raise FlattenError("Flatten the slides before generating.")
                out = Path(tempfile.mkdtemp(prefix="evotix_zip_")) / "course.zip"
                build_zip(modules, settings, out)
                data = out.read_bytes()
                slug = re.sub(r"[^A-Za-z0-9]+", "-", settings["title"]).strip("-") or "course"
                self._send(
                    200,
                    data,
                    "application/zip",
                    {"Content-Disposition": f'attachment; filename="{slug}-scorm.zip"'},
                )
                return
            self._json(404, {"error": "Not found"})
        except FlattenError as exc:
            self._json(400, {"error": str(exc)})
        except (json.JSONDecodeError, UnicodeError, OSError, ValueError, zipfile.BadZipFile) as exc:
            self._json(400, {"error": f"Could not build the course: {exc}"})


def make_server(port: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((HOST, port), StudioHandler)


def serve(port: int | None = None) -> None:
    chosen = PORT_START if port is None else port
    last_error: OSError | None = None
    httpd = None
    for offset in range(20):
        try:
            httpd = make_server(chosen + offset)
            break
        except OSError as exc:
            last_error = exc
    if httpd is None:
        raise SystemExit(f"Could not start the studio: {last_error}")
    url = f"http://{HOST}:{httpd.server_address[1]}/"
    print(f"Evotix SCORM Studio at {url}")
    print("The studio password is in README-USB.txt. It is stored only as a hash.")
    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


def run_cli(inputs: list[str], output: str, title: str) -> None:
    paths = [Path(item) for item in inputs]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise SystemExit("Cannot find: " + ", ".join(missing))
    work = Path(tempfile.mkdtemp(prefix="evotix_cli_"))
    try:
        modules = prepare_modules(paths, work)
        notes = [f"{module['name']}: {len(module['pages'])} page images" for module in modules]
        print("Flattened first. " + "; ".join(notes))
        build_zip(modules, {"title": title}, output)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(output)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Flatten documents to images and pack a SCORM 1.2 course.")
    parser.add_argument("--cli", action="store_true", help="Convert files without opening the studio")
    parser.add_argument("--set-password", action="store_true", help="Store a new studio password hash")
    parser.add_argument("-o", "--output", default="course-scorm.zip")
    parser.add_argument("--title", default="Training course")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("inputs", nargs="*")
    args = parser.parse_args(argv)
    if args.set_password:
        first = getpass.getpass("New studio password: ")
        second = getpass.getpass("Repeat: ")
        if first != second or len(first) < 4:
            raise SystemExit("The passwords did not match, or were shorter than 4 characters.")
        write_password(first)
        print(f"Wrote {password_record_path().name}. The old plain-text password file is not used.")
        return
    if args.cli:
        if not args.inputs:
            raise SystemExit("Give at least one file, for example: python evotix_scorm_gui.py --cli deck.pptx -o course.zip")
        run_cli(args.inputs, args.output, args.title)
        return
    serve(args.port or None)


if __name__ == "__main__":
    main()
