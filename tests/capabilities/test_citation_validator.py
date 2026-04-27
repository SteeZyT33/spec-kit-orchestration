from __future__ import annotations

import json
from pathlib import Path

import pytest

from orca.core.errors import ErrorKind
from orca.capabilities.citation_validator import (
    CitationValidatorInput,
    citation_validator,
)


def test_well_cited_text_passes(tmp_path):
    ref = tmp_path / "evidence.md"
    ref.write_text("# Evidence\n")
    text = "Results show 42% improvement [evidence]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert result.value["uncited_claims"] == []
    assert result.value["broken_refs"] == []
    assert result.value["citation_coverage"] == 1.0


def test_uncited_claim_detected(tmp_path):
    ref = tmp_path / "evidence.md"
    ref.write_text("# Evidence\n")
    text = "Results show 42% improvement."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert len(result.value["uncited_claims"]) == 1
    assert result.value["citation_coverage"] < 1.0


def test_broken_ref_detected(tmp_path):
    ref = tmp_path / "evidence.md"
    ref.write_text("# Evidence\n")
    text = "Results show 42% improvement [missing-ref]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert len(result.value["broken_refs"]) == 1
    assert result.value["broken_refs"][0]["ref"] == "missing-ref"


def test_lenient_mode_skips_non_numerical(tmp_path):
    ref = tmp_path / "evidence.md"
    ref.write_text("x")
    text = "The system shows good performance."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="lenient",
    ))
    assert result.ok
    assert result.value["uncited_claims"] == []
    # Zero assertions in lenient mode -> coverage is 1.0
    assert result.value["citation_coverage"] == 1.0


def test_content_path_loads_file(tmp_path):
    ref = tmp_path / "evidence.md"
    ref.write_text("x")
    content = tmp_path / "synthesis.md"
    content.write_text("Results show 42% improvement [evidence].")
    result = citation_validator(CitationValidatorInput(
        content_path=str(content),
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert result.value["citation_coverage"] == 1.0


def test_neither_content_nor_path_invalid():
    result = citation_validator(CitationValidatorInput(reference_set=[]))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID
    assert "content_text" in result.error.message or "content_path" in result.error.message


def test_both_content_and_path_invalid(tmp_path):
    """Mutual exclusion: capability rejects setting both inline text and a path."""
    f = tmp_path / "x.md"
    f.write_text("hi")
    result = citation_validator(CitationValidatorInput(
        content_text="x",
        content_path=str(f),
        reference_set=[],
    ))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_invalid_mode_returns_input_invalid():
    result = citation_validator(CitationValidatorInput(
        content_text="hi",
        mode="aggressive",
    ))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_missing_content_path_returns_input_invalid(tmp_path):
    result = citation_validator(CitationValidatorInput(
        content_path=str(tmp_path / "nope.md"),
        reference_set=[],
    ))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID
    assert "does not exist" in result.error.message


def test_well_supported_claims_listed(tmp_path):
    ref = tmp_path / "evidence.md"
    ref.write_text("x")
    text = "The data shows 75% completion [evidence]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert len(result.value["well_supported_claims"]) == 1
    assert result.value["well_supported_claims"][0]["text"].startswith("The data")


def test_ref_resolves_by_basename(tmp_path):
    """Ref name 'evidence' should resolve to ./evidence.md by stem match."""
    ref = tmp_path / "evidence.md"
    ref.write_text("x")
    text = "Results show 42% [evidence]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert result.value["broken_refs"] == []


def test_zero_assertions_yields_full_coverage(tmp_path):
    """No assertions means coverage is 1.0 (vacuous truth, not 0/0)."""
    text = "This is just a description."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    assert result.value["citation_coverage"] == 1.0


def test_partial_coverage_reflects_uncited_count(tmp_path):
    """4 assertions, 2 cited -> coverage 0.5."""
    ref = tmp_path / "e.md"
    ref.write_text("x")
    text = (
        "Results show 42% improvement [e].\n"
        "Tests prove 75% accuracy [e].\n"
        "The model demonstrates clear gains.\n"
        "Logs indicate 99% uptime.\n"
    )
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert len(result.value["uncited_claims"]) == 2
    assert result.value["citation_coverage"] == 0.5


def test_line_numbers_are_one_indexed(tmp_path):
    text = (
        "First line description.\n"
        "Results show 42% improvement.\n"
    )
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    assert result.value["uncited_claims"][0]["line"] == 2


def test_output_validates_against_schema(tmp_path):
    pytest.importorskip("jsonschema")
    import jsonschema
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "docs" / "capabilities" / "citation-validator" / "schema" / "output.json"
    )
    schema = json.loads(schema_path.read_text())

    ref = tmp_path / "evidence.md"
    ref.write_text("x")
    text = "Results show 42% improvement [evidence]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    jsonschema.validate(result.value, schema)
