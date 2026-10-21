"""Rank, verify and assign: which original page does each rescan belong to."""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

import cv2
import numpy as np

from . import limits
from .assign import maximise
from .signature import Signature, text_overlap

MIN_INLIERS = 25
MIN_AGREEMENT = 0.65
MIN_SCALE, MAX_SCALE, MAX_SKEW = 0.7, 1.4, 12.0
MIN_TEXT_WORDS = 12
CLEAR_SCORE = 0.55
CLEAR_MARGIN = 0.12


class Cancelled(Exception):
    pass


@dataclass
class Candidate:
    page: int
    score: float
    inliers: int
    matches: int
    agreement: float
    quick: int
    text: float | None
    quarter_turns: int
    angle: float
    scale: float
    transform: list[list[float]] | None = field(default=None, repr=False)

    def public(self) -> dict:
        return {
            "page": self.page + 1,
            "score": round(self.score, 3),
            "inliers": self.inliers,
            "matches": self.matches,
            "agreement": round(self.agreement, 3),
            "quick": self.quick,
            "text": None if self.text is None else round(self.text, 3),
            "quarter_turns": self.quarter_turns,
            "angle": round(self.angle, 2),
            "scale": round(self.scale, 3),
        }


@dataclass
class Proposal:
    """The matcher's answer for one rescan. `status` is clear, check or none."""

    rescan: int
    page: int | None
    status: str
    reason: str
    candidates: list[Candidate]

    def public(self) -> dict:
        return {
            "rescan": self.rescan,
            "page": None if self.page is None else self.page + 1,
            "status": self.status,
            "reason": self.reason,
            "candidates": [c.public() for c in self.candidates],
        }


def _consistent(
    desc_a: np.ndarray | None, pts_a: np.ndarray, desc_b: np.ndarray | None, pts_b: np.ndarray
) -> tuple[int, int, np.ndarray | None]:
    """Count geometrically consistent SIFT matches under a similarity transform."""
    if desc_a is None or desc_b is None or len(pts_a) < 8 or len(pts_b) < 8:
        return 0, 0, None
    knn = cv2.BFMatcher(cv2.NORM_L2).knnMatch(desc_a, desc_b, k=2)
    good = [m for m, n in (pair for pair in knn if len(pair) == 2) if m.distance < 0.78 * n.distance]
    if len(good) < 8:
        return 0, len(good), None
    src = pts_a[[m.queryIdx for m in good]]
    dst = pts_b[[m.trainIdx for m in good]]
    matrix, mask = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=4.0, maxIters=3000, confidence=0.995)
    if matrix is None:
        return 0, len(good), None
    return int(mask.sum()), len(good), matrix


def verify(rescan: Signature, page: Signature) -> tuple[int, int, np.ndarray | None]:
    return _consistent(rescan.descriptors, rescan.keypoints, page.descriptors, page.keypoints)


def agreement(rescan: Signature, page: Signature, matrix: np.ndarray) -> float:
    """How much of the ink in the overlap lines up once the rescan is moved onto the page."""
    h, w = page.gray.shape
    moved = cv2.warpAffine(rescan.ink, matrix, (w, h), flags=cv2.INTER_NEAREST)
    area = cv2.warpAffine(np.full(rescan.ink.shape, 255, np.uint8), matrix, (w, h), flags=cv2.INTER_NEAREST) > 0
    if area.mean() < 0.3:
        return 0.0
    kernel = np.ones((5, 5), np.uint8)
    a, b = page.ink > 0, moved > 0
    a, b = a & area, b & area
    near_a, near_b = cv2.dilate(page.ink, kernel) > 0, cv2.dilate(moved, kernel) > 0
    cover_a = (a & near_b).sum() / max(1, a.sum())
    cover_b = (b & near_a).sum() / max(1, b.sum())
    return float((cover_a + cover_b) / 2)


def quarter_turns_from(matrix: np.ndarray) -> tuple[int, float, float]:
    """Clockwise quarter turns that make the rescan upright, the residual-free angle and the scale."""
    angle = math.degrees(math.atan2(matrix[1, 0], matrix[0, 0]))
    scale = math.hypot(matrix[0, 0], matrix[1, 0])
    # The matrix carries the rescan onto the page, so applying its rotation makes the rescan upright.
    return int(round(angle / 90.0)) % 4, angle, scale


def plausible(matrix: np.ndarray) -> bool:
    """A rescan of the same page keeps its size and sits at a right angle, give or take a skew."""
    _, angle, scale = quarter_turns_from(matrix)
    return MIN_SCALE <= scale <= MAX_SCALE and abs(angle - 90 * round(angle / 90)) <= MAX_SKEW


def candidate_score(inliers: int, agree: float, text: float | None) -> float:
    visual = 1 - math.exp(-inliers / 150)
    score = visual * (0.98 + 0.02 * agree)
    if text is not None:
        score = 0.65 * score + 0.35 * text
    return score


def shortlist(rescan: Signature, pages: list[Signature], k: int) -> list[tuple[int, int]]:
    """Cheap pass on the spread-out feature subset of every page. Returns (page, inliers)."""
    ranked = []
    for index, page in enumerate(pages):
        inliers, _, _ = _consistent(rescan.coarse_descriptors, rescan.coarse_points, page.coarse_descriptors, page.coarse_points)
        ranked.append((index, inliers))
    ranked.sort(key=lambda r: -r[1])
    return ranked[:k]


def match(
    rescans: list[Signature],
    pages: list[Signature],
    *,
    progress: Callable[[int, int], None] | None = None,
    cancel: threading.Event | None = None,
    text_for: Callable[..., frozenset[str]] | None = None,
    top_k: int = limits.TOP_K,
) -> list[Proposal]:
    """Score every rescan against shortlisted pages, then resolve conflicts one to one."""
    all_candidates: list[list[Candidate]] = []
    for r, rescan in enumerate(rescans):
        if cancel is not None and cancel.is_set():
            raise Cancelled
        found: list[Candidate] = []
        if rescan.blank:
            blanks = [i for i, p in enumerate(pages) if p.blank]
            found = [Candidate(i, 0.0, 0, 0, 1.0, 0, None, 0, 0.0, 1.0) for i in blanks]
        else:
            for index, quick in shortlist(rescan, pages, top_k):
                if pages[index].blank:
                    continue
                inliers, matches, matrix = verify(rescan, pages[index])
                if matrix is None or not plausible(matrix):
                    continue
                quarter, angle, scale = quarter_turns_from(matrix)
                agree = agreement(rescan, pages[index], matrix) if inliers >= MIN_INLIERS // 2 else 0.0
                text = None
                if text_for is not None:
                    words = text_for("rescan", r, quarter)
                    if len(words) >= MIN_TEXT_WORDS:
                        # A page with no readable text cannot confirm a rescan that has some.
                        text = text_overlap(words, text_for("page", index)) or 0.0
                found.append(
                    Candidate(index, candidate_score(inliers, agree, text), inliers, matches, agree, quick, text, quarter, angle, scale, matrix.tolist())
                )
            found.sort(key=lambda c: -c.score)
        all_candidates.append(found)
        if progress is not None:
            progress(r + 1, len(rescans))
    return resolve(rescans, pages, all_candidates)


def resolve(rescans: list[Signature], pages: list[Signature], all_candidates: list[list[Candidate]]) -> list[Proposal]:
    n_pages = len(pages)
    matrix = np.zeros((len(rescans), n_pages))
    for r, found in enumerate(all_candidates):
        for c in found:
            if c.inliers >= MIN_INLIERS and c.agreement >= MIN_AGREEMENT:
                matrix[r, c.page] = max(c.score, 1e-3)
    chosen = {r: p for r, p in maximise(matrix) if matrix[r, p] > 0} if matrix.any() else {}
    proposals = []
    for r, found in enumerate(all_candidates):
        if rescans[r].blank:
            proposals.append(_blank_proposal(r, found, chosen))
            continue
        page = chosen.get(r)
        if page is None:
            reason = "no original page shares enough features or text with this rescan"
            proposals.append(Proposal(r, None, "none", reason, found[:4]))
            continue
        top = next(c for c in found if c.page == page)
        rivals = [c for c in found if c.page != page]
        margin = top.score - (rivals[0].score if rivals else 0.0)
        contested = [o for o in range(len(rescans)) if o != r and _best(all_candidates[o]) == page]
        status, reason = "clear", f"{top.inliers} consistent features, margin {margin:.2f}"
        if top.score < CLEAR_SCORE:
            status, reason = "check", f"weak evidence: {top.inliers} consistent features"
        elif margin < CLEAR_MARGIN:
            status, reason = "check", f"page {rivals[0].page + 1} scores almost as high (margin {margin:.2f})"
        elif contested:
            status, reason = "check", f"another rescan also ranks page {page + 1} first"
        proposals.append(Proposal(r, page, status, reason, [top] + rivals[:3]))
    return proposals


def _best(found: list[Candidate]) -> int | None:
    return found[0].page if found and found[0].inliers >= MIN_INLIERS and found[0].agreement >= MIN_AGREEMENT else None


def _blank_proposal(r: int, found: list[Candidate], chosen: dict[int, int]) -> Proposal:
    if not found:
        return Proposal(r, None, "none", "this rescan is blank and the original has no blank page", [])
    reason = "blank pages carry no evidence: confirm the position yourself"
    page = found[0].page if len(found) == 1 else None
    return Proposal(r, page, "check", reason, found[:4])
