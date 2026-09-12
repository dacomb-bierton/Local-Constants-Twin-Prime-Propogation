# TeslaCam Editor

A full-featured editor for Tesla dashcam and Sentry Mode footage that runs on **Windows** (also macOS and
Linux).  It is a small local Python server with a browser user interface; all video processing is done with
a bundled copy of ffmpeg, so nothing else has to be installed.

Everything the popular iOS "TeslaCam" apps do, on a PC:

| Area | What you get |
| --- | --- |
| Library | Open the USB drive or a copied `TeslaCam` folder. Events from `SavedClips`, `SentryClips` and `RecentClips` with thumbnails, trigger reason (honk, Sentry object detection, impact, manual save), city and map. Rolling `RecentClips` footage is grouped into drives. Filter by type or text. |
| Player | All six cameras (front, rear, left/right repeater, left/right B-pillar on HW4 cars) play **in sync**, and consecutive one-minute segment files are stitched into one continuous timeline with segment ticks and the Sentry trigger marker. Speed 0.25×–8×, frame step, fullscreen. |
| Layouts | Single, Grid, Picture-in-picture, Main + side strip, Cinematic, Strip. Select **any subset of cameras**; the layout adapts. Click a tile to make it the main camera. |
| Camera cycling | Rotate the main camera manually (`Cycle cam`, `C`, keys `1`–`6`) or **automatically every N seconds** while playing. Cycling is rendered into the export. |
| Aspect ratios | 16:9, 9:16, 1:1, 4:3, 3:4, 21:9, 4:5, 5:4, 2:1 at 480p, 720p, 1080p, 1440p or 4K. The preview is exactly the export canvas; layouts rearrange for portrait. |
| Sequences | Set In/Out points, add the range with its camera view to the sequence, **combine clips from different events and days**, drag to reorder, duplicate, split, per-clip speed (0.25× slow motion to 16× time-lapse), preview the whole sequence. |
| Music | Add an MP3 / M4A / WAV / FLAC / OGG. Choose where in the song to start, where in the video it starts, volume, fade in/out, loop. Heard during the sequence preview and mixed into the export. (TeslaCam clips themselves have no audio.) |
| Overlays | Running timestamp taken from the recording clock (accurate at any speed), location and event reason, camera labels, mirror rear-facing cameras, **blur regions** for licence plates and faces, custom watermark / logo. |
| Export | MP4 (H.264) with automatic GPU encoding (NVIDIA NVENC, AMD AMF, Intel Quick Sync) or CPU, three quality presets, GIF, single snapshot image, or the **original camera files joined losslessly**. Progress bar, cancel, "Show in folder". |
| Management | Delete events from the drive, open the event folder in Explorer, save/load projects, keyboard shortcuts (`?`). |

---

## 1. Requirements

* Windows 10 or 11 (64-bit). macOS 12+ and Linux also work.
* **Python 3.10 or newer** – free from <https://www.python.org/downloads/windows/>.  
  During installation tick **"Add python.exe to PATH"**.
* A modern browser (Edge, Chrome, Firefox). Edge is already on every Windows PC.
* About 300 MB of disk space for the Python packages and the bundled ffmpeg.
* Optional: an NVIDIA, AMD or Intel GPU for faster exports (detected automatically).

No admin rights are needed; everything is installed into the program folder and your user profile.

## 2. Installation and first start (Windows)

1. Unzip `TeslaCamEditor.zip` anywhere, for example `C:\TeslaCamEditor`.
2. Double-click **`run.bat`**.  
   The first run creates a private Python environment (`.venv`) inside the folder and downloads the
   dependencies including ffmpeg (~80 MB). This takes one to three minutes and happens only once.
3. A console window stays open (it is the server – keep it open while you use the app) and your browser
   opens <http://127.0.0.1:8321/>.
4. In the folder box at the top enter the location of your footage, e.g. `E:\TeslaCam`, and press **Open**
   – or press **Browse…** and pick it.  Plugged-in TeslaCam drives are listed automatically in the
   **Detected / recent…** dropdown.  You can also point it at a folder you copied from the drive to your PC,
   or directly at a single `SavedClips`, `SentryClips` or event folder.

To stop the program close the console window (or press `Ctrl+C` in it).  To start it again just run
`run.bat`; later starts take a second or two.

If Windows SmartScreen or Defender complains about `run.bat`, choose *More info → Run anyway*; the file is
a plain, readable batch script.

### Command line options

```
run.bat --root E:\TeslaCam      open this folder on start
run.bat --port 9000             use another port
run.bat --no-browser            do not open the browser automatically
run.bat --host 0.0.0.0          allow other devices on your network to use the UI
```

### macOS / Linux

```bash
chmod +x run.sh
./run.sh
```

### Optional: standalone .exe (no Python on the target PC)

Run `build_exe.bat` once on a PC that has the environment set up. It uses PyInstaller to create
`dist\TeslaCamEditor\TeslaCamEditor.exe` with ffmpeg included. Copy the whole `dist\TeslaCamEditor` folder
to any Windows PC and start the `.exe`.

## 3. Using the editor

The window has four areas: **Library** (left), **Stage + transport + timeline** (centre), **Sequence**
(bottom) and the **Inspector** with tabs *View · Clip · Music · Export · Info* (right).

### 3.1 Library

* Cards are grouped by day, newest first. Badges show *Saved*, *Sentry* or *Recent*; the second line shows
  the trigger reason (Honk, Sentry: object detected, Sentry: impact, …) and the third the city, length and
  number of cameras.
* Use the *All / Saved / Sentry / Recent* buttons and the search box (date, city, reason) to filter.
* Click a card to load it.  Sentry and Saved events open ten seconds before the trigger moment; the trigger is
  marked with an orange flag on the timeline.
* The **Info** tab shows the full metadata, GPS location on a map (needs internet for map tiles; a Google Maps
  link is always available) and buttons to **Show files**, **Export original files** and **Delete from
  drive…**.

### 3.2 Player and camera view

* **Cameras** (View tab): tick the cameras you want to see.  Cameras the event does not have are greyed out.
  *All* / *Front only* are shortcuts.
* **Layout**: pick one of the six layouts.  The icons show how the current canvas aspect is divided.
* **Main camera**: the large tile in PiP / side / cinematic layouts and the only one in *Single*.  Change it
  from the dropdown, by clicking a tile, with `Cycle cam`, with keys `1`–`6`, or with the mouse.
* **Fit**: *Fill tile* crops the 4:3 camera image to fill its tile; *Fit inside* letterboxes it.
* **Mirror**: flips the rear-facing cameras horizontally so they read like the car's mirrors.
* **Auto cycle**: tick *Auto* in the transport bar and set the seconds; while playing, the main camera rotates
  through the selected cameras.  This is stored with the clip and rendered into the export.
* **Speed**: 0.25× to 8× for playback (0.25× to 16× per clip for export).
* **Canvas aspect**: choose the output shape; the stage takes that shape immediately.
* **Overlays**: timestamp (from the recording clock), location & event reason, camera labels.  The preview
  shows them where the export will place them.
* Transport: previous/next segment, ±5 s, play/pause, time and clock readout, **Snapshot** (saves the current
  view as a JPG), fullscreen.

### 3.3 Timeline, In/Out and the sequence

1. Click or drag on the timeline to move the playhead.  Segment boundaries are marked with the wall-clock
   time.
2. Press **Set In** (`I`) and **Set Out** (`O`) to choose a range.  *Clear* uses the whole event.
3. Press **+ Add to sequence** (`Enter`).  The clip stores the range **and** the current camera view (cameras,
   layout, main camera, cycling, mirror, overlays, blur, speed).
4. Load another event (from another day if you like), set In/Out, add again.  Repeat as needed.
5. In the **Sequence** strip: click a clip to select and edit it, drag to reorder, use the small ←/→/⧉/✕
   buttons, or press `Delete`.  The header shows the total output length.
6. **Clip** tab (for the selected clip): exact In/Out seconds, speed, blur regions, duplicate, **split at
   playhead**, remove.  Any change to the camera view while a clip is selected updates that clip.
7. **▶ Preview sequence** plays everything in order, with music, exactly as it will be exported.

### 3.4 Blur (privacy)

Select a clip, open the *Clip* tab, press **Draw blur region**, then drag a rectangle on the stage.  Regions
are fixed to the canvas for the length of that clip; add as many as needed and remove them with the ×.

### 3.5 Music

*Music* tab → **Choose file…** (uploads a copy) or **Use path…** (type a path such as `C:\Music\song.mp3`).
Then set *Start in song*, *Start in video*, *Volume*, *Fade in/out* and *Loop*.  The music is trimmed or looped
to the video length and faded out at the end.

### 3.6 Export

*Export* tab:

* **Aspect ratio** and **Resolution** – the resolution is the length of the shorter canvas side, so 1080 gives
  1920×1080 for 16:9, 1080×1920 for 9:16 and 1080×1080 for 1:1.  The exact pixel size is shown.
* **Frame rate** 24/30/36/60, **Quality** Draft / Standard / High.
* **Format** MP4 or GIF (GIF is best kept short and at 480).
* **Encoder** – *Auto* uses your GPU when one is available, otherwise the CPU encoder.
* **Background colour** for letterboxing and empty canvas areas.
* **Watermark / logo** – any PNG/JPG, with position, size and opacity.
* **Destination** folder and optional file name (default: `Videos\TeslaCam Exports`).

Press **Export sequence**.  If the sequence is empty the current view and In/Out range are exported.  The
progress bar shows the clip being rendered; **Cancel** stops it.  When finished, **Show in folder** opens
Explorer and **Preview** plays the result.

*Export original files* (Info tab) joins the original one-minute files of the selected cameras without
re-encoding – fastest and lossless, no layout.

### 3.7 Projects

Type a name at the top and press **Save**; the sequence, music and export settings are stored.  Use **Load…**
to restore.  Projects reference the footage by path, so keep the TeslaCam folder in the same place.

### 3.8 Keyboard shortcuts

| Key | Action | Key | Action |
| --- | --- | --- | --- |
| `Space` / `K` | Play / pause | `J` / `L` | Back / forward 10 s |
| `←` / `→` | Back / forward 1 s (`Shift`: 5 s) | `,` / `.` | Step one frame |
| `[` / `]` | Previous / next segment | `Home` / `End` | Start / end |
| `I` / `O` | Set In / Out | `Enter` | Add to sequence |
| `C` | Cycle main camera | `1`–`6` | Main camera: front, rear, left, right, left pillar, right pillar |
| `M` | Mirror rear cameras | `F` | Fullscreen |
| `G` / `P` / `S` | Layout grid / PiP / single | `Delete` | Remove selected clip |

## 4. Where things are stored

| What | Location |
| --- | --- |
| Exports and snapshots | `%USERPROFILE%\Videos\TeslaCam Exports` (changeable in the Export tab) |
| Settings, thumbnails, projects, uploaded music | `%APPDATA%\TeslaCamEditor` |
| Python environment | `.venv` inside the program folder (delete it to reinstall) |

Nothing is written to the TeslaCam drive unless you use **Delete from drive…**.

## 5. Troubleshooting

* **"Python was not found"** – install Python from python.org and tick *Add python.exe to PATH*, then run
  `run.bat` again.  (The Microsoft Store version of Python also works.)
* **Browser did not open** – open <http://127.0.0.1:8321/> yourself.  If the port is busy the console shows
  the port actually used.
* **Dependency installation failed** – check your internet connection, delete the `.venv` folder and run
  `run.bat` again.  Behind a proxy set `HTTPS_PROXY` first.
* **Folder not found / 0 events** – point at the folder that contains `SavedClips`, `SentryClips`,
  `RecentClips` (usually `X:\TeslaCam`) or at one of those folders.  Files must keep Tesla's names
  (`2024-05-01_12-34-56-front.mp4`).
* **Video does not play in the browser** – Tesla records H.264, which every browser plays.  If a tile shows
  *No recording*, that camera file is missing from that minute (common on the rear camera or at the start of
  Sentry events); the export fills the gap with black.
* **Slow playback with six cameras** – choose fewer cameras or a smaller layout for previewing; the export is
  unaffected.  HW4 front-camera files are large.
* **Export is slow** – use *Draft* quality while testing, check that **Encoder** shows your GPU, keep the
  resolution at 1080 for social media.
* **No GPU encoder listed** – update your graphics driver.  The CPU encoder always works.
* **Map is blank** – the map needs internet access; the coordinates and a Google Maps link are still shown.
* **Text overlays use an odd font** – set the environment variable `TCE_FONT` to a `.ttf` file path.

Advanced environment variables: `TCE_FFMPEG` (use your own ffmpeg.exe), `TCE_DATA_DIR` (settings location),
`TCE_FONT` (overlay font).

## 6. How it works

* `teslacam_editor/scanner.py` reads the TeslaCam folder structure, `event.json`, groups files into events and
  segments, probes durations (cached).
* `teslacam_editor/layouts.py` computes tile geometry for a camera set on a canvas; the same numbers drive the
  browser preview and the ffmpeg render, so the preview is exact.
* `teslacam_editor/export.py` builds one ffmpeg pass per clip: for every camera the covering minute files are
  trimmed, scaled/cropped to their tile, mirrored, joined, and composited on the canvas; overlays, blur and
  watermark are added; camera cycling splits the clip into pieces with a rotating main camera.  Pieces are
  concatenated without re-encoding and the music is mixed in last.  Timestamps come from the file names
  (the car's clock) so they are correct at any speed.
* `teslacam_editor/overlays.py` renders text with Pillow; the running clock is a sprite sheet selected with a
  time expression, so it does not depend on ffmpeg's `drawtext` filter.
* `teslacam_editor/app.py` is the FastAPI server (library, range-request video streaming, layouts, export
  jobs, projects); `teslacam_editor/static/` is the plain HTML/JS/CSS interface.

Only `127.0.0.1` is served by default; nothing leaves your PC except map tiles and the Leaflet map library.

## 7. Development and tests

```bash
pip install -r requirements.txt pytest httpx
python -m pytest            # builds synthetic TeslaCam footage, exports it in 16:9 / 9:16 / 1:1, tests the API
python -m teslacam_editor --root /path/to/TeslaCam
```

Project layout:

```
run.bat / run.sh            launchers (create .venv, install, start)
build_exe.bat, teslacam_editor.spec, launcher.py   standalone .exe build
requirements.txt, pyproject.toml
teslacam_editor/            Python package (server, scanner, layouts, export, overlays, static UI)
tests/                      pytest suite with synthetic footage generator
```

## 8. Licence

MIT – see `LICENSE`.  ffmpeg is provided by the `imageio-ffmpeg` package under its own (LGPL/GPL) licence.
This project is not affiliated with Tesla, Inc.
