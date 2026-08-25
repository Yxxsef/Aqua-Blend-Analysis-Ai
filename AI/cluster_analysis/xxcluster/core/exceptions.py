"""
Exception and warning hierarchy.

Every error raised by this package derives from `XXClusterError`, so a
caller can distinguish our failures from a backend's. scikit-learn's
`NotFittedError` is re-exported rather than redefined, so that
`except NotFittedError` behaves the same for our classes and for adapted
third-party estimators.
"""

from __future__ import annotations

from sklearn.exceptions import ConvergenceWarning, NotFittedError

__all__ = [
    "XXClusterError",
    "ContractViolationError",
    "BackendUnavailableError",
    "RegistryError",
    "ConvergenceError",
    "NotFittedError",
    "ConvergenceWarning",
]


class XXClusterError(Exception):
    """Base class for every error raised by xxcluster."""


class ContractViolationError(XXClusterError):
    """A component does not honour the contract it declares.

    Raised when a subclass fails to set a documented fitted attribute, or
    when its declared capabilities contradict its behaviour (for example a
    method declaring `is_inductive` without exposing `predict`).
    """


class BackendUnavailableError(XXClusterError):
    """An adapted estimator's third-party dependency is not installed.

    Raised at fit time rather than import time, so that the rest of the
    package remains importable with only the core dependencies present.
    """


class RegistryError(XXClusterError):
    """A component name is unknown, or already taken by another component."""


class ConvergenceError(XXClusterError):
    """An iterative method failed to converge and cannot return a result.

    Use only where no partial result is meaningful; prefer emitting
    `ConvergenceWarning` and returning the last iterate otherwise.
    """
