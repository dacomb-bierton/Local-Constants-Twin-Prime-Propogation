# TeslaCam Editor

A desktop-grade editor for Tesla dashcam and Sentry Mode footage that runs on Windows (and macOS/Linux).
It is a small local Python server with a browser UI; all rendering is done with a bundled ffmpeg.

Features (everything the popular iOS TeslaCam apps do, on a PC):

- **Library** – open the USB drive (or a copied `TeslaCam` folder); events from `SavedClips`, `SentryClips`
  and `RecentClips` are listed with thumbnails, trigger reason (honk, Sentry detection, impact…), city and a
  map.  Rolling `RecentClips` footage is grouped into drives.
- **Synchronised multi-camera player** – all six cameras (front, rear, both repeaters, both B-pillars on
  HW4 cars) play in sync across consecutive one-minute segments as one continuous timeline, with segment
  ticks and the Sentry trigger marker.
- **Layouts** – single, grid, picture-in-picture, main + side strip, cinematic, side-by-side strip.  Select any
  subset of cameras; the layout adapts.  Click a tile to make it the main camera.
- **Camera cycling** – rotate the main camera manually (`C`, `1`–`6`) or automatically every N seconds; the
  cycling is baked into the export.
- **Any aspect ratio** – 16:9, 9:16, 1:1, 4:3, 3:4, 21:9, 4:5, 5:4, 2:1 at 480p–4K.  The preview is exactly
  the export canvas; layouts re-arrange for portrait canvases.
- **Multi-clip sequences** – set in/out points, add the range with its camera view to the sequence, combine
  clips from different events and days, reorder by drag and drop, duplicate, split, per-clip speed
  (0.25× slow motion to 16× time-lapse), preview the whole sequence.
- **Music** – add an MP3/M4A/WAV, choose where in the song to start, volume, fade in/out, loop, and where in
  the video it starts.  (TeslaCam clips contain no audio.)
- **Overlays** – running timestamp taken from the recording clock, location and event reason, camera
  labels, mirror rear-facing cameras, blur regions for licence plates, custom watermark/logo.
- **Export** – MP4 (H.264) with automatic GPU encoding (NVIDIA NVENC, AMD AMF, Intel Quick Sync) when
  available, GIF, or a single snapshot image.  Progress bar and cancel.
- Delete events from the drive, open the folder in Explorer, save/load projects, keyboard shortcuts (`?`).

## Run on Windows

1. Install Python 3.10 or newer from <https://www.python.org/downloads/windows/> and tick
   **Add python.exe to PATH**.
2. Download/clone this folder and double-click **`run.bat`**.  The first run creates a virtual
   environment and installs the dependencies (including ffmpeg, ~80 MB); later runs start immediately.
3. Your browser opens <http://127.0.0.1:8321/>.  Enter the path of your TeslaCam drive (for example
   `E:\TeslaCam`) or press **Browse…**.  Plugged-in TeslaCam drives are detected automatically.

Command line options: `run.bat --root E:\TeslaCam --port 8321 --no-browser`.

### Optional: build a standalone `.exe`

`build_exe.bat` uses PyInstaller to create `dist\TeslaCamEditor\TeslaCamEditor.exe` with ffmpeg bundled, so
the folder can be copied to a PC without Python.

## Run on macOS / Linux

```bash
./run.sh
```

## How exporting works

Each sequence clip is rendered by a single ffmpeg pass: the covering segment files of every selected camera
are trimmed, scaled/cropped to their tile, mirrored, joined and composited on the canvas; overlays, blur
regions and the watermark are added; camera cycling splits the clip into consecutive pieces with a rotating
main camera.  The pieces are concatenated without re-encoding and the music is mixed in last.  Timestamps
come from the segment file names (the car's clock), so they stay correct at any playback speed.

Files are written to `Videos\TeslaCam Exports` by default; settings, thumbnails and projects live in
`%APPDATA%\TeslaCamEditor`.

## Development

```bash
pip install -r requirements.txt pytest
python -m pytest            # generates synthetic TeslaCam footage and exports it in 16:9, 9:16 and 1:1
python -m teslacam_editor --root /path/to/TeslaCam
```

Environment variables: `TCE_FFMPEG` (use a specific ffmpeg binary), `TCE_DATA_DIR` (settings/cache
location), `TCE_FONT` (TrueType font for overlays).
