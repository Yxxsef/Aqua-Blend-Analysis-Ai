# Adding a task (extending sideways)

> **Status: derived from the contract, skeleton executed.** No task exists yet
> and `components()` raises `NotImplementedError` on the base, but a minimal
> `BaseTask` subclass overriding `components` and `run` was constructed and
> run successfully. The composed `run` body in the skeleton below is
> illustrative — it has not been executed against real components. **You are
> the first — correct this file as you go.**

**Read [00-the-contract.md](00-the-contract.md) first.** Policy:
[CONTRIBUTING §2.6](../CONTRIBUTING.md#26-adding-a-task-extending-sideways).
A task needs a **new template kind** — see
[§1.4](../CONTRIBUTING.md#14-adding-a-new-kind-of-template).

**File:** `xxcluster/tasks/<task>/` — a subpackage, not a module.

A task is an **end-to-end analysis**: time-series clustering, anomaly
detection, scenario generation, demand forecasting.

---

## The one rule that matters

> **A task composes components; it does not implement algorithms.**

Anything reusable belongs in the subpackage for its kind, where the registry
and the comparison can reach it:

| If your task needs | Put it in | Guide |
|---|---|---|
| a series dissimilarity | `measures/dissimilarity/` | [dissimilarity-measure.md](dissimilarity-measure.md) |
| a clustering method | `cluster/<family>/<subfamily>/` | [clustering-method.md](clustering-method.md) |
| a detector | on `BaseOutlierDetector` | — |
| a generator | on `BaseGenerator` | — |
| an index | `measures/validation/` | [validity-index-internal.md](validity-index-internal.md) |

**A component defined inside a task is invisible to the registry and to the
comparison.** It cannot appear in Sect. 8, cannot be shortlisted by
`REGISTRY.applicable`, and cannot be reused by the next task. If you find
yourself writing a `_fit` inside `tasks/`, stop — that code belongs elsewhere
and your task should be importing it.

---

## A task is not a `BaseComponent`

```python
class BaseTask(ABC):
    _kind: ClassVar[ComponentKind] = ComponentKind.TASK
    name: str

    def __init__(self, dataset=None, *, protocol=None): ...

    @abstractmethod
    def run(self, **kwargs) -> TaskResult: ...

    def components(self) -> Mapping[str, Any]: ...
```

A task is not fitted and has no `transform`. Forcing it into the estimator
contract would only obscure that it **runs once and returns a report**. So:

- `run`, not `fit`. No trailing-underscore state, no `_required_fitted`.
- No `_capabilities` — a task makes no claims about data it accepts.
- `_kind` is `TASK`, inherited. `@register("<name>")` still works and is still
  how a task is named in a configuration.
- **Tasks do not read files.** `dataset` arrives already loaded.

---

## `TaskResult` — what you must return

```python
@dataclass(frozen=True)
class TaskResult:
    task: str
    runs: Sequence[RunResult] = ()
    figures: Mapping[str, Any] = field(default_factory=dict)
    tables: Mapping[str, Any] = field(default_factory=dict)
    caveats: Sequence[str] = ()
```

The four fields are held together because **a task's output is an argument
rather than a number**: the tables, the figures that qualify them, and the
record of what produced both.

**`caveats` is not optional padding.** An inconclusive selection, an unstable
partition, a failed run — reported, not filtered. This is the field that keeps
a task honest, and it feeds Sect. 4.5 directly. A task that returns an empty
`caveats` on a real dataset is usually a task that is not looking.

---

## Skeleton

```
xxcluster/tasks/timeseries/
    __init__.py
    task.py          # the BaseTask subclass
```

```python
@register("timeseries_clustering")
class TimeSeriesClustering(BaseTask):
    """Cluster daily consumption profiles into operating regimes.

    Composes: a DTW dissimilarity, a precomputed-capable method, and the
    shared protocol. Implements none of them.
    """

    name = "timeseries_clustering"

    def __init__(self, dataset=None, *, protocol=None,
                 measure=None, method=None) -> None:
        super().__init__(dataset, protocol=protocol)
        self.measure = measure
        self.method = method

    def components(self):
        """The components this task uses, by role."""
        return {"measure": self.measure, "method": self.method}

    def run(self, **kwargs) -> TaskResult:
        X = self.dataset.cluster_matrix()
        D = self.measure.fit(X).pairwise(X)

        runs = ComparisonRun([self.method], protocol=self.protocol).run(D)

        caveats = [r.error for r in runs if r.failed]
        if not caveats:
            caveats = self._check_findings(runs)

        return TaskResult(
            task=self.name,
            runs=runs,
            tables={"results": ComparisonTable(runs).quantitative()},
            figures={"profiles": plot_cluster_profiles(...)},
            caveats=caveats,
        )
```

**Implement `components()`.** It raises on the base, and it exists so a task's
composition is inspectable *before* it is run, and so the reported result can
name what produced it. A task whose composition is only visible by reading
`run` is not auditable.

**Take the protocol, do not build one.** Two tasks over the same data are
comparable only if they share it.

---

## Verify

```bash
python -c "
from xxcluster.io.loaders import BenchmarkLoader
from xxcluster.evaluation.protocol import Protocol
from xxcluster.tasks.<task>.task import <Class>

t = <Class>(
    dataset=BenchmarkLoader('iris').load(),
    protocol=Protocol(indices=['silhouette'], random_state=42),
    <components>,
)
print('composition', t.components())

r = t.run()
print('task    ', r.task)
print('runs    ', [x.method for x in r.runs])
print('tables  ', list(r.tables))
print('figures ', list(r.figures))
print('caveats ', r.caveats)
"
```

Check `components()` before `run()` — if it raises, the task is not inspectable
and the contract is unmet.

---

## The document side

A task needs its own section, and therefore **a new template kind**. Follow
[CONTRIBUTING §1.4](../CONTRIBUTING.md#14-adding-a-new-kind-of-template):
add `template/<kind>_template.tex`, keep the `.docx` in step via
`template/build_docx.py`, and say in the pull request why an existing kind did
not fit.

**Scenario generation additionally feeds the MILP team — agree the output
format with them before building it.** That is a cross-team dependency, not a
detail to settle later.

---

## Common mistakes

| Symptom | Cause |
|---|---|
| A method the task uses is missing from Sect. 8 | it was defined inside `tasks/`; move it to its kind's subpackage |
| `components()` raises | not implemented; the base's default |
| Two tasks' results are not comparable | each built its own `Protocol` instead of taking one |
| The task reads a CSV | tasks do not read files; the dataset arrives loaded |
| `caveats` always empty | failures filtered rather than reported |
| No template kind for the section | see CONTRIBUTING §1.4 before writing the `.tex` |
