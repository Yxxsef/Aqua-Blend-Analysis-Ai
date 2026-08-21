"""
Density-based methods.

Defines clusters as regions of high density separated by regions of low
density, which lets them recover arbitrarily shaped clusters and refuse to
assign observations that lie in no dense region.

That refusal is the family's distinguishing feature and its consequence
for the rest of the package: the output is not a partition in the strict
sense of Def. 2, since noise points belong to no cluster. Everything that
consumes labels must handle the -1 convention, and any validity index
reported for these methods must state whether noise was scored or
excluded -- see `xxcluster.measures.validation`.

Per Sect. 2.3, HDBSCAN and the DBSCAN variants with automatic neighbourhood
selection are the candidates of interest for consumption profiles.
"""

from __future__ import annotations
