# Copyright (c) 2026
"""LINTS includes the canonical engineering rules and their source evidence."""

from __future__ import annotations

from functools import partial
from json import loads
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import (
    dig,
    expect_equal,
    expect_in,
    expect_true,
)
from exactus.tools.common import execution
from exactus.tools.lints.compliance import (
    ComplianceInput,
    ComplianceResult,
    scan_compliance,
)
from exactus.tools.lints.core import LintExactus
from exactus.tools.lints.main import main

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.common.models import ToolRunResult


@final
class Constants:
    """Group module-level constants.

    Attributes:
        marker: Grouped module constant.

    """

    marker: Final[str] = "# " + "noqa"


@pytest.mark.parametrize(
    ("source", "rule"),
    [
        ("def (:\n", "CMP000"),
        ("import os " + Constants.marker + "\n", "CMP001"),
        ("from typing import Any\nx: Any = None\n", "CMP002"),
        ("def load(value: object) -> int:\n    return 0\n", "CMP003"),
    ],
)
def test_source_rules_preserve_findings(
    tmp_path: Path,
    source: str,
    rule: str,
) -> None:
    """Preserve syntax, suppression and annotation rules in the lint scanner.

    Args:
        tmp_path: Isolated project root.
        source: Source violating an engineering rule.
        rule: Expected rule identifier.

    """
    (tmp_path / "pyproject.toml").write_text(data="[tool.ruff]\n")
    (tmp_path / "app.py").write_text(data=source)
    result: ComplianceResult = scan_compliance(
        inputs=ComplianceInput(root=tmp_path, includes=(), excludes=()),
    )
    expect_in(
        container=[finding.rule for finding in result.findings],
        member=rule,
    )
    expect_equal(actual=result.files, expected=1)


@pytest.mark.parametrize(
    ("settings", "rule"),
    [
        ('[tool.ruff.lint]\nignore = ["F401"]\n', "CMP004"),
        ("[tool.basedpyright]\nreportUnusedImport = false\n", "CMP005"),
        (None, "CMP006"),
    ],
)
def test_configuration_rules_preserve_findings(
    tmp_path: Path,
    settings: str | None,
    rule: str,
) -> None:
    """Keep configuration bans and the missing configuration diagnostic.

    Args:
        tmp_path: Isolated project root.
        settings: Configuration, or None for a missing file.
        rule: Expected rule identifier.

    """
    if settings is not None:
        (tmp_path / "pyproject.toml").write_text(data=settings)
    result: ComplianceResult = scan_compliance(
        inputs=ComplianceInput(root=tmp_path, includes=(), excludes=()),
    )
    expect_in(
        container=[finding.rule for finding in result.findings],
        member=rule,
    )


def no_commands(
    cwd: Path,
    toolchain: Path | None,
) -> dict[str, tuple[str, ...] | None]:
    """Resolve no external tools for the built-in report integration test.

    Args:
        cwd: Project root, unused.
        toolchain: Optional toolchain, unused.

    Returns:
        Empty external command mapping.

    """
    _ = (cwd, toolchain)
    return dict.fromkeys(
        (
            "ruff",
            "basedpyright",
            "pyrefly",
            "eslint",
            "tsc",
            "stylelint",
            "htmlhint",
            "prettier",
        ),
    )


def test_engineering_findings_are_part_of_lints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run the lints entry point and retain rule counts, gating and excerpts.

    Args:
        tmp_path: Isolated project root.
        monkeypatch: Patch external command resolution.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text(data="[tool.ruff]\n")
    (root / "app.py").write_text(
        data='"""Application."""\nimport os ' + Constants.marker + "\n",
    )
    monkeypatch.setattr(
        target=LintExactus,
        name="_resolve_commands",
        value=staticmethod(no_commands),
    )
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    output: Path = tmp_path / "LINTS"
    result: ToolRunResult = execution.execute_exactus(
        analyzer="lints",
        title="Lints Exactus",
        main=partial(
            main,
            arguments=(
                str(object=root),
                "--dry",
                "--output-dir",
                str(object=output),
            ),
        ),
        output=output,
    )
    expect_equal(actual=result.status, expected="FAIL")
    data: dict[str, JsonValue] = loads(s=(output / "result.json").read_text())
    findings: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=data["findings"],
    )
    selected: list[dict[str, JsonValue]] = [
        finding for finding in findings if finding["rule"] == "CMP001"
    ]
    expect_equal(actual=len(selected), expected=1)
    expect_equal(actual=selected[0]["source"], expected="custom_compliance")
    expect_true(condition=selected[0]["blocking"] is True)
    expect_equal(
        actual=dig(document=selected[0], path=("excerpt", "context")),
        expected=3,
    )
    text: str = (output / "result.md").read_text()
    expect_in(container=text, member="CMP001 | Suppression marker")
    expect_in(container=text, member="custom_compliance")
    expect_true(condition=not (tmp_path / "COMPLIANCE").exists())
