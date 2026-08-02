# Adding an external validity index

> **Status: derived from the contract, skeleton executed.** No external index
> exists yet, but the `AdjustedRandIndex` skeleton below was run: it scores
> `1.0` for a relabelled identical partition and `-0.364` for an unrelated
> one. It has **not** been used inside a `ComparisonRun` or a stability
> analysis. **You are the first — correct this file as you go.**

**Read [00-the-contract.md](00-the-contract.md) and
[validity-index-internal.md](validity-index-internal.md) first** — the second
covers the mechanics of `score`, `is_better`, registration and the
published-value check, and all of it applies here. This page covers only what
is different.

**File:** `xxcluster/measures/validation/external.py` — append to it.

An external index **compares a partition against a reference labelling**. The
Rand index and its adjusted form, mutual information, the set-matching
measures.

---

## Why this group exists here, given there is no ground truth

The operational data has no reference labelling, so the obvious use does not
apply. There are two others, and both matter:

1. **Validating an implementation.** On a benchmark dataset with known labels,
   an external index checks that your method behaves as published. That is the
   check a *native* implementation needs before its results are trusted at all.

2. **Measuring agreement between two clusterings.** Supply one partition as the
   "reference" and the same index measures how much two runs agree. This is
   exactly how [selection-perturbation.md](selection-perturbation.md) scores
   resampled runs against each other — the measure is identical, only the
   interpretation of the second argument changes.

Use 2 is why `selection/stability.py` is blocked on this file, and why the two
declarations below carry real weight.

---

## The two declarations that are yours

```python
class BaseExternalIndex(BaseValidityIndex, ABC):
    requires_labels_true = True     # inherited — do not restate
    requires_X = False              # inherited

    chance_corrected: bool = False
    symmetric: bool = True
```

### `chance_corrected`

Whether the index is adjusted for agreement expected by chance.

**Material when the number of clusters differs between the two labellings**:
uncorrected indices rise with the number of clusters, so comparing partitions
of different sizes needs a corrected one. The plain Rand index will tell you
that a 20-cluster partition agrees beautifully with a 3-cluster reference.

`chance_corrected` is paragraph 3 (*Properties*) of the write-up, per
[CONTRIBUTING §2.5](../CONTRIBUTING.md#25-adding-a-measure).

### `symmetric`

Whether swapping the two labellings leaves the value unchanged.

**Required for the stability use.** In a stability analysis neither argument is
privileged — there is no "true" partition, only two runs. An asymmetric index
used there gives a different answer depending on argument order, which makes
the reported mean agreement meaningless. `StabilityAnalysis` is entitled to
check `symmetric` before accepting your index; declare it accurately.

Adjusted Rand is symmetric. Homogeneity and completeness are **not** — they are
a deliberately asymmetric pair, and neither belongs in a stability analysis.

---

## `requires_X = False` changes how `ComparisonRun` treats you

Inherited, but know what it buys: your index reads the contingency table alone,
never the data. So `score(X=None, labels=..., labels_true=...)` is a legitimate
call, and the harness may make it.

Correspondingly, `requires_labels_true = True` means `ComparisonRun` will
**score your index as NaN when no `y` was supplied to `run`**, rather than
calling you with `labels_true=None`. You do not need to guard for that case,
but do not rely on being called either.

---

## Skeleton

```python
@register("adjusted_rand")
class AdjustedRandIndex(BaseExternalIndex):
    """<one paragraph: what it measures, citing ref_<n> for Hubert & Arabie>

    Chance-corrected, so it is the one to reach for when the two
    labellings have different numbers of clusters -- which is the normal
    case in a stability analysis, where |C| is not pinned across repeats.

    Applied per Sect. 4.2, and by `selection.stability`.
    """

    name = "adjusted_rand"
    higher_is_better = True
    range_ = (-0.5, 1.0)          # ARI can go slightly negative
    chance_corrected = True
    symmetric = True
    handles_noise = False

    def score(self, X=None, labels=None, *, labels_true=None,
              metric="euclidean", **kwargs) -> float:
        labels = check_labels(labels, allow_noise=self.handles_noise)
        labels_true = check_labels(labels_true, allow_noise=self.handles_noise)
        if labels.shape != labels_true.shape:
            raise ValueError(
                f"labels has {labels.shape[0]} entries but labels_true has "
                f"{labels_true.shape[0]}; the two must describe the same "
                f"observations."
            )
        from sklearn.metrics import adjusted_rand_score
        return float(adjusted_rand_score(labels_true, labels))
```

**`handles_noise` needs a decision here, not a default.** Two runs of a
density-based method will both contain `-1`, and the question is whether "both
called this point noise" counts as agreement. Treating `-1` as an ordinary
cluster label says yes, which is usually wrong — noise is not a cluster, and
two runs agreeing on what they could not assign is not evidence of a stable
partition. Declaring `handles_noise = False` and refusing is the defensible
default; if you declare `True`, say in the write-up what `-1` means to your
index.

**The length check matters more here than elsewhere.** In the stability use the
two label vectors come from different fits, potentially on different resamples.
Comparing them on their common observations is the caller's job — see
[selection-perturbation.md](selection-perturbation.md) — but a mismatched pair
reaching you is a real bug worth naming.

---

## Verify

```bash
python -c "
import numpy as np
from xxcluster.measures.validation.external import <Class>

a = np.array([0,0,1,1,2,2])
b = np.array([1,1,2,2,0,0])          # same partition, relabelled
c = np.array([0,1,0,1,0,1])          # unrelated

idx = <Class>()
print('identical (relabelled)', idx.score(labels=a, labels_true=b))   # -> 1.0
print('unrelated             ', idx.score(labels=a, labels_true=c))   # -> ~0
print('symmetric?            ', idx.score(labels=a, labels_true=c)
                             == idx.score(labels=c, labels_true=a))
print('declared symmetric    ', idx.symmetric)
"
```

Three properties to check, in this order:

1. **Label invariance.** A partition compared with a relabelling of itself must
   score the maximum. If it does not, you are comparing label *values* rather
   than the partition they induce — the single most common bug in this group.
2. **Symmetry matches the declaration.** Test it; do not assume it.
3. **Chance correction.** Two random partitions should score near zero if you
   declared `chance_corrected = True`, and clearly above zero if you did not.

---

## Write-up and notebook

`template/measure_template.tex` into
`documentation/sections/clustering_methods/measures/<nn>-<name>.tex`. Labels
`sec:measure:<name>:*`.

For the notebook: an external index needs a dataset with known labels, so use
`BenchmarkLoader("iris")` and report the index for a method whose published
agreement you can cite. State in §2 Scope that this notebook validates the
*index*, and that the method is the instrument rather than the subject.

---

## Common mistakes

| Symptom | Cause |
|---|---|
| A relabelled identical partition does not score 1.0 | comparing label values, not the partition |
| Stability reports implausibly high agreement | uncorrected index with varying `\|C\|` — declare and use a chance-corrected one |
| `StabilityAnalysis` rejects your index | `symmetric = False`; that is correct behaviour, pick another index |
| Noise points inflate agreement | `handles_noise` left `True` without deciding what `-1` means |
| Index scores NaN in every `ComparisonRun` row | no `y` was passed to `run`; expected, not a bug |
