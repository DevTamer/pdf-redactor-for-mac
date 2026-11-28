"""Redacted PDFs must look right in Apple's PDF renderer (Preview,
Safari, Quick Look), not only in MuPDF.

PyMuPDF 1.24 rewrote page content during redaction in an order MuPDF
accepts but Apple's renderer reads as written, clipping much of the
remaining page away. These tests render with macOS's own engine (via the
built-in `sips` tool) and compare with MuPDF.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import redactor  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("sips") is None,
                                reason="needs macOS's sips")


def _apple_ink(path, tmp_path):
    """Dark pixels in Apple's rendering of page 1 (72 dpi)."""
    png = tmp_path / "apple.png"
    subprocess.run(["sips", "-s", "format", "png", str(path), "--out", str(png)],
                   check=True, capture_output=True)
    image = Image.open(png).convert("RGBA")
    page = Image.new("RGBA", image.size, "white")
    page.alpha_composite(image)
    return sum(1 for v in page.convert("L").getdata() if v < 128)


def _mupdf_ink(path):
    pix = pymupdf.open(str(path))[0].get_pixmap(dpi=72, colorspace=pymupdf.csGRAY)
    return sum(1 for v in pix.samples if v < 128)


def _browser_style_pdf(path):
    """A page laid out the way Chrome and Skia write PDFs: a top-level
    scale, then text blocks inside clipping rectangles given in the scaled
    coordinates."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((10, 10), "x", fontname="helv")
    font = page.get_fonts()[0][4]
    blocks = []
    for i, line in enumerate(("Invoice number 0025", "Date of issue September 20",
                              "Amount due 189.93 USD", "Thank you for your business")):
        y = 300 + i * 250
        blocks.append(
            f"q\n100 {y} 2000 200 re\nW* n\nq\n4.1666665 0 0 4.1666665 0 0 cm\n"
            f"BT\n/{font} 14 Tf\n1 0 0 -1 30 {(y + 120) / 4.1666665:.3f} Tm\n"
            f"({line}) Tj\nET\nQ\nQ\n")
    stream = ".24 0 0 -.24 0 792 cm\n" + "".join(blocks)
    doc.update_stream(page.get_contents()[0], stream.encode())
    doc.save(str(path))


def test_redacted_browser_style_pdf_looks_right_in_preview(tmp_path):
    source = tmp_path / "web.pdf"
    _browser_style_pdf(source)
    model = redactor.RedactionModel()
    model.open_document(str(source))
    for page_num, quads in model.search_text("September").items():
        for quad in quads:
            model.add_redaction(redactor.RedactionRect.create(
                page_num, tuple(quad.rect), "search", "September"))
    model.apply_redactions()
    out = tmp_path / "redacted.pdf"
    model.save_document(str(out))

    text = pymupdf.open(str(out))[0].get_text()
    assert "September" not in text and "Invoice number 0025" in text
    # Everything left shows in Apple's renderer much as in MuPDF.
    assert _apple_ink(out, tmp_path) == pytest.approx(_mupdf_ink(out), rel=0.25)
