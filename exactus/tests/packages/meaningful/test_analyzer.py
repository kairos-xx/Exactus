# Copyright (c) 2026 João Lopes.
"""Behavioral tests for the single-file test-necessity classifier."""

from pathlib import Path
from textwrap import dedent

import pytest

from exactus.packages.meaningful.analyzer import (
    Classification,
    ClassificationJson,
    PythonTestNeedClassifier,
    UnitTestLevel,
)


def expect(*, condition: bool) -> None:
    """Fail when a test condition is false.

    Args:
        condition: Condition that must hold.

    Raises:
        AssertionError: If ``condition`` is false.

    """
    if not condition:
        raise AssertionError


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    [
        (
            "__init__.py",
            '"""Exports."""\nfrom pathlib import Path\n__all__ = ("Path",)\n',
            UnitTestLevel.TEST_0,
        ),
        (
            "__main__.py",
            (
                dedent(
                    text=(
                        '    """Entrypoint."""\n    from package import ru'
                        'n\n    \n    def main() -> None:\n        """Dele'
                        'gate."""\n        run()\n    \n    if __name__ =='
                        ' "__main__":\n        main()\n    '
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "delegate.py",
            (
                dedent(
                    text=(
                        '    """Delegate."""\n    from package import run'
                        "\n    \n    def execute(value: str) -> str:\n    "
                        '    """Delegate."""\n        return run(value)\n '
                        "   "
                    ),
                )
            ),
            UnitTestLevel.TEST_1,
        ),
        (
            "compute.py",
            (
                dedent(
                    text=(
                        '    """Compute."""\n    \n    def double(value: i'
                        'nt) -> int:\n        """Double."""\n        retur'
                        "n value * 2\n    "
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "io.py",
            (
                dedent(
                    text=(
                        '    """I/O."""\n    from pathlib import Path\n   '
                        ' \n    def load(path: Path) -> str:\n        """L'
                        'oad."""\n        return path.read_text(encoding="'
                        'utf-8")\n    '
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "branch.py",
            (
                dedent(
                    text=(
                        '    """Branch."""\n    \n    def clamp(value: int'
                        ') -> int:\n        """Clamp."""\n        if value'
                        " < 0:\n            return 0\n        if value > 1"
                        "00:\n            return 100\n        return value"
                        "\n    "
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "constants.py",
            (
                dedent(
                    text=(
                        '    """Constants."""\n    from typing import Fina'
                        "l\n    \n    NAMES: Final[frozenset[str]] = froze"
                        'nset({"a", "b"})\n    '
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "__main__.py",
            (
                dedent(
                    text=(
                        '    """Entrypoint."""\n    from package import cl'
                        'i\n    \n    def main() -> None:\n        """Dele'
                        'gate."""\n        raise SystemExit(cli())\n    \n'
                        '    if __name__ == "__main__":\n        main()\n '
                        "   "
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "__init__.py",
            (
                dedent(
                    text=(
                        '    """Init with behavior."""\n    \n    def norm'
                        'alize(value: int) -> int:\n        """Normalize."'
                        '""\n        if value < 0:\n            return 0\n'
                        "        return value\n    "
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "subprocess_import.py",
            (
                dedent(
                    text=(
                        '    """Subprocess."""\n    from subprocess import'
                        ' run\n    \n    def execute() -> None:\n        "'
                        '""Execute."""\n        run(args=("true",), check='
                        "True)\n    "
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "subprocess_alias.py",
            (
                dedent(
                    text=(
                        '    """Subprocess alias."""\n    import subproces'
                        "s as sp\n    \n    def execute() -> None:\n      "
                        '  """Execute."""\n        sp.run(args=("true",), '
                        "check=True)\n    "
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "ambient.py",
            (
                dedent(
                    text=(
                        '    """Ambient state."""\n    from os import envi'
                        'ron\n    \n    def token() -> str:\n        """Re'
                        'ad token."""\n        return environ["TOKEN"]\n  '
                        "  "
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "mutation.py",
            (
                dedent(
                    text=(
                        '    """Mutation."""\n    \n    def add(values: li'
                        'st[int], value: int) -> None:\n        """Add one'
                        ' value."""\n        values.append(value)\n    '
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "typing_only.py",
            (
                dedent(
                    text=(
                        '    """Typing only."""\n    from typing import TY'
                        "PE_CHECKING\n    \n    if TYPE_CHECKING:\n       "
                        " from package import Thing\n    "
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "model.py",
            (
                dedent(
                    text=(
                        '    """Model."""\n    from dataclasses import dat'
                        "aclass, field\n    \n    @dataclass(frozen=True, "
                        'slots=True)\n    class Model:\n        """Data mo'
                        'del."""\n        names: tuple[str, ...] = field(d'
                        "efault_factory=tuple)\n    "
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "stubs.py",
            (
                dedent(
                    text=(
                        '    """Stubs."""\n    \n    def first() -> None:'
                        '\n        """Stub."""\n        pass\n    \n    de'
                        'f second() -> None:\n        """Stub."""\n       '
                        " ...\n    "
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "complex.py",
            (
                dedent(
                    text=(
                        '    """Complex."""\n    \n    def choose(value: i'
                        'nt) -> int:\n        """Choose."""\n        if va'
                        "lue > 0:\n            if value > 1:\n            "
                        "    if value > 2:\n                    return val"
                        "ue * 2\n        if value < 0:\n            return"
                        " -value\n        return 0\n    "
                    ),
                )
            ),
            UnitTestLevel.TEST_3,
        ),
    ],
)
def test_classification_levels(
    *,
    tmp_path: Path,
    name: str,
    source: str,
    expected: UnitTestLevel,
) -> None:
    """Classify representative structural and behavioral source files.

    Args:
        tmp_path: Value supplied for ``tmp_path``.
        name: Value supplied for ``name``.
        source: Value supplied for ``source``.
        expected: Value supplied for ``expected``.

    """
    path: Path = tmp_path / name
    path.write_text(data=source, encoding="utf-8")
    expect(
        condition=PythonTestNeedClassifier(path=path).classify().level
        is expected,
    )


def test_metrics_json_and_render(*, tmp_path: Path) -> None:
    """Expose stable human and machine-readable reports.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    path: Path = tmp_path / "branch.py"
    path.write_text(
        data=(
            dedent(
                text=(
                    '    """Branch."""\n    \n    def choose(value: int) -'
                    '> int:\n        """Choose."""\n        if value:\n   '
                    "         return value + 1\n        return 0\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    result: Classification = PythonTestNeedClassifier(path=path).classify()
    payload: ClassificationJson = result.to_json()
    report: str = result.render()
    expect(condition=payload["level"] == "TEST-2")
    expect(condition=payload["metrics"]["branches"] == 1)
    expect(condition=payload["requires_branch_coverage"] is True)
    expect(condition="classification: TEST-2 (behavioral)" in report)
    expect(condition="branch coverage required: yes" in report)


def test_non_python_file_is_rejected(*, tmp_path: Path) -> None:
    """Reject paths without a Python suffix.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    path: Path = tmp_path / "module.txt"
    path.write_text(data="content", encoding="utf-8")
    with pytest.raises(
        expected_exception=ValueError,
        match=r"Expected a \.py file",
    ):
        PythonTestNeedClassifier(path=path)


def test_syntax_error_is_preserved(*, tmp_path: Path) -> None:
    """Surface Python syntax errors to callers.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    path: Path = tmp_path / "broken.py"
    path.write_text(data="def broken(:\n", encoding="utf-8")
    with pytest.raises(expected_exception=SyntaxError):
        PythonTestNeedClassifier(path=path)
