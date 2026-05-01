"""Agent launcher: prompt-file + launcher-script pattern.

Per spec §"Agent-launch quoting via prompt-file + launcher-script", the
prompt is written to a separate mode-0600 file that the launcher reads
and deletes (one-shot). The launcher script itself is mode-0700 and
persists for the lane lifetime (removed by `wt rm`). No tmux
set-environment is used, so the prompt does not leak across panes.
"""
from __future__ import annotations

import os
import shlex
import stat
from pathlib import Path

LAUNCHER_DIR = ".orca"

# Tokens with these characters are rejected to keep the launcher's bash
# from interpreting hostile content from a clone's worktrees.toml. The
# policy is: agents.<name> must be a plain command + args (no shell syntax).
_FORBIDDEN_METACHARS = (";", "&", "|", "`", "$", ">", "<", "\n")


def launcher_path(worktree_dir: Path, lane_id: str) -> Path:
    return worktree_dir / LAUNCHER_DIR / f".run-{lane_id}.sh"


def prompt_path(worktree_dir: Path, lane_id: str) -> Path:
    return worktree_dir / LAUNCHER_DIR / f".run-{lane_id}.prompt"


def _quote_agent_cmd(agent_cmd: str) -> str:
    """shlex.split + per-token metachar reject + shlex.quote each token.

    Rejects shell metacharacters so a hostile ``agents.<name>`` config
    cannot smuggle commands into the launcher's bash. Returns a string
    safe to interpolate into the launcher body.
    """
    try:
        tokens = shlex.split(agent_cmd)
    except ValueError as exc:  # unbalanced quotes etc.
        raise ValueError(
            f"agents.<name> failed shlex parse: {exc}"
        ) from exc
    if not tokens:
        raise ValueError("agents.<name> is empty after shlex.split")
    for token in tokens:
        if any(c in token for c in _FORBIDDEN_METACHARS):
            raise ValueError(
                "agents.<name> contains shell metacharacters; specify "
                "command + args without shell syntax (got token "
                f"{token!r})"
            )
    return " ".join(shlex.quote(t) for t in tokens)


def write_launcher(
    *,
    worktree_dir: Path,
    lane_id: str,
    agent_cmd: str,
    prompt: str | None,
    extra_args: list[str],
) -> Path:
    """Write the launcher script (and prompt file if a prompt is supplied).

    Returns the launcher path. Caller is responsible for invoking it via
    tmux send_keys; this function does not touch tmux.

    Raises ValueError if ``agent_cmd`` contains shell metacharacters.
    """
    ldir = worktree_dir / LAUNCHER_DIR
    ldir.mkdir(parents=True, exist_ok=True)

    pf = prompt_path(worktree_dir, lane_id)
    if prompt is not None:
        pf.write_text(prompt, encoding="utf-8")
        os.chmod(pf, 0o600)

    quoted_cmd = _quote_agent_cmd(agent_cmd)
    quoted_extra = " ".join(shlex.quote(a) for a in extra_args)
    rel_prompt = f"{LAUNCHER_DIR}/.run-{lane_id}.prompt"
    if prompt is not None:
        body = f'''#!/usr/bin/env bash
set -e
PROMPT_FILE="{rel_prompt}"
if [[ -f "$PROMPT_FILE" ]]; then
  PROMPT="$(cat "$PROMPT_FILE")"
  rm -f "$PROMPT_FILE"
else
  PROMPT=""
fi
exec {quoted_cmd}{(" " + quoted_extra) if quoted_extra else ""} --prompt "$PROMPT"
'''
    else:
        body = f'''#!/usr/bin/env bash
set -e
exec {quoted_cmd}{(" " + quoted_extra) if quoted_extra else ""}
'''

    lpath = launcher_path(worktree_dir, lane_id)
    lpath.write_text(body, encoding="utf-8")
    os.chmod(lpath, 0o700)
    return lpath
