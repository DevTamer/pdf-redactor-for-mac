"""End-to-end smoke test driving the real RedactorApp through actual Tk
widgets: open -> search-redact -> apply -> undo -> redo -> click-to-jump.

Unlike the rest of the suite, this needs a real (if hidden/withdrawn) Tk
window, which requires a Tcl/Tk that actually works on this machine (see
setup.sh's comments on Apple's system Python vs. Homebrew's python-tk) and
some kind of display session. It's valuable when it can run, but it's not
something every environment this project's tests might run in can be
expected to support, so it skips itself cleanly rather than failing when a
Tk root can't be created.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import redactor  # noqa: E402  (after sys.path setup above)


def _widget_state(widget) -> str:
    """ttk's widget["state"] returns a Tcl object, not a plain str."""
    return str(widget["state"])


@pytest.fixture
def app(sample_pdf_path):
    try:
        instance = redactor.RedactorApp()
    except Exception as exc:  # e.g. no working Tk / no display in this env
        pytest.skip(f"Tk isn't usable in this environment: {exc}")
        return
    instance.root.withdraw()
    yield instance
    instance.model.close_document()
    instance.root.destroy()


def test_open_populates_original_history_entry(app, sample_pdf_path):
    app.model.open_document(str(sample_pdf_path))
    app.renderer.invalidate()
    app._update_redaction_list()
    app._update_history_list()
    app._refresh_page()

    assert app.model.page_count == 3
    assert app.history_list.get(0, "end") == ("▸ Original",)
    assert _widget_state(app.undo_btn) == "disabled"
    assert _widget_state(app.redo_btn) == "disabled"


def test_search_apply_undo_redo_through_real_widgets(app, sample_pdf_path):
    app.model.open_document(str(sample_pdf_path))
    app.renderer.invalidate()
    app._update_redaction_list()
    app._update_history_list()
    app._refresh_page()

    # Search for real text via the real entry widget + handler.
    app.search_entry.insert(0, "John Doe")
    app._on_search()
    assert app.model.has_pending()

    # Apply via the real handler (as the APPLY REDACTIONS button would).
    app._do_apply()
    assert not app.model.has_pending()
    assert app.model.is_applied
    assert "John Doe" not in app.model.get_page(0).get_text()
    assert _widget_state(app.undo_btn) == "normal"
    assert _widget_state(app.redo_btn) == "disabled"
    assert app.edit_menu.entrycget("Undo Apply", "state") == "normal"

    # Undo via the real handler (as Cmd+Z would trigger).
    app._on_undo()
    assert not app.model.is_applied
    assert "John Doe" in app.model.get_page(0).get_text()
    assert _widget_state(app.undo_btn) == "disabled"
    assert _widget_state(app.redo_btn) == "normal"
    assert "Undo" in app.status_label["text"]

    # Redo.
    app._on_redo()
    assert app.model.is_applied
    assert "John Doe" not in app.model.get_page(0).get_text()
    assert "Redo" in app.status_label["text"]

    # Click-to-jump: select the "Original" row in the history list, as a
    # real click would, and confirm the handler reverts to it.
    app.history_list.selection_clear(0, "end")
    app.history_list.selection_set(0)
    app._on_history_select()
    assert app.model.history_index == 0
    assert "John Doe" in app.model.get_page(0).get_text()
    assert "Jumped to" in app.status_label["text"]


def test_closing_document_clears_history_list(app, sample_pdf_path):
    app.model.open_document(str(sample_pdf_path))
    app.renderer.invalidate()
    app._update_redaction_list()
    app._update_history_list()
    app._refresh_page()

    app._on_close_doc()

    assert app.history_list.size() == 0
    assert _widget_state(app.undo_btn) == "disabled"
