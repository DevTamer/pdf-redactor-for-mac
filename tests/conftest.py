"""Shared pytest fixtures for the redactor test suite.

No binary PDF fixtures are committed to the repo (the project's .gitignore
excludes *.pdf, and it's cleaner to generate small, known-content PDFs on the
fly with the same PyMuPDF the app itself uses).
"""

import sys
from pathlib import Path

import fitz
import pytest

# Make redactor.py importable as `redactor` without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PAGE_WIDTH = 500
PAGE_HEIGHT = 600

# Known text placed on each page, at known positions, so tests can search for
# it and assert on exactly what apply_redactions removes.
PAGE_TEXTS = [
    "CONFIDENTIAL: John Doe, SSN 123-45-6789",
    "Second page — CONFIDENTIAL project codename Falcon",
    "Third page has no secrets on it at all.",
]


def _build_sample_pdf(path: Path) -> None:
    doc = fitz.open()
    for text in PAGE_TEXTS:
        page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_text((50, 100), text, fontsize=14)
    doc.save(str(path))
    doc.close()


@pytest.fixture
def sample_pdf_path(tmp_path) -> Path:
    """Path to a freshly written 3-page sample PDF with known text."""
    path = tmp_path / "sample.pdf"
    _build_sample_pdf(path)
    return path


@pytest.fixture
def sample_doc():
    """An open fitz.Document with the same content, for tests that don't
    need a real file on disk."""
    doc = fitz.open()
    for text in PAGE_TEXTS:
        page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_text((50, 100), text, fontsize=14)
    yield doc
    if not doc.is_closed:
        doc.close()
