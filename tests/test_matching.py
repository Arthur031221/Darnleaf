import numpy as np
import pytest

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
