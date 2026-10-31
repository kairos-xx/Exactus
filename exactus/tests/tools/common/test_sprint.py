# Copyright (c) 2026
"""Flushed printing helpers and the ``DEBUG.txt`` capture directives."""

from __future__ import annotations

from importlib import import_module
from io import StringIO
from pathlib import Path
from textwrap import dedent
from time import time
from typing import TYPE_CHECKING, Protocol, cast

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_in,
    expect_true,
    private_call,
    require,
)
from exactus.tools.common import sprint as sp

if TYPE_CHECKING:
    from types import ModuleType


class SelectorShape(Protocol):
    """Fields of a parsed ``include::``/``exclude::`` selector.

    Attributes:
        file: Selected file path.
        functions: Selected function names, or ``None`` for all.

    """

    file: str
    functions: tuple[str, ...] | None


class SpecShape(Protocol):
    """Fields of a resolved ``DEBUG.txt`` specification.

    Attributes:
        save: Whether capture output is saved.
        max_age: Retention in seconds, if limited.
        streams: Captured stream names.
        include: Include selectors.
        exclude: Exclude selectors.

    """

    save: bool
    max_age: float | None
    streams: tuple[str, ...]
    include: tuple[object, ...]
    exclude: tuple[object, ...]


class SiteShape(Protocol):
    """Fields of a captured call site.

    Attributes:
        relative: Path relative to the project.
        qualname: Qualified function name.

    """

    relative: str
    qualname: str


def _selector(*, entry: str) -> SelectorShape:
    """Parse one selector through the private parser.

    Args:
        entry: Selector text.

    Returns:
        The parsed selector.

    """
    return cast(
        typ="SelectorShape",
        val=private_call(owner=sp, name="_debug_selector", entry=entry),
    )


def _spec(*, marker: Path) -> SpecShape | None:
    """Resolve a marker file through the private resolver.

    Args:
        marker: ``DEBUG.txt`` path.

    Returns:
        The resolved specification, or ``None``.

    """
    return cast(
        typ="SpecShape | None",
        val=private_call(owner=sp, name="_debug_spec", marker=marker),
    )


class Tty(StringIO):
    """A string stream pretending to be a terminal."""

    def isatty(self) -> bool:
        """Report terminal attachment.

        Returns:
            Always true.

        """
        return not self.closed


@pytest.mark.parametrize(
    ("level", "prefix"),
    [("info", ""), ("success", "✓ "), ("warning", "! "), ("error", "✗ ")],
)
def test_levels_prefix_output(level: sp.PrintLevel, prefix: str) -> None:
    """Each severity level decorates non-empty output.

    Args:
        level: Value for ``level``.
        prefix: Value for ``prefix``.

    """
    out: StringIO = StringIO()
    sp.sprint("hi", file=out, style=sp.SprintStyle(level=level, save=False))
    expect_equal(actual=out.getvalue(), expected=f"{prefix}hi\n")


def test_color_follows_terminal_detection() -> None:
    """ANSI colors appear for terminals or when forced."""
    tty: Tty = Tty()
    sp.sprint("x", file=tty, style=sp.SprintStyle(level="error", save=False))
    expect_in(member="\033[31m", container=tty.getvalue())
    plain: StringIO = StringIO()
    sp.sprint(
        "x",
        file=plain,
        style=sp.SprintStyle(level="error", color=True, save=False),
    )
    expect_in(member="\033[31m", container=plain.getvalue())
    quiet: StringIO = StringIO()
    sp.sprint("", "", file=quiet, sep="", style=sp.SprintStyle(save=False))
    expect_equal(actual=quiet.getvalue(), expected="\n")


def test_default_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    """Warnings and errors go to stderr, info to stdout.

    Args:
        monkeypatch: Pytest patching helper.

    """
    out, err = StringIO(), StringIO()
    monkeypatch.setattr(target=sp, name="stdout", value=out)
    monkeypatch.setattr(target=sp, name="stderr", value=err)
    sp.sprint("a", style=sp.SprintStyle(save=False))
    sp.sprint("b", style=sp.SprintStyle(level="warning", save=False))
    sp.sprint_err("c", style=sp.SprintStyle(level="error", save=False))
    expect_in(member="a", container=out.getvalue())
    expect_in(member="b", container=err.getvalue())
    expect_in(member="c", container=err.getvalue())


def test_save_target_resolution(tmp_path: Path) -> None:
    """Capture targets resolve relative to the project root.

    Args:
        tmp_path: Per-test temporary directory.

    """
    expect_equal(
        actual=private_call(
            owner=sp,
            name="_debug_save_target",
            root=tmp_path,
            value=None,
        ),
        expected=tmp_path / "debug" / "out.txt",
    )
    expect_equal(
        actual=private_call(
            owner=sp,
            name="_debug_save_target",
            root=tmp_path,
            value=" logs ",
        ),
        expected=tmp_path / "logs" / "out.txt",
    )
    expect_equal(
        actual=private_call(
            owner=sp,
            name="_debug_save_target",
            root=tmp_path,
            value="x/y.log",
        ),
        expected=tmp_path / "x" / "y.log",
    )
    absolute: Path = tmp_path / "abs.log"
    expect_equal(
        actual=private_call(
            owner=sp,
            name="_debug_save_target",
            root=tmp_path,
            value=str(object=absolute),
        ),
        expected=absolute,
    )


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("90", 90.0),
        ("1d5h", 104400.0),
        ("30m", 1800.0),
        ("", 86400.0),
        (None, 86400.0),
        ("junk", 86400.0),
    ],
)
def test_max_age_parsing(text: str | None, seconds: float) -> None:
    """Ages accept units, bare seconds, and fall back to a day.

    Args:
        text: Value for ``text``.
        seconds: Value for ``seconds``.

    """
    expect_equal(
        actual=private_call(owner=sp, name="_debug_max_age", value=text),
        expected=seconds,
    )


def test_selector_parsing() -> None:
    """Selectors split file globs from function filters."""
    plain: SelectorShape = _selector(entry="a/*.py")
    expect_equal(
        actual=(plain.file, plain.functions),
        expected=("a/*.py", None),
    )
    both: SelectorShape = _selector(entry="a.py[f, g.h]")
    expect_equal(actual=both.functions, expected=("f", "g.h"))
    only_fn: SelectorShape = _selector(entry="[work]")
    expect_equal(actual=only_fn.file, expected="**/*.py")
    empty: SelectorShape = _selector(entry="a.py[]")
    expect_none(value=empty.functions)
    bad: SelectorShape = _selector(entry="a[b[c]]")
    expect_equal(actual=bad.file, expected="a[b[c]]")


def test_spec_parsing(tmp_path: Path) -> None:
    """A marker file is resolved into capture directives.

    Args:
        tmp_path: Per-test temporary directory.

    """
    marker: Path = tmp_path / "DEBUG.txt"
    expect_none(
        value=private_call(owner=sp, name="_debug_spec", marker=marker),
    )
    marker.write_text(data="\nnoise\n", encoding="utf-8")
    expect_none(
        value=private_call(owner=sp, name="_debug_spec", marker=marker),
    )
    marker.write_text(
        data=dedent(
            text=(
                "    save::cap\n    clear::1h\n    filter::stdout bogus\n "
                "   filter::all\n    include::a.py b.py[f]\n    exclude::c"
                ".py\n    "
            ),
        ),
        encoding="utf-8",
    )
    spec: SpecShape = require(value=_spec(marker=marker))
    expect_true(condition=spec.save)
    expect_equal(actual=spec.max_age, expected=3600.0)
    expect_equal(actual=spec.streams, expected=("stderr", "stdout"))
    expect_equal(actual=len(spec.include), expected=2)
    expect_equal(actual=len(spec.exclude), expected=1)
    marker.write_text(data="clear\n", encoding="utf-8")
    cleared: SpecShape = require(value=_spec(marker=marker))
    expect_false(condition=cleared.save)


def test_selector_matching() -> None:
    """File and function globs both constrain matches."""
    site: object = private_call(
        owner=sp,
        name="_DebugSite",
        path="p",
        relative="pkg/mod.py",
        line=1,
        column=1,
        qualname="Klass.method",
    )

    def match(*, selector: object, site: object) -> object:
        """Run the private selector matcher.

        Args:
            selector: Selector under test.
            site: Call site under test.

        Returns:
            Whether the site satisfies the selector.

        """
        return private_call(
            owner=sp,
            name="_selector_matches",
            selector=selector,
            site=site,
        )

    def sel(*, file: str, functions: tuple[str, ...] | None) -> object:
        """Build a private debug selector.

        Args:
            file: File glob.
            functions: Function-name globs.

        Returns:
            The selector instance.

        """
        return private_call(
            owner=sp,
            name="_DebugSelector",
            file=file,
            functions=functions,
        )

    expect_true(
        condition=bool(
            match(selector=sel(file="pkg/*.py", functions=None), site=site),
        ),
    )
    expect_true(
        condition=bool(
            match(selector=sel(file="pkg", functions=None), site=site),
        ),
    )
    expect_false(
        condition=bool(
            match(selector=sel(file="other/*.py", functions=None), site=site),
        ),
    )
    expect_true(
        condition=bool(
            match(
                selector=sel(file="**/*.py", functions=("method",)),
                site=site,
            ),
        ),
    )
    expect_true(
        condition=bool(
            match(
                selector=sel(file="**/*.py", functions=("Klass.*",)),
                site=site,
            ),
        ),
    )
    expect_false(
        condition=bool(
            match(
                selector=sel(file="**/*.py", functions=("nope",)),
                site=site,
            ),
        ),
    )


def test_clear_drops_old_records(tmp_path: Path) -> None:
    """Records older than the limit are pruned, fresh ones kept.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "out.txt"
    private_call(
        owner=sp,
        name="_debug_clear",
        target=target,
        max_age=1.0,
        now=time(),
    )
    target.write_text(
        data=dedent(
            text=(
                "    STDOUT - 01/01/2000 00:00:00\n    old\n    -----\n   "
                " STDOUT - bad stamp 99/99/9999 99:99:99\n    weird\n    -"
                "----\n    no header\n    -----\n    \n    -----\n    "
            ),
        ),
        encoding="utf-8",
    )
    private_call(
        owner=sp,
        name="_debug_clear",
        target=target,
        max_age=60.0,
        now=time(),
    )
    text: str = target.read_text(encoding="utf-8")
    expect_not_in(member="old", container=text)
    expect_in(member="weird", container=text)


def test_record_is_written_and_filtered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture respects stream, include, and exclude directives.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=sp.Constants,
        name="project_root",
        value=tmp_path,
    )
    marker: Path = tmp_path / "DEBUG.txt"
    marker.write_text(data="save\nclear::1d\n", encoding="utf-8")
    sp.sprint("captured", file=StringIO())
    log: Path = tmp_path / "debug" / "out.txt"
    expect_in(member="captured", container=log.read_text(encoding="utf-8"))
    log.unlink()
    marker.write_text(data="save\nfilter::stderr\n", encoding="utf-8")
    sp.sprint("skipped", file=StringIO())
    expect_false(condition=log.exists())
    marker.write_text(data="save\nexclude::**/*.py\n", encoding="utf-8")
    sp.sprint("excluded", file=StringIO())
    expect_false(condition=log.exists())
    marker.write_text(data="save\ninclude::nothing/*.py\n", encoding="utf-8")
    sp.sprint("unselected", file=StringIO())
    expect_false(condition=log.exists())
    marker.write_text(data="clear\n", encoding="utf-8")
    sp.sprint("clearonly", file=StringIO())
    expect_false(condition=log.exists())
    marker.write_text(data="save\n", encoding="utf-8")
    sp.sprint("opt-out", file=StringIO(), style=sp.SprintStyle(save=False))
    expect_false(condition=log.exists())


def test_record_survives_unwritable_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I/O errors during capture never reach the caller.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=sp.Constants,
        name="project_root",
        value=tmp_path,
    )
    blocker: Path = tmp_path / "blocked"
    blocker.write_text(data="file", encoding="utf-8")
    (tmp_path / "DEBUG.txt").write_text(
        data=f"save::{blocker}/sub/out.txt\n",
        encoding="utf-8",
    )
    sp.sprint("still fine", file=StringIO())


def test_debug_site_skips_module_frames(tmp_path: Path) -> None:
    """The recorded site is the first frame outside the sprint module.

    The reflection helper that invokes the private function is that frame.

    Args:
        tmp_path: Per-test temporary directory.

    """
    site: SiteShape = require(
        value=cast(
            typ="SiteShape | None",
            val=private_call(
                owner=sp,
                name="_debug_site",
                root=Path(__file__).resolve().parents[4],
            ),
        ),
    )
    expect_true(condition=site.relative.endswith("support.py"))
    expect_equal(actual=site.qualname, expected="private_call")
    expect_true(condition=bool(tmp_path))


@pytest.fixture(
    autouse=True,
    params=("exactus.tools.common.sprint", "exactus.tools.record.sprint"),
)
def subsystem_contract(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the shared behavior in every shipped subsystem copy.

    Args:
        request: Parametrized implementation module name.
        monkeypatch: Isolated module binding substitutions.

    """
    implementation: ModuleType = import_module(name=request.param)
    monkeypatch.setattr(
        target=import_module(name=__name__),
        name="sp",
        value=implementation,
    )
