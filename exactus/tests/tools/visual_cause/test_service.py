# Copyright (c) 2026
"""Local page services reuse remote URLs and own the servers they start."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_none,
    expect_true,
)
from exactus.tools.visual_cause import service as service_module
from exactus.tools.visual_cause.service import LocalServices, ServedPage

if TYPE_CHECKING:
    from pathlib import Path


class FakeServers:
    """Record server starts, readiness probes and terminations."""

    def __init__(self, *, ready: bool, reused: bool) -> None:
        """Configure the outcome of every fake server.

        Args:
            ready: Whether the readiness probe succeeds.
            reused: Whether started servers count as adopted.

        """
        self.ready: bool = ready
        self.reused: bool = reused
        self.started: list[Path] = []
        self.terminated: list[int] = []

    def serve(self, *, path: Path, log: Path) -> tuple[int, str, bool]:
        """Pretend to start a server for one directory.

        Args:
            path: Directory to serve.
            log: Log destination, ignored.

        Returns:
            Process id, base URL and whether it was adopted.

        """
        del log
        self.started.append(path)
        pid: int = 100 + len(self.started)
        return (pid, f"http://127.0.0.1:{pid}/", self.reused)

    def wait_ready(self, *, url: str, pid: int, timeout: float) -> bool:
        """Report the configured readiness.

        Args:
            url: Probed URL, ignored.
            pid: Server process id, ignored.
            timeout: Probe timeout, ignored.

        Returns:
            The configured readiness.

        """
        del url, pid, timeout
        return self.ready

    def terminate(self, *, pid: int) -> None:
        """Record one terminated process.

        Args:
            pid: Terminated process id.

        """
        self.terminated.append(pid)


def _install(*, monkeypatch: pytest.MonkeyPatch, fake: FakeServers) -> None:
    """Route the service module through a fake server backend.

    Args:
        monkeypatch: Pytest patching helper.
        fake: Backend recording every call.

    """
    monkeypatch.setattr(target=service_module, name="serve", value=fake.serve)
    monkeypatch.setattr(
        target=service_module,
        name="wait_ready",
        value=fake.wait_ready,
    )
    monkeypatch.setattr(
        target=service_module,
        name="terminate_tree",
        value=fake.terminate,
    )


def test_remote_url_is_used_directly(tmp_path: Path) -> None:
    """A URL needs no server and has no log.

    Args:
        tmp_path: Per-test directory.

    """
    with LocalServices(
        artifacts=tmp_path / "logs",
        timeout_ms=1000,
    ) as services:
        page: ServedPage = services.page(
            url="https://example.com/x",
            html=None,
            landing="index.html",
            label="a",
        )
    expect_equal(actual=page.url, expected="https://example.com/x")
    expect_none(value=page.log)
    expect_true(condition=(tmp_path / "logs").is_dir())


def test_missing_and_absent_sources_are_errors(tmp_path: Path) -> None:
    """Each unusable source raises before any server starts.

    Args:
        tmp_path: Per-test directory.

    """
    folder: Path = tmp_path / "site"
    folder.mkdir()
    with LocalServices(
        artifacts=tmp_path / "logs",
        timeout_ms=1000,
    ) as services:
        with pytest.raises(expected_exception=ValueError, match="missing"):
            _ = services.page(url=None, html=None, landing="i.html", label="a")
        with pytest.raises(
            expected_exception=FileNotFoundError,
            match="not found",
        ):
            _ = services.page(
                url=None,
                html=tmp_path / "nope",
                landing="i.html",
                label="a",
            )
        with pytest.raises(
            expected_exception=FileNotFoundError,
            match="landing page",
        ):
            _ = services.page(
                url=None,
                html=folder,
                landing="index.html",
                label="a",
            )


def test_servers_are_shared_per_directory_and_terminated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One server per directory; exit terminates only owned processes.

    Args:
        tmp_path: Per-test directory.
        monkeypatch: Pytest patching helper.

    """
    fake: FakeServers = FakeServers(ready=True, reused=False)
    _install(monkeypatch=monkeypatch, fake=fake)
    site: Path = tmp_path / "site"
    site.mkdir()
    _ = (site / "index.html").write_text(data="<p>", encoding="utf-8")
    _ = (site / "a b.html").write_text(data="<p>", encoding="utf-8")
    with LocalServices(
        artifacts=tmp_path / "logs",
        timeout_ms=1000,
    ) as services:
        first: ServedPage = services.page(
            url=None,
            html=site,
            landing="index.html",
            label="a",
        )
        second: ServedPage = services.page(
            url=None,
            html=site / "a b.html",
            landing="ignored.html",
            label="b",
        )
    expect_equal(actual=len(fake.started), expected=1)
    expect_equal(actual=first.url, expected="http://127.0.0.1:101/index.html")
    expect_equal(actual=second.url, expected="http://127.0.0.1:101/a%20b.html")
    expect_in(member="a-server.log", container=str(object=first.log))
    expect_equal(actual=fake.terminated, expected=[101])


def test_adopted_servers_are_never_terminated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reused server stays running when the registry closes.

    Args:
        tmp_path: Per-test directory.
        monkeypatch: Pytest patching helper.

    """
    fake: FakeServers = FakeServers(ready=True, reused=True)
    _install(monkeypatch=monkeypatch, fake=fake)
    page: Path = tmp_path / "page.html"
    _ = page.write_text(data="<p>", encoding="utf-8")
    with LocalServices(
        artifacts=tmp_path / "logs",
        timeout_ms=1000,
    ) as services:
        _ = services.page(url=None, html=page, landing="x", label="a")
    expect_equal(actual=fake.terminated, expected=[])


def test_server_that_never_becomes_ready_is_stopped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unready owned server is terminated and reported.

    Args:
        tmp_path: Per-test directory.
        monkeypatch: Pytest patching helper.

    """
    fake: FakeServers = FakeServers(ready=False, reused=False)
    _install(monkeypatch=monkeypatch, fake=fake)
    page: Path = tmp_path / "page.html"
    _ = page.write_text(data="<p>", encoding="utf-8")
    registry: LocalServices = LocalServices(
        artifacts=tmp_path / "logs",
        timeout_ms=1000,
    )
    with (
        registry as services,
        pytest.raises(expected_exception=RuntimeError, match="ready"),
    ):
        _ = services.page(url=None, html=page, landing="x", label="a")
    expect_equal(actual=fake.terminated, expected=[101])
