# Copyright (c) 2026
"""Loopback server helpers: logs, ports, probing and lifecycle."""

from __future__ import annotations

from os import getpid
from textwrap import dedent
from time import monotonic, sleep
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from exactus.packages.server import local
from exactus.packages.server.diagnostics import parse_server_log
from exactus.tests.common.support import (
    Constant,
    expect_equal,
    expect_false,
    expect_none,
    expect_true,
    require,
)
from exactus.tools.common import process_control as pc

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import Popen

    from exactus.packages.server.diagnostics import ServerDiagnostic


def _wait(predicate: Callable[[], bool], seconds: float = 10.0) -> bool:
    """Poll until ``predicate`` holds.

    Args:
        predicate: Condition to await.
        seconds: Maximum wait.

    Returns:
        Whether the condition became true.

    """
    deadline: float = monotonic() + seconds
    while monotonic() < deadline:
        if predicate():
            return True
        sleep(0.05)
    return False


def test_parse_server_log(tmp_path: Path) -> None:
    """Access logs yield deduplicated 4xx/5xx diagnostics.

    Args:
        tmp_path: Per-test temporary directory.

    """
    log: Path = tmp_path / "server.log"
    log.write_text(
        data=dedent(
            text=(
                '    [stderr] 127.0.0.1 - - [d] "GET /a HTTP/1.1" 404 -\n '
                '   [stderr] 127.0.0.1 - - [d] "GET /a HTTP/1.1" 404 -\n  '
                '  [stdout] 127.0.0.1 - - [d] "POST /b HTTP/1.1" 500 -\n  '
                '  [stdout] 127.0.0.1 - - [d] "GET /ok HTTP/1.1" 200 -\n  '
                "  noise\n    "
            ),
        ),
        encoding="utf-8",
    )
    found: tuple[ServerDiagnostic, ...] = parse_server_log(path=log)
    expect_equal(
        actual=[(d.url, d.status, d.severity) for d in found],
        expected=[("/a", 404, "warning"), ("/b", 500, "error")],
    )
    expect_equal(actual=found[0].stream, expected="stderr")
    expect_equal(
        actual=parse_server_log(path=tmp_path / "missing.log"),
        expected=(),
    )


def test_accepts_free_port_and_state(tmp_path: Path) -> None:
    """Port probing and state-file naming are deterministic.

    Args:
        tmp_path: Per-test temporary directory.

    """
    port: int = local.free_port()
    expect_false(
        condition=local.accepts(host="127.0.0.1", port=port, timeout=0.2),
    )
    expect_equal(
        actual=local.server_state_path(path=tmp_path),
        expected=local.server_state_path(path=tmp_path),
    )
    local.clear_server_state(path=tmp_path)


def test_probe_and_wait_for_dead_process() -> None:
    """A dead pid short-circuits probing and waiting."""
    expect_none(value=local.probe_default_url(pid=0, timeout=0.2))
    expect_false(
        condition=local.wait_ready(
            url="http://127.0.0.1:1/",
            pid=0,
            timeout=0.2,
        ),
    )


def test_probe_default_url_finds_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first accepting default host is reported.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=local,
        name="accepts",
        value=Constant(value=True),
    )
    expect_true(
        condition=require(
            value=local.probe_default_url(pid=getpid()),
        ).startswith("http://"),
    )
    monkeypatch.setattr(
        target=local,
        name="accepts",
        value=Constant(value=False),
    )
    expect_none(value=local.probe_default_url(pid=getpid(), timeout=0.2))
    expect_false(
        condition=local.wait_ready(
            url="https://localhost/",
            pid=getpid(),
            timeout=0.2,
        ),
    )


def test_serve_ping_reuse_and_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A served directory answers the identity ping and can be reused.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setenv(
        name="XDG_CACHE_HOME",
        value=str(object=tmp_path / "cache"),
    )
    site: Path = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(data="hi", encoding="utf-8")
    pid, url, reused = local.serve(path=site, log=tmp_path / "s.log")
    try:
        expect_false(condition=reused)
        expect_true(condition=local.wait_ready(url=url, pid=pid))
        port: int = int(url.rsplit(sep=":", maxsplit=1)[1].strip("/"))
        expect_true(condition=local.ping_server(port=port))
        expect_equal(
            actual=local.reuse_server(path=site),
            expected=(pid, port),
        )
        expect_false(
            condition=local.ping_server(port=local.free_port(), timeout=0.2),
        )
        state: Path = local.server_state_path(path=site)
        state.write_text(data="[]", encoding="utf-8")
        expect_none(value=local.reuse_server(path=site))
        state.write_text(data='{"pid": "x"}', encoding="utf-8")
        expect_none(value=local.reuse_server(path=site))
        state.write_text(data="{bad", encoding="utf-8")
        expect_none(value=local.reuse_server(path=site))
        state.write_text(
            data=f'{{"pid": 0, "port": {port}}}',
            encoding="utf-8",
        )
        expect_none(value=local.reuse_server(path=site))
    finally:
        pc.terminate_tree(pid=pid)
        local.clear_server_state(path=site)
    expect_false(condition=local.server_state_path(path=site).exists())


def test_start_entrypoint_exports_port(tmp_path: Path) -> None:
    """Entrypoint scripts receive the assigned port and log output.

    Args:
        tmp_path: Per-test temporary directory.

    """
    script: Path = tmp_path / "srv.py"
    script.write_text(
        data=dedent(
            text=(
                "    import os,sys,time\n    print('port', os.environ['EXA"
                "CTUS_PORT'], flush=True)\n    print('err', file=sys.stder"
                "r, flush=True)\n    time.sleep(30)\n    "
            ),
        ),
        encoding="utf-8",
    )
    log: Path = tmp_path / "e.log"
    pid, port = local.start_entrypoint(path=script, log=log)
    try:
        expect_true(
            condition=_wait(
                predicate=lambda: (
                    log.is_file() and f"port {port}" in log.read_text()
                ),
            ),
        )
        expect_true(
            condition=_wait(
                predicate=lambda: "[stderr] err" in log.read_text(),
            ),
        )
        expect_true(condition=bool(local.start_entrypoint.__name__))
    finally:
        pc.terminate_tree(pid=pid)
    other, fixed = local.start_entrypoint(path=script, log=log, port=4321)
    try:
        expect_equal(actual=fixed, expected=4321)
    finally:
        pc.terminate_tree(pid=other)


def test_serve_adopts_a_recorded_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A surviving recorded server is adopted instead of respawning.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    site: Path = tmp_path / "site"
    site.mkdir()
    monkeypatch.setattr(
        target=local,
        name="reuse_server",
        value=Constant(value=(4321, 8765)),
    )

    def spawn(**_options: object) -> Popen[str]:
        """Fail if a spawn is attempted.

        Args:
            _options: Ignored spawn options.

        Returns:
            Never reached; the function always fails.

        """
        pytest.fail(reason="spawn must not run")

    monkeypatch.setattr(target=local, name="_spawn_captured", value=spawn)
    pid, url, reused = local.serve(path=site, log=tmp_path / "s.log")
    expect_equal(
        actual=(pid, url, reused),
        expected=(4321, "http://127.0.0.1:8765/", True),
    )


def test_serve_retries_a_failed_spawn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A server that dies during spawn is replaced on the next attempt.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    site: Path = tmp_path / "site"
    site.mkdir()
    monkeypatch.setenv(
        name="XDG_CACHE_HOME",
        value=str(object=tmp_path / "cache"),
    )
    monkeypatch.setattr(
        target=local,
        name="reuse_server",
        value=Constant(value=None),
    )
    monkeypatch.setattr(
        target=local,
        name="free_port",
        value=Constant(value=9876),
    )
    monkeypatch.setattr(target=local, name="sleep", value=Constant(value=None))
    monkeypatch.setattr(
        target=local,
        name="terminate_tree",
        value=Constant(value=None),
    )
    attempts: list[int] = []

    def spawn(**_options: object) -> Popen[str]:
        """Return a dead child first, then a live one.

        Args:
            _options: Ignored spawn options.

        Returns:
            A simulated process handle.

        """
        attempts.append(1)
        if len(attempts) == 1:
            return cast(
                typ="Popen[str]",
                val=SimpleNamespace(
                    pid=111,
                    poll=Constant(value=1),
                    wait=Constant(value=1),
                ),
            )
        return cast(
            typ="Popen[str]",
            val=SimpleNamespace(
                pid=222,
                poll=Constant(value=None),
                wait=Constant(value=0),
            ),
        )

    monkeypatch.setattr(target=local, name="_spawn_captured", value=spawn)
    pid, url, reused = local.serve(path=site, log=tmp_path / "s.log")
    expect_equal(
        actual=(pid, url, reused),
        expected=(222, "http://127.0.0.1:9876/", False),
    )
    expect_equal(actual=len(attempts), expected=2)


def test_serve_reports_persistent_spawn_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After every spawn attempt dies, serve reports the startup error.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    site: Path = tmp_path / "site"
    site.mkdir()
    monkeypatch.setenv(
        name="XDG_CACHE_HOME",
        value=str(object=tmp_path / "cache"),
    )
    monkeypatch.setattr(
        target=local,
        name="reuse_server",
        value=Constant(value=None),
    )
    monkeypatch.setattr(
        target=local,
        name="free_port",
        value=Constant(value=9876),
    )
    monkeypatch.setattr(target=local, name="sleep", value=Constant(value=None))
    monkeypatch.setattr(
        target=local,
        name="terminate_tree",
        value=Constant(value=None),
    )
    attempts: list[int] = []

    def spawn(**_options: object) -> Popen[str]:
        """Return a child that exited immediately.

        Args:
            _options: Ignored spawn options.

        Returns:
            A simulated process handle.

        """
        attempts.append(1)
        return cast(
            typ="Popen[str]",
            val=SimpleNamespace(
                pid=111,
                poll=Constant(value=1),
                wait=Constant(value=1),
            ),
        )

    monkeypatch.setattr(target=local, name="_spawn_captured", value=spawn)
    with pytest.raises(
        expected_exception=RuntimeError,
        match="could not start",
    ):
        local.serve(path=site, log=tmp_path / "s.log")
    expect_equal(actual=len(attempts), expected=local.Constants.serve_retries)
    expect_false(condition=local.server_state_path(path=site).exists())
