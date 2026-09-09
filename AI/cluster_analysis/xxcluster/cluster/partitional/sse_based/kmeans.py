from ....core.adapters import AdaptedClusterer
from ....core.registry import register
from ....core.tags import Capabilities
from ....core.types import Backend, Assignment, Family, Scaling, SubFamily
from ....core.validation import ensure_fitted
from .base import BasePrototypeClusterer


@register("kmeans")
class KMeans(AdaptedClusterer, BasePrototypeClusterer):
    _backend_import = "sklearn.cluster.KMeans"
    # Dropped rather than translated: scikit-learn's K-Means is Euclidean-only.
    # `_validate_params` below refuses any other value, so nothing is discarded
    # silently.
    _param_map = {"metric": None}
    _attr_map = {"criterion_": "inertia_"}
    _capabilities = Capabilities(
        family = Family.PARTITIONAL,
        subfamily = SubFamily.SSE_BASED,
        backend = Backend.SKLEARN,
        assignment = Assignment.CRISP,
        is_inductive = True,          # `predict` below; enforced by _check_capabilities
        requires_n_clusters = True,
        # Distances are Euclidean over the raw columns, so a feature in a
        # larger unit dominates the criterion. This is the declaration that
        # justifies the scaling step of Sect. 3.3.
        scale_invariant = False,
        # `n_init` restarts from a stochastic k-means++ initialisation.
        # Reproducible under a fixed seed, which is not the same thing.
        deterministic = False,
        scales_to = Scaling.LARGE,
        time_complexity = "O(m n |C| t)",
        space_complexity = "O((m + |C|) n)",
        doc_label = "sec:tech:kmeans",
    )

    def _validate_params(self) -> None:
        """Refuse a measure this method cannot fit under.

        `metric` is inherited from the family but never reaches the backend.
        Refusing it here rather than dropping it keeps a partition from being
        reported under a measure that never ran, the same reason
        `BasePrototypeClusterer._check_metric` refuses a precomputed matrix.
        """
        super()._validate_params()
        if self.metric != "euclidean":
            raise ValueError(
                f"{type(self).__name__} minimises the squared Euclidean "
                f"criterion, for which the mean is the minimiser, so it cannot "
                f"fit under metric={self.metric!r}. Use a medoid or median "
                f"method, whose prototype matches its measure."
            )

    def predict(self, X):
        ensure_fitted(self, "backend_")
        return self.backend_.predict(X)

    def transform(self, X):
        ensure_fitted(self, "backend_")
        return self.backend_.transform(X)

    def _derive_missing(self):
        """
            Fill in what scikit-learn does not have
        """
        super()._derive_missing()
        self.converged_ = bool(self.n_iter_ < self.max_iter)
