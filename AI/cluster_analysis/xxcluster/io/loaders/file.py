"""
Loading an extract from a file.

For external data and for exported extracts. A file is a fixed source, so
`data_cutoff` is whatever window the export covers -- state it, since the
file itself does not know.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from ..datasets import BaseDatasetLoader, FeatureSpec


class _FileLoader(BaseDatasetLoader):
    """Shared behaviour: a path, checked before it is read."""

    def __init__(
        self,
        path: str | Path,
        features: Sequence[FeatureSpec],
        *,
        data_cutoff: date | str | None = None,
        read_options: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(features, data_cutoff=data_cutoff)
        self.path = Path(path)
        self.read_options = read_options or {}

    def _source_description(self) -> str:
        return str(self.path)

    def _check_path(self) -> Path:
        if not self.path.exists():
            raise FileNotFoundError(f"no extract at {self.path}")
        return self.path


class CsvLoader(_FileLoader):
    """Reads a CSV extract.

    Note what is not done here: no dtype coercion beyond pandas' own
    inference, and no cleaning. A column that arrives as text when the
    schema declares a float is a problem for whoever produced the file --
    silently coercing it here would hide a data fault behind an analysis.

    Parameters
    ----------
    read_options
        Passed through to `pandas.read_csv`, for the separator, encoding or
        date parsing a particular extract needs.
    """

    def _read(self, **kwargs: Any) -> pd.DataFrame:
        return pd.read_csv(self._check_path(), **{**self.read_options, **kwargs})


class ParquetLoader(_FileLoader):
    """Reads a Parquet extract.

    Preferable to CSV where the choice exists: dtypes survive the round
    trip, so a timestamp stays a timestamp and a float does not come back
    as text. Requires `pyarrow`, which pandas imports on demand.
    """

    def _read(self, **kwargs: Any) -> pd.DataFrame:
        return pd.read_parquet(self._check_path(), **{**self.read_options, **kwargs})
