# Copyright (c) 2026
"""The kwargs-typehints analyzer on projects, flags and its artifacts."""

from __future__ import annotations

from ast import FunctionDef, parse, stmt
from importlib import import_module
from json import loads
from pathlib import Path
from sys import platform as host_platform
from sys import version_info
from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
    private_result,
)
from exactus.tools.common.catalog import Constants as _GroupFinalConstants
from exactus.tools.common.catalog import ToolSpec
from exactus.tools.kwargs_typehints import core as kwargs_core

if TYPE_CHECKING:
    from argparse import Namespace
    from types import ModuleType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]


def _module_name(*, name: str) -> str:
    """Return the catalog module of an analyzer.

    Args:
        name: Analyzer name with underscores.

    Returns:
        The dotted module name the catalog registers for the tool.

    Raises:
        ValueError: When the analyzer name is not in the catalog.

    """
    spec: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
        identifier=name,
    )
    if spec is None:
        msg: str = f"unknown analyzer {name}"
        raise ValueError(msg)
    return spec.module


def test_kwargs_strict_flag(sample_project: Path, tmp_path: Path) -> None:
    """Strict mode reports unannotatable bindings too.

    Args:
        sample_project: Generated sample project directory.
        tmp_path: Per-test temporary directory.

    """
    module: ModuleType = import_module(
        name=_module_name(name="kwargs_typehints"),
    )
    status: int = module.main(
        arguments=(
            str(object=sample_project),
            "-o",
            str(object=tmp_path / "out"),
            "--strict",
        ),
    )
    expect_in(member=status, container={0, 1})


@pytest.mark.parametrize("strict", [False, True])
def test_typevar_assignments_need_no_annotation(
    tmp_path: Path,
    *,
    strict: bool,
) -> None:
    """Exempt typing factories but retain ordinary assignment diagnostics.

    Args:
        tmp_path: Per-test temporary directory.
        strict: Whether unannotatable bindings are also checked.

    """
    path: Path = tmp_path / "types.py"
    _ = path.write_text(
        data=(
            dedent(
                text="""\
    from typing import TypeVar
    from typing_extensions import TypeVar as TV
    import typing as t
    T = TypeVar('T')
    U = TV('U', bound=str)
    V = t.TypeVar('V', int, str)
    ordinary = 1
    def local(TypeVar: object) -> None:
        not_a_typevar = TypeVar('X')
    """,
            )
        ),
        encoding="utf-8",
    )
    findings: tuple[kwargs_core.TypeHintFinding, ...] = (
        kwargs_core.TypeHintExactusor(path=path, strict=strict).exactus()
    )
    expect_equal(
        actual={item.name for item in findings},
        expected={"ordinary", "not_a_typevar"},
    )


def test_kwargs_exempts_positional_only_and_dynamic_callees(
    tmp_path: Path,
) -> None:
    """Dynamic and positional-only calls are counted apart, not unresolved.

    Args:
        tmp_path: Per-test temporary directory.

    """
    project: Path = tmp_path / "proj"
    project.mkdir()
    _ = (project / "pyproject.toml").write_text(
        data='[project]\nname = "proj"\n',
        encoding="utf-8",
    )
    _ = (project / "mod.py").write_text(
        data=(
            dedent(
                text="""\
    import pytest
    from importlib.resources import as_file


    @pytest.mark.parametrize("x", [1])
    def test_it(x: int) -> None:
        del x


    def use(widget: object, text: object) -> None:
        widget.setUrl("u")
        text.partition(":")
        as_file(text)
    """,
            )
        ),
        encoding="utf-8",
    )
    module: ModuleType = import_module(
        name=_module_name(name="kwargs_typehints"),
    )
    out: Path = tmp_path / "out"
    _ = module.main(arguments=(str(object=project), "-o", str(object=out)))
    payload: object = loads(
        s=(out / "result.json").read_text(encoding="utf-8"),
    )
    expect_equal(
        actual=dig(document=payload, path=("summary", "exempt_call_sites")),
        expected=3,
    )
    expect_equal(
        actual=dig(
            document=payload,
            path=("summary", "unresolved_call_sites"),
        ),
        expected=0,
    )
    expect_equal(
        actual=dig(document=payload, path=("comparison", "current_total")),
        expected=0,
    )
    rows: list[object] = dig_list(
        document=payload,
        path=("extension", "unresolved_callees"),
    )
    expect_equal(actual=rows, expected=[])


def test_kwargs_default_root_is_repository_root() -> None:
    """The kwargs core's ``--root`` default is the repository root."""
    root: Path = Constants.root
    options: Namespace = kwargs_core.parse_args(arguments=())
    expect_equal(actual=options.root, expected=root)
    expect_true(condition=(root / "exactus" / "tools").is_dir())


def test_import_roots_and_annotated_factories(tmp_path: Path) -> None:
    """Configured namespace roots and type aliases resolve real classes.

    Args:
        tmp_path: Isolated project containing explicit import roots.

    """
    scripts: Path = tmp_path / "scripts"
    scripts.mkdir()
    (tmp_path / "pyproject.toml").write_text(
        data='[tool.basedpyright]\nextraPaths = ["scripts"]\n',
    )
    module_path: Path = scripts / "factory.py"
    module_path.write_text(
        data=(
            dedent(
                text="""\
    class Stream:
        def read(self, size: int, /) -> bytes:
            return b'x' * size
    Factory: type[Stream] = Stream
    """,
            )
        ),
    )
    names: list[str] = kwargs_core.module_names(
        path=module_path,
        root=tmp_path,
    )
    expect_in(member="scripts.factory", container=names)
    expect_in(member="factory", container=names)
    project: kwargs_core.Project = kwargs_core.Project(root=tmp_path)
    resolved: kwargs_core.Resolved = project.resolve_dotted(
        dotted="factory.Factory",
    )
    expect_equal(actual=resolved.kind, expected="class")
    expect_true(condition=resolved.cls is not None)


def test_external_module_and_bound_classmethod_resolution(
    tmp_path: Path,
) -> None:
    """Imported submodules and class methods keep their actual receivers.

    Args:
        tmp_path: Isolated project used by the resolver.

    """
    project: kwargs_core.Project = kwargs_core.Project(root=tmp_path)
    module: kwargs_core.Resolved = project.resolve_external(
        dotted="xml.etree.ElementTree",
    )
    expect_equal(actual=module.kind, expected="external")
    expect_equal(actual=module.ext_kind, expected="module")
    source: Path = tmp_path / "probe.py"
    source.write_text(
        data=(
            dedent(
                text="""\
    from datetime import UTC, datetime
    def probe() -> None:
        datetime.now(UTC)
        int.from_bytes(b'x', 'big')
    """,
            )
        ),
    )
    indexed: kwargs_core.Project = kwargs_core.Project(root=tmp_path)
    exactusor: kwargs_core.CallExactusor = kwargs_core.CallExactusor(
        project=indexed,
        module=indexed.by_path[source],
    )
    exactusor.exactus()
    parameters: set[str] = {finding.param for finding in exactusor.findings}
    expect_in(member="tz", container=parameters)
    expect_false(condition="cls" in parameters)


def test_kwargs_writes_heuristics_under_artifacts(tmp_path: Path) -> None:
    """The type-fuzz heuristics land in ``ARTIFACTS/heuristics.json``.

    Args:
        tmp_path: Per-test temporary directory.

    """
    project: Path = tmp_path / "proj"
    project.mkdir()
    _ = (project / "mod.py").write_text(
        data="def one() -> int:\n    return 1\n",
        encoding="utf-8",
    )
    module: ModuleType = import_module(
        name=_module_name(name="kwargs_typehints"),
    )
    out: Path = tmp_path / "out"
    status: int = module.main(
        arguments=(str(object=project), "-o", str(object=out)),
    )
    expect_equal(actual=status, expected=0)
    expect_true(condition=(out / "ARTIFACTS" / "heuristics.json").is_file())
    expect_equal(
        actual=sorted(path.name for path in out.iterdir()),
        expected=[
            "ARTIFACTS",
            "README.md",
            "result.json",
            "result.md",
            "result_web",
        ],
    )


def test_kwargs_auto_heals_safe_findings_and_converges(tmp_path: Path) -> None:
    """Safe kwargs/import findings are repaired before the final report.

    Args:
        tmp_path: Per-test temporary directory.

    """
    project: Path = tmp_path / "proj"
    project.mkdir()
    source: Path = project / "mod.py"
    source.write_text(
        data=(
            dedent(
                text="""\
    import pathlib

    Alias: type[pathlib.Path] = pathlib.Path

    def consume(value: int) -> None:
        del value

    # keep this comment and unicode: café
    consume(1)
    """,
            )
        ),
        encoding="utf-8",
    )
    module: ModuleType = import_module(
        name=_module_name(name="kwargs_typehints"),
    )
    out: Path = tmp_path / "out"
    status: int = module.main(
        arguments=(str(object=project), "-o", str(object=out)),
    )
    healed: str = source.read_text(encoding="utf-8")
    expect_equal(actual=status, expected=0)
    expect_in(member="from pathlib import Path", container=healed)
    expect_in(member="Alias: type[Path] = Path", container=healed)
    expect_in(member="consume(value=1)", container=healed)
    expect_in(member="# keep this comment and unicode: café", container=healed)
    payload: object = loads(
        s=(out / "result.json").read_text(encoding="utf-8"),
    )
    expect_equal(
        actual=dig(document=payload, path=("comparison", "current_total")),
        expected=0,
    )
    fixes: list[object] = dig_list(
        document=payload,
        path=("extension", "auto_fixes"),
    )
    expect_true(condition=bool(fixes))
    expect_true(
        condition=all(
            isinstance(item, dict)
            and cast(typ="dict[str, object]", val=item).get("status")
            == "fixed"
            for item in fixes
        ),
    )


def test_kwargs_dry_run_preserves_sources(tmp_path: Path) -> None:
    """Dry-run reports validated repairs without changing source.

    Args:
        tmp_path: Per-test temporary directory.

    """
    project: Path = tmp_path / "proj"
    project.mkdir()
    source: Path = project / "mod.py"
    original: str = (
        "def consume(value: int) -> None:\n    del value\n\nconsume(1)\n"
    )
    source.write_text(data=original, encoding="utf-8")
    module: ModuleType = import_module(
        name=_module_name(name="kwargs_typehints"),
    )
    out: Path = tmp_path / "out"
    status: int = module.main(
        arguments=(str(object=project), "-o", str(object=out), "--dry-run"),
    )
    expect_equal(actual=status, expected=1)
    expect_equal(actual=source.read_text(encoding="utf-8"), expected=original)
    payload: object = loads(
        s=(out / "result.json").read_text(encoding="utf-8"),
    )
    fixes: list[object] = dig_list(
        document=payload,
        path=("extension", "auto_fixes"),
    )
    expect_true(condition=bool(fixes))
    expect_true(
        condition=all(
            isinstance(item, dict)
            and cast(typ="dict[str, object]", val=item).get("status")
            == "would-fix"
            for item in fixes
        ),
    )


def test_kwargs_pyproject_dry_reports_without_writing(tmp_path: Path) -> None:
    """Tool-local pyproject dry mode validates repairs without writing.

    Args:
        tmp_path: Per-test temporary directory.

    """
    project: Path = tmp_path / "proj"
    project.mkdir()
    source: Path = project / "mod.py"
    original: str = (
        "def consume(value: int) -> None:\n    del value\n\nconsume(1)\n"
    )
    source.write_text(data=original, encoding="utf-8")
    (project / "pyproject.toml").write_text(
        data=(
            dedent(
                text="""\
    [tool.exactus]
    root = true

    [tool.exactus.kwargs_typehints]
    dry = true
    """,
            )
        ),
        encoding="utf-8",
    )
    module: ModuleType = import_module(
        name=_module_name(name="kwargs_typehints"),
    )
    out: Path = tmp_path / "out"
    status: int = module.main(
        arguments=(str(object=project), "-o", str(object=out)),
    )
    expect_equal(actual=status, expected=1)
    expect_equal(actual=source.read_text(encoding="utf-8"), expected=original)
    payload: object = loads(
        s=(out / "result.json").read_text(encoding="utf-8"),
    )
    fixes: list[object] = dig_list(
        document=payload,
        path=("extension", "auto_fixes"),
    )
    expect_true(condition=bool(fixes))
    expect_true(
        condition=all(
            isinstance(item, dict)
            and cast(typ="dict[str, object]", val=item).get("status")
            == "would-fix"
            for item in fixes
        ),
    )


def test_bare_imports_require_only_attribute_access(tmp_path: Path) -> None:
    """Only module attribute access requires an explicit from-import.

    Args:
        tmp_path: Per-test temporary directory.

    """
    value_only: Path = tmp_path / "value.py"
    _ = value_only.write_text(
        data=(
            dedent(
                text="""\
    import sys

    monkeypatch.setattr(target=sys, name="argv", value=["x"])
    """,
            )
        ),
        encoding="utf-8",
    )
    both: Path = tmp_path / "both.py"
    _ = both.write_text(
        data=(
            dedent(
                text="""\
    import sys

    monkeypatch.setattr(target=sys, name="argv", value=["x"])
    first: str = sys.argv[0]
    """,
            )
        ),
        encoding="utf-8",
    )
    allowed: frozenset[str] = frozenset()
    value_findings: tuple[kwargs_core.BareImportFinding, ...] = (
        kwargs_core.BareImportExactusor(
            path=value_only,
            allowed=allowed,
        ).exactus()
    )
    expect_equal(actual=len(value_findings), expected=0)
    both_findings: tuple[kwargs_core.BareImportFinding, ...] = (
        kwargs_core.BareImportExactusor(path=both, allowed=allowed).exactus()
    )
    expect_equal(actual=len(both_findings), expected=1)
    finding: kwargs_core.BareImportFinding = both_findings[0]
    expect_true(condition=finding.safe)
    expect_in(
        member="import sys\nfrom sys import argv",
        container=finding.suggestion,
    )


def test_bare_import_heal_keeps_module_value_uses(tmp_path: Path) -> None:
    """Auto-heal keeps a bare import required by module value uses.

    Args:
        tmp_path: Per-test temporary directory.

    """
    project: Path = tmp_path / "proj"
    project.mkdir()
    source: Path = project / "mod.py"
    source.write_text(
        data=(
            dedent(
                text="""\
    import sys

    def apply() -> None:
        patch(target=sys, name="argv", value=["x"])

    first: str = sys.argv[0]
    """,
            )
        ),
        encoding="utf-8",
    )
    module: ModuleType = import_module(
        name=_module_name(name="kwargs_typehints"),
    )
    out: Path = tmp_path / "out"
    _ = module.main(arguments=(str(object=project), "-o", str(object=out)))
    healed: str = source.read_text(encoding="utf-8")
    expect_in(member="import sys\nfrom sys import argv", container=healed)
    expect_in(
        member='patch(target=sys, name="argv", value=["x"])',
        container=healed,
    )
    expect_in(member="first: str = argv[0]", container=healed)


def _fake_interpreter(*, root: Path, answer: str, status: int = 0) -> Path:
    """Install a project interpreter that answers the version probe.

    Args:
        root: Project root receiving ``.venv/bin/python``.
        answer: Text the fake interpreter prints.
        status: Exit status the fake interpreter returns.

    Returns:
        Path of the executable stand-in.

    """
    interpreter: Path = root / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    _ = interpreter.write_text(
        data=f"#!/bin/sh\nprintf '%s\\n' '{answer}'\nexit {status}\n",
        encoding="utf-8",
    )
    interpreter.chmod(mode=0o755)
    return interpreter


def _target(*, version: tuple[int, int]) -> kwargs_core.TargetPython:
    """Build interpreter facts for one Python release.

    Args:
        version: ``(major, minor)`` of the simulated interpreter.

    Returns:
        Facts with a final release and a linux platform.

    """
    return kwargs_core.TargetPython(
        executable="python",
        version_info=(*version, 0, "final", 0),
        platform="linux",
    )


def test_stub_guards_are_decided_by_the_target_interpreter() -> None:
    """Version and platform guards follow the target, not the host."""
    stub: str = dedent(
        text="""\
    import sys
    if sys.version_info >= (3, 14):
        def pointer(cls: int) -> None: ...
    else:
        def pointer(type: int, /) -> None: ...
    if sys.platform == 'win32':
        def windows_only() -> None: ...
    """,
    )
    names: dict[tuple[int, int], list[str]] = {}
    version: tuple[int, int]
    for version in ((3, 13), (3, 14)):
        live: list[stmt] = kwargs_core.live_stub_statements(
            body=parse(source=stub).body,
            target=_target(version=version),
        )
        names[version] = [
            f"{item.name}:{[*item.args.posonlyargs, *item.args.args][0].arg}"
            for item in live
            if isinstance(item, FunctionDef)
        ]
    expect_equal(actual=names[(3, 13)], expected=["pointer:type"])
    expect_equal(actual=names[(3, 14)], expected=["pointer:cls"])


@pytest.mark.skipif(
    condition=host_platform == "win32",
    reason="the stand-in interpreter is a POSIX shell script",
)
def test_target_python_reads_the_project_interpreter(tmp_path: Path) -> None:
    """The project's own interpreter supplies the inference facts.

    Args:
        tmp_path: Isolated project root.

    """
    _ = _fake_interpreter(
        root=tmp_path,
        answer='[[3, 12, 1, "final", 0], "linux"]',
    )
    target: kwargs_core.TargetPython = kwargs_core.target_python(root=tmp_path)
    expect_equal(actual=target.release, expected="3.12.1")
    expect_equal(actual=target.platform, expected="linux")
    expect_true(condition=target.executable.endswith("python"))


@pytest.mark.skipif(
    condition=host_platform == "win32",
    reason="the stand-in interpreter is a POSIX shell script",
)
def test_target_python_falls_back_to_the_running_interpreter(
    tmp_path: Path,
) -> None:
    """Missing, failing, or garbled interpreters use the running one.

    Args:
        tmp_path: Isolated project roots.

    """
    running: kwargs_core.TargetPython = kwargs_core.current_python()
    expect_equal(
        actual=kwargs_core.target_python(root=tmp_path),
        expected=running,
    )
    failing: Path = tmp_path / "failing"
    _ = _fake_interpreter(root=failing, answer="[]", status=1)
    expect_equal(
        actual=kwargs_core.target_python(root=failing),
        expected=running,
    )
    garbled: Path = tmp_path / "garbled"
    _ = _fake_interpreter(root=garbled, answer="not json")
    expect_equal(
        actual=kwargs_core.target_python(root=garbled),
        expected=running,
    )


@pytest.mark.skipif(
    condition=host_platform == "win32",
    reason="the stand-in interpreter is a POSIX shell script",
)
def test_target_python_uses_the_configured_interpreter(tmp_path: Path) -> None:
    """An explicit ``python`` setting wins over the project venv.

    Args:
        tmp_path: Isolated project root.

    """
    configured: Path = tmp_path / "standalone-python"
    _ = configured.write_text(
        data=(
            dedent(
                text="""\
    #!/bin/sh
    printf '%s\\n' '[[3, 11, 4, "final", 0], "plan9"]'
    """,
            )
        ),
        encoding="utf-8",
    )
    configured.chmod(mode=0o755)
    _ = _fake_interpreter(
        root=tmp_path,
        answer='[[3, 99, 0, "final", 0], "linux"]',
    )
    target: kwargs_core.TargetPython = kwargs_core.target_python(
        root=tmp_path,
        python=str(object=configured),
    )
    expect_equal(actual=target.release, expected="3.11.4")
    expect_equal(actual=target.platform, expected="plan9")


@pytest.mark.skipif(
    condition=host_platform == "win32",
    reason="the stand-in interpreter is a POSIX shell script",
)
def test_target_python_trusts_the_project_environment(tmp_path: Path) -> None:
    """A project ``.venv`` is used even outside ``requires-python``.

    Args:
        tmp_path: Isolated project root.

    """
    _ = _fake_interpreter(
        root=tmp_path,
        answer='[[3, 12, 1, "final", 0], "linux"]',
    )
    _ = (tmp_path / "pyproject.toml").write_text(
        data='[project]\nrequires-python = ">=99.0"\n',
        encoding="utf-8",
    )
    target: kwargs_core.TargetPython = kwargs_core.target_python(root=tmp_path)
    expect_equal(actual=target.release, expected="3.12.1")
    expect_equal(actual=target.platform, expected="linux")


@pytest.mark.skipif(
    condition=host_platform == "win32",
    reason="the stand-in interpreter is a POSIX shell script",
)
def test_target_python_accepts_an_environment_directory(
    tmp_path: Path,
) -> None:
    """The ``python`` setting may name a virtual-environment directory.

    Args:
        tmp_path: Isolated project root.

    """
    interpreter: Path = tmp_path / "environment" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    _ = interpreter.write_text(
        data=(
            dedent(
                text="""\
    #!/bin/sh
    printf '%s\\n' '[[3, 10, 2, "final", 0], "linux"]'
    """,
            )
        ),
        encoding="utf-8",
    )
    interpreter.chmod(mode=0o755)
    target: kwargs_core.TargetPython = kwargs_core.target_python(
        root=tmp_path,
        python=str(object=interpreter.parent.parent),
    )
    expect_equal(actual=target.release, expected="3.10.2")
    expect_equal(actual=target.platform, expected="linux")


def test_requires_python_reads_the_declared_specifier(tmp_path: Path) -> None:
    """``requires-python`` is read from the project table only.

    Args:
        tmp_path: Isolated project root.

    """
    expect_equal(
        actual=private_result(
            owner=kwargs_core,
            name="_requires_python",
            kind=str,
            root=tmp_path,
        ),
        expected="",
    )
    _ = (tmp_path / "pyproject.toml").write_text(
        data='[project]\nrequires-python = ">=3.13"\n',
        encoding="utf-8",
    )
    expect_equal(
        actual=private_result(
            owner=kwargs_core,
            name="_requires_python",
            kind=str,
            root=tmp_path,
        ),
        expected=">=3.13",
    )


def test_spec_clauses_and_version_ok_cover_common_operators() -> None:
    """Specifier parsing and evaluation cover the declared operators."""
    clauses: list[tuple[str, tuple[int, ...]]] = list(
        cast(
            typ="tuple[tuple[str, tuple[int, ...]], ...]",
            val=private_result(
                owner=kwargs_core,
                name="_spec_clauses",
                kind=tuple,
                specifier=">=3.13, <4, !=3.14.1",
            ),
        ),
    )
    expect_equal(actual=len(clauses), expected=3)
    expect_true(
        condition=private_result(
            owner=kwargs_core,
            name="_version_ok",
            kind=bool,
            version=(3, 13, 0),
            clauses=clauses,
        ),
    )
    expect_false(
        condition=private_result(
            owner=kwargs_core,
            name="_version_ok",
            kind=bool,
            version=(3, 14, 1),
            clauses=clauses,
        ),
    )
    expect_false(
        condition=private_result(
            owner=kwargs_core,
            name="_version_ok",
            kind=bool,
            version=(4, 0, 0),
            clauses=clauses,
        ),
    )
    compatible: list[tuple[str, tuple[int, ...]]] = list(
        cast(
            typ="tuple[tuple[str, tuple[int, ...]], ...]",
            val=private_result(
                owner=kwargs_core,
                name="_spec_clauses",
                kind=tuple,
                specifier="~=3.13",
            ),
        ),
    )
    expect_true(
        condition=private_result(
            owner=kwargs_core,
            name="_version_ok",
            kind=bool,
            version=(3, 13, 9),
            clauses=compatible,
        ),
    )
    expect_false(
        condition=private_result(
            owner=kwargs_core,
            name="_version_ok",
            kind=bool,
            version=(4, 0, 0),
            clauses=compatible,
        ),
    )
    expect_equal(
        actual=cast(
            typ="tuple[tuple[str, tuple[int, ...]], ...]",
            val=private_result(
                owner=kwargs_core,
                name="_spec_clauses",
                kind=tuple,
                specifier="not-a-version",
            ),
        ),
        expected=(),
    )


@pytest.mark.skipif(
    condition=host_platform == "win32",
    reason="the stand-in interpreter is a POSIX shell script",
)
def test_pointer_keywords_follow_the_project_python(tmp_path: Path) -> None:
    """``ctypes.POINTER`` is keyword-capable only where the project says so.

    Python 3.13 declares ``POINTER(type, /)``; 3.14 declares
    ``POINTER(cls)``. A project on 3.13 must never be told to write
    ``cls=``, whichever Python runs the analyzer.

    Args:
        tmp_path: Isolated project roots, one per simulated interpreter.

    """
    reported: dict[str, list[str]] = {}
    release: str
    for release in ("13", "14"):
        root: Path = tmp_path / release
        root.mkdir()
        _ = _fake_interpreter(
            root=root,
            answer=f'[[3, {release}, 0, "final", 0], "linux"]',
        )
        source: Path = root / "probe.py"
        _ = source.write_text(
            data=(
                dedent(
                    text="""\
    from ctypes import POINTER, c_char, wintypes

    pointer_type = POINTER(c_char)
    dword_pointer = POINTER(wintypes.DWORD)
    """,
                )
            ),
            encoding="utf-8",
        )
        project: kwargs_core.Project = kwargs_core.Project(root=root)
        exactusor: kwargs_core.CallExactusor = kwargs_core.CallExactusor(
            project=project,
            module=project.by_path[source],
        )
        exactusor.exactus()
        reported[release] = [finding.param for finding in exactusor.findings]
    expect_equal(actual=reported["13"], expected=[])
    expect_equal(actual=reported["14"], expected=["cls", "cls"])


@pytest.mark.skipif(
    condition=host_platform == "win32",
    reason="the venv interpreter is linked as on POSIX",
)
def test_pointer_keywords_hold_on_a_real_python_313(tmp_path: Path) -> None:
    """A real 3.13 project interpreter never yields a ``cls`` finding.

    Args:
        tmp_path: Isolated project root holding a ``.venv`` link.

    """
    real: Path = Path(__file__).resolve().parents[4] / ".venv/bin/python"
    if not real.is_file() or tuple(version_info[:2]) != (3, 13):
        pytest.skip(reason="needs the repository's Python 3.13 .venv")
    link: Path = tmp_path / ".venv/bin/python"
    link.parent.mkdir(parents=True)
    link.symlink_to(target=real)
    source: Path = tmp_path / "probe.py"
    _ = source.write_text(
        data=(
            dedent(
                text="""\
    from ctypes import POINTER, wintypes

    dword_pointer = POINTER(wintypes.DWORD)
    """,
            )
        ),
        encoding="utf-8",
    )
    project: kwargs_core.Project = kwargs_core.Project(root=tmp_path)
    exactusor: kwargs_core.CallExactusor = kwargs_core.CallExactusor(
        project=project,
        module=project.by_path[source],
    )
    exactusor.exactus()
    expect_equal(
        actual=kwargs_core.target_python(root=tmp_path).version_info[:2],
        expected=(3, 13),
    )
    expect_equal(actual=[f.param for f in exactusor.findings], expected=[])


def test_python_option_is_part_of_the_cli_grammar() -> None:
    """The shared grammar (help, completion) lists ``--python``."""
    grammar: ModuleType = import_module(
        name="exactus.tools.kwargs_typehints.arguments",
    )
    options: Namespace = grammar.create_parser().parse_args(
        args=["--python", ".venv"],
    )
    expect_equal(actual=options.python, expected=".venv")
    expect_equal(
        actual=grammar.create_parser().parse_args(args=[]).python,
        expected=None,
    )


def test_python_option_reaches_the_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--python`` is forwarded to the engine, and omitted when unset.

    Args:
        tmp_path: Isolated project root.
        monkeypatch: Replaces the engine entry point to capture its input.

    """
    entry: ModuleType = import_module(
        name="exactus.tools.kwargs_typehints.main",
    )
    seen: list[tuple[str, ...]] = []

    def capture(*, arguments: tuple[str, ...], **_: object) -> int:
        """Record the engine arguments instead of analyzing.

        Args:
            arguments: Arguments the tool would hand to the engine.
            **_: Remaining engine keywords, unused.

        Returns:
            Zero, as a successful run.

        """
        seen.append(arguments)
        return 0

    monkeypatch.setattr(target=entry, name="core_main", value=capture)
    root: str = str(object=tmp_path)
    for extra in ((), ("--python", ".venv")):
        expect_equal(
            actual=entry.main(
                arguments=(root, "-o", str(object=tmp_path / "out"), *extra),
            ),
            expected=0,
        )
    expect_true(condition="--python" not in seen[0])
    forwarded: tuple[str, ...] = seen[1]
    expect_equal(
        actual=forwarded[forwarded.index("--python") + 1],
        expected=".venv",
    )
