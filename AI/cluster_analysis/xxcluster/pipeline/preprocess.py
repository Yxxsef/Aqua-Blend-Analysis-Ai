"""
Preprocessing steps.

The transformations of Sect. 3.3, applied in a fixed order and recorded
with the result, since every one of them changes what a clustering method
sees. Contracts only: the concrete steps are scikit-learn transformers
where suitable ones exist.

Three that matter more here than in supervised work, because there is no
validation error to reveal a bad choice:

Scaling
    Distance-based methods are not scale-invariant, so the choice of
    scaler decides which features drive the partition. Left unscaled,
    turbidity in NTU and pH would contribute to a Euclidean distance in
    proportion to their units, which is not a modelling decision anyone
    made.
Missing values
    Imputation invents observations that will be clustered as if measured.
    An imputed value near a cluster boundary is a fabricated assignment,
    which is why the alternative -- a dissimilarity defined on incomplete
    data, see `measures.dissimilarity` -- is worth preferring where the
    method supports it.
Categorical encoding
    One-hot encoding imposes a geometry in which every pair of categories
    is equidistant. Where that is wrong, the encoding is the problem and a
    mixed-type dissimilarity is the fix.
"""

from __future__ import annotations

from abc import ABC
from typing import Any, Sequence

import numpy as np

from ..core.base import BaseTransformer
from ..core.types import ArrayLike


class BasePreprocessor(BaseTransformer, ABC):
    """A preprocessing step.

    Adds two things to the transformer contract, both needed for
    interpretation rather than for fitting.

    Class attributes
    ----------------
    invertible
        Whether the step can be undone. Cluster profiles are reported in
        original units, which requires inverting the chain of steps back to
        the measured features -- so a non-invertible step in the middle of a
        pipeline costs interpretability, and should be a decision.
    preserves_features
        Whether output columns still correspond to input features. False
        for any reduction step, after which a feature-level interpretation
        is no longer available.
    """

    invertible: bool = True
    preserves_features: bool = True

    def get_feature_names_out(self, input_features: Sequence[str] | None = None) -> ArrayLike:
        """Return output feature names, so columns stay traceable.

        Passes the names through where the step preserves features, which
        covers scaling and imputation -- they change values, not columns.
        A step that does not preserve them must override this, because
        after it a cluster profile can no longer be read in the measured
        variables and the names are the only record of what was lost.
        """
        if not self.preserves_features:
            raise NotImplementedError(
                f"{type(self).__name__} does not preserve features, so it must "
                f"name its outputs itself."
            )

        if input_features is None:
            input_features = getattr(self, "feature_names_in_", None)
        if input_features is None:
            raise ValueError(
                f"{type(self).__name__} has no recorded input feature names; "
                f"pass input_features, or fit on a DataFrame."
            )
        return np.asarray(input_features, dtype=object)


def describe_preprocessing(pipeline: Any) -> list[dict[str, Any]]:
    """Summarise a fitted pipeline, step by step, in applied order.

    Renders directly into Sect. 3.3, which asks for exactly this: the
    steps, in the order applied, so the pipeline is reproducible.

    Accepts anything with `steps` or `named_steps_` -- a
    `sklearn.pipeline.Pipeline`, a `ClusterPipeline`, or a bare list of
    (name, step) pairs -- since Sect. 3.3 describes the preprocessing
    whichever of those carried it.

    Each entry records the two properties that decide what can still be
    said about the result: whether the step can be inverted, and whether
    its output columns are still the measured features. A chain that is
    not invertible end to end cannot report cluster profiles in original
    units, which is what Sect. 4.4 asks for.

    Invertibility is read from the step itself. Feature preservation is
    `None` for a third-party transformer that does not declare it, since
    it cannot be inferred -- and reporting an unknown as True would let a
    reduction step pass for one that keeps the measured variables.
    """
    if hasattr(pipeline, "named_steps_"):
        steps = list(pipeline.named_steps_.items())
    elif hasattr(pipeline, "steps"):
        steps = list(pipeline.steps)
    else:
        steps = list(pipeline)

    described = []
    for position, (name, step) in enumerate(steps):
        described.append(
            {
                "position": position,
                "name": name,
                "class": type(step).__name__,
                "params": {
                    key: value
                    for key, value in sorted(step.get_params(deep=False).items())
                }
                if hasattr(step, "get_params")
                else {},
                "invertible": bool(
                    getattr(step, "invertible", hasattr(step, "inverse_transform"))
                ),
                "preserves_features": getattr(step, "preserves_features", None),
            }
        )
    return described
