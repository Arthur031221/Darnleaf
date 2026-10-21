"""Optional text reading. Uses Tesseract when it is on PATH, otherwise RapidOCR if installed."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium

from . import imaging, signature

OcrFn = Callable[[np.ndarray], str]


def available() -> str | None:
    """Name of the OCR engine that would run, or None."""
    if shutil.which("tesseract"):
        return "tesseract"
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except ImportError:
        return None
    return "rapidocr"


def engine() -> OcrFn | None:
    name = available()
    if name == "tesseract":
        return _tesseract
    if name == "rapidocr":
        from rapidocr_onnxruntime import RapidOCR

        reader = RapidOCR()

        def read(gray: np.ndarray) -> str:
            result, _ = reader(gray)
            return " ".join(line[1] for line in result or [])

        return read
    return None


def _tesseract(gray: np.ndarray) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "page.png"
        cv2.imwrite(str(path), gray)
        done = subprocess.run(["tesseract", str(path), "stdout", "--psm", "3"], capture_output=True, text=True, timeout=120, check=False)
        return done.stdout


def embedded_text(pdf: Path) -> list[frozenset[str]]:
    """Words already in the PDF's text layer, one set per page."""
    with imaging.PDFIUM:
        doc = pdfium.PdfDocument(str(pdf))
        try:
            return [signature.tokens_from_text(page.get_textpage().get_text_range()) for page in doc]
        finally:
            doc.close()


class TextProvider:
    """Lazy word sets for original pages and rescans. OCR runs only for pages the matcher asks about."""

    def __init__(self, pdf: Path, pages: list[signature.Signature], rescans: list[signature.Signature], read: OcrFn | None):
        self._embedded = embedded_text(pdf)
        self._pages, self._rescans, self._read = pages, rescans, read
        self._cache: dict[tuple, frozenset[str]] = {}

    def __call__(self, kind: str, index: int, quarter: int = 0) -> frozenset[str]:
        if kind == "page" and len(self._embedded[index]) >= 12:
            return self._embedded[index]
        if self._read is None:
            return frozenset()
        key = (kind, index, quarter if kind == "rescan" else 0)
        if key not in self._cache:
            gray = (self._pages if kind == "page" else self._rescans)[index].gray
            if kind == "rescan" and quarter:
                gray = np.ascontiguousarray(np.rot90(gray, -quarter))
            self._cache[key] = signature.tokens_from_text(self._read(gray))
        return self._cache[key]
