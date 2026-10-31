# Copyright (c) 2026 Project contributors
"""Protect externally inherited instance methods from binding changes."""

from ast import Module, parse
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, cast

from exactus.tests.common.support import expect_equal, private_call
from exactus.tools.lints.core import LintExactus

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


def test_external_override_keeps_instance_binding() -> None:
    """Retain explicit base contracts while diagnosing ordinary helpers."""
    tree: Module = parse(
        source=dedent(
            text=(
                "    from http.server import BaseHTTPRequestHandler\n    f"
                "rom typing import override\n    class Handler(BaseHTTPReq"
                "uestHandler):\n        @override\n        def log_message"
                "(self, format, *args):\n            pass\n        def hel"
                "per(self):\n            return 1\n    "
            ),
        ),
    )
    findings: list[JsonValue]
    findings = cast(
        typ="list[JsonValue]",
        val=private_call(
            owner=LintExactus,
            name="_method_kind_findings",
            file=Path("handler.py"),
            tree=tree,
        ),
    )
    expect_equal(actual=len(findings), expected=1)
    expect_equal(
        actual=cast(typ="dict[str, JsonValue]", val=findings[0])["rule"],
        expected="PY005",
    )
