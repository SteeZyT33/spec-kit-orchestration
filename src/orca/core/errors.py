from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorKind(str, Enum):
    INPUT_INVALID = "input_invalid"
    BACKEND_FAILURE = "backend_failure"
    TIMEOUT = "timeout"
    INTERNAL = "internal"


@dataclass(frozen=True)
class Error:
    kind: ErrorKind
    message: str
    detail: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind.value, "message": self.message}
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload
