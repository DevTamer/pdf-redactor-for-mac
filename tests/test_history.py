"""Tests for RedactionModel's session-scoped undo/redo history.

Each apply becomes one history entry holding a full snapshot of the
document. undo()/redo()/jump_to_history() swap the live document for an
earlier or later snapshot — this is the "Photoshop history palette"
feature, deliberately scoped to the current app session (see
HistoryEntry's docstring in redactor.py for why).
"""

import fitz
import pytest

from redactor import RedactionModel, RedactionRect, HISTORY_LIMIT


def _redact_term(model, term):
    """Helper: search for `term` and apply redactions on every match."""
    results = model.search_text(term)
    for page_num, quads in results.items():
        for q in quads:
            rect = q.rect
            model.add_redaction(RedactionRect.create(
                page_num, (rect.x0, rect.y0, rect.x1, rect.y1),
                "search", search_term=term))
    return model.apply_redactions()


# -- Baseline state -----------------------------------------------------------

def test_freshly_opened_document_has_one_history_entry(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        assert model.history_entries() == ["Original"]
        assert model.history_index == 0
        assert not model.can_undo()
        assert not model.can_redo()
        assert not model.is_applied
    finally:
        model.close_document()


# -- Undo / redo --------------------------------------------------------------

def test_apply_adds_history_entry_and_enables_undo(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        count = _redact_term(model, "John Doe")
        assert count >= 1

        expected_label = f"Applied {count} redaction{'s' if count != 1 else ''}"
        assert model.history_entries() == ["Original", expected_label]
        assert model.history_index == 1
        assert model.is_applied
        assert model.can_undo()
        assert not model.can_redo()
    finally:
        model.close_document()


def test_undo_restores_redacted_text(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        _redact_term(model, "John Doe")
        assert "John Doe" not in model.get_page(0).get_text()

        label = model.undo()

        assert label == "Original"
        assert "John Doe" in model.get_page(0).get_text()
        assert not model.is_applied
        assert model.can_redo()
        assert not model.can_undo()
    finally:
        model.close_document()


def test_redo_reapplies_the_redaction(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        _redact_term(model, "John Doe")
        model.undo()

        label = model.redo()

        assert label.startswith("Applied")
        assert "John Doe" not in model.get_page(0).get_text()
        assert model.is_applied
        assert not model.can_redo()
    finally:
        model.close_document()


def test_undo_with_nothing_to_undo_raises(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        with pytest.raises(ValueError):
            model.undo()
    finally:
        model.close_document()


def test_redo_with_nothing_to_redo_raises(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        with pytest.raises(ValueError):
            model.redo()
    finally:
        model.close_document()


def test_new_apply_after_undo_discards_redo_branch(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        _redact_term(model, "John Doe")   # entry 1
        model.undo()                       # back to entry 0
        _redact_term(model, "Falcon")      # branches: entry 1 becomes "Applied Falcon"

        assert not model.can_redo()
        assert len(model.history_entries()) == 2
        # The original "John Doe" apply is gone from history; that text is
        # back (we undid past it before branching), Falcon is redacted.
        text = model.get_page(0).get_text() + model.get_page(1).get_text()
        assert "John Doe" in text
        assert "Falcon" not in text
    finally:
        model.close_document()


# -- jump_to_history ------------------------------------------------------

def test_jump_to_history_arbitrary_entry(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        _redact_term(model, "John Doe")    # entry 1
        _redact_term(model, "Falcon")      # entry 2

        label = model.jump_to_history(0)

        assert label == "Original"
        assert model.history_index == 0
        text = model.get_page(0).get_text() + model.get_page(1).get_text()
        assert "John Doe" in text
        assert "Falcon" in text
    finally:
        model.close_document()


def test_jump_to_history_out_of_range_raises(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        with pytest.raises(IndexError):
            model.jump_to_history(5)
        with pytest.raises(IndexError):
            model.jump_to_history(-1)
    finally:
        model.close_document()


# -- Lifecycle interactions -------------------------------------------------

def test_opening_a_new_document_resets_history(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        _redact_term(model, "John Doe")
        assert len(model.history_entries()) == 2

        model.open_document(str(sample_pdf_path))  # reopen

        assert model.history_entries() == ["Original"]
        assert not model.can_undo()
    finally:
        model.close_document()


def test_close_document_clears_history(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    _redact_term(model, "John Doe")

    model.close_document()

    assert model.history_entries() == []
    assert model.history_index == -1


def test_undo_preserves_current_page_when_possible(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        _redact_term(model, "John Doe")
        model.current_page = 2

        model.undo()

        assert model.current_page == 2
    finally:
        model.close_document()


def test_save_after_undo_writes_the_reverted_state(sample_pdf_path, tmp_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        _redact_term(model, "John Doe")
        model.undo()

        out_path = tmp_path / "reverted.pdf"
        model.save_document(str(out_path))
    finally:
        model.close_document()

    reopened = fitz.open(str(out_path))
    try:
        assert "John Doe" in reopened[0].get_text()
    finally:
        reopened.close()


# -- History size cap -------------------------------------------------------

def test_history_is_capped_at_history_limit(sample_pdf_path):
    model = RedactionModel()
    model.open_document(str(sample_pdf_path))
    try:
        # One page has no redactable text of its own to exhaust, so
        # manually redact a tiny fixed rectangle repeatedly to generate
        # many history entries cheaply.
        for _ in range(HISTORY_LIMIT + 5):
            model.add_redaction(RedactionRect.create(
                2, (10, 10, 20, 20), "manual"))
            model.apply_redactions()

        assert len(model.history_entries()) == HISTORY_LIMIT
        assert model.history_index == HISTORY_LIMIT - 1
        # The oldest entries (including "Original") were dropped; undo
        # only goes as far back as what's left.
        assert model.history_entries()[0] != "Original"
    finally:
        model.close_document()
