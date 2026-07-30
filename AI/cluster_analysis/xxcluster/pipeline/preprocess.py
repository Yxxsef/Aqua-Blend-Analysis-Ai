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
        """Return output feature names, so columns stay traceable."""
        raise NotImplementedError


def describe_preprocessing(pipeline: Any) -> list[dict[str, Any]]:
    """Summarise a fitted pipeline, step by step, in applied order.

    Renders directly into Sect. 3.3, which asks for exactly this: the
    steps, in the order applied, so the pipeline is reproducible.
    """
    raise NotImplementedError
