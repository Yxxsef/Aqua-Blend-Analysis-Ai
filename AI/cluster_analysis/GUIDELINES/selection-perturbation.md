# Adding a perturbation (and the stability analysis)

> **Status: derived from the contract, partly executed.** The `Jitter`
> perturbation skeleton below was run and yields correct
> `(X_perturbed, index)` pairs. **`StabilityAnalysis._fit` still raises
> `NotImplementedError`**, so the `_fit` skeleton in Step 2 has not run and
> the expected output in Step 3 is a prediction, not a recorded result. **You
> are the first — correct this file as you go.**

**Read [00-the-contract.md](00-the-contract.md) first.** Documentation
counterpart: Sect. 4.3 and Sect. 2.1.

**File:** `xxcluster/selection/stability.py` — `BasePerturbation` is defined in
that file, so concrete perturbations go directly below it.

---

## What stability answers

Whether a partition is a property of **the data** or of **one particular run**.
A method is refitted over perturbations — resampled rows, added noise,
different seeds — and the resulting partitions are compared with each other.

This is the closest available substitute for held-out validation, and it
addresses two of the weaknesses named in Sect. 2.1 directly:

- **Local optima** — the same data and different seeds giving different
  partitions.
- **Subjective hyperparameters** — a result that only holds at one setting is
  not a robust one.

> A high internal index with low stability means the method found a partition
> it can score well, not one the data supports.

That sentence is the finding this machinery exists to produce, and it belongs
in Sect. 4.5.

---

## Step 1 — The perturbation defines what "stable" means

Which is why it is explicit and named. **Stability under bootstrap resampling
and stability under added measurement noise are different claims**, and for
sensor data the second is the one that matters.

```python
class BasePerturbation(ABC):
    name: str

    @abstractmethod
    def split(self, X, *, n_repeats: int = 10, random_state=None) -> Iterator[Any]:
        """Yield perturbed datasets, each with the index of retained rows."""
```

### `split` yields a pair, and the index is not optional

Yield `(X_perturbed, retained_index)`. The index is what lets two partitions be
compared **on their common observations**, which is the only place two
resampled runs can be compared at all — run A labelled rows {0,2,5,…} and run B
labelled {1,2,5,…}, and only the intersection is comparable.

Forget the index and the whole analysis is unsound, not merely inconvenient.

### The four perturbations the module names

```python
class Bootstrap(BasePerturbation):
    """Resample m rows with replacement."""
    name = "bootstrap"

    def split(self, X, *, n_repeats=10, random_state=None):
        rng = check_random_state(random_state)
        m = np.asarray(X).shape[0]
        for _ in range(n_repeats):
            idx = rng.randint(0, m, size=m)
            yield np.asarray(X)[idx], idx


class Subsample(BasePerturbation):
    """Draw a fraction of the rows without replacement."""
    name = "subsample"

    def __init__(self, *, fraction: float = 0.8) -> None:
        self.fraction = fraction
    ...


class Jitter(BasePerturbation):
    """Add small Gaussian noise — the sensor-data perturbation."""
    name = "jitter"

    def __init__(self, *, scale: float = 0.01) -> None:
        self.scale = scale       # in units of each feature's std

    def split(self, X, *, n_repeats=10, random_state=None):
        rng = check_random_state(random_state)
        X = np.asarray(X, dtype=float)
        sigma = X.std(axis=0) * self.scale
        index = np.arange(X.shape[0])          # every row retained
        for _ in range(n_repeats):
            yield X + rng.normal(0.0, sigma, size=X.shape), index


class LeaveOut(BasePerturbation):
    """Drop a small number of observations."""
    name = "leave_out"
    ...
```

### The rule that makes this meaningful

> The dataset should be **slightly** modified, otherwise it becomes a different
> dataset, and has no practical meaning.

A `Jitter` scaled to whole standard deviations, or a `Subsample` at 0.2, is not
measuring stability — it is measuring whether the method finds the same
structure in different data. Keep the parameter defaults conservative and state
them in Sect. 4.1.

**Bootstrap has a subtlety worth knowing:** sampling with replacement produces
duplicate rows, and a duplicate is at distance zero from itself. Density-based
methods notice — a point duplicated three times may become a core point that
was not one before. If your method is density-based, prefer `Subsample`, and
say why.

---

## Step 2 — `StabilityAnalysis._fit`

```python
def _fit(self, X, y=None, **fit_params) -> None:
    """Refit over perturbations and score the resulting agreement."""
    if self.scoring is None:
        raise ValueError(
            "StabilityAnalysis needs a symmetric external index to compare "
            "partitions; pass scoring=AdjustedRandIndex(). See "
            "measures/validation/external.py."
        )
    perturbation = self.perturbation or Bootstrap()
    rng = check_random_state(self.random_state)

    runs = []            # (labels, retained_index) per repeat
    for X_p, index in perturbation.split(
        X, n_repeats=self.n_repeats, random_state=rng
    ):
        model = clone(self.estimator).fit(X_p)
        runs.append((np.asarray(model.labels_), np.asarray(index)))

    agreements = []
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            agreements.append(self._agreement(runs[i], runs[j]))

    self.agreements_ = np.asarray(agreements, dtype=float)
    self.stability_ = float(np.mean(self.agreements_))
    self.stability_std_ = float(np.std(self.agreements_))
```

**Compare on the common observations.** `_agreement` takes two
`(labels, index)` pairs, intersects the indices, and scores the two label
vectors restricted to that intersection. This is the step the `index` exists
for, and skipping it compares row *positions* in two different resamples —
which produces a number that looks fine and means nothing.

**Both `stability_` and `stability_std_` are required.** Even a high mean with
a high spread is not stability, which is why the class declares both.

**`consensus_labels_` is optional** — "where the analysis produces one". It is
declared in the class annotations but `StabilityAnalysis` sets no
`_required_fitted`, so leaving it unset is legal. Where you do produce one, it
is often a better final answer than any single run.

### The `scoring` decision

The index must be **symmetric** — in a stability analysis neither argument is
privileged. See [validity-index-external.md](validity-index-external.md).

Until `AdjustedRandIndex` exists, a caller can pass
`sklearn.metrics.adjusted_rand_score` directly: `BaseValidityIndex.__call__`
exists precisely so an index and a bare function are interchangeable. But
**do not default to it** — a borrowed default silently becomes the permanent
answer, and `external.py`'s docstring says stability scores through that group.
Require `scoring` and name ARI in the error, as above.

---

## Step 3 — Verify

```bash
python -c "
import numpy as np
from sklearn.datasets import load_iris
from sklearn.metrics import adjusted_rand_score
from xxcluster.cluster.partitional.sse_based.kmeans import KMeans
from xxcluster.selection.stability import StabilityAnalysis, <Perturbation>

X = load_iris().data

for k in (2, 3, 10):
    s = StabilityAnalysis(
        KMeans(n_clusters=k), perturbation=<Perturbation>(),
        n_repeats=10, scoring=adjusted_rand_score, random_state=42,
    ).fit(X)
    print(f'k={k:2d}  stability {s.stability_:.3f} +/- {s.stability_std_:.3f}')
"
```

Expect stability to **fall as |C| rises** on iris — k=10 should be visibly less
reproducible than k=2. If it does not, you are almost certainly comparing row
positions rather than common observations.

Two more checks:

```bash
# reproducible: same seed, same numbers
# a deterministic method on an unperturbed dataset scores 1.0
```

Then the figure:

```bash
python -c "
import matplotlib; matplotlib.use('Agg')
from xxcluster.viz.diagnostics import plot_stability
plot_stability(s); print('figure OK')
"
```

---

## Step 4 — Sect. 4.3 and Sect. 4.5

No template. Record in the methodology: which perturbation, its parameter, how
many repeats, and which index. All four change what "stable" means, so all four
belong in the reported setup.

Stability is also **a selection criterion in its own right** — preferring the
|C| whose partition is most reproducible — so it composes with
[selection-selector.md](selection-selector.md) rather than duplicating it. A
|C| chosen by silhouette and rejected by stability is a finding, and Sect. 4.5
is where it goes.

---

## Common mistakes

| Symptom | Cause |
|---|---|
| Stability is high for every |C| | comparing row positions instead of common observations |
| Stability barely moves with the perturbation parameter | perturbation too small to perturb, or `Jitter` scale applied in raw units rather than per-feature std |
| Results change between runs with the same seed | `random_state` not threaded into `split` |
| A density method looks unstable under `Bootstrap` | duplicate rows changing core-point status; use `Subsample` |
| Stability reported without spread | a high mean with a high spread is not stability |
