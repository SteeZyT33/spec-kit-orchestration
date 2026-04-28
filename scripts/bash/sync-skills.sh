#!/usr/bin/env bash
# sync-skills.sh - regenerate orca SKILL.md wrappers from source command files.
#
# Use this after editing source command files at
# `.specify/extensions/orca/plugins/claude-code/commands/*.md` (host repo) or
# `plugins/claude-code/commands/*.md` (orca source tree). Force-regenerates
# every `orca-<base>/SKILL.md` so edits propagate.
#
# Mirrors the generator in src/orca/assets/orca-main.sh:generate_extension_skills().
#
# Search order matches the bootstrap:
#   1. .specify/extensions/orca/plugins/claude-code/commands  (installed host repo)
#   2. plugins/claude-code/commands                           (orca source tree)
#
# Target skills dir:
#   - .claude/skills/   when integration.json says claude
#   - .agents/skills/   otherwise
#
# Exit 0 on success (including the "no commands dir found" graceful case).

set -euo pipefail

# Resolve commands dir.
ext_commands=""
if [[ -d ".specify/extensions/orca/plugins/claude-code/commands" ]]; then
  ext_commands=".specify/extensions/orca/plugins/claude-code/commands"
elif [[ -d "plugins/claude-code/commands" ]]; then
  ext_commands="plugins/claude-code/commands"
else
  echo "sync-skills: no orca commands dir found (looked in .specify/extensions/orca/... and plugins/claude-code/...)" >&2
  exit 0
fi

# Resolve integration (claude vs other) from .specify/integration.json if present.
integration="claude"
if [[ -f ".specify/integration.json" ]]; then
  detected="$(python3 -c 'import json,sys
try:
    print(json.load(open(".specify/integration.json")).get("integration",""))
except Exception:
    pass' 2>/dev/null || true)"
  if [[ -n "$detected" ]]; then
    integration="$detected"
  fi
fi

# Generate all skill files via a single Python heredoc.
result=$(python3 - "$ext_commands" "$integration" <<'SKILL_GEN'
import pathlib, re, sys

commands_dir = pathlib.Path(sys.argv[1])
integration = sys.argv[2]

if integration == "claude":
    skills_dir = pathlib.Path(".claude/skills")
    extra_fm = "user-invocable: true\ndisable-model-invocation: true\n"
else:
    skills_dir = pathlib.Path(".agents/skills")
    extra_fm = ""

generated = 0

for cmd_file in sorted(commands_dir.glob("*.md")):
    base = cmd_file.stem
    skill_name = f"orca-{base}"
    skill_dir = skills_dir / skill_name
    skill_file = skill_dir / "SKILL.md"

    text = cmd_file.read_text(encoding="utf-8")

    description = ""
    body = text
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if line.startswith("description:"):
                description = line[len("description:"):].strip().strip("\"'")
                break
        body = text[m.end():]

    if not description:
        description = f"Spec-kit workflow command: {skill_name}"

    safe_desc = description.replace("'", "''")

    skill_dir.mkdir(parents=True, exist_ok=True)

    frontmatter = (
        f"---\n"
        f"name: {skill_name}\n"
        f"description: '{safe_desc}'\n"
        f"compatibility: Requires spec-kit project structure with .specify/ directory\n"
        f"metadata:\n"
        f"  author: github-spec-kit\n"
        f"  source: orca:commands/{base}.md\n"
        f"{extra_fm}"
        f"---\n"
    )

    skill_file.write_text(frontmatter + "\n" + body, encoding="utf-8")
    generated += 1

print(f"{generated}:{skills_dir}")
SKILL_GEN
)

gen="${result%%:*}"
sdir="${result#*:}"

echo "regenerated ${gen} skills at ${sdir}"
