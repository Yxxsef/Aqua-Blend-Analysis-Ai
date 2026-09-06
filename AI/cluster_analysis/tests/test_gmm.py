"""
Tests for the Gaussian mixture adapter (Task 42).

`n_parameters_` is the one quantity this adapter computes rather than
copies from the backend, so it gets the most scrutiny here: cross-checked
against scikit-learn's own (private) `_n_parameters()` across every
`covariance_type`, then checked in the place it actually matters -- that
`bic`/`aic` agree with the backend's own `bic(X)`/`aic(X)`, not merely that
the parameter count matches in isolation.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.datasets import make_blobs
from sklearn.utils.estimator_checks import check_estimator

from xxcluster.cluster.partitional.model_based.gmm import GaussianMixture
from xxcluster.core.registry import REGISTRY
from xxcluster.core.types import Assignment


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def blobs() -> np.ndarray:
    """Three well-separated blobs -- enough structure for BIC to prefer the
    true component count over an obviously wrong one, without needing a
    hand-rolled mixture sampler.
    """
    X, _ = make_blobs(n_samples=300, n_features=4, centers=3, random_state=0)
    return X


@pytest.fixture(scope="module")
def known_mixture() -> tuple[np.ndarray, int]:
    """A synthetic draw from a mixture whose true component count is known,
    for the "BIC selects a sensible |C|" check the task sheet asks for
    directly, rather than inferring "sensible" from an unrelated dataset.
    """
    rng = np.random.default_rng(0)
    true_k = 3
    means = rng.uniform(-15, 15, size=(true_k, 2))
    draws = [
        rng.normal(loc=means[i], scale=0.6, size=(150, 2)) for i in range(true_k)
    ]
    X = np.vstack(draws)
    return X, true_k


# ---------------------------------------------------------------------------
# Contract basics: fit produces what BaseClusterer + BasePartitionalClusterer
# require, correctly, not just present.
# ---------------------------------------------------------------------------
class TestContractCompliance:
    def test_fit_sets_labels_of_the_right_shape(self, blobs):
        model = GaussianMixture(n_clusters=3, random_state=0).fit(blobs)
        assert model.labels_.shape == (blobs.shape[0],)

    def test_n_clusters_matches_the_request(self, blobs):
        model = GaussianMixture(n_clusters=3, random_state=0).fit(blobs)
        assert model.n_clusters_ == 3

    def test_criterion_mirrors_the_backends_lower_bound(self, blobs):
        model = GaussianMixture(n_clusters=3, random_state=0).fit(blobs)
        assert model.criterion_ == model.backend_.lower_bound_

    def test_n_iter_and_converged_are_set(self, blobs):
        model = GaussianMixture(n_clusters=3, random_state=0, max_iter=200).fit(blobs)
        assert isinstance(model.n_iter_, int)
        assert isinstance(model.converged_, bool)

    def test_is_fitted_is_false_before_fit_and_true_after(self, blobs):
        model = GaussianMixture(n_clusters=3)
        assert model.is_fitted is False
        model.fit(blobs)
        assert model.is_fitted is True

    def test_capabilities_declare_probabilistic_assignment(self):
        caps = GaussianMixture.capabilities()
        assert caps.assignment is Assignment.PROBABILISTIC
        assert caps.is_inductive is True
        assert caps.requires_n_clusters is True
        assert caps.handles_noise is False

    def test_capabilities_declare_handles_missing_and_categorical_explicitly(self):
        """Both must be *declared*, not left at the Capabilities() default --
        GUIDELINES/00-the-contract.md, rule 4: a field left at its default
        is a claim, not a blank."""
        caps = GaussianMixture.capabilities()
        assert caps.handles_missing is False
        assert caps.handles_categorical is False

    def test_complexity_fields_are_declared(self):
        caps = GaussianMixture.capabilities()
        assert caps.time_complexity
        assert caps.space_complexity
        assert caps.scales_to is not None


# ---------------------------------------------------------------------------
# predict / predict_proba -- "Done when" criterion 1
# ---------------------------------------------------------------------------
class TestProbabilisticAssignment:
    def test_predict_proba_rows_sum_to_one(self, blobs):
        model = GaussianMixture(n_clusters=3, random_state=0).fit(blobs)
        proba = model.predict_proba(blobs)
        assert proba.shape == (blobs.shape[0], 3)
        np.testing.assert_allclose(proba.sum(axis=1), 1.0, rtol=1e-6)

    def test_predict_equals_predict_proba_argmax(self, blobs):
        model = GaussianMixture(n_clusters=3, random_state=0).fit(blobs)
        proba = model.predict_proba(blobs)
        predicted = model.predict(blobs)
        np.testing.assert_array_equal(predicted, np.argmax(proba, axis=1))

    def test_labels_from_fit_agree_with_a_fresh_predict(self, blobs):
        """labels_ is set inside _fit by calling backend_.predict(X) directly,
        not through the public predict() -- confirm the two give the same
        answer on the training data, since that equivalence is exactly what
        the _fit override assumes.
        """
        model = GaussianMixture(n_clusters=3, random_state=0).fit(blobs)
        np.testing.assert_array_equal(model.labels_, model.predict(blobs))


# ---------------------------------------------------------------------------
# n_parameters_ -- cross-checked against scikit-learn's own private
# _n_parameters(), across every covariance_type, the same way linkage
# criteria are checked against SciPy's reference implementation (Task 31).
# ---------------------------------------------------------------------------
class TestParameterCount:
    @pytest.mark.parametrize(
        "covariance_type", ["full", "tied", "diag", "spherical"]
    )
    def test_n_parameters_matches_the_backends_own_count(self, blobs, covariance_type):
        model = GaussianMixture(
            n_clusters=3, covariance_type=covariance_type, random_state=0
        ).fit(blobs)
        assert model.n_parameters_ == model.backend_._n_parameters()

    def test_full_covariance_has_more_parameters_than_diagonal(self, blobs):
        """Sanity check on the direction, not just the count: a full
        covariance matrix is always at least as expensive as a diagonal
        one for n_features > 1, and strictly more here.
        """
        full = GaussianMixture(n_clusters=3, covariance_type="full", random_state=0).fit(blobs)
        diag = GaussianMixture(n_clusters=3, covariance_type="diag", random_state=0).fit(blobs)
        assert full.n_parameters_ > diag.n_parameters_

    def test_bic_matches_the_backends_own_bic(self, blobs):
        """The point of n_parameters_ existing at all: ProbabilisticMixin.bic
        must agree with the backend's own bic(X), not merely compute *a*
        number that happens to look plausible.
        """
        model = GaussianMixture(n_clusters=3, random_state=0).fit(blobs)
        assert model.bic(blobs) == pytest.approx(model.backend_.bic(blobs))

    def test_aic_matches_the_backends_own_aic(self, blobs):
        model = GaussianMixture(n_clusters=3, random_state=0).fit(blobs)
        assert model.aic(blobs) == pytest.approx(model.backend_.aic(blobs))


# ---------------------------------------------------------------------------
# BIC selects a sensible |C| -- "Done when" criterion 2, on a fixture whose
# true component count is known, not inferred after the fact.
# ---------------------------------------------------------------------------
class TestBicModelSelection:
    def test_bic_prefers_the_true_component_count(self, known_mixture):
        X, true_k = known_mixture
        candidates = range(2, 7)
        scores = {
            k: GaussianMixture(n_clusters=k, random_state=0, n_init=3).fit(X).bic(X)
            for k in candidates
        }
        best_k = min(scores, key=scores.get)
        assert best_k == true_k, (
            f"BIC selected {best_k}, expected the true count {true_k}. "
            f"Scores: {scores}"
        )


# ---------------------------------------------------------------------------
# sample() -- "Deliverables: including a sample reproducibility test"
# ---------------------------------------------------------------------------
class TestSampling:
    def test_sample_returns_draws_and_component_labels(self, blobs):
        model = GaussianMixture(n_clusters=3, random_state=0).fit(blobs)
        draws, components = model.sample(50)
        assert draws.shape == (50, blobs.shape[1])
        assert components.shape == (50,)
        assert set(np.unique(components)).issubset({0, 1, 2})

    def test_sample_is_reproducible_from_the_same_seed(self, blobs):
        """Reproducible here because sklearn's own check_random_state(int)
        constructs a fresh, independent generator on every call rather than
        advancing one shared stream -- verified directly against the real
        backend before writing this test. The "restores the borrowed seed"
        test below checks something different and still real: that the
        wrapper puts the attribute back, which matters the moment
        random_state is ever an already-instantiated generator instead of
        a plain int, since *that* kind does carry state across calls.
        """
        model = GaussianMixture(n_clusters=3, random_state=0).fit(blobs)
        draws_a, components_a = model.sample(20, random_state=7)
        draws_b, components_b = model.sample(20, random_state=7)
        np.testing.assert_array_equal(draws_a, draws_b)
        np.testing.assert_array_equal(components_a, components_b)

    def test_sample_restores_the_borrowed_seed(self, blobs):
        """BaseMixtureClusterer.sample borrows backend_.random_state for the
        call and restores it afterwards -- confirm it actually does, since
        leaving it changed would make the *next* unseeded draw depend on
        this one.
        """
        model = GaussianMixture(n_clusters=3, random_state=0).fit(blobs)
        original_state = model.backend_.random_state
        model.sample(10, random_state=99)
        assert model.backend_.random_state == original_state


# ---------------------------------------------------------------------------
# Registration and scikit-learn conformance
# ---------------------------------------------------------------------------
class TestRegistrationAndConformance:
    def test_registered_under_the_documented_name(self):
        assert REGISTRY.get("gaussian_mixture") is GaussianMixture

    def test_mro_reaches_the_adapter_before_the_family_base(self):
        """GUIDELINES/00-the-contract.md, rule 7: the adapter must come
        first, so AdaptedClusterer._fit resolves before the family base's
        NotImplementedError-raising native hooks.
        """
        mro_names = [c.__name__ for c in GaussianMixture.__mro__]
        assert mro_names.index("AdaptedClusterer") < mro_names.index(
            "BaseMixtureClusterer"
        )

    def test_conforms_to_check_estimator(self):
        # EM restarts are unseeded by default across sklearn's own internal
        # checks unless random_state is fixed; check_estimator handles
        # cloning, so a fixed seed here is enough for reproducible checks.
        check_estimator(GaussianMixture(n_clusters=2, random_state=0))


# ---------------------------------------------------------------------------
# covariance_type variation -- confirms the parameter is real, not decorative
# ---------------------------------------------------------------------------
class TestCovarianceType:
    @pytest.mark.parametrize(
        "covariance_type", ["full", "tied", "diag", "spherical"]
    )
    def test_every_covariance_type_fits(self, blobs, covariance_type):
        model = GaussianMixture(
            n_clusters=3, covariance_type=covariance_type, random_state=0
        ).fit(blobs)
        assert model.is_fitted
        assert model.covariance_type == covariance_type
