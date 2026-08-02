from ....core.adapters import AdaptedClusterer
from ....core.registry import register
from ....core.tags import Capabilities
from ....core.types import Backend, Assignment, Family, Scaling, SubFamily
from ....core.validation import ensure_fitted
from .base import BasePrototypeClusterer


@register("kmeans")
class KMeans(AdaptedClusterer, BasePrototypeClusterer):
    _backend_import = "sklearn.cluster.KMeans"
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
