# Worked example: K-Means and Silhouette, start to finish

> **Status: verified.** Every command on this page was run against this repository. The numbers shown are the numbers it produced.

This is one complete contribution, carried out. Read it alongside [clustering-method.md](clustering-method.md), [validity-index-internal.md](validity-index-internal.md) and [notebook.md](notebook.md); those give the general rule, this shows what it looks like when actually done.

**Order matters:** the index first, then the method. `ComparisonRun` needs an index to exist, and Silhouette gives you something to check K-Means with immediately.

---

## 1. Silhouette: `measures/validation/internal.py`

Appended to the existing module, beside `BaseInternalIndex`.

```python
@register("silhouette")          # kind comes from BaseValidityIndex._kind
class Silhouette(BaseInternalIndex):
    """Mean silhouette coefficient over all observations.

    Compares each observation's mean distance to its own cluster against
    its mean distance to the nearest other cluster, so it rewards
    compact, well-separated clusters, the shape the SSE family
    produces. Scoring K-Means and a density-based method with it does not
    rank them neutrally; see Sect. 4.5.

    Applied per Sect. 4.2.
    """

    name = "silhouette"
    higher_is_better = True
    range_ = (-1.0, 1.0)
    handles_noise = False
    assumes_shape = "compact, isotropic"

    def score(self, X=None, labels=None, *, labels_true=None,
              metric="euclidean", **kwargs):
        from sklearn.metrics import silhouette_score
        labels = check_labels(labels, allow_noise=self.handles_noise)
        return silhouette_score(X, labels, metric=metric)
```

Two declarations doing real work:

- **`handles_noise = False`, enforced by `allow_noise=self.handles_noise`.** A caller scoring a DBSCAN result now gets an error naming the problem instead of a number that treats noise as cluster `-1`.
- **`assumes_shape`** is the caveat `internal.py` requires of every class in the group, and the single most important sentence in this contribution.

**Verified:**

```bash
python -c "
from sklearn.datasets import load_iris
from sklearn.cluster import KMeans
from xxcluster.measures.validation.internal import Silhouette
X = load_iris().data
print(Silhouette().score(X, KMeans(3, n_init=10, random_state=0).fit_predict(X)))
print(Silhouette().is_better(0.55, 0.41))
"
```

```
0.5528190123564091
True
```

`0.5528` is the published value for iris at |C|=3. That agreement is what makes this an implementation rather than a plausible function.

---

## 2. K-Means: `cluster/partitional/sse_based/kmeans.py`

A new module, at the path CONTRIBUTING §2.2 dictates: `cluster/<family>/<subfamily>/<name>.py`. The package and `SubFamily.SSE_BASED` already existed.

```python
from ....core.adapters import AdaptedClusterer
from ....core.registry import register
from ....core.tags import Capabilities
from ....core.types import Assignment, Backend, Family, Scaling, SubFamily
from ....core.validation import ensure_fitted
from .base import BasePrototypeClusterer


@register("kmeans")
class KMeans(AdaptedClusterer, BasePrototypeClusterer):
    _backend_import = "sklearn.cluster.KMeans"
    _param_map = {"metric": None}
    _attr_map = {"criterion_": "inertia_"}
    _capabilities = Capabilities(
        family=Family.PARTITIONAL,
        subfamily=SubFamily.SSE_BASED,
        backend=Backend.SKLEARN,
        assignment=Assignment.CRISP,
        is_inductive=True,
        requires_n_clusters=True,
        scale_invariant=False,
        deterministic=False,
        scales_to=Scaling.LARGE,
        time_complexity="O(m n |C| t)",
        space_complexity="O((m + |C|) n)",
        doc_label="sec:tech:kmeans",
    )

    def predict(self, X):
        ensure_fitted(self, "backend_")
        return self.backend_.predict(X)

    def transform(self, X):
        ensure_fitted(self, "backend_")
        return self.backend_.transform(X)

    def _derive_missing(self):
        """Fill in what scikit-learn does not report."""
        super()._derive_missing()
        self.converged_ = bool(self.n_iter_ < self.max_iter)
```

### Why each line is there

**`AdaptedClusterer` first.** The MRO must reach `AdaptedClusterer._fit` before `BasePartitionalClusterer._fit`. The family base's `_fit` is the native restart loop: it calls `_fit_once`, which an adapted method does not implement. Order the bases the other way and K-Means fits by running our loop around a hook that raises, instead of by handing the whole fit to the backend:

```
KMeans -> AdaptedClusterer -> BackendAdapter -> BasePrototypeClusterer
       -> InductiveMixin -> TransformerMixin -> _SetOutputMixin
       -> BasePartitionalClusterer -> BaseClusterer -> ClusterMixin
       -> BaseComponent -> BaseEstimator -> ...
```

Print your own rather than trusting this one: `python -c "from ... import X; print(' -> '.join(c.__name__ for c in X.__mro__))"`.

`InductiveMixin` is **not** added by hand; `BasePrototypeClusterer` already carries it, because the family is inductive by construction.

**`_param_map = {"metric": None}`** drops the parameter. `BasePrototypeClusterer` exposes `metric`, but scikit-learn's K-Means is Euclidean-only. Mapping to `None` keeps it from reaching the backend. *Still outstanding: `_fit` should reject a non-Euclidean value rather than ignoring it; a silently discarded `metric="manhattan"` is a wrong result that looks fine.*

**`_attr_map = {"criterion_": "inertia_"}`**: one backend attribute feeding two contract names. `_collect_fitted` looks up each required attribute through the map, defaulting to the same name, so `criterion_` redirects to the backend's SSE while `inertia_` resolves to itself.

**`_derive_missing` sets `converged_`.** scikit-learn exposes `n_iter_` but no convergence flag; it signals convergence by stopping early. Without this override:

```
ContractViolationError: KMeans._fit did not set: converged_
```

which is `_check_fitted` doing its job. Call `super()` first; it derives `n_clusters_` and `n_noise_`.

**`ensure_fitted` in `predict` is not optional.** scikit-learn ≥ 1.6 checks that `predict` raises `NotFittedError` before a fit; bare delegation raises `AttributeError: no attribute 'backend_'` and fails `check_estimator`.

**Verified:**

```bash
python -c "
from sklearn.datasets import load_iris
from sklearn.utils.estimator_checks import check_estimator
from xxcluster.cluster.partitional.sse_based.kmeans import KMeans
X = load_iris().data
m = KMeans(n_clusters=3).fit(X)
print('inertia_', round(m.inertia_,3), '| criterion_', round(m.criterion_,3))
print('n_iter_', m.n_iter_, '| converged_', m.converged_)
print('cap hit ->', KMeans(n_clusters=3, max_iter=1).fit(X).converged_)
check_estimator(KMeans(n_clusters=3)); print('check_estimator PASSED')
"
```

```
inertia_ 78.851 | criterion_ 78.851
n_iter_ 6 | converged_ True
cap hit -> False
check_estimator PASSED
```

### What the capability declaration bought

Before it, `_capabilities` was the default and `REGISTRY.applicable(requires_n_clusters=True)` returned `[]`, so the shortlisting query silently found nothing. After:

```bash
python -c "
import xxcluster.cluster.partitional.sse_based.kmeans
from xxcluster.core.registry import REGISTRY
print(REGISTRY.applicable(requires_n_clusters=True))
print(REGISTRY.capabilities('kmeans').describe()['family'])
"
```

```
['kmeans']
partitional
```

Two comments earned their place in the file, because both carry an argument rather than a fact:

- `scale_invariant=False`: distances are Euclidean over raw columns, so a feature in a larger unit dominates. **This is the declaration that justifies the scaling step of Sect. 3.3.**
- `deterministic=False`: `n_init` restarts from a stochastic k-means++ initialisation. Reproducible under a fixed seed, which is **not the same claim**.

---

## 3. The notebook

`notebooks/Minh (s224236373)/kmeans_silhouette.ipynb`, from `notebooks/00-template.ipynb`. Full procedure: [notebook.md](notebook.md).

Three things had to be fixed that the template does not anticipate, all because a personal folder is one level deeper than `notebooks/`:

```python
# §1: the template's Path.cwd().parent lands on notebooks/, not cluster_analysis/
ROOT = next(p for p in Path.cwd().parents if (p / "xxcluster").is_dir())
sys.path.insert(0, str(ROOT))

# §4: the template ships `preprocessing = ...`; Ellipsis is not None
preprocessing=None,        # §5 and §6 fit on raw X; a scaler here alone
                           # would make §7 incomparable to them

# §9: ../documentation/ resolves to notebooks/documentation/ from here
TABLES = ROOT / "documentation" / "tables"
```

Result, on a restarted kernel running every cell:

```
RunResult(method='kmeans', scores={'silhouette': 0.5528},
          n_clusters_found=3, n_noise=None, fit_seconds=0.003, error=None)
```

and `documentation/tables/kmeans-results.tex`:

```latex
% Generated by xxcluster.evaluation.report -- do not edit by hand.
\begin{tabularx}{\textwidth}{@{}L l l l@{}}
  \toprule
  \textbf{method} & \textbf{silhouette} & \textbf{n\_clusters\_found} & \textbf{fit\_seconds} \\
  \midrule
  kmeans & 0.553 & 3 & 0.004 \\
  \bottomrule
\end{tabularx}
\label{tab:kmeans:results}
```

That file is `\input` into the section. No number was retyped.

### §6 was inlined

`BaseNClustersSelector._fit` and `StabilityAnalysis._fit` both raise, so the sweep was done by hand:

```python
curve = {k: Silhouette().score(X, KMeans(n_clusters=k, random_state=RANDOM_STATE)
                                        .fit(X).labels_)
         for k in protocol.n_clusters_candidates}
selected = max(curve, key=curve.get)          # the "max" criterion, inlined
```

and §10 records that stability was **not** assessed. See [selection-selector.md](selection-selector.md) and [validity-index-relative.md](validity-index-relative.md) for what unblocks it.

---

## 4. The document sections

Two sections, two templates.

```bash
mkdir -p documentation/sections/clustering_methods/partitional/sse_based
cp template/method_template.tex \
   documentation/sections/clustering_methods/partitional/sse_based/01-kmeans.tex

cp template/measure_template.tex \
   documentation/sections/clustering_methods/measures/02-silhouette.tex
```

The `sse_based/` directory did not exist, so you create it, mirroring the code tree the way `partitional/density_based/` already does.

Replace `<NAME>` and every label suffix `template` → `kmeans`: `sec:tech:template:overview` → `sec:tech:kmeans:overview`. **The section label `sec:tech:kmeans` must equal `Capabilities.doc_label`.** Then `\input` under the *Partition–based clustering methods* subsection of `cluster_main.tex`.

Fill both write-ups and both declarations **in one pass**. Sect. 8.2 is generated from the declarations, so a disagreement puts a false row in the document.

---

## 5. What was still outstanding when this was written

Listed so the §10 caveats are accurate, and because a real contribution ends with a list like this rather than with silence.

| Outstanding | Needs |
|---|---|
| `references=()` on `KMeans` | the `literature.bib` keys Sect. 7.3 actually cites, left empty rather than guessed |
| `sec:tech:kmeans` | the section does not exist yet; `doc_label` is a forward reference |
| `metric="manhattan"` silently dropped | reject it in `_fit` |
| `selection/n_clusters.py` | `_evaluate_candidate` + a concrete `BaseRelativeCriterion` |
| `selection/stability.py` | a `BasePerturbation` + a symmetric external index (ARI) |
| Sect. 8 over *configurations* | `RunResult` cannot distinguish `kmeans` from `pca+kmeans`; see `ARCHITECTURE.md §5` |

---

## Commit sequence

One branch, `task-<n>-kmeans-silhouette`.

1. `Fix the clustering contract: declared fitted attributes, adaptable bases`
2. `Add the Silhouette validity index`
3. `Add K-Means, adapting scikit-learn`
4. `Implement ComparisonRun.run and best`
5. `Add the K-Means notebook and its exported tables and figures`
6. `Add the K-Means and Silhouette sections`

Keeping the contract fix separate matters: it changes shared files in `core/`, and a reviewer should see that change without it being buried in a method commit.
