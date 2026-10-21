from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from darnleaf import assign, matcher, signature


def test_hungarian_beats_greedy():
    score = np.array([[0.9, 0.8], [0.85, 0.1]])
    assert sorted(assign.maximise(score)) == [(0, 1), (1, 0)]


def test_hungarian_handles_more_rows_than_columns():
    pairs = assign.maximise(np.array([[0.1], [0.9], [0.5]]))
    assert pairs == [(1, 0)]


@pytest.mark.parametrize("angle, turns", [(0, 0), (90, 1), (180, 2), (270, 3), (-90, 3), (2, 0)])
def test_quarter_turns_from_matrix(angle, turns):
    a = np.radians(angle)
    matrix = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0]])
    assert matcher.quarter_turns_from(matrix)[0] == turns


def test_implausible_transforms_are_rejected():
    def mat(angle, scale):
        a = np.radians(angle)
        return np.array([[scale * np.cos(a), -scale * np.sin(a), 0], [scale * np.sin(a), scale * np.cos(a), 0]])

    assert matcher.plausible(mat(1.5, 1.0))
    assert matcher.plausible(mat(91, 1.1))
    assert not matcher.plausible(mat(45, 1.0))
    assert not matcher.plausible(mat(0, 2.5))
    assert not matcher.plausible(mat(0, 0.3))


def test_score_rises_with_inliers_and_text_cannot_replace_vision():
    assert matcher.candidate_score(300, 0.9, None) > matcher.candidate_score(60, 0.9, None)
    assert matcher.candidate_score(0, 0.0, 1.0) <= 0.36


def test_text_overlap_needs_enough_words():
    few = signature.tokens_from_text("only a few words here")
    many = signature.tokens_from_text(" ".join(f"word{i}" for i in range(30)))
    assert signature.text_overlap(few, many) is None
    assert signature.text_overlap(many, many) == 1.0


def test_blank_page_is_flagged():
    sig = signature.compute(np.full((900, 640), 250, dtype=np.uint8))
    assert sig.blank


def test_every_distinct_page_is_found_and_nothing_clear_is_wrong(case, matched):
    sources, proposals = matched
    truth = case["truth"]["truth"]
    forms, blank = range(30, 36), 2
    for proposal in proposals:
        real = truth[sources[proposal.rescan].label]
        if real is None:
            assert proposal.status == "none"
            continue
        if proposal.status == "clear":
            assert proposal.page + 1 == real, f"{sources[proposal.rescan].label} was labelled clear but is wrong"
        if real not in forms and real != blank:
            assert proposal.page + 1 == real
            assert proposal.status == "clear"
        assert real in [c.page + 1 for c in proposal.candidates], "the true page must at least be listed"


def test_blank_and_repeated_forms_are_never_called_clear_without_evidence(case, matched):
    sources, proposals = matched
    truth = case["truth"]["truth"]
    for proposal in proposals:
        if truth[sources[proposal.rescan].label] == 2:
            assert proposal.status == "check"


def test_rotation_of_rescans_is_recovered(case, matched):
    sources, proposals = matched
    turned = case["truth"]["turned_ccw"]
    for proposal in proposals:
        if proposal.page is None:
            continue
        # The sample turns a rescan counter-clockwise; the matcher reports the clockwise turns that undo it.
        want = (turned[sources[proposal.rescan].label] // 90) % 4
        top = proposal.candidates[0]
        assert top.quarter_turns == want


def _homography(strength: float, size=(600, 800)):
    w, h = size
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    # The top edge is pulled in and down, the bottom stays: a page photographed from below.
    moved = corners + np.float32([[1, 1], [-1, 0.5], [0, 0], [0, 0]]) * strength * np.float32([w, h])
    return cv2.getPerspectiveTransform(corners, moved)


def test_a_mild_keystone_is_plausible_and_a_wild_one_is_not():
    size = (600, 800)
    assert matcher.plausible(_homography(0.04, size), size)
    assert matcher.plausible(_homography(0.07, size), size)
    assert not matcher.plausible(_homography(0.3, size), size)
    mirrored = np.array([[-1.0, 0, 600], [0, 1.0, 0], [0, 0, 1.0]])
    assert matcher._keystone(mirrored, size) == float("inf")


def test_perspective_fit_is_used_only_when_it_explains_clearly_more():
    rng = np.random.default_rng(3)
    src = rng.uniform(0, 600, (150, 2)).astype(np.float32) * [1, 800 / 600]
    size = (600, 800)

    flat = (src * 1.02 + 15).astype(np.float32)
    inliers, matrix = matcher._fit(src, flat, size)
    assert inliers >= 145 and matrix[2, 0] == matrix[2, 1] == 0

    slanted = cv2.perspectiveTransform(src.reshape(-1, 1, 2), _homography(0.05, size)).reshape(-1, 2)
    slanted[:20] += rng.uniform(-200, 200, (20, 2))
    inliers, matrix = matcher._fit(src, slanted.astype(np.float32), size)
    assert inliers >= 125 and abs(matrix[2, 0]) + abs(matrix[2, 1]) > 0


def test_rescans_photographed_at_a_slant_still_match_and_never_clear_wrongly(case, tmp_path):
    import importlib.util
    import shutil

    from darnleaf import imaging, pipeline

    spec = importlib.util.spec_from_file_location("benchmark", Path(__file__).parent.parent / "scripts" / "benchmark.py")
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    shutil.copytree(case["dir"] / "rescans", tmp_path / "rescans")
    bench.tilt_rescans(tmp_path / "rescans", 0.05, seed=7)
    sources = imaging.expand_sources(sorted((tmp_path / "rescans").glob("*.jpg")))
    truth = case["truth"]["truth"]
    found = 0
    for proposal in pipeline.run(case["pdf"], sources):
        real = truth[sources[proposal.rescan].label]
        if proposal.status == "clear":
            assert proposal.page + 1 == real
        if real not in (None, 2, *range(30, 36)) and proposal.page is not None and proposal.page + 1 == real:
            found += 1
    assert found >= 3, "most distinct pages should still be found under a 5% keystone"


def test_slanted_rescan_is_straightened_onto_the_page(case):
    from darnleaf import evidence, imaging

    source = imaging.expand_sources([case["rescans"][3]])[0]
    page = int(case["truth"]["truth"][source.label]) - 1
    rescan = source.load()
    w, h = rescan.size
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    moved = corners + np.float32([[1, 1], [-1, 0.5], [0, 0], [0, 0]]) * 0.04 * np.float32([w, h])
    slanted = cv2.warpPerspective(np.asarray(rescan), cv2.getPerspectiveTransform(corners, moved), (w, h), borderValue=(60, 60, 60))
    target = imaging.render_pdf_page(case["pdf"], page, longest=1000)
    aligned = evidence.align(Image.fromarray(slanted), target)
    assert aligned is not None
    a, b = np.asarray(aligned.convert("L"), np.float32), np.asarray(target.convert("L"), np.float32)
    assert np.corrcoef(a.ravel(), b.ravel())[0, 1] > 0.85
