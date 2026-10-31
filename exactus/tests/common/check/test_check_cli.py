# Copyright (c) 2026
"""The ``check`` orchestrator driven in-process with isolated global state."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast
from zipfile import ZipFile

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
from exactus import __main__ as check
from exactus.__main__ import Application, Check, main
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_not_in,
    expect_true,
    private_call,
    private_result,
)

pytestmark: pytest.MarkDecorator = pytest.mark.usefixtures("isolated_check")


def _extract(*, arguments: list[str]) -> tuple[tuple[str, ...], Path | None]:
    """Call the orchestrator's ``--root`` extraction helper.

    Args:
        arguments: Raw command-line arguments.

    Returns:
        Remaining arguments and the requested root.

    """
    return cast(
        typ="tuple[tuple[str, ...], Path | None]",
        val=private_call(
            owner=check,
            name="_extract_root",
            arguments=arguments,
        ),
    )


def test_help_and_listings(capsys: pytest.CaptureFixture[str]) -> None:
    """Help text and catalog listings are rendered.

    Args:
        capsys: Pytest output capture fixture.

    """
    expect_equal(actual=main(arguments=["-h"]), expected=0)
    expect_equal(actual=main(arguments=["--list-tools"]), expected=0)
    expect_equal(actual=main(arguments=["--list-pipelines"]), expected=0)
    _ = capsys.readouterr()


def test_tool_help_and_unknown(capsys: pytest.CaptureFixture[str]) -> None:
    """Per-tool help exits cleanly and unknown tools are rejected.

    Args:
        capsys: Pytest output capture fixture.

    """
    with pytest.raises(expected_exception=SystemExit):
        main(arguments=["--docs", "--help"])
    expect_equal(actual=main(arguments=["nonsense"]), expected=2)
    _ = capsys.readouterr()


def test_run_single_tool(sample_project: Path) -> None:
    """A tool flag runs the analyzer and writes reports in the project.

    Args:
        sample_project: Generated sample project directory.

    """
    preserved: Path = sample_project / "EXACTUS_RESULTS" / "DOCS" / "keep.txt"
    preserved.parent.mkdir(parents=True)
    preserved.write_text(data="keep", encoding="utf-8")
    expect_in(
        member=main(
            arguments=["--root", str(object=sample_project), "--readme"],
        ),
        container={0, 1},
    )
    expect_true(
        condition=(sample_project / "EXACTUS_RESULTS" / "README").is_dir(),
    )
    expect_true(condition=preserved.is_file())


def test_orchestrator_tools_and_clear(sample_project: Path) -> None:
    """The orchestrator runs selected tools and clears results.

    Args:
        sample_project: Generated sample project directory.

    """
    root: str = str(object=sample_project)
    expect_in(
        member=main(arguments=["--root", root, "--tool", "readme", "docs"]),
        container={0, 1},
    )
    expect_equal(
        actual=main(
            arguments=["--root", root, "--clear", "readme", "--list-tools"],
        ),
        expected=0,
    )
    expect_equal(
        actual=main(arguments=["--root", root, "--clear", "--list-pipelines"]),
        expected=0,
    )
    expect_equal(
        actual=main(arguments=["--root", root, "--clear", "bogus"]),
        expected=2,
    )


def test_orchestrator_pipeline_with_exclusions(sample_project: Path) -> None:
    """A pipeline runs in waves honoring excluded tools.

    Args:
        sample_project: Generated sample project directory.

    """
    status: int = main(
        arguments=[
            "--root",
            str(object=sample_project),
            "--pipeline",
            "self",
            "--exclude-tools",
            "lints",
            "coverage_tests",
            "--exclude",
            "EXACTUS_RESULTS/**",
        ],
    )
    expect_in(member=status, container={0, 1})
    expect_true(
        condition=(
            sample_project / "EXACTUS_RESULTS" / "PIPELINES" / "SELF"
        ).is_dir(),
    )


def test_orchestrator_bad_selections(sample_project: Path) -> None:
    """Invalid tool and pipeline names produce errors.

    Args:
        sample_project: Generated sample project directory.

    """
    root: str = str(object=sample_project)
    expect_equal(
        actual=main(arguments=["--root", root, "--exclude-tools", "zzz"]),
        expected=2,
    )
    expect_equal(
        actual=main(arguments=["--root", root, "--tool", "zzz"]),
        expected=2,
    )
    expect_equal(
        actual=main(arguments=["--root", root, "--pipeline", "zzz"]),
        expected=2,
    )


def test_extract_root_forms() -> None:
    """Both ``--root DIR`` and ``--root=DIR`` are removed from argv."""
    remaining, root = _extract(
        arguments=["--root", "a", "x", "--", "--root", "b"],
    )
    expect_equal(actual=root, expected=Path("a"))
    expect_equal(actual=remaining, expected=("x", "--", "--root", "b"))
    remaining, root = _extract(arguments=["--root=z", "y"])
    expect_equal(actual=root, expected=Path("z"))
    expect_equal(actual=remaining, expected=("y",))


def test_application_class_constants() -> None:
    """Tool dispatch flags stay disjoint from help flags."""
    dispatch: frozenset[str] = frozenset(
        flag for tool in check.bundled_tools() for flag in tool.flags
    )
    expect_false(condition=bool(Application.HELP_FLAGS & dispatch))


def _bundled_pyz(*, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point ``argv[0]`` at a zipapp archive and quiet startup hooks.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    Returns:
        The fake zipapp path.

    """
    archive: Path = tmp_path / "exactus"
    zipped: ZipFile = ZipFile(file=archive, mode="w")
    zipped.writestr(zinfo_or_arcname="__main__.py", data="")
    zipped.close()
    monkeypatch.setattr(target=check, name="argv", value=[str(object=archive)])

    def noop() -> None:
        """Ignore the startup side effect."""

    monkeypatch.setattr(target=check, name="warn_if_stale", value=noop)
    monkeypatch.setattr(target=check, name="ensure_completion", value=noop)
    return archive


def test_bundled_runtime_detects_zipapp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A zipapp ``argv[0]`` marks the bundled runtime.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _bundled_pyz(monkeypatch=monkeypatch, tmp_path=tmp_path)
    expect_true(
        condition=private_result(
            owner=check,
            name="_bundled_runtime",
            kind=bool,
        ),
    )


def test_bundled_runtime_rejects_source_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Directories, plain scripts, and misses are not bundled.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    monkeypatch.setattr(
        target=check,
        name="argv",
        value=[str(object=tmp_path)],
    )
    expect_false(
        condition=private_result(
            owner=check,
            name="_bundled_runtime",
            kind=bool,
        ),
    )
    script: Path = tmp_path / "runner.py"
    _ = script.write_text(data="print(1)\n", encoding="utf-8")
    monkeypatch.setattr(target=check, name="argv", value=[str(object=script)])
    expect_false(
        condition=private_result(
            owner=check,
            name="_bundled_runtime",
            kind=bool,
        ),
    )
    monkeypatch.setattr(target=check, name="argv", value=["exactus-missing"])

    def no_which(*, cmd: str) -> None:
        """Resolve no command on ``PATH``.

        Args:
            cmd: Command looked up on ``PATH``.

        """
        del cmd

    monkeypatch.setattr(target=check, name="which", value=no_which)
    expect_false(
        condition=private_result(
            owner=check,
            name="_bundled_runtime",
            kind=bool,
        ),
    )


def test_bundled_runtime_resolves_path_lookup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A bare command name resolves through ``PATH``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    archive: Path = tmp_path / "exactus"
    zipped: ZipFile = ZipFile(file=archive, mode="w")
    zipped.writestr(zinfo_or_arcname="__main__.py", data="")
    zipped.close()

    def fake_which(*, cmd: str) -> str:
        """Return the archive for the bare command name.

        Args:
            cmd: Command looked up on ``PATH``.

        Returns:
            The archive path.

        """
        del cmd
        return str(object=archive)

    monkeypatch.setattr(target=check, name="argv", value=["exactus"])
    monkeypatch.setattr(target=check, name="which", value=fake_which)
    expect_true(
        condition=private_result(
            owner=check,
            name="_bundled_runtime",
            kind=bool,
        ),
    )


def _opt_in_self_test(*, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a build produced with ``--build-self-test``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    monkeypatch.setattr(
        target=check,
        name="_bundled_self_test",
        value=lambda: True,
    )


def test_bundled_tools_omit_self_test(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A default build hides the self-diagnostic tool.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _bundled_pyz(monkeypatch=monkeypatch, tmp_path=tmp_path)
    names: tuple[str, ...] = tuple(tool.name for tool in check.bundled_tools())
    expect_not_in(member="self_test", container=names)
    expect_in(member="frontend", container=names)
    expect_in(member="visual_cause", container=names)


def test_bundled_optin_keeps_self_test(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A ``--build-self-test`` build keeps the diagnostic tool.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _bundled_pyz(monkeypatch=monkeypatch, tmp_path=tmp_path)
    _opt_in_self_test(monkeypatch=monkeypatch)
    names: tuple[str, ...] = tuple(tool.name for tool in check.bundled_tools())
    expect_in(member="self_test", container=names)
    expect_in(member="frontend", container=names)


def test_source_tools_keep_self_test(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Source checkouts keep the self-diagnostic tool.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    launcher: Path = tmp_path / "exactus"
    _ = launcher.write_text(data="print('x')\n", encoding="utf-8")
    monkeypatch.setattr(
        target=check,
        name="argv",
        value=[str(object=launcher)],
    )
    names: tuple[str, ...] = tuple(tool.name for tool in check.bundled_tools())
    expect_in(member="self_test", container=names)


def _record_tools(*, captured: list[str]) -> Callable[..., bool]:
    """Return a ``Check.run_tool`` fake recording tool names.

    Args:
        captured: List receiving each dispatched tool name.

    Returns:
        Fake ``run_tool`` reporting success.

    """

    def fake_run_tool(
        cls: type[Check],
        *,
        name: str,
        arguments: tuple[str, ...],
        common: tuple[str, ...] = (),
    ) -> bool:
        """Record the tool name instead of running it.

        Args:
            cls: Bound class.
            name: Tool identifier.
            arguments: Tool CLI arguments.
            common: Forwarded flag pairs.

        Returns:
            Always ``True``.

        """
        del cls, arguments, common
        captured.append(name)
        return True

    return fake_run_tool


def test_bundled_rejects_self_test_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--self_test`` is an unknown flag on a default build.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _bundled_pyz(monkeypatch=monkeypatch, tmp_path=tmp_path)
    expect_equal(actual=main(arguments=["--self_test"]), expected=2)


def test_bundled_optin_accepts_self_test_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--self_test`` dispatches on an opt-in build.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _bundled_pyz(monkeypatch=monkeypatch, tmp_path=tmp_path)
    _opt_in_self_test(monkeypatch=monkeypatch)
    captured: list[str] = []
    monkeypatch.setattr(
        target=Check,
        name="run_tool",
        value=classmethod(_record_tools(captured=captured)),
    )
    expect_equal(actual=main(arguments=["--self_test"]), expected=0)
    expect_equal(actual=captured, expected=["self_test"])


def test_self_test_dash_flag_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--self-test`` dispatches to ``self_test`` like ``--self_test``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    captured: list[str] = []
    monkeypatch.setattr(
        target=Check,
        name="run_tool",
        value=classmethod(_record_tools(captured=captured)),
    )
    expect_equal(actual=main(arguments=["--self-test"]), expected=0)
    expect_equal(actual=captured, expected=["self_test"])


def test_bundled_rejects_self_test_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``-t self_test`` is refused on a default build.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _bundled_pyz(monkeypatch=monkeypatch, tmp_path=tmp_path)
    expect_equal(actual=main(arguments=["--tool", "self_test"]), expected=2)


def test_bundled_optin_accepts_self_test_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``-t self_test`` is accepted on an opt-in build.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _bundled_pyz(monkeypatch=monkeypatch, tmp_path=tmp_path)
    _opt_in_self_test(monkeypatch=monkeypatch)
    captured: list[str] = []
    monkeypatch.setattr(
        target=Check,
        name="run_tool",
        value=classmethod(_record_tools(captured=captured)),
    )
    expect_equal(actual=main(arguments=["--tool", "self_test"]), expected=0)
    expect_equal(actual=captured, expected=["self_test"])


def test_bundled_pipeline_excludes_self_test(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pipelines drop ``self_test`` on a default build.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _bundled_pyz(monkeypatch=monkeypatch, tmp_path=tmp_path)
    captured: list[frozenset[str]] = []

    def fake_pipeline(
        cls: type[Check],
        *,
        name: str,
        tool_arguments: dict[str, tuple[str, ...]],
        exclude: frozenset[str],
        common: tuple[str, ...],
    ) -> bool:
        """Record the exclusion set instead of running.

        Args:
            cls: Bound class.
            name: Pipeline identifier.
            tool_arguments: Per-tool command-line arguments.
            exclude: Canonical tools skipped by the run.
            common: Flat ``--include``/``--exclude`` flag pairs.

        Returns:
            Always ``True``.

        """
        del cls, name, tool_arguments, common
        captured.append(exclude)
        return True

    monkeypatch.setattr(
        target=Check,
        name="run_pipeline",
        value=classmethod(fake_pipeline),
    )
    expect_equal(actual=main(arguments=[]), expected=0)
    expect_in(member="self_test", container=captured[0])
    captured.clear()
    _opt_in_self_test(monkeypatch=monkeypatch)
    expect_equal(actual=main(arguments=[]), expected=0)
    expect_not_in(member="self_test", container=captured[0])
    captured.clear()
    monkeypatch.setattr(
        target=check,
        name="argv",
        value=[str(object=tmp_path)],
    )
    expect_equal(actual=main(arguments=[]), expected=0)
    expect_not_in(member="self_test", container=captured[0])


def _identity(*, pid: int) -> check.RunIdentity:
    """Build a verified-looking run identity for kill tests.

    Args:
        pid: Process identifier the identity advertises.

    Returns:
        Immutable run identity bound to the test runtime database.

    """
    return check.RunIdentity(
        root_pid=pid,
        run_id="run-abc",
        runs_db=str(object=Check.exactus_root / ".runtime" / "runs.db"),
        created_at=1.0,
        instance_id="a" * 32,
    )


def test_kill_dispatches_run_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bare ``--kill`` terminates every live run and exits.

    Args:
        monkeypatch: Pytest patching helper.

    """
    calls: list[Path | None] = []

    def fake_terminate(
        *,
        pipeline_run_id: str | None = None,
        output: Path | None = None,
    ) -> int:
        """Record the requested run ``output``.

        Args:
            pipeline_run_id: Ignored run filter.
            output: Output directory of the run to terminate.

        Returns:
            Fake termination exit code.

        """
        del pipeline_run_id
        calls.append(output)
        return 3

    monkeypatch.setattr(
        target=Check,
        name="_terminate_run_tools",
        value=staticmethod(fake_terminate),
    )
    expect_equal(actual=main(arguments=["--kill"]), expected=0)
    expect_equal(actual=calls, expected=[None])


def test_kill_named_and_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--kill NAME`` scopes termination and rejects unknown names.

    Args:
        monkeypatch: Pytest patching helper.

    """
    calls: list[Path | None] = []

    def fake_terminate(
        *,
        pipeline_run_id: str | None = None,
        output: Path | None = None,
    ) -> int:
        """Record the requested run ``output``.

        Args:
            pipeline_run_id: Ignored run filter.
            output: Output directory of the run to terminate.

        Returns:
            Fake termination exit code.

        """
        del pipeline_run_id
        calls.append(output)
        return 1

    monkeypatch.setattr(
        target=Check,
        name="_terminate_run_tools",
        value=staticmethod(fake_terminate),
    )
    expect_equal(actual=main(arguments=["--kill", "readme"]), expected=0)
    expect_equal(actual=len(calls), expected=1)
    expect_true(condition=str(object=calls[0]).endswith("README"))
    expect_equal(actual=main(arguments=["--kill", "bogus"]), expected=2)


def test_kill_all_dispatches_scanner(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--kill-all`` and ``--kill_all`` run the global scan once.

    Args:
        monkeypatch: Pytest patching helper.

    """
    calls: list[bool] = []

    def fake_kill_all() -> tuple[int, int]:
        """Record each global scan.

        Returns:
            Fake verified/leftover termination counts.

        """
        calls.append(True)
        return (2, 1)

    monkeypatch.setattr(
        target=Check,
        name="_kill_all",
        value=staticmethod(fake_kill_all),
    )
    expect_equal(actual=main(arguments=["--kill-all"]), expected=0)
    expect_equal(actual=main(arguments=["--kill_all"]), expected=0)
    expect_equal(actual=len(calls), expected=2)


def test_kill_all_terminates_verified_and_leftovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Global kill verifies identities then sweeps leftovers.

    Args:
        monkeypatch: Pytest patching helper.

    """
    discovered: list[bytes] = []
    terminated: list[int] = []
    swept: list[int] = []

    def fake_keys() -> list[bytes]:
        """Return one fixed authkey.

        Returns:
            Single protocol-sized secret.

        """
        return [b"k" * 32]

    def fake_discover(
        *,
        authkey: bytes,
        timeout: float = 0.3,
        workers: int = 32,
        full_scan: bool = True,
    ) -> list[check.RunIdentity]:
        """Record the authkey and return one fake identity.

        Args:
            authkey: Secret used to authenticate the scan.
            timeout: Ignored discovery timeout.
            workers: Ignored discovery worker count.
            full_scan: Whether the scan covered the whole runtime.

        Returns:
            Single fake ``RunIdentity``.

        """
        del timeout, workers
        expect_true(condition=full_scan)
        discovered.append(authkey)
        return [_identity(pid=4242)]

    class FakeTerminator:
        """Record verified terminations without touching processes."""

        @staticmethod
        def terminate(
            *,
            identity: check.RunIdentity,
            force: bool = True,
        ) -> check.TerminationResult:
            """Record one verified termination.

            Args:
                identity: Fake run identity to terminate.
                force: Whether the termination is forced.

            Returns:
                Fake ``TerminationResult`` for ``identity``.

            """
            expect_true(condition=force)
            terminated.append(identity.root_pid)
            return check.TerminationResult(
                root_pid=identity.root_pid,
                run_id=identity.run_id,
                runs_db=identity.runs_db,
                discovered=(identity.root_pid,),
                terminated=(identity.root_pid,),
                killed=(),
                already_exited=(),
                failed=(),
                skipped=(),
                duration=0.01,
            )

    def fake_sweep(*, pid: int) -> None:
        """Record one swept process.

        Args:
            pid: Process identifier passed to the tree sweep.

        """
        swept.append(pid)

    monkeypatch.setattr(
        target=Check,
        name="_candidate_authkeys",
        value=staticmethod(fake_keys),
    )
    monkeypatch.setattr(target=check, name="discover", value=fake_discover)
    monkeypatch.setattr(
        target=check,
        name="ProcessTerminator",
        value=FakeTerminator,
    )
    monkeypatch.setattr(
        target=Check,
        name="_exactus_processes",
        value=staticmethod(lambda: {4242, 5150}),
    )
    monkeypatch.setattr(target=check, name="terminate_tree", value=fake_sweep)
    verified: int
    leftovers: int
    verified, leftovers = cast(
        typ="tuple[int, int]",
        val=private_call(owner=Check, name="_kill_all"),
    )
    expect_equal(actual=len(discovered), expected=1)
    expect_equal(actual=terminated, expected=[4242])
    expect_in(member=5150, container=swept)
    expect_equal(actual=verified, expected=1)
    expect_equal(actual=leftovers, expected=len(swept))


def test_exactus_processes_heuristic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The leftover scan matches Exactus processes, not lookalikes.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """

    class FakeProcess:
        """Minimal psutil stand-in for the process table scan."""

        def __init__(
            self,
            *,
            pid: int,
            name: str,
            cmdline: list[str],
            exe: str = "",
        ) -> None:
            self.pid: int = pid
            self._name: str = name
            self._cmdline: list[str] = cmdline
            self._exe: str = exe

        def name(self) -> str:
            """Process name."""
            return self._name

        def cmdline(self) -> list[str]:
            """Process argument vector."""
            return self._cmdline

        def exe(self) -> str:
            """Return the executable path."""
            return self._exe

    exactus_dir: Path = tmp_path / "exactus"
    exactus_dir.mkdir()
    table: list[FakeProcess] = [
        FakeProcess(
            pid=1,
            name="python3",
            cmdline=["python", "-m", "exactus.packages.pmanager.runtime"],
        ),
        FakeProcess(
            pid=2,
            name="exactus",
            cmdline=["/usr/local/bin/exactus", "run"],
            exe="/usr/local/bin/exactus",
        ),
        FakeProcess(
            pid=3,
            name="node",
            cmdline=["node", "/opt/other/langserver.index.js"],
            exe="/home/u/.cache/exactus-tools/abc/components/x/bin/node",
        ),
        FakeProcess(
            pid=4,
            name="electron",
            cmdline=["/opt/code/code", str(object=exactus_dir)],
        ),
        FakeProcess(
            pid=5,
            name="python3",
            cmdline=["python", str(object=exactus_dir)],
        ),
        FakeProcess(pid=6, name="bash", cmdline=["bash", "-c", "exactus"]),
    ]
    monkeypatch.setattr(
        target=check,
        name="process_iter",
        value=lambda: iter(table),
    )
    found: set[int] = cast(
        typ="set[int]",
        val=private_call(owner=Check, name="_exactus_processes"),
    )
    expect_in(member=1, container=found)
    expect_in(member=2, container=found)
    expect_in(member=3, container=found)
    expect_not_in(member=4, container=found)
    expect_not_in(member=5, container=found)
    expect_not_in(member=6, container=found)
