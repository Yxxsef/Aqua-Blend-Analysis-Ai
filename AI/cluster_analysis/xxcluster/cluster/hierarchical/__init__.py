"""
Hierarchical Cluster Analysis (HCA).

Produces multi-level partitions represented as a dendrogram, from which a
partition is obtained by cutting rather than by refitting. Two
construction directions, sharing the same components -- a dissimilarity
measure and a linkage criterion:

    agglomerative.py    bottom-up (AHC)
    divisive.py         top-down (DHC)
    linkage.py          linkage criteria, shared by both

Methods here are transductive by default: the hierarchy is built over the
fitted sample, and labelling a new observation requires a rule the method
does not have. A subclass that can assign unseen points -- by nearest
centroid, say -- must add `InductiveMixin` and say so in its capabilities.
"""

from __future__ import annotations
