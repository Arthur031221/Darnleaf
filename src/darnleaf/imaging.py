"""Loading pages and rescans into comparable grayscale images."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps

from . import limits

Image.MAX_IMAGE_PIXELS = limits.MAX_IMAGE_PIXELS
# PDFium is not thread safe. Every call into it, from the match thread or from a request, takes this lock.
PDFIUM = threading.RLock()
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
HEIC_SUFFIXES = {".heic", ".heif"}
try:  # Phone photos. Optional: pip install "darnleaf[heic]"
    from pillow_heif import register_heif_opener

    register_heif_opener()
    IMAGE_SUFFIXES |= HEIC_SUFFIXES
except ImportError:
    pass


class InputError(ValueError):
    """A file the tool cannot use, with a message meant for the person who supplied it."""


@dataclass
class Source:
    """One replacement candidate: an image file or one page of a scanned PDF."""

    label: str
    path: Path
    page: int | None = None

    def load(self) -> Image.Image:
        if self.page is not None:
            return render_pdf_page(self.path, self.page, scale=200 / 72)
        try:
            with Image.open(self.path) as raw:
                img = ImageOps.exif_transpose(raw)
                return img.convert("RGB")
        except Image.DecompressionBombError as exc:
            raise InputError(f"{self.label}: image is larger than {limits.MAX_IMAGE_PIXELS:,} pixels") from exc
        except OSError as exc:
            raise InputError(f"{self.label}: not a readable image") from exc


def render_page(page: pdfium.PdfPage, scale: float) -> Image.Image:
    with PDFIUM:
        return page.render(scale=scale).to_pil().convert("RGB")


def render_pdf_page(path: Path, index: int, *, scale: float | None = None, longest: int | None = None) -> Image.Image:
    """Open a PDF, render one page and close it again, all under the PDFium lock."""
    with PDFIUM:
        doc = pdfium.PdfDocument(str(path))
        try:
            page = doc[index]
            width, height = page.get_size()
            if not (width > 0 and height > 0):
                raise InputError("a page has no usable size")
            wanted = scale if scale is not None else (longest or 1000) / max(width, height)
            if width * height * wanted * wanted > limits.MAX_IMAGE_PIXELS:
                # A huge MediaBox must not turn a 200 dpi render into gigabytes of memory.
                wanted = (limits.MAX_IMAGE_PIXELS / (width * height)) ** 0.5 * 0.98
            return render_page(page, wanted)
        finally:
            doc.close()


def expand_sources(paths: list[Path]) -> list[Source]:
    """Turn image and PDF paths into one Source per image or PDF page."""
    out: list[Source] = []
    for path in paths:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            with PDFIUM:
                try:
                    doc = pdfium.PdfDocument(str(path))
                except pdfium.PdfiumError as exc:
                    raise InputError(f"{path.name}: not a readable PDF") from exc
                count = len(doc)
                doc.close()
            out.extend(Source(f"{path.name} p.{i + 1}", path, i) for i in range(count))
        elif suffix in IMAGE_SUFFIXES:
            out.append(Source(path.name, path))
        elif suffix in HEIC_SUFFIXES:
            raise InputError(f"{path.name}: HEIC photos need the heic extra (pip install \"darnleaf[heic]\"), or export them as JPEG first")
        else:
            raise InputError(f"{path.name}: use PNG, JPEG, TIFF, BMP, WebP or PDF files")
    if len(out) > limits.MAX_REPLACEMENTS:
        raise InputError(f"{len(out)} replacement pages is over the limit of {limits.MAX_REPLACEMENTS}")
    return out


def to_work_gray(img: Image.Image, size: int = limits.WORK_SIZE) -> np.ndarray:
    """Grayscale, longest side scaled to `size`, page cut out of a dark scanner bed if there is one."""
    gray = np.asarray(img.convert("L"))
    scale = size / max(gray.shape)
    if scale < 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return crop_to_page(gray)


def crop_to_page(gray: np.ndarray) -> np.ndarray:
    """If the scan shows a darker bed around a bright page, rotate and crop to the page."""
    h, w = gray.shape
    edge = np.concatenate([gray[:6].ravel(), gray[-6:].ravel(), gray[:, :6].ravel(), gray[:, -6:].ravel()])
    if np.median(edge) > 0.7 * np.median(gray):
        return gray
    blur = cv2.GaussianBlur(gray, (0, 0), 3)
    _, mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return gray
    biggest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(biggest) < 0.4 * h * w:
        return gray
    box = cv2.boxPoints(cv2.minAreaRect(biggest)).astype(np.float32)
    ordered = _order_corners(box)
    tl, tr, br, bl = ordered
    width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    if min(width, height) < 100:
        return gray
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
    warped = cv2.warpPerspective(gray, cv2.getPerspectiveTransform(ordered, target), (width, height))
    inset = max(4, min(width, height) // 100)
    return warped[inset:-inset, inset:-inset]


def _order_corners(points: np.ndarray) -> np.ndarray:
    """Top-left, top-right, bottom-right, bottom-left for a quad that is roughly upright."""
    total, diff = points.sum(axis=1), np.diff(points, axis=1).ravel()
    return np.array([points[total.argmin()], points[diff.argmin()], points[total.argmax()], points[diff.argmax()]], np.float32)
