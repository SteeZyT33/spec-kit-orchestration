# Release Process

Orca releases ship via git tag + GitHub Release. There is no PyPI distribution.

## When to release

After landing a meaningful set of changes on `main`. There is no fixed cadence; release when there's something worth shipping.

## How to release

From a clean checkout of `main`:

```bash
git pull origin main
scripts/release.sh vX.Y.Z
```

The script will:

1. Verify the working tree is clean and you're on `main`
2. Verify `vX.Y.Z` is a strict semver bump from the latest tag
3. Bump `pyproject.toml` and refresh `uv.lock`
4. Generate a `CHANGELOG.md` entry from conventional commits since the last tag
5. Create the release commit `chore(release): vX.Y.Z`
6. Create an annotated tag with the CHANGELOG block as the body
7. Push the commit and tag to `origin`
8. Create a GitHub Release with the CHANGELOG as the body

## Choosing the version

Strict semver:
- `v2.1.0` → `v2.1.1` for patch (bug fixes only)
- `v2.1.0` → `v2.2.0` for minor (backwards-compatible features)
- `v2.1.0` → `v3.0.0` for major (breaking changes)

The script enforces this. `v2.1.0` → `v2.3.0` (skip) is rejected.

## Breaking changes

If any commit since the last tag uses `feat!:` / `fix!:` syntax or contains a `BREAKING CHANGE:` footer, the script:

1. Refuses any version that isn't a major bump
2. Requires `docs/migrations/vN.0.0.md` to exist (empty file is fine)
3. Appends a `### ⚠ BREAKING CHANGES` section to the CHANGELOG
4. Adds a `**Migration guide:**` link to the GitHub Release body

Write the migration doc as prose. There's no template — describe what consumers need to change. The file's existence is the contract.

## Flags

- `--dry-run` — print what would happen, change nothing
- `--allow-empty` — proceed even if no conventional commits since last tag
- `--allow-branch <name>` — release from a non-`main` branch
- `--resume` — retry after a partial failure (skips already-completed steps)

## Recovery

If the script fails partway:

- **Pre-flight failure:** no state changes; fix the cause and re-run
- **After commit, before push:** `scripts/release.sh vX.Y.Z --resume` retries push + release create
- **After push, before GitHub Release:** `gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <(awk '/^## vX.Y.Z/,/^## v[0-9]/' CHANGELOG.md | sed '$d')`

## Migration to release-please (future)

When PR-based release automation is desired:

1. Delete `scripts/release.sh` and `tests/scripts/test_release.sh`
2. Add `.github/workflows/release-please.yml`:
   ```yaml
   on:
     push:
       branches: [main]
   jobs:
     release-please:
       runs-on: ubuntu-latest
       steps:
         - uses: googleapis/release-please-action@v4
           with:
             release-type: python
             package-name: orca
   ```

CHANGELOG history continues uninterrupted because the script's output format matches release-please's verbatim.
