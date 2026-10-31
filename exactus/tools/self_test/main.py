# Copyright (c) 2026 João Lopes.
"""Probe every tool reachable by this exactus and report the results.

``exactus --self_test`` is the executable's self-diagnostic
catalog tool: it generates a minimal fixture project
in a temporary directory — one HTML, JS, CSS, Python, pytest and
JS-test file plus a ``pyproject.toml`` — then checks every expected
tool twice over. A system-installed executable found on ``PATH`` is
probed first; when absent, the same name is dispatched through the
pyz's own bundled toolchain. That makes the tool valid on a bare
``python:3.13-slim`` container, a development machine with a full
toolchain, and anything in between — each check records which source
answered (``system``, ``bundle``, or ``none``).

After the tool probes the ``unified`` pipeline runs against the temp
fixture — a loopback-only static site ungates ``frontend``, ``record``
and ``visual_cause`` so no network is needed — and every expected
``EXACTUS_RESULTS`` report must be fresh, PASS, and issue-free.
Everything happens inside a temporary directory; like every catalog
tool the only artifact left behind is the standard
``EXACTUS_RESULTS/SELF_TEST`` report bundle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from json import loads
from os import environ, pathsep
from pathlib import Path
from platform import machine, platform
from shutil import which
from socket import create_connection, socket
from sqlite3 import Error, connect
from subprocess import (
    DEVNULL,
    STDOUT,
    CompletedProcess,
    Popen,
    TimeoutExpired,
    run,
)
from sys import argv, executable, stdout
from tempfile import TemporaryDirectory
from textwrap import dedent
from time import monotonic, sleep, time
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from collections.abc import Iterable
    from sqlite3 import Connection
from zipfile import is_zipfile

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Sequence

    from exactus.tools.common.json_types import JsonValue
from exactus.packages.project_python import auto as _project_python_auto
from exactus.packages.steps import step_log, trace
from exactus.tools.common.cli import (
    resolve_exactus_tool_bundle,
    resolve_output,
)
from exactus.tools.common.config import resolve_arguments
from exactus.tools.common.execution import run_exactus
from exactus.tools.common.runtime import (
    Progress,
    emit_progress,
    publish_progress,
)
from exactus.tools.reports.bundle import ReportBundle, ReportPaths
from exactus.tools.self_test.arguments import create_parser as _create_parser

_project_python_active: bool = _project_python_auto.Constants.activated


@final
class Constants:
    """Group module-level constants.

    Attributes:
        cache_root: Grouped module constant.
        probe_args: Grouped module constant.
        tool_probes: Grouped module constant.
        expected_tools: Grouped module constant.
        browser_names: Grouped module constant.
        host_browsers: Grouped module constant.
        windows_browsers: Grouped module constant.
        browser_envs: Grouped module constant.
        system_browsers: Grouped module constant.
        reports: Grouped module constant.
        gated_reports: Grouped module constant.
        run_scoped_env: Grouped module constant.
        run_scoped_prefixes: Grouped module constant.
        fixture: Grouped module constant.
        site_pages: Grouped module constant.

    """

    cache_root: Final[Path] = (
        Path(environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        / "exactus-tools"
        / "embedded"
    )
    probe_args: Final[tuple[tuple[str, ...], ...]] = (
        ("--version",),
        ("--help",),
        ("-h",),
        (),
    )
    tool_probes: Final[dict[str, tuple[tuple[str, ...], str]]] = {
        "basedpyright-langserver": ((), "Connection input stream is not set"),
        "node-which": (("ls",), ""),
        "which": (("ls",), ""),
    }
    expected_tools: Final[frozenset[str]] = frozenset(
        {
            "basedpyright",
            "build",
            "coverage",
            "eslint",
            "exactus-mcp",
            "exactus-mcp-wakeup",
            "htmlhint",
            "jinja2",
            "jslint",
            "mutmut",
            "node",
            "pillow",
            "playwright",
            "prettier",
            "pyrefly",
            "pytest",
            "ruff",
            "stylelint",
            "tsc",
            "twine",
            "uvicorn",
        },
    )
    browser_names: Final[frozenset[str]] = frozenset(
        {
            "chrome",
            "Chromium",
            "Google Chrome",
            "Google Chrome for Testing",
            "headless_shell",
        },
    )
    host_browsers: Final[tuple[str, ...]] = (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        (
            "/Applications/Google Chrome for "
            "Testing.app/Contents/MacOS/Google "
            "Chrome for Testing"
        ),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/lib/chromium/chromium",
        "/usr/lib/chromium-browser/chromium-browser",
        "/snap/bin/chromium",
        "/opt/google/chrome/chrome",
    )
    windows_browsers: Final[tuple[str, ...]] = (
        "Google/Chrome/Application/chrome.exe",
        "Chromium/Application/chrome.exe",
    )
    browser_envs: Final[tuple[str, ...]] = (
        "CHROME_PATH",
        "CHROMIUM_PATH",
        "CHROME_BIN",
        "PUPPETEER_EXECUTABLE_PATH",
        "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH",
    )
    system_browsers: Final[tuple[str, ...]] = (
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "headless_shell",
    )
    reports: Final[tuple[str, ...]] = (
        "COVERAGE_TESTS",
        "DOCS",
        "FRONTEND",
        "KWARGS_TYPEHINTS",
        "LINTS",
        "PERFORMANCE",
        "README",
        "RECORD",
        "VISUAL_CAUSE",
        "PIPELINES/UNIFIED",
    )
    gated_reports: Final[frozenset[str]] = frozenset(
        {"FRONTEND", "RECORD", "VISUAL_CAUSE"},
    )
    run_scoped_env: Final[frozenset[str]] = frozenset(
        {
            "EXACTUS_COLLECT_FILES",
            "EXACTUS_COMPARISON_BASELINE",
            "EXACTUS_CONFIG",
            "EXACTUS_HOST",
            "EXACTUS_ORCHESTRATED",
            "EXACTUS_PIPELINE_RUN_ID",
            "EXACTUS_PMANAGER_WORKER",
            "EXACTUS_PORT",
            "EXACTUS_PROJECT_ROOT",
            "EXACTUS_RECORD_ROOT",
            "EXACTUS_REGISTRY",
            "EXACTUS_REPORTS_ROOT",
            "EXACTUS_REPORT_OUTPUT",
            "EXACTUS_RESULTS",
            "EXACTUS_RESULTS_RELEASE",
            "EXACTUS_ROOT",
            "EXACTUS_RUN_ID",
            "EXACTUS_TOOL",
        },
    )
    run_scoped_prefixes: Final[tuple[str, ...]] = (
        "EXACTUS_ACTION__",
        "EXACTUS_ES__",
        "EXACTUS_RECORDER_FLUSH__",
        "EXACTUS_TOOLS_PAYLOAD__",
    )
    fixture: Final[dict[str, str]] = {
        "pyproject.toml": dedent(
            text=(
                '\n            [project]\n            name = "exactus-self_tes'
                't-fixture"\n            version = "0.1.0"\n            requir'
                'es-python = ">=3.13"\n\n            [tool.pytest.ini_options]'
                '\n            testpaths = ["."]\n            '
            ),
        ).lstrip(),
        "app.py": dedent(
            text=(
                "\n            # Copyright (c) 2026 Project contributors.\n   "
                '         """Small fixture module exercised by the self-test."'
                '""\n\n            from __future__ import annotations\n\n     '
                "       from typing import Final, final\n\n\n            @fina"
                'l\n            class Constants:\n                """Group fix'
                "ture constants.\n\n                Attributes:\n             "
                "       greeting: Grouped module constant.\n\n                "
                '"""\n\n                greeting: Final[str] = "Hello, self_te'
                'st!"\n\n\n            def greet(*, name: str) -> str:\n      '
                '          """Return the greeting shown by the fixture page.\n'
                "\n                Args:\n                    name: Name to gr"
                "eet.\n\n                Returns:\n                    The gre"
                'eting text.\n\n                """\n                return f"'
                'Hello, {name}!"\n\n\n            def add(*, left: int, right:'
                ' int) -> int:\n                """Add two integers.\n\n      '
                "          Args:\n                    left: First operand.\n  "
                "                  right: Second operand.\n\n                R"
                'eturns:\n                    The sum.\n\n                """'
                "\n                return left + right\n            "
            ),
        ).lstrip(),
        "test_app.py": dedent(
            text=(
                "\n            # Copyright (c) 2026 Project contributors.\n   "
                '         """Pytest coverage for the fixture module."""\n\n   '
                "         from __future__ import annotations\n\n            fr"
                "om typing import NoReturn\n\n            from app import Cons"
                "tants, add, greet\n\n\n            def fail(*, message: str) "
                '-> NoReturn:\n                """Fail the running test.\n\n  '
                "              Args:\n                    message: Explanation"
                " of the failed expectation.\n\n                Raises:\n     "
                '               AssertionError: Always.\n\n                """'
                "\n                raise AssertionError(message)\n\n\n        "
                "    def expect_equal(\n                *,\n                ac"
                "tual: str | int,\n                expected: str | int,\n     "
                '       ) -> None:\n                """Require ``actual`` to e'
                "qual ``expected``.\n\n                Args:\n                "
                "    actual: Observed value.\n                    expected: Re"
                'quired value.\n\n                """\n                if actu'
                'al != expected:\n                    fail(message=f"expected '
                '{expected!r}, got {actual!r}")\n\n\n            def test_gree'
                't() -> None:\n                """The greeting includes the su'
                'pplied name."""\n                expect_equal(\n             '
                '       actual=greet(name="self_test"),\n                    e'
                'xpected="Hello, self_test!",\n                )\n\n\n        '
                '    def test_add() -> None:\n                """Two operands '
                'add together."""\n                expect_equal(\n            '
                "        actual=add(left=2, right=3),\n                    exp"
                "ected=5,\n                )\n\n\n            def test_constan"
                'ts() -> None:\n                """The grouped greeting matche'
                's the function output."""\n                expect_equal(\n   '
                "                 actual=Constants.greeting,\n                "
                '    expected=greet(name="self_test"),\n                )\n   '
                "         "
            ),
        ).lstrip(),
        "app.js": dedent(
            text=(
                "\n            /**\n             * Return the greeting shown b"
                "y the fixture page.\n             * @param {string} name Name"
                " to greet.\n             * @returns {string} The greeting tex"
                "t.\n             */\n            export const greet = name =>"
                " `Hello, ${name}!`;\n\n            /**\n             * Add tw"
                "o integers.\n             * @param {number} left First operan"
                "d.\n             * @param {number} right Second operand.\n   "
                "          * @returns {number} The sum.\n             */\n    "
                "        export const add = (left, right) => left + right;\n  "
                "          "
            ),
        ).lstrip(),
        "app.test.mjs": dedent(
            text=(
                '\n            import { add, greet } from "./app.js";\n\n     '
                "       /**\n             * Require two values to compare equa"
                "l.\n             * @param {string | number} actual Observed v"
                "alue.\n             * @param {string | number} expected Requi"
                "red value.\n             * @throws {Error} When the values di"
                "ffer.\n             */\n            const expectEqual = (actu"
                "al, expected) => {\n                if (actual !== expected) "
                "{\n                    throw new Error(`expected ${expected},"
                " got ${actual}`);\n                }\n            };\n\n     "
                '       expectEqual(greet("self_test"), "Hello, self_test!");'
                "\n            expectEqual(add(2, 3), 5);\n            "
            ),
        ).lstrip(),
        "style.css": dedent(
            text=(
                "\n            .page {\n              display: flex;\n        "
                "      flex-direction: column;\n              position: relati"
                "ve;\n            }\n            "
            ),
        ).lstrip(),
        "index.html": dedent(
            text=(
                '\n            <!doctype html>\n            <html lang="en">\n'
                '              <head>\n                <meta charset="utf-8" /'
                '>\n                <meta\n                  name="viewport"\n'
                '                  content="width=device-width, initial-scale='
                '1"\n                />\n                <title>Exactus Fixtur'
                'e</title>\n                <link rel="stylesheet" href="style'
                '.css" />\n              </head>\n              <body>\n      '
                '          <main class="page">\n                  <h1>Exactus '
                "Fixture</h1>\n                  <p data-greeting>Hello</p>\n "
                '                 <script type="module" src="app.js"></script>'
                "\n                </main>\n              </body>\n           "
                " </html>\n            "
            ),
        ).lstrip(),
    }
    site_pages: Final[dict[str, str]] = {
        "index.html": dedent(
            text=(
                "\n                <!doctype html>\n                <html lang"
                '="en">\n                <head>\n                    <meta cha'
                'rset="utf-8">\n                    <title>exactus probe</titl'
                "e>\n                </head>\n                <body>\n        "
                "            <h1>exactus probe site</h1>\n                    "
                '<a href="second.html">second</a>\n                    <form>'
                "\n                    <label>\n                        Name\n"
                '                        <input name="q" type="text">\n       '
                '             </label>\n                    <button type="subm'
                'it">Go</button>\n                    </form>\n               '
                " </body>\n                </html>\n                "
            ),
        ).lstrip(),
        "second.html": dedent(
            text=(
                "\n                <!doctype html>\n                <html lang"
                '="en">\n                <head>\n                    <meta cha'
                'rset="utf-8">\n                    <title>exactus second</tit'
                "le>\n                </head>\n                <body>\n       "
                "             <h1>exactus second page</h1>\n                  "
                '  <a href="index.html">back</a>\n                </body>\n   '
                "             </html>\n                "
            ),
        ).lstrip(),
    }


def say(*, text: str) -> None:
    """Write one report line to standard output.

    Args:
        text: Line content.

    """
    stdout.write(f"{text}\n")
    stdout.flush()


def _preferred_python() -> str:
    """Return the interpreter that should host spawned exactus work.

    The bundles ship CPython-tagged wheels (``cp313`` extensions), so
    spawned tools must run under the interpreter the project uses —
    exported as ``EXACTUS_PROJECT_PYTHON`` by the entrypoint — rather
    than whichever ``python3`` happened to launch the pyz.

    Returns:
        ``EXACTUS_PROJECT_PYTHON`` when exported, else the running
        interpreter.

    """
    return environ.get("EXACTUS_PROJECT_PYTHON", executable)


def self_command(*arguments: str) -> list[str]:
    """Build a command that re-invokes this exactus.

    A zipapp executes directly as ``python <argv0>``; every other form
    (``python -m exactus``, ``python exactus``, an installed console
    script) re-enters through ``python -m exactus`` with
    :func:`subprocess_env` making the package importable.

    Args:
        arguments: Command line placed after the executable.

    Returns:
        Argument vector headed by the running interpreter.

    """
    argv0: Path = Path(argv[0])
    if is_zipfile(filename=argv0):
        return [_preferred_python(), str(object=argv0.resolve()), *arguments]
    return [_preferred_python(), "-m", "exactus", *arguments]


def bundle_launcher() -> Path | None:
    """Return the current context's bundle dispatch launcher.

    ``resolve_exactus_tool_bundle`` answers the same question the
    dispatcher asks: inside a zipapp it materializes the embedded
    bundle matching this build, while a source checkout resolves its
    own ``exactus/bundle/<host>/`` leaf — never an arbitrary cache
    directory left over from an older build.

    Returns:
        The bundle's ``__main__.py``, or ``None`` when no bundle is
        available for this platform.

    """
    return resolve_exactus_tool_bundle(root=Path.cwd())


def bundle_command(*arguments: str) -> list[str] | None:
    """Build a command that dispatches a bundled third-party tool.

    The resolved bundle launcher performs the same job in every mode —
    a zipapp materializes its own embedded leaf, a source checkout
    resolves its ``exactus/bundle/<host>/`` leaf — so probes always
    exercise the toolchain this exactus actually ships.

    Args:
        arguments: Tool name plus its own arguments.

    Returns:
        The dispatch command, or ``None`` when no bundle resolves.

    """
    launcher: Path | None = bundle_launcher()
    if launcher is None:
        return None
    return [_preferred_python(), str(object=launcher), *arguments]


def subprocess_env() -> dict[str, str] | None:
    """Return the environment self-test subprocesses must inherit.

    Outside a zipapp, ``python -m exactus`` only resolves when the
    package's parent directory is importable, so ``PYTHONPATH`` is
    prepended with the source/install root derived from ``__file__``.

    Returns:
        An adjusted environment, or ``None`` to inherit the parent's.

    """
    if is_zipfile(filename=Path(argv[0])):
        return None
    root: str = str(object=Path(__file__).resolve().parents[3])
    env: dict[str, str] = dict(environ)
    inherited: str = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        root if not inherited else f"{root}{pathsep}{inherited}"
    )
    return env


def pipeline_env() -> dict[str, str]:
    """Return the nested pipeline's environment with a fresh context.

    The fixture pipeline owns its own ``EXACTUS_RESULTS/.runtime``
    registry and pmanager coordination files, so every run-scoped
    ``EXACTUS_*`` variable inherited from the outer run — the registry
    path, run identity, and orchestration flags — is removed; without
    that the inner run would register into the outer project's
    ``runs.db`` and conflict with the pipeline already running there.
    Toolchain variables (``EXACTUS_PROJECT_PYTHON``,
    ``EXACTUS_LINTER_TOOLCHAIN``, the cache/verify flags, and
    ``EXACTUS_MCP_*`` settings) stay because they describe the local
    installation, not a run.

    Returns:
        Environment free of run-scoped ``EXACTUS_*`` variables.

    """
    env: dict[str, str] = dict(subprocess_env() or environ)
    for name in Constants.run_scoped_env:
        _ = env.pop(name, None)
    for name in tuple(env):
        if name.startswith(Constants.run_scoped_prefixes):
            _ = env.pop(name, None)
    return env


def describe_command(
    *,
    command: list[str],
    timeout: int = 120,
    cwd: Path | None = None,
    marker: str = "",
) -> tuple[bool, str]:
    """Run one command and report its outcome.

    Args:
        command: Argument vector to run.
        timeout: Seconds before the probe is killed.
        cwd: Optional working directory for the child process.
        marker: Output substring proving liveness on a nonzero exit.

    Returns:
        Success flag and a human-readable failure reason.

    """
    label: str = " ".join(command)
    try:
        result: CompletedProcess[bytes] = run(
            args=command,
            check=False,
            capture_output=True,
            cwd=str(object=cwd) if cwd is not None else None,
            env=subprocess_env(),
            stdin=DEVNULL,
            timeout=timeout,
        )
    except TimeoutExpired:
        return (False, f"{label} timed out after {timeout}s")
    except OSError as error:
        return (False, f"{label} could not start: {error}")
    output: str = (
        ((result.stdout or b"") + (result.stderr or b""))
        .decode(encoding="utf-8", errors="replace")
        .strip()
    )
    if result.returncode == 0 or (marker and marker in output):
        return (True, "")
    tail: str = output.splitlines()[-1] if output else "no output"
    return (False, f"{label} exited {result.returncode}: {tail[:160]}")


def describe(*arguments: str, timeout: int = 120) -> tuple[bool, str]:
    """Re-invoke this exactus with ``arguments`` and report the outcome.

    Args:
        arguments: Command line run after the executable.
        timeout: Seconds before the probe is killed.

    Returns:
        Success flag and a human-readable failure reason.

    """
    return describe_command(command=self_command(*arguments), timeout=timeout)


def _mutmut_cwd() -> Path:
    """Create a temporary directory with a minimal mutmut config.

    ``mutmut`` refuses to run without ``source_paths`` configured; a
    throw-away ``setup.cfg`` satisfies the parser without touching the
    real project.

    Returns:
        Directory containing a valid ``setup.cfg``.

    """
    temporary: Path = Path(TemporaryDirectory(prefix="exactus-mutmut-").name)
    temporary.mkdir(parents=True, exist_ok=True)
    _ = (temporary / "setup.cfg").write_text(
        data="[mutmut]\nsource_paths = src\n",
        encoding="utf-8",
    )
    return temporary


def describe_bundle(
    *arguments: str,
    timeout: int = 120,
    cwd: Path | None = None,
    marker: str = "",
) -> tuple[bool, str]:
    """Dispatch a bundled third-party tool and report its outcome.

    Args:
        arguments: Tool name plus its own arguments.
        timeout: Seconds before the probe is killed.
        cwd: Optional working directory for the child process.
        marker: Output substring proving liveness on a nonzero exit.

    Returns:
        Success flag and a human-readable failure reason.

    """
    command: list[str] | None = bundle_command(*arguments)
    if command is None:
        return (False, "no materialized bundle to dispatch")
    return describe_command(
        command=command,
        timeout=timeout,
        cwd=cwd,
        marker=marker,
    )


def probe_tool(*, tool: str) -> tuple[bool, str, str]:
    """Probe one tool, system executable first, bundle as fallback.

    Args:
        tool: Tool name tried on ``PATH`` then through the pyz.

    Returns:
        Success flag, a human-readable failure reason, and which
        source answered: ``system``, ``bundle``, or ``none``.

    """
    cwd: Path | None = _mutmut_cwd() if tool == "mutmut" else None
    custom: tuple[tuple[str, ...], str] | None = Constants.tool_probes.get(
        tool,
    )
    flagsets: tuple[tuple[str, ...], ...] = (
        (custom[0],) if custom is not None else Constants.probe_args
    )
    marker: str = custom[1] if custom is not None else ""
    system: str | None = which(cmd=tool)
    if system is not None:
        for flags in flagsets:
            ok, _ = describe_command(
                command=[system, *flags],
                cwd=cwd,
                marker=marker,
            )
            if ok:
                return (True, "", "system")
    reasons: list[str] = []
    for flags in flagsets:
        ok, reason = describe_bundle(tool, *flags, cwd=cwd, marker=marker)
        if ok:
            return (True, "", "bundle")
        reasons.append(reason)
    return (False, "; ".join(reasons), "none")


def probe_chromium() -> tuple[bool, str, str]:
    """Launch a Chromium binary — system first, then the bundle's.

    Components materialize under the ``exactus-tools`` cache; browser
    system libraries are supplied by the environment, matching how a
    real deployment satisfies them.

    Returns:
        Success flag, a human-readable failure reason, and which
        source answered.

    """
    for name in Constants.system_browsers:
        system: str | None = which(cmd=name)
        if system is None:
            continue
        ok, reason = describe_command(
            command=[system, "--version"],
            timeout=60,
        )
        if ok:
            return (True, "", "system")
    reason: str = "no Chromium binary found"
    for candidate in host_browsers():
        ok, reason = describe_command(
            command=[str(object=candidate), "--version"],
            timeout=60,
        )
        if ok:
            return (True, "", "system")
    search_root: Path | None
    for name, search_root in (
        ("playwright", playwright_browsers()),
        ("bundle", Constants.cache_root.parent),
    ):
        if search_root is None or not search_root.is_dir():
            continue
        binary: Path | None = next(
            (
                path
                for path in sorted(search_root.rglob(pattern="*"))
                if path.is_file() and path.name in Constants.browser_names
            ),
            None,
        )
        if binary is not None:
            ok, reason = describe_command(
                command=[str(object=binary), "--version"],
                timeout=60,
            )
            if ok:
                return (True, "", name)
    return (False, reason, "none")


def browser_candidates() -> Iterable[Path]:
    """Yield configured and conventional browser paths.

    Yields:
        Browser candidates in deterministic precedence order.

    """
    for name in Constants.browser_envs:
        if raw := environ.get(name):
            yield Path(raw)
    yield from map(Path, Constants.host_browsers)
    home: Path = Path.home()
    for name in ("Google Chrome", "Chromium", "Google Chrome for Testing"):
        yield (
            home / "Applications" / f"{name}.app" / "Contents" / "MacOS" / name
        )
    for base_var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if base := environ.get(base_var):
            for relative in Constants.windows_browsers:
                yield Path(base).joinpath(*relative.split(sep="/"))


def host_browsers() -> Iterable[Path]:
    """Yield well-known browser install locations on this host.

    Environment overrides are honored first, followed by the common
    macOS, Linux, and Windows install locations — every candidate is
    checked for existence, so the list stays silent on hosts (and
    containers) where nothing is installed.

    Yields:
        Existing executable candidates in deterministic order.

    """
    seen: set[Path] = set()
    for path in browser_candidates():
        if path.is_file() and path not in seen:
            seen.add(path)
            yield path


def playwright_browsers() -> Path | None:
    """Resolve the host's Playwright browsers directory.

    Returns:
        The ``ms-playwright`` directory for this platform, or
        ``None`` when it does not exist.

    """
    override: str | None = environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if override:
        root: Path = Path(override)
        return root if root.is_dir() else None
    home: Path = Path.home()
    for root in (
        home / "Library" / "Caches" / "ms-playwright",
        home / ".cache" / "ms-playwright",
        home / "AppData" / "Local" / "ms-playwright",
    ):
        if root.is_dir():
            return root
    return None


def serve_display() -> Popen[bytes] | None:
    """Start a virtual X display for headed browser tools.

    ``record`` and ``visual_cause`` can launch Chromium headed, so
    they need ``DISPLAY`` even though nothing is ever shown;
    ``xvfb-run`` is avoided because it needs ``xauth``, which the
    Playwright dependency set does not install.

    Returns:
        The running ``Xvfb`` process, or ``None`` when the system
        has no ``Xvfb`` binary or no free display.

    """
    xvfb: str | None = which(cmd="Xvfb")
    if xvfb is None:
        return None
    for number in range(99, 110):
        display: str = f":{number}"
        server: Popen[bytes] = Popen(
            args=[xvfb, display, "-screen", "0", "1280x800x24"],
            stdin=DEVNULL,
            stdout=DEVNULL,
            stderr=DEVNULL,
        )
        sleep(1)
        if server.poll() is None:
            environ["DISPLAY"] = display
            return server
    return None


def free_port() -> int:
    """Reserve an ephemeral loopback port for the demo site.

    Returns:
        A port number the site server can bind immediately.

    """
    with socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return cast(typ="int", val=probe.getsockname()[1])


def serve_site(*, directory: Path, port: int) -> Popen[bytes]:
    """Publish a clean two-page site for the url-gated tools.

    ``frontend``, ``record`` and ``visual_cause`` only join a
    pipeline when handed ``--url``/``--workspace``/``--actions``;
    a local static site gives them a target that cannot produce
    4xx/5xx or console findings.

    Args:
        directory: Temp directory receiving the site pages.
        port: Loopback port the server binds.

    Returns:
        The running ``http.server`` process.

    Raises:
        RuntimeError: When the demo site does not become reachable
            within the readiness deadline.

    """
    site: Path = directory / "site"
    site.mkdir(parents=True, exist_ok=True)
    for name, content in Constants.site_pages.items():
        _ = (site / name).write_text(data=content, encoding="utf-8")
    server: Popen[bytes] = Popen(
        args=[
            _preferred_python(),
            "-m",
            "http.server",
            str(object=port),
            "--bind",
            "127.0.0.1",
            "--directory",
            str(object=site),
        ],
        stdin=DEVNULL,
        stdout=DEVNULL,
        stderr=DEVNULL,
    )
    deadline: float = monotonic() + 30
    while monotonic() < deadline:
        try:
            with create_connection(address=("127.0.0.1", port), timeout=2):
                return server
        except OSError:
            sleep(0.5)
    server.kill()
    msg: str = "demo site did not start"
    raise RuntimeError(msg)


def _inner_pipeline_progress(*, project: Path, checks: Checks) -> None:
    """Read the inner pipeline registry and reflect its progress.

    The nested ``exactus --pipeline unified`` process writes its own
    orchestrator state under ``EXACTUS_RESULTS/.runtime``. Polling that
    registry lets the outer self_test progress bar fill the ``unified``
    check's slice with real inner progress — how many inner tools have
    finished — so a host watching the container sees work advancing
    instead of only an elapsed-time pulse.

    Args:
        project: Fixture directory holding the inner
            ``EXACTUS_RESULTS`` tree.
        checks: Accumulated check outcomes; re-emits progress.

    """
    registry: Path = project / "EXACTUS_RESULTS" / ".runtime" / "runs.db"
    if not registry.is_file():
        return
    try:
        connection: Connection = connect(
            database=str(object=registry),
            timeout=1,
        )
        with connection:
            total: int = connection.execute(
                "select count(*) from runs",
            ).fetchone()[0]
            done: int = connection.execute(
                "select count(*) from runs where status != 'RUNNING'",
            ).fetchone()[0]
    except Error:
        return
    if total == 0:
        return
    completed: int = len(checks.entries)
    planned: int = max(checks.planned, completed + 1)
    publish_progress(
        progress=Progress(
            state="RUNNING",
            completed=done,
            total=total,
            step=f"pipeline: unified ({done}/{total} inner tools)",
            span=(completed / planned, (completed + 1) / planned),
        ),
    )


def stop_process(*, process: Popen[bytes]) -> int | None:
    """Terminate one helper process, escalating to ``kill``.

    Args:
        process: Spawned helper to stop.

    Returns:
        The process exit status.

    """
    process.terminate()
    try:
        return process.wait(timeout=15)
    except TimeoutExpired:
        process.kill()
        return process.wait()


def write_fixture(*, project: Path) -> None:
    """Generate the seven-file fixture project in ``project``.

    Args:
        project: Temp directory receiving the fixture files.

    """
    project.mkdir(parents=True, exist_ok=True)
    for name, content in Constants.fixture.items():
        _ = (project / name).write_text(data=content, encoding="utf-8")


def probe_pipeline(
    *,
    checks: Checks,
    project: Path,
    url: str | None,
    log: Path,
) -> tuple[bool, str]:
    """Run the unified pipeline against the fixture project.

    The inner pipeline is the longest stage by far. Its output goes
    to ``log`` — never the tool's own pipes: an orphaned pipeline
    worker holding the inherited descriptors would hang the worker
    supervisor waiting for EOF, and inheriting stdin lets a nested
    prompt block forever. While it runs, the outer progress bar
    pulses with the elapsed time.

    Args:
        checks: Accumulated check outcomes; supplies the progress
            counts the pulses re-emit.
        project: Fixture directory the pipeline runs against.
        url: Demo-site URL unlocking the browser tools, or ``None``
            when no browser is available — the url-gated tools then
            skip instead of failing.
        log: Artifact file receiving the pipeline's combined output.

    Returns:
        Success flag and a human-readable failure reason.

    """
    gated: tuple[str, ...] = (
        ()
        if url is None
        else (
            "--tool-arg",
            f"frontend::--url={url}",
            "--tool-arg",
            f"record::--url={url}",
            "--tool-arg",
            "record::--crawl",
            "--tool-arg",
            "record::--headless",
            "--tool-arg",
            "record::--max-depth=1",
            "--tool-arg",
            "record::--max-states=4",
            "--tool-arg",
            f"visual_cause::--url={url}",
            "--tool-arg",
            f"visual_cause::--url-b={url}second.html",
            "--tool-arg",
            "visual_cause::--fail-on=never",
        )
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open(mode="wb") as stream:
        process: Popen[bytes] = Popen(
            args=[
                *self_command(),
                "--root",
                str(object=project),
                "--pipeline",
                "unified",
                "--exclude-tools",
                "self_test",
                *gated,
            ],
            cwd=project,
            env=pipeline_env(),
            stdin=DEVNULL,
            stdout=stream,
            stderr=STDOUT,
        )
        started: float = monotonic()
        while process.poll() is None:
            sleep(5)
            _inner_pipeline_progress(project=project, checks=checks)
            checks.pulse(
                step=(
                    f"pipeline: unified ({monotonic() - started:.0f}s elapsed)"
                ),
            )
    if process.returncode != 0:
        return (
            False,
            f"unified pipeline exited {process.returncode} — see {log}",
        )
    return (True, "")


def probe_report(
    *,
    project: Path,
    relative: str,
    started: float,
) -> tuple[bool, str, dict[str, JsonValue]]:
    """Check one generated report for freshness and zero issues.

    Args:
        project: Fixture directory holding ``EXACTUS_RESULTS``.
        relative: Report directory under ``EXACTUS_RESULTS``.
        started: Pipeline start timestamp; older reports are stale.

    Returns:
        Success flag, a human-readable failure reason, and the
        report fields collected for the JSON summary.

    """
    report: Path = project / "EXACTUS_RESULTS" / relative / "result.json"
    detail: dict[str, JsonValue] = {"path": str(object=report)}
    if not report.is_file():
        return (False, "result.json missing", detail)
    if report.stat().st_mtime < started:
        return (False, "report predates this run", detail)
    try:
        data: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=report.read_text(encoding="utf-8")),
        )
    except (OSError, ValueError) as error:
        return (False, f"unreadable result.json: {error}", detail)
    if not isinstance(data, dict):
        return (False, "result.json is not an object", detail)
    status: JsonValue = data.get("status")
    passed: JsonValue = data.get("passed")
    run_data: JsonValue = data.get("run") or {}
    exit_code: JsonValue = (
        run_data.get("exit_code") if isinstance(run_data, dict) else None
    )
    duration: JsonValue = (
        run_data.get("duration_seconds")
        if isinstance(run_data, dict)
        else data.get("duration_seconds")
    )
    summary: JsonValue = data.get("summary") or {}
    findings: JsonValue = (
        summary.get("findings_total") if isinstance(summary, dict) else None
    )
    detail.update(
        {
            "status": status,
            "passed": passed,
            "exit_code": exit_code,
            "findings_total": findings,
            "duration_seconds": duration,
        },
    )
    problems: list[str] = []
    if status != "PASS":
        problems.append(f"status={status!r}")
    if passed is False:
        problems.append(f"passed={passed!r}")
    if exit_code is not None and exit_code != 0:
        problems.append(f"exit_code={exit_code!r}")
    if isinstance(findings, int) and findings != 0:
        problems.append(f"findings_total={findings}")
    if problems:
        return (False, ", ".join(problems), detail)
    return (True, "", detail)


@final
@dataclass(slots=True)
class Checks:
    """Accumulate structured check outcomes for the report.

    Attributes:
        entries: Check outcomes in execution order.
        failed: Names of failed checks.
        skipped: Names of skipped checks.
        planned: Expected total check count driving the progress bar;
            refined once the bundle's tool list is known.

    """

    entries: list[dict[str, JsonValue]] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    planned: int = len(Constants.expected_tools) + len(Constants.reports) + 5

    def note(
        self,
        *,
        kind: str,
        name: str,
        status: str,
        reason: str = "",
        detail: dict[str, JsonValue] | None = None,
    ) -> None:
        """Print one result line and record it for the report.

        Args:
            kind: Check category (cli, stage, tool, binary, pipeline,
                report).
            name: Check label printed on the line.
            status: ``PASS``, ``FAIL``, or ``SKIP``.
            reason: Human-readable failure or skip reason.
            detail: Extra fields merged into the JSON entry.

        """
        suffix: str = f" — {reason}" if reason else ""
        say(text=f"{status} {name}{suffix}")
        entry: dict[str, JsonValue] = {
            "kind": kind,
            "name": name,
            "status": status,
            "reason": reason,
        }
        if detail:
            entry.update(detail)
        self.entries.append(entry)
        if status == "FAIL":
            self.failed.append(name)
        elif status == "SKIP":
            self.skipped.append(name)
        self.pulse(step=f"{kind}: {name}")

    def pulse(self, *, step: str) -> None:
        """Re-emit the current counts so the bar still advances.

        Long-running stages — the nested pipeline above all — call
        this so the displayed step changes even though no new check
        has completed yet.

        Args:
            step: Current step label shown on the progress bar.

        """
        emit_progress(
            state="RUNNING",
            completed=len(self.entries),
            total=max(self.planned, len(self.entries)),
            step=step,
        )


def _findings(*, checks: Checks) -> list[JsonValue]:
    """Convert failed checks into normalized report findings.

    Args:
        checks: Accumulated check outcomes.

    Returns:
        One finding entry per failed check.

    """
    findings: list[JsonValue] = []
    index: int = 0
    for entry in checks.entries:
        if entry["status"] != "FAIL":
            continue
        index += 1
        finding: dict[str, JsonValue] = {
            "id": f"SEL-{index:03d}",
            "title": f"self_test {entry['kind']} check failed",
            "severity": "error",
            "rule": f"self_test-{entry['kind']}",
            "path": str(object=entry["name"]),
            "file": str(object=entry["name"]),
            "line": 0,
            "message": str(object=entry["reason"] or "check failed"),
            "blocking": True,
        }
        findings.append(finding)
    return findings


def _data(
    *,
    checks: Checks,
    findings: list[JsonValue],
    root: Path,
    project: Path,
) -> dict[str, JsonValue]:
    """Build the normalized report payload.

    Args:
        checks: Accumulated check outcomes.
        findings: Normalized findings built from failed checks.
        root: Project root recorded in the payload.
        project: Temp fixture directory the run executed against.

    Returns:
        ``summary``, ``scope``, ``findings`` and ``extension`` blocks
        plus the ``resume`` line lifted into the envelope.

    """
    total: int = len(checks.entries)
    resume: str = (
        f"{total - len(checks.failed) - len(checks.skipped)}/{
            total
        } checks passed — "
        f"{len(checks.failed)} failed, {len(checks.skipped)} skipped"
    )
    return {
        "status": "PASS" if not checks.failed else "FAIL",
        "project_root": str(object=root),
        "resume": resume,
        "summary": {
            "checks": total,
            "passed": total - len(checks.failed) - len(checks.skipped),
            "failed": len(checks.failed),
            "skipped": len(checks.skipped),
            "findings": len(findings),
            "findings_total": len(findings),
            "severity": {"error": len(findings), "warning": 0, "info": 0},
        },
        "findings": findings,
        "scope": {"include": [], "exclude": []},
        "extension": {
            "platform": platform(),
            "machine": machine(),
            "executable": str(object=Path(argv[0]).resolve()),
            "fixture": str(object=project),
            "checks": cast(typ="list[JsonValue]", val=checks.entries),
        },
    }


def _markdown(*, checks: Checks) -> str:
    """Render the Markdown report body from the check outcomes.

    Args:
        checks: Accumulated check outcomes.

    Returns:
        Markdown listing every probe result.

    """
    lines: list[str] = ["## Checks", ""]
    for entry in checks.entries:
        reason: str = f" — {entry['reason']}" if entry.get("reason") else ""
        lines.append(f"- **{entry['status']}** `{entry['name']}`{reason}")
    lines.append("")
    return "\n".join(lines)


def bundle_tools() -> list[str] | None:
    """List the tools declared by the materialized bundle.

    Returns:
        Sorted dispatch names, or ``None`` when this executable has
        no materialized bundle (a pyz without a compatible leaf).

    """
    launcher: Path | None = bundle_launcher()
    if launcher is None:
        return None
    listing: CompletedProcess[str] = run(
        args=[_preferred_python(), str(object=launcher), "list-tools"],
        check=False,
        capture_output=True,
        env=subprocess_env(),
        stdin=DEVNULL,
        text=True,
        timeout=120,
    )
    if listing.returncode != 0:
        return None
    return sorted(listing.stdout.split())


def probe_tools(*, checks: Checks) -> list[str]:
    """Probe every expected tool and record per-source outcomes.

    Args:
        checks: Accumulated check outcomes.

    Returns:
        The bundle-declared tool list, or the expected set when no
        bundle materialized.

    """
    listed: list[str] | None = bundle_tools()
    if listed is None:
        checks.note(
            kind="stage",
            name="list-tools",
            status="SKIP",
            reason="no materialized bundle",
        )
        tools: list[str] = sorted(Constants.expected_tools)
    else:
        tools = sorted(set(listed) | Constants.expected_tools)
        checks.planned = len(tools) + len(Constants.reports) + 5
        for tool in sorted(Constants.expected_tools - set(listed)):
            checks.note(
                kind="tool",
                name=tool,
                status="SKIP",
                reason="not declared by bundle list-tools",
                detail={"source": "none"},
            )
    say(text=f"==> Probing {len(tools)} tools (system first, then bundle)")
    for tool in tools:
        ok, reason, source = probe_tool(tool=tool)
        checks.note(
            kind="tool",
            name=tool,
            status="PASS" if ok else "FAIL",
            reason=reason,
            detail={"source": source},
        )
    return tools


def run_checks(*, checks: Checks, project: Path, artifacts: Path) -> None:
    """Run every check, recording outcomes instead of exiting.

    Args:
        checks: Accumulated check outcomes.
        project: Temp fixture directory generated for this run.
        artifacts: Tool artifact directory receiving the nested
            pipeline's log.

    """
    emit_progress(
        state="RUNNING",
        completed=0,
        total=checks.planned,
        step="self_test: cli probe",
    )
    ok, reason = describe("--version")
    if not ok:
        ok, reason = describe("--help")
    checks.note(
        kind="cli",
        name="exactus",
        status="PASS" if ok else "FAIL",
        reason=reason,
    )
    if not ok:
        return
    say(text="==> Materializing embedded bundle")
    ok, reason = describe_bundle("node", "--version", timeout=600)
    if not ok:
        ok, reason = describe_bundle("node", "--help", timeout=600)
    checks.note(
        kind="stage",
        name="materialization",
        status="PASS" if ok else "FAIL",
        reason=reason,
    )
    probe_tools(checks=checks)
    browser_ok, reason, source = probe_chromium()
    checks.note(
        kind="binary",
        name="chromium",
        status="PASS" if browser_ok else "SKIP",
        reason=reason,
        detail={"source": source},
    )
    display: Popen[bytes] | None = serve_display()
    checks.note(
        kind="stage",
        name="xvfb",
        status="SKIP" if display is None else "PASS",
        reason="no usable Xvfb display" if display is None else "",
    )
    say(text="==> Starting local demo site")
    server: Popen[bytes] | None = None
    port: int = free_port()
    try:
        server = serve_site(directory=project, port=port)
    except (OSError, RuntimeError) as error:
        checks.note(
            kind="stage",
            name="demo-site",
            status="FAIL",
            reason=str(object=error),
        )
    if server is not None:
        try:
            say(
                text=(
                    "==> Running unified pipeline on "
                    "the generated fixture tree"
                ),
            )
            started: float = time()
            ok, reason = probe_pipeline(
                checks=checks,
                project=project,
                url=f"http://127.0.0.1:{port}/" if browser_ok else None,
                log=artifacts / "pipeline.log",
            )
            checks.note(
                kind="pipeline",
                name="unified",
                status="PASS" if ok else "FAIL",
                reason=reason,
            )
            say(text="==> Verifying generated reports")
            for relative in Constants.reports:
                if relative in Constants.gated_reports and (not browser_ok):
                    checks.note(
                        kind="report",
                        name=f"report {relative}",
                        status="SKIP",
                        reason="no browser available",
                    )
                    continue
                ok, reason, detail = probe_report(
                    project=project,
                    relative=relative,
                    started=started,
                )
                checks.note(
                    kind="report",
                    name=f"report {relative}",
                    status="PASS" if ok else "FAIL",
                    reason=reason,
                    detail=detail,
                )
        finally:
            _ = stop_process(process=server)
    if display is not None:
        _ = stop_process(process=display)


def create_parser() -> ArgumentParser:
    """Return the shared CLI grammar used by execution and completion.

    Returns:
        Configured tool argument parser.

    """
    return _create_parser()


def parse_args(*, arguments: tuple[str, ...] | None = None) -> Namespace:
    """Parse args.

    Args:
        arguments: Arguments.

    Returns:
        The resulting value.

    """
    parser: ArgumentParser = create_parser()
    return parser.parse_args(
        args=resolve_arguments(
            tool="self_test",
            parser=parser,
            arguments=arguments,
        ),
    )


def main(*, arguments: Sequence[str] | None = None) -> int:
    """Generate the fixture, probe every tool, and emit the report.

    Args:
        arguments: Command-line arguments; ``argv[1:]`` when omitted.

    Returns:
        Exit status: zero when all checks pass.

    """
    options: Namespace = parse_args(
        arguments=None if arguments is None else tuple(arguments),
    )
    root: Path = cast(typ="Path", val=options.root).resolve()
    output_dir: Path = resolve_output(
        root=root,
        output=cast(typ="Path", val=options.output_dir),
    )
    with step_log(path=output_dir / "ARTIFACTS" / "steps.txt"):
        trace(
            step=(f"self_test: arguments — root {root}, output {output_dir}"),
        )
        checks: Checks = Checks()
        with TemporaryDirectory(prefix="exactus-self_test-") as temporary:
            project: Path = Path(temporary) / "repo"
            write_fixture(project=project)
            trace(step="self_test: run start")
            run_checks(
                checks=checks,
                project=project,
                artifacts=output_dir / "ARTIFACTS",
            )
            total: int = len(checks.entries)
            passed: int = total - len(checks.failed) - len(checks.skipped)
            say(
                text=f"==> {passed}/{total} checks passed"
                + (
                    f" ({len(checks.skipped)} skipped)"
                    if checks.skipped
                    else ""
                ),
            )
            if checks.failed:
                say(text="==> Failed: " + ", ".join(checks.failed))
            findings: list[JsonValue] = _findings(checks=checks)
            trace(step="stage: report", depth=1)
            _ = ReportBundle.write(
                paths=ReportPaths(
                    markdown=output_dir / "result.md",
                    json=output_dir / "result.json",
                    web=output_dir / "result_web",
                ),
                analyzer="self_test",
                title="Self Test Exactus",
                markdown=_markdown(checks=checks),
                data=_data(
                    checks=checks,
                    findings=findings,
                    root=root,
                    project=project,
                ),
            )
            trace(
                step=f"report: bundle written — {output_dir / 'result.md'}",
                depth=2,
            )
        status: int = 1 if checks.failed else 0
        emit_progress(
            state="FAIL" if checks.failed else "DONE",
            completed=len(checks.entries),
            total=len(checks.entries),
            step="self_test: report",
        )
        trace(step=f"self_test: run finished — status {status}")
        return status


if __name__ == "__main__":
    raise SystemExit(
        run_exactus(
            analyzer="self_test",
            title="Self Test Exactus",
            main=main,
        ),
    )
