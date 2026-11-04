# Copyright (c) 2026
"""Verify combined JavaScript preparation retains separate-stage findings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.lints.javascript_pipeline import scan_javascript_conventions
from exactus.tools.lints.js_delimiters import (
    DelimiterInput,
    DelimiterResult,
    scan_delimiters,
)
from exactus.tools.lints.js_function_blocks import (
    FunctionBlocksInput,
    FunctionBlocksResult,
    JavaScriptBlockAnalyzer,
    scan_function_blocks,
)

if TYPE_CHECKING:
    from pathlib import Path
    from typing import NoReturn

    import pytest


def test_combined_findings_and_repairs_match_separate_stages(
    tmp_path: Path,
) -> None:
    """The shared traversal preserves findings and the same fixed point.

    Args:
        tmp_path: Independent JavaScript project.

    """
    path: Path = tmp_path / "sample.js"
    path.write_text(
        data="""\
const plus = (value) => { return (value + 1); };
""",
        encoding="utf-8",
    )
    delimiters: DelimiterInput = DelimiterInput(
        root=tmp_path,
        files=(path,),
        fix=False,
    )
    notation: FunctionBlocksInput = FunctionBlocksInput(
        root=tmp_path,
        files=(path,),
        fix=False,
    )
    separate_delimiters: DelimiterResult = scan_delimiters(inputs=delimiters)
    separate_notation: FunctionBlocksResult = scan_function_blocks(
        inputs=notation,
    )
    merged_delimiters, merged_notation = scan_javascript_conventions(
        delimiters=delimiters,
        notation=notation,
    )
    expect_equal(
        actual=merged_delimiters.findings,
        expected=separate_delimiters.findings,
    )
    expect_equal(
        actual=merged_notation.findings,
        expected=separate_notation.findings,
    )
    fixed_delimiters, fixed_notation = scan_javascript_conventions(
        delimiters=DelimiterInput(root=tmp_path, files=(path,), fix=True),
        notation=FunctionBlocksInput(root=tmp_path, files=(path,), fix=True),
    )
    expect_true(
        condition=bool(fixed_delimiters.healed or fixed_notation.healed),
    )
    expect_false(
        condition=bool(fixed_delimiters.findings or fixed_notation.findings),
    )
    clean_delimiters, clean_notation = scan_javascript_conventions(
        delimiters=delimiters,
        notation=notation,
    )
    expect_false(
        condition=bool(clean_delimiters.findings or clean_notation.findings),
    )


def test_parser_resolution_failure_preserves_delimiter_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing notation parser preserves delimiter findings.

    Args:
        tmp_path: Independent project.
        monkeypatch: Controlled parser availability.

    """
    path: Path = tmp_path / "sample.js"
    path.write_text(
        data="""\
const value = ((1));
""",
        encoding="utf-8",
    )

    def unavailable(_self: JavaScriptBlockAnalyzer) -> NoReturn:
        """Model a missing local Espree installation.

        Args:
            _self: Analyzer instance.

        Raises:
            RuntimeError: The parser is unavailable.

        """
        msg: str = "Espree unavailable"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        target=JavaScriptBlockAnalyzer,
        name="resolve_espree",
        value=unavailable,
    )
    delimiters, notation = scan_javascript_conventions(
        delimiters=DelimiterInput(root=tmp_path, files=(path,), fix=False),
        notation=FunctionBlocksInput(root=tmp_path, files=(path,), fix=False),
    )
    expect_true(condition=bool(delimiters.findings))
    expect_equal(actual=notation.findings[0].rule, expected="JSN003")
