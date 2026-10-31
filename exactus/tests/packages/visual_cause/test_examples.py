# Copyright (c) 2026
"""Coverage and behavior tests for bundled runnable examples."""

from importlib import import_module
from pathlib import Path
from runpy import run_path
from textwrap import dedent
from types import ModuleType
from typing import Final, final

import pytest

from exactus.packages import visual_cause as package
from exactus.packages.server import local as server_local
from exactus.packages.visual_cause.examples import run, validate_results
from exactus.tests.packages.visual_cause.support import (
    expect_equal,
    expect_false,
    expect_true,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        run_modules: Grouped module constant.
        validate_modules: Grouped module constant.

    """

    run_modules: Final[tuple[ModuleType, ...]] = (run,)
    validate_modules: Final[tuple[ModuleType, ...]] = (validate_results,)


@pytest.mark.parametrize(argnames="demo", argvalues=Constants.run_modules)
def test_example_run_builds_demo_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    demo: ModuleType,
) -> None:
    """Run the example orchestration without launching a real browser.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.
        demo: Example run module under test.

    """
    example_root: Path = tmp_path / "examples"
    web: Path = example_root / "web"
    results: Path = example_root / "results"
    web.mkdir(parents=True)
    results.mkdir()
    (web / "index.html").write_text(data="<html></html>", encoding="utf-8")
    (web / "a.css").write_text(data="a{}", encoding="utf-8")
    (web / "b.css").write_text(data="b{}", encoding="utf-8")
    monkeypatch.setattr(
        target=demo,
        name="__file__",
        value=str(object=example_root / "run.py"),
    )
    observed: list[object] = []

    class AnalyzerStub:
        def __init__(self, *, settings: object) -> None:
            """Record the settings used to build the stub.

            Args:
                settings: Analyzer settings instance.

            """
            observed.append(settings)

        @staticmethod
        def run() -> None:
            """Record the synthetic analysis run."""
            observed.append("run")

    def _record_validation() -> None:
        """Record the synthetic validation call."""
        observed.append("validate")

    class LocalStub:
        @staticmethod
        def reuse_server(*, path: Path) -> tuple[int, int] | None:
            """Return a recorded server so no child process is spawned.

            Args:
                path: Served root directory.

            Returns:
                Synthetic process/port pair for the recorded server.

            """
            observed.append(path)
            return (4321, 9876)

        @staticmethod
        def wait_ready(*, url: str, pid: int) -> bool:
            """Report the synthetic server as ready.

            Args:
                url: Recorded loopback URL.
                pid: Recorded process id.

            Returns:
                Always true for the adopted server.

            """
            expect_equal(
                actual=(pid, url),
                expected=(4321, "http://127.0.0.1:9876/"),
            )
            return True

    monkeypatch.setattr(target=demo, name="local", value=LocalStub)
    monkeypatch.setattr(target=demo, name="CssVisualCause", value=AnalyzerStub)
    monkeypatch.setattr(
        target=demo,
        name="validate_demo_results",
        value=_record_validation,
    )
    demo.main()
    expect_equal(actual=observed[-2:], expected=["run", "validate"])
    expect_false(condition=results.exists())


@pytest.mark.parametrize(
    argnames="validator",
    argvalues=Constants.validate_modules,
)
def test_validate_results_success_and_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    validator: ModuleType,
) -> None:
    """Validate complete evidence and reject missing reports.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.
        validator: Validate-results module under test.

    """
    example_root: Path = tmp_path / "examples"
    results: Path = example_root / "results"
    evidence: Path = results / "evidence"
    evidence.mkdir(parents=True)
    monkeypatch.setattr(
        target=validator,
        name="__file__",
        value=str(object=example_root / "validate_results.py"),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="was not generated",
    ):
        validator.main()
    references: list[str] = [
        "evidence/a.png",
        "evidence/b.png",
        "evidence/diff.png",
    ]
    for reference in references:
        (results / reference).write_bytes(data=b"png")
    markdown: str = "\n".join(
        [
            "## `b.css`",
            "### Rule 1: `.a`",
            "#### `width: 1px`",
            "##### Affected element `.a`",
            "**What changed:**",
            "**Other contributing properties:**",
            "```css",
            ".a{}",
            "```",
            *[f"![]({reference})" for reference in references],
        ],
    )
    (results / "report.md").write_text(data=markdown, encoding="utf-8")
    validator.main()


@pytest.mark.parametrize(
    argnames="validator",
    argvalues=Constants.validate_modules,
)
def test_validate_results_rejects_incomplete_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    validator: ModuleType,
) -> None:
    """Cover malformed-report validation branches.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.
        validator: Validate-results module under test.

    """
    example_root: Path = tmp_path / "examples"
    results: Path = example_root / "results"
    results.mkdir(parents=True)
    monkeypatch.setattr(
        target=validator,
        name="__file__",
        value=str(object=example_root / "validate_results.py"),
    )
    (results / "report.md").write_text(data="# incomplete", encoding="utf-8")
    with pytest.raises(
        expected_exception=RuntimeError,
        match="missing required sections",
    ):
        validator.main()


@pytest.mark.parametrize(
    argnames="validator",
    argvalues=Constants.validate_modules,
)
def test_validate_results_rejects_incomplete_evidence_triplet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    validator: ModuleType,
) -> None:
    """Reject a structurally complete report with incomplete image evidence.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.
        validator: Validate-results module under test.

    """
    example_root: Path = tmp_path / "examples"
    results: Path = example_root / "results"
    results.mkdir(parents=True)
    monkeypatch.setattr(
        target=validator,
        name="__file__",
        value=str(object=example_root / "validate_results.py"),
    )
    markdown: str = dedent(
        text=(
            "    ## `b.css`\n    ### Rule 1: `.a`\n    #### `width: 1px`\n    "
            "##### Affected element `.a`\n    **What changed:**\n    **Other c"
            "ontributing properties:**\n    ```css\n    .a{}\n    ```\n    ![]"
            "(evidence/a.png)"
        ),
    )
    (results / "report.md").write_text(data=markdown, encoding="utf-8")
    with pytest.raises(
        expected_exception=RuntimeError,
        match="complete A/B/diff evidence triplets",
    ):
        validator.main()


@pytest.mark.parametrize(
    argnames="validator",
    argvalues=Constants.validate_modules,
)
def test_validate_results_rejects_zero_missing_and_empty_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    validator: ModuleType,
) -> None:
    """Cover zero-evidence, missing-file, and empty-file validation.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.
        validator: Validate-results module under test.

    """
    example_root: Path = tmp_path / "examples"
    results: Path = example_root / "results"
    evidence: Path = results / "evidence"
    evidence.mkdir(parents=True)
    monkeypatch.setattr(
        target=validator,
        name="__file__",
        value=str(object=example_root / "validate_results.py"),
    )
    base: str = dedent(
        text=(
            "    ## `b.css`\n    ### Rule 1: `.a`\n    #### `width: 1px`\n    "
            "##### Affected element `.a`\n    **Other contributing properties:"
            "**\n    ```css\n    .a{}\n    ```"
        ),
    )
    triplet: str = (
        "![](evidence/a.png)\n![](evidence/b.png)\n![](evidence/diff.png)"
    )
    (results / "report.md").write_text(
        data=base + "\nChanged rules represented | 0\n" + triplet,
        encoding="utf-8",
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="no CSS rule/property evidence",
    ):
        validator.main()
    (results / "report.md").write_text(
        data=base + "\n" + triplet,
        encoding="utf-8",
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="missing evidence",
    ):
        validator.main()
    for name in ("a.png", "b.png", "diff.png"):
        (evidence / name).write_bytes(data=b"")
    with pytest.raises(
        expected_exception=RuntimeError,
        match="empty evidence",
    ):
        validator.main()


def test_example_run_reports_a_server_that_never_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise ``RuntimeError`` when the demo server does not come up.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    demo: ModuleType = import_module(
        name="exactus.packages.visual_cause.examples.run",
    )
    example_root: Path = tmp_path / "examples"
    web: Path = example_root / "web"
    web.mkdir(parents=True)
    (web / "index.html").write_text(data="<html></html>", encoding="utf-8")
    monkeypatch.setattr(
        target=demo,
        name="__file__",
        value=str(object=example_root / "run.py"),
    )

    class LocalStub:
        @staticmethod
        def reuse_server(*, path: Path) -> tuple[int, int] | None:
            """Report that no recorded server exists.

            Args:
                path: Served root directory.

            Returns:
                Always ``None``.

            """
            _ = path
            return None

        @staticmethod
        def serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
            """Return a spawned-but-unresponsive server.

            Args:
                path: Served root directory.
                log: Server log destination.

            Returns:
                Synthetic process id, URL, and adoption flag.

            """
            _ = path, log
            return (4321, "http://127.0.0.1:9876/", False)

        @staticmethod
        def wait_ready(*, url: str, pid: int) -> bool:
            """Report the synthetic server as never ready.

            Args:
                url: Recorded loopback URL.
                pid: Recorded process id.

            Returns:
                Always false.

            """
            _ = url, pid
            return False

        @staticmethod
        def clear_server_state(*, path: Path) -> None:
            """Pretend to clear recorded server state.

            Args:
                path: Served root directory.

            """
            _ = path

    terminated: list[int] = []

    def _record_termination(*, pid: int) -> None:
        """Record the terminated process id.

        Args:
            pid: Process id to terminate.

        """
        terminated.append(pid)

    def _no_analyzer(**_ignored: object) -> None:
        """Report that no recorded analyzer exists.

        Args:
            _ignored: Keyword arguments (unused).

        """
        return

    monkeypatch.setattr(target=demo, name="local", value=LocalStub)
    monkeypatch.setattr(
        target=demo,
        name="terminate_tree",
        value=_record_termination,
    )
    monkeypatch.setattr(target=demo, name="CssVisualCause", value=_no_analyzer)
    with pytest.raises(
        expected_exception=RuntimeError,
        match="did not become ready",
    ):
        demo.main()
    expect_equal(actual=terminated, expected=[4321])


def test_example_run_module_executes_as_a_script(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the ``examples/run.py`` file's ``__main__`` entry point.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    example_root: Path = tmp_path / "examples"
    web: Path = example_root / "web"
    web.mkdir(parents=True)
    (web / "index.html").write_text(data="<html></html>", encoding="utf-8")
    (web / "a.css").write_text(data="a{}", encoding="utf-8")
    (web / "b.css").write_text(data="b{}", encoding="utf-8")
    observed: list[object] = []

    class AnalyzerStub:
        def __init__(self, *, settings: object) -> None:
            """Record the settings used to build the stub.

            Args:
                settings: Analyzer settings instance.

            """
            observed.append(settings)

        @staticmethod
        def run() -> None:
            """Record the synthetic analysis run."""
            observed.append("run")

    def _recorded_server(**_ignored: object) -> tuple[int, int]:
        """Return the recorded process and port pair.

        Args:
            _ignored: Keyword arguments (unused).

        Returns:
            The synthetic process id and port.

        """
        return (4321, 9876)

    def _ready(**_ignored: object) -> bool:
        """Report the server as immediately ready.

        Args:
            _ignored: Keyword arguments (unused).

        Returns:
            Always ``True``.

        """
        return True

    def _record_validation() -> None:
        """Record the synthetic validation call."""
        observed.append("validate")

    monkeypatch.setattr(
        target=server_local,
        name="reuse_server",
        value=_recorded_server,
    )
    monkeypatch.setattr(target=server_local, name="wait_ready", value=_ready)
    monkeypatch.setattr(
        target=package,
        name="CssVisualCause",
        value=AnalyzerStub,
    )
    monkeypatch.setattr(
        target=validate_results,
        name="main",
        value=_record_validation,
    )
    run_path(
        path_name=str(
            object=(
                Path(__file__).resolve().parents[4]
                / "exactus"
                / "packages"
                / "visual_cause"
                / "examples"
                / "run.py"
            ),
        ),
        run_name="__main__",
    )
    expect_true(condition="run" in observed)


def test_examples_run_module_executes_as_a_script(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run ``examples/run.py`` via ``__main__`` with a stubbed pipeline.

    Args:
        tmp_path: Pytest temporary directory (unused).
        monkeypatch: Pytest patching helper.

    """
    _ = tmp_path
    events: list[str] = []
    removed: list[Path] = []

    def reuse_server(*, path: Path) -> tuple[int, int] | None:
        """Report no recorded server.

        Args:
            path: Served root directory.

        Returns:
            Always ``None``.

        """
        _ = path
        return None

    def serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
        """Return a synthetic server spawn.

        Args:
            path: Served root directory.
            log: Access-log destination.

        Returns:
            Synthetic pid, origin, and reuse flag.

        """
        _ = path
        _ = log
        events.append("serve")
        return (99, "http://127.0.0.1:8080/", False)

    def wait_ready(*, url: str, pid: int) -> bool:
        """Report the synthetic server as ready.

        Args:
            url: Server origin.
            pid: Spawned process id.

        Returns:
            Always ``True``.

        """
        _ = url
        _ = pid
        return True

    def terminate(*, pid: int) -> None:
        """Record the terminated process id.

        Args:
            pid: Process id to terminate.

        """
        events.append(f"kill:{pid}")

    def clear_server_state(*, path: Path) -> None:
        """Record the cleared server state.

        Args:
            path: Served root directory.

        """
        _ = path
        events.append("clear")

    def fake_rmtree(*, path: Path) -> None:
        """Record the cleanup instead of deleting tracked results.

        Args:
            path: Directory that would be removed.

        """
        removed.append(path)

    class AnalyzerStub:
        """Stand-in for the real ``CssVisualCause`` analyzer."""

        def __init__(self, *, settings: object) -> None:
            """Record the analyzer settings.

            Args:
                settings: Analyzer settings instance.

            """
            events.append(f"settings:{type(settings).__name__}")

        @staticmethod
        def run() -> None:
            """Record the synthetic analysis run."""
            events.append("analyze")

    def fake_validate() -> None:
        """Record the synthetic validation run."""
        events.append("validate")

    monkeypatch.setattr(
        target=server_local,
        name="reuse_server",
        value=reuse_server,
    )
    monkeypatch.setattr(target=server_local, name="serve", value=serve)
    monkeypatch.setattr(
        target=server_local,
        name="wait_ready",
        value=wait_ready,
    )
    monkeypatch.setattr(
        target=server_local,
        name="clear_server_state",
        value=clear_server_state,
    )
    monkeypatch.setattr(
        target=import_module(name="exactus.packages.server.process_control"),
        name="terminate_tree",
        value=terminate,
    )
    monkeypatch.setattr(
        target=import_module(name="exactus.packages.visual_cause"),
        name="CssVisualCause",
        value=AnalyzerStub,
    )
    monkeypatch.setattr(
        target=validate_results,
        name="main",
        value=fake_validate,
    )
    monkeypatch.setattr(
        target=import_module(name="shutil"),
        name="rmtree",
        value=fake_rmtree,
    )
    run_path(path_name=str(object=run.__file__), run_name="__main__")
    expect_true(condition="analyze" in events)
    expect_true(condition="validate" in events)
    expect_true(condition="kill:99" in events)
    expect_true(condition="clear" in events)
    expect_true(condition=len(removed) <= 1)


def test_examples_run_module_reuses_the_recorded_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An adopted demo server skips spawning and termination.

    Args:
        monkeypatch: Pytest patching helper.

    """
    events: list[str] = []

    def reuse_server(*, path: Path) -> tuple[int, int] | None:
        """Return the recorded demo server.

        Args:
            path: Served root directory.

        Returns:
            The recorded process id and port.

        """
        _ = path
        return (4321, 8080)

    def wait_ready(*, url: str, pid: int) -> bool:
        """Report the adopted server as ready.

        Args:
            url: Server origin.
            pid: Spawned process id.

        Returns:
            Always ``True``.

        """
        _ = url
        _ = pid
        events.append(f"ready:{pid}")
        return True

    def terminate(*, pid: int) -> None:
        """Record the terminated process id.

        Args:
            pid: Process id to terminate.

        """
        events.append(f"kill:{pid}")

    class AnalyzerStub:
        """Stand-in for the real ``CssVisualCause`` analyzer."""

        def __init__(self, *, settings: object) -> None:
            """Accept analyzer settings without acting.

            Args:
                settings: Analyzer settings instance.

            """
            _ = settings

        @staticmethod
        def run() -> None:
            """Record the synthetic analysis run."""
            events.append("analyze")

    def fake_validate() -> None:
        """Record the synthetic validation run."""
        events.append("validate")

    monkeypatch.setattr(
        target=server_local,
        name="reuse_server",
        value=reuse_server,
    )
    monkeypatch.setattr(
        target=server_local,
        name="wait_ready",
        value=wait_ready,
    )
    monkeypatch.setattr(
        target=import_module(name="exactus.packages.server.process_control"),
        name="terminate_tree",
        value=terminate,
    )
    monkeypatch.setattr(
        target=import_module(name="exactus.packages.visual_cause"),
        name="CssVisualCause",
        value=AnalyzerStub,
    )
    monkeypatch.setattr(
        target=validate_results,
        name="main",
        value=fake_validate,
    )
    run_path(path_name=str(object=run.__file__), run_name="__main__")
    expect_equal(actual=events, expected=["ready:4321", "analyze", "validate"])
