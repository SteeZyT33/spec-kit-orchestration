# PyPI Publication Decision for Orca

**Date:** 2026-04-29
**Status:** Decided
**Decision:** Option C — no PyPI publication; perf-lab devcontainer uses bind-mount only

This note captures the Phase 4b-pre-3 decision. Phase 4b's perf-lab integration spec (`docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md` § "Devcontainer Installation") needs a real install path; T0Z11 in the perf-lab spec PR depends on this decision.

## Real-state findings

- **`pyproject.toml` package name is `orca`** (verified 2026-04-29: `grep "^name" pyproject.toml` → `name = "orca"`). The Phase 1 rename moved away from `spec-kit-orca`.
- **`orca` on PyPI is taken** by UrbanSim's land-use modeling package (HTTP 200 on `https://pypi.org/pypi/orca/json`). We cannot publish under that name.
- **`spec-kit-orca` on PyPI is unclaimed** (HTTP 404). The legacy fork name is still available.
- **The Phase 4b spec previously assumed `spec-kit-orca`** as the install line. v2.2 of that spec needs to be reconciled with the real package name as part of this decision.

## Options evaluated

### A. Publish as `spec-kit-orca` (distribution name) with import name `orca`

Python permits a distribution name distinct from the import path (e.g., `Pillow` is `import PIL`). pyproject would re-declare `name = "spec-kit-orca"` while preserving `src/orca/` and `[tool.setuptools.packages.find]` such that `import orca` keeps working.

- **Pro:** PyPI install line `uv tool install spec-kit-orca` works in perf-lab Dockerfile; the legacy name is reused, no re-squatting risk.
- **Con:** Distribution-vs-import-name divergence is a known footgun for newcomers; introspection (`importlib.metadata.version("orca")` per Pre-2) breaks unless we also expose the dist metadata under both names. Pre-2 currently calls `version("orca")` — this would need to change to `version("spec-kit-orca")` and the test re-pinned. Not free.
- **Con:** No external consumer is asking for PyPI install today. Publishing pre-emptively for a single internal consumer (perf-lab v6, which is mid-build) is speculative.

### B. Publish under a new name (`orca-toolchest`, `orca-cli`, etc.)

Same shape as A but with a fresh, descriptive name.

- **Pro:** No legacy-name reuse; the name describes what orca actually is now.
- **Con:** Adds a fourth name to the project's identity universe (`orca` import, `orca-toolchest` distribution, `Orca` colloquial, `spec-kit-orca` historical). More confusion, not less.
- **Con:** Same Pre-2 / `importlib.metadata` re-pinning required.
- **Con:** Same speculative-publication concern as A.

### C. No PyPI publication; bind-mount only

Perf-lab Dockerfile mounts the orca source tree at a fixed path inside the devcontainer; `ENV ORCA_PROJECT=/opt/orca` plus a bind-mount of the host's orca clone. No `pip install` of orca; perf-lab skills invoke `orca-cli` via `uv run --project $ORCA_PROJECT orca-cli ...` (or equivalent).

- **Pro:** Zero publication overhead. No name decisions, no PyPI account, no version-bump-and-push workflow.
- **Pro:** Operators iterating on orca and perf-lab simultaneously get instant pickup of orca changes (no `pip install` cycle).
- **Pro:** Pre-2's `importlib.metadata.version("orca")` keeps working unchanged in editable / source installs (the package is still importable; only its distribution-status changes).
- **Pro:** Defers the publication decision until there is an external consumer demanding it. When that happens, A or B can ship in a single follow-up.
- **Con:** Operators not running perf-lab from a host with an orca clone need an extra setup step. Mitigated by clear documentation in T0Z13 operator guide.
- **Con:** No simple `pip install orca-something` path for ad-hoc users. Acceptable: orca is not a standalone library yet.

## Decision

**Option C.** No PyPI publication for Phase 4b. Perf-lab devcontainer bind-mounts the orca source tree.

Rationale:
1. **No external demand.** Perf-lab v6 is the only near-term consumer, and bind-mount works fine for it.
2. **Avoids a one-way naming decision** under time pressure. A and B both lock in a distribution name; once published, renames break consumers.
3. **Keeps Pre-2's `importlib.metadata.version("orca")` stable.** Changing the metadata source mid-Phase-4b would add risk for no benefit.
4. **Smallest scope for Phase 4b-pre-3.** No Twine workflow, no PyPI 2FA setup, no maintainer-mailing-list entry. Decision artifact + a Dockerfile-shape note is the deliverable.

## Implications for downstream tasks

### Phase 4b spec (orca repo) — minor updates needed

Lines in `docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md` that mention "spec-kit-orca" as a PyPI install or a publication target should be reconciled:
- The Dockerfile snippet's `uv tool install spec-kit-orca==<version-pin>` (Option A) becomes a documented but DEFERRED path; the canonical install for Phase 4b is bind-mount (Option B in that section).
- The "Phase 4b-pre-3" task description in the spec should say "decision: bind-mount only; publication deferred."

These edits can ride on the Pre-3 commit or land in v2.3 of the spec; either is fine.

### Phase 4b perf-lab spec PR — T0Z11 implementation

T0Z11 implements bind-mount in `.devcontainer/Dockerfile`:
```dockerfile
# orca source bind-mount (Phase 4b-pre-3 decision: no PyPI publication)
ENV ORCA_PROJECT=/opt/orca
# perf-lab's compose file mounts the host orca tree at /opt/orca read-only.
# Operators without a local orca clone: see docs/runtime/orca-policy.md § Setup.
```

The compose file (`docker-compose.yml` or equivalent) gets the actual mount line.

### Future: when to revisit

Trigger conditions for revisiting (move to A or B):
- A second external consumer outside perf-lab requests a `pip install`-able orca.
- Perf-lab v6 ships and operators report bind-mount friction.
- Orca semantic-versioning becomes important enough that distribution-as-artifact pays for itself.

Until then, this decision stands.

## References

- pyproject.toml (current): `name = "orca"`, `version = "2.1.0"`
- PyPI state (2026-04-29): `orca` taken (UrbanSim), `spec-kit-orca` available
- Phase 4b spec § "Devcontainer Installation"
- Phase 4b spec § "Orca Repo Prerequisites" → Phase 4b-pre-3
- Plan: `docs/superpowers/plans/2026-04-29-orca-phase-4b-pre-prereqs.md` § "Task 3"
