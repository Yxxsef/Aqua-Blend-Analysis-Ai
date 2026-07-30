"""
Loading the analysis dataset.

Returns a feature matrix, its feature metadata, and its provenance -- the
three things Sect. 3.1 and Sect. 3.2 ask to have recorded. The metadata is
not decoration: which columns are clustered on and which are held back for
interpretation is a decision that must travel with the data, since
clustering on a column and then explaining the clusters by it is circular.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class FeatureSpec:
    """One column of the dataset.

    Attributes
    ----------
    name, dtype, unit
        Identity of the column, as tabulated in Sect. 3.2.
    role
        "cluster" for a column the methods see, "interpret" for one held
        out to characterise the result, "identifier" for keys, "time" for
        a timestamp. Only the first is clustered on.
    valid_range
        Physically plausible range, where one is known. A value outside it
        is a data problem to raise upstream, not an outlier to cluster.
    """

    name: str
    dtype: str = "float"
    unit: str | None = None
    role: str = "cluster"
    valid_range: tuple[float, float] | None = None


@dataclass(frozen=True)
class Dataset:
    """A loaded dataset with its metadata and provenance.

    Attributes
    ----------
    X
        The feature matrix, columns in `features` order.
    features
        One `FeatureSpec` per column.
    index
        Row identifiers -- timestamps, typically -- kept so a cluster can
        be traced back to the observations that formed it. This is what
        makes a partition actionable rather than abstract.
    provenance
        Source, extract version and retrieval date, per Sect. 3.1.
    """

    X: Any
    features: Sequence[FeatureSpec] = ()
    index: Any = None
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def cluster_matrix(self) -> Any:
        """Return only the columns whose role is "cluster"."""
        raise NotImplementedError

    def interpretation_frame(self) -> Any:
        """Return the held-out columns, for characterising a result."""
        raise NotImplementedError

    def summary(self) -> Any:
        """Per-feature counts, ranges and missingness, for Sect. 3.4."""
        raise NotImplementedError


class BaseDatasetLoader(ABC):
    """Loads a dataset from a source.

    One subclass per source -- a published extract, a database, a
    generated fixture -- so that swapping the source does not touch the
    analysis. Every loader returns the same `Dataset`, and validates the
    schema before returning it: a silently renamed column would otherwise
    surface as an unexplained change in the results.
    """

    @abstractmethod
    def load(self, **kwargs: Any) -> Dataset:
        """Load, validate and return the dataset."""
        ...

    def describe(self) -> Mapping[str, Any]:
        """Return the provenance of the source, without loading it."""
        raise NotImplementedError
