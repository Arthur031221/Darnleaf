"""Per-page evidence: local features, an ink map and optional text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import cv2
import numpy as np

BLANK_INK = 0.004
_SIFT = None


def sift():
    global _SIFT
    if _SIFT is None:
        _SIFT = cv2.SIFT_create(nfeatures=1500, contrastThreshold=0.02)
    return _SIFT


@dataclass
class Signature:
    gray: np.ndarray
    keypoints: np.ndarray
    descriptors: np.ndarray | None
    ink: np.ndarray
    coarse_points: np.ndarray
    coarse_descriptors: np.ndarray | None
    ink_fraction: float
    tokens: frozenset[str] = field(default_factory=frozenset)

    @property
    def blank(self) -> bool:
        return self.ink_fraction < BLANK_INK


def spread(keypoints, shape, cells: int = 8, per_cell: int = 14) -> np.ndarray:
    """Indices of the strongest keypoints in each cell, so one stain cannot own the shortlist."""
    best: dict[tuple[int, int], list[tuple[float, int]]] = {}
    for i, k in enumerate(keypoints):
        cell = (int(k.pt[1] * cells / shape[0]), int(k.pt[0] * cells / shape[1]))
        best.setdefault(cell, []).append((k.response, i))
    return np.array([i for items in best.values() for _, i in sorted(items, reverse=True)[:per_cell]], dtype=int)


def ink_map(gray: np.ndarray) -> np.ndarray:
    """Binary map of dark marks, robust to uneven lighting; speckle is opened away."""
    k = max(15, (min(gray.shape) // 25) | 1)
    mask = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, k, 14)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))


def compute(gray: np.ndarray) -> Signature:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    keypoints, descriptors = sift().detectAndCompute(clahe, None)
    pts = np.array([k.pt for k in keypoints], np.float32).reshape(-1, 2)
    coarse = spread(keypoints, gray.shape) if descriptors is not None else np.zeros(0, dtype=int)
    ink = ink_map(gray)
    return Signature(
        gray,
        pts,
        descriptors,
        ink,
        pts[coarse],
        np.ascontiguousarray(descriptors[coarse]) if descriptors is not None else None,
        float((ink > 0).mean()),
    )


_WORD = re.compile(r"[a-z0-9]{3,}")


def tokens_from_text(text: str) -> frozenset[str]:
    return frozenset(_WORD.findall(text.lower()))


def text_overlap(a: frozenset[str], b: frozenset[str]) -> float | None:
    """Overlap coefficient of two word sets, or None when either page has too little text."""
    if len(a) < 12 or len(b) < 12:
        return None
    return len(a & b) / min(len(a), len(b))
