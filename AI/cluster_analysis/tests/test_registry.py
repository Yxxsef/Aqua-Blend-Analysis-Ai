"""
Tests for the registry and the capability declarations it reads.

What this layer guarantees: a name resolves to exactly one class, the
taxonomy filters agree with the declarations, and a name that means two
things is refused rather than silently rebound.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

import xxcluster
from xxcluster.core.exceptions import RegistryError
from xxcluster.core.registry import ComponentRegistry
from xxcluster.core.tags import Capabilities
from xxcluster.core.types import (
    Assignment,
    Backend,
    ComponentKind,
    Family,
    Scaling,
    SubFamily,
)


@pytest.fixture
def registry() -> ComponentRegistry:
    registry = ComponentRegistry()

    @registry.register("kmeans", kind=ComponentKind.CLUSTERER)
    class KMeans:
        _capabilities = Capabilities(
            family=Family.PARTITIONAL,
            subfamily=SubFamily.SSE_BASED,
            requires_n_clusters=True,
            is_inductive=True,
        )

        def __init__(self, n_clusters: int = 3) -> None:
            self.n_clusters = n_clusters

    @registry.register("dbscan", kind=ComponentKind.CLUSTERER)
    class DBSCAN:
        _capabilities = Capabilities(
            family=Family.PARTITIONAL,
            subfamily=SubFamily.DENSITY_BASED,
            handles_noise=True,
            scales_to=Scaling.LARGE,
        )

    @registry.register("pca", kind=ComponentKind.DIM_REDUCER)
    class PCA:
        _capabilities = Capabilities(backend=Backend.SKLEARN, is_inductive=True)

    return registry


# --- Registration ----------------------------------------------------------


def test_registered_name_resolves_to_its_class(registry):
    assert registry.get("kmeans").__name__ == "KMeans"


def test_duplicate_name_is_refused(registry):
    """Names reach saved artefacts, so rebinding one makes a result ambiguous."""
    with pytest.raises(RegistryError, match="already registered"):

        @registry.register("kmeans")
        class Impostor:
            pass


def test_duplicate_name_can_be_overwritten_deliberately(registry):
    @registry.register("kmeans", overwrite=True)
    class Replacement:
        pass

    assert registry.get("kmeans").__name__ == "Replacement"


def test_unknown_name_lists_what_is_registered(registry):
    with pytest.raises(RegistryError, match="kmeans"):
        registry.get("k_means")


def test_kind_mismatch_is_caught(registry):
    with pytest.raises(RegistryError, match="not a"):
        registry.get("pca", kind=ComponentKind.CLUSTERER)


def test_kind_defaults_to_the_class_declaration():
    registry = ComponentRegistry()

    @registry.register("thing")
    class Thing:
        _kind = ComponentKind.CLUSTERER

    assert registry.names(kind=ComponentKind.CLUSTERER) == ["thing"]


def test_registering_a_non_class_is_refused():
    registry = ComponentRegistry()
    with pytest.raises(RegistryError, match="must decorate a class"):
        registry.register("f")(lambda: None)


# --- Construction ----------------------------------------------------------


def test_create_instantiates_with_parameters(registry):
    assert registry.create("kmeans", n_clusters=5).n_clusters == 5


def test_create_reports_a_bad_parameter_by_name(registry):
    with pytest.raises(RegistryError, match="cannot construct"):
        registry.create("kmeans", n_clustres=5)


# --- Filtering -------------------------------------------------------------


def test_names_are_listed_in_registration_order(registry):
    """Stable across runs, so a generated table diffs cleanly."""
    assert registry.names() == ["kmeans", "dbscan", "pca"]


def test_names_filter_by_kind(registry):
    assert registry.names(kind=ComponentKind.DIM_REDUCER) == ["pca"]


def test_names_filter_by_subfamily(registry):
    assert registry.names(subfamily=SubFamily.DENSITY_BASED) == ["dbscan"]


def test_applicable_shortlists_on_declarations(registry):
    assert registry.applicable(handles_noise=True) == ["dbscan"]


def test_applicable_without_properties_lists_everything(registry):
    assert registry.applicable(kind=ComponentKind.CLUSTERER) == ["kmeans", "dbscan"]


def test_iteration_and_membership(registry):
    assert len(registry) == 3
    assert "pca" in registry
    assert [name for name, _ in registry] == registry.names()


# --- Capabilities ----------------------------------------------------------


def test_capabilities_come_from_the_class(registry):
    assert registry.capabilities("dbscan").handles_noise


def test_a_class_declaring_nothing_gets_defaults():
    """A gap in the write-up shows as a default row, not an exception."""
    registry = ComponentRegistry()

    @registry.register("bare")
    class Bare:
        pass

    assert registry.capabilities("bare") == Capabilities()


def test_describe_renders_enums_as_values(registry):
    row = registry.capabilities("kmeans").describe()
    assert row["family"] == "partitional"
    assert row["assignment"] == Assignment.CRISP.value
    assert row["scales_to"] == "medium"


def test_describe_omits_prose_only_fields(registry):
    row = registry.capabilities("kmeans").describe()
    assert "references" not in row and "doc_label" not in row


def test_is_applicable_rejects_an_unknown_property():
    """A misspelling would otherwise shortlist everything rather than nothing."""
    with pytest.raises(ValueError, match="unknown capability"):
        Capabilities().is_applicable(handles_mising=True)


def test_is_applicable_ignores_properties_the_data_lacks():
    assert Capabilities().is_applicable(handles_missing=False)


# --- Kind declarations -----------------------------------------------------
#
# `ComponentKind` says each member pairs with a base class. These keep that
# true: without a declared `_kind`, every `@register` needs a `kind=` argument
# and forgetting one silently empties the registry's taxonomy filters.


def _kind_bases() -> dict:
    """Every kind-level base, by the kind it claims."""
    from xxcluster.core.base import (
        BaseClusterer,
        BaseDimReducer,
        BaseGenerator,
        BaseOutlierDetector,
        BasePredictor,
        BaseTransformer,
    )
    from xxcluster.measures.dissimilarity.base import BaseDissimilarity
    from xxcluster.measures.validation.base import BaseValidityIndex
    from xxcluster.selection.base import BaseSelector
    from xxcluster.tasks.base import BaseTask

    bases = (
        BaseClusterer, BaseDimReducer, BaseTransformer, BaseOutlierDetector,
        BaseGenerator, BasePredictor, BaseDissimilarity, BaseValidityIndex,
        BaseSelector, BaseTask,
    )
    return {base._kind: base for base in bases}


def test_every_component_kind_has_a_base_class():
    """The pairing `ComponentKind` documents; nothing else enforces it."""
    claimed = _kind_bases()
    missing = [k for k in ComponentKind if k not in claimed]
    assert not missing, f"no base class declares: {[k.value for k in missing]}"


def test_no_two_bases_claim_the_same_kind():
    from xxcluster.core.base import BaseClusterer, BaseDimReducer

    assert BaseClusterer._kind is not BaseDimReducer._kind


def test_a_subfamily_base_inherits_its_kind():
    """So a concrete method declares nothing and still registers correctly."""
    from xxcluster.cluster.partitional.sse_based.base import BasePrototypeClusterer

    assert BasePrototypeClusterer._kind is ComponentKind.CLUSTERER


def test_dim_reducer_overrides_the_transformer_kind():
    """It is a transformer, but the more specific kind must win."""
    from xxcluster.core.base import BaseDimReducer

    assert BaseDimReducer._kind is ComponentKind.DIM_REDUCER


def test_register_takes_the_kind_from_the_base():
    """The point of all of the above: `@register("name")` and nothing else."""
    from xxcluster.core.base import BaseClusterer

    registry = ComponentRegistry()

    @registry.register("some_method")
    class SomeMethod(BaseClusterer):
        def _fit(self, X, y=None, **kw):
            pass

    assert registry.names(kind=ComponentKind.CLUSTERER) == ["some_method"]


# --- Population from a bare import -----------------------------------------


def test_importing_the_package_registers_every_shipped_component():
    """`import xxcluster` must be enough to resolve a registered name.

    Run in a fresh interpreter on purpose. Within this suite other modules
    have already imported the method modules, so the registry is populated
    however the package is written and the test would pass either way.

    The guarantee matters beyond convenience: a sweep asks the registry for
    every method of a family, so a registry populated only by whatever the
    caller happened to import silently covers less than the comparison of
    Sect. 8 claims to.
    """
    program = (
        "import xxcluster;"
        "from xxcluster.core.registry import REGISTRY;"
        "print(REGISTRY.get('kmeans').__name__, REGISTRY.get('silhouette').__name__)"
    )
    # The subprocess inherits neither `conftest.py`'s path setup nor this
    # process's `sys.path`, and must not depend on the directory pytest was
    # invoked from. Point it at the package's own parent instead.
    root = pathlib.Path(xxcluster.__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(root), env.get("PYTHONPATH")) if part
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.split() == ["KMeans", "Silhouette"]
