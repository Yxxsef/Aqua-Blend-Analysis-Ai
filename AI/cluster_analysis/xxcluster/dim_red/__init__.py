"""
Dimensionality reduction techniques.

Mirrors Sect. 6 of the documentation:

    linear/         PCA, LDA, and other linear projections
    nonlinear/      manifold learning: t-SNE, UMAP, and others
    intrinsic_dim.py    how many dimensions the data actually occupies

The motivation is the curse of dimensionality: as d grows, pairwise
distances concentrate, and a clustering method that reads the data only
through d(., .) degrades accordingly. Reduction is therefore not a
convenience step but part of the method's applicability.

The distinction that matters throughout this subpackage is inductive
versus transductive. A linear projection learns a mapping that applies to
any point; most manifold learners embed only the sample they were fitted
on. Only the former can sit before a clustering step in a pipeline that
will later see new data, so `Capabilities.is_inductive` is not optional
here -- see `core.base.BaseDimReducer`.

A second distinction is worth keeping in view: reduction for visualisation
and reduction for clustering are different jobs. A technique that produces
a readable two-dimensional picture may distort the density and distance
structure that a clustering method then relies on, so an embedding used
for a figure should not be assumed fit to cluster on.
"""

from __future__ import annotations
