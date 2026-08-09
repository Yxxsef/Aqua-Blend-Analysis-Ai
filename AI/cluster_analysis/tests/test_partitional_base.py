"""
Tests for `BasePartitionalClusterer._fit` -- the restart loop.

The loop is shared by every native partitional method, so what it
guarantees is what those methods may assume: that restarts are seeded from
one value and replay, that the retained restart is the best one in the
direction the class declares, and that a method supplying only its own
iteration gets the rest of the contract filled in.

The direction is the case worth pinning hardest. A comparison the wrong way
round returns the worst restart of the batch and nothing downstream can
tell -- there is no exception, only a poorer number.
"""

from __future__ import annotations

import numpy as np
import pytest

from xxcluster.cluster.partitional.base import BasePartitionalClusterer
from xxcluster.core.exceptions import ContractViolationError

X = np.array([[0.0, 0.0], [1.0, 1.0], [8.0, 8.0], [9.0, 9.0]])


class Toy(BasePartitionalClusterer):
    """A native method whose criterion is drawn from its restart's seed.

    Deliberately not a real algorithm: the point is to observe which
    restart the loop keeps, so `_fit_once` records every value it produced
    in `seen_` and the tests assert the winner against that list.
    """

    def _fit_once(self, X, random_state):
        value = float(random_state.uniform())
        self.__dict__.setdefault("seen_", []).append(value)
        return {
            "labels_": (X[:, 0] > X[:, 0].mean()).astype(int),
            "criterion_": value,
            "n_iter_": 1,
            "converged_": True,
        }


class Maximising(Toy):
    """The same method, reporting a criterion that improves upwards."""

    _criterion_higher_is_better = True


# --- What the loop guarantees ---------------------------------------------


def test_fit_sets_every_attribute_the_chain_declares():
    model = Toy(n_init=3, random_state=0).fit(X)
    for name in Toy._required_fitted_attributes():
        assert hasattr(model, name), name


def test_the_same_seed_replays_exactly():
    a = Toy(n_init=5, random_state=0).fit(X)
    b = Toy(n_init=5, random_state=0).fit(X)
    assert a.seen_ == b.seen_
    assert a.criterion_ == b.criterion_


def test_a_different_seed_gives_a_different_run():
    a = Toy(n_init=5, random_state=0).fit(X)
    b = Toy(n_init=5, random_state=1).fit(X)
    assert a.seen_ != b.seen_


def test_every_restart_gets_its_own_seed():
    model = Toy(n_init=8, random_state=0).fit(X)
    assert len(model.seen_) == 8
    assert len(set(model.seen_)) == 8, "two restarts drew the same stream"


def test_seeds_are_drawn_before_fitting_begins():
    """Restart i is the same run whatever happened in restart i-1."""
    assert Toy(n_init=1, random_state=0).fit(X).seen_[0] == pytest.approx(
        Toy(n_init=9, random_state=0).fit(X).seen_[0]
    )


# --- Direction -------------------------------------------------------------


def test_the_minimum_is_retained_by_default():
    model = Toy(n_init=12, random_state=0).fit(X)
    assert model.criterion_ == min(model.seen_)


def test_the_maximum_is_retained_where_the_class_declares_it():
    model = Maximising(n_init=12, random_state=0).fit(X)
    assert model.criterion_ == max(model.seen_)


def test_more_restarts_never_return_a_worse_criterion():
    few = Toy(n_init=1, random_state=0).fit(X).criterion_
    many = Toy(n_init=20, random_state=0).fit(X).criterion_
    assert many <= few


def test_a_finite_criterion_beats_a_non_finite_one_whichever_ran_first():
    """Every comparison against NaN is False, so this needs its own guard."""

    class LeadingNaN(Toy):
        def _fit_once(self, X, random_state):
            result = dict(super()._fit_once(X, random_state))
            if len(self.seen_) == 1:
                result["criterion_"] = float("nan")
            return result

    model = LeadingNaN(n_init=4, random_state=0).fit(X)
    assert np.isfinite(model.criterion_)


# --- What `_derive_fitted` fills in ---------------------------------------


def test_n_clusters_is_derived_from_the_labels():
    model = Toy(n_init=2, random_state=0).fit(X)
    assert model.n_clusters_ == np.unique(model.labels_).size


def test_n_clusters_is_recomputed_rather_than_left_from_an_earlier_fit():
    class OneCluster(Toy):
        def _fit_once(self, X, random_state):
            return dict(super()._fit_once(X, random_state),
                        labels_=np.zeros(X.shape[0], dtype=int))

    model = Toy(n_init=1, random_state=0).fit(X)
    assert model.n_clusters_ == 2
    model.__class__ = OneCluster
    model.fit(X)
    assert model.n_clusters_ == 1


# --- What the loop refuses -------------------------------------------------


def test_fit_once_must_return_a_mapping():
    class Wrong(Toy):
        def _fit_once(self, X, random_state):
            return np.zeros(3)

    with pytest.raises(ContractViolationError, match="mapping"):
        Wrong().fit(X)


def test_fit_once_must_report_a_criterion():
    class NoCriterion(Toy):
        def _fit_once(self, X, random_state):
            return {"labels_": np.zeros(X.shape[0], dtype=int)}

    with pytest.raises(ContractViolationError, match="criterion_"):
        NoCriterion().fit(X)


@pytest.mark.parametrize("n_init", ["auto", 0, -1, 2.5, True])
def test_n_init_must_be_a_positive_integer_for_a_native_method(n_init):
    with pytest.raises(ValueError, match="n_init"):
        Toy(n_init=n_init).fit(X)


def test_n_init_is_not_validated_on_the_shared_parameter_path():
    """A backend may accept spellings we do not, such as `n_init="auto"`.

    Validating in `_validate_params` would reject the value before the
    adapted method ever reached its backend, so the check belongs in the
    loop that actually uses it.
    """
    model = Toy(n_init="auto")
    model._validate_params()  # must not raise


# --- The adapted route bypasses all of the above --------------------------


def test_an_adapted_method_never_reaches_the_restart_loop():
    from xxcluster.cluster.partitional.sse_based.kmeans import KMeans
    from xxcluster.core.adapters import AdaptedClusterer

    assert KMeans._fit is AdaptedClusterer._fit
    assert KMeans(n_clusters=2, n_init="auto").fit(X).n_clusters_ == 2
