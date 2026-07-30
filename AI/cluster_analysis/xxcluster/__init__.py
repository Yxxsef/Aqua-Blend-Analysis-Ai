"""
xxcluster -- cluster analysis for the AquaBlend dataset.

The codebase accompanying `documentation/main.pdf`, *On the Search for
Cluster Analysis*. The document's structure and this package's structure
are the same structure: a method's write-up and its implementation sit at
matching addresses in the two trees, and the section numbers referenced in
docstrings here are that document's.

Layout
------
    core/         the contract everything else implements
    cluster/      clustering methods, by family (Sect. 7)
    dim_red/      dimensionality reduction (Sect. 6)
    measures/     dissimilarity and validation measures (Sect. 7.1)
    pipeline/     preprocessing and composition (Sect. 3.3)
    selection/    choosing |C| and testing stability (Sect. 4.3)
    evaluation/   the shared protocol and the comparison (Sect. 4, 8)
    io/           dataset access and artefact storage
    viz/          figures
    tasks/        end-to-end analyses; the horizontal extension point

The contract
------------
Every component is a scikit-learn estimator: parameters in `__init__`,
fitted state in trailing-underscore attributes, `fit`/`transform`/
`predict` where they apply. That choice is what lets a method written here
be used with `Pipeline` and the `*SearchCV` classes, be checked by
`check_estimator`, and be swapped for a third-party estimator without the
surrounding code noticing. See `xxcluster.core.base` for the conventions
and `xxcluster/README.md` for how to add to it.

Status
------
Skeleton. The structure, contracts and conventions are settled; no method
is implemented yet. Abstract methods have empty bodies, and concrete
methods that are not yet written raise `NotImplementedError`.
"""

from __future__ import annotations

from .core import (
    REGISTRY,
    AdaptedClusterer,
    AdaptedDimReducer,
    BaseClusterer,
    BaseComponent,
    BaseDimReducer,
    BaseGenerator,
    BaseOutlierDetector,
    BasePredictor,
    BaseTransformer,
    Capabilities,
    register,
)

__version__ = "0.1.0"

__all__ = [
    "BaseComponent",
    "BaseClusterer",
    "BaseDimReducer",
    "BaseTransformer",
    "BaseOutlierDetector",
    "BaseGenerator",
    "BasePredictor",
    "AdaptedClusterer",
    "AdaptedDimReducer",
    "Capabilities",
    "REGISTRY",
    "register",
    "__version__",
]
