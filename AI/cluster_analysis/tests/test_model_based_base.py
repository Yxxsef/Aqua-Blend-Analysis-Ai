"""
Tests for `BaseModelBasedClusterer` / `BaseMixtureClusterer`.

The family delegates to the fitted model rather than reimplementing an
assignment rule, so a method supplies the model and inherits `predict`,
`predict_proba`, `score_samples` and `sample`. Delegation is what keeps
the crisp and the soft answer from disagreeing, and that is pinned first.

`sample` carries the weight for scenario generation: it must return the
component each draw came from, replay from a seed, and leave the model's
own seed as it found it -- a borrowed seed left in place would make the
next draw depend on this one.

This family also declares the opposite comparison direction from the SSE
default, since a log-likelihood improves upwards.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.mixture import GaussianMixture

from xxcluster.cluster.partitional.model_based.base import (
    BaseMixtureClusterer,
    BaseModelBasedClusterer,
)
from xxcluster.core.exceptions import NotFittedError
from xxcluster.core.tags import Capabilities
from xxcluster.core.types import Assignment

rng = np.random.RandomState(0)
X = np.vstack([rng.normal(loc, 0.5, size=(40, 2)) for loc in (0.0, 6.0)])


class Mixture(BaseMixtureClusterer):
    """A native mixture: fits scikit-learn's EM and hands over the model."""

    _capabilities = Capabilities(assignment=Assignment.PROBABILISTIC, is_inductive=True)

    def _fit_once(self, X, random_state):
        model = GaussianMixture(
            n_components=self.n_clusters,
            covariance_type=self.covariance_type,
            max_iter=self.max_iter,
            tol=self.tol,
            n_init=1,
            random_state=int(random_state.randint(2**31 - 1)),
        ).fit(X)
        return {
            "model_": model,
            "labels_": model.predict(X),
            "memberships_": model.predict_proba(X),
            "criterion_": float(model.score(X)),
            "n_iter_": int(model.n_iter_),
            "converged_": bool(model.converged_),
            "n_parameters_": int(model._n_parameters()),
        }


@pytest.fixture
def fitted():
    return Mixture(n_clusters=2, n_init=2, random_state=0).fit(X)


# --- Delegation ------------------------------------------------------------


def test_predict_proba_rows_are_a_distribution(fitted):
    proba = fitted.predict_proba(X)
    assert proba.shape == (X.shape[0], 2)
    np.testing.assert_allclose(proba.sum(axis=1), 1.0)


def test_predict_is_the_argmax_of_predict_proba(fitted):
    """Both come from the model, so the crisp and soft answers agree."""
    np.testing.assert_array_equal(
        fitted.predict(X), np.argmax(fitted.predict_proba(X), axis=1)
    )


def test_score_samples_returns_one_log_likelihood_per_observation(fitted):
    assert fitted.score_samples(X).shape == (X.shape[0],)


def test_the_information_criteria_are_finite(fitted):
    assert np.isfinite(fitted.bic(X)) and np.isfinite(fitted.aic(X))


def test_predict_assigns_unseen_observations(fitted):
    assert fitted.predict(np.array([[0.1, 0.1], [6.1, 5.9]])).shape == (2,)


def test_the_feature_count_is_checked_against_the_fit(fitted):
    with pytest.raises(ValueError, match="features"):
        fitted.predict(X[:, :1])


def test_an_adapted_model_is_reached_through_backend(fitted):
    """`model_` for a native method, `backend_` for an adapted one."""
    del fitted.model_
    fitted.backend_ = GaussianMixture(n_components=2, random_state=0).fit(X)
    assert fitted.predict(X).shape == (X.shape[0],)


def test_with_neither_model_nor_backend_it_is_not_fitted():
    with pytest.raises(NotFittedError, match="model_"):
        Mixture(n_clusters=2)._model()


# --- Sampling --------------------------------------------------------------


def test_sample_returns_the_draws_and_their_components(fitted):
    draws, components = fitted.sample(30, random_state=7)
    assert draws.shape == (30, 2)
    assert set(np.unique(components)) <= {0, 1}


def test_sample_replays_from_a_seed(fitted):
    first, comp_first = fitted.sample(30, random_state=7)
    again, comp_again = fitted.sample(30, random_state=7)
    np.testing.assert_array_equal(first, again)
    np.testing.assert_array_equal(comp_first, comp_again)


def test_a_different_seed_gives_a_different_draw(fitted):
    assert not np.array_equal(
        fitted.sample(30, random_state=7)[0], fitted.sample(30, random_state=8)[0]
    )


def test_sample_restores_the_seed_it_borrowed(fitted):
    """Leaving it set would make the next draw depend on this one."""
    before = fitted._model().random_state
    fitted.sample(5, random_state=999)
    assert fitted._model().random_state == before


def test_sample_does_not_clip_to_a_feasible_region(fitted):
    """Unbounded support is the model's; clipping here would hide it.

    A scenario generator rejects and redraws, and reports the rate. Moving
    a draw onto a boundary instead would pile probability mass there and
    whatever consumes the sample would take it at face value.
    """
    draws, _ = fitted.sample(2000, random_state=0)
    assert draws.min() < X.min() or draws.max() > X.max()


# --- Direction -------------------------------------------------------------


def test_this_family_maximises_its_criterion():
    assert BaseModelBasedClusterer._criterion_higher_is_better is True


def test_the_best_restart_is_the_most_likely_one():
    model = Mixture(n_clusters=4, n_init=6, random_state=3).fit(X)
    single = Mixture(n_clusters=4, n_init=1, random_state=3).fit(X)
    assert model.criterion_ >= single.criterion_
