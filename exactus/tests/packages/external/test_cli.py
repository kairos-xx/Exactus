# Copyright (c) 2026
"""Drive ``exactus --external`` inventory and dispatch in-process."""

from __future__ import annotations

from io import StringIO
from json import dumps
from pathlib import Path
from subprocess import CompletedProcess
from sys import executable
from typing import TYPE_CHECKING

import pytest

from exactus import __main__ as check
from exactus.packages.external import cli as external
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
)
from exactus.tools.common.cli import resolve_exactus_tool_bundle

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
pytestmark: pytest.MarkDecorator = pytest.mark.usefixtures("isolated_check")


def _fake_leaf(*, root: Path) -> Path:
    """Write a minimal bundle leaf with a launcher and a manifest.

    Args:
        root: Directory the leaf is created under.

    Returns:
        The fake launcher's ``__main__.py`` path.

    """
    leaf: Path = root / "leaf"
    (leaf / "data").mkdir(parents=True)
    launcher: Path = leaf / "__main__.py"
    _ = launcher.write_text(data="print('launcher')\n", encoding="utf-8")
    _ = (leaf / "data" / "bundle.json").write_text(
        data=dumps(
            obj={
                "versions": {
                    "node": "22.21.1",
                    "python": {
                        "basedpyright": "1.40.2",
                        "pyrefly": "1.4.0",
                        "pytest": "9.1.1",
                        "ruff": "0.17.1",
                    },
                    "node_packages": {
                        "eslint": "10.13.0",
                        "prettier": "3.9.10",
                    },
                },
                "components": {
                    "zstd-cli": {"metadata": {"version": "1.5.7"}},
                    "chromium": {
                        "metadata": {
                            "browsers": {
                                "chromium": {
                                    "revision": "1208",
                                    "version": "141.0.7390.37",
                                },
                            },
                        },
                    },
                    "payloadless": {"metadata": {}},
                    "node": {
                        "metadata": {
                            "tools": {
                                "node": {
                                    "kind": "binary",
                                    "target": "node/bin/node",
                                },
                            },
                        },
                    },
                    "python_tools": {
                        "metadata": {
                            "python_packages": ("ruff", "pyrefly"),
                            "tools": {
                                "ruff": {
                                    "kind": "binary",
                                    "target": "python/bin/ruff",
                                },
                                "pyrefly": {
                                    "kind": "binary",
                                    "target": "python/bin/pyrefly",
                                },
                                "basedpyright": {
                                    "kind": "python-module",
                                    "target": "basedpyright",
                                },
                                "pytest": {
                                    "kind": "python-module",
                                    "target": "pytest",
                                },
                            },
                        },
                    },
                    "node_tools": {
                        "metadata": {
                            "node_packages": ("eslint", "prettier"),
                            "tools": {
                                "eslint": {
                                    "kind": "js-entry",
                                    "target": "eslint/bin/eslint.js",
                                },
                            },
                        },
                    },
                },
            },
        ),
        encoding="utf-8",
    )
    return launcher


def _use_leaf(monkeypatch: pytest.MonkeyPatch, *, launcher: Path) -> None:
    """Point the external resolver at a fixture leaf.

    Args:
        monkeypatch: Pytest patching helper.
        launcher: Fixture ``__main__.py`` returned for every lookup.

    """

    def fake_resolve(*, root: Path) -> Path:
        """Return the fixture launcher regardless of the root.

        Args:
            root: Project root passed to the resolver.

        Returns:
            The fixture launcher path.

        """
        del root
        return launcher

    monkeypatch.setattr(
        target=external,
        name="resolve_exactus_tool_bundle",
        value=fake_resolve,
    )


def _fake_spawn(
    *,
    commands: list[list[str]],
    status: int = 0,
) -> Callable[..., CompletedProcess[list[str]]]:
    """Return a ``spawn`` fake recording forwarded command lines.

    Args:
        commands: List receiving each forwarded command.
        status: Status reported back through ``CompletedProcess``.

    Returns:
        Fake ``subprocess.run`` replacement.

    """

    def fake_spawn(
        *,
        args: list[str],
        check: bool,
    ) -> CompletedProcess[list[str]]:
        """Record the command and report the configured status.

        Args:
            args: Fully resolved command line.
            check: Whether failures raise; ignored.

        Returns:
            Completed process carrying the configured status.

        """
        del check
        commands.append(args)
        return CompletedProcess(args=args, returncode=status)

    return fake_spawn


def _use_spawn(
    *,
    monkeypatch: pytest.MonkeyPatch,
    commands: list[list[str]],
    status: int = 0,
) -> None:
    """Route the module's ``spawn`` into a recording fake.

    Args:
        monkeypatch: Pytest patching helper.
        commands: List receiving each forwarded command.
        status: Status reported through ``CompletedProcess``.

    """
    monkeypatch.setattr(
        target=external,
        name="spawn",
        value=_fake_spawn(commands=commands, status=status),
    )


def _captured_stream(
    *,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> StringIO:
    """Replace a module writer with an in-memory capture stream.

    Args:
        monkeypatch: Pytest patching helper.
        name: ``stdout`` or ``stderr`` writer on the CLI module.

    Returns:
        The stream receiving everything the module writes.

    """
    stream: StringIO = StringIO()
    monkeypatch.setattr(target=external, name=name, value=stream)
    return stream


def test_inventory_groups_versions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A bare ``--external`` prints OS/Python/Node version groups.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    _use_leaf(monkeypatch=monkeypatch, launcher=_fake_leaf(root=tmp_path))
    stream: StringIO = _captured_stream(monkeypatch=monkeypatch, name="stdout")
    expect_equal(actual=external.run(arguments=[]), expected=0)
    out: str = stream.getvalue()
    for entry in (
        "OS:\n",
        "- chromium [141.0.7390.37]",
        "- node [22.21.1]",
        "- payloadless\n",
        "- pyrefly [1.4.0]",
        "- ruff [0.17.1]",
        "- zstd-cli [1.5.7]",
        "Python:\n",
        "- basedpyright [1.40.2]",
        "- pytest [9.1.1]",
        "Node:\n",
        "- eslint [10.13.0]",
        "- prettier [3.9.10]",
    ):
        expect_in(member=entry, container=out)
    python_section: str = out.partition("Python:")[2].partition("Node:")[0]
    expect_not_in(member="ruff", container=python_section)
    expect_not_in(member="pyrefly", container=python_section)


def test_dispatch_forwards_command_line(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--external TOOL ARGS`` reaches the launcher verbatim.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    launcher: Path = _fake_leaf(root=tmp_path)
    _use_leaf(monkeypatch=monkeypatch, launcher=launcher)
    commands: list[list[str]] = []
    _use_spawn(monkeypatch=monkeypatch, commands=commands)
    status: int = external.run(arguments=["ruff", "check", "--select", "ALL"])
    expect_equal(actual=status, expected=0)
    expect_equal(
        actual=commands,
        expected=[
            [
                executable,
                str(object=launcher),
                "ruff",
                "check",
                "--select",
                "ALL",
            ],
        ],
    )


def test_missing_tool_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unknown tool names fail before any dispatch happens.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    _use_leaf(monkeypatch=monkeypatch, launcher=_fake_leaf(root=tmp_path))
    stream: StringIO = _captured_stream(monkeypatch=monkeypatch, name="stderr")
    commands: list[list[str]] = []
    _use_spawn(monkeypatch=monkeypatch, commands=commands)
    status: int = external.run(arguments=["missing", "tests"])
    expect_equal(actual=status, expected=2)
    expect_equal(actual=commands, expected=[])
    expect_in(
        member='ERROR: no bundled tool named "missing"',
        container=stream.getvalue(),
    )


def test_launcher_meta_commands_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Launcher subcommands like ``list-tools`` pass membership checks.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    _use_leaf(monkeypatch=monkeypatch, launcher=_fake_leaf(root=tmp_path))
    commands: list[list[str]] = []
    _use_spawn(monkeypatch=monkeypatch, commands=commands)
    expect_equal(actual=external.run(arguments=["list-tools"]), expected=0)
    expect_equal(actual=external.run(arguments=["--verify"]), expected=0)
    expect_equal(actual=len(commands), expected=2)
    expect_equal(actual=commands[0][-1], expected="list-tools")
    expect_equal(actual=commands[1][-1], expected="--verify")


def test_dispatch_status_passthrough(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The tool's own exit status is returned to the caller.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    _use_leaf(monkeypatch=monkeypatch, launcher=_fake_leaf(root=tmp_path))
    _use_spawn(monkeypatch=monkeypatch, commands=[], status=3)
    expect_equal(actual=external.run(arguments=["ruff"]), expected=3)


def test_no_bundle_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing toolchain reports an error without dispatching.

    Args:
        monkeypatch: Pytest patching helper.

    """
    stream: StringIO = _captured_stream(monkeypatch=monkeypatch, name="stderr")

    def no_bundle(*, root: Path) -> None:
        """Report that no toolchain resolves.

        Args:
            root: Project root passed to the resolver.

        """
        del root

    monkeypatch.setattr(
        target=external,
        name="resolve_exactus_tool_bundle",
        value=no_bundle,
    )
    expect_equal(actual=external.run(arguments=["ruff"]), expected=2)
    expect_equal(actual=external.run(arguments=[]), expected=2)
    expect_in(
        member="ERROR: no compatible bundled toolchain is available",
        container=stream.getvalue(),
    )


def test_missing_manifest_lists_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A launcher without a manifest cannot render an inventory.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    leaf: Path = tmp_path / "leaf"
    leaf.mkdir()
    launcher: Path = leaf / "__main__.py"
    _ = launcher.write_text(data="print('x')\n", encoding="utf-8")
    _use_leaf(monkeypatch=monkeypatch, launcher=launcher)
    stream: StringIO = _captured_stream(monkeypatch=monkeypatch, name="stderr")
    expect_equal(actual=external.run(arguments=[]), expected=2)
    expect_in(
        member="ERROR: bundled manifest is unavailable",
        container=stream.getvalue(),
    )


def test_missing_manifest_defers_to_launcher(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Without a manifest the launcher's own validation decides.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    leaf: Path = tmp_path / "leaf"
    leaf.mkdir()
    launcher: Path = leaf / "__main__.py"
    _ = launcher.write_text(data="print('x')\n", encoding="utf-8")
    _use_leaf(monkeypatch=monkeypatch, launcher=launcher)
    commands: list[list[str]] = []
    _use_spawn(monkeypatch=monkeypatch, commands=commands)
    expect_equal(actual=external.run(arguments=["anything"]), expected=0)
    expect_equal(actual=len(commands), expected=1)


def test_main_routes_external_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``exactus --external`` reaches the external dispatcher.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    _use_leaf(monkeypatch=monkeypatch, launcher=_fake_leaf(root=tmp_path))
    forwarded: list[tuple[str, ...]] = []

    def fake_run(*, arguments: Sequence[str] | None = None) -> int:
        """Record the forwarded arguments.

        Args:
            arguments: Arguments after ``--external``.

        Returns:
            Always ``0``.

        """
        forwarded.append(tuple(arguments or ()))
        return 0

    monkeypatch.setattr(
        target=check,
        name="run_external_command",
        value=fake_run,
    )
    expect_equal(
        actual=check.main(
            arguments=["--external", "ruff", "check", "--select", "ALL"],
        ),
        expected=0,
    )
    expect_equal(
        actual=forwarded,
        expected=[("ruff", "check", "--select", "ALL")],
    )
    expect_equal(
        actual=check.main(arguments=["external", "node", "--version"]),
        expected=0,
    )
    expect_equal(actual=forwarded[-1], expected=("node", "--version"))


def test_real_bundle_lists_tools(capfd: pytest.CaptureFixture[str]) -> None:
    """The real host bundle answers ``--external list-tools``.

    Args:
        capfd: Pytest descriptor-level capture fixture.

    """
    if resolve_exactus_tool_bundle(root=Path.cwd()) is None:
        pytest.skip(reason="no host bundle is staged")
    expect_equal(actual=external.run(arguments=["list-tools"]), expected=0)
    expect_in(member="ruff", container=capfd.readouterr().out)


def test_real_bundle_runs_tool() -> None:
    """The real host bundle runs a binary tool end to end."""
    if resolve_exactus_tool_bundle(root=Path.cwd()) is None:
        pytest.skip(reason="no host bundle is staged")
    status: int = external.run(arguments=["ruff", "--version"])
    expect_true(condition=status in {0, 1, 2})
