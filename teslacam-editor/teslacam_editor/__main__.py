"""`python -m teslacam_editor` — start the local server and open the UI in the default browser."""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="teslacam-editor", description="TeslaCam multi-camera dashcam editor")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8321)
    parser.add_argument("--no-browser", action="store_true", help="do not open the UI in a browser")
    parser.add_argument("--root", help="TeslaCam folder to load on start")
    args = parser.parse_args(argv)

    import uvicorn

    from . import ffmpeg_tools as ff
    from .app import app, library
    from .export import cleanup_stale_workdirs

    try:
        print(f"ffmpeg: {ff.ffmpeg_exe()}")
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    cleanup_stale_workdirs()

    port = args.port
    while not _port_free(port) and port < args.port + 20:
        port += 1
    if args.root:
        try:
            library.scan(args.root)
            print(f"Loaded {len(library.order)} events from {library.root}")
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)

    url = f"http://{args.host}:{port}/"
    print(f"TeslaCam Editor running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:

        def _open() -> None:
            time.sleep(1.0)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()
    uvicorn.run(app, host=args.host, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
