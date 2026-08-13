"""
Tests for the relative validity criteria.

What this layer guarantees: a criterion selects in the direction its index
declares rather than the direction its code was written in, it reports an
uninformative curve as uninformative instead of returning an arbitrary
argmax, and the curve it hands back is the one `viz` can plot.
"""

from __future__ import annotations

import pytest

from xxcluster.measures.validation.base import BaseValidityIndex
from xxcluster.measures.validation.internal import Silhouette
from xxcluster.measures.validation.relative import (
    ElbowCriterion,
    MaxCriterion,
)


class Minimised(BaseValidityIndex):
    """A stub index that is better when lower, e.g. Davies-Bouldin.

    Defined here rather than imported because no minimised index is
    implemented yet. Without one, every test would agree with a criterion
    that hardcoded `>`, which is the mistake these tests exist to catch.
    """

    name = "minimised_stub"
    higher_is_better = False
    range_ = None

    def score(self, X=None, labels=None, **kwargs) -> float:
        raise NotImplementedError("stub; the criteria read scores, not data")


@pytest.fixture
def maximised() -> MaxCriterion:
    return MaxCriterion(Silhouette())


@pytest.fixture
def minimised() -> MaxCriterion:
    return MaxCriterion(Minimised())


PEAKED = {2: 0.40, 3: 0.75, 4: 0.42, 5: 0.38}
TROUGHED = {2: 1.90, 3: 0.60, 4: 1.70, 5: 1.80}


# --- Direction -------------------------------------------------------------


def test_maximised_index_selects_the_peak(maximised):
    assert maximised.select(PEAKED) == 3


def test_minimised_index_selects_the_trough(minimised):
    assert minimised.select(TROUGHED) == 3


def test_direction_comes_from_the_index_not_the_criterion():
    """The same curve read both ways must give opposite answers."""
    scores = {2: 0.1, 3: 0.9, 4: 0.5}
    assert MaxCriterion(Silhouette()).select(scores) == 3
    assert MaxCriterion(Minimised()).select(scores) == 2


def test_a_tie_goes_to_the_first_candidate_swept(maximised):
    """`is_better` is strict, so the smaller |C| wins; the conservative choice."""
    assert maximised.select({2: 0.7, 3: 0.7, 4: 0.5}) == 2


# --- Failed runs -----------------------------------------------------------


def test_nan_never_wins_the_selection(maximised):
    assert maximised.select({2: 0.4, 3: float("nan"), 4: 0.9, 5: 0.3}) == 4


def test_nan_in_first_position_does_not_win(maximised):
    """The seeded comparison is where a NaN would otherwise survive."""
    assert maximised.select({2: float("nan"), 3: 0.5, 4: 0.3}) == 3


def test_a_sweep_that_failed_entirely_is_an_error(maximised):
    with pytest.raises(ValueError, match="every run in the sweep failed"):
        maximised.select({2: float("nan"), 3: float("nan")})


def test_an_empty_sweep_is_an_error(maximised):
    with pytest.raises(ValueError, match="nothing was swept"):
        maximised.select({})


# --- Conclusiveness --------------------------------------------------------


def test_a_peaked_curve_is_conclusive(maximised):
    assert maximised.is_conclusive(PEAKED)


def test_a_flat_curve_is_not_conclusive(maximised):
    """No selection is a valid outcome; an argmax here would read as a finding."""
    assert not maximised.is_conclusive({2: 0.500, 3: 0.501, 4: 0.499, 5: 0.500})


def test_a_monotone_curve_is_not_conclusive(maximised):
    """The best candidate is at the edge, so it reflects where the sweep stopped."""
    assert not maximised.is_conclusive({2: 0.20, 3: 0.40, 4: 0.60, 5: 0.80})


def test_two_candidates_are_too_few_to_show_a_shape(maximised):
    assert not maximised.is_conclusive({2: 0.3, 3: 0.9})


def test_a_bare_peak_over_its_runner_up_is_not_conclusive(maximised):
    """A margin below the declared threshold is a tie, not a selection."""
    assert not maximised.is_conclusive({2: 0.700, 3: 0.702, 4: 0.699})


def test_the_margin_threshold_is_a_declared_parameter():
    scores = {2: 0.60, 3: 0.66, 4: 0.58}
    assert MaxCriterion(Silhouette(), min_margin=0.01).is_conclusive(scores)
    assert not MaxCriterion(Silhouette(), min_margin=0.20).is_conclusive(scores)


# --- The curve -------------------------------------------------------------


def test_curve_is_keyed_by_candidate(maximised):
    assert maximised.curve(PEAKED) == PEAKED


def test_curve_preserves_sweep_order(maximised):
    """Sorting by score would misalign the figure from the sweep it describes."""
    scattered = {5: 0.1, 2: 0.9, 4: 0.4}
    assert list(maximised.curve(scattered)) == [5, 2, 4]


def test_curve_is_a_copy(maximised):
    returned = maximised.curve(PEAKED)
    returned[99] = 0.0
    assert 99 not in PEAKED


def test_viz_consumes_the_curve_unchanged(maximised):
    """The contract `plot_selection_curve` relies on: indexable by candidate."""
    import matplotlib

    matplotlib.use("Agg")
    from xxcluster.viz.diagnostics import plot_selection_curve

    curve = maximised.curve(PEAKED)
    ax = plot_selection_curve(curve, selected=maximised.select(PEAKED),
                              criterion=maximised.name)
    assert ax is not None


# --- The elbow -------------------------------------------------------------


SSE = {1: 100.0, 2: 40.0, 3: 22.0, 4: 18.0, 5: 16.0, 6: 15.0}


def test_the_elbow_reads_a_curve_the_maximum_cannot():
    """An SSE curve has no peak; its best value is always the widest sweep."""
    assert ElbowCriterion().select(SSE) == 3


def test_the_elbow_preserves_the_candidate_type():
    """The selector hands this straight to `viz`, which checks membership."""
    assert ElbowCriterion().select(SSE) == 3
    assert isinstance(ElbowCriterion().select(SSE), int)


def test_a_bending_curve_is_conclusive():
    assert ElbowCriterion().is_conclusive(SSE)


def test_a_straight_line_has_no_elbow():
    assert not ElbowCriterion().is_conclusive({1: 10.0, 2: 8.0, 3: 6.0, 4: 4.0})


def test_the_elbow_needs_three_candidates():
    with pytest.raises(ValueError, match="at least three candidates"):
        ElbowCriterion().select({1: 10.0, 2: 4.0})


def test_the_elbow_needs_numeric_candidates():
    """It measures a distance along the swept axis, so a label has no position."""
    with pytest.raises(TypeError, match="numeric candidates"):
        ElbowCriterion().select({"a": 1.0, "b": 2.0, "c": 9.0})


def test_the_elbow_records_the_index_its_curve_came_from():
    """"The elbow" is not a result on its own; the curve is part of the finding."""
    assert ElbowCriterion(Silhouette()).base_index == "silhouette"


# --- Registration ----------------------------------------------------------


def test_both_criteria_are_registered():
    from xxcluster.core.registry import REGISTRY

    assert REGISTRY.get("max") is MaxCriterion
    assert REGISTRY.get("elbow") is ElbowCriterion