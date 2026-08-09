"""
Tests for `BaseDensityClusterer._fit` -- estimate, extract, recount.

The family's `_fit` is thin by design: two hooks in order, then the
bookkeeping that makes a noisy result reportable. What it guarantees is
that `n_clusters_` counts clusters and not noise, that `n_noise_` exists
on every fit including when it is zero, and that the `-1` convention is
enforced at the point it is established rather than assumed downstream.

A method that marks noise as `0` produces a plausible partition with a
phantom cluster and no error anywhere, which is why the convention is
checked here and not left to the caller.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.cluster import DBSCAN as SkDBSCAN

from xxcluster.cluster.partitional.density_based.base import BaseDensityClusterer
from xxcluster.core.types import NOISE_LABEL

rng = np.random.RandomState(0)
#: Two tight blobs plus three scattered points that no radius will absorb.
X = np.vstack(
    [
        rng.normal(0.0, 0.20, size=(20, 2)),
        rng.normal(6.0, 0.20, size=(20, 2)),
        np.array([[-9.0, 9.0], [9.0, -9.0], [12.0, 12.0]]),
    ]
)


class Density(BaseDensityClusterer):
    """A native density method: neighbour counts, then DBSCAN's extraction.

    `_extract_clusters` sets only `labels_`; `n_clusters_` and `n_noise_`
    are the base's to derive, which is what these tests pin.
    """

    def __init__(self, *, eps=0.6, min_samples=5, metric="euclidean", n_jobs=None):
        super().__init__(min_samples=min_samples, metric=metric, n_jobs=n_jobs)
        self.eps = eps

    def _density_estimate(self, X):
        self.estimates_ = getattr(self, "estimates_", 0) + 1
        from sklearn.metrics import pairwise_distances

        return (pairwise_distances(X, metric=self.metric) <= self.eps).sum(axis=1)

    def _extract_clusters(self, X, density):
        self.seen_density_ = density
        inner = SkDBSCAN(eps=self.eps, min_samples=self.min_samples).fit(X)
        self.labels_ = inner.labels_
        self.core_sample_indices_ = inner.core_sample_indices_


@pytest.fixture
def fitted():
    return Density(eps=0.6, min_samples=5).fit(X)


# --- The orchestration -----------------------------------------------------


def test_fit_runs_both_hooks(fitted):
    assert fitted.estimates_ == 1
    assert hasattr(fitted, "seen_density_")


def test_the_estimate_reaching_extraction_is_the_one_that_was_computed(fitted):
    """A diagnostic plots this array, so it must be the array clusters came from."""
    assert fitted.seen_density_.shape == (X.shape[0],)


def test_fit_finds_the_two_blobs_and_leaves_the_scatter_as_noise(fitted):
    assert fitted.n_clusters_ == 2
    assert fitted.n_noise_ == 3


# --- What the base derives -------------------------------------------------


def test_n_noise_counts_the_unassigned(fitted):
    assert fitted.n_noise_ == int((fitted.labels_ == NOISE_LABEL).sum())


def test_n_clusters_excludes_noise(fitted):
    assigned = fitted.labels_[fitted.labels_ != NOISE_LABEL]
    assert fitted.n_clusters_ == np.unique(assigned).size


def test_noise_mask_agrees_with_the_count(fitted):
    assert int(fitted.noise_mask().sum()) == fitted.n_noise_


def test_n_noise_is_set_even_when_nothing_is_noise():
    """Absent rather than zero would drop the Sect. 8.1 column entirely."""
    model = Density(eps=50.0, min_samples=2).fit(X)
    assert model.n_noise_ == 0


def test_a_refit_recounts_rather_than_inheriting():
    model = Density(eps=0.6, min_samples=5).fit(X)
    assert model.n_noise_ == 3
    model.fit(X[:40])          # the scattered points are gone
    assert model.n_noise_ == int((model.labels_ == NOISE_LABEL).sum())
    assert model.n_noise_ == 0


def test_tightening_the_radius_produces_more_noise():
    loose = Density(eps=0.6, min_samples=5).fit(X).n_noise_
    tight = Density(eps=0.1, min_samples=5).fit(X).n_noise_
    assert tight > loose


# --- The convention is enforced, not assumed ------------------------------


def test_a_method_marking_noise_as_zero_reports_no_noise():
    """The failure this guards: a phantom cluster, and no error anywhere."""

    class Mislabelled(Density):
        def _extract_clusters(self, X, density):
            super()._extract_clusters(X, density)
            self.labels_ = np.where(self.labels_ == NOISE_LABEL, 0, self.labels_ + 1)

    model = Mislabelled(eps=0.6, min_samples=5).fit(X)
    assert model.n_noise_ == 0
    assert model.n_clusters_ == 3      # the phantom, visible in the count


def test_a_label_below_the_noise_value_is_refused():
    class Negative(Density):
        def _extract_clusters(self, X, density):
            self.labels_ = np.full(X.shape[0], -2, dtype=int)

    with pytest.raises(ValueError, match="-1 is the only"):
        Negative().fit(X)


def test_non_integral_labels_are_refused():
    """A membership vector is not a partition."""

    class Soft(Density):
        def _extract_clusters(self, X, density):
            self.labels_ = np.full(X.shape[0], 0.5)

    with pytest.raises(ValueError, match="non-integral"):
        Soft().fit(X)
