"""
Tests for the figures.

Plots are not asserted pixel by pixel. What is checked is the reporting
discipline the module docstrings commit to: noise drawn distinctly rather
than as a cluster, a selection marked on its own curve, and a
feature-level reading refused where the technique does not support one.
"""

from __future__ import annotations

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

from scipy.cluster.hierarchy import linkage  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402

from xxcluster.evaluation.report import profile_clusters  # noqa: E402
from xxcluster.viz.dendrogram import plot_dendrogram, plot_merge_heights  # noqa: E402
from xxcluster.viz.diagnostics import (  # noqa: E402
    plot_cluster_profiles,
    plot_selection_curve,
    plot_silhouette,
    plot_stability,
)
from xxcluster.viz.embedding import (  # noqa: E402
    plot_component_loadings,
    plot_embedding,
    plot_feature_pairs,
)


@pytest.fixture
def X() -> np.ndarray:
    rng = np.random.default_rng(0)
    return np.vstack([rng.normal(0, 0.4, (20, 3)), rng.normal(4, 0.4, (20, 3))])


@pytest.fixture
def labels() -> np.ndarray:
    return np.array([0] * 20 + [1] * 20)


@pytest.fixture
def Z(X: np.ndarray) -> np.ndarray:
    return linkage(X, "ward")


# --- Dendrograms -----------------------------------------------------------


def test_dendrogram_accepts_a_bare_linkage_matrix(Z):
    """So a stored linkage replots without rebuilding the model."""
    assert plot_dendrogram(Z) is not None


def test_dendrogram_accepts_a_fitted_model(Z):
    class Fitted:
        linkage_ = Z

    assert plot_dendrogram(Fitted()) is not None


def test_dendrogram_rejects_something_that_is_not_a_linkage():
    with pytest.raises(ValueError, match="linkage matrix"):
        plot_dendrogram(np.zeros((5, 2)))


def test_cut_height_is_drawn_with_the_colouring(Z):
    """A coloured tree without its cut line invites inferring the cut."""
    ax = plot_dendrogram(Z, color_threshold=5.0)
    assert any(line.get_linestyle() == "--" for line in ax.lines)


def test_merge_heights_read_as_clusters_remaining(Z):
    ax = plot_merge_heights(Z)
    assert ax.get_xlabel() == "clusters remaining"
    assert ax.xaxis_inverted()


# --- Selection curves ------------------------------------------------------


def test_selection_curve_marks_the_choice():
    ax = plot_selection_curve({2: 0.68, 3: 0.55, 4: 0.5}, selected=2, criterion="max")
    assert any(line.get_linestyle() == "--" for line in ax.lines)


def test_selection_curve_is_drawn_without_a_selection():
    """An inconclusive curve is the finding; hiding it manufactures a result."""
    assert plot_selection_curve({2: 0.5, 3: 0.5, 4: 0.5}) is not None


def test_a_selection_outside_the_sweep_is_caught():
    with pytest.raises(ValueError, match="not among the swept"):
        plot_selection_curve({2: 0.5, 3: 0.4}, selected=9)


def test_an_empty_curve_is_refused():
    with pytest.raises(ValueError, match="nothing was swept"):
        plot_selection_curve({})


# --- Silhouette ------------------------------------------------------------


def test_silhouette_plots_per_observation(X, labels):
    assert plot_silhouette(X, labels) is not None


def test_noise_is_excluded_and_declared(X, labels):
    """The silhouette is undefined on observations in no cluster."""
    noisy = labels.copy()
    noisy[:4] = -1
    ax = plot_silhouette(X, noisy)
    assert "4 noise observations excluded" in ax.get_xlabel()


def test_no_noise_means_no_caveat(X, labels):
    assert "excluded" not in plot_silhouette(X, labels).get_xlabel()


# --- Embeddings ------------------------------------------------------------


def test_embedding_labels_the_components_plotted(X, labels):
    ax = plot_embedding(PCA(n_components=3).fit_transform(X), labels, components=(0, 2))
    assert ax.get_xlabel() == "component 0"
    assert ax.get_ylabel() == "component 2"


def test_noise_is_drawn_as_its_own_series(X, labels):
    noisy = labels.copy()
    noisy[:4] = -1
    ax = plot_embedding(PCA(n_components=2).fit_transform(X), noisy)
    assert "noise" in [text.get_text() for text in ax.get_legend().get_texts()]


def test_requesting_a_component_that_does_not_exist_is_caught(X):
    with pytest.raises(ValueError, match="only 2"):
        plot_embedding(PCA(n_components=2).fit_transform(X), components=(0, 5))


def test_provenance_is_shown_on_the_figure(X):
    ax = plot_embedding(
        PCA(n_components=2).fit_transform(X), annotate={"technique": "PCA", "seed": 0}
    )
    assert "technique=PCA" in ax.get_title()


def test_loadings_are_available_for_a_linear_technique(X):
    assert plot_component_loadings(PCA(n_components=2).fit(X)) is not None


def test_loadings_are_refused_for_a_nonlinear_embedding():
    """A feature-level reading the technique does not support."""

    class Manifold:
        embedding_ = np.zeros((10, 2))

    with pytest.raises(NotImplementedError, match="linear techniques only"):
        plot_component_loadings(Manifold())


def test_feature_pairs_returns_a_square_grid(X, labels):
    frame = pd.DataFrame(X, columns=["a", "b", "c"])
    assert plot_feature_pairs(frame, labels).shape == (3, 3)


def test_feature_pairs_can_be_restricted(X, labels):
    frame = pd.DataFrame(X, columns=["a", "b", "c"])
    assert plot_feature_pairs(frame, labels, features=["a", "b"]).shape == (2, 2)


def test_one_feature_cannot_be_paired(X, labels):
    with pytest.raises(ValueError, match="at least two"):
        plot_feature_pairs(pd.DataFrame(X[:, :1], columns=["a"]), labels)


# --- Profiles and stability ------------------------------------------------


def test_cluster_profiles_plot_separation(X, labels):
    frame = pd.DataFrame(X, columns=["a", "b", "c"])
    ax = plot_cluster_profiles(profile_clusters(frame, labels))
    assert "standard deviations" in ax.get_ylabel()


def test_cluster_profiles_reject_an_unrelated_frame():
    with pytest.raises(ValueError, match="profile_clusters"):
        plot_cluster_profiles(pd.DataFrame({"a": [1, 2]}))


def test_stability_plots_the_distribution_not_the_mean():
    """A high mean with a wide spread is not stability."""

    class Analysis:
        agreements_ = np.random.default_rng(0).beta(8, 2, 45)

    ax = plot_stability(Analysis())
    assert ax.get_ylabel() == "pairs"
    assert any("mean" in text.get_text() for text in ax.get_legend().get_texts())
