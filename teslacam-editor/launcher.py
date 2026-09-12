"""Entry point used by the PyInstaller build (see teslacam_editor.spec)."""

import multiprocessing
import sys

from teslacam_editor.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
