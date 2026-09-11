"""Tests for CoordinateMapper: pure PDF <-> canvas coordinate math.

No Tk widgets involved, so these run anywhere (including headless/sandboxed
environments where a real tkinter.Canvas can't be created).
"""

import pytest

from redactor import CoordinateMapper, RENDER_DPI


def test_pdf_to_canvas_scales_by_total_scale():
    mapper = CoordinateMapper(total_scale=2.0)
    assert mapper.pdf_to_canvas(10, 20) == (20.0, 40.0)


def test_canvas_to_pdf_scales_by_total_scale():
    mapper = CoordinateMapper(total_scale=2.0)
    assert mapper.canvas_to_pdf(20, 40) == (10.0, 20.0)


def test_canvas_to_pdf_zero_scale_guard():
    mapper = CoordinateMapper(total_scale=0.0)
    assert mapper.canvas_to_pdf(100, 100) == (0.0, 0.0)


@pytest.mark.parametrize("scale", [0.5, 1.0, 2.08333, 3.0])
def test_round_trip_is_identity(scale):
    mapper = CoordinateMapper(total_scale=scale)
    px, py = 123.4, 56.7
    cx, cy = mapper.pdf_to_canvas(px, py)
    back_px, back_py = mapper.canvas_to_pdf(cx, cy)
    assert back_px == pytest.approx(px)
    assert back_py == pytest.approx(py)


def test_render_scale_matches_dpi_constant():
    assert CoordinateMapper.render_scale() == RENDER_DPI / 72.0


def test_compute_total_scale_combines_render_and_display_scale():
    # A 300 DPI page image (2x render-only scale relative to 150 DPI images
    # elsewhere in the app) fit into a 150px-wide canvas from a 300px-wide
    # source image should halve on top of the render scale.
    render_scale = CoordinateMapper.render_scale()
    total = CoordinateMapper.compute_total_scale(image_width=300, fit_width=150)
    assert total == pytest.approx(render_scale * 0.5)
