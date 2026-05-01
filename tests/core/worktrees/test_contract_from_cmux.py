from pathlib import Path

import pytest

from orca.core.worktrees.contract_from_cmux import parse_cmux_setup, ParseResult


PERFLAB_STYLE = """\
#!/bin/bash
set -euo pipefail
REPO_ROOT="$(git rev-parse --git-common-dir | xargs dirname)"

for f in .env .env.local .env.secrets perf-lab.config.json; do
  [ -e "$REPO_ROOT/$f" ] && ln -sf "$REPO_ROOT/$f" "$f"
done

for d in specs .specify docs shared; do
  [ -e "$d" ] && [ ! -L "$d" ] && rm -rf "$d"
  [ -e "$REPO_ROOT/$d" ] && ln -sfn "$REPO_ROOT/$d" "$d"
done

# Build steps
if [ -f tui/go.sum ]; then
  (cd tui && go mod download)
fi
if [ -f requirements-dev.txt ]; then
  pip install -q -r requirements-dev.txt
fi
"""

LLM_STYLE = """\
#!/usr/bin/env bash
# LLM-generated; uses functions and find
set -e
shared_dirs() {
    find . -maxdepth 1 -type d -name "shared*"
}
for d in $(shared_dirs); do
    ln -sf "../$d" "$d"
done
echo "done"
"""

FIND_FED = """\
#!/bin/bash
for f in $(find . -name ".env*"); do
    ln -sf "$f" .
done
"""


class TestParseCmuxSetup:
    def test_perflab_style_extracts_loops_cleanly(self):
        result = parse_cmux_setup(PERFLAB_STYLE)
        assert isinstance(result, ParseResult)
        assert sorted(result.symlink_files) == sorted(
            [".env", ".env.local", ".env.secrets", "perf-lab.config.json"]
        )
        assert sorted(result.symlink_paths) == sorted(
            ["specs", ".specify", "docs", "shared"]
        )
        # Build steps preserved
        assert "go mod download" in result.init_script_body
        assert "pip install" in result.init_script_body
        assert result.warnings == []

    def test_llm_style_refuses_with_warnings(self):
        result = parse_cmux_setup(LLM_STYLE)
        assert result.symlink_paths == []
        assert result.symlink_files == []
        assert any("cannot extract" in w for w in result.warnings)

    def test_find_fed_iterable_refused(self):
        result = parse_cmux_setup(FIND_FED)
        assert result.symlink_files == []
        assert any("cannot extract" in w for w in result.warnings)

    def test_double_bracket_test_form_accepted(self):
        script = """\
for f in .env .env.local; do
  [[ -e "$REPO_ROOT/$f" ]] && ln -sf "$REPO_ROOT/$f" "$f"
done
"""
        result = parse_cmux_setup(script)
        assert sorted(result.symlink_files) == [".env", ".env.local"]

    def test_test_command_form_accepted(self):
        script = """\
for f in .env .env.local; do
  test -e "$REPO_ROOT/$f" && ln -sf "$REPO_ROOT/$f" "$f"
done
"""
        result = parse_cmux_setup(script)
        assert sorted(result.symlink_files) == [".env", ".env.local"]

    def test_inline_comments_in_loop_body_tolerated(self):
        script = """\
for f in .env .env.local; do
  # symlink env files
  [ -e "$REPO_ROOT/$f" ] && ln -sf "$REPO_ROOT/$f" "$f"
done
"""
        result = parse_cmux_setup(script)
        assert sorted(result.symlink_files) == [".env", ".env.local"]

    def test_boilerplate_only_init_script_body_is_empty(self):
        """Pure shebang/set/REPO_ROOT setups produce empty init_script_body.

        Without the strip, from-cmux would emit a useless after_create.sh
        wrapping nothing but more boilerplate.
        """
        script = """\
#!/bin/bash
set -euo pipefail
REPO_ROOT="$(git rev-parse --git-common-dir | xargs dirname)"

for f in .env .env.local; do
  [ -e "$REPO_ROOT/$f" ] && ln -sf "$REPO_ROOT/$f" "$f"
done
"""
        result = parse_cmux_setup(script)
        assert sorted(result.symlink_files) == [".env", ".env.local"]
        assert result.init_script_body == ""

    def test_real_build_steps_preserved_in_init_script_body(self):
        """When non-boilerplate work remains, it must survive the strip."""
        script = """\
#!/bin/bash
set -euo pipefail
REPO_ROOT="$(git rev-parse --git-common-dir | xargs dirname)"

for f in .env; do
  [ -e "$REPO_ROOT/$f" ] && ln -sf "$REPO_ROOT/$f" "$f"
done

pip install -q -r requirements.txt
"""
        result = parse_cmux_setup(script)
        assert "pip install" in result.init_script_body

    def test_quoted_iterable_refused(self):
        script = """\
for f in "${env_files[@]}"; do
  ln -sf "$f" .
done
"""
        result = parse_cmux_setup(script)
        assert result.symlink_files == []
        assert any("cannot extract" in w for w in result.warnings)
