"""
Loading data already in memory.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

import numpy as np
import pandas as pd

from ..datasets import BaseDatasetLoader, FeatureSpec


class FrameLoader(BaseDatasetLoader):
    """Wraps a DataFrame or array that is already in hand.

    The smallest loader, and the one that makes the rest testable: a
    fixture, a notebook experiment, or the output of somebody else's
    script becomes a `Dataset` with a declared schema and stated
    provenance, so it travels through the same pipeline as real data.

    Recording where an in-memory frame came from is the point of
    `description`. An array with no provenance is exactly the thing that
    ends up in a report with nobody able to say what it was.

    Parameters
    ----------
    data
        A DataFrame, or a 2-D array whose columns are in `features` order.
    features
        The declared schema.
    description
        Where the data came from, in one line.
    data_cutoff
        The date the data runs up to, where that is meaningful.
    """

    def __init__(
        self,
        data: pd.DataFrame | np.ndarray,
        features: Sequence[FeatureSpec],
        *,
        description: str = "in-memory data",
        data_cutoff: date | str | None = None,
    ) -> None:
        super().__init__(features, data_cutoff=data_cutoff)
        self.data = data
        self.description = description

    def _read(self, **kwargs: Any) -> pd.DataFrame:
        if isinstance(self.data, pd.DataFrame):
            return self.data.copy()
        array = np.asarray(self.data)
        if array.ndim != 2:
            raise ValueError(f"data must be two-dimensional; got shape {array.shape}.")
        if array.shape[1] != len(self.features):
            raise ValueError(
                f"data has {array.shape[1]} columns but {len(self.features)} "
                f"features are declared; an array carries no column names, so "
                f"the two must correspond positionally."
            )
        return pd.DataFrame(array, columns=[f.name for f in self.features])

    def _source_description(self) -> str:
        return self.description
