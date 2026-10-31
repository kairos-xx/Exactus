# Copyright (c) 2026
"""Diagnostic normalizers for every external tool's JSON output."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_true,
    private_call,
)
from exactus.tools.lints.core import LintExactus

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


def normalize(*, tool: str, payload: object) -> list[dict[str, JsonValue]]:
    """Run the lints core's private diagnostic normalizer.

    Args:
        tool: Producing tool name.
        payload: Native tool payload.

    Returns:
        The normalized diagnostics.

    """
    return cast(
        typ="list[dict[str, JsonValue]]",
        val=private_call(
            owner=LintExactus,
            name="_normalize",
            tool=tool,
            payload=payload,
        ),
    )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        ignored_notice: Grouped module constant.
        bad: Grouped module constant.

    """

    ignored_notice: Final[str] = (
        "File ignored because of a matching ignore pattern. x"
    )
    bad: Final[dict[str, list[object]]] = {
        "ruff": [
            {},
            [1],
            [{"location": 1}],
            [{"location": {}, "end_location": 2}],
        ],
        "ruff_docs": ["x"],
        "basedpyright": [
            [],
            {"generalDiagnostics": 1},
            {"generalDiagnostics": [1]},
            {"generalDiagnostics": [{}]},
            {"generalDiagnostics": [{"range": {"start": 1}}]},
        ],
        "pyrefly": [
            1,
            {"errors": 2},
            {"errors": [1]},
            {"errors": [{"range": {"start": 1}}]},
        ],
        "eslint": [{}, [1], [{"messages": 1}], [{"messages": [1]}]],
        "stylelint": [{}, [1], [{"warnings": 1}], [{"warnings": [1]}]],
        "htmlhint": [1, [1], [{"messages": 1}], [{"messages": [1]}]],
    }


@pytest.mark.parametrize(
    ("tool", "payload"),
    [
        (tool, bad)
        for tool, payloads in Constants.bad.items()
        for bad in payloads
    ],
)
def test_malformed_payloads_raise(tool: str, payload: object) -> None:
    """Unexpected shapes are rejected with ``TypeError``.

    Args:
        tool: Value for ``tool``.
        payload: Value for ``payload``.

    """
    with pytest.raises(expected_exception=TypeError):
        _ = normalize(tool=tool, payload=payload)


def test_valid_payloads() -> None:
    """Representative native payloads normalize to the shared schema."""
    ruff: list[dict[str, JsonValue]] = normalize(
        tool="ruff",
        payload=[
            {
                "filename": "a.py",
                "code": "E1",
                "message": "m",
                "location": {"row": 1, "column": 2},
            },
        ],
    )
    expect_equal(actual=ruff[0]["rule"], expected="E1")
    pyright: list[dict[str, JsonValue]] = normalize(
        tool="basedpyright",
        payload={
            "generalDiagnostics": [
                {
                    "file": "a.py",
                    "rule": "r",
                    "severity": "error",
                    "message": "m",
                    "range": {
                        "start": {"line": 0, "character": 1},
                        "end": {"line": 0, "character": 4},
                    },
                },
            ],
        },
    )
    expect_equal(actual=pyright[0]["severity"], expected="error")
    for payload in (
        {
            "errors": [
                {
                    "path": "a",
                    "name": "n",
                    "range": {"start": {"line": 1, "column": 2}},
                },
            ],
        },
        [
            {
                "file": "a",
                "code": "c",
                "location": {"line": 1, "character": 2},
                "severity": 2,
            },
        ],
        {"diagnostics": [{"message": "m"}]},
    ):
        expect_true(condition=bool(normalize(tool="pyrefly", payload=payload)))
    pyrefly: list[dict[str, JsonValue]] = normalize(
        tool="pyrefly",
        payload={
            "errors": [
                {
                    "line": 3,
                    "column": 5,
                    "stop_line": 3,
                    "stop_column": 19,
                    "path": "a.py",
                    "name": "unknown-name",
                    "concise_description": "Could not find name `x`",
                    "description": "Could not find name `x`",
                    "severity": "error",
                },
            ],
        },
    )
    expect_equal(actual=pyrefly[0]["line"], expected=3)
    expect_equal(actual=pyrefly[0]["column"], expected=5)
    expect_equal(actual=pyrefly[0]["end_line"], expected=3)
    expect_equal(actual=pyrefly[0]["end_column"], expected=19)
    expect_equal(actual=pyrefly[0]["file"], expected="a.py")
    expect_equal(actual=pyrefly[0]["rule"], expected="unknown-name")
    expect_equal(
        actual=pyrefly[0]["message"],
        expected="Could not find name `x`",
    )
    eslint: list[dict[str, JsonValue]] = normalize(
        tool="eslint",
        payload=[
            {
                "filePath": "a.js",
                "messages": [
                    {
                        "ruleId": "r",
                        "severity": 2,
                        "message": "m",
                        "line": 1,
                        "column": 1,
                        "endLine": 2,
                        "endColumn": 3,
                    },
                    {"ruleId": None, "message": Constants.ignored_notice},
                ],
            },
        ],
    )
    expect_equal(actual=len(eslint), expected=1)
    expect_true(
        condition=bool(
            normalize(
                tool="stylelint",
                payload=[
                    {
                        "source": "a.css",
                        "warnings": [
                            {
                                "rule": "r",
                                "text": "t",
                                "severity": "error",
                                "line": 1,
                                "column": 1,
                            },
                        ],
                    },
                ],
            ),
        ),
    )
    payloads: tuple[object, ...] = (
        [
            {
                "file": "a.html",
                "messages": [
                    {"ruleId": "r", "message": "m", "line": 1, "col": 2},
                ],
            },
        ],
        {
            "messages": [
                {
                    "filePath": "a.html",
                    "message": "single",
                    "rule": {"id": "x"},
                },
            ],
        },
        {"results": []},
    )
    for payload in payloads:
        _ = normalize(tool="htmlhint", payload=payload)
    expect_equal(
        actual=normalize(tool="unknown-tool", payload=[]),
        expected=[],
    )


def test_helper_conversions() -> None:
    """Severity labels and rule names normalize."""

    def severity(*, value: object) -> object:
        """Normalize one severity label.

        Args:
            value: Native severity value.

        Returns:
            The normalized label.

        """
        return private_call(owner=LintExactus, name="_severity", value=value)

    def rule_name(*, value: object) -> object:
        """Extract one rule identifier.

        Args:
            value: Native rule identifier or descriptor.

        Returns:
            The identifier text.

        """
        return private_call(owner=LintExactus, name="_rule_name", value=value)

    expect_equal(actual=severity(value="FATAL"), expected="error")
    expect_equal(actual=severity(value=1), expected="error")
    expect_equal(actual=severity(value="warn"), expected="warning")
    expect_equal(actual=severity(value="note"), expected="information")
    expect_equal(actual=severity(value="custom"), expected="custom")
    expect_equal(actual=severity(value=None), expected="warning")
    expect_equal(actual=rule_name(value={"name": "n"}), expected="n")
    expect_equal(actual=rule_name(value={"id": "i"}), expected="i")
    expect_equal(actual=rule_name(value=5), expected="5")
    expect_equal(
        actual=private_call(
            owner=LintExactus,
            name="_line_column",
            text="a\nbc",
            offset=3,
        ),
        expected=(2, 2),
    )
