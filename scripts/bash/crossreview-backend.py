#!/usr/bin/env python3
"""Cross-review backend with agent selection and adapter dispatch."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


TIER_1 = "tier1-supported-auto"
TIER_2 = "tier2-supported-manual"
TIER_3 = "tier3-known-unsupported"

AUTO_SELECTION_ORDER = ["codex", "claude", "gemini", "opencode"]
KNOWN_UNSUPPORTED = [
    "copilot",
    "windsurf",
    "junie",
    "amp",
    "auggie",
    "kiro-cli",
    "qodercli",
    "roo",
    "kilo",
    "bob",
    "shai",
    "tabnine",
    "kimi",
    "generic",
]
ENV_AGENT_KEYS = ("CROSSREVIEW_AGENT", "REVIEW_AGENT")
ENV_HARNESS_KEYS = ("CROSSREVIEW_HARNESS", "REVIEW_HARNESS")
ENV_ACTIVE_AGENT_KEYS = (
    "ORCA_ACTIVE_AGENT",
    "SPECIFY_ACTIVE_AGENT",
    "CURRENT_AI_PROVIDER",
    "AI_PROVIDER",
)
ENV_LAST_SUCCESS_KEYS = ("CROSSREVIEW_LAST_SUCCESS", "REVIEW_LAST_SUCCESS")
CONFIG_CANDIDATES = (
    "orca-config.yml",
    "orca-config.yaml",
    ".specify/orca-config.yml",
    ".specify/orca-config.yaml",
    "orchestration-config.yml",
    "orchestration-config.yaml",
    ".specify/orchestration-config.yml",
    ".specify/orchestration-config.yaml",
)
INIT_OPTIONS_PATH = Path(".specify/init-options.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cross-review backend")
    parser.add_argument("--agent", default=None)
    parser.add_argument("--harness", default=None)
    parser.add_argument("--active-agent", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--effort", default=None)
    parser.add_argument("--patch-file", required=True, type=Path)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--schema-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--claude-path", default=None, help="Explicit path to claude CLI binary")
    parser.add_argument("--timeout", type=int, default=600, help="Agent subprocess timeout in seconds")
    return parser.parse_args()


def _env_first(keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return None


def _resolve_claude(explicit_path: str | None) -> str:
    if explicit_path:
        return explicit_path

    found = shutil.which("claude")
    if found:
        return found

    home = Path.home()
    for candidate in [
        home / ".claude" / "local" / "claude",
        home / ".claude" / "local" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
    ]:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "claude"


def _can_resolve_claude(explicit_path: str | None) -> bool:
    path = _resolve_claude(explicit_path)
    if Path(path).is_file():
        return os.access(path, os.X_OK)
    return shutil.which(path) is not None


def _normalize_agent_name(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    aliases = {
        "cursor": "cursor-agent",
    }
    return aliases.get(normalized, normalized)


def _parse_scalar(value: str) -> object:
    value = value.split("#", 1)[0].strip()
    if value in {"null", "~", ""}:
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def _load_crossreview_yaml_config() -> dict[str, object]:
    for relative in CONFIG_CANDIDATES:
        path = Path(relative)
        if not path.is_file():
            continue

        values: dict[str, object] = {}
        in_crossreview = False
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not raw_line.startswith((" ", "\t")):
                in_crossreview = stripped == "crossreview:"
                continue
            if not in_crossreview:
                continue
            line = raw_line.lstrip()
            if ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            key = key.strip()
            if key not in {"agent", "harness", "model", "effort", "ask_on_ambiguous", "remember_last_success"}:
                continue
            values[key] = _parse_scalar(raw_value)
        if values:
            return values
    return {}


def _load_init_options() -> dict[str, object]:
    if not INIT_OPTIONS_PATH.is_file():
        return {}
    try:
        payload = json.loads(INIT_OPTIONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def load_runtime_config() -> dict[str, object]:
    config = _load_crossreview_yaml_config()
    init_options = _load_init_options()
    config.setdefault("agent", init_options.get("review_agent"))
    config.setdefault("harness", init_options.get("review_harness"))
    config.setdefault("model", init_options.get("review_model"))
    config.setdefault("effort", init_options.get("review_effort"))
    config.setdefault("ask_on_ambiguous", True)
    config.setdefault("remember_last_success", True)
    config.setdefault("active_agent", init_options.get("ai"))
    return config


def _run_subprocess(cmd: list[str], agent: str, timeout: int) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or f"{agent} exited with code {result.returncode}."
        raise RuntimeError(detail[:4000])
    return result.stdout


def invoke_codex(args: argparse.Namespace, prompt: str) -> str:
    cmd = [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--ask-for-approval",
        "never",
    ]
    if args.model:
        cmd += ["-c", f"model={args.model}"]
    if args.effort:
        cmd += ["-c", f"model_reasoning_effort={args.effort}"]
    cmd += ["--output-schema", str(args.schema_file), prompt]
    return _run_subprocess(cmd, "codex", args.timeout)


def invoke_claude(args: argparse.Namespace, prompt: str) -> str:
    cmd = [
        _resolve_claude(args.claude_path),
        "-p",
        "--allowedTools",
        "Read,Grep,Glob,Bash",
    ]
    if args.model:
        cmd += ["--model", args.model]
    if args.effort:
        cmd += ["--effort", args.effort]
    cmd.append(prompt)
    return _run_subprocess(cmd, "claude", args.timeout)


def invoke_gemini(args: argparse.Namespace, prompt: str) -> str:
    cmd = ["gemini", "--approval-mode", "plan", "--output-format", "json"]
    if args.model:
        cmd += ["-m", args.model]
    cmd += ["-p", prompt]
    raw = _run_subprocess(cmd, "gemini", args.timeout)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    response = payload.get("response", raw)
    if isinstance(response, (dict, list)):
        return json.dumps(response)
    return str(response)


def invoke_opencode(args: argparse.Namespace, prompt: str) -> str:
    cmd = ["opencode", "run", "--format", "json"]
    if args.model:
        cmd += ["--model", args.model]
    if args.effort:
        cmd += ["--variant", args.effort]
    cmd.append(prompt)
    raw = _run_subprocess(cmd, "opencode", args.timeout)
    texts: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            text = event.get("part", {}).get("text")
            if text:
                texts.append(str(text))
    return "\n".join(texts).strip() or raw


def invoke_cursor_agent(args: argparse.Namespace, prompt: str) -> str:
    cmd = ["cursor-agent", "-p", "--output-format", "json"]
    if args.model:
        cmd += ["--model", args.model]
    cmd.append(prompt)
    return _run_subprocess(cmd, "cursor-agent", args.timeout)


@dataclass(frozen=True)
class AgentSpec:
    name: str
    tier: str
    auto_selectable: bool
    available: Callable[[argparse.Namespace], bool]
    invoke: Callable[[argparse.Namespace, str], str] | None


AGENT_SPECS: dict[str, AgentSpec] = {
    "codex": AgentSpec(
        name="codex",
        tier=TIER_1,
        auto_selectable=True,
        available=lambda _args: shutil.which("codex") is not None,
        invoke=invoke_codex,
    ),
    "claude": AgentSpec(
        name="claude",
        tier=TIER_1,
        auto_selectable=True,
        available=lambda args: _can_resolve_claude(args.claude_path),
        invoke=invoke_claude,
    ),
    "gemini": AgentSpec(
        name="gemini",
        tier=TIER_1,
        auto_selectable=True,
        available=lambda _args: shutil.which("gemini") is not None,
        invoke=invoke_gemini,
    ),
    "opencode": AgentSpec(
        name="opencode",
        tier=TIER_1,
        auto_selectable=True,
        available=lambda _args: shutil.which("opencode") is not None,
        invoke=invoke_opencode,
    ),
    "cursor-agent": AgentSpec(
        name="cursor-agent",
        tier=TIER_2,
        auto_selectable=False,
        available=lambda _args: shutil.which("cursor-agent") is not None,
        invoke=invoke_cursor_agent,
    ),
}


def _build_metadata(
    *,
    requested_agent: str | None,
    resolved_agent: str | None,
    active_agent: str | None,
    model: str | None,
    effort: str,
    selection_reason: str,
    support_tier: str,
    status: str,
    substantive_review: bool,
    used_legacy_input: bool,
) -> dict[str, object]:
    return {
        "requested_agent": requested_agent,
        "resolved_agent": resolved_agent,
        "active_agent": active_agent,
        "model": model,
        "effort": effort,
        "selection_reason": selection_reason,
        "support_tier": support_tier,
        "is_cross_agent": bool(active_agent and resolved_agent and active_agent != resolved_agent),
        "same_agent_fallback": bool(active_agent and resolved_agent and active_agent == resolved_agent),
        "status": status,
        "substantive_review": substantive_review,
        "used_legacy_input": used_legacy_input,
    }


def _result(
    *,
    summary: str,
    metadata: dict[str, object],
    blocking: list[dict[str, object]] | None = None,
    non_blocking: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "metadata": metadata,
        "summary": summary,
        "blocking": blocking or [],
        "non_blocking": non_blocking or [],
    }


def _failure_result(
    *,
    summary: str,
    metadata: dict[str, object],
    issue: str,
) -> dict[str, object]:
    return _result(
        summary=summary,
        metadata=metadata,
        blocking=[{"file": "-", "issue": issue[:4000]}],
        non_blocking=[],
    )


def _select_explicit_agent(args: argparse.Namespace) -> tuple[str | None, str | None, str, bool]:
    explicit_agent = _normalize_agent_name(args.agent)
    legacy_harness = _normalize_agent_name(args.harness)
    if explicit_agent and legacy_harness and explicit_agent != legacy_harness:
        return explicit_agent, explicit_agent, f"explicit --agent={explicit_agent} took precedence over legacy --harness={legacy_harness}", False
    if explicit_agent:
        return explicit_agent, explicit_agent, "explicit --agent", False
    if legacy_harness:
        return legacy_harness, legacy_harness, "legacy --harness compatibility input", True
    return None, None, "", False


def _select_from_config(config: dict[str, object]) -> tuple[str | None, str | None, str, bool]:
    config_agent_value = config.get("agent")
    raw_env_agent = _env_first(ENV_AGENT_KEYS)
    config_agent = _normalize_agent_name(raw_env_agent) or _normalize_agent_name(config_agent_value if isinstance(config_agent_value, str) or config_agent_value is None else None)
    if config_agent:
        source = "env crossreview.agent" if raw_env_agent else "configured crossreview.agent"
        return config_agent, config_agent, source, False
    config_harness = config.get("harness")
    raw_env_harness = _env_first(ENV_HARNESS_KEYS)
    legacy_harness = _normalize_agent_name(raw_env_harness) or _normalize_agent_name(config_harness if isinstance(config_harness, str) or config_harness is None else None)
    if legacy_harness:
        source = "legacy env crossreview.harness" if raw_env_harness else "legacy configured crossreview.harness"
        return legacy_harness, legacy_harness, source, True
    return None, None, "", False


def _select_last_success(active_agent: str | None, args: argparse.Namespace, config: dict[str, object]) -> tuple[str | None, str | None, str, bool]:
    if config.get("remember_last_success") is False:
        return None, None, "", False
    remembered = _normalize_agent_name(_env_first(ENV_LAST_SUCCESS_KEYS))
    if not remembered:
        return None, None, "", False
    spec = AGENT_SPECS.get(remembered)
    if spec and spec.auto_selectable and spec.available(args) and remembered != active_agent:
        return remembered, None, "most recent successful reviewer memory", False
    return None, None, "", False


def _candidate_auto_agents(active_agent: str | None, args: argparse.Namespace) -> list[str]:
    candidates: list[str] = []
    for candidate in AUTO_SELECTION_ORDER:
        spec = AGENT_SPECS[candidate]
        if spec.auto_selectable and candidate != active_agent and spec.available(args):
            candidates.append(candidate)
    return candidates


def _auto_select(active_agent: str | None, args: argparse.Namespace, config: dict[str, object]) -> tuple[str | None, str]:
    candidates = _candidate_auto_agents(active_agent, args)
    if candidates:
        candidate = candidates[0]
        if len(candidates) > 1 and config.get("ask_on_ambiguous") is True:
            return candidate, (
                f"highest-ranked installed Tier 1 non-current reviewer ({candidate}); "
                "deterministic fallback used because interactive ambiguity escalation is not implemented"
            )
        return candidate, f"highest-ranked installed Tier 1 non-current reviewer ({candidate})"
    if active_agent:
        spec = AGENT_SPECS.get(active_agent)
        if spec and spec.auto_selectable and spec.available(args):
            return active_agent, f"same-agent fallback because no alternative Tier 1 reviewer was available ({active_agent})"
    for candidate in AUTO_SELECTION_ORDER:
        spec = AGENT_SPECS[candidate]
        if spec.auto_selectable and spec.available(args):
            return candidate, f"highest-ranked installed Tier 1 reviewer ({candidate})"
    return None, ""


def resolve_selection(args: argparse.Namespace, config: dict[str, object]) -> tuple[str | None, str | None, str, str | None, bool]:
    config_active = config.get("active_agent")
    active_agent = _normalize_agent_name(args.active_agent) or _normalize_agent_name(_env_first(ENV_ACTIVE_AGENT_KEYS)) or _normalize_agent_name(config_active if isinstance(config_active, str) or config_active is None else None)

    for selector in (
        lambda ns: _select_explicit_agent(ns),
        lambda ns: _select_from_config(config),
        lambda ns: _select_last_success(active_agent, ns, config),
    ):
        selected, requested_agent, reason, used_legacy_input = selector(args)
        if selected:
            return selected, requested_agent, reason, active_agent, used_legacy_input

    selected, reason = _auto_select(active_agent, args, config)
    return selected, None, reason, active_agent, False


def extract_json(raw: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    texts: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            text = event.get("part", {}).get("text")
            if text:
                texts.append(str(text))
    if texts:
        joined = "\n".join(texts).strip()
        try:
            parsed = json.loads(joined)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            raw = joined

    return {
        "summary": "Review completed but output was not structured JSON. Raw output preserved below.",
        "blocking": [],
        "non_blocking": [{"file": "-", "issue": raw[:4000]}],
    }


def _merge_metadata(parsed: dict[str, object], metadata: dict[str, object]) -> dict[str, object]:
    merged = dict(parsed)
    existing_metadata = merged.get("metadata")
    if isinstance(existing_metadata, dict):
        # Preserve only schema-owned metadata keys from agent output so
        # runtime-authored fields remain authoritative and validation does not
        # fail on arbitrary agent-side telemetry.
        allowed_keys = set(metadata)
        filtered_existing_metadata = {
            key: value for key, value in existing_metadata.items() if key in allowed_keys
        }
        metadata = {**filtered_existing_metadata, **metadata}
    merged["metadata"] = metadata
    for key in ("summary", "blocking", "non_blocking"):
        if key not in merged:
            merged[key] = [] if key != "summary" else "Output missing required fields."
    return merged


def _type_matches(expected: object, value: object) -> bool:
    expected_types = expected if isinstance(expected, list) else [expected]
    mapping = {
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "null": lambda v: v is None,
    }
    for expected_type in expected_types:
        checker = mapping.get(expected_type)
        if checker and checker(value):
            return True
    return False


def _validate_against_schema(data: object, schema: dict[str, object], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not _type_matches(expected_type, data):
        return [f"{path}: expected {expected_type}, got {type(data).__name__}"]

    if isinstance(data, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in data:
                    errors.append(f"{path}: missing required property '{key}'")
        if schema.get("additionalProperties") is False and isinstance(properties, dict):
            for key in data:
                if key not in properties:
                    errors.append(f"{path}: unexpected property '{key}'")
        if isinstance(properties, dict):
            for key, value in data.items():
                child_schema = properties.get(key)
                if isinstance(child_schema, dict):
                    errors.extend(_validate_against_schema(value, child_schema, f"{path}.{key}"))
    elif isinstance(data, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(data):
                errors.extend(_validate_against_schema(item, item_schema, f"{path}[{index}]"))
    return errors


def validate_output(parsed: dict[str, object], schema_path: Path) -> list[str]:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to load schema '{schema_path}': {exc}"]
    if not isinstance(schema, dict):
        return [f"Schema '{schema_path}' is not a JSON object."]
    return _validate_against_schema(parsed, schema)


def main() -> None:
    args = parse_args()
    config = load_runtime_config()
    if args.model is None and isinstance(config.get("model"), str):
        args.model = str(config["model"])
    if args.effort is None and isinstance(config.get("effort"), str):
        args.effort = str(config["effort"])
    if args.effort is None:
        args.effort = "high"
    prompt = args.prompt_file.read_text(encoding="utf-8")
    patch = args.patch_file.read_text(encoding="utf-8")
    full_prompt = f"{prompt}\n\n## Patch to Review\n\n```diff\n{patch}\n```"

    resolved_agent, requested_agent, selection_reason, active_agent, used_legacy_input = resolve_selection(args, config)

    if not resolved_agent:
        metadata = _build_metadata(
            requested_agent=requested_agent,
            resolved_agent=None,
            active_agent=active_agent,
            model=args.model,
            effort=args.effort,
            selection_reason="no valid review agent could be resolved",
            support_tier="unresolved",
            status="selection_failed",
            substantive_review=False,
            used_legacy_input=used_legacy_input,
        )
        parsed = _failure_result(
            summary="Cross-review could not resolve a reviewer agent.",
            metadata=metadata,
            issue="Specify --agent explicitly or configure CROSSREVIEW_AGENT / CROSSREVIEW_HARNESS with an installed supported reviewer.",
        )
    else:
        spec = AGENT_SPECS.get(resolved_agent)
        if spec is None and resolved_agent in KNOWN_UNSUPPORTED:
            metadata = _build_metadata(
                requested_agent=requested_agent,
                resolved_agent=resolved_agent,
                active_agent=active_agent,
                model=args.model,
                effort=args.effort,
                selection_reason=selection_reason,
                support_tier=TIER_3,
                status="unsupported",
                substantive_review=False,
                used_legacy_input=used_legacy_input,
            )
            parsed = _failure_result(
                summary=f"Agent '{resolved_agent}' is known to Orca but not supported for cross-review.",
                metadata=metadata,
                issue=f"Agent '{resolved_agent}' has no verified cross-review adapter. Choose one of: {', '.join(AUTO_SELECTION_ORDER + ['cursor-agent'])}.",
            )
        elif spec is None:
            metadata = _build_metadata(
                requested_agent=requested_agent,
                resolved_agent=resolved_agent,
                active_agent=active_agent,
                model=args.model,
                effort=args.effort,
                selection_reason=selection_reason,
                support_tier="unknown",
                status="unsupported",
                substantive_review=False,
                used_legacy_input=used_legacy_input,
            )
            parsed = _failure_result(
                summary=f"Agent '{resolved_agent}' is unknown to Orca cross-review.",
                metadata=metadata,
                issue=f"Unknown review agent '{resolved_agent}'.",
            )
        elif spec.invoke is None:
            metadata = _build_metadata(
                requested_agent=requested_agent,
                resolved_agent=resolved_agent,
                active_agent=active_agent,
                model=args.model,
                effort=args.effort,
                selection_reason=selection_reason,
                support_tier=spec.tier,
                status="unsupported",
                substantive_review=False,
                used_legacy_input=used_legacy_input,
            )
            parsed = _failure_result(
                summary=f"Agent '{resolved_agent}' is registered but cannot run cross-review yet.",
                metadata=metadata,
                issue=f"Agent '{resolved_agent}' does not have a verified review adapter.",
            )
        elif not spec.available(args):
            metadata = _build_metadata(
                requested_agent=requested_agent,
                resolved_agent=resolved_agent,
                active_agent=active_agent,
                model=args.model,
                effort=args.effort,
                selection_reason=selection_reason,
                support_tier=spec.tier,
                status="unavailable",
                substantive_review=False,
                used_legacy_input=used_legacy_input,
            )
            parsed = _failure_result(
                summary=f"Agent '{resolved_agent}' is configured for cross-review but is not available on this machine.",
                metadata=metadata,
                issue=f"Agent '{resolved_agent}' could not be resolved from the current environment.",
            )
        else:
            metadata = _build_metadata(
                requested_agent=requested_agent,
                resolved_agent=resolved_agent,
                active_agent=active_agent,
                model=args.model,
                effort=args.effort,
                selection_reason=selection_reason,
                support_tier=spec.tier,
                status="completed",
                substantive_review=True,
                used_legacy_input=used_legacy_input,
            )
            sys.stderr.write(f"Invoking {resolved_agent}")
            if args.model:
                sys.stderr.write(f" ({args.model})")
            sys.stderr.write("...\n")
            try:
                raw_result = spec.invoke(args, full_prompt)
                parsed = _merge_metadata(extract_json(raw_result), metadata)
                validation_errors = validate_output(parsed, args.schema_file)
                if validation_errors:
                    metadata["status"] = "schema_validation_failed"
                    metadata["substantive_review"] = False
                    parsed = _failure_result(
                        summary="Cross-review output failed schema validation.",
                        metadata=metadata,
                        issue="; ".join(validation_errors[:10]),
                    )
            except subprocess.TimeoutExpired:
                metadata["status"] = "timeout"
                metadata["substantive_review"] = False
                parsed = _failure_result(
                    summary=f"Cross-review timed out after {args.timeout}s.",
                    metadata=metadata,
                    issue=f"{resolved_agent} did not complete within {args.timeout}s.",
                )
            except FileNotFoundError:
                metadata["status"] = "unavailable"
                metadata["substantive_review"] = False
                parsed = _failure_result(
                    summary=f"Agent CLI '{resolved_agent}' was not found.",
                    metadata=metadata,
                    issue=f"Install or expose '{resolved_agent}' in PATH before running cross-review.",
                )
            except RuntimeError as exc:
                metadata["status"] = "runtime_error"
                metadata["substantive_review"] = False
                parsed = _failure_result(
                    summary=f"Agent '{resolved_agent}' failed during cross-review execution.",
                    metadata=metadata,
                    issue=str(exc),
                )

    output_json = json.dumps(parsed, indent=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_json, encoding="utf-8")
    print(output_json)


if __name__ == "__main__":
    main()
