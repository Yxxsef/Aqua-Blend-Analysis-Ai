"""
Dimensionality reduction techniques.

Mirrors Sect. 6 of the documentation:

    linear/         PCA, LDA, and other linear projections
    nonlinear/      manifold learning: t-SNE, UMAP, and others
    intrinsic_dim.py    how many dimensions the data actually occupies

The motivation is the curse of dimensionality: as n grows, pairwise
distances concentrate, and a clustering method that reads the data only
through d(., .) degrades accordingly. Reduction is therefore not a
convenience step but part of the method's applicability.

One distinction is easy to lose and belongs here rather than on any one
class: reduction for visualisation and reduction for clustering are
different jobs. A technique that produces a readable two-dimensional
picture may distort the density and distance structure a clustering method
then relies on, so an embedding used for a figure should not be assumed
fit to cluster on.
"""

from __future__ import annotations
