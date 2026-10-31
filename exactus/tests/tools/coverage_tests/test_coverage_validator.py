# Copyright (c) 2026
"""Coverage evidence validation and per-file floors."""

from __future__ import annotations

from hashlib import sha256
from json import dumps
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_true,
    private_call,
)
from exactus.tools.coverage_tests import main as coverage_main
from exactus.tools.coverage_tests.core import CoverageRunError
from exactus.tools.coverage_tests.main import CoverageValidator, parse_args

if TYPE_CHECKING:
    from argparse import Namespace
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        coverage: Grouped module constant.

    """

    coverage: Final[dict[str, JsonValue]] = {
        "totals": {"percent_covered": 91.5},
        "files": {
            "src/core/a.py": {"summary": {"percent_covered": 95.0}},
            "src/core/b.py": {"summary": {"percent_covered": 55.0}},
            "src/other.py": {"summary": {"percent_covered": 10.0}},
        },
    }


def _evidence(
    directory: Path,
    *,
    coverage: dict[str, JsonValue] | None = None,
    overrides: dict[str, JsonValue] | None = None,
) -> Path:
    """Write a coverage evidence directory.

    Args:
        directory: Target directory.
        coverage: Coverage JSON payload.
        overrides: Completion marker overrides.

    Returns:
        The directory.

    """
    directory.mkdir(parents=True, exist_ok=True)
    body: bytes = dumps(obj=coverage or Constants.coverage).encode()
    (directory / "coverage.json").write_bytes(data=body)
    marker: dict[str, JsonValue] = {
        "coverage_file": "coverage.json",
        "returncode": 0,
        "completed": True,
        "coverage_sha256": sha256(data=body).hexdigest(),
        "tests_collected": 3,
        "tests_executed": 3,
    }
    marker.update(overrides or {})
    (directory / "completion.json").write_text(data=dumps(obj=marker))
    return directory


def test_valid_evidence(tmp_path: Path) -> None:
    """Complete matching evidence passes, flat or under ``ARTIFACTS``.

    Args:
        tmp_path: Per-test temporary directory.

    """
    result: dict[str, JsonValue] = CoverageValidator.validate(
        directory=_evidence(
            directory=tmp_path / "e",
            coverage=Constants.coverage,
        ),
        minimum_percent=80.0,
    )
    expect_equal(actual=result["status"], expected="PASS")
    root: Path
    evidence: Path
    for root, evidence in (
        (tmp_path / "n", tmp_path / "n" / "ARTIFACTS"),
        (tmp_path / "m", tmp_path / "m" / "ARTIFACTS" / "COVERAGE"),
    ):
        _ = _evidence(directory=evidence)
        expect_equal(
            actual=CoverageValidator.evidence(directory=root),
            expected=evidence,
        )
        expect_equal(
            actual=CoverageValidator.validate(
                directory=root,
                minimum_percent=50.0,
            )["percent"],
            expected=91.5,
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"returncode": 1}, "did not complete"),
        ({"completed": False}, "did not complete"),
        ({"js_tests_discovered": 2, "js_returncode": 3}, "javascript"),
        ({"coverage_sha256": "0"}, "hash"),
    ],
)
def test_invalid_evidence(
    overrides: dict[str, JsonValue],
    message: str,
    tmp_path: Path,
) -> None:
    """Failed runs, JS failures and tampered data are rejected.

    Args:
        overrides: Value for ``overrides``.
        message: Value for ``message``.
        tmp_path: Per-test temporary directory.

    """
    directory: Path = _evidence(directory=tmp_path / "e", overrides=overrides)
    with pytest.raises(expected_exception=ValueError, match=message):
        _ = CoverageValidator.validate(
            directory=directory,
            minimum_percent=1.0,
        )


def test_missing_files_rejected(tmp_path: Path) -> None:
    """A missing marker or data file means incomplete evidence.

    Args:
        tmp_path: Per-test temporary directory.

    """
    empty: Path = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(expected_exception=ValueError, match="incomplete"):
        _ = CoverageValidator.validate(directory=empty, minimum_percent=1.0)
    directory: Path = _evidence(directory=tmp_path / "e")
    (directory / "coverage.json").unlink()
    with pytest.raises(expected_exception=ValueError, match="incomplete"):
        _ = CoverageValidator.validate(
            directory=directory,
            minimum_percent=1.0,
        )


def test_floors(tmp_path: Path) -> None:
    """Total and critical-module floors are enforced.

    Args:
        tmp_path: Per-test temporary directory.

    """
    directory: Path = _evidence(directory=tmp_path / "e")
    with pytest.raises(expected_exception=ValueError, match="below required"):
        _ = CoverageValidator.validate(
            directory=directory,
            minimum_percent=99.0,
        )
    with pytest.raises(expected_exception=ValueError, match="control-plane"):
        _ = CoverageValidator.validate(
            directory=directory,
            minimum_percent=50.0,
            critical_patterns=("core/",),
            critical_minimum=80.0,
        )
    expect_equal(
        actual=CoverageValidator.critical_shortfalls(
            data=Constants.coverage,
            patterns=(),
            minimum_percent=80.0,
        ),
        expected=(),
    )
    shortfalls: tuple[tuple[str, float], ...] = (
        CoverageValidator.critical_shortfalls(
            data=Constants.coverage,
            patterns=("src",),
            minimum_percent=60.0,
        )
    )
    expect_equal(
        actual=[path for path, _ in shortfalls],
        expected=["src/other.py", "src/core/b.py"],
    )


def test_validate_writes_verdict(tmp_path: Path) -> None:
    """The verdict file records pass and failure reasons.

    Args:
        tmp_path: Per-test temporary directory.

    """
    good: Path = tmp_path / "good"
    _ = _evidence(directory=good / "ARTIFACTS" / "COVERAGE")
    options: Namespace = parse_args(arguments=("x", "--minimum", "50"))
    expect_equal(
        actual=private_call(
            owner=coverage_main,
            name="_validate",
            options=options,
            output_dir=good,
        ),
        expected=0,
    )
    expect_true(
        condition=(
            good / "ARTIFACTS" / "COVERAGE" / "validation.json"
        ).is_file(),
    )
    bad: Path = _evidence(
        directory=tmp_path / "bad",
        overrides={"returncode": 2},
    )
    expect_equal(
        actual=private_call(
            owner=coverage_main,
            name="_validate",
            options=options,
            output_dir=bad,
        ),
        expected=2,
    )


def test_fail_raises() -> None:
    """``_fail`` raises the coverage error type."""
    with pytest.raises(expected_exception=CoverageRunError):
        _ = private_call(owner=coverage_main, name="_fail", message="x")
