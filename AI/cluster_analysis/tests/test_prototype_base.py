"""
Tests for `BasePrototypeClusterer` -- the inductive interface.

`predict` and `transform` are pure geometry once the prototypes exist, so
they belong to the family rather than to each method. What that buys is
pinned here: a method supplying only `_fit_once` can assign unseen
observations, and the two entry points cannot disagree with each other
because one is defined in terms of the other.

Also the home of the `check_estimator` run over the adapted K-Means. It
lives with the prototype family because K-Means is the only registered
member, and its known divergences are recorded as `expected_failed_checks`
rather than skipped -- a skipped estimator is an unchecked one.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import pairwise_distances

from xxcluster.cluster.partitional.sse_based.base import BasePrototypeClusterer
from xxcluster.cluster.partitional.sse_based.kmeans import KMeans
from xxcluster.core.exceptions import NotFittedError

X = np.array(
    [[0.0, 0.0], [0.5, 0.4], [1.0, 1.0], [8.0, 8.0], [8.5, 8.4], [9.0, 9.0]]
)


class Lloyd(BasePrototypeClusterer):
    """A native prototype method: assignment and mean update, nothing else.

    Writes `_fit_once` only -- the restart loop, `predict`, `transform` and
    the `inertia_` derivation are all the family's.
    """

    def _initialise(self, X, random_state):
        return X[random_state.choice(X.shape[0], self.n_clusters, replace=False)]

    def _assign(self, X, centers):
        return np.argmin(
            pairwise_distances(X, centers, metric=self._check_metric()), axis=1
        )

    def _update_centers(self, X, labels):
        return np.stack(
            [
                X[labels == c].mean(axis=0) if (labels == c).any() else X[c]
                for c in range(self.n_clusters)
            ]
        )

    def _fit_once(self, X, random_state):
        centers = self._initialise(X, random_state)
        labels = self._assign(X, centers)
        for n_iter in range(1, self.max_iter + 1):
            centers = self._update_centers(X, labels)
            updated = self._assign(X, centers)
            if np.array_equal(updated, labels):
                break
            labels = updated
        sse = float(
            sum(((X[labels == c] - centers[c]) ** 2).sum() for c in range(self.n_clusters))
        )
        return {
            "labels_": labels,
            "cluster_centers_": centers,
            "criterion_": sse,
            "n_iter_": n_iter,
            "converged_": True,
        }


@pytest.fixture
def fitted():
    return Lloyd(n_clusters=2, n_init=3, random_state=0).fit(X)


# --- What the family provides ---------------------------------------------


def test_predict_reproduces_the_training_labels(fitted):
    np.testing.assert_array_equal(fitted.predict(X), fitted.labels_)


def test_transform_returns_one_distance_per_prototype(fitted):
    assert fitted.transform(X).shape == (X.shape[0], 2)


def test_predict_is_the_argmin_of_transform(fitted):
    """Defined in terms of each other, so they cannot drift apart."""
    np.testing.assert_array_equal(
        np.argmin(fitted.transform(X), axis=1), fitted.predict(X)
    )


def test_predict_assigns_unseen_observations(fitted):
    unseen = np.array([[0.2, 0.1], [8.8, 8.9]])
    np.testing.assert_array_equal(
        fitted.predict(unseen), fitted.predict(X)[[0, -1]]
    )


def test_inertia_mirrors_the_family_criterion(fitted):
    """One quantity, two names -- scikit-learn's and the family's."""
    assert fitted.inertia_ == fitted.criterion_


# --- What it refuses -------------------------------------------------------


def test_predict_before_fit_raises_not_fitted():
    with pytest.raises(NotFittedError):
        Lloyd(n_clusters=2).predict(X)


def test_the_feature_count_is_checked_against_the_fit(fitted):
    with pytest.raises(ValueError, match="features"):
        fitted.predict(X[:, :1])


def test_a_precomputed_metric_is_refused_by_name():
    """Silently falling back to Euclidean would report a measure that never ran."""
    with pytest.raises(NotImplementedError, match="precomputed"):
        Lloyd(n_clusters=2, metric="precomputed").fit(X)


def test_prototypes_given_as_row_indices_are_refused(fitted):
    """A medoid method records rows in `medoid_indices_`, not here."""
    fitted.cluster_centers_ = np.array([0, 3])
    with pytest.raises(ValueError, match="medoid_indices_"):
        fitted.transform(X)


# --- The adapted K-Means overrides the family, and stays conformant -------


def test_the_adapted_kmeans_keeps_its_own_predict_and_transform():
    assert KMeans.predict is not BasePrototypeClusterer.predict
    assert KMeans.transform is not BasePrototypeClusterer.transform


def test_the_adapted_kmeans_passes_check_estimator():
    """Known divergences are recorded, not skipped.

    Both exclusions are scikit-learn's own `KMeans` failing a check
    scikit-learn wrote; they are not ours to fix, and silencing the whole
    estimator to hide them would stop the other checks running too.
    """
    from sklearn.utils.estimator_checks import check_estimator

    check_estimator(
        KMeans(),
        expected_failed_checks={
            "check_sample_weight_equivalence_on_dense_data": (
                "sklearn's own KMeans fails this; not introduced by the adapter"
            ),
            "check_sample_weight_equivalence_on_sparse_data": (
                "sklearn's own KMeans fails this; not introduced by the adapter"
            ),
        },
    )
