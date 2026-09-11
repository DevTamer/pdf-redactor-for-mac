"""Tests for PDFRenderer: rendering and its LRU page-image cache."""

from redactor import PDFRenderer, RENDER_DPI, CACHE_LIMIT
from conftest import PAGE_WIDTH, PAGE_HEIGHT


def test_render_page_returns_image_at_render_dpi(sample_doc):
    renderer = PDFRenderer()
    page = sample_doc[0]

    img = renderer.render_page(page, 0)

    expected_w = round(PAGE_WIDTH * RENDER_DPI / 72.0)
    expected_h = round(PAGE_HEIGHT * RENDER_DPI / 72.0)
    # PyMuPDF's pixmap sizing can be off by a pixel from naive rounding;
    # allow a small tolerance rather than pinning an exact pixel count.
    assert abs(img.width - expected_w) <= 1
    assert abs(img.height - expected_h) <= 1
    assert img.mode == "RGB"


def test_render_page_is_cached(sample_doc):
    renderer = PDFRenderer()
    page = sample_doc[0]

    first = renderer.render_page(page, 0)
    second = renderer.render_page(page, 0)

    assert first is second  # same cached object, not re-rendered


def test_cache_evicts_oldest_beyond_limit(sample_doc):
    renderer = PDFRenderer()
    # sample_doc only has 3 pages; render page 0 repeatedly under different
    # synthetic page_num keys to exercise the LRU eviction without needing a
    # CACHE_LIMIT-sized document.
    page = sample_doc[0]

    for page_num in range(CACHE_LIMIT + 2):
        renderer.render_page(page, page_num)

    assert len(renderer._cache) == CACHE_LIMIT
    # The earliest-inserted keys should have been evicted first.
    assert 0 not in renderer._cache
    assert 1 not in renderer._cache
    assert (CACHE_LIMIT + 1) in renderer._cache


def test_cache_move_to_end_on_hit_protects_from_eviction(sample_doc):
    renderer = PDFRenderer()
    page = sample_doc[0]

    for page_num in range(CACHE_LIMIT):
        renderer.render_page(page, page_num)
    # Touch page 0 so it becomes the most-recently-used entry.
    renderer.render_page(page, 0)
    # Push one more new entry in; without the touch, page 0 would be the
    # oldest and get evicted.
    renderer.render_page(page, CACHE_LIMIT)

    assert 0 in renderer._cache
    assert 1 not in renderer._cache


def test_invalidate_single_page(sample_doc):
    renderer = PDFRenderer()
    page = sample_doc[0]
    renderer.render_page(page, 0)
    renderer.render_page(page, 1)

    renderer.invalidate(0)

    assert 0 not in renderer._cache
    assert 1 in renderer._cache


def test_invalidate_all_pages(sample_doc):
    renderer = PDFRenderer()
    page = sample_doc[0]
    renderer.render_page(page, 0)
    renderer.render_page(page, 1)

    renderer.invalidate()

    assert len(renderer._cache) == 0
