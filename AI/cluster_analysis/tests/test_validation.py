"""
Tests for the validation helpers.

The precomputed-matrix checks come first and carry the most tests,
because every failure they catch produces a plausible-looking partition
rather than an exception. One test per failure mode.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.spatial.distance import squareform

from xxcluster.core.exceptions import NotFittedError
from xxcluster.core.mixins import PrecomputedMixin
from xxcluster.core.types import PrecomputedKind
from xxcluster.core.validation import (
    check_affinity_matrix,
    check_dissimilarity_matrix,
    check_kernel_matrix,
    check_labels,
    check_n_clusters,
    check_random_state,
    ensure_fitted,
)


@pytest.fixture
def D() -> np.ndarray:
    """A valid dissimilarity matrix."""
    X = np.array([[0.0, 0.0], [3.0, 4.0], [6.0, 8.0]])
    return np.linalg.norm(X[:, None, :] - X[None, :, :], axis=-1)


@pytest.fixture
def S(D: np.ndarray) -> np.ndarray:
    """A valid affinity matrix: Gaussian kernel on the distances."""
    return np.exp(-(D**2) / 50.0)


# --- Dissimilarity ---------------------------------------------------------


def test_valid_dissimilarity_passes(D):
    out = check_dissimilarity_matrix(D)
    np.testing.assert_allclose(out, D)


def test_condensed_form_is_expanded(D):
    out = check_dissimilarity_matrix(squareform(D))
    assert out.shape == D.shape
    np.testing.assert_allclose(out, D)


def test_similarity_passed_as_dissimilarity_is_caught(S):
    """The most common mistake, and silent without this check."""
    with pytest.raises(ValueError, match="non-zero diagonal"):
        check_dissimilarity_matrix(S)


def test_similarity_error_names_the_likely_cause(S):
    with pytest.raises(ValueError, match="signature of a similarity matrix"):
        check_dissimilarity_matrix(S)


def test_non_zero_diagonal_is_caught(D):
    bad = D.copy()
    bad[1, 1] = 0.5
    with pytest.raises(ValueError, match="non-zero diagonal"):
        check_dissimilarity_matrix(bad)


def test_negative_entry_is_caught(D):
    bad = D.copy()
    bad[0, 1] = bad[1, 0] = -1.0
    with pytest.raises(ValueError, match="negative entries"):
        check_dissimilarity_matrix(bad)


def test_asymmetry_is_caught_by_default(D):
    bad = D.copy()
    bad[0, 1] = 99.0
    with pytest.raises(ValueError, match="not symmetric"):
        check_dissimilarity_matrix(bad)


def test_asymmetry_allowed_when_declared(D):
    """Def. 2 permits a dissimilarity that is not a metric."""
    asym = D.copy()
    asym[0, 1] = 99.0
    out = check_dissimilarity_matrix(asym, symmetric=False)
    assert out[0, 1] == 99.0


def test_non_square_is_caught():
    with pytest.raises(ValueError, match="must be square"):
        check_dissimilarity_matrix(np.zeros((3, 4)))


def test_wrong_n_samples_is_caught(D):
    with pytest.raises(ValueError, match="observations were expected"):
        check_dissimilarity_matrix(D, n_samples=5)


def test_nan_rejected_by_default(D):
    bad = D.copy()
    bad[0, 1] = bad[1, 0] = np.nan
    with pytest.raises(ValueError, match="NaN or infinite"):
        check_dissimilarity_matrix(bad)


def test_triangle_inequality_is_not_checked():
    """Violating it is admissible under Def. 2, and O(m^3) to verify."""
    violating = np.array([[0.0, 1.0, 10.0], [1.0, 0.0, 1.0], [10.0, 1.0, 0.0]])
    check_dissimilarity_matrix(violating)


# --- Affinity --------------------------------------------------------------


def test_valid_affinity_passes(S):
    np.testing.assert_allclose(check_affinity_matrix(S), S)


def test_affinity_keeps_its_non_zero_diagonal(S):
    """The check a dissimilarity would wrongly reject."""
    assert check_affinity_matrix(S)[0, 0] == pytest.approx(1.0)


def test_negative_affinity_is_caught(S):
    bad = S.copy()
    bad[0, 1] = bad[1, 0] = -0.5
    with pytest.raises(ValueError, match="negative entries"):
        check_affinity_matrix(bad)


def test_asymmetric_affinity_is_caught(S):
    bad = S.copy()
    bad[0, 1] = 0.9
    with pytest.raises(ValueError, match="not symmetric"):
        check_affinity_matrix(bad)


# --- Kernel ----------------------------------------------------------------


def test_valid_kernel_passes(S):
    np.testing.assert_allclose(check_kernel_matrix(S), S)


def test_negative_off_diagonal_is_allowed():
    """A linear kernel on centred data routinely produces them."""
    X = np.array([[-1.0, 0.0], [1.0, 0.0], [0.0, 2.0]])
    K = X @ X.T
    assert K.min() < 0
    np.testing.assert_allclose(check_kernel_matrix(K), K)


def test_negative_diagonal_is_caught(S):
    bad = S.copy()
    bad[1, 1] = -1.0
    with pytest.raises(ValueError, match="negative diagonal"):
        check_kernel_matrix(bad)


def test_asymmetric_kernel_is_caught(S):
    bad = S.copy()
    bad[0, 1] = 0.9
    with pytest.raises(ValueError, match="not symmetric"):
        check_kernel_matrix(bad)


# --- Mixin dispatch --------------------------------------------------------


class _Dissimilarity(PrecomputedMixin):
    def __init__(self, metric="euclidean"):
        self.metric = metric


class _Affinity(PrecomputedMixin):
    _precomputed_kind = PrecomputedKind.AFFINITY
    _precomputed_param = "affinity"

    def __init__(self, affinity="rbf"):
        self.affinity = affinity


class _Kernel(PrecomputedMixin):
    _precomputed_kind = PrecomputedKind.KERNEL
    _precomputed_param = "kernel"

    def __init__(self, kernel="rbf"):
        self.kernel = kernel


@pytest.mark.parametrize(
    "cls,param",
    [(_Dissimilarity, "metric"), (_Affinity, "affinity"), (_Kernel, "kernel")],
)
def test_is_precomputed_reads_the_declared_parameter(cls, param):
    assert not cls()._is_precomputed()
    assert cls(**{param: "precomputed"})._is_precomputed()


def test_dispatch_rejects_a_similarity_for_a_dissimilarity_method(S):
    with pytest.raises(ValueError, match="non-zero diagonal"):
        _Dissimilarity()._check_precomputed(S)


def test_dispatch_accepts_the_same_matrix_as_an_affinity(S):
    """The conflation this dispatch exists to prevent."""
    np.testing.assert_allclose(_Affinity()._check_precomputed(S), S)


def test_dispatch_accepts_a_signed_kernel():
    X = np.array([[-1.0, 0.0], [1.0, 0.0], [0.0, 2.0]])
    K = X @ X.T
    np.testing.assert_allclose(_Kernel()._check_precomputed(K), K)


def test_dispatch_passes_n_samples_through(D):
    with pytest.raises(ValueError, match="observations were expected"):
        _Dissimilarity()._check_precomputed(D, n_samples=7)


# --- Labels ----------------------------------------------------------------


def test_labels_pass_through_as_integers():
    assert check_labels([0, 1, 2]).dtype.kind == "i"


def test_integral_floats_are_accepted_and_converted():
    """A label vector via a DataFrame column arrives as float, unchanged in meaning."""
    labels = check_labels(np.array([0.0, 1.0, -1.0]))
    assert labels.dtype.kind == "i"
    np.testing.assert_array_equal(labels, [0, 1, -1])


def test_non_integral_values_are_refused():
    """Truncating these would silently defuzzify a membership vector."""
    with pytest.raises(ValueError, match="membership vector"):
        check_labels([0.0, 0.6, 1.0])


def test_a_membership_matrix_is_refused():
    with pytest.raises(ValueError, match="one-dimensional"):
        check_labels(np.zeros((4, 3)))


def test_string_labels_are_refused():
    with pytest.raises(ValueError, match="integer cluster indices"):
        check_labels(["a", "b"])


def test_wrong_length_is_caught():
    with pytest.raises(ValueError, match="length 3"):
        check_labels([0, 1, 2], n_samples=5)


def test_noise_is_allowed_by_default():
    np.testing.assert_array_equal(check_labels([-1, 0, 1]), [-1, 0, 1])


def test_noise_is_refused_where_the_consumer_is_undefined_on_it():
    with pytest.raises(ValueError, match="handles_noise"):
        check_labels([-1, 0, 1], allow_noise=False)


def test_labels_below_the_noise_label_are_caught():
    with pytest.raises(ValueError, match="only"):
        check_labels([-2, 0, 1])


# --- Number of clusters ----------------------------------------------------


def test_valid_n_clusters_passes():
    assert check_n_clusters(3, n_samples=10) == 3


def test_one_cluster_is_refused():
    """Not a partition, and every validity index is undefined on it."""
    with pytest.raises(ValueError, match="at least 2"):
        check_n_clusters(1)


def test_n_clusters_above_the_sample_size_is_caught():
    with pytest.raises(ValueError, match="exceeds"):
        check_n_clusters(11, n_samples=10)


@pytest.mark.parametrize("value", [3.0, "3", None, True])
def test_non_integer_n_clusters_is_refused(value):
    with pytest.raises(ValueError, match="must be an integer"):
        check_n_clusters(value)


# --- Seeds -----------------------------------------------------------------


def test_generator_passes_through_unchanged():
    """scikit-learn's own helper rejects it; `Seed` admits it."""
    rng = np.random.default_rng(0)
    assert check_random_state(rng) is rng


def test_int_becomes_a_legacy_random_state():
    assert isinstance(check_random_state(0), np.random.RandomState)


def test_none_yields_a_usable_state():
    assert check_random_state(None).rand() is not None


# --- Fitted checks ---------------------------------------------------------


def test_ensure_fitted_passes_when_attributes_are_present():
    class Fitted:
        labels_ = np.array([0, 1])

    ensure_fitted(Fitted(), "labels_")


def test_ensure_fitted_names_what_is_missing():
    class Unfitted:
        pass

    with pytest.raises(NotFittedError, match="labels_"):
        ensure_fitted(Unfitted(), "labels_")


def test_ensure_fitted_falls_back_to_the_declaration():
    """So the check stays correct as a class's `_required_fitted` grows."""

    class Declared:
        @classmethod
        def _required_fitted_attributes(cls):
            return ("labels_", "n_clusters_")

    with pytest.raises(NotFittedError, match="n_clusters_"):
        ensure_fitted(Declared())
