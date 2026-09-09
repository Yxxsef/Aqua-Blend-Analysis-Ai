"""
Tests for the K-Means adapter.

`metric` is exposed by the family but dropped before the backend sees it,
since scikit-learn's K-Means is Euclidean-only. The one thing this class
must not do is accept a measure it will not use.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.datasets import load_iris

from xxcluster.cluster.partitional.sse_based.kmeans import KMeans


@pytest.fixture(scope="module")
def X() -> np.ndarray:
    return load_iris().data


def test_a_measure_the_backend_will_not_use_is_refused(X):
    with pytest.raises(ValueError, match="metric"):
        KMeans(n_clusters=3, metric="manhattan").fit(X)


def test_the_default_and_an_explicit_euclidean_both_fit(X):
    assert KMeans(n_clusters=3).fit(X).n_clusters_ == 3
    assert KMeans(n_clusters=3, metric="euclidean").fit(X).n_clusters_ == 3


def test_the_refused_value_still_round_trips_through_get_params():
    """Deferred to `fit` so that `clone` and `check_estimator` still work."""
    assert KMeans(metric="manhattan").get_params()["metric"] == "manhattan"
