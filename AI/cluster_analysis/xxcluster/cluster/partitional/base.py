"""
Base class shared by partitional methods.
"""

from __future__ import annotations

from abc import ABC
from typing import Any

from ...core.base import BaseClusterer
from ...core.types import MatrixLike, Seed


class BasePartitionalClusterer(BaseClusterer, ABC):
    """A method that optimises a criterion function by iterative relocation.

    Common to the family, and the reason it is worth a shared base: these
    methods are iterative, converge to a local optimum, and depend on their
    initialisation. All three are declared here so that every subfamily
    reports them the same way -- the number of iterations run, whether the
    tolerance was met, and how many restarts were kept.

    A method whose criterion has no closed form, or which does not iterate
    at all, still belongs here provided it relocates observations between
    clusters; if it does not, it is probably hierarchical or hybrid.

    Parameters
    ----------
    max_iter
        Iteration cap, reached without convergence being a reportable
        outcome rather than an error.
    tol
        Convergence tolerance on the criterion or on the assignment change.
    n_init
        Number of restarts; the best run by criterion value is kept. This
        is the mitigation for local optima noted in Sect. 2.1, and its
        value belongs in the experimental setup of Sect. 4.1.
    random_state
        Seed, required for reproducibility wherever `n_init > 1` or the
        initialisation is stochastic.

    Fitted attributes
    -----------------
    n_iter_ : int
        Iterations run by the retained restart.
    criterion_ : float
        Criterion value of the retained restart.
    converged_ : bool
    """

    #: Declared, not merely documented: `_check_fitted` verifies these after
    #: every fit, and `BackendAdapter._collect_fitted` copies exactly this set
    #: from a backend. An attribute named only in the docstring above is
    #: neither checked nor copied.
    #:
    #: Safe for the whole family because the subfamilies that do not iterate
    #: -- density-based and graph-theoretic -- derive from `BaseClusterer`
    #: directly and never inherit this.
    _required_fitted = ("n_iter_", "converged_", "criterion_")

    n_iter_: int
    criterion_: float
    converged_: bool

    def __init__(
        self,
        n_clusters: int = 2,
        *,
        max_iter: int = 300,
        tol: float = 1e-4,
        n_init: int = 10,
        random_state: Seed = None,
    ) -> None:
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.tol = tol
        self.n_init = n_init
        self.random_state = random_state

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Run `n_init` restarts and retain the best by criterion value."""
        raise NotImplementedError

    def _fit_once(self, X: MatrixLike, random_state: Any) -> Any:
        """Run a single restart to convergence and return its result.

        The iteration itself, which is what a subfamily defines: alternate
        assignment and update, run EM, adapt a lattice. Restarts,
        comparison and selection are handled by `_fit` above.

        Required of a native method. Not abstract, because an adapted method
        never reaches it -- its backend runs its own iteration -- and making
        it abstract would leave no way to adapt a method of this family at
        all. See the note on native hooks in `core/adapters.py`.
        """
        raise NotImplementedError

    def _initialise(self, X: MatrixLike, random_state: Any) -> Any:
        """Produce the starting state for one restart."""
        raise NotImplementedError
