"""Regression tests for RedactionModel._snap_to_text_lines.

PyMuPDF's apply_redactions() removes a whole text line if a redaction
rectangle merely touches its bounding box — with tightly-spaced lines, a
hand-drawn rectangle that's a few points too tall grazes a neighboring
line and wipes it completely, even though the user only meant to redact
the line they dragged over. RedactionModel snaps a rectangle's vertical
extent to the line(s) it substantially covers before handing it to
PyMuPDF, specifically to prevent that.
"""

import fitz
import pytest

from redactor import RedactionModel, RedactionRect, LINE_OVERLAP_THRESHOLD


TIGHT_LINE_SPACING = 20  # points; deliberately tight, like real single-spaced body text


def _three_line_doc(path):
    doc = fitz.open()
    page = doc.new_page(width=500, height=600)
    for i, line in enumerate(["Line one alpha", "Line two beta", "Line three gamma"]):
        page.insert_text((50, 100 + i * TIGHT_LINE_SPACING), line, fontsize=14)
    doc.save(str(path))
    doc.close()


def test_sloppy_manual_rect_does_not_blank_neighboring_lines(tmp_path):
    """The exact bug report: redacting one line with a hand-drawn
    rectangle that has a few points of vertical slop must not also erase
    the lines directly above/below it."""
    path = tmp_path / "lines.pdf"
    _three_line_doc(path)

    model = RedactionModel()
    model.open_document(str(path))
    try:
        tight = model.get_page(0).search_for("Line two beta")[0]
        # A few points of slop on every side — well within normal
        # mouse-drawn imprecision, especially with lines this close.
        sloppy = (tight.x0 - 3, tight.y0 - 6, tight.x1 + 3, tight.y1 + 6)
        model.add_redaction(RedactionRect.create(0, sloppy, "manual"))

        count = model.apply_redactions()

        assert count == 1
        text = model.get_page(0).get_text()
        assert "Line one alpha" in text
        assert "Line three gamma" in text
        assert "Line two beta" not in text
    finally:
        model.close_document()


def test_deliberately_multiline_rect_redacts_all_covered_lines(tmp_path):
    """A rectangle that's genuinely drawn across several lines (a
    paragraph redaction) should still take all of them out — the fix
    must not make multi-line redaction impossible."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=600)
    for i, line in enumerate(["Para line one", "Para line two", "Para line three",
                               "Untouched footer"]):
        page.insert_text((50, 100 + i * TIGHT_LINE_SPACING), line, fontsize=14)
    path = tmp_path / "paragraph.pdf"
    doc.save(str(path))
    doc.close()

    model = RedactionModel()
    model.open_document(str(path))
    try:
        l1 = model.get_page(0).search_for("Para line one")[0]
        l3 = model.get_page(0).search_for("Para line three")[0]
        rect = (min(l1.x0, l3.x0), l1.y0, max(l1.x1, l3.x1) + 20, l3.y1)
        model.add_redaction(RedactionRect.create(0, rect, "manual"))

        model.apply_redactions()

        text = model.get_page(0).get_text()
        assert "Para line one" not in text
        assert "Para line two" not in text
        assert "Para line three" not in text
        assert "Untouched footer" in text
    finally:
        model.close_document()


def test_partial_word_horizontal_redaction_still_precise(tmp_path):
    """Horizontal extent must stay exactly as drawn (only the vertical
    extent is snapped), so masking part of a word — e.g. only the last
    few digits of an ID on the same line as other text — still works."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=600)
    page.insert_text((50, 100), "SSN 123-45-6789 end", fontsize=14)
    path = tmp_path / "partial.pdf"
    doc.save(str(path))
    doc.close()

    model = RedactionModel()
    model.open_document(str(path))
    try:
        full = model.get_page(0).search_for("123-45-6789")[0]
        # Only the right ~40% of the number, full line height.
        right_part = (full.x0 + (full.x1 - full.x0) * 0.6, full.y0, full.x1, full.y1)
        model.add_redaction(RedactionRect.create(0, right_part, "manual"))

        model.apply_redactions()

        text = model.get_page(0).get_text()
        assert "SSN" in text
        assert "end" in text
        assert "123-45-6789" not in text
    finally:
        model.close_document()


def test_rect_over_non_text_area_is_unaffected(tmp_path):
    """A redaction rectangle with nothing underneath (blank space / an
    image, no text lines at all on the page) should pass through as
    drawn, not be discarded or altered."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=600)  # no text at all
    path = tmp_path / "blank.pdf"
    doc.save(str(path))
    doc.close()

    model = RedactionModel()
    model.open_document(str(path))
    try:
        rect = (50, 50, 150, 100)
        model.add_redaction(RedactionRect.create(0, rect, "manual"))

        # Should apply cleanly (no text to remove, but shouldn't error,
        # and the annotation/graphics redaction still happens over the
        # originally-drawn area).
        count = model.apply_redactions()

        assert count == 1
    finally:
        model.close_document()


def test_snap_to_text_lines_respects_overlap_threshold():
    """Unit-level check of the snapping function's threshold boundary,
    independent of a real document."""
    line_bboxes = [(0, 100, 200, 120)]  # one 20pt-tall line

    # Rect overlapping >= LINE_OVERLAP_THRESHOLD of the line's height:
    # gets snapped to the line's exact bbox.
    heavily_overlapping = fitz.Rect(10, 105, 190, 125)  # 15/20 = 75% overlap
    snapped = RedactionModel._snap_to_text_lines(heavily_overlapping, line_bboxes)
    assert (snapped.y0, snapped.y1) == (100, 120)
    # Horizontal extent untouched.
    assert (snapped.x0, snapped.x1) == (10, 190)

    # Rect overlapping well under the threshold: left as drawn.
    barely_touching = fitz.Rect(10, 118, 190, 140)  # 2/20 = 10% overlap
    unsnapped = RedactionModel._snap_to_text_lines(barely_touching, line_bboxes)
    assert (unsnapped.y0, unsnapped.y1) == (118, 140)
