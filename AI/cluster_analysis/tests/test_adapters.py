"""
Tests for the backend adapters.

What this layer guarantees: our parameter and attribute names reach a
third-party estimator unchanged in meaning, the contract attributes exist
whichever backend was used, and a transductive technique refuses unseen
data rather than refitting.

Fitted against real scikit-learn estimators, since the disagreements the
adapter exists to absorb are properties of actual backends.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.datasets import load_iris

from xxcluster.core.adapters import AdaptedClusterer, AdaptedDimReducer
from xxcluster.core.exceptions import BackendUnavailableError, ContractViolationError
from xxcluster.core.mixins import InductiveMixin, NoiseAwareMixin
from xxcluster.core.tags import Capabilities
from xxcluster.core.types import Backend, Family, SubFamily


@pytest.fixture(scope="module")
def X() -> np.ndarray:
    return load_iris().data


class KMeans(InductiveMixin, AdaptedClusterer):
    _backend_import = "sklearn.cluster.KMeans"
    _fixed_params = {"n_init": 10}
    _capabilities = Capabilities(
        family=Family.PARTITIONAL,
        subfamily=SubFamily.SSE_BASED,
        backend=Backend.SKLEARN,
        is_inductive=True,
        requires_n_clusters=True,
    )

    def __init__(self, n_clusters: int = 3, random_state: int | None = 0) -> None:
        self.n_clusters = n_clusters
        self.random_state = random_state

    def predict(self, X):
        return self.backend_.predict(X)


class DBSCAN(NoiseAwareMixin, AdaptedClusterer):
    _backend_import = "sklearn.cluster.DBSCAN"
    _param_map = {"radius": "eps"}
    _capabilities = Capabilities(
        family=Family.PARTITIONAL,
        subfamily=SubFamily.DENSITY_BASED,
        backend=Backend.SKLEARN,
        handles_noise=True,
    )

    def __init__(self, radius: float = 0.5, min_samples: int = 5) -> None:
        self.radius = radius
        self.min_samples = min_samples


class PCA(AdaptedDimReducer):
    _backend_import = "sklearn.decomposition.PCA"
    _capabilities = Capabilities(backend=Backend.SKLEARN, is_inductive=True)


class TSNE(AdaptedDimReducer):
    _backend_import = "sklearn.manifold.TSNE"
    _capabilities = Capabilities(backend=Backend.SKLEARN, is_inductive=False)


# --- Backend loading -------------------------------------------------------


def test_missing_backend_names_the_package_to_install(X):
    class Absent(AdaptedClusterer):
        _backend_import = "hdbscan.HDBSCAN"

        def __init__(self) -> None:
            pass

    with pytest.raises(BackendUnavailableError, match="pip install hdbscan"):
        Absent().fit(X)


def test_renamed_backend_class_is_reported_as_such(X):
    class Moved(AdaptedClusterer):
        _backend_import = "sklearn.cluster.KMeansPlusPlus"

        def __init__(self) -> None:
            pass

    with pytest.raises(BackendUnavailableError, match="API has changed"):
        Moved().fit(X)


def test_backend_is_not_imported_until_fit():
    """An optional dependency must not break `import xxcluster`."""

    class Absent(AdaptedClusterer):
        _backend_import = "umap.UMAP"

        def __init__(self) -> None:
            pass

    Absent()  # constructing is enough to prove no import happened


# --- Parameter translation -------------------------------------------------


def test_our_name_reaches_the_backend_under_its_name(X):
    model = DBSCAN(radius=0.8).fit(X)
    assert model.backend_.eps == 0.8


def test_fixed_params_are_applied(X):
    assert KMeans().fit(X).backend_.n_init == 10


def test_a_parameter_mapped_to_none_is_dropped(X):
    class Capped(KMeans):
        _param_map = {"random_state": None}

    assert Capped().fit(X).backend_.random_state is None


def test_a_stale_param_map_is_reported_against_the_adapter(X):
    class Stale(AdaptedClusterer):
        _backend_import = "sklearn.cluster.KMeans"

        def __init__(self, nonsense: int = 1) -> None:
            self.nonsense = nonsense

    with pytest.raises(ContractViolationError, match="_param_map"):
        Stale().fit(X)


# --- Fitted attributes -----------------------------------------------------


def test_declared_attributes_are_copied_from_the_backend(X):
    model = KMeans().fit(X)
    np.testing.assert_array_equal(model.labels_, model.backend_.labels_)


def test_n_clusters_is_derived_where_the_backend_omits_it(X):
    """scikit-learn reports labels but never how many clusters resulted."""
    assert KMeans(n_clusters=4).fit(X).n_clusters_ == 4


def test_noise_is_excluded_from_the_cluster_count(X):
    model = DBSCAN().fit(X)
    assert -1 in model.labels_
    assert model.n_clusters_ == len(set(model.labels_)) - 1


def test_noise_is_counted_for_a_noise_aware_method(X):
    model = DBSCAN().fit(X)
    assert model.n_noise_ == int(np.sum(model.labels_ == -1))
    assert model.noise_mask().sum() == model.n_noise_


def test_a_method_without_noise_awareness_gets_no_noise_count(X):
    assert not hasattr(KMeans().fit(X), "n_noise_")


def test_backend_stays_reachable_for_what_is_not_surfaced(X):
    assert KMeans().fit(X).backend_.inertia_ > 0


# --- Dimensionality reduction ----------------------------------------------


def test_embedding_and_its_width_are_set(X):
    model = PCA(n_components=2).fit(X)
    assert model.embedding_.shape == (X.shape[0], 2)
    assert model.n_components_ == 2


def test_inductive_technique_maps_unseen_data(X):
    assert PCA(n_components=2).fit(X).transform(X[:5]).shape == (5, 2)


def test_transductive_technique_refuses_unseen_data(X):
    """Refitting would return an embedding from a model never reported."""
    model = TSNE(n_components=2).fit(X)
    with pytest.raises(NotImplementedError, match="transductive"):
        model.transform(X[:5])


def test_transductive_technique_still_exposes_its_own_embedding(X):
    assert TSNE(n_components=2).fit(X).embedding_.shape == (X.shape[0], 2)


# --- Contract --------------------------------------------------------------


def test_an_inductive_reducer_satisfies_the_capability_check(X):
    """`is_inductive` is `transform` for a reducer, `predict` for a clusterer."""
    PCA(n_components=2).fit(X)


def test_declaring_noise_without_the_interface_is_caught(X):
    class Liar(AdaptedClusterer):
        _backend_import = "sklearn.cluster.KMeans"
        _capabilities = Capabilities(handles_noise=True)

        def __init__(self) -> None:
            pass

    with pytest.raises(ContractViolationError, match="handles_noise"):
        Liar().fit(X)
