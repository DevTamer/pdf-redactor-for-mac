# Manual GUI testing checklist

The automated `pytest` suite covers `RedactionModel`, `PDFRenderer`, and
`CoordinateMapper` — the logic that doesn't need a live window. It does not,
and cannot, drive real Tk widgets (clicks, drags, dialogs). Run this
checklist by hand against the actual app before cutting a release or after
any change that touches `CanvasController` / `RedactorApp`.

You'll need at least one real (non-sensitive) test PDF with a few pages and
some repeated text on it — e.g. print any document to PDF, or reuse a public
sample PDF.

## Setup

- [ ] `source venv/bin/activate && python redactor.py` launches without
      errors and shows the main window (toolbar, canvas, sidebar).

## Opening & navigation

- [ ] **File → Open…** (and `Cmd+O`) opens a file picker; selecting a PDF
      loads it and renders page 1.
- [ ] Page label reads `Page 1 / N` for an N-page document.
- [ ] `◀` / `▶` buttons move between pages and stay disabled at the first
      / last page respectively.
- [ ] "Go to:" entry + Enter jumps to a valid page number (1-indexed).
- [ ] Entering an out-of-range or non-numeric page number shows a warning
      dialog and does not change the current page.
- [ ] Resizing the window re-fits the page to the new width (give it a
      moment — resize is debounced).
- [ ] Mouse wheel scrolls the page vertically.

## Manual rectangle redaction

- [ ] Click-drag on the page draws a dashed selection rectangle live.
- [ ] Releasing creates a solid red/hatched overlay and adds a row to
      "Pending Redactions" with the correct page number and coordinates.
- [ ] A tiny accidental click/drag (a few px) is ignored — no redaction is
      created.
- [ ] Right-click (or Control-click) on a pending overlay removes it, and
      the matching sidebar row disappears.
- [ ] Clicking a row in the sidebar list jumps to that page (if needed) and
      highlights the rectangle in blue on the canvas.
- [ ] On a page with closely-spaced single-line text, draw a rectangle
      loosely over one line (don't try to be pixel-precise, drag the way
      you naturally would) and Apply. Confirm the lines directly above and
      below survive — only your target line should be gone. Deliberately
      dragging a rectangle across several lines on purpose should still
      redact all of them.

## Search-based redaction

- [ ] Type a term that appears multiple times across multiple pages into
      **Search Text** and press **Find All** (or Enter). Status line reports
      the correct match/page counts.
- [ ] All matches appear as pending redactions in the sidebar, and the view
      jumps to the first page with a match.
- [ ] Searching a term with no matches shows "No matches found" and adds
      nothing.
- [ ] Searching with an empty box shows a prompt and adds nothing.

## Managing pending redactions

- [ ] "Remove Selected" removes only the selected row/rectangle.
- [ ] "Clear Page" removes only the current page's pending redactions.
- [ ] "Clear All" asks for confirmation, and on confirm clears every
      pending redaction across all pages.
- [ ] All the buttons above (and Apply) are disabled when there's nothing
      pending, and enabled again as soon as something is added.

## Apply

- [ ] **APPLY REDACTIONS** with nothing pending shows an informational
      dialog and does nothing.
- [ ] With redactions pending, it shows a confirmation dialog with the
      count/pages and a mention that it's undoable while the document
      stays open; **Cancel** applies nothing.
- [ ] Confirming applies: overlays are replaced by black boxes rendered
      into the page, pending list empties, status bar reflects "Applied N
      redaction(s)," and a new entry appears in the **History** panel.
- [ ] Zoom in / rescroll — the redacted area is genuinely black, no
      underlying text/image bleeds through at the edges.

## Undo / History

- [ ] Freshly opening a document shows exactly one **History** entry,
      "Original," and Undo/Redo are disabled.
- [ ] After applying, **Edit → Undo Apply** (`Cmd+Z`) restores the
      redacted content and moves the current-state marker back in the
      History list; Redo becomes enabled.
- [ ] **Edit → Redo Apply** (`Cmd+Shift+Z`) reapplies it; content is
      redacted again.
- [ ] Clicking an entry directly in the **History** list jumps straight to
      that state (try jumping back two applies, not just one).
- [ ] Undo past a point, then apply something new: the discarded "redo"
      entries disappear from the list (the new apply replaces them), not
      just get appended after.
- [ ] Undo/redo do not touch the current *pending* (not-yet-applied)
      redactions list — only applied history.
- [ ] Undo/Redo/History are disabled/empty again immediately after
      **Close Document**, and a freshly opened document doesn't carry over
      history from whatever was open before.
- [ ] **Save Redacted As…** after an Undo saves the *current* (reverted)
      state — open the saved file and confirm the content you undid back
      to is present, and that nothing about the discarded redo branch
      leaked into the file.

## Save

- [ ] **Save Redacted As…** (`Cmd+S`) with pending (unapplied) redactions
      shows the Yes/No/Cancel prompt; each of the three choices does what
      it says (apply-then-save / save-as-is / abort back to the window).
- [ ] Default filename suggested is `<original>_redacted.pdf` in the
      original file's folder.
- [ ] After saving, open the **saved** file (a different file, not the one
      still open in the app) in Preview.app (or another PDF viewer) and:
  - [ ] The redacted areas are opaque black with nothing visible under
        zoom.
  - [ ] `Cmd+F` search in Preview for the redacted text finds **nothing**.
  - [ ] Select-all + copy from a redacted area yields no hidden text.
  - [ ] Content on *un*redacted parts of the document is untouched.

## Closing / edge cases

- [ ] **Close Document** (`Cmd+W`) with pending redactions asks to discard;
      declining keeps the document and its pending redactions open.
- [ ] Opening a second PDF while one is already open replaces it cleanly
      (no stale overlays/pending list from the previous document).
- [ ] Opening a non-PDF or corrupt file shows an error dialog instead of
      crashing.
