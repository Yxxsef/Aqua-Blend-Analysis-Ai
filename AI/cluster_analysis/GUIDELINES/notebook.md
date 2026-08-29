# Writing the notebook

> **Status: verified.** `notebooks/Minh (s224236373)/kmeans_silhouette.ipynb` runs top to bottom on a restarted kernel. The path fix and the export block below come from that run.

**Read [00-the-contract.md](00-the-contract.md) first.** Policy: [CONTRIBUTING Part 3](../CONTRIBUTING.md#part-3-the-notebooks), covering §3.1 what a notebook is for, §3.2 one per contribution, §3.3 the structure, §3.6 what to commit.

**Start from:** `notebooks/00-template.ipynb` **Copy to:** `notebooks/<Name (SID)>/<nn>-<name>.ipynb`

---

## One notebook, one contribution

A notebook evidences **one** implementation against **its own write-up**: one clustering method, or one reduction technique, or one measure. Not a survey.

The cross-notebook comparison is Sect. 8, and it happens **once, after all the sections and notebooks are final**. That is `ARCHITECTURE.md §5`, and it is not what a notebook does.

**Rename the file immediately after copying.** Name it for the code module and document subsection it evidences, e.g. `01-kmeans.ipynb`. Leaving a second file called `00-template.ipynb` in your folder guarantees the two drift.

### The awkward case: an index has nothing to score

A validity index needs a method to score, so strictly a method and an index are two contributions and two notebooks. In practice, write the **method's** notebook and have it double as the index check by including the published-benchmark assertion. **Say that explicitly in §2 Scope** rather than leaving it implied.

---

## Section 1: Setup, and the path line that catches everyone

```python
from pathlib import Path
import sys

ROOT = next(p for p in Path.cwd().parents if (p / "xxcluster").is_dir())
sys.path.insert(0, str(ROOT))
```

The template ships `Path.cwd().parent`, which assumes the notebook sits directly in `notebooks/`. **Yours does not; it is in a personal folder, one level deeper**, so `.parent` lands on `notebooks/` and the import fails with `ModuleNotFoundError`. The search form above works at any depth.

Keep `ROOT`; §9 uses it for the export paths.

Then seed and environment, before anything else:

```python
RANDOM_STATE = 42
env = Environment.capture()
env
```

`Environment.capture()` records Python, the package versions, the platform and the git revision, suffixed `-dirty` if the tree has uncommitted changes. That record is what App. A rests on, and it is why **one seed, set once, used everywhere**.

---

## Section 4: The protocol is given, not tuned

```python
protocol = Protocol(
    indices=["silhouette"],
    n_restarts=10,
    random_state=RANDOM_STATE,
    preprocessing=None,
    n_clusters_candidates=range(2, 11),
    environment=env,
)
```

**Fill every field.** The template writes `...` in three of them, and a `Protocol` still carrying one now refuses to construct:

```
ValueError: preprocessing still holds the notebook template's `...`.
```

`preprocessing=None` is a legitimate answer: it means no shared pipeline. But it must be an answer. And if you do set a pipeline, remember that §5 and §6 below fit on raw `X`; a scaler in the protocol alone makes §7 incomparable to them.

**Do not tune the protocol here.** A method needing a deviation records it against itself, in its own *Application* paragraph.

---

## Section 5: Contract check

Replace the template's assertions with the real conformance suite once `fit` works:

```python
from sklearn.utils.estimator_checks import check_estimator
check_estimator(Method(n_clusters=3))

print(method._capabilities)      # must match what the write-up claims
```

That `print` is not decoration. A class with no `_capabilities` prints the default (native, non-inductive, requires no |C|), and if your write-up says otherwise, Sect. 8.2 will carry the lie. Read the line; do not just run it.

---

## Section 7: Results

```python
run = ComparisonRun(methods=[method], protocol=protocol)
results = run.run(X)
```

Three behaviours to know before you read the output:

- **Your seeds get overwritten.** `run` applies `protocol.seed_for(...)` to any `random_state` and `protocol.n_restarts` to any `n_init`, including inside a pipeline. A `KMeans(random_state=0)` you pass in **will be reseeded**, because Sect. 4.1 fixes seeds for every method at once.
- **An index that cannot read a result scores NaN, not an error.** Silhouette on a partition containing noise, or an external index with no `y`. It reaches the table as `--`, and the run keeps its other scores.
- **A method that fails is recorded in `RunResult.error`, not dropped.** A comparison missing its hardest case silently is worse than one that reports the failure.

**Report every index in `protocol.indices`, including the unfavourable ones.** Reporting only the flattering subset is the failure mode this structure exists to prevent.

---

## Section 6: Selection, while the machinery is unwritten

`BaseNClustersSelector._fit` and `StabilityAnalysis._fit` both raise `NotImplementedError`, and there is no concrete `BaseRelativeCriterion`. Do the sweep by hand; it is the same computation the selector will do, and the curve is what `plot_selection_curve` consumes either way:

```python
curve = {k: Silhouette().score(X, KMeans(n_clusters=k, random_state=RANDOM_STATE)
                                        .fit(X).labels_)
         for k in protocol.n_clusters_candidates}
selected = max(curve, key=curve.get)          # the "max" criterion, inlined

plot_selection_curve(curve, selected=selected, criterion="max silhouette")
```

Then **state in §10 that selection was inlined and stability was not assessed**, and why. That is a caveat, not a gap to hide; [CONTRIBUTING §3.4](../CONTRIBUTING.md#34-from-notebook-to-document) is explicit that unassessed results belong in *Limitations* and Sect. 4.5.

See [selection-selector.md](selection-selector.md) if you intend to unblock it.

---

## The check that makes this evidence rather than assertion

```python
assert abs(Silhouette().score(X, labels) - 0.5528) < 1e-3
```

Where a published value exists for your method or index on a benchmark dataset, **assert it**. That is what turns *"my implementation ran"* into *"my implementation agrees with the literature"*, and it is what `BenchmarkLoader` exists for. An assertion that fires is the notebook doing its job.

---

## Section 9: Export

Numbers reach the document this way and no other. A retyped number is the most likely place for a result to be corrupted.

```python
TABLES  = ROOT / "documentation" / "tables"
FIGURES = ROOT / "documentation" / "figures"

table = ComparisonTable(results)
table.to_csv(TABLES / "kmeans-results.csv")
table.to_latex(TABLES / "kmeans-results.tex", label="tab:kmeans:results")

plt.savefig(FIGURES / "kmeans-selection.png", dpi=200, bbox_inches="tight")
```

**Use `ROOT`, not `../documentation/`.** From a personal folder the relative path is `../../`, and the template's `../` silently resolves to `notebooks/documentation/`, which does not exist, so the export fails at the last cell after everything else worked.

`to_latex` emits the `tabularx` body only, for `\input` into a section file, so regenerating results never touches the surrounding prose. Pick the filenames now; the document references them verbatim.

---

## Section 10: Findings and caveats

The bridge to the write-up. Each row names an output above and the paragraph it supports.

**Name the negative result in advance, in §2 Scope.** Deciding after you have seen the numbers what would have counted as a failure is how a notebook stops being evidence.

Caveats that belong here, from `CONTRIBUTING §3.4`: inconclusive selections, unstable partitions, failed runs, deviations from the protocol. Also, for an internal index, the `assumes_shape` caveat: an index that rewards compact isotropic clusters does not rank a density-based method neutrally.

---

## Before you commit

```
Kernel → Restart & Run All
```

- [ ] Runs top to bottom on a **restarted** kernel
- [ ] `RANDOM_STATE` set once and used everywhere; no unseeded randomness
- [ ] Environment captured in §1
- [ ] Protocol taken from the shared setup; deviations stated
- [ ] `check_estimator` passes, exclusions recorded
- [ ] Every index in `protocol.indices` reported, favourable or not
- [ ] Export paths resolve from your personal folder
- [ ] §10 completed, caveats included
- [ ] **Outputs left in the committed file**: they are the evidence

That last one is the opposite of the usual convention, and it is deliberate: per [CONTRIBUTING §3.6](../CONTRIBUTING.md#36-what-to-commit), a notebook with its outputs stripped is not evidence of anything.

Use the `xxcluster` Jupyter kernel; it points at the project venv, so `Environment.capture()` records one stack rather than a different one per contributor.

---

## Common mistakes

| Symptom | Cause |
|---|---|
| `ModuleNotFoundError: xxcluster` | `Path.cwd().parent` from a personal folder; use the search form |
| `ValueError: ... still holds the notebook template's ...` | an unfilled `...` in the `Protocol` |
| `Cannot save file into a non-existent directory` | `../documentation/` instead of `ROOT / "documentation"` |
| Scores differ from the ones you saw in §6 | §7 reseeded the method from the protocol, which is expected |
| The notebook covers two methods | one notebook, one contribution |
| Reviewer cannot reproduce a figure | drawn before `RANDOM_STATE` was set, or in a cell that was re-run out of order |
