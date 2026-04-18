"""Adapter registry + the module-level default-populated instance.

019 Sub-phase C (T035): extracted from the original ``sdd_adapter.py``.
The registry is the single lookup surface ``flow_state`` (and later
``yolo``, ``matriarch``) use to find the adapter that owns a given
path/feature/repo. Sub-phase C pre-populates it with ``SpecKitAdapter()``
only; T050 will append ``OpenSpecAdapter()``.

Design decisions (plan §Design §3):
  - Plain class over tuple-of-adapters: callers want ``register``,
    ``resolve_for_*``, and ``reset_to_defaults`` as methods.
  - No discovery mechanism: adapters are registered by hand in
    ``_default_adapters()``.
  - ``register`` is idempotent by ``adapter.name``: re-registering the
    same adapter is a no-op, so test helpers and importers can call it
    defensively.
  - Registration ORDER is preserved. ``resolve_for_path`` walks the
    ordered tuple and returns the first adapter whose ``id_for_path``
    is non-None.
"""

from __future__ import annotations

from pathlib import Path

from .base import FeatureHandle, SddAdapter
from .spec_kit import SpecKitAdapter


class AdapterRegistry:
    """Ordered registry of SDD adapters.

    The registry owns the adapter instances used by ``flow_state`` (and
    later ``yolo`` / ``matriarch``) to resolve a path, feature, or repo
    to an adapter. Sub-phase B shipped with only ``SpecKitAdapter``;
    T050 appends ``OpenSpecAdapter``.
    """

    def __init__(self) -> None:
        self._adapters: tuple[SddAdapter, ...] = ()

    def register(self, adapter: SddAdapter) -> None:
        """Register an adapter. Idempotent by ``adapter.name``.

        If an adapter with the same `name` is already registered, this
        is a no-op; existing instances are preserved so in-flight
        references stay valid.
        """
        for existing in self._adapters:
            if existing.name == adapter.name:
                return
        self._adapters = (*self._adapters, adapter)

    def adapters(self) -> tuple[SddAdapter, ...]:
        """Return the ordered tuple of currently-registered adapters."""
        return self._adapters

    def resolve_for_path(
        self,
        path: Path,
        repo_root: Path | None = None,
    ) -> tuple[SddAdapter, str] | None:
        """Return ``(adapter, feature_id)`` for the first adapter that
        claims ``path``, or ``None``.

        Resolution is O(N) over the two in-tree adapters; negligible.
        """
        for adapter in self._adapters:
            feature_id = adapter.id_for_path(path, repo_root=repo_root)
            if feature_id is not None:
                return adapter, feature_id
        return None

    def resolve_for_feature(
        self,
        repo_root: Path,
        feature_id: str,
    ) -> tuple[SddAdapter, FeatureHandle] | None:
        """Return ``(adapter, FeatureHandle)`` for the first adapter whose
        `list_features` yields a handle with ``feature_id``.
        """
        for adapter in self._adapters:
            for handle in adapter.list_features(repo_root):
                if handle.feature_id == feature_id:
                    return adapter, handle
        return None

    def resolve_for_repo(
        self,
        repo_root: Path,
    ) -> tuple[SddAdapter, ...]:
        """Return the adapters whose ``detect(repo_root)`` is ``True``,
        in registration order.
        """
        return tuple(
            adapter for adapter in self._adapters if adapter.detect(repo_root)
        )

    def reset_to_defaults(self) -> None:
        """Drop all adapters and re-register the in-tree defaults."""
        self._adapters = ()
        for adapter in _default_adapters():
            self.register(adapter)


def _default_adapters() -> tuple[SddAdapter, ...]:
    """The in-tree default adapter list.

    019 Sub-phase C T050: ``SpecKitAdapter`` first, ``OpenSpecAdapter``
    second. Registration ORDER is load-bearing for ``resolve_for_path``
    because it walks adapters in order and returns the first match; the
    two adapters' path scopes (``specs/`` vs ``openspec/``) do not
    overlap, so order is belt-and-suspenders.
    """
    # Local import to avoid a circular: openspec.py imports from .base
    # which is fine, but keeping the import here keeps registry.py from
    # pulling adapters at ABC-import time for callers that monkeypatch.
    from .openspec import OpenSpecAdapter

    return (SpecKitAdapter(), OpenSpecAdapter())


# Module-level registry, built at import time and pre-populated with the
# default adapters. ``speckit_orca.sdd_adapter.__init__`` re-exports this
# instance as the canonical ``registry`` name.
registry = AdapterRegistry()
for _adapter in _default_adapters():
    registry.register(_adapter)