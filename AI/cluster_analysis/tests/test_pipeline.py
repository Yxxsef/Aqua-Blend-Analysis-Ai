"""
Tests for composition and preprocessing description.

What this layer guarantees: a pipeline ending in a clusterer *is* a
clusterer, fitting it never mutates the components handed in, and a step
that cannot map unseen data makes the whole pipeline say so rather than
refit.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.cluster import KMeans as SkKMeans
from sklearn.datasets import load_iris
from sklearn.decomposition import PCA as SkPCA
from sklearn.manifold import TSNE as SkTSNE
from sklearn.preprocessing import StandardScaler

from xxcluster.core.adapters import AdaptedClusterer
from xxcluster.core.base import BaseClusterer
from xxcluster.core.mixins import InductiveMixin
from xxcluster.core.tags import Capabilities
from xxcluster.core.types import Backend
from xxcluster.pipeline.compose import ClusterPipeline, make_cluster_pipeline
from xxcluster.pipeline.preprocess import describe_preprocessing


class KMeans(InductiveMixin, AdaptedClusterer):
    _backend_import = "sklearn.cluster.KMeans"
    _fixed_params = {"n_init": 10}
    _capabilities = Capabilities(backend=Backend.SKLEARN, is_inductive=True)

    def __init__(self, n_clusters: int = 3, random_state: int | None = 0) -> None:
        self.n_clusters = n_clusters
        self.random_state = random_state

    def predict(self, X):
        return self.backend_.predict(X)


class Transductive(AdaptedClusterer):
    """A clusterer with no rule for unseen points, like most density methods."""

    _backend_import = "sklearn.cluster.DBSCAN"
    _capabilities = Capabilities(backend=Backend.SKLEARN)

    def __init__(self, eps: float = 0.8) -> None:
        self.eps = eps


@pytest.fixture(scope="module")
def X() -> np.ndarray:
    return load_iris().data


@pytest.fixture
def pipeline() -> ClusterPipeline:
    return make_cluster_pipeline(StandardScaler(), SkPCA(n_components=2), KMeans())


# --- Composition -----------------------------------------------------------


def test_a_pipeline_is_a_clusterer(pipeline, X):
    fitted = pipeline.fit(X)
    assert isinstance(fitted, BaseClusterer)
    assert fitted.labels_.shape == (X.shape[0],)
    assert fitted.n_clusters_ == 3


def test_fit_predict_works_through_the_cluster_mixin(pipeline, X):
    assert pipeline.fit_predict(X).shape == (X.shape[0],)


def test_steps_are_named_from_their_classes(pipeline):
    assert list(dict(pipeline.steps)) == ["standardscaler", "pca", "kmeans"]


def test_repeated_classes_get_distinct_names():
    steps = make_cluster_pipeline(StandardScaler(), StandardScaler(), KMeans()).steps
    assert [name for name, _ in steps] == [
        "standardscaler",
        "standardscaler-2",
        "kmeans",
    ]


def test_fitting_does_not_mutate_the_components_handed_in(pipeline, X):
    """Otherwise a sweep carries state from one candidate into the next."""
    scaler = pipeline.steps[0][1]
    pipeline.fit(X)
    assert not hasattr(scaler, "mean_")
    assert hasattr(pipeline.named_steps_["standardscaler"], "mean_")


def test_intermediate_results_stay_reachable(pipeline, X):
    fitted = pipeline.fit(X)
    assert fitted.named_steps_["pca"].n_components_ == 2


# --- Unseen data -----------------------------------------------------------


def test_transform_applies_the_preprocessing_only(pipeline, X):
    assert pipeline.fit(X).transform(X[:5]).shape == (5, 2)


def test_predict_transforms_then_assigns(pipeline, X):
    fitted = pipeline.fit(X)
    np.testing.assert_array_equal(fitted.predict(X), fitted.labels_)


def test_a_transductive_final_step_refuses_to_predict(X):
    fitted = make_cluster_pipeline(StandardScaler(), Transductive()).fit(X)
    with pytest.raises(NotImplementedError, match="transductive"):
        fitted.predict(X[:5])


def test_a_transductive_preprocessing_step_refuses_to_transform(X):
    """Refitting it would return an embedding of a model never reported."""
    fitted = make_cluster_pipeline(SkTSNE(n_components=2), KMeans()).fit(X)
    with pytest.raises(NotImplementedError, match="transductive"):
        fitted.transform(X[:5])


# --- Validation ------------------------------------------------------------


def test_an_empty_pipeline_is_refused(X):
    with pytest.raises(ValueError, match="at least a final clusterer"):
        ClusterPipeline([]).fit(X)


def test_a_pipeline_ending_in_a_transformer_is_refused(X):
    with pytest.raises(ValueError, match="not a clusterer"):
        ClusterPipeline([("scale", StandardScaler())]).fit(X)


def test_a_non_transformer_in_the_middle_is_refused(X):
    with pytest.raises(ValueError, match="not a transformer"):
        ClusterPipeline([("a", Transductive()), ("b", KMeans())]).fit(X)


def test_kmeans_in_the_middle_is_allowed(X):
    """It transforms to distance-to-centroid space, which is a real step."""
    ClusterPipeline([("a", SkKMeans(n_init=10)), ("b", KMeans())])._validate_steps()


def test_duplicate_step_names_are_refused(X):
    with pytest.raises(ValueError, match="unique"):
        ClusterPipeline(
            [("s", StandardScaler()), ("s", StandardScaler()), ("k", KMeans())]
        ).fit(X)


def test_a_bare_sklearn_clusterer_is_accepted_as_the_final_step(X):
    """Duck-typed on `fit_predict`, so composition is not limited to ours."""
    ClusterPipeline([("scale", StandardScaler()), ("k", SkKMeans(n_init=10))])._validate_steps()


# --- Description -----------------------------------------------------------


def test_describe_lists_steps_in_applied_order(pipeline, X):
    described = describe_preprocessing(pipeline.fit(X))
    assert [row["name"] for row in described] == ["standardscaler", "pca", "kmeans"]
    assert [row["position"] for row in described] == [0, 1, 2]


def test_describe_records_parameters(pipeline, X):
    described = describe_preprocessing(pipeline.fit(X))
    assert described[1]["params"]["n_components"] == 2


def test_describe_reads_invertibility_from_the_step(pipeline, X):
    described = describe_preprocessing(pipeline.fit(X))
    assert described[0]["invertible"] is True
    assert described[2]["invertible"] is False


def test_feature_preservation_is_unknown_for_a_foreign_transformer(pipeline, X):
    """Reporting an unknown as True would let PCA pass for a value-only step."""
    assert describe_preprocessing(pipeline.fit(X))[1]["preserves_features"] is None


def test_describe_accepts_a_bare_list_of_steps():
    described = describe_preprocessing([("scale", StandardScaler())])
    assert described[0]["class"] == "StandardScaler"
