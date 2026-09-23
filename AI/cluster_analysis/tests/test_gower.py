"""Task 34: independent values, estimator contract and clustering evidence."""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose, assert_array_equal
from scipy import sparse
from sklearn.base import clone
from sklearn.cluster import AgglomerativeClustering
from sklearn.exceptions import NotFittedError
from sklearn.metrics import adjusted_rand_score
from sklearn.utils.estimator_checks import check_estimator

from xxcluster.core.registry import REGISTRY
from xxcluster.core.types import ComponentKind
from xxcluster.core.validation import check_dissimilarity_matrix
from xxcluster.measures.dissimilarity import Gower


def test_registry_and_declarations():
    assert REGISTRY.get("gower", kind=ComponentKind.DISSIMILARITY) is Gower
    assert "_kind" not in Gower.__dict__
    assert not Gower.is_metric
    assert Gower.is_symmetric and Gower.accepts_missing and Gower.accepts_categorical
    assert Gower.bounded == (0.0, 1.0)
    assert "gower" in REGISTRY.applicable(handles_missing=True, handles_categorical=True)


def test_full_sklearn_conformance():
    check_estimator(Gower())  # no exclusions or blanket skips


def test_clone_preserves_constructor_parameters_without_fitted_state():
    types = ["numeric", "ordinal"]
    weights = [2.0, 1.0]
    orders = {1: ["low", "high"]}
    g = Gower(feature_types=types, weights=weights, ordinal_categories=orders)
    assert g.feature_types is types and g.weights is weights and g.ordinal_categories is orders
    assert not g.is_fitted
    assert clone(g).get_params() == g.get_params()
    g.fit([[0, "low"], [10, "high"]])
    assert not clone(g).is_fitted
    assert not hasattr(clone(g), "ranges_")


@pytest.mark.parametrize("call", [lambda g: g.pairwise([[0]]), lambda g: g([0], [1])])
def test_unfitted_calls_fail(call):
    with pytest.raises(NotFittedError):
        call(Gower())


def test_hand_calculated_mixed_weighted_distances():
    X = np.array([[0, "river", 0], [10, "river", 1], [5, "ground", 0]], dtype=object)
    g = Gower(feature_types=["numeric", "categorical", "symmetric_binary"], weights=[2, 1, 1]).fit(X)
    # AB=(2*1 + 0 + 1)/4; AC=(2*.5 + 1 + 0)/4;
    # BC=(2*.5 + 1 + 1)/4. Expected values are calculated independently.
    expected = np.array([[0, .75, .5], [.75, 0, .75], [.5, .75, 0]])
    assert_allclose(g.pairwise(X), expected)
    assert_allclose(g.pairwise(X, X[:2]), expected[:, :2])
    for i in range(3):
        for j in range(3):
            assert g(X[i], X[j]) == pytest.approx(expected[i, j])
    assert isinstance(g(X[0], X[1]), float)


def test_missing_omits_weight_from_numerator_and_denominator():
    X = [[0, "a", 0], [10, None, 1], [5, "b", 0]]
    g = Gower(feature_types=["numeric", "categorical", "symmetric_binary"], weights=[2, 1, 1]).fit(X)
    assert g(X[0], X[1]) == pytest.approx(1.0)  # (2 + 1)/(2 + 1)
    assert g(X[1], X[2]) == pytest.approx(2 / 3)  # (2*.5 + 1)/3


def test_scalar_mixed_lists_preserve_numeric_versus_string_categories():
    X = [[0, 1, "a"], [10, "1", "a"]]
    g = Gower(feature_types=["numeric", "categorical", "categorical"]).fit(X)
    assert g(X[0], X[1]) == pytest.approx(2 / 3)
    assert_allclose(g.pairwise(X)[0, 1], g(X[0], X[1]))


def test_missingness_breaks_triangle_and_identity():
    X = np.array([[0, 0, np.nan], [0, np.nan, 0], [np.nan, 1, 0], [1, 1, 1]])
    D = Gower().fit(X).pairwise(X)
    assert_allclose([D[0, 1], D[1, 2], D[0, 2]], [0, 0, 1])
    assert D[0, 2] > D[0, 1] + D[1, 2]
    assert not np.array_equal(X[0], X[1], equal_nan=True) and D[0, 1] == 0
    check_dissimilarity_matrix(D)  # the non-metric dissimilarity remains admissible


def test_asymmetric_joint_absence_changes_result():
    X = [[0, 0], [1, 0], [0, 1]]
    sym = Gower(feature_types=["numeric", "symmetric_binary"]).fit(X)
    asym = Gower(feature_types=["numeric", "asymmetric_binary"]).fit(X)
    assert sym(X[0], X[1]) == pytest.approx(.5)
    assert asym(X[0], X[1]) == pytest.approx(1.0)
    assert asym(X[0], X[2]) == pytest.approx(.5)


def test_pure_asymmetric_binary_matches_jaccard():
    X = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 1]])
    g = Gower(feature_types=["asymmetric_binary"] * 3).fit(X)
    for i, j in combinations(range(len(X)), 2):
        a, b = set(np.flatnonzero(X[i])), set(np.flatnonzero(X[j]))
        assert g(X[i], X[j]) == pytest.approx(1 - len(a & b) / len(a | b))
    assert g(X[0], X[0]) == 0


@pytest.mark.parametrize("kind", ["symmetric_binary", "asymmetric_binary"])
@pytest.mark.parametrize("invalid", [2, -.1, "yes"])
def test_invalid_binary_values_fail(kind, invalid):
    with pytest.raises(ValueError):
        Gower(feature_types=[kind]).fit([[0], [invalid]])


def test_declared_ordinal_levels_not_nominal_codes():
    X = [["low"], ["medium"], ["high"]]
    g = Gower(feature_types=["ordinal"], ordinal_categories={0: ["low", "medium", "high"]}).fit(X)
    assert_allclose(g.pairwise(X), [[0, .5, 1], [.5, 0, .5], [1, .5, 0]])
    # A level absent in training is allowed when it is in the declared schema.
    g.fit([["low"], ["high"]])
    assert g(["low"], ["medium"]) == pytest.approx(.5)
    with pytest.raises(ValueError, match="Unknown ordinal"):
        g.pairwise([["very high"]])


@pytest.mark.parametrize("orders", [None, {}, {1: ["a", "b"]}, {0: ["a", "a"]},
                                    {0: []}, {0: ["a", None]}, {0: {"a", "b"}}, {0: "ab"}])
def test_ordinal_schema_errors(orders):
    with pytest.raises(ValueError):
        Gower(feature_types=["ordinal"], ordinal_categories=orders).fit([["a"], ["b"]])


def test_no_implicit_categorical_type_inference():
    with pytest.raises(ValueError, match="requires numeric"):
        Gower().fit([[0, "a"], [1, "b"]])
    # Numeric-looking category codes remain nominal when explicitly declared.
    g = Gower(feature_types=["categorical"]).fit([[10], [20], [100]])
    assert g([10], [20]) == g([10], [100]) == 1


def test_unseen_nominal_levels_compare_by_equality():
    g = Gower(feature_types=["categorical"]).fit([["a"], ["b"]])
    assert g(["c"], ["a"]) == 1
    assert g(["c"], ["c"]) == 0


def test_zero_range_and_all_missing_columns_are_excluded():
    X = [[0, 4, None], [10, 4, None]]
    g = Gower().fit(X)
    assert_array_equal(g.active_, [True, False, False])
    assert_allclose(g.ranges_, [10, 0, np.nan])
    assert g(X[0], X[1]) == 1  # no dilution by the constant feature
    assert g([0, 999, 20], [10, -20, 90]) == 1  # no query-based activation


@pytest.mark.parametrize("X", [[[2, 2], [2, 2]], [[None, np.nan], [pd.NA, None]]])
def test_identical_uninformative_vectors_have_zero_distance_in_every_path(X):
    g = Gower().fit(X)
    assert_allclose(g.pairwise(X), np.zeros((2, 2)))
    assert_allclose(g.pairwise(X, X), np.zeros((2, 2)))
    assert g(X[0], X[1]) == 0


def test_single_level_ordinal_is_excluded():
    g = Gower(feature_types=["numeric", "ordinal"], ordinal_categories={1: ["only"]})
    X = [[0, "only"], [10, "only"]]
    assert g.fit(X)(X[0], X[1]) == 1


def test_no_overlap_is_an_explicit_error_not_an_invented_distance():
    g = Gower().fit([[0, 0], [1, 1]])
    for X, Y in [([[0, None]], [[None, 1]]), ([[None, None]], [[1, 1]])]:
        with pytest.raises(ValueError, match="No comparable positive-weight"):
            g.pairwise(X, Y)
    with pytest.raises(ValueError, match="No comparable positive-weight"):
        g.pairwise([[0, None], [None, 1]])


def test_ranges_fitted_once_batch_invariance_and_saturation():
    g = Gower().fit([[0], [10]])
    assert g([0], [5]) == .5
    assert g([0], [20]) == 1
    ranges = g.ranges_.copy()
    assert_allclose(g.pairwise([[0], [5]], [[0], [5], [100]])[:, :2], [[0, .5], [.5, 0]])
    assert_array_equal(g.ranges_, ranges)


def test_positive_numeric_affine_rescaling_with_refit():
    X = np.array([[1., 2], [4, 5], [6, 3]])
    Z = X * [1000, .01] + [-20, 3]
    assert_allclose(Gower().fit(X).pairwise(X), Gower().fit(Z).pairwise(Z))


def test_refit_replaces_ranges_and_schema():
    g = Gower().fit([[0], [10]])
    assert g.fit([[0], [100]])([0], [5]) == .05
    g.set_params(feature_types=["categorical"]).fit([["a"], ["b"]])
    assert np.isnan(g.ranges_[0]) and g(["a"], ["b"]) == 1


def test_failed_refit_does_not_report_fitted():
    g = Gower().fit([[0], [1]])
    g.set_params(weights=[-1])
    with pytest.raises(ValueError):
        g.fit([[0], [1]])
    assert not g.is_fitted
    with pytest.raises(NotFittedError):
        g.pairwise([[0], [1]])


@pytest.mark.parametrize("weights", [[-1, 1], [0, 0], [1], [1, np.nan], [1, np.inf], [[1, 1]]])
def test_invalid_weights_checked_at_fit(weights):
    g = Gower(weights=weights)
    with pytest.raises(ValueError, match="weights"):
        g.fit([[0, 0], [1, 1]])


def test_weight_scaling_and_zero_weight():
    X = [[0, 0], [10, 100]]
    assert Gower(weights=[1, 0]).fit(X)([0, 0], [0, 100]) == 0
    for weights in [[1, 1], [1e308, 1e308], [1e-300, 1e-300]]:
        assert Gower(weights=weights).fit(X)(X[0], X[1]) == 1


@pytest.mark.parametrize("types", ["numeric", ["numeric"], ["number", "categorical"], [None, "numeric"]])
def test_invalid_types(types):
    with pytest.raises(ValueError, match="feature_types"):
        Gower(feature_types=types).fit([[0, 0], [1, 1]])


@pytest.mark.parametrize("bad", [np.inf, -np.inf, complex(1, 2)])
def test_nonfinite_and_complex_rejected_at_fit_and_query(bad):
    with pytest.raises(ValueError):
        Gower().fit([[0], [bad]])
    with pytest.raises(ValueError):
        Gower().fit([[0], [1]]).pairwise([[bad]])


def test_string_nan_is_not_silently_treated_as_missing_numeric():
    with pytest.raises(ValueError, match="non-finite"):
        Gower().fit([["nan"], [0]])


def test_sparse_rejected():
    with pytest.raises(TypeError, match="[Ss]parse"):
        Gower().fit(sparse.csr_matrix([[0], [1]]))


def test_dataframe_nullable_values_names_and_no_mutation():
    frame = pd.DataFrame({"number": pd.Series([0, pd.NA, 10], dtype="Float64"),
                          "category": pd.Series(["a", "a", "b"], dtype="string")})
    original = frame.copy(deep=True)
    g = Gower(feature_types=["numeric", "categorical"]).fit(frame)
    D = g.pairwise(frame)
    assert_allclose(D, [[0, 0, 1], [0, 0, 1], [1, 1, 0]])
    assert_array_equal(g.feature_names_in_, frame.columns)
    assert g(frame.iloc[0], frame.iloc[2]) == D[0, 2]
    pd.testing.assert_frame_equal(frame, original)
    with pytest.raises(ValueError, match="feature names"):
        g.pairwise(frame.iloc[:, ::-1])
    with pytest.warns(UserWarning, match="feature names"):
        with pytest.raises(ValueError, match="features"):
            g.pairwise(np.zeros((2, 3)))


def test_randomised_mixed_distances_against_independent_scalar_formula():
    rng = np.random.default_rng(34)
    X = np.empty((24, 3), dtype=object)
    X[:, 0] = rng.uniform(-2, 8, len(X))  # always observed: every pair comparable
    X[:, 1] = rng.choice(["a", "b", None], len(X))
    X[:, 2] = rng.choice([0, 1, None], len(X))
    g = Gower(feature_types=["numeric", "categorical", "asymmetric_binary"], weights=[2, 3, 4]).fit(X)
    D = g.pairwise(X)
    extent = max(X[:, 0]) - min(X[:, 0])
    for i, j in combinations(range(len(X)), 2):
        terms = [(2, abs(X[i, 0] - X[j, 0]) / extent)]
        if X[i, 1] is not None and X[j, 1] is not None:
            terms.append((3, int(X[i, 1] != X[j, 1])))
        if X[i, 2] is not None and X[j, 2] is not None and (X[i, 2] or X[j, 2]):
            terms.append((4, int(X[i, 2] != X[j, 2])))
        expected = sum(w * delta for w, delta in terms) / sum(w for w, _ in terms)
        assert D[i, j] == pytest.approx(expected)
    assert_allclose(D, D.T)
    assert_array_equal(np.diag(D), np.zeros(len(X)))
    assert (D >= 0).all() and (D <= 1).all()


def test_incomplete_data_clusters_without_imputation_and_ward_backend_refuses():
    X = np.array([[0, "a"], [.1, None], [.2, "a"], [9.8, "b"], [9.9, None], [10, "b"]], dtype=object)
    original = pd.DataFrame(X.copy())
    D = Gower(feature_types=["numeric", "categorical"]).fit(X).pairwise(X)
    check_dissimilarity_matrix(D)
    labels = AgglomerativeClustering(n_clusters=2, linkage="average", metric="precomputed").fit_predict(D)
    assert adjusted_rand_score([0, 0, 0, 1, 1, 1], labels) == 1
    pd.testing.assert_frame_equal(pd.DataFrame(X), original)
    assert pd.isna(X).sum() == 2
    # This proves backend Euclidean-only rejection, NOT an xxcluster
    # is_metric guard. Keep the latter as its own dependency check below.
    with pytest.raises(ValueError, match="(?i)euclidean"):
        AgglomerativeClustering(n_clusters=2, linkage="ward", metric="precomputed").fit(D)


def test_task40_ward_is_metric_gate_when_registered():
    # Filtered by kind, not by bare name: Task 31 registers a Ward *linkage
    # criterion* under "ward" as well, and constructing that as a clusterer
    # fails with `WardLinkage() takes no arguments` rather than skipping.
    # What this test needs is Task 40's Ward *method*.
    from xxcluster.core.types import ComponentKind

    if "ward" not in REGISTRY.names(kind=ComponentKind.CLUSTERER):
        pytest.skip("Task 40: no registered Ward implementation; is_metric gate cannot yet be exercised.")
    X = np.array([[0., 0], [0, 1], [1, 0], [1, 1]])
    measure = Gower().fit(X)
    ward = REGISTRY.create("ward", n_clusters=2, metric=measure)
    with pytest.raises(ValueError, match="(?i)is_metric|non.metric|requires.*metric"):
        ward.fit(X)
