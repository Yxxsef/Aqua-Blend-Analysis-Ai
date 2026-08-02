# The contract — read this first

> **Status: verified.** Every rule below is enforced by code in `core/` and
> covered by `tests/`. The failure messages quoted are the real ones.

Six rules. They apply to everything you add, and they are all mechanically
checked — you will meet them as error messages if you skip this page.

Reference: [`xxcluster/ARCHITECTURE.md`](../xxcluster/ARCHITECTURE.md) for why
the contract is shaped this way, [CONTRIBUTING §2.7](../CONTRIBUTING.md#27-the-contract)
for the rule as policy.

---

## 1. Where everything comes from

One import site per thing. A second path to the same object is how two
registries, or two `ComponentKind`s, come to exist.

| Name | Import from |
|---|---|
| `register`, `REGISTRY` | `xxcluster.core.registry` |
| `ComponentKind`, `Family`, `SubFamily`, `Backend`, `Assignment`, `Scaling`, `PrecomputedKind`, `NOISE_LABEL` | `xxcluster.core.types` |
| `Capabilities` | `xxcluster.core.tags` |
| `BackendAdapter`, `AdaptedClusterer`, `AdaptedDimReducer` | `xxcluster.core.adapters` |
| `InductiveMixin`, `SoftAssignmentMixin`, `HierarchyMixin`, `NoiseAwareMixin`, `ProbabilisticMixin`, `PrecomputedMixin` | `xxcluster.core.mixins` |
| `check_labels`, `check_n_clusters`, `check_random_state`, `ensure_fitted`, `finite_policy` | `xxcluster.core.validation` |
| `ContractViolationError`, `BackendUnavailableError`, `RegistryError`, `NotFittedError` | `xxcluster.core.exceptions` |

Use **relative** imports at your module's depth, as every existing module does:

```python
# xxcluster/cluster/partitional/sse_based/kmeans.py  — four levels down
from ....core.adapters import AdaptedClusterer
from ....core.registry import register
from ....core.tags import Capabilities
from ....core.types import Assignment, Backend, Family, Scaling, SubFamily
from .base import BasePrototypeClusterer

# xxcluster/measures/validation/internal.py  — three levels down
from ...core.registry import register
from ...core.validation import check_labels
from .base import BaseValidityIndex
```

---

## 2. The template method — override `_fit`, never `fit`

`BaseComponent.fit` is concrete and does five things in a fixed order:

```python
def fit(self, X, y=None, **fit_params):
    self._validate_params()        # 1. parameter constraints
    self._check_capabilities()     # 2. declaration vs interface
    X = self._validate_input(X, reset=True)   # 3. shape, dtype, finiteness
    self._fit(X, y, **fit_params)  # 4. YOURS
    self._check_fitted()           # 5. did _fit set what it declared?
    return self
```

You write step 4 and nothing else. That fixed order is what makes Sect. 8 a
comparison rather than a collection of differently-guarded runs.

**Parameters go in `__init__` only, stored unmodified, never validated there.**

```python
def __init__(self, n_clusters=2, *, tol=1e-4, random_state=None):
    self.n_clusters = n_clusters      # store under its own name
    self.random_state = random_state  # do NOT call check_random_state here
```

`clone` and `check_estimator` both depend on parameters round-tripping through
`get_params`/`set_params` untouched. Validate in `_fit`, or declare
`_parameter_constraints` and let scikit-learn's machinery do it.

**Fitted state carries a trailing underscore and does not exist before `fit`.**

---

## 3. Declare what `_fit` must set

```python
class BasePartitionalClusterer(BaseClusterer, ABC):
    _required_fitted = ("n_iter_", "converged_", "criterion_")
```

`_check_fitted` runs after every fit and names anything missing:

```
ContractViolationError: KMeans._fit did not set: converged_.
Every attribute a class declares in `_required_fitted` must exist once
fitting succeeds.
```

Declarations are **collected across the MRO**, so you list only what you add to
your parent's. A density-based method need not restate `labels_` to also
require `n_noise_`.

This is not documentation — an attribute named only in a docstring is neither
checked here nor copied by the adapter (rule 5).

---

## 4. Declare capabilities, and back them with an interface

```python
_capabilities = Capabilities(
    family=Family.PARTITIONAL,
    subfamily=SubFamily.SSE_BASED,
    backend=Backend.SKLEARN,
    is_inductive=True,
    requires_n_clusters=True,
    ...
)
```

`_check_capabilities` runs on every fit and checks **one direction**: a
declaration must be backed by the interface it promises. Declaring more than
you have fails; having more than you declare does not.

| Declaring | Requires |
|---|---|
| `is_inductive=True` | `predict` **or** `transform` |
| `produces_hierarchy=True` | `cut` |
| `handles_noise=True` | `noise_mask` |
| `supports_precomputed=True` | `_check_precomputed` |
| `assignment` other than `CRISP` | `predict_proba` |

```
ContractViolationError: Ward declares produces_hierarchy but has no `cut`.
Either mix in the capability or correct the declaration — the comparison
table of Sect. 8.2 is generated from it.
```

**A `Capabilities` field left at its default is a claim, not a blank.**
`_capabilities` defaults to `Capabilities()`, which claims native, crisp,
non-inductive, requires no `|C|`, handles nothing, medium scale. If you do not
declare, Sect. 8.2 prints that as though you meant it. Fill every field you can
justify from your write-up; see the pairing tables in
[CONTRIBUTING §2.3.1](../CONTRIBUTING.md#231-what-must-agree) and
[§2.5](../CONTRIBUTING.md#25-adding-a-measure).

---

## 5. Adapt a backend, or write it natively

Adapting is the default. [CONTRIBUTING §2.3](../CONTRIBUTING.md#23-adding-a-clustering-method)
step 4 states when to reimplement instead: no good implementation exists, or
following the formulation *is* the point.

An adapter declares four things and inherits `_fit`:

| Attribute | Meaning |
|---|---|
| `_backend_import` | Dotted path, imported at **fit** time so a missing optional dependency does not break `import xxcluster` |
| `_param_map` | our name → backend name. Identity by default; list only differences. **Mapping to `None` drops the parameter.** |
| `_attr_map` | our fitted attribute → backend attribute |
| `_fixed_params` | backend parameters we pin and do not expose |

`_collect_fitted` copies **only what `_required_fitted` declares**, through
`_attr_map`. Mirroring everything would put the backend's vocabulary into ours,
which is the coupling the adapter exists to prevent. Anything else stays
reachable on `backend_`.

Attributes the backend does not report go in `_derive_missing`, calling
`super()` first:

```python
def _derive_missing(self) -> None:
    super()._derive_missing()      # derives n_clusters_, n_noise_, n_components_
    self.converged_ = bool(self.n_iter_ < self.max_iter)
```

**One backend attribute may feed two contract names.** `_attr_map =
{"criterion_": "inertia_"}` redirects `criterion_` to the backend's SSE while
`inertia_` resolves to itself, because lookup defaults to the same name.

### The native-hook rule, if you are writing a base class

A hook that exists only for a native fitting loop — `_fit_once`,
`_update_centers`, `_build_hierarchy`, `_partition_graph` — **must be a
concrete method raising `NotImplementedError`, never `@abstractmethod`.** An
adapted method never reaches it, so an abstract one makes the entire subfamily
impossible to adapt: `ABCMeta` refuses to instantiate the class. Only `_fit`
stays abstract, and the adapters supply it.

The exception is a hook every subclass must answer whichever route it took,
such as `BaseHybridClusterer._check_steps`. Those stay abstract.

---

## 6. Register — and never pass `kind=`

```python
@register("kmeans")
class KMeans(AdaptedClusterer, BasePrototypeClusterer):
    ...
```

That is the whole declaration. `@register` takes the kind from the class's
`_kind`, and **`_kind` is declared once per kind-level base**, so you inherit
the right one:

| Base | `_kind` |
|---|---|
| `BaseClusterer` | `CLUSTERER` |
| `BaseDimReducer` | `DIM_REDUCER` |
| `BaseTransformer` | `TRANSFORMER` |
| `BaseDissimilarity` | `DISSIMILARITY` |
| `BaseValidityIndex` | `VALIDITY_INDEX` |
| `BaseSelector` | `SELECTOR` |
| `BaseTask` | `TASK` |
| `BaseOutlierDetector`, `BaseGenerator`, `BasePredictor` | the matching member |

**Never set `_kind` on a concrete class.** It can then disagree with the base
the class actually derives from, and the registry believes the class.
`tests/test_registry.py` asserts every `ComponentKind` member is claimed by
exactly one base, so a new kind added without its base fails the suite rather
than failing quietly at report time.

A component is registered **when its module is imported**. If `REGISTRY.get`
cannot find your name, that is usually the reason.

---

## 7. Mixin order

scikit-learn's own mixins go **left** of `BaseComponent`, and our capability
mixins go **left** of the family base. scikit-learn 1.8 checks this
(`check_mixin_order`) and fails `check_estimator` otherwise.

```python
class BasePrototypeClusterer(InductiveMixin, TransformerMixin, BasePartitionalClusterer, ABC):
```

The general rule: more specialised precedes more general.

**For an adapter, the adapter goes first of all:**

```python
class KMeans(AdaptedClusterer, BasePrototypeClusterer):
```

The MRO must reach `AdaptedClusterer._fit` before the family base's `_fit`,
which raises `NotImplementedError`. Check yours resolves as you expect:

```bash
python -c "
from xxcluster.cluster.partitional.sse_based.kmeans import KMeans
print(' -> '.join(c.__name__ for c in KMeans.__mro__[:8]))
"
```

**Mix in only what you have.** `InductiveMixin` only if you can label unseen
observations; `NoiseAwareMixin` only if you can decline to assign one. And
check your family base first — `BasePrototypeClusterer` already carries
`InductiveMixin`, so adding it again is noise.

---

## 8. Verify before you open the pull request

```bash
# 1. The suite still passes
python -m pytest -q

# 2. Your component conforms to scikit-learn
python -c "
from sklearn.utils.estimator_checks import check_estimator
from xxcluster.<path> import <YourClass>
check_estimator(<YourClass>(<minimal args>)); print('PASSED')
"

# 3. The registry can find it, and its declaration is what you meant
python -c "
import xxcluster.<path>                       # import registers it
from xxcluster.core.registry import REGISTRY
print(REGISTRY.capabilities('<name>').describe())
"
```

If `check_estimator` fails on something genuinely inapplicable to unsupervised
work, record the exclusion and the reason in the pull request rather than
weakening the class.

---

## The failure messages, and what they mean

| Message | Cause |
|---|---|
| `_fit did not set: X` | `_required_fitted` declares `X`; your `_fit` (or `_attr_map`) does not provide it |
| `declares <cap> but has no <method>` | `_capabilities` promises an interface you did not implement |
| `Cannot clone object` | a parameter was mutated in `__init__`, or something that is not an estimator was passed as one |
| `'X' object has no attribute 'backend_'` from `predict` | missing `ensure_fitted(self, "backend_")` — scikit-learn ≥ 1.6 requires `NotFittedError` before fit |
| `no component registered as 'X'` | the module was never imported |
| `'X' is already registered to ...` | names are permanent; pick another |
| `X adapts Y, which is not installed` | uncomment the backend in `requirements.txt` |
