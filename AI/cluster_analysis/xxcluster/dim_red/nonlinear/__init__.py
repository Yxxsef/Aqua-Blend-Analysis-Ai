"""
Nonlinear dimensionality reduction techniques.

Implement nonlinear dimensionality reduction techniques, e.g. t-SNE, UMAP.

Nonlinear means only that the learned map is not a linear projection. It
does not imply the manifold hypothesis, and the techniques here divide by
what they do assume -- see `base.py`:

    BaseManifoldReducer   t-SNE, UMAP, Isomap, LLE, Laplacian eigenmaps.
                          Assume the data lie on a low-dimensional
                          manifold and recover coordinates on it; reach
                          the data through neighbourhoods; mostly
                          transductive; report a stress.
    BaseKernelReducer     Kernel PCA and relatives. Assume a feature map
                          induced by a kernel, not a manifold; inductive,
                          deterministic, and spectral, so they report an
                          explained-variance ratio like linear PCA.

The manifold hypothesis of Sect. 6.2 is therefore a property of the first
subfamily, not of this directory. Whether it holds for this dataset is an
open question of the documentation, and `../intrinsic_dim.py` is what
answers it; a manifold learner applied where it does not hold still
produces a picture -- one with structure that is not in the data. A kernel
method makes no such claim and needs no such check, which is exactly why
the two cannot share a base class.

One caution does follow from nonlinearity alone, and holds for everything
here: distances in the embedding are not the input distances.
Neighbourhood structure may be preserved while global geometry, cluster
sizes and inter-cluster separation are not, so a validity index computed
on the embedding measures the embedding, not the data.

The other two cautions are subfamily-specific rather than universal, and
are declared per class rather than assumed:

* Transductivity -- true of most manifold learners, false of kernel
  methods, which extend to unseen points exactly.
* Absence of an inverse -- true of most manifold learners; kernel methods
  have an approximate one through the pre-image problem.
"""

from __future__ import annotations
