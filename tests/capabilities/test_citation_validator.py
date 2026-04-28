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


def test_zero_assertions_yields_full_coverage():
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


def test_line_numbers_are_one_indexed():
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


def test_pure_digit_refs_treated_as_footnote_markers():
    """[42], [1] etc. are numeric footnote markers, not file refs.
    They should not be flagged as broken_refs."""
    text = "Results show 42% improvement [42]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],  # no refs at all; [42] should not produce broken_ref
        mode="strict",
    ))
    assert result.ok
    assert result.value["broken_refs"] == []
    # Sentence is treated as cited (has a bracket marker)
    assert len(result.value["well_supported_claims"]) == 1


def test_sentence_split_handles_dr_abbreviation(tmp_path):
    """'Dr.' should not end a sentence; preserves the full assertion."""
    ref = tmp_path / "e.md"
    ref.write_text("x")
    text = "Dr. Smith shows 42% improvement [e]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    # Single assertion (the full sentence, not split at Dr.)
    assert result.value["citation_coverage"] == 1.0
    well = result.value["well_supported_claims"]
    assert len(well) == 1
    assert "Dr. Smith" in well[0]["text"]


def test_sentence_split_handles_eg_abbreviation():
    """'e.g.' should not end a sentence."""
    text = "See e.g. results that show 42% gain."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    # The sentence is one assertion (uncited); should not be split into "See e.g." + "results..."
    assert len(result.value["uncited_claims"]) == 1
    assert "e.g." in result.value["uncited_claims"][0]["text"]


# ---------------------------------------------------------------------------
# Markdown-aware preprocessing (Phase 3.2 backlog item 1)
# ---------------------------------------------------------------------------


def test_skips_lines_inside_fenced_code_blocks():
    """Lines inside ``` fences are not prose; assertions inside are ignored."""
    text = (
        "Intro paragraph.\n"
        "```bash\n"
        "Results show 50% improvement.\n"
        "```\n"
        "Closing paragraph.\n"
    )
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    # The fenced "Results show 50%" must NOT count as an uncited claim.
    assert result.value["uncited_claims"] == []
    assert result.value["citation_coverage"] == 1.0


def test_skips_lines_inside_tilde_fenced_blocks():
    """Lines inside ~~~ fences are skipped just like ``` fences."""
    text = (
        "Intro.\n"
        "~~~\n"
        "Results show 50% improvement.\n"
        "~~~\n"
    )
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    assert result.value["uncited_claims"] == []


def test_handles_unclosed_fence_at_eof():
    """An unclosed fence at EOF should not error; trailing lines are skipped."""
    text = (
        "Intro.\n"
        "```\n"
        "Results show 50% improvement.\n"
        "More code that never closes.\n"
    )
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    assert result.value["uncited_claims"] == []


def test_skips_markdown_table_rows():
    """Pipe-delimited table rows are not prose; their content is ignored."""
    text = (
        "| col1 | col2 |\n"
        "| --- | --- |\n"
        "| Results show 50% | yes |\n"
    )
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    assert result.value["uncited_claims"] == []


def test_skips_fr_scaffolding():
    """`**FR-001**: ...` is spec-kit scaffolding, not a prose claim."""
    text = "**FR-001**: System shows 50% improvement."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    assert result.value["uncited_claims"] == []


def test_skips_session_header():
    """`### Session 2026-04-27` lines are scaffolding."""
    text = "### Session 2026-04-27\nResults show 50%.\n"
    result = citation_validator(CitationValidatorInput(
        content_text="### Session 2026-04-27\n",
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    assert result.value["uncited_claims"] == []
    # Sanity: the second line in `text` would still count if we ran it - but
    # the test scope is just "session header skipped".
    del text


def test_skips_field_scaffolding():
    """`**Field**: shows 50%` is a scaffolding bullet, not a prose claim."""
    text = "**Field**: shows 50%"
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    assert result.value["uncited_claims"] == []


def test_skips_run_n_of_n_scaffolding():
    """`Run 1/3: shows 50%` is a verification-run tag, not a prose claim."""
    text = "Run 1/3: shows 50%"
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    assert result.value["uncited_claims"] == []


def test_custom_skip_pattern_extends_defaults():
    """Operator-supplied skip_patterns extend (not replace) the defaults."""
    text = (
        "**Custom**: shows 50% improvement.\n"
        "**FR-002**: shows 75% improvement.\n"
    )
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
        skip_patterns=[r"^\s*\*\*Custom\*\*"],
    ))
    assert result.ok
    # Both lines should be skipped: custom regex catches the first,
    # default FR-NNN pattern catches the second.
    assert result.value["uncited_claims"] == []


def test_invalid_custom_skip_pattern_returns_err():
    """A skip_pattern that fails re.compile returns INPUT_INVALID."""
    result = citation_validator(CitationValidatorInput(
        content_text="anything",
        reference_set=[],
        mode="strict",
        skip_patterns=["[unclosed"],
    ))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID
    assert "skip_pattern" in result.error.message


def test_non_reflike_bracket_not_flagged_as_broken():
    """`[all: 1440 1438 1445]` is prose, not a ref. Sentence is uncited."""
    text = "Results show 42% [all: 1440 1438 1445]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    # No broken ref - the bracket content does not look like a ref.
    assert result.value["broken_refs"] == []
    # The sentence has no real refs, so it counts as uncited.
    assert len(result.value["uncited_claims"]) == 1


def test_reflike_path_brackets_resolved(tmp_path):
    """`[evidence.md]` is path-shaped; resolves cleanly when in reference_set."""
    ref = tmp_path / "evidence.md"
    ref.write_text("x")
    text = "Results show 42% [evidence.md]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert result.value["broken_refs"] == []
    assert len(result.value["well_supported_claims"]) == 1


def test_anchor_brackets_treated_as_reflike():
    """`[#section]` is anchor-shaped; flagged as broken when not in refs."""
    text = "Results show 42% [#section]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[],
        mode="strict",
    ))
    assert result.ok
    # Anchor counts as a real ref candidate. With no refs configured, it
    # resolves as broken.
    assert len(result.value["broken_refs"]) == 1
    assert result.value["broken_refs"][0]["ref"] == "#section"


def test_explicit_ref_prefix(tmp_path):
    """`[ref:my-evidence]` resolves against a reference named `my-evidence`."""
    ref = tmp_path / "my-evidence.md"
    ref.write_text("x")
    text = "Results show 42% [ref:my-evidence]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    # The `ref:` prefix is stripped for resolution; `my-evidence` resolves
    # by stem match against `my-evidence.md`.
    assert result.value["broken_refs"] == []
    assert len(result.value["well_supported_claims"]) == 1


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
