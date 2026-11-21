# PDF Redactor

A small macOS app for **true PDF redaction** — permanently removing sensitive
text and image content from a PDF, not just drawing a black box over it.

Draw rectangles over content to remove, or search for text and redact every
match, then apply. The underlying text, graphics, and image pixels are
stripped from the document before you save — so the "hidden" content can't
be recovered by copy-pasting, exporting, or looking at the raw file.

## Demo

https://github.com/user-attachments/assets/3b1a2d27-6fc4-45a1-821d-c9b5958e56a3

## Quick Start (no programming required)

1. Go to the [Releases page](https://github.com/DevTamer/pdf-redactor-for-mac/releases)
   and download the latest `PDF Redactor.dmg`.
2. Open the DMG and drag **PDF Redactor** into your **Applications** folder.
3. The app isn't code-signed/notarized (that requires a paid Apple Developer
   account), so macOS Gatekeeper will refuse to open it with a normal
   double-click the first time. Instead: **right-click (or Control-click) the
   app → Open → Open**. You only need to do this once.
4. Use **File → Open…** to load a PDF, mark what you want redacted, then
   **APPLY REDACTIONS** and **Save Redacted As…**.

## How redaction works here

- **Draw a rectangle** on the page to mark that area for redaction. You
  don't need to be pixel-precise — the app tightens your rectangle to the
  actual text line(s) it substantially covers before removing anything, so
  a bit of stray margin above or below a line you're dragging over won't
  take a neighboring line down with it.
- **Search Text** finds every occurrence of a term on every page and marks
  each match automatically.
- Marked areas show as pending (semi-transparent red) until you press
  **APPLY REDACTIONS** — at that point the text, vector graphics, and image
  pixels under each marked rectangle are permanently removed from the
  document and a black box is drawn in their place.
- **Save Redacted As…** writes the result to a new file. Saving also strips
  metadata, embedded files, and JavaScript, and garbage-collects the file
  so leftover unreferenced objects don't carry redacted content along with
  them. Your original file is never modified.

### Undo / History

Applying redactions isn't a dead end while you're still working: **Edit →
Undo Apply** (`Cmd+Z`) / **Redo Apply** (`Cmd+Shift+Z`), or clicking an
entry in the **History** panel, can take you back to (or forward from) any
earlier state — much like Photoshop's history palette.

This history is intentionally session-only: it lives in memory for as long
as the document stays open in the app, and closing the document or quitting
discards it. Nothing about it is ever written to disk. **Whatever you Save
always reflects only the current state** — a saved file never contains
history, so redacted content it no longer shows is genuinely gone from
that file, not just hidden behind an available "undo." If you want to walk
a redaction back after you've already saved, reopen the *original* source
file (which the app never modifies) and start again from there.

## Developer setup

Requires [Homebrew](https://brew.sh). macOS's built-in system Python links
against an old Tcl/Tk that crashes on modern macOS as soon as a window
opens, so `setup.sh` installs and uses a Homebrew Python (`python-tk@3.11`)
with a working Tk instead.

```bash
git clone https://github.com/DevTamer/pdf-redactor-for-mac.git
cd pdf-redactor-for-mac
./setup.sh
source venv/bin/activate && python redactor.py
```

### Running the tests

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

The automated suite (`tests/`) covers the redaction model, redaction
precision, undo/redo history, and what actually ends up in saved files. It
also includes a smoke test that drives the real window's handlers, including
drawing rectangles with simulated mouse events. That test skips itself if
Tk can't open a window. Tests for rendering and coordinate math live in
[pdfcore](https://github.com/DevTamer/pdfcore). Dialogs and real clicking
still need a manual pass before a release; see
[`docs/MANUAL_TESTING.md`](docs/MANUAL_TESTING.md).

### Working on pdfcore at the same time

The page rendering, PDF↔screen coordinate math, undo/redo snapshot history
and canvas page view come from [pdfcore](https://github.com/DevTamer/pdfcore),
a small library shared with the PDF Editor app. `requirements.txt` pins it to
an exact release tag. To change pdfcore and see the effect here immediately,
clone it next to this repo and install it in editable mode:

```bash
git clone https://github.com/DevTamer/pdfcore.git ../pdfcore
./setup.sh --with-local-pdfcore     # or: pip install -e ../pdfcore
```

Before releasing the redactor against a new pdfcore version, tag that
pdfcore release, bump the pin in `requirements.txt`, and let the build
script's test run pass (see below).

### Building the macOS app / DMG

See [`packaging/`](packaging/) for the `py2app` build used to produce the
`.app`/`.dmg` published on the Releases page. `packaging/build_app.sh`
builds in a fresh venv from the exact pinned `requirements.txt` (never from
a local editable pdfcore), and runs the test suite there before building.

## Architecture

The app itself is `redactor.py`. The code it shares with the PDF Editor app
lives in [pdfcore](https://github.com/DevTamer/pdfcore). Anything that
decides what happens to a document's content (redaction, scrubbing, saving)
stays in `redactor.py`. That way a change to pdfcore made for the editor
can't weaken this app's guarantees.

In `redactor.py`:

- `RedactionModel` tracks pending redactions per page and runs
  search/apply/save. It builds on pdfcore's `DocumentSession`, which holds
  the open `fitz.Document`, the current page, and the in-memory undo/redo
  history (one full document snapshot per apply). No UI code.
- `CanvasController` handles drawing, selecting and removing redaction
  rectangles with the mouse. It builds on pdfcore's `PageView`, which shows
  the page on the Tk canvas and converts between screen pixels and PDF
  points.
- `RedactorApp` builds the Tk window, menus and sidebar and connects the
  pieces above.

From pdfcore:

- `PDFRenderer` renders pages to `PIL.Image`s with a small LRU cache.
- `CoordinateMapper` does the PDF-point ↔ canvas-pixel math, with no Tk
  dependency.
- `SnapshotHistory` is the undo/redo stack behind `DocumentSession`. It is
  memory-only by design and never writes to disk.
- `configure_bundled_tcl_tk()` points Tcl/Tk at the copy bundled inside the
  `.app`. It runs before `tkinter` is imported.

## Limitations

- The app is unsigned and not notarized — see the Gatekeeper workaround
  above. If this matters to you, PRs adding a signing/notarization CI step
  (given an Apple Developer account) are welcome.
- Redaction removes what's inside the marked rectangle on that page (text,
  vector art, and image pixel data). It's still your responsibility to mark
  every place the sensitive content appears — the tool doesn't infer that
  for you beyond exact text search matches.
