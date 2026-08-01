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

from sklearn.base import clone
from sklearn.utils.validation import check_memory

from ..core.base import BaseClusterer
from ..core.types import Embedding, Labels, MatrixLike
from ..core.validation import ensure_fitted


def _fit_transform_one(step: Any, X: MatrixLike) -> tuple[Any, MatrixLike]:
    """Fit one transformer and apply it, returning both.

    A module-level function so `joblib.Memory` can cache it: the cache key
    covers the step's parameters and the data, so a sweep over the final
    method's parameters reuses one reduction rather than recomputing it.
    """
    return step, step.fit_transform(X)


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
        """Fit each transformer in turn, then the final clusterer.

        Every step is cloned first, so fitting a pipeline never mutates the
        components the caller handed in. Without that, a sweep would carry
        state from one candidate into the next and the second fit would not
        be the run it is reported as.
        """
        self._validate_steps()
        cached = check_memory(self.memory).cache(_fit_transform_one)

        Xt = X
        fitted: dict[str, Any] = {}
        for name, step in self.steps[:-1]:
            step, Xt = cached(clone(step), Xt)
            fitted[name] = step

        name, final = self.steps[-1]
        final = clone(final)
        final.fit(Xt, y, **fit_params)
        fitted[name] = final

        self.named_steps_ = fitted
        self.labels_ = final.labels_
        self.n_clusters_ = final.n_clusters_

    def predict(self, X: MatrixLike) -> Labels:
        """Transform and assign, where the final method is inductive.

        Available only if the final step declares `is_inductive` and every
        transformer applies to unseen data -- which excludes a transductive
        manifold step. Refuses otherwise, rather than refitting.
        """
        ensure_fitted(self, "named_steps_")

        final = self._fitted_steps()[-1]
        if not hasattr(final, "predict"):
            raise NotImplementedError(
                f"the final step {type(final).__name__} is transductive: it "
                f"labels only the observations it was fitted on. Use `labels_`."
            )
        return final.predict(self.transform(X))

    def transform(self, X: MatrixLike) -> Embedding:
        """Apply the preprocessing steps without clustering.

        Refuses where a step cannot map unseen data, rather than refitting
        it -- the same rule as `AdaptedDimReducer.transform`, and for the
        same reason: a refitted step returns an embedding from a model
        that was never the one reported.
        """
        ensure_fitted(self, "named_steps_")

        Xt = X
        for step in self._fitted_steps()[:-1]:
            if not hasattr(step, "transform"):
                raise NotImplementedError(
                    f"step {type(step).__name__} is transductive and cannot "
                    f"map unseen observations, so neither can this pipeline."
                )
            Xt = step.transform(Xt)
        return Xt

    def _fitted_steps(self) -> list[Any]:
        """The fitted steps in applied order."""
        return [self.named_steps_[name] for name, _ in self.steps]

    def _validate_steps(self) -> None:
        """Check the step types and that the last one is a clusterer."""
        if not self.steps:
            raise ValueError(
                "steps is empty; a pipeline needs at least a final clusterer."
            )

        names = [name for name, _ in self.steps]
        if len(set(names)) != len(names):
            raise ValueError(f"step names must be unique; got {names}.")

        for name, step in self.steps[:-1]:
            if not hasattr(step, "fit_transform") and not (
                hasattr(step, "fit") and hasattr(step, "transform")
            ):
                raise ValueError(
                    f"step {name!r} ({type(step).__name__}) is not a "
                    f"transformer; every step but the last must transform."
                )

        name, final = self.steps[-1]
        if not isinstance(final, BaseClusterer) and not hasattr(final, "fit_predict"):
            raise ValueError(
                f"the final step {name!r} ({type(final).__name__}) is not a "
                f"clusterer. A pipeline ending in a transformer is a "
                f"`sklearn.pipeline.Pipeline` -- use that instead."
            )


def make_cluster_pipeline(*steps: Any, memory: Any = None) -> ClusterPipeline:
    """Build a `ClusterPipeline` from components, naming steps automatically.

    Mirrors `sklearn.pipeline.make_pipeline`, so the shorthand is the one
    already familiar from scikit-learn. Names are the lower-cased class
    names, suffixed where a class appears twice.
    """
    names: list[str] = []
    for step in steps:
        base = type(step).__name__.lower()
        duplicates = sum(1 for name in names if name == base or name.startswith(f"{base}-"))
        names.append(base if not duplicates else f"{base}-{duplicates + 1}")
    return ClusterPipeline(list(zip(names, steps)), memory=memory)
