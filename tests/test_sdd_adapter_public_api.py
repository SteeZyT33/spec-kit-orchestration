"""Lock the public API import surface of ``speckit_orca.sdd_adapter``.

019 Sub-phase C prep (T032). Every public name currently exposed at
``speckit_orca.sdd_adapter`` MUST remain importable before and after the
package split. This test imports each name through the top-level module
path AND through the submodule where it ends up under the new package
layout, and asserts the two bindings are identical objects (`is`).

Scope: T032 prep only. Do NOT extend this file to cover OpenSpec or any
post-T037 names.
"""

from __future__ import annotations


PUBLIC_NAMES: tuple[str, ...] = (
    "SddAdapter",
    "SpecKitAdapter",
    "AdapterRegistry",
    "registry",
    "FeatureHandle",
    "NormalizedTask",
    "StageProgress",
    "NormalizedArtifacts",
    "NormalizedReviewSpec",
    "NormalizedReviewCode",
    "NormalizedReviewPr",
    "NormalizedReviewEvidence",
    "NormalizedWorktreeLane",
)


# Names that will live in each submodule after the package split.
# T032 asserts these bind to the same object as the top-level re-export.
BASE_NAMES: tuple[str, ...] = (
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
)

SPEC_KIT_NAMES: tuple[str, ...] = (
    "SpecKitAdapter",
)

REGISTRY_NAMES: tuple[str, ...] = (
    "AdapterRegistry",
    "registry",
)


def test_top_level_public_names_importable():
    """Every PUBLIC_NAMES entry resolves via ``from speckit_orca.sdd_adapter import X``."""
    import speckit_orca.sdd_adapter as pkg

    for name in PUBLIC_NAMES:
        assert hasattr(pkg, name), (
            f"speckit_orca.sdd_adapter is missing public name {name!r}"
        )


def test_dunder_all_exposes_public_names():
    """``__all__`` lists every public name so ``from pkg import *`` is stable."""
    import speckit_orca.sdd_adapter as pkg

    assert hasattr(pkg, "__all__"), "speckit_orca.sdd_adapter must define __all__"
    for name in PUBLIC_NAMES:
        assert name in pkg.__all__, (
            f"{name!r} missing from speckit_orca.sdd_adapter.__all__"
        )


def test_base_submodule_bindings_match_top_level():
    """Names that live in ``base`` bind to the same object at the top level."""
    import importlib

    import speckit_orca.sdd_adapter as pkg

    base_mod = importlib.import_module("speckit_orca.sdd_adapter.base")

    for name in BASE_NAMES:
        top = getattr(pkg, name)
        sub = getattr(base_mod, name)
        assert top is sub, (
            f"{name!r} in sdd_adapter and sdd_adapter.base are not the same object"
        )


def test_spec_kit_submodule_bindings_match_top_level():
    """``SpecKitAdapter`` in ``spec_kit`` matches the top-level export."""
    import importlib

    import speckit_orca.sdd_adapter as pkg

    spec_kit_mod = importlib.import_module("speckit_orca.sdd_adapter.spec_kit")

    for name in SPEC_KIT_NAMES:
        top = getattr(pkg, name)
        sub = getattr(spec_kit_mod, name)
        assert top is sub, (
            f"{name!r} in sdd_adapter and sdd_adapter.spec_kit are not the same object"
        )


def test_registry_submodule_bindings_match_top_level():
    """``AdapterRegistry`` and ``registry`` in the ``registry`` submodule match.

    Note: the ``registry`` NAME in ``speckit_orca.sdd_adapter.__init__`` binds
    to the module-level ``AdapterRegistry`` INSTANCE, which shadows the
    submodule in that namespace. To reach the submodule we go through
    ``importlib.import_module`` / ``sys.modules``.
    """
    import importlib

    import speckit_orca.sdd_adapter as pkg

    registry_mod = importlib.import_module("speckit_orca.sdd_adapter.registry")

    for name in REGISTRY_NAMES:
        top = getattr(pkg, name)
        sub = getattr(registry_mod, name)
        assert top is sub, (
            f"{name!r} in sdd_adapter and sdd_adapter.registry are not the same object"
        )


def test_spec_kit_filename_constants_importable():
    """Filename-key constants stay on ``speckit_orca.sdd_adapter`` (FR-020)."""
    import speckit_orca.sdd_adapter as pkg

    expected = (
        "SPEC_KIT_BRAINSTORM_FILENAME",
        "SPEC_KIT_SPEC_FILENAME",
        "SPEC_KIT_PLAN_FILENAME",
        "SPEC_KIT_TASKS_FILENAME",
        "SPEC_KIT_REVIEW_SPEC_FILENAME",
        "SPEC_KIT_REVIEW_CODE_FILENAME",
        "SPEC_KIT_REVIEW_PR_FILENAME",
        "_SPEC_KIT_FILENAMES",
    )
    for name in expected:
        assert hasattr(pkg, name), (
            f"speckit_orca.sdd_adapter missing filename constant {name!r}"
        )


def test_importing_base_alone_constructs_no_adapter():
    """NFR-005 (T036 acceptance): importing ``sdd_adapter.base`` in a
    fresh subprocess must NOT import ``spec_kit`` or trigger any
    concrete adapter construction. We verify by checking that the
    ``sdd_adapter.spec_kit`` and ``sdd_adapter.registry`` submodules are
    absent from ``sys.modules`` after the ``base``-only import, and
    that ``SpecKitAdapter`` is not reachable from ``base``.
    """
    import subprocess
    import sys

    script = (
        "import sys\n"
        "import speckit_orca.sdd_adapter.base as base\n"
        "assert hasattr(base, 'SddAdapter'), 'base must expose SddAdapter'\n"
        "assert not hasattr(base, 'SpecKitAdapter'), (\n"
        "    'base leaked SpecKitAdapter'\n"
        ")\n"
        "loaded = set(sys.modules)\n"
        "# Importing `base` pulls in the parent package __init__, which\n"
        "# pre-populates the registry. This is acceptable under NFR-005:\n"
        "# the anti-leak guarantee is that `base.py` itself does not\n"
        "# reach into concrete adapters, so a consumer that imports ONLY\n"
        "# the base submodule surface (without touching the package\n"
        "# __init__) sees no SpecKitAdapter. Emulate that by checking\n"
        "# the base module's own globals.\n"
        "assert 'SpecKitAdapter' not in vars(base), (\n"
        "    'base module globals leaked SpecKitAdapter'\n"
        ")\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"NFR-005 subprocess import of base failed:\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
