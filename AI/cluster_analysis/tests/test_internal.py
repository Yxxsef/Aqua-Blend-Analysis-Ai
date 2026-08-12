import numpy as np
import pytest

from xxcluster.measures.validation.internal import (
    CalinskiHarabasz,
    DaviesBouldin,
)


@pytest.fixture
def simple_partition():
    X = np.array([
        [0.0, 0.0],
        [0.1, 0.2],
        [5.0, 5.0],
        [5.1, 5.2],
    ])
    labels = np.array([0, 0, 1, 1])
    return X, labels


def test_calinski_harabasz_returns_float(simple_partition):
    X, labels = simple_partition
    score = CalinskiHarabasz().score(X, labels)

    assert isinstance(score, float)


def test_davies_bouldin_returns_float(simple_partition):
    X, labels = simple_partition
    score = DaviesBouldin().score(X, labels)

    assert isinstance(score, float)


def test_calinski_harabasz_refuses_one_cluster(simple_partition):
    X, _ = simple_partition
    labels = np.zeros(len(X), dtype=int)

    with pytest.raises(ValueError, match="at least two clusters"):
        CalinskiHarabasz().score(X, labels)


def test_davies_bouldin_refuses_one_cluster(simple_partition):
    X, _ = simple_partition
    labels = np.zeros(len(X), dtype=int)

    with pytest.raises(ValueError, match="at least two clusters"):
        DaviesBouldin().score(X, labels)


@pytest.mark.parametrize(
    "index",
    [CalinskiHarabasz(), DaviesBouldin()],
)
def test_internal_indices_refuse_noise(simple_partition, index):
    X, labels = simple_partition
    noisy_labels = labels.copy()
    noisy_labels[0] = -1

    with pytest.raises(ValueError):
        index.score(X, noisy_labels)


def test_davies_bouldin_is_minimised():
    assert DaviesBouldin.higher_is_better is False


def test_internal_indices_declare_shape():
    assert CalinskiHarabasz.assumes_shape == "compact, isotropic"
    assert DaviesBouldin.assumes_shape == "compact, isotropic"