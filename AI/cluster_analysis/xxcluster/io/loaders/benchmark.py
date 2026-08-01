"""
Loading reference datasets with known labels.

Two uses, neither of them about AquaBlend.

Verification: a native implementation has to be shown to behave as
published before its results on our data are trusted, and that needs data
whose answer is known. The external indices of
`measures.validation.external` are defined for exactly this and have no
other use here, since the operational data carries no ground truth.

Illustration: a figure or a worked example in the document is clearer on
data a reader already knows than on an extract they do not.

The true labels are returned as an "interpret" column rather than being
clustered on, so they cannot leak into a method by accident.
"""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd

from ..datasets import INTERPRET, BaseDatasetLoader, FeatureSpec

#: Reference datasets available from scikit-learn, by name.
BENCHMARKS: dict[str, str] = {
    "iris": "load_iris",
    "wine": "load_wine",
    "breast_cancer": "load_breast_cancer",
    "digits": "load_digits",
}

#: Column holding the published labels.
LABEL_COLUMN = "target"


class BenchmarkLoader(BaseDatasetLoader):
    """Loads a scikit-learn reference dataset with its published labels.

    The schema is derived rather than declared, which is the one place that
    is acceptable: the roles are not a modelling decision here, since every
    measurement is a clustering feature and the published label is by
    definition held out.

    Parameters
    ----------
    name
        One of `BENCHMARKS`.
    include_labels
        Whether to carry the published labels as an "interpret" column.
        Turn it off to check that a method cannot see them at all.
    """

    def __init__(
        self,
        name: str = "iris",
        *,
        include_labels: bool = True,
        features: Sequence[FeatureSpec] | None = None,
    ) -> None:
        if name not in BENCHMARKS:
            raise ValueError(
                f"unknown benchmark {name!r}; available: {', '.join(sorted(BENCHMARKS))}"
            )
        self.name = name
        self.include_labels = include_labels
        super().__init__(features or self._derive_schema(), data_cutoff=None)

    def _derive_schema(self) -> list[FeatureSpec]:
        frame = self._load_frame()
        specs = [
            FeatureSpec(name=column, dtype="float")
            for column in frame.columns
            if column != LABEL_COLUMN
        ]
        if self.include_labels:
            specs.append(FeatureSpec(name=LABEL_COLUMN, dtype="int", role=INTERPRET))
        return specs

    def _load_frame(self) -> pd.DataFrame:
        from sklearn import datasets as sklearn_datasets

        bunch = getattr(sklearn_datasets, BENCHMARKS[self.name])()
        frame = pd.DataFrame(bunch.data, columns=list(bunch.feature_names))
        if self.include_labels:
            frame[LABEL_COLUMN] = bunch.target
        return frame

    def _read(self, **kwargs: Any) -> pd.DataFrame:
        return self._load_frame()

    def _source_description(self) -> str:
        return f"scikit-learn reference dataset '{self.name}'"

    def true_labels(self, dataset: Any) -> Any:
        """Return the published labels from a loaded `Dataset`.

        Convenience for the external indices, which take `labels_true`.
        """
        if not self.include_labels:
            raise ValueError("this loader was configured without labels.")
        return dataset.interpretation_frame()[LABEL_COLUMN].to_numpy()
