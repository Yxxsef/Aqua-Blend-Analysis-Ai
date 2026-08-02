# Adding a dimensionality reduction technique

> **Status: derived from the contract.** No reducer exists yet. The base
> classes, `AdaptedDimReducer` and the template are real and were read
> directly; the skeletons below are import-checked but have not been fitted end
> to end. **You are the first — correct this file as you go.**

**Read [00-the-contract.md](00-the-contract.md) first.** Placement:
[CONTRIBUTING §2.2](../CONTRIBUTING.md#22-where-your-contribution-goes).
The base-class decision and the pairing table:
[§2.4](../CONTRIBUTING.md#24-adding-a-dimensionality-reduction-technique) —
read it before this page, it owns that decision.

**File:** `xxcluster/dim_red/<linear|nonlinear>/<name>.py`

---

## Step 1 — Pick the base by what the technique *assumes*

CONTRIBUTING §2.4 states the rule; here is what each choice costs you in code.

| Base | You inherit | You must implement | You must set |
|---|---|---|---|
| `BaseLinearReducer` | `transform`/`inverse_transform` slots | `_fit` | `components_`, `mean_`, `explained_variance_ratio_`, plus `embedding_`, `n_components_` |
| `BaseKernelReducer` | `PrecomputedMixin` (kernel) | `_fit` | as above, kernel-flavoured |
| `BaseManifoldReducer` | `PrecomputedMixin` (dissimilarity), `n_neighbors` | `_fit` | `embedding_`, `n_components_`; `stress_` where defined |
| `BaseNonlinearReducer` | nothing beyond `BaseDimReducer` | `_fit`, and say why in the docstring | `embedding_`, `n_components_` |

`BaseDimReducer` requires `embedding_` and `n_components_` of everyone, and
gives you `n_components` and `random_state` as parameters.

**Kernel PCA is the trap.** It is nonlinear but inductive, deterministic,
spectral, and takes a kernel matrix rather than a neighbourhood graph — so it
is *not* manifold learning. Putting it under `BaseManifoldReducer` attaches
five false claims to it at once, and gives it an `n_neighbors` it has no use
for.

---

## Step 2 — Decide `is_inductive`, honestly

This is the declaration that matters most in this kind, because getting it
wrong corrupts results silently rather than failing.

- A **linear or kernel** map applies to unseen points. `is_inductive=True`.
- **Most manifold learners** embed only the sample they were fitted on.
  `is_inductive=False`.

`AdaptedDimReducer.transform` already enforces this for you:

```python
def transform(self, X):
    ensure_fitted(self, "backend_")
    if not self._capabilities.is_inductive:
        raise NotImplementedError(
            f"{type(self).__name__} is transductive: it embeds only the "
            f"observations it was fitted on. Use `embedding_` for those, "
            f"or refit on the combined data and say so in the write-up."
        )
    return self.backend_.transform(X)
```

**Refitting to accommodate new points is never an acceptable implementation.**
It changes the embedding of every existing point, so any figure drawn from it
is of a model that was never reported.

UMAP is the awkward case: it *has* a `transform`, but it approximates. Declare
`is_inductive=True` and say in the *Out-of-sample and inverse mapping*
paragraph that the extension is approximate — that paragraph is exactly where a
reviewer checks this.

---

## Step 3 — Write it

### Adapting

```python
@register("pca")
class PCA(AdaptedDimReducer, BaseLinearReducer):
    _backend_import = "sklearn.decomposition.PCA"
    _attr_map = {
        "components_": "components_",
        "mean_": "mean_",
        "explained_variance_ratio_": "explained_variance_ratio_",
    }
    _capabilities = Capabilities(
        backend=Backend.SKLEARN,
        is_inductive=True,
        deterministic=True,
        scale_invariant=False,
        scales_to=Scaling.LARGE,
        time_complexity="O(m n min(m, n))",
        doc_label="sec:dimred:pca",
    )
```

`AdaptedDimReducer._fit` calls the backend's **`fit_transform`**, not `fit`,
and assigns `embedding_` — a transductive technique has no other way to expose
its embedding, and for an inductive one the backend computes the same thing
either way. `_derive_missing` then sets `n_components_` from
`embedding_.shape[1]`, so you usually need not.

Identity entries in `_attr_map` are unnecessary — lookup defaults to the same
name. List only what differs. (They are shown above for clarity; delete them.)

### Natively

Implement `_fit`, and `transform`/`inverse_transform` if linear:

```python
@register("mypca")
class MyPCA(BaseLinearReducer):
    def _fit(self, X, y=None, **fit_params):
        self.mean_ = X.mean(axis=0)
        ...
        self.components_ = V[: self.n_components]
        self.explained_variance_ratio_ = ...
        self.embedding_ = (X - self.mean_) @ self.components_.T
        self.n_components_ = self.components_.shape[0]

    def transform(self, X):
        ensure_fitted(self, "components_")
        X = self._validate_input(X, reset=False)
        return (X - self.mean_) @ self.components_.T
```

Note `reset=False` on a `transform` — it checks the new data against the
recorded `n_features_in_` rather than overwriting it.

---

## Step 4 — Verify

```bash
python -c "
from sklearn.datasets import load_iris
from sklearn.utils.estimator_checks import check_estimator
from xxcluster.dim_red.<linear|nonlinear>.<name> import <Class>

X = load_iris().data
r = <Class>(n_components=2).fit(X)

print('embedding_   ', r.embedding_.shape)
print('n_components_', r.n_components_)
print('inductive?   ', r._capabilities.is_inductive)
try:
    print('transform    ', r.transform(X[:5]).shape)
except NotImplementedError as e:
    print('transform    refused (transductive):', str(e)[:60])

check_estimator(<Class>(n_components=2)); print('check_estimator PASSED')
"
```

Then the two results the write-up needs:

```bash
# structure preservation
python -c "... r.explained_variance_ratio_ ...      # linear/kernel
           ... r.trustworthiness(X) ...             # manifold"

# downstream effect — the finding Sect. 6 actually reports
python -c "
from xxcluster.evaluation.report import ComparisonRun
from xxcluster.evaluation.protocol import Protocol
from xxcluster.pipeline.compose import make_cluster_pipeline
# score the same clustering method with and without the reduction
"
```

That second one is the point of the whole contribution, and
[CONTRIBUTING §2.4](../CONTRIBUTING.md#24-adding-a-dimensionality-reduction-technique)
lists it as paragraph 9. A reduction that improves the embedding and worsens
the clustering is a finding, not a failure — report it.

---

## Step 5 — Write-up and notebook

`template/dimreduction_template.tex` into
`documentation/sections/dimensionality/<name>.tex`. Labels `sec:dimred:<name>:*`.
Then [notebook.md](notebook.md).

The paragraphs with a code counterpart are in
[CONTRIBUTING §2.4](../CONTRIBUTING.md#24-adding-a-dimensionality-reduction-technique);
paragraph 4 (out-of-sample) and paragraph 9 (results) are the two a reviewer
will check against your declarations.

---

## The caveat every nonlinear technique carries

From `BaseNonlinearReducer`'s own docstring, and it belongs in your
*Limitations* paragraph verbatim:

> Distances in the embedding are not the input distances. Neighbourhood
> structure may be preserved while global geometry, cluster sizes and apparent
> density are not — so a validity index computed on the embedding measures the
> embedding, not the data.

This has a direct consequence for Sect. 8: a silhouette computed on a UMAP
embedding is not comparable to one computed on raw features. If your notebook
scores in the reduced space, say so in §10.

---

## Common mistakes

| Symptom | Cause |
|---|---|
| Kernel PCA with an `n_neighbors` parameter | wrong base — it is not manifold learning |
| `transform` silently returns a different embedding each call | refitting inside `transform`; never do this |
| `_fit did not set: n_components_` | you set `embedding_` after calling `_collect_fitted`, so `_derive_missing` saw nothing |
| A manifold learner declared `is_inductive=True` | it will corrupt any pipeline that calls `predict` downstream |
| `check_estimator` fails on `transform` shape | validate with `reset=False`, not `reset=True` |
