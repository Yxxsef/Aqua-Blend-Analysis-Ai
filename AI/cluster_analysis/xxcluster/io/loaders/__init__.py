"""
Dataset loaders, one per source.

    frame.py      FrameLoader   -- a DataFrame or array already in memory
    file.py       CsvLoader, ParquetLoader -- an external or exported extract
    benchmark.py  BenchmarkLoader -- reference data with known labels

Every loader returns the same `Dataset`, so swapping the source touches one
line of a notebook and nothing downstream. Adding one means a subclass of
`BaseDatasetLoader` implementing `_read` and `_source_description`; the
schema validation is inherited and cannot be skipped.

The live AquaBlend store is not here yet. It belongs in `supabase.py`,
reading over Postgres with `psycopg` and `DATABASE_URL` from a local `.env`
-- the pattern the project's existing loader already uses -- with the
dependency imported at load time so that `import xxcluster` does not need
it. It is deliberately unwritten until the Data Engineering team publishes
the view, since its schema would otherwise be a guess.
"""

from __future__ import annotations

from .benchmark import BenchmarkLoader
from .file import CsvLoader, ParquetLoader
from .frame import FrameLoader

__all__ = ["FrameLoader", "CsvLoader", "ParquetLoader", "BenchmarkLoader"]
