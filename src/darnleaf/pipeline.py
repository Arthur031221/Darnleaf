"""Glue between files and the matcher: build signatures and run a full match."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

import pypdfium2 as pdfium

from . import imaging, ocr, signature
from .imaging import Source
from .matcher import Cancelled, Proposal, match


def page_signatures(pdf: Path, progress: Callable[[str, int, int], None] | None = None, cancel: threading.Event | None = None) -> list[signature.Signature]:
    with imaging.PDFIUM:
        doc = pdfium.PdfDocument(str(pdf))
        total = len(doc)
    try:
        out = []
        for i in range(total):
            if cancel is not None and cancel.is_set():
                raise Cancelled
            with imaging.PDFIUM:
                img = imaging.render_page(doc[i], 1100 / max(doc[i].get_size()))
            out.append(signature.compute(imaging.to_work_gray(img)))
            if progress is not None:
                progress("pages", i + 1, total)
        return out
    finally:
        with imaging.PDFIUM:
            doc.close()


def rescan_signatures(sources: list[Source], progress: Callable[[str, int, int], None] | None = None) -> list[signature.Signature]:
    out = []
    for i, source in enumerate(sources):
        out.append(signature.compute(imaging.to_work_gray(source.load())))
        if progress is not None:
            progress("rescans", i + 1, len(sources))
    return out


def run(
    pdf: Path,
    sources: list[Source],
    progress: Callable[[str, int, int], None] | None = None,
    cancel: threading.Event | None = None,
    use_ocr: bool = False,
) -> list[Proposal]:
    pages = page_signatures(pdf, progress, cancel)
    rescans = rescan_signatures(sources, progress)
    text_for = ocr.TextProvider(pdf, pages, rescans, ocr.engine()) if use_ocr else None
    return match(rescans, pages, progress=(lambda d, t: progress("matching", d, t)) if progress else None, cancel=cancel, text_for=text_for)
