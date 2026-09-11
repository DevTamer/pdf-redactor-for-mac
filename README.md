# PDF Redactor

A small macOS app for **true PDF redaction** — permanently removing sensitive
text and image content from a PDF, not just drawing a black box over it.

Draw rectangles over content to remove, or search for text and redact every
match, then apply. The underlying text/graphics/image pixels are stripped
from the document (via [PyMuPDF](https://pymupdf.readthedocs.io/)'s redaction
+ scrub pipeline) before you save — so the "hidden" content can't be
recovered by copy-pasting, exporting, or looking at the raw file.

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

- **Draw a rectangle** on the page to mark that area for redaction.
- **Search Text** finds every occurrence of a term on every page and marks
  each match automatically.
- Marked areas show as pending (semi-transparent red) until you press
  **APPLY REDACTIONS** — at that point PyMuPDF permanently removes the text,
  vector graphics, and image pixels under each marked rectangle and draws a
  black box in their place. **This step is irreversible** in the open
  document (nothing is written to disk yet).
- **Save Redacted As…** writes the result to a new file. Saving also runs
  `scrub()` (strips metadata, embedded files, JavaScript, etc.) and garbage
  collection so leftover unreferenced objects don't carry redacted content
  along with them. Your original file is never modified.

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
  redactions per page, runs search/apply/save. No UI code.
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
