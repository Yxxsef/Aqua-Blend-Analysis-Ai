"""
Base class shared by partitional methods.
"""

from __future__ import annotations

from abc import ABC
from typing import Any, ClassVar, Mapping

import numpy as np

from ...core.base import BaseClusterer
from ...core.exceptions import ContractViolationError
from ...core.types import NOISE_LABEL, MatrixLike, Seed
from ...core.validation import check_random_state


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

    #: Direction of `criterion_`, read by `_fit` when comparing restarts.
    #: False for every method whose criterion is an error to minimise, which
    #: is the SSE subfamily and the default here. A likelihood-based method
    #: sets it True. Stated as a declaration rather than inferred, because a
    #: comparison in the wrong direction returns the worst restart of the
    #: batch and nothing downstream can tell.
    _criterion_higher_is_better: ClassVar[bool] = False

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
        """Run `n_init` restarts and retain the best by criterion value.

        Concrete for the whole family, so a native method supplies only its
        own iteration through `_fit_once` and never writes a restart loop of
        its own. The mitigation for local optima of Sect. 2.1 is therefore
        applied identically by every method here, which is what makes their
        restart counts comparable in Sect. 8.1.

        Reproducibility comes from deriving one seed per restart from
        `random_state`, so the whole fit replays from that single value. The
        seeds are drawn up front rather than as the loop runs, so restart i
        is the same run whatever happened in restart i-1.

        An adapted method never arrives here: `AdaptedClusterer._fit`
        precedes this class in the MRO and its backend runs its own restarts.
        `n_init` is validated in this method rather than in
        `_validate_params` for that reason -- a backend may accept spellings
        we do not, such as scikit-learn's `n_init="auto"`, and validating on
        the shared path would reject a value the backend understands.
        """
        n_init = self._check_n_init()

        best: Mapping[str, Any] | None = None
        for seed in self._restart_seeds(n_init):
            candidate = self._check_restart(self._fit_once(X, check_random_state(seed)))
            if best is None or self._is_better_restart(
                candidate["criterion_"], best["criterion_"]
            ):
                best = candidate

        for name, value in best.items():
            setattr(self, name, value)
        self._derive_fitted()

    def _fit_once(self, X: MatrixLike, random_state: Any) -> Mapping[str, Any]:
        """Run a single restart to convergence and return its result.

        The iteration itself, which is what a subfamily defines: alternate
        assignment and update, run EM, adapt a lattice. Restarts,
        comparison and selection are handled by `_fit` above.

        Returns a mapping of fitted attribute name to value -- the names
        with their trailing underscore, so `_fit` installs the winning
        restart with `setattr` and nothing has to agree on a second
        vocabulary. It must contain `criterion_`, which is what the restarts
        are compared on; `_derive_fitted` fills in whatever else is
        mechanically derivable, so a typical return is `labels_`,
        `criterion_`, `n_iter_`, `converged_` and the subfamily's own state.

        Returning rather than assigning is deliberate: a restart that fails
        part way leaves no half-written state on `self`, and the losing
        restarts never touch the object at all.

        Required of a native method. Not abstract, because an adapted method
        never reaches it -- its backend runs its own iteration -- and making
        it abstract would leave no way to adapt a method of this family at
        all. See the note on native hooks in `core/adapters.py`.
        """
        raise NotImplementedError

    def _initialise(self, X: MatrixLike, random_state: Any) -> Any:
        """Produce the starting state for one restart."""
        raise NotImplementedError

    # --- Steps of the restart loop ----------------------------------------

    def _check_n_init(self) -> int:
        """Validate `n_init` at the point the restart loop actually uses it."""
        n_init = self.n_init
        if isinstance(n_init, bool) or not isinstance(n_init, (int, np.integer)):
            raise ValueError(
                f"n_init must be an integer for a native method; got "
                f"{n_init!r}. Spellings such as \"auto\" are a backend's "
                f"convention and are only meaningful to an adapted method."
            )
        if n_init < 1:
            raise ValueError(f"n_init must be at least 1; got {n_init}.")
        return int(n_init)

    def _restart_seeds(self, n_init: int) -> list[int]:
        """Derive one seed per restart from `random_state`.

        Drawn from the root state rather than by offsetting it, so two
        restarts cannot share a stream, and the whole set is fixed before
        any fitting begins.
        """
        root = check_random_state(self.random_state)
        high = np.iinfo(np.int32).max
        # `check_random_state` passes a Generator through unchanged, and the
        # two interfaces spell the same draw differently.
        draw = root.integers if isinstance(root, np.random.Generator) else root.randint
        return [int(seed) for seed in draw(high, size=n_init)]

    def _check_restart(self, result: Any) -> Mapping[str, Any]:
        """Verify one restart returned something `_fit` can install."""
        if not isinstance(result, Mapping) or "criterion_" not in result:
            raise ContractViolationError(
                f"{type(self).__name__}._fit_once must return a mapping of "
                f"fitted attribute name to value, containing at least "
                f"`criterion_`; got {type(result).__name__}. The restart loop "
                f"compares restarts on that value and installs the winner."
            )
        return result

    def _is_better_restart(self, candidate: float, incumbent: float) -> bool:
        """Compare two restarts, in the direction the class declares.

        A non-finite criterion loses to any finite one. Without this the
        comparison would be decided by whichever restart happened to run
        first, since every comparison against NaN is False in both
        directions.
        """
        if not np.isfinite(incumbent):
            return True
        if not np.isfinite(candidate):
            return False
        if self._criterion_higher_is_better:
            return bool(candidate > incumbent)
        return bool(candidate < incumbent)

    def _derive_fitted(self) -> None:
        """Fill in the fitted attributes that follow from the ones set.

        Called once, on the winning restart, so `_fit_once` reports only
        what its iteration actually produces. Recomputed rather than filled
        in when absent, because these quantities are functions of `labels_`
        and a stale value from an earlier fit of the same instance would
        otherwise survive.

        Subclasses that add a derivable attribute override this and call
        `super()` first; see `BasePrototypeClusterer`.
        """
        labels = getattr(self, "labels_", None)
        if labels is not None:
            labels = np.asarray(labels)
            self.n_clusters_ = int(np.unique(labels[labels != NOISE_LABEL]).size)
