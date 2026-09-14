"""
xxcluster/cluster/partitional/model_based/gmm.py

Gaussian mixture clustering (Task 42, Sect. 7.4.2).

Adapts scikit-learn's GaussianMixture. The family base
(BaseMixtureClusterer) already implements `predict`, `predict_proba`,
`score_samples` and `sample` by delegating to `self._model()`, so this
class supplies only what the family base cannot infer on its own: the
adapter wiring, the capability declaration, and `n_parameters_` -- the one
quantity `ProbabilisticMixin.bic`/`.aic` need that the backend does not
expose as public API.

Code counterpart of: documentation/sections/clustering_methods/
    partitional/model_based/<nn>-gmm.tex
"""

from __future__ import annotations

from typing import ClassVar

from ....core.adapters import AdaptedClusterer
from ....core.registry import register
from ....core.tags import Capabilities
from ....core.types import Assignment, Backend, Family, Scaling, SubFamily
from .base import BaseMixtureClusterer

# Covariance-parameter count per component, by covariance_type. Matches
# scikit-learn's own (private) GaussianMixture._n_parameters(), reproduced
# here rather than called, so the formula is visible and citable in the
# write-up (Sect. 7.4.2, Formulation) instead of resting on an
# undocumented private method that could change across sklearn versions
# without our contract noticing.
#
#   full:      each component gets its own full covariance matrix:
#              n * (n + 1) / 2 free entries (symmetric, n(n+1)/2 upper
#              triangle including the diagonal).
#   tied:      one covariance matrix shared by every component:
#              n * (n + 1) / 2 total, not per component.
#   diag:      each component gets its own diagonal covariance: n entries.
#   spherical: each component gets one scalar variance: 1 entry.
def _covariance_parameters(n_components: int, n_features: int, covariance_type: str) -> int:
    if covariance_type == "full":
        return n_components * n_features * (n_features + 1) // 2
    if covariance_type == "tied":
        return n_features * (n_features + 1) // 2
    if covariance_type == "diag":
        return n_components * n_features
    if covariance_type == "spherical":
        return n_components
    raise ValueError(
        f"Unknown covariance_type={covariance_type!r}; expected one of "
        f"'full', 'tied', 'diag', 'spherical'."
    )


@register("gaussian_mixture")
class GaussianMixture(AdaptedClusterer, BaseMixtureClusterer):
    """Gaussian mixture model, adapted from scikit-learn.

    Models each regime as a Gaussian component rather than a single
    prototype, so `covariance_type="full"` recovers elongated and
    correlated clusters the SSE family (Sect. 7.4.1) cannot, at the cost
    of the extra parameters `n_parameters_` charges against it in `bic`
    and `aic`.

    No `__init__` override: `BaseMixtureClusterer.__init__` already
    declares every parameter this class needs (`n_clusters`,
    `covariance_type`, `max_iter`, `tol`, `n_init`, `random_state`), and
    they take the same meaning here as there. Only the *name* `n_clusters`
    differs from the backend's `n_components`, which `_param_map` handles.

    Fitted attributes
    ------------------
    n_parameters_ : int
        Free parameters of the fitted mixture, computed from
        `covariance_type` (see `_covariance_parameters`). Read by
        `ProbabilisticMixin.bic` / `.aic`.
    """

    _backend_import = "sklearn.mixture.GaussianMixture"

    # Identity by default; list only the differences (GUIDELINES/
    # 00-the-contract.md, rule 5). n_clusters is the contract's name for
    # the requested cluster count; scikit-learn calls the same thing
    # n_components on GaussianMixture, since "component" is the mixture
    # term and "cluster" is ours.
    _param_map = {"n_clusters": "n_components"}

    # criterion_ is required by BasePartitionalClusterer, and this family
    # is maximised (_criterion_higher_is_better = True, declared on
    # BaseModelBasedClusterer). scikit-learn's GaussianMixture reports the
    # converged model's average per-sample log-likelihood as
    # `lower_bound_`, which is exactly that criterion, so this is a
    # rename, not a derivation.
    _attr_map = {"criterion_": "lower_bound_"}

    # doc_label is a forward reference until the write-up lands, the same
    # pattern GUIDELINES/worked-example.md records for K-Means's own
    # sec:tech:kmeans at the equivalent stage. Task 53's registry sweep
    # will catch it if the section is never written.
    #
    # references: ref_13 (De Santi et al., 2025) and ref_5 (Xu & Tian,
    # 2015) are already assigned keys in the task's own reading list, so
    # they are cited here directly. Fraley & Raftery (2002) and Dempster,
    # Laird & Rubin (1977) are read but have no ref_<n> yet -- per
    # CONTRIBUTING.md Sect. 1.6, a key is not invented here; add them to
    # the shared mapping sheet first, then extend this tuple.
    _capabilities: ClassVar[Capabilities] = Capabilities(
        family=Family.PARTITIONAL,
        subfamily=SubFamily.MODEL_BASED,
        backend=Backend.SKLEARN,
        is_inductive=True,
        requires_n_clusters=True,
        handles_noise=False,
        # Both left undeclared on the K-Means skeleton in GUIDELINES/
        # worked-example.md, which the contract explicitly warns against:
        # a field left at its default is a claim, not a blank. sklearn's
        # GaussianMixture accepts neither missing values nor raw
        # categorical features without preprocessing, so declaring both
        # False here is a checked fact about the backend, not an
        # oversight left for the default to paper over.
        handles_missing=False,
        handles_categorical=False,
        assignment=Assignment.PROBABILISTIC,
        deterministic=False,  # EM restarts from random initialisations
        scale_invariant=False,  # likelihood depends on the feature scale
        # One EM iteration is dominated by the E-step responsibility
        # matrix, O(m * n_components * n_features), and, for
        # covariance_type="full", the M-step's per-component covariance
        # estimate, O(n_components * n_features^2). Space is dominated by
        # storing one full covariance matrix per component,
        # O(n_components * n_features^2), against O(n_components *
        # n_features) for every other covariance_type.
        time_complexity="O(m * n_components * n_features^2) per EM iteration (full covariance)",
        space_complexity="O(n_components * n_features^2) (full covariance)",
        scales_to=Scaling.MEDIUM,
        doc_label="sec:tech:gmm",
        references=("ref_13", "ref_5"),
    )

    def _fit(self, X, y=None, **fit_params):
        """Fit the backend, then set `labels_`.

        Overrides `AdaptedClusterer._fit` (rather than relying on it
        unmodified, as most adapters do) for one reason: scikit-learn's
        `GaussianMixture` has no `labels_` as fitted state, only
        `predict(X)` as a method -- a mixture's natural output is
        `predict_proba`, and a crisp partition is a defuzzification of it,
        not something the backend stores. `BackendAdapter._derive_missing`
        derives `n_clusters_` from `labels_`, so without this override
        neither attribute would ever be set, and `_check_fitted` would
        fail naming both.

        `self.backend_.predict(X)` rather than `self.predict(X)`: the
        latter goes through `_validate_input(X, reset=False)`, which
        requires `n_features_in_` to already exist -- it is set by the
        base `fit()` template method's `_validate_input(X, reset=True)`
        step, but only *after* `_fit` returns, so calling the public
        `predict` from inside `_fit` would fail on a fresh fit.
        """
        self.backend_ = self._build_backend()
        self.backend_.fit(X, **fit_params)
        self.labels_ = self.backend_.predict(X).astype(int)
        self._collect_fitted()

    def _derive_missing(self) -> None:
        """Set `n_clusters_` (via the base class) and `n_parameters_`.

        Calls `super()` first per the contract (GUIDELINES/
        00-the-contract.md, rule 5): `BackendAdapter._derive_missing`
        derives `n_clusters_` from `labels_`, which `_fit` above has
        already set by this point. This override adds only what is
        specific to a mixture's parameter count.
        """
        super()._derive_missing()
        n_features = self.n_features_in_
        n_components = self.n_clusters_
        covariance_type = self.covariance_type

        covariance_params = _covariance_parameters(
            n_components, n_features, covariance_type
        )
        mean_params = n_components * n_features
        weight_params = n_components - 1  # weights sum to 1

        self.n_parameters_ = covariance_params + mean_params + weight_params
