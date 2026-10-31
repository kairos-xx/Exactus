# Copyright (c) 2026
"""Launch the Studio package with a bounded real service lifetime."""

from __future__ import annotations

from socket import socket
from subprocess import PIPE, Popen
from sys import executable
from time import monotonic, sleep
from typing import TYPE_CHECKING

import pytest

from exactus.packages.server import ports
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.record.studio import __main__ as studio

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.record.studio.service import StudioService


def test_studio_package_cli_stops_cleanly(tmp_path: Path) -> None:
    """The package CLI starts and stops its owned HTTP and browser worker.

    Args:
        tmp_path: Disposable project directory.

    """
    expect_equal(
        actual=studio.main(
            arguments=(
                "--project",
                str(object=tmp_path),
                "--headless",
                "--no-open",
                "--duration",
                "0.05",
                "--url",
                "about:blank",
            ),
        ),
        expected=0,
    )
    expect_true(condition=(tmp_path / ".studio").is_dir())


def test_studio_editor_link_and_shutdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The launch opens its authorized editor URL and returns a stopped host.

    Args:
        tmp_path: Disposable project directory.
        monkeypatch: Capture the browser request without opening a user tab.

    """
    urls: list[str] = []

    class FakeSession:
        """Record the editor URL without launching a real browser."""

        @staticmethod
        def open(*, url: str) -> None:
            """Capture the requested editor URL.

            Args:
                url: Authorized editor URL.

            """
            urls.append(url)

        @staticmethod
        def wait_closed(*, timeout: float | None = None) -> bool:
            """Report the simulated browser as closed.

            Args:
                timeout: Maximum wait, ignored by the fake.

            Returns:
                True because the fake browser closes immediately.

            """
            return timeout is not None

        def close(self) -> None:
            """Release nothing; the fake owns no browser."""

    monkeypatch.setattr(
        target=studio,
        name="BrowserSession",
        value=FakeSession,
    )
    service: StudioService = studio.serve(
        options=studio.StudioLaunch(
            root=tmp_path,
            headless=True,
            window=True,
            duration_seconds=0.05,
        ),
    )
    expect_equal(actual=urls, expected=[service.url])
    expect_false(condition=service.running)


@pytest.mark.parametrize("duration", [0.0, -1.0])
def test_studio_rejects_invalid_duration(
    tmp_path: Path,
    duration: float,
) -> None:
    """Invalid lifetimes fail before creating any service resources.

    Args:
        tmp_path: Disposable project directory.
        duration: Nonpositive session duration.

    """
    with pytest.raises(expected_exception=ValueError, match="positive"):
        studio.serve(
            options=studio.StudioLaunch(
                root=tmp_path,
                duration_seconds=duration,
            ),
        )
    expect_false(condition=(tmp_path / ".studio").exists())


def test_studio_replaces_previous_package_launcher(tmp_path: Path) -> None:
    """A second launch gracefully releases the first launch's fixed port.

    Args:
        tmp_path: Disposable project directory.

    """
    with socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port: int = listener.getsockname()[1]
    process: Popen[str] = Popen(
        args=(
            executable,
            "-m",
            "exactus.tools.record.studio",
            "--project",
            str(object=tmp_path),
            "--port",
            str(object=port),
            "--headless",
            "--no-open",
            "--duration",
            "30",
        ),
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )
    try:
        deadline: float = monotonic() + 15
        while not ports.listening(port=port) and monotonic() < deadline:
            sleep(0.05)
        expect_true(condition=ports.listening(port=port))
        expect_equal(
            actual=ports.listener_owner(
                port=port,
                module="exactus.tools.record.studio",
            ),
            expected=process.pid,
        )
        service: StudioService = studio.serve(
            options=studio.StudioLaunch(
                root=tmp_path,
                port=port,
                headless=True,
                open_editor=False,
                duration_seconds=0.05,
            ),
        )
        expect_false(condition=service.running)
        expect_equal(actual=process.wait(timeout=5), expected=0)
    finally:
        if process.poll() is None:
            process.kill()
        _ = process.communicate(timeout=5)


def test_studio_preserves_unrelated_listener() -> None:
    """A busy port must not authorize stopping an unrelated process."""
    with socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port: int = listener.getsockname()[1]
        with pytest.raises(expected_exception=OSError, match="not stopped"):
            ports.replace_listener(
                port=port,
                module="exactus.tools.record.studio",
            )
        expect_true(condition=ports.listening(port=port))


def test_studio_cli_maps_launch_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Map URL, port, duration and window flags into one launch object.

    Args:
        tmp_path: Disposable project directory.
        monkeypatch: Capture launch options without starting a service.

    """
    seen: list[studio.StudioLaunch] = []
    window_calls: list[tuple[bool | None, Path]] = []

    def capture(*, options: studio.StudioLaunch) -> None:
        """Record parsed launch options.

        Args:
            options: Launch settings built from CLI arguments.

        """
        seen.append(options)

    def window(*, flag: bool | None, start: Path) -> bool:
        """Record window resolution inputs.

        Args:
            flag: Explicit CLI window setting.
            start: Project used for config discovery.

        Returns:
            Explicit window setting.

        """
        window_calls.append((flag, start))
        return flag is True

    monkeypatch.setattr(target=studio, name="serve", value=capture)
    monkeypatch.setattr(target=studio, name="resolve_window", value=window)
    expect_equal(
        actual=studio.main(
            arguments=(
                "--project",
                str(object=tmp_path),
                "--port",
                "8123",
                "--url",
                "https://example.test/app",
                "--duration",
                "2.5",
                "--window",
                "--no-open",
            ),
        ),
        expected=0,
    )
    expect_equal(
        actual=seen,
        expected=[
            studio.StudioLaunch(
                root=tmp_path,
                port=8123,
                open_editor=False,
                window=True,
                target_url="https://example.test/app",
                duration_seconds=2.5,
            ),
        ],
    )
    expect_equal(actual=window_calls, expected=[(True, tmp_path)])


def test_the_test_browser_has_no_window_unless_asked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run headless by default so the Browser panel is the only view.

    Args:
        tmp_path: Disposable project directory.
        monkeypatch: Capture the launch options instead of serving.

    """
    seen: list[studio.StudioLaunch] = []

    def capture(*, options: studio.StudioLaunch) -> None:
        """Record the options the command line produced.

        Args:
            options: Launch settings built from the arguments.

        """
        seen.append(options)

    monkeypatch.setattr(target=studio, name="serve", value=capture)
    base: tuple[str, ...] = ("--project", str(object=tmp_path), "--no-open")
    expect_equal(actual=studio.main(arguments=base), expected=0)
    expect_equal(actual=studio.main(arguments=(*base, "--headed")), expected=0)
    # The old flag still works for existing scripts.
    expect_equal(
        actual=studio.main(arguments=(*base, "--headless")),
        expected=0,
    )
    expect_equal(
        actual=[launch.headless for launch in seen],
        expected=[True, False, True],
    )
    expect_true(condition=studio.StudioLaunch(root=tmp_path).headless)
