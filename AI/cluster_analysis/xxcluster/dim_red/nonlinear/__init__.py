"""
Nonlinear dimensionality reduction techniques.

Carried over from the original `nonlinear_dr.py`: implement nonlinear
dimensionality reduction techniques, e.g. t-SNE, UMAP.

These rest on the manifold hypothesis of Sect. 6.2 -- that the data lie on
or near a low-dimensional manifold embedded in the n-dimensional feature
space -- and try to recover coordinates on it. Whether the hypothesis
holds for this dataset is an open question of the documentation, and
`intrinsic_dim.py` is what answers it; a manifold learner applied where it
does not hold produces a picture with structure that is not in the data.

Three cautions, all consequences of the nonlinearity, are enforced or
declared by the base class:

* Most are transductive -- no `transform` for unseen points.
* Most have no inverse, so a component cannot be read back in terms of the
  measured features; interpretation must come from elsewhere.
* Distances in the embedding are not the input distances. Neighbourhood
  structure may be preserved while global geometry, cluster sizes and
  inter-cluster separation are not, so a validity index computed on the
  embedding measures the embedding, not the data.
"""

from __future__ import annotations
