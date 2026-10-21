"""Decide whether a PDF is safe to edit with this tool before any work is done."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pikepdf

from . import limits


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class Report:
    pages: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    annotated_pages: list[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def public(self) -> dict:
        return {"pages": self.pages, "errors": self.errors, "warnings": self.warnings, "annotated_pages": [p + 1 for p in self.annotated_pages]}


def inherited(page: pikepdf.Page, key: str, default=None):
    node = page.obj
    for _ in range(64):  # a /Parent cycle in a damaged file must not hang the tool
        if node is None:
            break
        if key in node:
            return node[key]
        node = node.get("/Parent")
    return default


def page_box(page: pikepdf.Page) -> tuple[float, float, float, float]:
    """MediaBox clipped by CropBox as four floats. Raises ValueError when either is missing or malformed."""
    media = inherited(page, "/MediaBox")
    if media is None:
        raise ValueError("no MediaBox")
    media_box = [float(v) for v in media]
    crop = inherited(page, "/CropBox", media)
    crop_box = [float(v) for v in crop]
    if len(media_box) != 4 or len(crop_box) != 4:
        raise ValueError("a page box does not have four numbers")
    left, bottom = max(crop_box[0], media_box[0]), max(crop_box[1], media_box[1])
    right, top = min(crop_box[2], media_box[2]), min(crop_box[3], media_box[3])
    if not (right - left > 0 and top - bottom > 0):
        raise ValueError("a page box is empty")
    return left, bottom, right, top


def _has_signature(pdf: pikepdf.Pdf) -> bool:
    root = pdf.Root
    if "/Perms" in root:
        return True
    form = root.get("/AcroForm")
    if form is not None and int(form.get("/SigFlags", 0)) & 1:
        return True
    fields = (form.get("/Fields") if form is not None else None) or []
    return any(str(field_.get("/FT", "")) == "/Sig" for field_ in fields)


def check(path: Path) -> Report:
    report = Report()
    try:
        return _check(path, report)
    except (pikepdf.PdfError, ValueError, TypeError, AttributeError, KeyError, IndexError, RecursionError, OverflowError):
        report.errors.append("the PDF structure is damaged or unusual and cannot be edited safely")
        return report


def _check(path: Path, report: Report) -> Report:
    if path.stat().st_size > limits.MAX_ORIGINAL_BYTES:
        report.errors.append(f"file is larger than {limits.MAX_ORIGINAL_BYTES // 2**20} MB")
        return report
    try:
        pdf = pikepdf.open(path)
    except pikepdf.PasswordError:
        report.errors.append("the PDF is password protected: remove the password first")
        return report
    except pikepdf.PdfError:
        report.errors.append("this is not a readable PDF")
        return report
    with pdf:
        report.pages = len(pdf.pages)
        if report.pages == 0:
            report.errors.append("the PDF has no pages")
        if report.pages > limits.MAX_ORIGINAL_PAGES:
            report.errors.append(f"{report.pages} pages is over the limit of {limits.MAX_ORIGINAL_PAGES}")
        if pdf.is_encrypted:
            report.errors.append("the PDF is encrypted: remove the encryption first")
        if _has_signature(pdf):
            report.errors.append("the PDF is digitally signed and any edit would invalidate the signature")
        form = pdf.Root.get("/AcroForm")
        if form is not None and len(form.get("/Fields", [])):
            report.errors.append("the PDF has interactive form fields that this tool does not preserve")
        for index, page in enumerate(pdf.pages):
            if len(page.obj.get("/Annots", [])):
                report.annotated_pages.append(index)
            if int(inherited(page, "/Rotate", 0)) % 90:
                report.errors.append(f"page {index + 1} has a rotation that is not a multiple of 90 degrees")
                break
            try:
                page_box(page)
            except (ValueError, TypeError):
                report.errors.append(f"page {index + 1} has a missing or malformed page size")
                break
        if "/StructTreeRoot" in pdf.Root:
            report.warnings.append("this is a tagged PDF: replaced pages lose their reading structure")
        if report.annotated_pages:
            report.warnings.append("some pages carry annotations or links: replacing one of them removes its annotations")
    return report
