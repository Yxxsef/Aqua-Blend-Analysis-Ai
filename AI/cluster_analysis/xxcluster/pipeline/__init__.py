"""
Preprocessing and composition.

    preprocess.py   the steps of Sect. 3.3, as contracts
    compose.py      assembling steps and a method into one component

Composition uses scikit-learn's `Pipeline` rather than replacing it: that
is most of the value of inheriting the estimator contract, and a
reimplementation would only reproduce it with fewer guarantees. What is
added here is what `Pipeline` does not provide -- a composition ending in a
clusterer, which has no `predict` to call and exposes `labels_` instead.

The distinction from `cluster/hybrid` is intent. A pipeline prepares data
and then clusters it, and its steps are independently meaningful. A hybrid
is a method whose parts are not separable claims. Scaling then k-means is a
pipeline; a SOM whose map is then partitioned is a hybrid.
"""

from __future__ import annotations
