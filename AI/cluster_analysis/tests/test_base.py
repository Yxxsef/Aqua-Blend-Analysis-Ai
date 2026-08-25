"""
Tests for the `BaseComponent.fit` template method.

`fit` is the one place every component is validated, so what it guarantees
is what the rest of the package may assume: parameters checked,
declarations honoured, input validated and recorded, fitted state present.
Each test pins one of those guarantees.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.base import clone

from xxcluster.core.base import BaseClusterer, BaseComponent
from xxcluster.core.exceptions import ContractViolationError
from xxcluster.core.mixins import PrecomputedMixin
from xxcluster.core.tags import Capabilities
from xxcluster.core.types import Assignment, PrecomputedKind

X = np.array([[0.0, 0.0], [1.0, 1.0], [8.0, 8.0], [9.0, 9.0]])


class Dummy(BaseClusterer):
    """A minimal well-behaved clusterer: splits on the first feature."""

    def __init__(self, n_clusters: int = 2) -> None:
        self.n_clusters = n_clusters

    def _fit(self, X, y=None, **fit_params) -> None:
        self.labels_ = (X[:, 0] > X[:, 0].mean()).astype(int)
        self.n_clusters_ = int(self.labels_.max()) + 1


class Forgetful(Dummy):
    """Sets `labels_` but not `n_clusters_` -- the omission `_check_fitted` exists for."""

    def _fit(self, X, y=None, **fit_params) -> None:
        self.labels_ = np.zeros(X.shape[0], dtype=int)


# --- The guarantees --------------------------------------------------------


def test_fit_returns_self():
    est = Dummy()
    assert est.fit(X) is est


def test_fit_records_n_features_in():
    assert Dummy().fit(X).n_features_in_ == 2


def test_fit_delegates_to_private_fit():
    np.testing.assert_array_equal(Dummy().fit(X).labels_, [0, 0, 1, 1])


def test_no_fitted_state_before_fit():
    est = Dummy()
    assert not est.is_fitted
    assert not hasattr(est, "labels_")


def test_is_fitted_after_fit():
    assert Dummy().fit(X).is_fitted


def test_missing_fitted_attribute_is_caught():
    with pytest.raises(ContractViolationError, match="did not set: n_clusters_"):
        Forgetful().fit(X)


def test_fit_predict_works_through_the_template():
    """ClusterMixin.fit_predict routes through our fit."""
    np.testing.assert_array_equal(Dummy().fit_predict(X), [0, 0, 1, 1])


def test_params_round_trip_so_clone_works():
    est = Dummy(n_clusters=5)
    assert clone(est).get_params() == {"n_clusters": 5}


def test_nan_rejected_by_default():
    bad = X.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError, match="[Nn]a[Nn]"):
        Dummy().fit(bad)


def test_nan_allowed_when_declared():
    class Tolerant(Dummy):
        _capabilities = Capabilities(handles_missing=True)

    bad = X.copy()
    bad[0, 0] = np.nan
    assert Tolerant().fit(bad).is_fitted


# --- Capability declarations ----------------------------------------------


def test_declaring_inductive_without_predict_is_caught():
    class Liar(Dummy):
        _capabilities = Capabilities(is_inductive=True)

    with pytest.raises(ContractViolationError, match="is_inductive"):
        Liar().fit(X)


def test_declaring_soft_assignment_without_predict_proba_is_caught():
    class Liar(Dummy):
        _capabilities = Capabilities(assignment=Assignment.FUZZY)

    with pytest.raises(ContractViolationError, match="predict_proba"):
        Liar().fit(X)


def test_backed_declaration_passes():
    class Honest(Dummy):
        _capabilities = Capabilities(is_inductive=True)

        def predict(self, X):
            return np.zeros(len(X), dtype=int)

    assert Honest().fit(X).is_fitted


def test_undeclared_capability_is_not_an_error():
    """One direction only: a class may expose more than it advertises."""

    class Quiet(Dummy):
        def predict(self, X):
            return np.zeros(len(X), dtype=int)

    assert Quiet().fit(X).is_fitted


def test_capabilities_accessor():
    assert Dummy.capabilities() is Dummy._capabilities


# --- Required-attribute collection ----------------------------------------


def test_required_fitted_accumulates_down_the_mro():
    class Density(Dummy):
        _required_fitted = ("n_noise_",)

    assert set(Density._required_fitted_attributes()) == {
        "labels_",
        "n_clusters_",
        "n_noise_",
    }


def test_inherited_requirement_is_still_enforced():
    class Density(Dummy):
        _required_fitted = ("n_noise_",)

    with pytest.raises(ContractViolationError, match="n_noise_"):
        Density().fit(X)


# --- The precomputed route -------------------------------------------------


class Precomputed(PrecomputedMixin, Dummy):
    _capabilities = Capabilities(supports_precomputed=True)

    def __init__(self, n_clusters: int = 2, metric: str = "euclidean") -> None:
        super().__init__(n_clusters=n_clusters)
        self.metric = metric

    def _fit(self, X, y=None, **fit_params) -> None:
        self.labels_ = np.zeros(X.shape[0], dtype=int)
        self.n_clusters_ = 1


def _distances() -> np.ndarray:
    return np.linalg.norm(X[:, None, :] - X[None, :, :], axis=-1)


def test_feature_matrix_route_when_not_precomputed():
    assert Precomputed().fit(X).n_features_in_ == 2


def test_precomputed_route_validates_the_matrix():
    est = Precomputed(metric="precomputed")
    assert est.fit(_distances()).n_features_in_ == 4


def test_precomputed_route_rejects_a_similarity():
    """A feature-matrix check would have accepted this silently."""
    similarity = np.exp(-(_distances() ** 2))
    with pytest.raises(ValueError, match="non-zero diagonal"):
        Precomputed(metric="precomputed").fit(similarity)


def test_precomputed_route_rejects_a_non_square_matrix():
    with pytest.raises(ValueError, match="must be square"):
        Precomputed(metric="precomputed").fit(X)


def test_declaring_precomputed_without_the_mixin_is_caught():
    class Liar(Dummy):
        _capabilities = Capabilities(supports_precomputed=True)

    with pytest.raises(ContractViolationError, match="supports_precomputed"):
        Liar().fit(X)


# --- Parameter constraints -------------------------------------------------


def test_sklearn_parameter_constraints_are_applied_when_declared():
    from sklearn.utils._param_validation import Interval
    from numbers import Integral

    class Constrained(Dummy):
        _parameter_constraints = {"n_clusters": [Interval(Integral, 2, None, closed="left")]}

    assert Constrained(n_clusters=3).fit(X).is_fitted
    with pytest.raises(ValueError, match="n_clusters"):
        Constrained(n_clusters=1).fit(X)


def test_absent_constraints_do_not_break_fit():
    """BaseEstimator._validate_params assumes an attribute we may not have."""
    assert not hasattr(Dummy, "_parameter_constraints")
    assert Dummy().fit(X).is_fitted


def test_abstract_fit_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseComponent()


# --- Conformance -----------------------------------------------------------


def test_template_method_produces_a_conformant_sklearn_estimator():
    """The whole point of inheriting BaseEstimator, asserted end to end.

    A component that does nothing but override `_fit` passes scikit-learn's
    full estimator check suite, so `Pipeline`, `clone` and the `*SearchCV`
    classes work on anything built on this contract.

    If a future scikit-learn adds a check we fail, that is worth knowing:
    record the exclusion deliberately rather than loosening the contract.
    """
    from sklearn.utils.estimator_checks import check_estimator

    check_estimator(Dummy())
