# Adding a clustering method

> **Status: verified.** Carried out for K-Means; see
> [worked-example.md](worked-example.md). The commands below were run against
> this repository.

**Read [00-the-contract.md](00-the-contract.md) first.** Placement rule:
[CONTRIBUTING §2.2](../CONTRIBUTING.md#22-where-your-contribution-goes).
Procedure as policy: [§2.3](../CONTRIBUTING.md#23-adding-a-clustering-method).
Pairing table: [§2.3.1](../CONTRIBUTING.md#231-what-must-agree).

**File:** `xxcluster/cluster/<family>/<subfamily>/<name>.py`

---

## Step 1 — Pick the subfamily base

Choose by **how the method builds the partition**, not by what its output looks
like. Your choice fixes what you must implement and what you inherit.

| Base | Import from | Subfamily | You must set | Native hook |
|---|---|---|---|---|
| `BasePrototypeClusterer` | `cluster.partitional.sse_based.base` | `SSE_BASED` | `cluster_centers_` | `_update_centers` |
| `BaseDensityClusterer` | `cluster.partitional.density_based.base` | `DENSITY_BASED` | (family's) | `_density_estimate`, `_extract_clusters` |
| `BaseModelBasedClusterer` / `BaseMixtureClusterer` | `cluster.partitional.model_based.base` | `MODEL_BASED` | `model_` (or `backend_`) | `_fit_once` |
| `BaseFuzzyClusterer` | `cluster.partitional.fuzzy.base` | `FUZZY` | `memberships_` | `_update_memberships`, `_update_centers` |
| `BaseGraphClusterer` | `cluster.partitional.graph_theoretic.base` | `GRAPH_THEORETIC` | (family's) | `_partition_graph` |
| `BaseAgglomerative` | `cluster.hierarchical.agglomerative.base` | `AGGLOMERATIVE` | `linkage_` **or** `children_` + `distances_` | `_build_hierarchy` |
| `BaseDivisive` | `cluster.hierarchical.divisive.base` | `DIVISIVE` | `linkage_` **or** `children_` + `distances_` | `_select_cluster`, `_split` |
| `BaseHybridClusterer` | `cluster.hybrid.base` | — | (family's) | `_check_steps` (**abstract**) |

Everything under `partitional/` except density-based and graph-theoretic also
inherits `BasePartitionalClusterer`, which requires `n_iter_`, `converged_` and
`criterion_`, and gives you `max_iter`, `tol`, `n_init`, `random_state` — plus
the restart loop itself, so you write `_fit_once` and not `_fit`.

**What you no longer set by hand.** Each family base derives whatever follows
mechanically from what you did set, so it cannot drift:

| Family | You set | The base derives |
|---|---|---|
| partitional | `labels_`, `criterion_` | `n_clusters_` |
| SSE-based | `criterion_` | `inertia_` |
| density-based | `labels_` | `n_clusters_`, `n_noise_` |
| hierarchical | either tree format | the other two of `linkage_` / `children_` / `distances_`, and `labels_` from the requested cut |
| model-based | `model_` | `predict`, `predict_proba`, `score_samples`, `sample` |

**If the subfamily package does not exist,** create it with `__init__.py` and
`base.py` modelled on an existing one, and check the name is already in
`core.types.SubFamily`. When you write that `base.py`, the native-hook rule in
[00-the-contract.md §5](00-the-contract.md#the-native-hook-rule-if-you-are-writing-a-base-class)
is the one that matters — get it wrong and nobody can ever adapt a backend into
your subfamily.

**If none of them fits,** subclass `BaseClusterer` directly and justify it in
the module docstring. Do not force a method into a base whose assumptions it
does not share; the base classes carry claims, not just code.

---

## Step 2 — Adapt, or write it natively

### Adapting (the default)

```python
@register("dbscan")
class DBSCAN(AdaptedClusterer, BaseDensityClusterer):
    _backend_import = "sklearn.cluster.DBSCAN"
    _param_map = {"metric": "metric"}       # identity — omit if nothing differs
    _attr_map = {}
    _capabilities = Capabilities(...)
```

`AdaptedClusterer` **first** in the bases. `_fit` is inherited; you write none.

Three things adapters routinely need:

**A parameter the backend has no equivalent for** — map it to `None` to drop
it rather than passing it:

```python
_param_map = {"metric": None}    # sklearn's KMeans is Euclidean-only
```

If you do this, **reject the value in `_fit` rather than ignoring it**. A
silently discarded `metric="manhattan"` is a wrong result that looks fine.

**An attribute the backend does not report** — derive it:

```python
def _derive_missing(self) -> None:
    super()._derive_missing()
    self.converged_ = bool(self.n_iter_ < self.max_iter)
```

**A method that generalises to unseen points** — delegate, with the guard:

```python
def predict(self, X):
    ensure_fitted(self, "backend_")
    return self.backend_.predict(X)
```

The `ensure_fitted` guard is **not optional**. scikit-learn ≥ 1.6 checks that
`predict` raises `NotFittedError` before a fit; bare delegation raises
`AttributeError: no attribute 'backend_'` and fails `check_estimator`.

### Writing it natively

Subclass the family base and implement the subfamily's native hooks. **Do not
write `_fit`.** `BasePartitionalClusterer._fit` is concrete: it derives one
seed per restart from `random_state`, runs `_fit_once` for each, keeps the best
and installs it. A second restart loop in your class is the duplication the
family base exists to prevent — and it would run the restarts under a different
seeding scheme, so your method's `n_init` would not mean what every other
method's `n_init` means in Sect. 8.1.

`_fit_once` returns **a mapping of fitted attribute name to value**, with the
trailing underscores, so the loop installs the winner with `setattr` and there
is no second vocabulary to agree on. It must contain `criterion_`; that is what
the restarts are compared on.

```python
@register("kmedoids")
class KMedoids(BasePrototypeClusterer):
    def _fit_once(self, X, random_state):
        centers = self._initialise(X, random_state)
        for n_iter in range(1, self.max_iter + 1):
            labels = self._assign(X, centers)
            centers = self._update_centers(X, labels)
            ...
        return {
            "labels_": labels,
            "cluster_centers_": centers,
            "criterion_": cost,
            "n_iter_": n_iter,
            "converged_": converged,
        }
```

You do not return `n_clusters_` or `inertia_`. `_derive_fitted` recomputes
`n_clusters_` from `labels_` and mirrors `criterion_` into `inertia_`, so the
two names for the SSE cannot drift apart. Override `_derive_fitted` (calling
`super()` first) only if your subfamily adds another attribute that follows
mechanically from the ones `_fit_once` sets.

**Declare the direction of your criterion.** The loop minimises by default,
which is right for an SSE. A method whose criterion improves upwards — a
log-likelihood — sets `_criterion_higher_is_better = True` on the class, as
`BaseModelBasedClusterer` already does for its whole family. Get this wrong and
every fit silently returns the *worst* restart of the batch.

Everything else the family declares in `_required_fitted` is yours to set.

Set `backend=Backend.NATIVE` and cite the formulation you followed in the
module docstring — a native implementation exists because following the
document's formulation is the point, so say which equations you implemented.

---

## Step 3 — Declare capabilities

Fill from your write-up, not from memory. Every field is a claim Sect. 8.2 will
print. See [CONTRIBUTING §2.3.1](../CONTRIBUTING.md#231-what-must-agree) for
which document paragraph owns each one.

```python
_capabilities = Capabilities(
    family=Family.PARTITIONAL,
    subfamily=SubFamily.DENSITY_BASED,
    backend=Backend.SKLEARN,
    assignment=Assignment.CRISP,
    is_inductive=False,
    produces_hierarchy=False,
    supports_precomputed=True,
    requires_n_clusters=False,
    handles_noise=True,
    handles_missing=False,
    handles_categorical=False,
    scale_invariant=False,
    deterministic=True,
    scales_to=Scaling.MEDIUM,
    time_complexity="O(m log m)",
    space_complexity="O(m)",
    references=("ref_12",),
    doc_label="sec:tech:dbscan",
)
```

Four that are got wrong most often:

- **`deterministic`** means *same input and seed give the same partition*. A
  method with seeded restarts is **not** deterministic — it is reproducible,
  which is a different claim.
- **`scale_invariant`** is almost always `False` for anything distance-based.
  This declaration is what justifies the scaling step of Sect. 3.3; declaring
  `True` quietly removes that justification.
- **`is_inductive`** requires a real `predict`. Most density-based and
  hierarchical methods are transductive — declaring otherwise corrupts any
  pipeline that later calls `predict`.
- **`handles_noise`** requires `noise_mask`, which `NoiseAwareMixin` provides.
  It also decides whether `n_noise` appears in your Sect. 8.1 row at all.

`doc_label` must equal your section's `\label`. `references` are the
`literature.bib` keys you actually cite ([CONTRIBUTING §1.6](../CONTRIBUTING.md#16-references-and-academic-integrity)).
Leave `references` empty rather than guessing — an unfounded citation is worse
than a missing one.

---

## Step 4 — Register

```python
@register("dbscan")
```

No `kind=`. The name is **permanent** — it lands in stored artefacts and in the
Sect. 8 tables.

---

## Step 5 — Verify

```bash
python -c "
from sklearn.datasets import load_iris
from sklearn.utils.estimator_checks import check_estimator
from xxcluster.cluster.<family>.<subfamily>.<name> import <Class>
from xxcluster.core.registry import REGISTRY

X = load_iris().data
m = <Class>(<args>).fit(X)

print('labels_    ', m.labels_[:8])
print('n_clusters_', m.n_clusters_)
for attr in type(m)._required_fitted_attributes():
    print(f'  {attr:20s}', hasattr(m, attr))

check_estimator(<Class>(<args>)); print('check_estimator PASSED')
print(REGISTRY.capabilities('<name>').describe())
"
```

Every attribute the chain declares must be present. That loop over
`_required_fitted_attributes()` is the fastest way to see what your base
expects of you.

Then score it, which is the real check that it produced something:

```bash
python -c "
from sklearn.datasets import load_iris
from xxcluster.measures.validation.internal import Silhouette
from xxcluster.cluster.<...> import <Class>
X = load_iris().data
print(Silhouette().score(X, <Class>(<args>).fit(X).labels_))
"
```

If your method produces noise, Silhouette will refuse it — correctly, since it
is undefined on unassigned points. That is a real constraint on your notebook,
not a bug; see [validity-index-internal.md](validity-index-internal.md).

---

## Step 6 — The write-up and the notebook

Copy `template/method_template.tex` into
`documentation/sections/clustering_methods/<family>/<subfamily>/<nn>-<name>.tex`,
mirroring the code tree. Replace every label suffix; `sec:tech:<name>` must
equal `Capabilities.doc_label`. `\input` it from `cluster_main.tex`.

Then [notebook.md](notebook.md). One notebook, one contribution.

---

## Common mistakes

| Symptom | Cause |
|---|---|
| `Can't instantiate abstract class X with abstract methods _density_estimate` | your subfamily base made a native hook `@abstractmethod`; it must raise `NotImplementedError` instead |
| `_fit did not set: converged_` | the backend has no such attribute — derive it in `_derive_missing` |
| `check_mixin_order` fails | a scikit-learn mixin is right of `BaseComponent`, or the adapter is not first |
| `criterion_` and `inertia_` disagree | map both: `_attr_map = {"criterion_": "inertia_"}` |
| Sect. 8.2 row is all defaults | `_capabilities` never declared — the default `Capabilities()` is what prints |
| `predict` raises `AttributeError` pre-fit | missing `ensure_fitted(self, "backend_")` |
