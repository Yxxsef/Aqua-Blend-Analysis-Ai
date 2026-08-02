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
Everything that does not depend on a clustering algorithm is implemented
and tested; no clustering method or reduction technique is yet. Abstract
methods have empty bodies, and a concrete method not yet written raises
`NotImplementedError` -- as does one refusing something it genuinely
cannot do. See `xxcluster/README.md`.

Requires scikit-learn >= 1.6; see `requirements.txt`.
"""

from __future__ import annotations

#: Floor from `requirements.txt`. Checked here because the APIs the contract
#: depends on -- `validate_data`, `ensure_all_finite` -- were introduced in
#: 1.6, and importing against an older release otherwise fails with a bare
#: `ImportError` naming a symbol that means nothing to the reader.
_MIN_SKLEARN = (1, 6)

def _check_sklearn() -> None:
    import sklearn

    installed = tuple(int(part) for part in sklearn.__version__.split(".")[:2])
    if installed < _MIN_SKLEARN:
        raise ImportError(
            f"xxcluster needs scikit-learn >= "
            f"{'.'.join(map(str, _MIN_SKLEARN))}, but {sklearn.__version__} is "
            f"installed. 1.6 moved `_validate_data` off BaseEstimator and "
            f"renamed `force_all_finite`, both of which the component contract "
            f"uses. Upgrade with `pip install -r requirements.txt`."
        )


_check_sklearn()
del _check_sklearn

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
