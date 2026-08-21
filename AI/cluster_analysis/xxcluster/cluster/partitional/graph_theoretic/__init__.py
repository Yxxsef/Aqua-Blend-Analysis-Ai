"""
Graph-theoretic methods.

Represents the data as a weighted graph -- observations as vertices,
pairwise affinities as edges -- and clusters by partitioning it: spectral
clustering via the eigenvectors of the graph Laplacian, and the
graph-neural-network approaches noted in Sect. 2.3.

Two consequences shape the contract in `base.py`. First, the result
depends on the affinity graph at least as much as on the partitioning
step, so graph construction is an explicit, inspectable stage rather than
a private detail. Second, spectral methods embed before they cluster,
which places them on the boundary with `xxcluster.dim_red`: the embedding
is exposed as a fitted attribute so it can be reused and plotted, while
the technique itself stays here because its purpose is the partition.
"""

from __future__ import annotations
