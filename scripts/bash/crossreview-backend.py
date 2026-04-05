#!/usr/bin/env python3
"""Cross-harness review backend.

Invokes a configured AI harness CLI to review a patch file.
Returns structured JSON with summary, blocking, and non_blocking findings.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cross-harness review backend")
    p.add_argument("--harness", required=True, choices=["codex", "claude", "gemini"])
    p.add_argument("--model", default=None)
    p.add_argument("--effort", default="high")
    p.add_argument("--patch-file", required=True, type=Path)
    p.add_argument("--prompt-file", required=True, type=Path)
    p.add_argument("--schema-file", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--claude-path", default=None, help="Explicit path to claude CLI binary")
    return p.parse_args()


def _failure_payload(harness: str, stderr: str, returncode: int) -> str:
    """Return a structured failure JSON string for non-zero exits."""
    return json.dumps({
        "summary": f"{harness} exited with code {returncode}. See error details.",
        "blocking": [{"file": "—", "issue": stderr[:2000] or "Non-zero exit with no stderr"}],
        "non_blocking": [],
    })


def _run_harness(cmd: list[str], harness: str) -> str:
    """Run a harness subprocess. Return structured failure on non-zero exit."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        sys.stderr.write(f"{harness} stderr: {result.stderr}\n")
        return _failure_payload(harness, result.stderr, result.returncode)
    return result.stdout


def invoke_codex(args: argparse.Namespace, prompt: str) -> str:
    cmd = [
        "codex", "exec",
        "--sandbox", "read-only",
        "--ask-for-approval", "never",
    ]
    if args.model:
        cmd += ["-c", f"model={args.model}"]
    if args.effort:
        cmd += ["-c", f"model_reasoning_effort={args.effort}"]
    cmd += ["--output-schema", str(args.schema_file)]
    cmd.append(prompt)
    return _run_harness(cmd, "codex")


def _resolve_claude(explicit_path: str | None) -> str:
    """Resolve the claude CLI binary, checking common install locations."""
    if explicit_path:
        return explicit_path
    # Check PATH first
    found = shutil.which("claude")
    if found:
        return found
    # Check common install locations (matches specify init/check resolution)
    home = Path.home()
    for candidate in [
        home / ".claude" / "local" / "claude",
        home / ".claude" / "local" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
    ]:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "claude"  # fallback to PATH lookup


def invoke_claude(args: argparse.Namespace, prompt: str) -> str:
    claude_bin = _resolve_claude(getattr(args, "claude_path", None))
    cmd = [
        claude_bin, "-p",
        "--allowedTools", "Read,Grep,Glob,Bash",
    ]
    if args.model:
        cmd += ["--model", args.model]
    if args.effort:
        cmd += ["--effort", args.effort]
    cmd.append(prompt)
    return _run_harness(cmd, "claude")


def invoke_gemini(args: argparse.Namespace, prompt: str) -> str:
    cmd = ["gemini", "--sandbox", "-p"]
    if args.model:
        cmd += ["-m", args.model]
    cmd += ["--output-format", "json"]
    cmd.append(prompt)
    raw = _run_harness(cmd, "gemini")
    try:
        payload = json.loads(raw)
        return payload.get("response", raw)
    except json.JSONDecodeError:
        return raw


def extract_json(raw: str) -> dict:
    """Extract JSON from raw output, handling markdown fences and preamble."""
    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: wrap raw output in a valid structure
    return {
        "summary": "Review completed but output was not structured JSON. Raw output preserved below.",
        "blocking": [],
        "non_blocking": [{"file": "\u2014", "issue": raw[:2000]}],
    }


def main() -> None:
    args = parse_args()

    prompt = args.prompt_file.read_text(encoding="utf-8")
    patch = args.patch_file.read_text(encoding="utf-8")

    full_prompt = f"{prompt}\n\n## Patch to Review\n\n```diff\n{patch}\n```"

    harness_fn = {
        "codex": invoke_codex,
        "claude": invoke_claude,
        "gemini": invoke_gemini,
    }[args.harness]

    sys.stderr.write(f"Invoking {args.harness}")
    if args.model:
        sys.stderr.write(f" ({args.model})")
    sys.stderr.write("...\n")

    try:
        raw_result = harness_fn(args, full_prompt)
    except subprocess.TimeoutExpired:
        raw_result = json.dumps({
            "summary": "Review timed out after 300s",
            "blocking": [],
            "non_blocking": [],
        })
    except FileNotFoundError:
        raw_result = json.dumps({
            "summary": f"Harness CLI '{args.harness}' not found. Is it installed?",
            "blocking": [],
            "non_blocking": [],
        })

    parsed = extract_json(raw_result)

    # Validate contract: ensure required keys exist
    for key in ("summary", "blocking", "non_blocking"):
        if key not in parsed:
            parsed = {
                "summary": parsed.get("summary", "Output missing required fields."),
                "blocking": parsed.get("blocking", []),
                "non_blocking": parsed.get("non_blocking", [{"file": "—", "issue": str(parsed)[:2000]}]),
            }
            break

    output_json = json.dumps(parsed, indent=2)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_json, encoding="utf-8")
    print(output_json)


if __name__ == "__main__":
    main()
