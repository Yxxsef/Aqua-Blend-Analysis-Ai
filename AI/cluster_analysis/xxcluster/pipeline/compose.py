"""
Composing steps and a method into one component.

A pipeline ending in a clusterer is not a `Pipeline`: the final step has no
`predict` to delegate to, and the result of fitting is `labels_` rather
than a transformation. `ClusterPipeline` closes that gap, so a composition
satisfies the `Clusterer` protocol and can be passed anywhere a bare
method can -- to a selector, to a stability analysis, to the comparison
run.

That substitutability is the point. Without it, every consumer would need
two code paths, one for a method and one for a method with preprocessing,
and the preprocessing would end up applied outside the resampling loop --
where it leaks information across folds and inflates stability.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..core.base import BaseClusterer
from ..core.types import Embedding, Labels, MatrixLike


class ClusterPipeline(BaseClusterer):
    """Preprocessing steps followed by a clustering method.

    Parameters
    ----------
    steps
        (name, component) pairs. Every step but the last is a transformer;
        the last is a clusterer.
    memory
        Optional cache for fitted transformers, so a sweep over the
        method's parameters does not repeat the reduction step each time.

    Fitted attributes
    -----------------
    labels_
        Taken from the final step, so the pipeline is a clusterer.
    named_steps_ : dict
        The fitted steps, for inspecting an intermediate result -- the
        embedding a figure is drawn from, typically.
    """

    named_steps_: dict[str, Any]

    def __init__(self, steps: Sequence[tuple[str, Any]] | None = None, *, memory: Any = None) -> None:
        self.steps = steps
        self.memory = memory

    def _fit(self, X: MatrixLike, y: Any = None, **fit_params: Any) -> None:
        """Fit each transformer in turn, then the final clusterer."""
        raise NotImplementedError

    def predict(self, X: MatrixLike) -> Labels:
        """Transform and assign, where the final method is inductive.

        Available only if the final step declares `is_inductive` and every
        transformer applies to unseen data -- which excludes a transductive
        manifold step. Refuses otherwise, rather than refitting.
        """
        raise NotImplementedError

    def transform(self, X: MatrixLike) -> Embedding:
        """Apply the preprocessing steps without clustering."""
        raise NotImplementedError

    def _validate_steps(self) -> None:
        """Check the step types and that the last one is a clusterer."""
        raise NotImplementedError


def make_cluster_pipeline(*steps: Any, memory: Any = None) -> ClusterPipeline:
    """Build a `ClusterPipeline` from components, naming steps automatically.

    Mirrors `sklearn.pipeline.make_pipeline`, so the shorthand is the one
    already familiar from scikit-learn.
    """
    raise NotImplementedError
