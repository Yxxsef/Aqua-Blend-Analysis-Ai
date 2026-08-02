# Adding a selector

> **Status: derived from the contract, and currently blocked.**
> `BaseSelector` and `BaseNClustersSelector` were read directly, but
> `BaseSelector._evaluate_candidate` and `BaseNClustersSelector._fit` both
> raise `NotImplementedError`, and **no concrete `BaseRelativeCriterion`
> exists**. Read the *What must land first* section before starting.

**Read [00-the-contract.md](00-the-contract.md) first.** A selector's
documentation counterpart is Sect. 4.3, not a template.

**File:** `xxcluster/selection/n_clusters.py`, or a new module under
`xxcluster/selection/` for a different parameter.

---

## What a selector is

A selector **wraps a method, evaluates it over candidate configurations, and
exposes the winner**. It is itself a `BaseComponent`, so it is composable,
registrable and reportable like anything else — a selector wrapping a method is
a legitimate thing to put in a pipeline, and the search it performed then
becomes part of the recorded result rather than something a notebook did once.

Selection without labels cannot be done by held-out error, so it rests on two
substitutes: a **criterion curve** over candidate values (this page) and
**reproducibility under perturbation** ([selection-perturbation.md](selection-perturbation.md)).
They answer different questions, and a partition that is optimal by the first
and unstable under the second is not a finding.

**This applies to more than |C|.** A density-based method has no |C| to choose
but still has density parameters to sweep, and the same machinery serves both —
which is why the package says "selection" rather than "choosing k".

---

## What must land first

Three pieces, in this order. The first is the real blocker.

### 1. A concrete `BaseRelativeCriterion` — see [validity-index-relative.md](validity-index-relative.md)

`BaseNClustersSelector` promises three fitted attributes and gets two of them
from the criterion:

| Attribute | Comes from |
|---|---|
| `n_clusters_` | `criterion.select(curve)` |
| `curve_` | `criterion.curve(scores)` |
| `conclusive_` | `criterion.is_conclusive(scores)` |

Both of the latter raise `NotImplementedError` on the base class. Without a
concrete criterion there is nothing to call.

**Do not inline an argmax to get around this.** `n_clusters.py`'s own docstring
forbids it: *"Three parts, deliberately separate: generate the candidate
values, score each one, then apply a relative criterion from
`measures.validation.relative`."* Separating them is what lets the criterion
change without touching the sweep, several criteria be applied to one sweep,
and the curve stay available whatever the criterion decides.

### 2. `BaseSelector._evaluate_candidate`

```python
def _evaluate_candidate(self, X, params: dict) -> dict[str, float]:
    """Fit one candidate and score it under every `scoring` entry."""
    raise NotImplementedError
```

Roughly fifteen lines: clone the estimator, `set_params(**params)`, fit, score
under each entry of `scoring`, return the dict. It lives on the base because
every selector needs it — inlining it in `n_clusters.py` leaves the shared hook
dead and makes the next selector rewrite it.

### 3. Then `BaseNClustersSelector._fit`

---

## Step 1 — Implement `_fit`

```python
def _fit(self, X, y=None, **fit_params) -> None:
    """Sweep the candidates, build the curve, then apply the criterion."""
    candidates = list(self.candidates or ())
    if not candidates:
        raise ValueError(
            "no candidates to sweep; pass candidates=range(2, 11) or take "
            "them from protocol.n_clusters_candidates."
        )

    self.results_ = {}
    scores = {}
    for k in candidates:
        row = self._evaluate_candidate(X, {"n_clusters": k})
        self.results_[k] = row
        scores[k] = row[self._primary_index()]     # the first scoring entry

    self.curve_ = self.criterion.curve(scores)
    self.conclusive_ = self.criterion.is_conclusive(scores)
    self.n_clusters_ = self.criterion.select(scores)
    self.best_params_ = {"n_clusters": self.n_clusters_}

    if self.refit:
        self.best_estimator_ = clone(self.estimator).set_params(**self.best_params_)
        self.best_estimator_.fit(X)
        self.labels_ = self.best_estimator_.labels_
```

Five things the contract requires of you here:

**`results_` holds every candidate and every score, not only the winner.** It
is the input to the selection figure, and the record that makes a selection
auditable.

**Where several `scoring` entries are given, all are recorded and the first
decides.** Their disagreement is a result worth keeping —
[CONTRIBUTING §2.7](../CONTRIBUTING.md#27-the-contract) and `BaseSelector`'s
docstring both say so.

**`labels_` makes a fitted selector stand in for a clusterer.** Set it when
`refit` is on; that is what lets a selector sit in a pipeline.

**Clone, never mutate.** The estimator handed in is left as the caller left it.

**Report `conclusive_` even when false.** Do not override an inconclusive curve
with an arbitrary argmax — record it and let Sect. 4.5 say so.

---

## Step 2 — Sweeping something other than |C|

`BaseSelector.param_grid` is the general case; `BaseNClustersSelector` is the
special one that fixes the parameter name to `n_clusters`. For a density
parameter, subclass `BaseSelector` directly:

```python
@register("eps_selector")
class EpsSelector(BaseSelector):
    def _fit(self, X, y=None, **fit_params) -> None:
        for params in ParameterGrid(self.param_grid):
            self.results_[frozenset(params.items())] = \
                self._evaluate_candidate(X, params)
        ...
```

Density-based methods are **out of scope for `BaseNClustersSelector` by
construction** — applying it would impose a parameter they do not have. Sweep
their own parameters instead.

---

## Step 3 — Verify

```bash
python -c "
from sklearn.datasets import load_iris
from xxcluster.cluster.partitional.sse_based.kmeans import KMeans
from xxcluster.measures.validation.internal import Silhouette
from xxcluster.measures.validation.relative import <Criterion>
from xxcluster.selection.n_clusters import BaseNClustersSelector

X = load_iris().data
s = BaseNClustersSelector(
    KMeans(), candidates=range(2, 11),
    criterion=<Criterion>(index=Silhouette()), scoring=[Silhouette()],
).fit(X)

print('n_clusters_', s.n_clusters_, '(expect 2 on iris by silhouette)')
print('conclusive_', s.conclusive_)
print('curve_     ', list(s.curve_))
print('candidates ', list(s.results_))
print('labels_    ', s.labels_[:8])
"
```

Then the figure, which is half the deliverable:

```bash
python -c "
import matplotlib; matplotlib.use('Agg')
from xxcluster.viz.diagnostics import plot_selection_curve
# curve_ is a sequence; plot_selection_curve wants candidate -> score
plot_selection_curve(dict(zip(range(2, 11), s.curve_)),
                     selected=s.n_clusters_, criterion='<name>')
print('figure OK')
"
```

**Note:** `curve_` is documented as `dict` on `BaseNClustersSelector` and as a
`Sequence[float]` on `BaseRelativeCriterion.curve`. Decide which when you
implement this, make the two agree, and fix whichever docstring is wrong — this
is exactly the kind of drift a first implementer is expected to catch.

---

## Step 4 — Sect. 4.3

No template. Write the procedure into
`documentation/sections/methodology.tex`: the candidate range, the criterion,
the conclusiveness rule, and the fact that the same procedure is applied
identically to every method so none is advantaged by a more favourable choice.

The candidate range is **a judgement about the domain** — how many operating
regimes could be acted on — as much as about the data, and belongs in the
reported setup.

---

## Until this lands

Notebooks do the sweep by hand. It is the same computation, and the curve is
what `plot_selection_curve` consumes either way:

```python
curve = {k: Silhouette().score(X, KMeans(n_clusters=k, random_state=RANDOM_STATE)
                                        .fit(X).labels_)
         for k in protocol.n_clusters_candidates}
selected = max(curve, key=curve.get)      # the "max" criterion, inlined
```

State in the notebook's §10 that selection was done by hand and stability was
not assessed. That is a caveat, not a gap to hide.

---

## Common mistakes

| Symptom | Cause |
|---|---|
| `_fit did not set: conclusive_` | criterion's `is_conclusive` still raises |
| Every sweep selects the largest candidate | criterion applies `>` instead of `index.is_better`, on a minimised index |
| The estimator handed in comes back fitted | missing `clone` |
| Only the winner is in `results_` | the record that makes the selection auditable is gone |
| A density method swept for `n_clusters` | wrong selector — sweep its own parameters |
