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

The automated suite (`tests/`) covers the redaction model, PDF rendering
cache, and coordinate math — everything that doesn't require an actual
on-screen window. It does **not** exercise the GUI itself (clicking,
dragging, dialogs); see [`docs/MANUAL_TESTING.md`](docs/MANUAL_TESTING.md)
for a checklist to run the real app through its paces by hand before a
release.

### Building the macOS app / DMG

See [`packaging/`](packaging/) for the `py2app` build used to produce the
`.app`/`.dmg` published on the Releases page.

## Architecture

Everything lives in `redactor.py`, split into focused pieces:

- `RedactionModel` — owns the open `fitz.Document`, tracks pending
  redactions per page, runs search/apply/save, and keeps the in-memory
  undo/redo history (a stack of full document snapshots, one per apply).
  No UI code.
- `PDFRenderer` — renders pages to `PIL.Image`s with a small LRU cache.
- `CoordinateMapper` — pure PDF-point ↔ canvas-pixel math, with no Tk
  dependency (this is what makes it unit-testable in the first place).
- `CanvasController` — wires up Tk canvas mouse events (draw/select/remove
  rectangles) and delegates coordinate math to `CoordinateMapper`.
- `RedactorApp` — builds the Tk window/menus/sidebar and glues the above
  together.

## Limitations

- The app is unsigned and not notarized — see the Gatekeeper workaround
  above. If this matters to you, PRs adding a signing/notarization CI step
  (given an Apple Developer account) are welcome.
- Redaction removes what's inside the marked rectangle on that page (text,
  vector art, and image pixel data). It's still your responsibility to mark
  every place the sensitive content appears — the tool doesn't infer that
  for you beyond exact text search matches.
