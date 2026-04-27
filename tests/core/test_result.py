from __future__ import annotations

from orca.core.result import Err, Ok, Result
from orca.core.errors import Error, ErrorKind


def test_ok_carries_value():
    r: Result[int, Error] = Ok(42)
    assert r.ok is True
    assert r.value == 42


def test_err_carries_error():
    e = Error(kind=ErrorKind.INPUT_INVALID, message="bad input")
    r: Result[int, Error] = Err(e)
    assert r.ok is False
    assert r.error.kind == ErrorKind.INPUT_INVALID
    assert r.error.message == "bad input"


def test_ok_to_json():
    r: Result[dict, Error] = Ok({"foo": "bar"})
    payload = r.to_json(capability="test", version="0.1.0", duration_ms=12)
    assert payload["ok"] is True
    assert payload["result"] == {"foo": "bar"}
    assert payload["metadata"] == {"capability": "test", "version": "0.1.0", "duration_ms": 12}
    assert "error" not in payload


def test_err_to_json():
    e = Error(kind=ErrorKind.TIMEOUT, message="slow", detail={"after_s": 30})
    r: Result[dict, Error] = Err(e)
    payload = r.to_json(capability="test", version="0.1.0", duration_ms=30000)
    assert payload["ok"] is False
    assert payload["error"] == {
        "kind": "timeout",
        "message": "slow",
        "detail": {"after_s": 30},
    }
    assert "result" not in payload


def test_error_kind_round_trip():
    for kind in ErrorKind:
        assert ErrorKind(kind.value) is kind


def test_error_default_detail_is_none():
    e = Error(kind=ErrorKind.INTERNAL, message="boom")
    payload = Err(e).to_json(capability="x", version="0", duration_ms=0)
    assert "detail" not in payload["error"]
