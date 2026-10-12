Evotix SCORM Studio
===================

Turns PowerPoint, PDF, Word, and Excel files into a SCORM 1.2 course for
Evotix Learn. The first step flattens every whole page to one image. The
course shows those images. It does not pull pictures out of the file and
draw the slide again, so the page keeps the colours, pictures, and text
from the original.

Run it from a work PC or a USB stick. Nothing here needs administrator rights.


What you need
-------------
- Windows PowerPoint, or LibreOffice (including a portable copy in a
  LibreOffice folder next to this file). One of those flattens the slides.
- Python 3.10 or newer. The launcher uses python-portable\python.exe if
  that folder is present, then py -3, then python.
- Optional, for faster PDF pages: pip install --user pymupdf
  Poppler's pdftoppm is used when PyMuPDF is not installed.

The Galano Grotesque family is not included. Put your licensed .woff2, .ttf,
or .otf files in a fonts folder next to Launch-SCORM.bat before you generate,
and the course will use them. If the files are not there, the course still
asks for Galano Grotesque and then uses the PC's usual font.


Start the studio
----------------
1. Copy this whole folder onto the PC or the USB stick.
2. Double-click Launch-SCORM.bat.
   Or, in PowerShell:  powershell -ExecutionPolicy Bypass -File .\Launch-SCORM.ps1
3. The browser opens a page on this computer only (127.0.0.1).
4. Studio password: EvotixUSB
   The program stores only a PBKDF2 hash of that password. It is not written
   in evotix_scorm_gui.py. To change it, open a command window in this folder
   and run:  python evotix_scorm_gui.py --set-password
   That writes studio-password.hash. Delete any old studio-password.txt.

The launcher prints whether the folder is on a removable drive.


Build a course
--------------
1. Drop in the PowerPoint, PDF, Word, Excel, image, or video files.
2. Click "Flatten slides to images".
   Wait until each page shows a picture and a size such as 1920×1080.
   That picture is the whole slide. If this step fails, PowerPoint and
   LibreOffice were both missing or the file could not be opened. Fix that
   and flatten again. The studio will not invent a slide from the loose pictures.
3. On each page you can replace the image, add an image or video page, move
   it, or remove it. Edit the temporary questions under the pages.
   Questions are written as:  prompt | choice / choice | correct number
4. Collins is the starting colour template (orange 021 C #FE5000, green
   3425 C #006242, rich black #1A1A1A, silver page #E4E5E6, white cards).
   Click Collins again after trying another theme. Colour boxes are pickers,
   not hex fields. Sliders set button roundness, transition, slide size,
   pass mark, and auto-advance. Slide size scales the picture evenly. It does
   not crop or stretch it.
5. The pass mark starts at 1%, so almost everyone who views the pages and
   answers the questions will pass.
6. Click "Generate SCORM ZIP".

Without the browser, from a command window:

  python evotix_scorm_gui.py --cli "Safety deck.pptx" -o course-scorm.zip --title "Safety"


What the learner sees
----------------------
- Each flattened slide, at its real shape.
- Next and Back, the arrow keys, and a sideways swipe.
  Drag from right to left for the next page. Drag from left to right to go back.
  A mostly vertical drag still scrolls. Buttons and video controls are left alone.
- Time on the current page, and time for every page on the completion screen.
- Two temporary questions after each file. Change them before you generate.
- Completion is reported to the LMS only after every page has been opened and
  the score is at least the pass mark.


Upload to Evotix Learn
-----------------------
1. In Learn, open Media, choose Add new, and upload the .zip.
   Do not unzip it first.
2. Open SCORM Stages, choose Add new, and give the stage a title.
3. Under SCORM media, select the zip you uploaded.
4. Publish.

The package is SCORM 1.2. imsmanifest.xml is at the root of the zip, the
lesson is a SCO, and it reports lesson_status, score, session time, and the
pages already viewed. Evotix loads it in the same window. Completion is
recorded when the course reports it.


Themes
------
Collins, Evotix, Dark, Light, Corporate, High Contrast, Ocean, Forest,
Sunset, Slate, Plum, Sand, Navy, Rose, Amber, Glacier, Ink, Paper, Safety,
Night, Mint, Copper, Stone, Wine, Arctic, Graphite.


If the slides look wrong
-------------------------
Flatten again with this version and generate a new zip. The picture on the
page has to be the whole slide. A small picture of only one shape, a stretched
picture, or a recoloured background means that step did not run.
