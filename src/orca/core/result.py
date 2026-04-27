from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar, Union

from orca.core.errors import Error

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
    ok: bool = True

    def to_json(self, *, capability: str, version: str, duration_ms: int) -> dict[str, Any]:
        return {
            "ok": True,
            "result": _to_json_safe(self.value),
            "metadata": {
                "capability": capability,
                "version": version,
                "duration_ms": duration_ms,
            },
        }


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E
    ok: bool = False

    def to_json(self, *, capability: str, version: str, duration_ms: int) -> dict[str, Any]:
        err_payload = (
            self.error.to_json()
            if hasattr(self.error, "to_json")
            else {"message": str(self.error)}
        )
        return {
            "ok": False,
            "error": err_payload,
            "metadata": {
                "capability": capability,
                "version": version,
                "duration_ms": duration_ms,
            },
        }


Result = Union[Ok[T], Err[E]]


def _to_json_safe(value: Any) -> Any:
    if hasattr(value, "to_json") and callable(value.to_json):
        return value.to_json()
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    return value
