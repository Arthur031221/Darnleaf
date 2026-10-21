"""Write the repaired PDF and a receipt that says exactly what changed."""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pikepdf
from PIL import Image

from . import __version__, evidence, imaging, preflight
from .imaging import InputError, Source

ALIGN_DPI = 200


@dataclass
class Replacement:
    """One confirmed swap. `page` is zero-based; `quarter_turns` are clockwise."""

    page: int
    source: Source
    quarter_turns: int = 0
    evidence: dict = field(default_factory=dict)
    confirmed_by: str = "user"


def _placement(page: pikepdf.Page) -> tuple[str, tuple[float, float]]:
    """Content stream matrix that draws a unit-square image upright on a possibly rotated page."""
    left, bottom, right, top = preflight.page_box(page)
    w, h = right - left, top - bottom
    rotate = int(preflight.inherited(page, "/Rotate", 0)) % 360
    matrix = {
        0: (w, 0, 0, h, 0, 0),
        90: (0, h, -w, 0, w, 0),
        180: (-w, 0, 0, -h, w, h),
        270: (0, -h, w, 0, 0, h),
    }[rotate]
    a, b, c, d, e, f = matrix
    shown = (h, w) if rotate in (90, 270) else (w, h)
    return f"q {a:g} {b:g} {c:g} {d:g} {e + left:g} {f + bottom:g} cm /DarnleafScan Do Q", shown


def _render_original(pdf_path: Path, index: int) -> Image.Image:
    return imaging.render_pdf_page(pdf_path, index, scale=ALIGN_DPI / 72)


def letterbox(img: Image.Image, aspect: float) -> Image.Image:
    """Pad with white to the page's aspect ratio so placing the image never stretches it."""
    if abs(img.width / img.height - aspect) < 0.01:
        return img
    width = max(img.width, round(img.height * aspect))
    height = max(img.height, round(img.width / aspect))
    canvas = Image.new("RGB", (width, height), "white")
    canvas.paste(img, ((width - img.width) // 2, (height - img.height) // 2))
    return canvas


def _prepare(item: Replacement, original: Path, page: pikepdf.Page, mode: str) -> tuple[Image.Image, str]:
    img = item.source.load()
    if item.quarter_turns:
        img = img.rotate(-90 * item.quarter_turns, expand=True)
    if mode == "align":
        warped = evidence.align(img, _render_original(original, item.page))
        if warped is not None:
            return warped, "aligned"
    _, (shown_w, shown_h) = _placement(page)
    return letterbox(img, shown_w / shown_h), "fit"


def _jpeg(img: Image.Image, quality: int) -> tuple[bytes, str]:
    gray = img.convert("L")
    diff = np.abs(np.asarray(img.convert("RGB"), dtype=np.int16) - np.asarray(gray.convert("RGB"), dtype=np.int16)).mean()
    use = gray if diff < 1.5 else img.convert("RGB")
    buffer = io.BytesIO()
    use.save(buffer, "JPEG", quality=quality, optimize=True)
    return buffer.getvalue(), "/DeviceGray" if use.mode == "L" else "/DeviceRGB"


def _swap_page(pdf: pikepdf.Pdf, page: pikepdf.Page, img: Image.Image, quality: int) -> None:
    data, space = _jpeg(img, quality)
    stream = pdf.make_stream(data)
    stream.Type, stream.Subtype = pikepdf.Name.XObject, pikepdf.Name.Image
    stream.Width, stream.Height, stream.BitsPerComponent = img.width, img.height, 8
    stream.ColorSpace, stream.Filter = pikepdf.Name(space), pikepdf.Name.DCTDecode
    command, _ = _placement(page)
    page.obj["/Contents"] = pdf.make_stream(command.encode())
    page.obj["/Resources"] = pikepdf.Dictionary(XObject=pikepdf.Dictionary(DarnleafScan=stream))
    for key in ("/Annots", "/Thumb", "/StructParents"):
        if key in page.obj:
            del page.obj[key]


def _same_file(a: Path, b: Path) -> bool:
    """True when both names reach the same file, through a symlink or a hard link."""
    if a.resolve() == b.resolve():
        return True
    return a.exists() and b.exists() and os.path.samefile(a, b)


def _umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


def _save_atomically(pdf: pikepdf.Pdf, target: Path) -> None:
    """Write beside the target and rename over it, so a failed save never leaves a half file and never writes through a link."""
    fd, tmp = tempfile.mkstemp(prefix=".darnleaf-", suffix=".tmp", dir=target.parent)
    os.close(fd)
    try:
        pdf.save(tmp)
        os.chmod(tmp, 0o666 & ~_umask())
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _write_atomically(target: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".darnleaf-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(tmp, 0o666 & ~_umask())
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def export(
    original: Path,
    items: list[Replacement],
    out_pdf: Path,
    receipt_path: Path | None = None,
    *,
    mode: str = "align",
    quality: int = 92,
    drop_annotations: bool = False,
    label: str | None = None,
) -> dict:
    """Replace the listed pages in place and save a new file. The original is never written to."""
    for target in (out_pdf, receipt_path):
        if target is not None and _same_file(target, original):
            raise InputError("the output must be a different file from the original")
    report = preflight.check(original)
    if not report.ok:
        raise InputError("; ".join(report.errors))
    pages = [i.page for i in items]
    if len(set(pages)) != len(pages):
        raise InputError("two rescans were assigned to the same page")
    if any(not 0 <= p < report.pages for p in pages):
        raise InputError("a replacement points at a page that does not exist")
    blocked = [p + 1 for p in pages if p in report.annotated_pages]
    if blocked and not drop_annotations:
        raise InputError(f"pages {blocked} carry annotations that would be lost; confirm that they may be dropped")
    source_hash = preflight.sha256(original)
    entries = []
    with pikepdf.open(original) as pdf:
        for item in sorted(items, key=lambda i: i.page):
            img, how = _prepare(item, original, pdf.pages[item.page], mode)
            _swap_page(pdf, pdf.pages[item.page], img, quality)
            entries.append(
                {
                    "page": item.page + 1,
                    "replacement": item.source.label,
                    "replacement_sha256": preflight.sha256(item.source.path),
                    "quarter_turns_clockwise": item.quarter_turns,
                    "placement": how,
                    "evidence": item.evidence,
                    "confirmed_by": item.confirmed_by,
                }
            )
        _save_atomically(pdf, out_pdf)
    receipt = {
        "tool": f"darnleaf {__version__}",
        "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "original": {"file": label or original.name, "sha256": source_hash, "pages": report.pages},
        "output": {"file": out_pdf.name, "sha256": preflight.sha256(out_pdf), "pages": report.pages},
        "replaced": entries,
        "untouched_pages": report.pages - len(entries),
        "note": "Pages not listed are the original page objects, saved without re-rendering.",
    }
    if receipt_path is not None:
        _write_atomically(receipt_path, (json.dumps(receipt, indent=2) + "\n").encode())
    return receipt
