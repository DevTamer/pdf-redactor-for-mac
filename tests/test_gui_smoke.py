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
from conftest import PAGE_WIDTH  # noqa: E402


def _widget_state(widget) -> str:
    """ttk's widget["state"] returns a Tcl object, not a plain str."""
    return str(widget["state"])


@pytest.fixture(autouse=True)
def no_real_dialogs(monkeypatch):
    """A real dialog would block the run waiting for a click (on the
    screen of whoever runs the tests). Any dialog a test doesn't expect,
    by monkeypatching it again, fails the test instead."""
    def unexpected(name):
        def fail(*args, **kwargs):
            raise AssertionError(f"unexpected dialog {name}: {args} {kwargs}")
        return fail
    for name in ("showinfo", "showwarning", "showerror", "askyesno",
                 "askyesnocancel", "askokcancel", "askquestion"):
        monkeypatch.setattr(redactor.messagebox, name, unexpected(name))
    for name in ("askopenfilename", "asksaveasfilename"):
        monkeypatch.setattr(redactor.filedialog, name, unexpected(name))


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
    try:
        instance.root.destroy()
    except redactor.tk.TclError:
        pass   # the test quit the app


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


# -- Drawing on the canvas (exercises pdfcore's PageView mapping) -------------

class _MouseEvent:
    def __init__(self, x, y):
        self.x, self.y = x, y


def _open_in_app(app, path, fit_width=600):
    app.model.open_document(str(path))
    app.renderer.invalidate()
    app._update_redaction_list()
    app._update_history_list()
    # A fixed fit width makes the canvas<->PDF scale deterministic.
    app.controller.display_page(0, fit_width=fit_width)
    assert app.canvas.canvasx(0) == 0 and app.canvas.canvasy(0) == 0


def _drag(controller, x0, y0, x1, y1):
    controller._on_press(_MouseEvent(x0, y0))
    controller._on_drag(_MouseEvent((x0 + x1) / 2, (y0 + y1) / 2))
    controller._on_drag(_MouseEvent(x1, y1))
    controller._on_release(_MouseEvent(x1, y1))


def _expected_scale(fit_width):
    """Canvas pixels per PDF point for a page shown ``fit_width`` px wide,
    worked out from the page size alone (not from the code under test), so
    a scaling bug in the mapper can't cancel itself out."""
    return fit_width / PAGE_WIDTH


def test_drawn_rectangle_redacts_exactly_the_text_under_it(app, sample_pdf_path):
    _open_in_app(app, sample_pdf_path, fit_width=600)
    ctrl = app.controller
    scale = _expected_scale(600)

    # Where "John Doe" is on the page, in PDF points, then on screen.
    target = app.model.get_page(0).search_for("John Doe")[0]
    x0, y0, x1, y1 = (v * scale for v in target)

    # Drag over it (bottom-right to top-left, to check normalisation too).
    _drag(ctrl, x1 + 1, y1 + 1, x0 - 1, y0 - 1)

    pending = app.model.all_redactions()
    assert len(pending) == 1
    assert pending[0].source == "manual"
    px0, py0, px1, py1 = pending[0].pdf_rect
    tolerance = 2 / scale  # 1px of slop each side, plus rounding, in points
    assert px0 == pytest.approx(target.x0, abs=tolerance)
    assert py0 == pytest.approx(target.y0, abs=tolerance)
    assert px1 == pytest.approx(target.x1, abs=tolerance)
    assert py1 == pytest.approx(target.y1, abs=tolerance)
    assert len(app.canvas.find_withtag("redaction")) == 1
    assert "1 pending redaction" in app.status_label["text"]

    app._do_apply()

    text = app.model.get_page(0).get_text()
    assert "John Doe" not in text
    assert "CONFIDENTIAL" in text
    assert "123-45-6789" in text


def test_drawing_while_scrolled_maps_to_the_right_place(app, sample_pdf_path):
    """Mouse events arrive in window coordinates; once the canvas is
    scrolled they must be offset by the scroll position."""
    _open_in_app(app, sample_pdf_path, fit_width=1200)  # page taller than view
    ctrl = app.controller
    scale = _expected_scale(1200)
    app.canvas.configure(height=300)
    app.root.update_idletasks()
    app.canvas.yview_moveto(0.1)
    app.root.update_idletasks()
    scroll_y = app.canvas.canvasy(0)
    assert scroll_y > 0, "canvas didn't scroll; test setup is broken"

    target = app.model.get_page(0).search_for("John Doe")[0]
    x0, y0, x1, y1 = (v * scale for v in target)
    # Window coordinates = canvas coordinates minus the scroll offset.
    _drag(ctrl, x0 - 1, y0 - 1 - scroll_y, x1 + 1, y1 + 1 - scroll_y)

    px0, py0, px1, py1 = app.model.all_redactions()[0].pdf_rect
    tolerance = 2 / scale
    assert py0 == pytest.approx(target.y0, abs=tolerance)
    assert py1 == pytest.approx(target.y1, abs=tolerance)

    app._do_apply()
    assert "John Doe" not in app.model.get_page(0).get_text()


def test_tiny_drag_is_ignored(app, sample_pdf_path):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 100, 100, 102, 102)
    assert not app.model.has_pending()
    assert app.canvas.find_withtag("temp_drawing") == ()


def test_overlays_are_redrawn_when_page_is_redisplayed(app, sample_pdf_path):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 50, 50, 200, 120)
    rid = app.model.all_redactions()[0].id

    # Re-displaying at a different size clears the canvas and redraws.
    app.controller.display_page(0, fit_width=900)

    items = app.canvas.find_withtag("redaction")
    assert len(items) == 1
    # Drawn at the new scale: same PDF rect, 1.5x the canvas size.
    cx0, cy0, cx1, cy1 = app.canvas.coords(items[0])
    expected = [v * app.controller.mapper.total_scale
                for v in app.model.all_redactions()[0].pdf_rect]
    assert [cx0, cy0, cx1, cy1] == pytest.approx(expected, abs=0.5)
    # Selection still works against the rebuilt id mapping.
    app.controller.select_redaction(rid)
    assert app.canvas.itemcget(items[0], "outline") == redactor.SELECTED_OUTLINE


def test_right_click_removes_the_redaction_under_the_pointer(app, sample_pdf_path):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 50, 50, 200, 120)
    assert app.model.has_pending()

    app.controller._on_right_click(_MouseEvent(120, 80))

    assert not app.model.has_pending()
    assert app.canvas.find_withtag("redaction") == ()


def test_failed_open_shows_error_and_keeps_document(app, sample_pdf_path,
                                                    tmp_path, monkeypatch):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 50, 50, 200, 120)
    junk = tmp_path / "junk.pdf"
    junk.write_bytes(b"not a pdf")
    errors = []
    monkeypatch.setattr(redactor.filedialog, "askopenfilename",
                        lambda **k: str(junk))
    monkeypatch.setattr(redactor.messagebox, "showerror",
                        lambda title, message: errors.append(message))
    # Opening asks about the pending mark first; carry on without saving.
    monkeypatch.setattr(redactor.messagebox, "askyesnocancel",
                        lambda *a, **k: False)

    app._on_open()

    assert errors and "Could not open PDF" in errors[0]
    assert app.model.file_path == str(sample_pdf_path)
    assert app.model.has_pending()


# -- Quitting, closing and opening ask about unsaved work ----------------------

def _root_exists(app):
    try:
        return bool(app.root.winfo_exists())
    except redactor.tk.TclError:
        return False


def _answer(monkeypatch, answer):
    asked = []
    monkeypatch.setattr(redactor.messagebox, "askyesnocancel",
                        lambda title, message: asked.append(message) or answer)
    return asked


def test_quit_handlers_are_registered(app):
    commands = app.root.tk.splitlist(app.root.tk.call("info", "commands",
                                                      "::tk::mac::Quit"))
    assert commands == ("::tk::mac::Quit",)
    assert "_on_quit" in app.root.protocol("WM_DELETE_WINDOW")


def test_quit_with_nothing_unsaved_just_quits(app, sample_pdf_path):
    _open_in_app(app, sample_pdf_path)
    app._on_quit()
    assert not _root_exists(app)


def test_quit_with_pending_marks_asks_and_cancel_keeps_running(
        app, sample_pdf_path, monkeypatch):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 50, 50, 200, 120)
    asked = _answer(monkeypatch, None)          # Cancel
    app._on_quit()
    assert asked and "haven't been applied" in asked[0]
    assert _root_exists(app) and app.model.has_pending()

    _answer(monkeypatch, False)                 # Don't save
    app._on_quit()
    assert not _root_exists(app)


def test_quit_after_applying_without_saving_asks(app, sample_pdf_path, monkeypatch):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 50, 50, 200, 120)
    app._do_apply()
    assert not app.model.has_pending()
    asked = _answer(monkeypatch, None)
    app._on_quit()
    assert asked and "haven't been saved" in asked[0]
    assert _root_exists(app)


def test_choosing_save_when_quitting_saves_then_quits(app, sample_pdf_path,
                                                      tmp_path, monkeypatch):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 50, 50, 200, 120)
    app._do_apply()
    out = tmp_path / "out.pdf"
    _answer(monkeypatch, True)
    monkeypatch.setattr(redactor.filedialog, "asksaveasfilename",
                        lambda **k: str(out))
    monkeypatch.setattr(redactor.messagebox, "showinfo", lambda *a, **k: None)
    app._on_quit()
    assert out.exists() and not _root_exists(app)


def test_cancelling_the_save_dialog_cancels_quitting(app, sample_pdf_path,
                                                     monkeypatch):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 50, 50, 200, 120)
    app._do_apply()
    _answer(monkeypatch, True)
    monkeypatch.setattr(redactor.filedialog, "asksaveasfilename", lambda **k: "")
    app._on_quit()
    assert _root_exists(app)


def test_saved_work_doesnt_ask(app, sample_pdf_path, tmp_path, monkeypatch):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 50, 50, 200, 120)
    app._do_apply()
    monkeypatch.setattr(redactor.filedialog, "asksaveasfilename",
                        lambda **k: str(tmp_path / "out.pdf"))
    monkeypatch.setattr(redactor.messagebox, "showinfo", lambda *a, **k: None)
    assert app._on_save()
    assert not app.model.has_unsaved_work
    app._on_quit()                              # no dialog expected
    assert not _root_exists(app)


def test_opening_another_pdf_asks_first(app, sample_pdf_path, monkeypatch):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 50, 50, 200, 120)
    asked = _answer(monkeypatch, None)
    app._on_open()                              # no file dialog: cancelled first
    assert asked and app.model.has_pending()


def test_close_document_after_applying_asks(app, sample_pdf_path, monkeypatch):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 50, 50, 200, 120)
    app._do_apply()
    asked = _answer(monkeypatch, None)
    app._on_close_doc()
    assert asked and app.model.doc is not None


def test_a_failed_save_cancels_quitting(app, sample_pdf_path, tmp_path, monkeypatch):
    _open_in_app(app, sample_pdf_path)
    _drag(app.controller, 50, 50, 200, 120)
    app._do_apply()
    _answer(monkeypatch, True)
    monkeypatch.setattr(redactor.filedialog, "asksaveasfilename",
                        lambda **k: str(tmp_path / "missing-folder" / "out.pdf"))
    errors = []
    monkeypatch.setattr(redactor.messagebox, "showerror",
                        lambda title, message: errors.append(message))
    app._on_quit()
    assert errors and _root_exists(app)
