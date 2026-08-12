"""
Sum-of-squared-error methods.

Prototype-based methods whose criterion is the SSE between observations
and the prototype of their assigned cluster: k-means and its variants,
k-medoids and k-medians among them. The prototype is what makes the family
inductive -- a new observation is assigned to the nearest one -- and what
makes it assume compact, roughly isotropic clusters of comparable size.

The prototype also carries the interpretation: a cluster centre in the
original feature space is what Sect. 4.4 turns into a named operating
regime, which is why `cluster_centers_` is part of the contract here
rather than an implementation detail.
"""

from __future__ import annotations
