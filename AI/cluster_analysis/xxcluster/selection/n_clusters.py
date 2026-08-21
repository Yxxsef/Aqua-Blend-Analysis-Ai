"""
Choosing the number of clusters.

The procedure of Sect. 4.3, applied identically wherever |C| must be fixed
in advance, so that no method is advantaged by a more favourable choice
than another received.

Three parts, deliberately separate: generate the candidate values, score
each one, then apply a relative criterion from
`measures.validation.relative` to select. Separating them means the
criterion can be changed without touching the sweep, several criteria can
be applied to one sweep, and the curve is available whatever the
criterion decides.

Methods that determine |C| themselves -- the density-based family -- are
out of scope here by construction. Applying this procedure to them would
impose a parameter they do not have; sweep their own parameters instead.
"""

from __future__ import annotations

from abc import ABC
from typing import Any, Sequence

from ..core.types import MatrixLike
from .base import BaseSelector


class BaseNClustersSelector(BaseSelector, ABC):
    """Selects |C| for a method that requires it in advance.

    Parameters
    ----------
    candidates
        Values of |C| to try. The range is a judgement about the domain --
        how many operating regimes could be acted on -- as much as about
        the data, and belongs in the reported setup.
    criterion
        Relative criterion applied to the resulting curve.

    Fitted attributes
    -----------------
    n_clusters_ : int
        The selected value.
    curve_ : dict
        Candidate -> score, for every index scored. The figure that
        justifies the selection.
    conclusive_ : bool
        Whether the criterion found the curve informative. A false value
        is reported, not overridden.
    """

    n_clusters_: int
    curve_: dict[int, Any]
    conclusive_: bool

    def __init__(
        self,
        estimator: Any = None,
        *,
        candidates: Sequence[int] | None = None,
        criterion: Any = None,
        scoring: Any = None,
        refit: bool = True,
    ) -> None:
        super().__init__(
            estimator=estimator, param_grid=None, scoring=scoring, refit=refit
        )
        self.candidates = candidates
        self.criterion = criterion

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Sweep the candidates, build the curve, then apply the criterion."""
        raise NotImplementedError
