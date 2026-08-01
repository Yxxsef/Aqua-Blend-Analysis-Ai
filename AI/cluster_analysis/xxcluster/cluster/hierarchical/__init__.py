"""
Hierarchical Cluster Analysis (HCA).

Produces multi-level partitions represented as a dendrogram, from which a
partition is obtained by cutting rather than by refitting. Two
construction directions, sharing the same components -- a dissimilarity
measure and a linkage criterion:

    agglomerative/      bottom-up (AHC)
    divisive/           top-down (DHC)
    base.py             the family base, shared by both directions
    linkage.py          linkage criteria, shared by both

The two directions are packages rather than modules because each is a
subfamily of `core.types.SubFamily`, and a concrete method belongs in the
package for its subfamily -- `agglomerative/ward.py`, not
`agglomerative.py` holding every variant. `linkage.py` stays here: a
criterion is shared by both directions and belongs to neither.

Methods here are transductive by default: the hierarchy is built over the
fitted sample, and labelling a new observation requires a rule the method
does not have. A subclass that can assign unseen points -- by nearest
centroid, say -- must add `InductiveMixin` and say so in its capabilities.
"""

from __future__ import annotations
