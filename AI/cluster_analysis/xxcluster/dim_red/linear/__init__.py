"""
Linear dimensionality reduction techniques.

Carried over from the original `linear_dr.py`: implement linear
dimensionality reduction techniques, e.g. PCA, LDA.

Each learns a linear map from the n input features to n_components
directions. Two properties follow and are relied on elsewhere: the map
applies to unseen observations, so these techniques are inductive; and it
is invertible on its image, so `inverse_transform` reconstructs an
approximation in the original feature space -- which is what allows a
component to be interpreted in terms of the measured variables rather
than as an abstract axis.

Note that supervised techniques belong here too. LDA uses labels to find
its directions, so within this project it applies only where a label
exists -- a prior clustering, or an external classification -- and never
before clustering on the same data, which would leak the partition into
its own input.
"""

from __future__ import annotations
