"""Pairwise views of a rescan and a page: alignment, overlay and the matched features."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from . import limits, signature
from .matcher import consistent_matches, plausible, verify

ALIGN_MIN_INLIERS = 25


@dataclass
class Registration:
    """3x3 transform (a similarity, or a mild perspective for a slanted photo) that carries the rescan onto the page, in full-resolution pixels."""

    matrix: np.ndarray
    inliers: int
    matches: int


def _work(img: Image.Image) -> tuple[signature.Signature, float]:
    gray = np.asarray(img.convert("L"))
    scale = min(1.0, limits.WORK_SIZE / max(gray.shape))
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else gray
    return signature.compute(small), scale


def register(rescan: Image.Image, page: Image.Image) -> Registration | None:
    """Estimate how the upright rescan sits on the page. None when they do not agree."""
    (sig_r, s1), (sig_p, s2) = _work(rescan), _work(page)
    inliers, matches, matrix = verify(sig_r, sig_p)
    if matrix is None or inliers < ALIGN_MIN_INLIERS or not plausible(matrix, (sig_r.gray.shape[1], sig_r.gray.shape[0])):
        return None
    full = np.diag([1 / s2, 1 / s2, 1.0]) @ matrix @ np.diag([s1, s1, 1.0])
    return Registration(full, inliers, matches)


def align(rescan: Image.Image, page: Image.Image) -> Image.Image | None:
    """Warp the rescan onto the page frame, or None when the two do not agree well enough."""
    reg = register(rescan, page)
    if reg is None:
        return None
    color = cv2.cvtColor(np.asarray(rescan.convert("RGB")), cv2.COLOR_RGB2BGR)
    # Anything the rescan does not cover becomes white paper rather than black.
    warped = cv2.warpPerspective(color, reg.matrix, page.size, flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
    return Image.fromarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))


def difference(aligned: Image.Image, page: Image.Image) -> Image.Image:
    """Overlay of the page and the aligned rescan: shared ink is dark, ink in only one of them is coloured."""
    a = 255 - np.asarray(page.convert("L"), dtype=np.int16)
    b = 255 - np.asarray(aligned.convert("L").resize(page.size), dtype=np.int16)
    a, b = np.clip((a - 25) * 2, 0, 255), np.clip((b - 25) * 2, 0, 255)
    # White paper; page-only ink pulls toward blue, rescan-only ink toward red, shared ink stays dark.
    out = np.stack([255 - b, 255 - (a + b) // 2, 255 - a], axis=-1)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def match_map(rescan: Image.Image, page: Image.Image, limit: int = 60) -> Image.Image | None:
    """Side by side picture with lines between a sample of the consistent features."""
    (sig_r, _), (sig_p, _) = _work(rescan), _work(page)
    good, _, matrix, mask = consistent_matches(sig_r.descriptors, sig_r.keypoints, sig_p.descriptors, sig_p.keypoints, (sig_r.gray.shape[1], sig_r.gray.shape[0]))
    if matrix is None:
        return None
    keep = [m for m, ok in zip(good, mask.ravel(), strict=True) if ok]
    keep = keep[:: max(1, len(keep) // limit)]
    drawn = cv2.drawMatches(
        cv2.cvtColor(sig_r.gray, cv2.COLOR_GRAY2BGR),
        [cv2.KeyPoint(float(x), float(y), 6) for x, y in sig_r.keypoints],
        cv2.cvtColor(sig_p.gray, cv2.COLOR_GRAY2BGR),
        [cv2.KeyPoint(float(x), float(y), 6) for x, y in sig_p.keypoints],
        keep,
        None,
        matchColor=(60, 90, 220),
        singlePointColor=None,
        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
    )
    return Image.fromarray(cv2.cvtColor(drawn, cv2.COLOR_BGR2RGB))
