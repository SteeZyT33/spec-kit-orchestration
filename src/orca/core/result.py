from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeVar, Union

from orca.core.errors import Error

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
    ok: Literal[True] = True

    def to_json(self, *, capability: str, version: str, duration_ms: float) -> dict[str, Any]:
        return {
            "ok": True,
            "result": self.value,
            "metadata": {
                "capability": capability,
                "version": version,
                "duration_ms": duration_ms,
            },
        }


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E
    ok: Literal[False] = False

    def to_json(self, *, capability: str, version: str, duration_ms: float) -> dict[str, Any]:
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
