"""
Base classes for nonlinear techniques.

Nonlinearity is one property; the manifold hypothesis is a different and
stronger assumption, and only some nonlinear techniques make it. Sect. 6.2
treats it as a topic in its own right, while Sect. 6.4 is the broader
family, so the classes here are split the same way:

    BaseNonlinearReducer     the family; assumes only that the map is not
                             a linear projection
    ├── BaseManifoldReducer  neighbour-embedding; assumes the data lie on
    │                        a low-dimensional manifold and tries to
    │                        recover coordinates on it
    └── BaseKernelReducer    kernel methods; assume a feature map induced
                             by a kernel, and no manifold at all

Kernel PCA is why the distinction is load-bearing rather than pedantic. It
is nonlinear, but it is inductive, deterministic, has an eigenvalue
spectrum rather than a stress, takes a kernel matrix rather than a
neighbourhood graph, and has no `n_neighbors`. A manifold base class
declaring the opposite of each of those would be wrong about every one.

A technique that is neither -- a parametric autoencoder, say, which is
inductive and has a true decoder rather than a pre-image approximation --
subclasses `BaseNonlinearReducer` directly, or gets a third sibling if
several arrive.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ...core.base import BaseDimReducer
from ...core.mixins import PrecomputedMixin
from ...core.types import (
    ArrayLike,
    Embedding,
    MatrixLike,
    MetricLike,
    PrecomputedKind,
    Seed,
)


class BaseNonlinearReducer(BaseDimReducer, ABC):
    """A technique whose mapping is not a linear projection.

    Holds only what nonlinearity itself implies, which is less than it
    seems. It does not assume a manifold, a neighbourhood, a kernel, a
    stochastic optimisation, or transductivity: each of those belongs to a
    subfamily, and a technique that does not make the assumption must not
    inherit a class that states it.

    What does follow from nonlinearity, and applies to every subclass:
    distances in the embedding are not the input distances. Neighbourhood
    structure may be preserved while global geometry, cluster sizes and
    apparent density are not -- so a validity index computed on the
    embedding measures the embedding, not the data.

    Fitted attributes
    -----------------
    embedding_ : ndarray of shape (m, n_components)
        Coordinates of the fitted sample; the primary output.
    """

    @abstractmethod
    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Fit the technique and set `embedding_`."""
        ...

    def transform(self, X: MatrixLike) -> Embedding:
        """Embed observations unseen at fit time.

        Left refusing by default: whether this is possible at all is a
        property of the technique, so each subclass either implements a
        genuine extension or lets this stand. Refitting to accommodate new
        points is never an acceptable implementation -- it changes the
        embedding of every existing point.
        """
        raise NotImplementedError

    def trustworthiness(self, X: MatrixLike, n_neighbors: int = 5) -> float:
        """Fraction of input neighbourhoods preserved in the embedding.

        Defined for any embedding, so it sits at the family level. Report
        it with any embedding used to support a conclusion rather than to
        illustrate one.
        """
        raise NotImplementedError


class BaseManifoldReducer(PrecomputedMixin, BaseNonlinearReducer, ABC):
    """A technique recovering coordinates on a low-dimensional manifold.

    The subfamily that rests on the manifold hypothesis of Sect. 6.2: the
    data lie on or near a low-dimensional manifold embedded in the
    n-dimensional feature space. Applied where that does not hold, these
    techniques still produce a picture -- one with structure that is not
    in the data. `dim_red/intrinsic_dim.py` is what checks the premise.

    Transductive unless a subclass declares otherwise. These techniques
    fit the embedding of a particular sample, and most have no rule for a
    new point; the ones that do (UMAP) approximate.

    They reach the data only through pairwise dissimilarities, hence
    `PrecomputedMixin`: a measure from `xxcluster.measures.dissimilarity`
    can drive the embedding directly, which is the route to embedding
    mixed-type data.

    Parameters
    ----------
    metric
        Measure defining the input neighbourhoods, or "precomputed".
    n_neighbors
        Size of the local neighbourhood preserved. The balance between
        local and global structure, and the parameter most likely to
        change the conclusions drawn from a figure.
    random_state
        Required wherever the optimisation is stochastic, as it is for
        t-SNE and UMAP: a figure is only reproducible with the seed
        recorded alongside it. Spectral members of this subfamily --
        Isomap, LLE, Laplacian eigenmaps -- are deterministic and should
        declare themselves so.

    Fitted attributes
    -----------------
    stress_ : float
        Discrepancy between input and embedding structure, under whatever
        objective the technique minimises. The quantitative check against
        over-reading a picture.
    """

    stress_: float

    def __init__(
        self,
        n_components: int = 2,
        *,
        metric: MetricLike = "euclidean",
        n_neighbors: int = 15,
        random_state: Seed = None,
    ) -> None:
        super().__init__(n_components=n_components, random_state=random_state)
        self.metric = metric
        self.n_neighbors = n_neighbors

    @abstractmethod
    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Optimise the embedding and set `embedding_`.

        Abstract with no shared implementation: these techniques differ in
        the objective itself -- a divergence between neighbour
        distributions, a cross-entropy over a fuzzy simplicial set, a
        stress function -- not merely in its parameters.
        """
        ...


class BaseKernelReducer(PrecomputedMixin, BaseNonlinearReducer, ABC):
    """A technique performing a linear decomposition in a kernel feature space.

    Kernel PCA and its relatives: the data are mapped implicitly into a
    feature space by a kernel, and a linear decomposition is performed
    there. Nonlinear in the input space, linear in the feature space, and
    assuming nothing about a manifold.

    Three consequences separate this subfamily from manifold learning, and
    each is why the two cannot share a base class:

    * **Inductive.** The components are functions of the kernel between a
      new point and the training points, so `transform` is exact rather
      than an approximation. These techniques can sit before a clustering
      step in a pipeline that will later see new data.
    * **Deterministic.** The solution is an eigendecomposition, so no seed
      is needed and `random_state` matters only to an approximate solver.
    * **Spectral.** The eigenvalues give an explained-variance ratio, so
      `n_components` can be chosen on the same evidence as for linear PCA
      rather than by a stress curve.

    Note what "precomputed" means here: `kernel="precomputed"` takes a
    kernel matrix, not a dissimilarity. A kernel is a similarity, has a
    non-negative diagonal rather than a zero one, and may have negative
    off-diagonal entries. `PrecomputedMixin` is declared with
    `PrecomputedKind.KERNEL` so it validates the right thing; a
    dissimilarity is bridged across by `BaseDissimilarity.to_similarity`,
    which is a modelling choice and so is made explicitly.

    Parameters
    ----------
    kernel
        Kernel name, a callable, or "precomputed" for a kernel matrix.
    kernel_params
        Parameters of the kernel -- gamma, degree, coef0 as it requires.
        Held together rather than enumerated so a subclass does not carry
        parameters its kernel ignores.
    fit_inverse_transform
        Whether to learn the pre-image map. Off by default: it is a second
        fitted model and an approximation, not an algebraic inverse.

    Fitted attributes
    -----------------
    eigenvalues_ : ndarray of shape (n_components,)
    eigenvectors_ : ndarray of shape (m, n_components)
        The decomposition of the centred kernel matrix.
    explained_variance_ratio_ : ndarray of shape (n_components,)
        Share of variance per component, in the feature space -- not in
        the input space, which is what makes it harder to interpret than
        the linear case.
    """

    _precomputed_kind = PrecomputedKind.KERNEL
    _precomputed_param = "kernel"

    eigenvalues_: ArrayLike
    eigenvectors_: ArrayLike
    explained_variance_ratio_: ArrayLike

    def __init__(
        self,
        n_components: int = 2,
        *,
        kernel: MetricLike = "rbf",
        kernel_params: dict[str, Any] | None = None,
        fit_inverse_transform: bool = False,
        random_state: Seed = None,
    ) -> None:
        super().__init__(n_components=n_components, random_state=random_state)
        self.kernel = kernel
        self.kernel_params = kernel_params
        self.fit_inverse_transform = fit_inverse_transform

    def transform(self, X: MatrixLike) -> Embedding:
        """Project `X` onto the kernel principal components.

        Concrete for the subfamily: once the decomposition is fitted, the
        projection is the same computation for every kernel.
        """
        raise NotImplementedError

    def inverse_transform(self, X: MatrixLike) -> ArrayLike:
        """Approximate a point in the input space from its embedding.

        The pre-image problem. Unlike the linear case there is generally
        no exact solution, and often no exact pre-image exists at all, so
        this is an approximation to be reported as one. Available only
        where `fit_inverse_transform` was set.
        """
        raise NotImplementedError

    @abstractmethod
    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Build the kernel matrix, centre it, and decompose it.

        Where `kernel="precomputed"`, validate the input with
        `self._check_precomputed(X)` first. Positive semi-definiteness is
        established by the decomposition itself: report negative
        eigenvalues with their magnitudes rather than rejecting the matrix
        at the door.
        """
        ...
