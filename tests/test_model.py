"""Tests for RedactionModel: document lifecycle, redaction bookkeeping,
search, apply, and save.
"""

import fitz
import pytest

from redactor import RedactionModel, RedactionRect
from conftest import PAGE_TEXTS


# -- Document lifecycle -------------------------------------------------------

def test_open_document_loads_pages(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        assert model.page_count == len(PAGE_TEXTS)
        assert model.file_path == str(sample_pdf_path)
        assert model.current_page == 0
        assert not model.has_pending()
        assert not model.is_applied
    finally:
        model.close_document()


def test_open_document_resets_prior_state(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    model.add_redaction(RedactionRect.create(0, (0, 0, 10, 10), "manual"))
    model.current_page = 2

    model.open_document(str(sample_pdf_path))  # reopen same doc

    assert model.current_page == 0
    assert not model.has_pending()


def test_close_document_clears_state(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    model.add_redaction(RedactionRect.create(0, (0, 0, 10, 10), "manual"))

    model.close_document()

    assert model.doc is None
    assert model.file_path is None
    assert model.page_count == 0
    assert not model.has_pending()
    # Closing with no open document must not raise.
    model.close_document()


# -- Redaction bookkeeping -----------------------------------------------------

def test_add_and_get_page_redactions():
    model = RedactionModel()
    r1 = RedactionRect.create(0, (0, 0, 10, 10), "manual")
    r2 = RedactionRect.create(0, (5, 5, 20, 20), "manual")
    r3 = RedactionRect.create(1, (0, 0, 10, 10), "manual")
    model.add_redaction(r1)
    model.add_redaction(r2)
    model.add_redaction(r3)

    assert model.get_page_redactions(0) == [r1, r2]
    assert model.get_page_redactions(1) == [r3]
    assert model.get_page_redactions(2) == []
    assert model.redaction_count() == 3
    assert model.has_pending()


def test_all_redactions_ordered_by_page():
    model = RedactionModel()
    r_p1 = RedactionRect.create(1, (0, 0, 10, 10), "manual")
    r_p0 = RedactionRect.create(0, (0, 0, 10, 10), "manual")
    model.add_redaction(r_p1)
    model.add_redaction(r_p0)

    assert model.all_redactions() == [r_p0, r_p1]


def test_remove_redaction_by_id():
    model = RedactionModel()
    r1 = RedactionRect.create(0, (0, 0, 10, 10), "manual")
    r2 = RedactionRect.create(0, (5, 5, 20, 20), "manual")
    model.add_redaction(r1)
    model.add_redaction(r2)

    removed = model.remove_redaction(r1.id)

    assert removed is r1
    assert model.get_page_redactions(0) == [r2]


def test_remove_redaction_drops_empty_page_entry():
    model = RedactionModel()
    r1 = RedactionRect.create(0, (0, 0, 10, 10), "manual")
    model.add_redaction(r1)

    model.remove_redaction(r1.id)

    assert 0 not in model.pending


def test_remove_unknown_redaction_returns_none():
    model = RedactionModel()
    model.add_redaction(RedactionRect.create(0, (0, 0, 10, 10), "manual"))

    assert model.remove_redaction("does-not-exist") is None
    assert model.redaction_count() == 1


def test_clear_page_redactions():
    model = RedactionModel()
    model.add_redaction(RedactionRect.create(0, (0, 0, 10, 10), "manual"))
    model.add_redaction(RedactionRect.create(0, (5, 5, 20, 20), "manual"))
    model.add_redaction(RedactionRect.create(1, (0, 0, 10, 10), "manual"))

    removed = model.clear_page_redactions(0)

    assert removed == 2
    assert model.get_page_redactions(0) == []
    assert model.redaction_count() == 1


def test_clear_page_redactions_on_empty_page_returns_zero():
    model = RedactionModel()
    assert model.clear_page_redactions(5) == 0


def test_clear_all_redactions():
    model = RedactionModel()
    model.add_redaction(RedactionRect.create(0, (0, 0, 10, 10), "manual"))
    model.add_redaction(RedactionRect.create(1, (0, 0, 10, 10), "manual"))

    removed = model.clear_all_redactions()

    assert removed == 2
    assert not model.has_pending()


# -- Search ---------------------------------------------------------------

def test_search_text_finds_expected_pages(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        results = model.search_text("CONFIDENTIAL")
        assert set(results.keys()) == {0, 1}
        assert len(results[0]) >= 1
        assert len(results[1]) >= 1
    finally:
        model.close_document()


def test_search_text_no_matches(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        results = model.search_text("no-such-term-anywhere")
        assert results == {}
    finally:
        model.close_document()


def test_search_text_empty_string_returns_no_matches(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        results = model.search_text("")
        assert results == {}
    finally:
        model.close_document()


# -- Apply & save -----------------------------------------------------------

def test_apply_redactions_removes_target_text(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        results = model.search_text("John Doe")
        assert results, "expected the sample fixture to contain 'John Doe'"
        for page_num, quads in results.items():
            for q in quads:
                rect = q.rect
                model.add_redaction(RedactionRect.create(
                    page_num, (rect.x0, rect.y0, rect.x1, rect.y1),
                    "search", search_term="John Doe"))

        count = model.apply_redactions()

        assert count >= 1
        assert not model.has_pending()
        assert model.is_applied
        # The text must actually be gone from the page content, not just
        # visually covered.
        assert "John Doe" not in model.get_page(0).get_text()
    finally:
        model.close_document()


def test_apply_redactions_with_nothing_pending_is_a_noop(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        count = model.apply_redactions()
        assert count == 0
        assert model.is_applied
    finally:
        model.close_document()


def test_save_document_persists_redactions(sample_pdf_path, tmp_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        results = model.search_text("Falcon")
        for page_num, quads in results.items():
            for q in quads:
                rect = q.rect
                model.add_redaction(RedactionRect.create(
                    page_num, (rect.x0, rect.y0, rect.x1, rect.y1),
                    "search", search_term="Falcon"))
        model.apply_redactions()

        out_path = tmp_path / "redacted.pdf"
        model.save_document(str(out_path))
    finally:
        model.close_document()

    assert out_path.exists()
    reopened = fitz.open(str(out_path))
    try:
        all_text = "".join(p.get_text() for p in reopened)
        assert "Falcon" not in all_text
        # Unrelated content on other pages must survive untouched.
        assert "John Doe" in all_text
    finally:
        reopened.close()
