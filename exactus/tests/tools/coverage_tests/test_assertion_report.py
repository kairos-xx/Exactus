# Copyright (c) 2026
"""Report quoted assertion values as readable multiline evidence."""

from exactus.tests.common.support import expect_equal
from exactus.tools.coverage_tests.report import CoverageTestsReport


def test_missing_content_decodes_actual_markdown() -> None:
    """Decode a missing table row and the complete actual Markdown."""
    expected: str = "| docs | present | 170 | 1 | 1 | 0 |"
    actual: str = (
        "# README Exactus\n\n## Rules\n\n| RDM001 | Missing README.md | 0 |\n"
    )
    message: str = f"AssertionError: {expected!r} not found in {actual!r}"
    expect_equal(
        actual=CoverageTestsReport.assertion_diff(message=message),
        expected={"expected": expected, "actual": actual},
    )


def test_expected_actual_decodes_quotes_and_newlines() -> None:
    """Keep original quoting and whitespace in both assertion values."""
    expected: str = "# Title\n\nAn apostrophe: ' and a backslash: \\"
    actual: str = "# Other title\n"
    message: str = f"AssertionError: expected {expected!r}, got {actual!r}"
    expect_equal(
        actual=CoverageTestsReport.assertion_diff(message=message),
        expected={"expected": expected, "actual": actual},
    )


def test_unstructured_assertion_is_preserved() -> None:
    """Leave unrelated or truncated messages unparsed."""
    for message in (
        "AssertionError: expected true:",
        "AssertionError: 'a' not found in 'unterminated",
    ):
        expect_equal(
            actual=CoverageTestsReport.assertion_diff(message=message),
            expected=None,
        )
