"""
Model-based methods.

Treats the data as a realisation of a model and clusters by fitting it:
mixture models, where each component is a cluster and membership is a
posterior probability, and topology-preserving models such as the
Self-Organising Map, where the model is a lattice of prototypes.

The two differ in what the model gives back. A mixture model yields a
likelihood, hence BIC and AIC as a principled route to the number of
clusters -- an alternative to the internal indices of Sect. 4.2 -- and
cluster shapes richer than the isotropic assumption of the SSE family.
A SOM yields a low-dimensional topology, which is why the literature of
Sect. 2.3 pairs it with a second clustering step over the fitted map:
that composition belongs in `cluster/hybrid`, while the map itself
belongs here.
"""

from __future__ import annotations
