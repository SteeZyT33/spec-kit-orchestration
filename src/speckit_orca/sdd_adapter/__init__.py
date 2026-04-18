"""SDD Adapter package (was ``sdd_adapter.py``).

019 Sub-phase C (T033-T036): the original single-module
``sdd_adapter.py`` split into a package. Every Phase 1 public name stays
importable via ``from speckit_orca.sdd_adapter import X`` (FR-020,
NFR-003); T032's public-API test locks this surface before and after.

Submodule layout:
  - ``base``: ABC + normalized dataclasses. No adapter construction.
  - ``spec_kit``: concrete ``SpecKitAdapter`` + spec-kit filename
    constants and helpers private to it.
  - ``registry``: ``AdapterRegistry`` class and the default-populated
    module-level ``registry`` instance.

Sub-phase B's ``_SPEC_KIT_ADAPTER`` deprecation shim lives in
``speckit_orca.flow_state`` (PEP 562 ``__getattr__`` + a ``ModuleType``
subclass for setattr interception). The shim is NOT affected by this
package split: it operates on ``flow_state``'s module object, and its
adapter reads happen through ``sdd_adapter.registry``, which stays
importable at the same top-level name.
"""

from __future__ import annotations

from .base import (
    FeatureHandle,
    NormalizedArtifacts,
    NormalizedReviewCode,
    NormalizedReviewEvidence,
    NormalizedReviewPr,
    NormalizedReviewSpec,
    NormalizedTask,
    NormalizedWorktreeLane,
    SddAdapter,
    StageProgress,
)
from .openspec import OpenSpecAdapter
from .registry import AdapterRegistry, registry
from .spec_kit import (
    SPEC_KIT_BRAINSTORM_FILENAME,
    SPEC_KIT_PLAN_FILENAME,
    SPEC_KIT_REVIEW_CODE_FILENAME,
    SPEC_KIT_REVIEW_PR_FILENAME,
    SPEC_KIT_REVIEW_SPEC_FILENAME,
    SPEC_KIT_SPEC_FILENAME,
    SPEC_KIT_TASKS_FILENAME,
    SpecKitAdapter,
    _SPEC_KIT_FILENAMES,
)

__all__ = [
    # ABC + normalized types (base)
    "SddAdapter",
    "FeatureHandle",
    "NormalizedTask",
    "StageProgress",
    "NormalizedArtifacts",
    "NormalizedReviewSpec",
    "NormalizedReviewCode",
    "NormalizedReviewPr",
    "NormalizedReviewEvidence",
    "NormalizedWorktreeLane",
    # Concrete spec-kit adapter (spec_kit)
    "SpecKitAdapter",
    # Concrete OpenSpec adapter (openspec)
    "OpenSpecAdapter",
    # Spec-kit filename constants (spec_kit)
    "SPEC_KIT_BRAINSTORM_FILENAME",
    "SPEC_KIT_SPEC_FILENAME",
    "SPEC_KIT_PLAN_FILENAME",
    "SPEC_KIT_TASKS_FILENAME",
    "SPEC_KIT_REVIEW_SPEC_FILENAME",
    "SPEC_KIT_REVIEW_CODE_FILENAME",
    "SPEC_KIT_REVIEW_PR_FILENAME",
    "_SPEC_KIT_FILENAMES",
    # Registry (registry)
    "AdapterRegistry",
    "registry",
]
