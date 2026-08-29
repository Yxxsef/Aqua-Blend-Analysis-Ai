"""
Loading the analysis dataset.

Returns a feature matrix, its feature metadata, and its provenance -- the
three things Sect. 3.1 and Sect. 3.2 ask to have recorded. The metadata is
not decoration: which columns are clustered on and which are held back for
interpretation is a decision that must travel with the data, since
clustering on a column and then explaining the clusters by it is circular.

On reproducibility. The upstream store is live, so the data behind a result
changes and that is expected. What a result must carry is therefore not a
copy of the rows but the window they came from: `provenance["data_cutoff"]`
records the date the extract runs up to, and `Dataset.provenance_statement`
renders it for Sect. 3.1. Two runs over the same cutoff are comparable; a
later cutoff is a new dataset, and any difference in the numbers is
attributable rather than mysterious.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

#: Roles a column may take. Only CLUSTER columns reach a clustering method.
CLUSTER = "cluster"
INTERPRET = "interpret"
IDENTIFIER = "identifier"
TIME = "time"
ROLES = (CLUSTER, INTERPRET, IDENTIFIER, TIME)


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
        Either bound may be None for a one-sided range.
    """

    name: str
    dtype: str = "float"
    unit: str | None = None
    role: str = CLUSTER
    valid_range: tuple[float | None, float | None] | None = None

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(
                f"unknown role {self.role!r} for feature {self.name!r}; "
                f"expected one of {', '.join(ROLES)}."
            )


@dataclass(frozen=True)
class Dataset:
    """A loaded dataset with its metadata and provenance.

    Attributes
    ----------
    X
        The feature matrix, columns in `features` order. A DataFrame or a
        2-D array; column selection returns the same container type, so a
        caller who supplied names keeps them and one who supplied an array
        is not handed a DataFrame back.
    features
        One `FeatureSpec` per column.
    index
        Row identifiers -- timestamps, typically -- kept so a cluster can
        be traced back to the observations that formed it. This is what
        makes a partition actionable rather than abstract.
    provenance
        Source, extract version and retrieval date, per Sect. 3.1. By
        convention loaders set `source`, `retrieved_at`, `data_cutoff`,
        `n_observations` and `n_features`.
    """

    X: Any
    features: Sequence[FeatureSpec] = ()
    index: Any = None
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        n_columns = self._frame().shape[1]
        if len(self.features) != n_columns:
            raise ValueError(
                f"{len(self.features)} feature specs describe a matrix with "
                f"{n_columns} columns. Every column must be declared, so that "
                f"a silently added or renamed column is caught here rather "
                f"than surfacing as an unexplained change in the results."
            )
        if self.index is not None and len(self.index) != self._frame().shape[0]:
            raise ValueError("index length does not match the number of observations.")

    # --- Shape -------------------------------------------------------------

    @property
    def n_observations(self) -> int:
        """m, the number of observations."""
        return int(self._frame().shape[0])

    @property
    def n_features(self) -> int:
        """n, counting every declared column whatever its role."""
        return len(self.features)

    def names(self, role: str | None = None) -> list[str]:
        """Column names, optionally restricted to one role."""
        return [f.name for f in self.features if role is None or f.role == role]

    # --- Column selection --------------------------------------------------

    def cluster_matrix(self) -> Any:
        """Return only the columns whose role is "cluster".

        The matrix the methods see. Selecting by role rather than by hand
        is what keeps a held-out column out of the clustering: an
        interpretation column that leaks in makes the eventual explanation
        circular, and nothing downstream would reveal it.
        """
        return self._select(CLUSTER)

    def interpretation_frame(self) -> pd.DataFrame:
        """Return the held-out columns, for characterising a result.

        Always a DataFrame, named: this is read by a human alongside a
        cluster profile, not fed to an estimator.
        """
        return self._frame().loc[:, self.names(INTERPRET)]

    def _select(self, role: str) -> Any:
        """Select by role positionally, preserving the container type."""
        positions = [i for i, f in enumerate(self.features) if f.role == role]
        if isinstance(self.X, pd.DataFrame):
            return self.X.iloc[:, positions]
        return np.asarray(self.X)[:, positions]

    def _frame(self) -> pd.DataFrame:
        """View the matrix as a named DataFrame, whatever was supplied."""
        if isinstance(self.X, pd.DataFrame):
            return self.X
        array = np.asarray(self.X)
        if array.ndim != 2:
            raise ValueError(f"X must be two-dimensional; got shape {array.shape}.")
        names = [f.name for f in self.features] if self.features else None
        if names is not None and len(names) != array.shape[1]:
            names = None  # let __post_init__ raise the informative error
        return pd.DataFrame(array, columns=names)

    # --- Description -------------------------------------------------------

    def summary(self) -> pd.DataFrame:
        """Per-feature counts, ranges and missingness, for Sect. 3.4.

        One row per declared column, whatever its role, since a problem in
        an identifier or a timestamp is worth seeing too. Non-numeric
        columns report counts and leave the statistics empty rather than
        being dropped.
        """
        frame = self._frame()
        rows = []
        for spec in self.features:
            column = frame[spec.name]
            row: dict[str, Any] = {
                "feature": spec.name,
                "role": spec.role,
                "unit": spec.unit,
                "count": int(column.notna().sum()),
                "missing": int(column.isna().sum()),
            }
            if pd.api.types.is_numeric_dtype(column):
                row |= {
                    "min": float(column.min()),
                    "max": float(column.max()),
                    "mean": float(column.mean()),
                    "std": float(column.std()),
                    "out_of_range": int(self._range_violations(spec, column).sum()),
                }
            else:
                row |= {"min": None, "max": None, "mean": None, "std": None,
                        "out_of_range": 0}
            rows.append(row)
        return pd.DataFrame(rows).set_index("feature")

    def check_ranges(self) -> pd.DataFrame:
        """Report values falling outside a declared `valid_range`.

        Returns one row per offending feature, empty where all is well.
        These are data problems to raise with the owning team, not outliers
        to cluster -- which is the distinction `valid_range` exists to
        make, and it is worthless unless something checks it.
        """
        frame = self._frame()
        rows = []
        for spec in self.features:
            if spec.valid_range is None:
                continue
            column = frame[spec.name]
            if not pd.api.types.is_numeric_dtype(column):
                continue
            violations = self._range_violations(spec, column)
            if violations.any():
                offending = column[violations]
                rows.append(
                    {
                        "feature": spec.name,
                        "n_violations": int(violations.sum()),
                        "declared_range": spec.valid_range,
                        "observed_min": float(offending.min()),
                        "observed_max": float(offending.max()),
                    }
                )
        return pd.DataFrame(rows, columns=[
            "feature", "n_violations", "declared_range", "observed_min", "observed_max"
        ])

    @staticmethod
    def _range_violations(spec: FeatureSpec, column: pd.Series) -> pd.Series:
        if spec.valid_range is None:
            return pd.Series(False, index=column.index)
        low, high = spec.valid_range
        violations = pd.Series(False, index=column.index)
        if low is not None:
            violations |= column < low
        if high is not None:
            violations |= column > high
        return violations.fillna(False)

    def provenance_statement(self) -> str:
        """Render the provenance as one sentence for Sect. 3.1.

        States the window the data covers rather than pretending it is
        fixed. The upstream store is live; a later cutoff is a new dataset,
        and saying so is what makes a change in the numbers attributable.
        """
        parts = [f"Data from {self.provenance.get('source', 'an unrecorded source')}"]
        cutoff = self.provenance.get("data_cutoff")
        parts.append(f"used up until {cutoff}" if cutoff else "with no cutoff recorded")
        retrieved = self.provenance.get("retrieved_at")
        if retrieved:
            parts.append(f"retrieved {retrieved}")
        statement = ", ".join(parts)
        return (
            f"{statement}. {self.n_observations} observations over "
            f"{len(self.names(CLUSTER))} clustering features."
        )

    def with_provenance(self, **entries: Any) -> "Dataset":
        """Return a copy with additional provenance recorded."""
        return replace(self, provenance={**self.provenance, **entries})


class BaseDatasetLoader(ABC):
    """Loads a dataset from a source.

    One subclass per source -- the live store, a published extract, a
    benchmark, a generated fixture -- so that swapping the source does not
    touch the analysis. Every loader returns the same `Dataset`, and
    validates the schema before returning it: a silently renamed column
    would otherwise surface as an unexplained change in the results.

    `load` is a template method, as `BaseComponent.fit` is: subclasses
    implement `_read` and inherit the validation, so no loader can skip it.

    Parameters
    ----------
    features
        The declared schema. Required, and deliberately not inferred:
        `role` is a modelling decision, not a property of the source, so no
        loader can work it out for you.
    data_cutoff
        The date the extract runs up to. Recorded in the provenance and
        rendered into Sect. 3.1; results are comparable within one cutoff.
    """

    def __init__(
        self,
        features: Sequence[FeatureSpec],
        *,
        data_cutoff: date | str | None = None,
    ) -> None:
        if not features:
            raise ValueError(
                "a loader needs a declared schema: role cannot be inferred "
                "from a source, so it must be stated."
            )
        self.features = tuple(features)
        self.data_cutoff = data_cutoff

    @abstractmethod
    def _read(self, **kwargs: Any) -> pd.DataFrame:
        """Read the source and return a frame; source-specific."""
        ...

    @abstractmethod
    def _source_description(self) -> str:
        """One line naming where the data came from."""
        ...

    def load(self, **kwargs: Any) -> Dataset:
        """Load, validate and return the dataset."""
        frame = self._read(**kwargs)
        frame = self._validate_schema(frame)
        index = self._extract_index(frame)
        return Dataset(
            X=frame,
            features=self.features,
            index=index,
            provenance=self.describe() | {
                "n_observations": int(frame.shape[0]),
                "n_features": int(frame.shape[1]),
            },
        )

    def describe(self) -> Mapping[str, Any]:
        """Return the provenance of the source, without loading it."""
        return {
            "source": self._source_description(),
            "loader": type(self).__name__,
            "data_cutoff": str(self.data_cutoff) if self.data_cutoff else None,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    def _validate_schema(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Check the source against the declared schema and order columns.

        Missing and unexpected columns are both errors: the first breaks
        the analysis, and the second means the source changed in a way
        nobody recorded.
        """
        declared = [f.name for f in self.features]
        present = list(frame.columns)
        missing = [name for name in declared if name not in present]
        unexpected = [name for name in present if name not in declared]
        if missing or unexpected:
            problems = []
            if missing:
                problems.append(f"missing {', '.join(missing)}")
            if unexpected:
                problems.append(f"undeclared {', '.join(unexpected)}")
            raise ValueError(
                f"{type(self).__name__} source does not match the declared "
                f"schema: {'; '.join(problems)}. Update the schema deliberately "
                f"rather than letting the source define it."
            )
        return frame.loc[:, declared]

    def _extract_index(self, frame: pd.DataFrame) -> Any:
        """Use the time column, else the identifier column, as row labels."""
        for role in (TIME, IDENTIFIER):
            names = [f.name for f in self.features if f.role == role]
            if names:
                return frame[names[0]].to_numpy()
        return None


def features_from_names(
    names: Iterable[str], *, role: str = CLUSTER, **kwargs: Any
) -> list[FeatureSpec]:
    """Build a uniform schema from column names.

    A convenience for external data where every column plays the same
    part -- a benchmark, or a quick look at someone else's extract. Not
    for the AquaBlend schema, where the roles differ and stating them is
    the point.
    """
    return [FeatureSpec(name=name, role=role, **kwargs) for name in names]
